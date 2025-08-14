import os
import json

import re
import struct
import sys
import importlib.util
import types
from typing import Dict, List

import numpy as np

try:
    import trimesh
except ImportError as e:
    raise SystemExit("Please install trimesh: pip install trimesh") from e

try:
    import pyassimp
except ImportError:
    pyassimp = None



# Prefer the robust parser from the packaged `xfile` module if available
ExternalXFileParser = None
try:
	# Ensure package path contains this directory so `xfile` is importable
	base_dir = os.path.dirname(os.path.abspath(__file__))
	if base_dir not in sys.path:
		sys.path.insert(0, base_dir)
	from xfile.xfile_parser import XFileParser as ExternalXFileParser
except Exception as _x_import_err:
	print(f"Falling back to inline XFileParser, external import failed: {_x_import_err}")

# Try loading robust parser by directly loading modules from the xfile folder without executing its __init__.py
if ExternalXFileParser is None:
	try:
		xfile_dir = os.path.join(base_dir, 'xfile')
		if os.path.isdir(xfile_dir):
			# Create a synthetic package 'xfile' to satisfy relative imports
			if 'xfile' not in sys.modules:
				pkg = types.ModuleType('xfile')
				pkg.__path__ = [xfile_dir]
				sys.modules['xfile'] = pkg
			# Load helper first
			spec_h = importlib.util.spec_from_file_location('xfile.xfile_helper', os.path.join(xfile_dir, 'xfile_helper.py'))
			mod_h = importlib.util.module_from_spec(spec_h)
			sys.modules['xfile.xfile_helper'] = mod_h
			spec_h.loader.exec_module(mod_h)
			# Load parser
			spec_p = importlib.util.spec_from_file_location('xfile.xfile_parser', os.path.join(xfile_dir, 'xfile_parser.py'))
			mod_p = importlib.util.module_from_spec(spec_p)
			sys.modules['xfile.xfile_parser'] = mod_p
			spec_p.loader.exec_module(mod_p)
			ExternalXFileParser = getattr(mod_p, 'XFileParser', None)
			if ExternalXFileParser is None:
				raise ImportError('XFileParser class not found in loaded module')
			print('Loaded robust XFileParser via direct module loading')
	except Exception as _x_direct_err:
		print(f"Direct xfile loader failed: {_x_direct_err}")

# DirectX .X file parser classes (copied from xfile folder to avoid import issues)
class Face:
    """Helper structure representing a XFile mesh face"""
    def __init__(self):
        self.indices = []


class Mesh:
    """Helper structure to represent an XFile mesh"""
    def __init__(self):
        self.positions = []
        self.posFaces = []
        self.normals = []
        self.normalFaces = []
        self.numTextures = 0
        self.texCoords = [[], []]
        self.numColorSets = 0
        self.colors = [[]]
        self.faceMaterials = []
        self.materials = []
        self.bones = []


class Node:
    """Helper structure to represent a XFile frame"""
    def __init__(self, parent=None):
        self.name = ''
        self.trafoMatrix = ()
        self.parent = parent
        self.children = []
        self.meshes = []


class Scene:
    """Helper structure analogue to aiScene"""
    def __init__(self):
        self.rootNode = None
        self.globalMeshes = []
        self.globalMaterials = []
        self.anims = []
        self.animTicksPerSecond = 0


class XFileParser:
    """Complete DirectX .X file parser for binary and text formats"""
    
    def __init__(self, buffer: bytes):
        self.buffer = buffer
        self.p = 0
        self.end = len(buffer)
        self.isBinaryFormat = False
        self.binaryFloatSize = 32
        self.binaryNumCount = 0
        self.lineNumber = 0
        
        # Check header
        if self.buffer[self.p:self.p+4] != b'xof ':
            raise ValueError('Header mismatch, file is not an XFile.')
        
        # Read version
        self.majorVersion = int(self.buffer[4:6])
        self.minorVersion = int(self.buffer[6:8])
        
        # Check format
        if self.buffer[8:12] == b'bin ':
            self.isBinaryFormat = True
        elif self.buffer[8:12] == b'txt ':
            self.isBinaryFormat = False
        else:
            raise ValueError(f'Unsupported xfile format {self.buffer[8:12]}')
        
        # Float size
        self.binaryFloatSize = int(self.buffer[12:16])
        if self.binaryFloatSize != 32 and self.binaryFloatSize != 64:
            raise ValueError(f'Unknown float size {self.binaryFloatSize} specified in xfile header.')
        
        self.p += 16
        
        self.scene = Scene()
        self.ParseFile()
    
    def ParseFile(self):
        """Parse the file structure"""
        running = True
        while running:
            objectName = self.GetNextToken()
            if not objectName:
                break
            if objectName == b'Mesh':
                mesh = self.ParseDataObjectMesh()
                self.scene.globalMeshes.append(mesh)
            elif objectName == b'Frame':
                self.ParseDataObjectFrame()
            elif objectName == b'}':
                break
            else:
                self.ParseUnknownDataObject()
    
    def ParseDataObjectFrame(self, parent=None):
        """Parse a frame object"""
        name = self.ReadHeadOfDataObject()
        node = Node(parent)
        node.name = name.decode() if name else ''
        
        if parent:
            parent.children.append(node)
        else:
            if self.scene.rootNode:
                if self.scene.rootNode.name != '$dummy_root':
                    exroot = self.scene.rootNode
                    self.scene.rootNode = Node()
                    self.scene.rootNode.children.append(exroot)
                    exroot.parent = self.scene.rootNode
                self.scene.rootNode.children.append(node)
                node.parent = self.scene.rootNode
            else:
                self.scene.rootNode = node
        
        running = True
        while running:
            objectName = self.GetNextToken()
            if not objectName:
                break
            if objectName == b'}':
                break
            elif objectName == b'Frame':
                self.ParseDataObjectFrame(node)
            elif objectName == b'Mesh':
                mesh = self.ParseDataObjectMesh()
                node.meshes.append(mesh)
            else:
                self.ParseUnknownDataObject()
    
    def ParseDataObjectMesh(self) -> Mesh:
        """Parse a mesh object"""
        mesh = Mesh()
        name = self.ReadHeadOfDataObject()
        
        # Read vertex count
        numVertices = self.ReadInt()
        
        # Read vertices
        for a in range(numVertices):
            mesh.positions.append(self.ReadVector3())
        
        # Read position faces
        numPosFaces = self.ReadInt()
        mesh.posFaces = []
        for a in range(numPosFaces):
            numIndices = self.ReadInt()
            if numIndices < 3:
                raise ValueError(f"Invalid index count {numIndices} for face {a}")
            
            # Read indices
            face = Face()
            face.indices = []
            for b in range(numIndices):
                face.indices.append(self.ReadInt())
            mesh.posFaces.append(face)
            self.TestForSeparator()
        
        # Parse other mesh data
        running = True
        while running:
            objectName = self.GetNextToken()
            if not objectName:
                break
            elif objectName == b'}':
                break
            elif objectName == b'MeshNormals':
                self.ParseDataObjectMeshNormals(mesh)
            elif objectName == b'MeshTextureCoords':
                self.ParseDataObjectMeshTextureCoords(mesh)
            elif objectName == b'MeshMaterialList':
                self.ParseDataObjectMeshMaterialList(mesh)
            else:
                self.ParseUnknownDataObject()
        
        return mesh
    
    def ParseDataObjectMeshNormals(self, mesh: Mesh):
        """Parse mesh normals"""
        self.ReadHeadOfDataObject()
        numNormals = self.ReadInt()
        
        for a in range(numNormals):
            mesh.normals.append(self.ReadVector3())
        
        numFaces = self.ReadInt()
        for a in range(numFaces):
            numIndices = self.ReadInt()
            face = Face()
            face.indices = []
            for b in range(numIndices):
                face.indices.append(self.ReadInt())
            mesh.normalFaces.append(face)
            self.TestForSeparator()
        
        self.CheckForClosingBrace()
    
    def ParseDataObjectMeshTextureCoords(self, mesh: Mesh):
        """Parse mesh texture coordinates"""
        self.ReadHeadOfDataObject()
        numCoords = self.ReadInt()
        
        coords = [0] * numCoords
        for a in range(numCoords):
            coords[a] = self.ReadVector2()
        
        mesh.texCoords = coords
        mesh.numTextures += 1
        self.CheckForClosingBrace()
    
    def ParseDataObjectMeshMaterialList(self, mesh: Mesh):
        """Parse mesh material list"""
        self.ReadHeadOfDataObject()
        numMaterials = self.ReadInt()
        numMatIndices = self.ReadInt()
        
        for a in range(numMatIndices):
            mesh.faceMaterials.append(self.ReadInt())
        
        # Read following data objects
        running = True
        while running:
            objectName = self.GetNextToken()
            if not objectName:
                break
            elif objectName == b'}':
                break
            elif objectName == b'Material':
                # Skip material for now
                self.ParseUnknownDataObject()
            else:
                self.ParseUnknownDataObject()
    
    def GetNextToken(self) -> bytes:
        """Get next parseable token"""
        if self.isBinaryFormat:
            return self.GetNextTokenBinary()
        else:
            return self.GetNextTokenText()
    
    def GetNextTokenBinary(self) -> bytes:
        """Get next token from binary format"""
        if self.end - self.p < 2:
            return b''
        
        tok = self.ReadBinWord()
        
        if tok == 1:  # NAME token
            if self.end - self.p < 4:
                return b''
            l = self.ReadBinDWord()
            if l < 0 or self.end - self.p < l:
                return b''
            s = self.buffer[self.p:self.p+l]
            self.p += l
            return s
        elif tok == 2:  # STRING token
            if self.end - self.p < 4:
                return b''
            l = self.ReadBinDWord()
            if self.end - self.p < l:
                return b''
            s = self.buffer[self.p:self.p+l]
            self.p += l + 2
            return s
        elif tok == 3:  # INTEGER
            self.p += 4
            return b'<integer>'
        elif tok == 5:  # GUID
            self.p += 16
            return b'<guid>'
        elif tok == 6:  # INTEGER_LIST
            if self.end - self.p < 4:
                return b''
            l = self.ReadBinDWord()
            self.p += l * 4
            return b'<int_list>'
        elif tok == 7:  # FLOAT_LIST
            if self.end - self.p < 4:
                return b''
            l = self.ReadBinDWord()
            self.p += l * (self.binaryFloatSize // 8)
            return b'<flt_list>'
        elif tok == 0x0a:  # OBRACE
            return b'{'
        elif tok == 0x0b:  # CBRACE
            return b'}'
        elif tok == 0x0c:  # OPAREN
            return b'('
        elif tok == 0x0d:  # CPAREN
            return b')'
        elif tok == 0x0e:  # OBRACKET
            return b'['
        elif tok == 0x0f:  # CBRACKET
            return b']'
        elif tok == 0x10:  # OANGLE
            return b'<'
        elif tok == 0x11:  # CANGLE
            return b'>'
        elif tok == 0x12:  # DOT
            return b'.'
        elif tok == 0x13:  # COMMA
            return b','
        elif tok == 0x14:  # SEMICOLON
            return b';'
        elif tok == 0x1f:  # TEMPLATE
            return b'template'
        elif tok == 0x28:  # WORD
            return b'WORD'
        elif tok == 0x29:  # DWORD
            return b'DWORD'
        elif tok == 0x2a:  # FLOAT
            return b'FLOAT'
        elif tok == 0x2b:  # DOUBLE
            return b'DOUBLE'
        elif tok == 0x2c:  # CHAR
            return b'CHAR'
        elif tok == 0x2d:  # UCHAR
            return b'UCHAR'
        elif tok == 0x2e:  # SWORD
            return b'SWORD'
        elif tok == 0x2f:  # SDWORD
            return b'SDWORD'
        elif tok == 0x30:  # VOID
            return b'void'
        elif tok == 0x31:  # STRING
            return b'string'
        elif tok == 0x32:  # UNICODE
            return b'unicode'
        elif tok == 0x33:  # CSTRING
            return b'cstring'
        elif tok == 0x34:  # ARRAY
            return b'array'
        else:
            return b'<unknown>'
    
    def GetNextTokenText(self) -> bytes:
        """Get next token from text format"""
        # Skip whitespace
        while self.p < self.end and self.buffer[self.p] in b' \r\n\t':
            if self.buffer[self.p] == b'\n'[0]:
                self.lineNumber += 1
            self.p += 1
        
        if self.p >= self.end:
            return b''
        
        # Read token
        s = b''
        while self.p < self.end and not self.buffer[self.p] in b' \r\n\t{};,()[]<>':
            s += self.buffer[self.p:self.p+1]
            self.p += 1
        
        return s
    
    def ReadHeadOfDataObject(self) -> bytes:
        """Read header of data object including opening brace"""
        nameOrBrace = self.GetNextToken()
        if nameOrBrace != b'{':
            if self.GetNextToken() != b'{':
                raise ValueError("Opening brace expected.")
            return nameOrBrace
        return b''
    
    def CheckForClosingBrace(self):
        """Check for closing curly brace"""
        if self.GetNextToken() != b'}':
            raise ValueError("Closing brace expected.")
    
    def TestForSeparator(self):
        """Test and possibly consume a separator character"""
        if self.isBinaryFormat:
            return
        
        while self.p < self.end and self.buffer[self.p] in b' \r\n\t':
            self.p += 1
        
        if self.p < self.end and self.buffer[self.p] in b';,':
            self.p += 1
    
    def FindNextNoneWhiteSpace(self):
        """Find next non-whitespace character"""
        while self.p < self.end and self.buffer[self.p] in b' \r\n\t':
            if self.buffer[self.p] == b'\n'[0]:
                self.lineNumber += 1
            self.p += 1
    
    def CheckForSeparator(self):
        """Check for separator character"""
        if self.isBinaryFormat:
            return
        
        while self.p < self.end and self.buffer[self.p] in b' \r\n\t':
            self.p += 1
        
        if self.p < self.end and self.buffer[self.p] in b';,':
            self.p += 1
    
    def ReadBinWord(self) -> int:
        """Read binary word (16-bit)"""
        if self.end - self.p < 2:
            raise ValueError("Unexpected end of file")
        tmp = struct.unpack_from('<H', self.buffer, self.p)[0]
        self.p += 2
        return tmp
    
    def ReadBinDWord(self) -> int:
        """Read binary dword (32-bit)"""
        if self.end - self.p < 4:
            raise ValueError("Unexpected end of file")
        tmp = struct.unpack_from('<I', self.buffer, self.p)[0]
        self.p += 4
        return tmp
    
    def ReadInt(self) -> int:
        """Read integer value"""
        if self.isBinaryFormat:
            if self.binaryNumCount == 0 and self.end - self.p >= 2:
                tmp = self.ReadBinWord()
                if tmp == 0x06 and self.end - self.p >= 4:
                    self.binaryNumCount = self.ReadBinDWord()
                else:
                    self.binaryNumCount = 1
            
            self.binaryNumCount -= 1
            if self.end - self.p >= 4:
                return self.ReadBinDWord()
            else:
                self.p = self.end
                return 0
        else:
            self.FindNextNoneWhiteSpace()
            
            # Check preceding minus sign
            isNegative = False
            if self.p < self.end and self.buffer[self.p:self.p+1] == b'-':
                isNegative = True
                self.p += 1
            
            # At least one digit expected
            if self.p >= self.end or not self.buffer[self.p:self.p+1].isdigit():
                raise ValueError('Number expected.')
            
            # Read digits
            number = 0
            while self.p < self.end:
                if not self.buffer[self.p:self.p+1].isdigit():
                    break
                number = number * 10 + int(self.buffer[self.p:self.p+1])
                self.p += 1
            
            self.CheckForSeparator()
            if isNegative:
                return -number
            else:
                return number
    
    def ReadFloat(self) -> float:
        """Read float value"""
        if self.isBinaryFormat:
            if self.binaryNumCount == 0 and self.end - self.p >= 2:
                tmp = self.ReadBinWord()
                if tmp == 0x07 and self.end - self.p >= 4:
                    self.binaryNumCount = self.ReadBinDWord()
                else:
                    self.binaryNumCount = 1
            
            self.binaryNumCount -= 1
            if self.binaryFloatSize == 8:
                if self.end - self.p >= 8:
                    result = struct.unpack_from('<d', self.buffer, self.p)[0]
                    self.p += 8
                    return result
                else:
                    self.p = self.end
                    return 0.0
            else:
                if self.end - self.p >= 4:
                    result = struct.unpack_from('<f', self.buffer, self.p)[0]
                    self.p += 4
                    return result
                else:
                    self.p = self.end
                    return 0.0
        else:
            # Text version
            self.FindNextNoneWhiteSpace()
            
            # Check for various special strings
            if self.p + 9 <= self.end and self.buffer[self.p:self.p+9] == b'-1.#IND00':
                self.p += 9
                self.CheckForSeparator()
                return 0.0
            elif self.p + 8 <= self.end and self.buffer[self.p:self.p+8] == b'1.#IND00':
                self.p += 8
                self.CheckForSeparator()
                return 0.0
            elif self.p + 8 <= self.end and self.buffer[self.p:self.p+8] == b'1.#QNAN0':
                self.p += 8
                self.CheckForSeparator()
                return 0.0
            
            # Read number
            digitStart = self.p
            digitEnd = self.p
            notSplitChar = [b'0', b'1', b'2', b'3', b'4', b'5',
                            b'6', b'7', b'8', b'9', b'+', b'.', b'-', b'e', b'E']
            
            while self.p < self.end:
                c = self.buffer[self.p:self.p+1]
                if c in notSplitChar:
                    digitEnd = self.p
                    self.p += 1
                else:
                    break
            
            if digitStart == digitEnd:
                raise ValueError('Number expected.')
            
            tmp = self.buffer[digitStart:digitEnd+1]
            result = float(tmp)
            self.CheckForSeparator()
            return result
    
    def ReadVector2(self) -> tuple[float, float]:
        """Read 2D vector"""
        x = self.ReadFloat()
        y = self.ReadFloat()
        self.TestForSeparator()
        return (x, y)
    
    def ReadVector3(self) -> tuple[float, float, float]:
        """Read 3D vector"""
        x = self.ReadFloat()
        y = self.ReadFloat()
        z = self.ReadFloat()
        self.TestForSeparator()
        return (x, y, z)
    
    def ParseUnknownDataObject(self):
        """Parse unknown data object by finding matching braces"""
        counter = 1
        while counter > 0:
            t = self.GetNextToken()
            if not t:
                raise ValueError("Unexpected end of file while parsing unknown segment.")
            if t == b'{':
                counter += 1
            elif t == b'}':
                counter -= 1
    
    def getImportedData(self) -> Scene:
        """Get the imported scene data"""
        return self.scene


def parse_directx_x_file_with_materials(file_path: str) -> dict:
    """Parse DirectX .X files with material/texture information"""
    print(f"Attempting to parse DirectX .X file with materials: {file_path}")
    
    try:
        # Read the file into memory
        with open(file_path, 'rb') as f:
            buffer = f.read()
        
        # Choose parser: prefer external robust parser if import succeeded
        ParserClass = ExternalXFileParser or XFileParser
        print(f"Using parser class: {ParserClass.__module__}.{ParserClass.__name__}")
        parser = ParserClass(buffer)
        scene = parser.getImportedData()
        
        # Extract mesh data from the parsed scene
        vertices = []
        faces = []
        materials = []
        textures = []
        
        # Extract materials from meshes (not scene.globalMaterials)
        # We'll collect materials from all meshes
        mesh_materials = []
        
        # Get meshes from the scene
        if scene.globalMeshes:
            # Use the first mesh found
            mesh = scene.globalMeshes[0]
            
            # Extract materials from this mesh
            for i, mat in enumerate(mesh.materials):
                material_data = {
                    'name': getattr(mat, 'name', f'Material_{i}'),
                    'diffuse': list(getattr(mat, 'diffuse', [1.0, 1.0, 1.0, 1.0])),
                    'specular': list(getattr(mat, 'specular', [0.0, 0.0, 0.0])),
                    'emissive': list(getattr(mat, 'emissive', [0.0, 0.0, 0.0])),
                    'power': getattr(mat, 'specularExponent', 1.0),
                    'textures': []
                }
                
                # Extract texture filenames from material
                if hasattr(mat, 'textures'):
                    for tex in mat.textures:
                        if hasattr(tex, 'name'):
                            # Convert bytes to string if needed
                            tex_name = tex.name
                            if isinstance(tex_name, bytes):
                                tex_name = tex_name.decode('utf-8')
                            material_data['textures'].append(tex_name)
                            if tex_name not in textures:
                                textures.append(tex_name)
                
                materials.append(material_data)
                print(f"Found material {i}: {material_data['name']} with {len(material_data['textures'])} textures")
                if material_data['textures']:
                    print(f"  Textures: {material_data['textures']}")
            
            # Extract vertices
            for pos in mesh.positions:
                vertices.append([pos[0], pos[1], pos[2]])
            
            # Extract UV coordinates if available
            uv_coords = []
            if hasattr(mesh, 'texCoords') and mesh.texCoords:
                for uv in mesh.texCoords:
                    uv_coords.append([uv[0], uv[1]])
                print(f"Extracted {len(uv_coords)} UV coordinates")
            
            # Extract faces and track original face indices for material mapping
            face_to_original = []  # Maps triangulated face index to original face index
            original_face_idx = 0
            for face in mesh.posFaces:
                if len(face.indices) >= 3:
                    # Convert to triangles if needed
                    if len(face.indices) == 3:
                        faces.append(face.indices)
                        face_to_original.append(original_face_idx)
                    elif len(face.indices) > 3:
                        # Simple triangulation (fan)
                        for j in range(1, len(face.indices) - 1):
                            faces.append([face.indices[0], face.indices[j], face.indices[j+1]])
                            face_to_original.append(original_face_idx)
                original_face_idx += 1
        
        # If no global meshes, check frame nodes
        elif scene.rootNode:
            face_to_original = []
            def extract_meshes_from_node(node):
                nonlocal vertices, faces, materials, textures, uv_coords, face_to_original
                
                # Extract meshes from this node
                for mesh in node.meshes:
                    # Extract materials from this mesh
                    for i, mat in enumerate(mesh.materials):
                        material_data = {
                            'name': getattr(mat, 'name', f'Material_{len(materials)}'),
                            'diffuse': list(getattr(mat, 'diffuse', [1.0, 1.0, 1.0, 1.0])),
                            'specular': list(getattr(mat, 'specular', [0.0, 0.0, 0.0])),
                            'emissive': list(getattr(mat, 'emissive', [0.0, 0.0, 0.0])),
                            'power': getattr(mat, 'specularExponent', 1.0),
                            'textures': []
                        }
                        
                        # Extract texture filenames from material
                        if hasattr(mat, 'textures'):
                            for tex in mat.textures:
                                if hasattr(tex, 'name'):
                                    # Convert bytes to string if needed
                                    tex_name = tex.name
                                    if isinstance(tex_name, bytes):
                                        tex_name = tex_name.decode('utf-8')
                                    material_data['textures'].append(tex_name)
                                    if tex_name not in textures:
                                        textures.append(tex_name)
                        
                        materials.append(material_data)
                        print(f"Found material {len(materials)-1}: {material_data['name']} with {len(material_data['textures'])} textures")
                        if material_data['textures']:
                            print(f"  Textures: {material_data['textures']}")
                    
                    # Extract vertices
                    for pos in mesh.positions:
                        vertices.append([pos[0], pos[1], pos[2]])
                    
                    # Extract UV coordinates if available
                    if hasattr(mesh, 'texCoords') and mesh.texCoords:
                        for uv in mesh.texCoords:
                            uv_coords.append([uv[0], uv[1]])
                        print(f"Extracted {len(mesh.texCoords)} UV coordinates from frame node")
                    
                    # Extract faces and track original face indices
                    original_face_idx = len(face_to_original)
                    for face in mesh.posFaces:
                        if len(face.indices) >= 3:
                            # Convert to triangles if needed
                            if len(face.indices) == 3:
                                faces.append(face.indices)
                                face_to_original.append(original_face_idx)
                            elif len(face.indices) > 3:
                                # Simple triangulation (fan)
                                for j in range(1, len(face.indices) - 1):
                                    faces.append([face.indices[0], face.indices[j], face.indices[j+1]])
                                    face_to_original.append(original_face_idx)
                        original_face_idx += 1
                
                # Recursively check children
                for child in node.children:
                    extract_meshes_from_node(child)
            
            extract_meshes_from_node(scene.rootNode)
        
        if not vertices or not faces:
            raise ValueError("Could not extract vertices or faces from .X file")
        
        print(f"Parsed {len(vertices)} vertices, {len(faces)} faces, {len(materials)} materials, {len(textures)} textures from .X file")
        
        # Create trimesh
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        
        # Add UV coordinates if available
        if uv_coords and len(uv_coords) == len(vertices):
            mesh.visual.uv = np.array(uv_coords)
            print(f"Applied {len(uv_coords)} UV coordinates to mesh")
        
        # Extract face materials for multi-material splitting
        face_materials = []
        if scene.globalMeshes and hasattr(scene.globalMeshes[0], 'faceMaterials'):
            original_face_materials = scene.globalMeshes[0].faceMaterials
            # Map original face materials to triangulated faces
            if 'face_to_original' in locals() and face_to_original:
                face_materials = [original_face_materials[orig_idx] for orig_idx in face_to_original]
                print(f"Mapped {len(original_face_materials)} original face materials to {len(face_materials)} triangulated faces")
            else:
                face_materials = original_face_materials
                print(f"Using {len(face_materials)} face material assignments directly")
        
        return {
            'mesh': mesh,
            'materials': materials,
            'textures': textures,
            'uv_coords': uv_coords,
            'face_materials': face_materials
        }
        
    except Exception as e:
        print(f"XFileParser failed: {e}")
        raise


def parse_directx_x_file(file_path: str) -> trimesh.Trimesh:
    """Parse DirectX .X files using the integrated XFileParser (backward compatibility)"""
    result = parse_directx_x_file_with_materials(file_path)
    return result['mesh']


def load_mesh_with_materials(path: str) -> dict:
    """Load mesh with material and texture information"""
    print(f"Attempting to load mesh with materials: {path}")
    
    # Try DirectX .X parser first for .X files
    if path.lower().endswith('.x'):
        try:
            result = parse_directx_x_file_with_materials(path)
            print(f"Successfully parsed {path} as DirectX .X file with materials")
            return result
        except Exception as e:
            print(f"DirectX parser with materials failed: {e}")
    
    # Fallback to regular mesh loading (no materials)
    try:
        mesh = load_mesh(path)
        return {
            'mesh': mesh,
            'materials': [],
            'textures': []
        }
    except Exception as e:
        print(f"Failed to load mesh {path}: {e}")
        raise


def load_mesh(path: str) -> trimesh.Trimesh:
    """Load mesh without material information (backward compatibility)"""
    print(f"Attempting to load mesh: {path}")
    
    # Try DirectX .X parser first for .X files
    if path.lower().endswith('.x'):
        try:
            mesh = parse_directx_x_file(path)
            print(f"Successfully parsed {path} as DirectX .X file")
            return mesh
        except Exception as e:
            print(f"DirectX parser failed: {e}")
    
    # Attempt via trimesh directly
    try:
        mesh = trimesh.load(path, force='mesh')
        if isinstance(mesh, trimesh.Trimesh):

            print(f"Successfully loaded {path} as Trimesh")
            return mesh
        if hasattr(mesh, 'dump') and hasattr(mesh, 'geometry') and mesh.geometry:
            # Scene with geometries
            # merge into a single mesh
            parts = [g for g in mesh.geometry.values()]

            result = trimesh.util.concatenate(parts)
            print(f"Successfully loaded {path} as Scene with {len(parts)} geometries")
            return result
    except Exception as e:
        print(f"trimesh failed to load {path}: {e}")
    
    # Try pyassimp as last resort
    if pyassimp is None:

        print(f"pyassimp not available, cannot load {path}")
        raise RuntimeError(f"Failed to load mesh {path}. Install pyassimp for broader support.")


    print(f"Trying pyassimp for {path}")
    scene = pyassimp.load(path)
    try:
        meshes = []
        for m in scene.meshes:
            vertices = m.vertices.copy()
            faces = m.faces.copy()
            tm = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            meshes.append(tm)
        if not meshes:
            raise RuntimeError(f"No meshes in {path}")

        result = trimesh.util.concatenate(meshes)
        print(f"Successfully loaded {path} via pyassimp with {len(meshes)} meshes")
        return result
    finally:
        pyassimp.release(scene)



def merge_body_meshes(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Merge multiple body part meshes into a single unified mesh.
    This helps fill gaps between modular body parts.
    """
    if not meshes:
        return trimesh.Trimesh()
    
    if len(meshes) == 1:
        return meshes[0]
    
    # Combine all meshes
    combined = trimesh.util.concatenate(meshes)
    
    # Try to merge duplicate vertices to create a more unified mesh
    combined.merge_vertices()
    
    # Remove duplicate faces
    combined.remove_duplicate_faces()
    
    # Fill small holes if possible (this is experimental)
    try:
        combined.fill_holes()
    except:
        pass  # Fill holes might fail on complex geometry
    
    return combined


def split_mesh_by_materials(mesh_data: dict) -> List[dict]:
    """Split a mesh into separate meshes by material for proper GLTF multi-material support"""
    mesh = mesh_data['mesh']
    materials = mesh_data['materials']
    face_materials = mesh_data.get('face_materials', [])
    uv_coords = mesh_data.get('uv_coords', [])
    
    if not face_materials or len(face_materials) != len(mesh.faces):
        print("No face materials or mismatch, returning single mesh")
        return [mesh_data]
    
    # Group faces by material
    material_faces = {}
    for face_idx, mat_idx in enumerate(face_materials):
        if mat_idx not in material_faces:
            material_faces[mat_idx] = []
        material_faces[mat_idx].append(face_idx)
    
    print(f"Splitting mesh into {len(material_faces)} material groups")
    
    # Create separate meshes for each material
    split_meshes = []
    for mat_idx, face_indices in material_faces.items():
        if mat_idx >= len(materials):
            print(f"Warning: Material index {mat_idx} out of range, skipping")
            continue
            
        # Extract faces for this material
        faces_subset = mesh.faces[face_indices]
        
        # Find unique vertices used by these faces
        unique_vertices = np.unique(faces_subset.flatten())
        vertex_map = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_vertices)}
        
        # Extract vertices and remap faces
        new_vertices = mesh.vertices[unique_vertices]
        new_faces = np.array([[vertex_map[v] for v in face] for face in faces_subset])
        
        # Create new mesh
        new_mesh = trimesh.Trimesh(vertices=new_vertices, faces=new_faces, process=False)
        
        # Copy UV coordinates if available
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            new_mesh.visual.uv = mesh.visual.uv[unique_vertices]
            print(f"Copied UV coordinates for material {mat_idx} ({len(unique_vertices)} vertices)")
        
        # Create mesh data with single material
        split_mesh_data = {
            'mesh': new_mesh,
            'materials': [materials[mat_idx]],
            'textures': materials[mat_idx]['textures'],
            'material_index': mat_idx
        }
        
        split_meshes.append(split_mesh_data)
        print(f"Created mesh for material {mat_idx}: {len(new_vertices)} vertices, {len(new_faces)} faces, textures: {materials[mat_idx]['textures']}")
    
    return split_meshes


def apply_materials_to_mesh(mesh: trimesh.Trimesh, materials: List[dict], textures: List[str], base_path: str) -> trimesh.Trimesh:
    """Apply materials and textures to a mesh"""
    if not materials:
        return mesh
    
    try:
        # For now, use the first material that has a texture
        material_with_texture = None
        for mat in materials:
            if mat['textures']:
                material_with_texture = mat
                break
        
        if not material_with_texture:
            # Use first material for color
            if materials:
                mat = materials[0]
                # Apply diffuse color
                if 'diffuse' in mat and len(mat['diffuse']) >= 3:
                    color = mat['diffuse'][:4]  # RGBA
                    if len(color) == 3:
                        color.append(1.0)  # Add alpha
                    mesh.visual.face_colors = color
                    print(f"Applied diffuse color {color} to mesh")
            return mesh
        
        # Try to load texture
        texture_name = material_with_texture['textures'][0]
        # Try multiple possible locations for texture files
        texture_paths = [
            os.path.join(base_path, texture_name),  # Same directory as mesh
            os.path.join(os.path.dirname(base_path), texture_name),  # Parent directory (data/)
            os.path.join('data', texture_name)  # Relative to project root
        ]
        
        texture_path = None
        for path in texture_paths:
            if os.path.exists(path):
                texture_path = path
                break
        
        if texture_path and os.path.exists(texture_path):
            print(f"Loading texture: {texture_path}")
            
            # Create PBR material with texture
            material = trimesh.visual.material.PBRMaterial()
            material.name = material_with_texture['name']
            
            # Set base color from diffuse
            if 'diffuse' in material_with_texture and len(material_with_texture['diffuse']) >= 3:
                material.baseColorFactor = material_with_texture['diffuse'][:4]
                if len(material.baseColorFactor) == 3:
                    material.baseColorFactor.append(1.0)
            
            # Load texture image
            try:
                from PIL import Image
                img = Image.open(texture_path)
                material.baseColorTexture = img
                print(f"Successfully loaded texture {texture_name}")
                
                # Preserve existing UV coordinates before creating TextureVisuals
                existing_uv = None
                if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                    existing_uv = mesh.visual.uv.copy()
                    print(f"Preserving existing UV coordinates from .X file ({existing_uv.shape})")
                
                # Create texture visuals for the mesh
                mesh.visual = trimesh.visual.TextureVisuals(material=material)
                
                # Restore or generate UV coordinates
                if existing_uv is not None:
                    mesh.visual.uv = existing_uv
                    print("Restored UV coordinates from .X file")
                else:
                    print("Generating UV coordinates for mesh (no UV data from .X file)")
                    # Simple planar UV mapping as fallback
                    vertices = mesh.vertices
                    bounds = mesh.bounds
                    width = bounds[1][0] - bounds[0][0]
                    height = bounds[1][1] - bounds[0][1]
                    
                    uv = np.zeros((len(vertices), 2))
                    uv[:, 0] = (vertices[:, 0] - bounds[0][0]) / width if width > 0 else 0
                    uv[:, 1] = (vertices[:, 1] - bounds[0][1]) / height if height > 0 else 0
                    
                    mesh.visual.uv = uv
                
            except ImportError:
                print("PIL not available, cannot load texture images")
                # Fall back to color
                if 'diffuse' in material_with_texture:
                    mesh.visual.face_colors = material_with_texture['diffuse'][:4]
            except Exception as e:
                print(f"Failed to load texture {texture_path}: {e}")
                # Fall back to color
                if 'diffuse' in material_with_texture:
                    mesh.visual.face_colors = material_with_texture['diffuse'][:4]
        else:
            print(f"Texture not found: {texture_path}")
            # Apply color only
            if 'diffuse' in material_with_texture:
                mesh.visual.face_colors = material_with_texture['diffuse'][:4]
                
    except Exception as e:
        print(f"Error applying materials to mesh: {e}")
    
    return mesh


def assemble_scene(descriptor_path: str, include_skin: bool = True, include_items: bool = True, merge_female_body: bool = False) -> dict:
    print(f"Reading descriptor: {descriptor_path}")
    desc = read_descriptor(descriptor_path)

    print(f"Descriptor blocks: {list(desc.blocks.keys())}")
    
    bones = parse_frame_bones(desc)

    print(f"Found {len(bones)} bones: {list(bones.keys())}")
    
    # Build attachments per flags
    attachments: List[Attachment] = []  # type: ignore[name-defined]
    dynamic_meshes = []  # Store DynamicVisual mesh data
    if include_skin:
        for _, ident in parse_skin_entries(desc):  # type: ignore[name-defined]
            atts, dynamic_mesh = resolve_identifier_to_attachments(ident, desc)  # type: ignore[name-defined]
            attachments.extend(atts)
            if dynamic_mesh:
                dynamic_meshes.append(dynamic_mesh)
    if include_items:
        for full in parse_defaultcos(desc):  # type: ignore[name-defined]
            if '.' not in full:
                continue
            prefix, item = full.split('.', 1)
            item_block = desc.blocks.get(item)
            if not item_block:
                continue
            for raw in item_block:
                s = raw.strip()
                if not s or ':' not in s or s.startswith('class:'):
                    continue
                _, vp_ident = s.split(':', 1)
                vp_ident = vp_ident.strip()
                if '.' in vp_ident:
                    _, vp_name = vp_ident.split('.', 1)
                else:
                    vp_name = vp_ident
                vp_block = desc.blocks.get(vp_name)
                if vp_block:
                    attachments.extend(parse_attachment_block_lines(vp_block))  # type: ignore[name-defined]
                    # CRITICAL: Also parse DynamicVisual data from clothing blocks!
                    clothing_dyn_mesh = parse_dynamic_visual_mesh(vp_block)  # type: ignore[name-defined]
                    if clothing_dyn_mesh:
                        print(f"DEBUG: Found clothing DynamicVisual mesh in {vp_name} with {len(clothing_dyn_mesh['vertices'])} vertices")
                        dynamic_meshes.append(clothing_dyn_mesh)
                break
    
    # CRITICAL: Process additional *_vp blocks with DynamicVisual data that aren't in defaultcos
    if include_items:
        processed_vp_blocks = set()
        
        # Track which *_vp blocks were already processed in defaultcos
        for full in parse_defaultcos(desc):  # type: ignore[name-defined]
            if '.' in full:
                prefix, item = full.split('.', 1)
                item_block = desc.blocks.get(item)
                if item_block:
                    for raw in item_block:
                        s = raw.strip()
                        if ':' in s and not s.startswith('class:'):
                            _, vp_ident = s.split(':', 1)
                            vp_ident = vp_ident.strip()
                            if '.' in vp_ident:
                                _, vp_name = vp_ident.split('.', 1)
                            else:
                                vp_name = vp_ident
                            if vp_name.endswith('_vp'):
                                processed_vp_blocks.add(vp_name)
                            break
        
        print(f"DEBUG: Already processed *_vp blocks: {processed_vp_blocks}")
        
        # Process remaining *_vp blocks with DynamicVisual data
        additional_dynamic_count = 0
        for block_name, block_lines in desc.blocks.items():
            if (block_name.endswith('_vp') and 
                block_name not in processed_vp_blocks and 
                any('DynamicVisual:' in line for line in block_lines)):
                
                additional_dyn_mesh = parse_dynamic_visual_mesh(block_lines)  # type: ignore[name-defined]
                if additional_dyn_mesh:
                    additional_dynamic_count += 1
                    print(f"DEBUG: Found additional DynamicVisual mesh in {block_name} with {len(additional_dyn_mesh['vertices'])} vertices")
                    dynamic_meshes.append(additional_dyn_mesh)
        
        if additional_dynamic_count > 0:
            print(f"DEBUG: Found {additional_dynamic_count} additional *_vp blocks with DynamicVisual data")
    
    print(f"Found {len(attachments)} attachments:")
    for att in attachments:
        print(f"  - {att.attach_bone} -> {att.resource_id}")
    
    world = build_world_transforms(bones, attachments)

    print(f"Built {len(world)} world transforms")
    # Debug key transforms
    for key in ['body', 'waist', 'skirt_f', 'skirt_r']:
        if key in world:
            print(f"  DEBUG: {key} world position: {world[key]}")

    scene = trimesh.Scene()
    scene_graph_nodes: Dict[str, trimesh.SceneNode] = {}

    # Collect all materials and textures
    all_materials = []
    all_textures = []


    # Create transform nodes for bones and child attachment nodes (kept for reference)
    for name, pos in world.items():
        tf = np.eye(4)
        tf[:3, 3] = np.array(pos, dtype=float)
        scene_graph_nodes[name] = scene.graph.update(frame_to=name, matrix=tf)

    # Attach meshes

    mesh_count = 0
    prefix_counts: Dict[str, int] = {}
    female_body_meshes: List[trimesh.Trimesh] = []
    processed_attachments: Dict[str, List[str]] = {}  # bone -> list of resource_ids to allow multiple attachments per bone
    geometry_to_attachment_map: Dict[str, str] = {}  # Track which geometry corresponds to which attachment/bone
    
    # Define core body parts that should replace each other vs accessories that should be added
    CORE_BODY_PARTS = {
        'body', 'head', 'l_breast', 'r_breast', 'l_arm1', 'l_arm2', 'l_hand', 
        'r_arm1', 'r_arm2', 'r_hand', 'waist', 'l_leg1', 'l_leg2', 'l_foot', 
        'r_leg1', 'r_leg2', 'r_foot'
    }
    
    def is_core_body_part(resource_id: str) -> bool:
        """Check if a resource represents a core body part vs an accessory"""
        if resource_id.startswith('female.'):
            part_name = resource_id.split('.', 1)[1]
            return part_name in CORE_BODY_PARTS
        return False
    
    for att in attachments:

        # Handle duplicate attachments for the same bone
        bone_key = att.attach_bone
        if bone_key not in processed_attachments:
            processed_attachments[bone_key] = []
        
        existing_resources = processed_attachments[bone_key]
        
        # Check for conflicts only among core body parts
        should_skip = False
        if is_core_body_part(att.resource_id):
            # This is a core body part - check if we already have another core body part for this bone
            for existing_resource in existing_resources:
                if is_core_body_part(existing_resource):
                    # Prioritize character-specific over generic female for core body parts
                    if existing_resource.startswith('female.') and not att.resource_id.startswith('female.'):
                        print(f"Replacing core body part {existing_resource} with character-specific {att.resource_id} for bone {bone_key}")
                        processed_attachments[bone_key].remove(existing_resource)
                        break
                    elif not existing_resource.startswith('female.') and att.resource_id.startswith('female.'):
                        print(f"Skipping generic core body part {att.resource_id} - already have character-specific {existing_resource} for bone {bone_key}")
                        should_skip = True
                        break
                    else:
                        print(f"Skipping duplicate core body part {att.resource_id} for bone {bone_key} - already have {existing_resource}")
                        should_skip = True
                        break
        else:
            # This is an accessory - check if it's already been processed
            if att.resource_id in existing_resources:
                print(f"Skipping duplicate accessory {att.resource_id} for bone {bone_key}")
                should_skip = True
        
        if should_skip:
            continue
        
        processed_attachments[bone_key].append(att.resource_id)
        mesh_path = find_mesh_file(att.resource_id)
        if not mesh_path:

            print(f"Could not find mesh file for {att.resource_id}")
            continue

        print(f"Found mesh file: {mesh_path}")
        try:
            # Get node and mesh names first
            node_name = att.child_name or att.attach_bone
            name = os.path.basename(mesh_path)
            
            mesh_data = load_mesh_with_materials(mesh_path)
            mesh = mesh_data['mesh']
            
            # Store materials for this mesh
            if mesh_data['materials']:
                all_materials.extend(mesh_data['materials'])
                print(f"  Loaded {len(mesh_data['materials'])} materials from {mesh_path}")
            
            if mesh_data['textures']:
                all_textures.extend([tex for tex in mesh_data['textures'] if tex not in all_textures])
                print(f"  Found textures: {mesh_data['textures']}")
            
            # Handle multi-material meshes by splitting them
            if mesh_data.get('face_materials') and len(set(mesh_data['face_materials'])) > 1:
                print(f"Multi-material mesh detected, splitting into {len(set(mesh_data['face_materials']))} parts")
                split_meshes = split_mesh_by_materials(mesh_data)
                
                # Process each split mesh
                for split_data in split_meshes:
                    split_mesh = split_data['mesh']
                    
                    # Apply materials to this split mesh
                    if split_data['materials'] or split_data['textures']:
                        base_path = os.path.dirname(mesh_path)
                        split_mesh = apply_materials_to_mesh(split_mesh, split_data['materials'], split_data['textures'], base_path)
                    
                    # Apply world transform to each split mesh
                    world_t = world.get(node_name, (0.0, 0.0, 0.0))
                    T = np.eye(4)
                    T[:3, 3] = np.array(world_t, dtype=float)
                    split_mesh = split_mesh.copy()
                    split_mesh.apply_transform(T)
                    
                    # Add to scene with unique name
                    split_name = f"{name}_mat{split_data['material_index']}"
                    if merge_female_body and att.resource_id.startswith('female.'):
                        female_body_meshes.append(split_mesh)
                        print(f"Collected female body part {split_name} for merging")
                    else:
                        scene.add_geometry(split_mesh, node_name=split_name)
                        geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = att.resource_id
                        print(f"Added split mesh {split_name} to scene")
                
            else:
                # Single material mesh - process normally
                # Apply materials to this mesh
                if mesh_data['materials'] or mesh_data['textures']:
                    base_path = os.path.dirname(mesh_path)  # Directory containing the mesh file
                    mesh = apply_materials_to_mesh(mesh, mesh_data['materials'], mesh_data['textures'], base_path)
                
                # Apply world transform
                world_t = world.get(node_name, (0.0, 0.0, 0.0))
                T = np.eye(4)
                T[:3, 3] = np.array(world_t, dtype=float)
                mesh = mesh.copy()
                mesh.apply_transform(T)
                
                # Add to scene
                if merge_female_body and att.resource_id.startswith('female.'):
                    female_body_meshes.append(mesh)
                    print(f"Collected female body part {name} for merging")
                else:
                    scene.add_geometry(mesh, node_name=name)
                    geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = att.resource_id
                    print(f"Added mesh {name} to scene")

            mesh_count += 1
        except Exception as e:
            print(f"Failed to load mesh {mesh_path}: {e}")
            continue

        # Count by resource prefix (e.g., 'female', 'ciel')
        if '.' in att.resource_id:
            pref = att.resource_id.split('.', 1)[0]
            prefix_counts[pref] = prefix_counts.get(pref, 0) + 1

        # Bake world-space translation for the target node into mesh vertices to ensure correct placement in glTF
        world_t = world.get(node_name, (0.0, 0.0, 0.0))
        # Debug child frame positioning
        if 'skirt' in node_name.lower():
            print(f"    DEBUG: Child frame {node_name} world transform: {world_t} (from world dict)")
        T = np.eye(4)
        T[:3, 3] = np.array(world_t, dtype=float)
        mesh = mesh.copy()
        mesh.apply_transform(T)

        # If merging female body parts, collect them instead of adding individually
        if merge_female_body and att.resource_id.startswith('female.'):
            female_body_meshes.append(mesh)
            print(f"Collected female body part {name} for merging")
        else:
            # Add geometry directly (no scene-graph parenting relied upon for transforms)
            scene.add_geometry(mesh, node_name=name)
            # Track which geometry corresponds to which resource (not just bone)
            # The geometry will be named something like "geometry_0", "geometry_1", etc.
            # We need to track this BEFORE incrementing mesh_count
            geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = att.resource_id
            print(f"Added mesh {name} to scene under node {node_name}")
    
    # Merge female body parts if requested
    if merge_female_body and female_body_meshes:
        print(f"Merging {len(female_body_meshes)} female body parts into unified mesh...")
        merged_body = merge_body_meshes(female_body_meshes)
        scene.add_geometry(merged_body, node_name="female_body_merged")
        geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = "female_body_merged"
        print(f"Added merged female body with {len(merged_body.vertices)} vertices and {len(merged_body.faces)} faces")

    print(f"Total meshes added to scene: {mesh_count}")
    if prefix_counts:
        print("Meshes by source prefix:")
        for k, v in sorted(prefix_counts.items()):
            print(f"  - {k}: {v}")
    
    # Add DynamicVisual meshes (the connecting geometry!)
    if dynamic_meshes:
        print(f"\nProcessing {len(dynamic_meshes)} DynamicVisual mesh sections...")
        # Collect all existing mesh vertices for snapping
        all_mesh_vertices = []
        mesh_vertex_map = {}  # Track which mesh each vertex belongs to
        mesh_info = {}  # Track mesh info for debugging
        geometry_to_mesh_map = {}  # Map geometry names back to original mesh file names
        vertex_offset = 0
        
        # Use the tracked geometry to attachment mapping
        geometry_to_mesh_map = geometry_to_attachment_map.copy()
        print(f"  Using tracked geometry mapping: {geometry_to_mesh_map}")
        
        for geom_name, geom in scene.geometry.items():
            if hasattr(geom, 'vertices') and len(geom.vertices) > 0:
                all_mesh_vertices.extend(geom.vertices.tolist())
                mesh_info[geom_name] = len(geom.vertices)
                
                # Use the original mesh file name if we can map it, otherwise use geometry name
                original_name = geometry_to_mesh_map.get(geom_name, geom_name)
                
                # Map vertex indices to original mesh names for debugging
                for i in range(len(geom.vertices)):
                    mesh_vertex_map[vertex_offset + i] = original_name
                vertex_offset += len(geom.vertices)
        
        print(f"  Collected {len(all_mesh_vertices)} vertices from existing meshes for snapping")
        print(f"  Mesh breakdown: {mesh_info}")
        print(f"  Geometry to mesh mapping: {geometry_to_mesh_map}")
        all_mesh_vertices = np.array(all_mesh_vertices)
        
        for i, dyn_data in enumerate(dynamic_meshes):
            if dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data:
                vertices = dyn_data['vertices']  # Now contains (pos1, pos2) tuples
                faces = np.array(dyn_data['faces'])
                print(f"  DynamicVisual mesh {i}: {len(vertices)} vertices, {len(faces)} faces")
                
                # Debugging for specific meshes
                if i == 5:  # Focus on connector 5 (knee-ankle issue)
                    bone_breakdown = {}
                    for bone in dyn_data['vertex_bones']:
                        bone_breakdown[bone] = bone_breakdown.get(bone, 0) + 1
                    print(f"    DEBUG: Connector 5 bone breakdown: {bone_breakdown}")
                    
                    # Analyze Y-coordinates to see the vertical span
                    y_coords = []
                    for vertex_tuple, bone_name in zip(vertices, dyn_data['vertex_bones']):
                        pos1, pos2 = vertex_tuple
                        bone_pos = world.get(bone_name, (0.0, 0.0, 0.0))
                        candidate_y = pos2[1] + bone_pos[1]
                        y_coords.append((candidate_y, bone_name))
                    
                    y_coords.sort()  # Sort by Y coordinate
                    print(f"    DEBUG: Connector 5 Y-coordinate range: {y_coords[0][0]:.1f} to {y_coords[-1][0]:.1f}")
                    print(f"    DEBUG: Lowest vertices: {[f'{y:.1f}({bone})' for y, bone in y_coords[:4]]}")
                    print(f"    DEBUG: Highest vertices: {[f'{y:.1f}({bone})' for y, bone in y_coords[-4:]]}")
                elif i == 8:  # Skirt mesh
                    skirt_f_count = sum(1 for b in dyn_data['vertex_bones'] if b == 'skirt_f')
                    skirt_r_count = sum(1 for b in dyn_data['vertex_bones'] if b == 'skirt_r')
                    waist_count = sum(1 for b in dyn_data['vertex_bones'] if b == 'waist')
                    print(f"    DEBUG: Skirt DynamicVisual breakdown: waist={waist_count}, skirt_f={skirt_f_count}, skirt_r={skirt_r_count}")
                    
                    # Show all unique bones in this mesh
                    unique_bones = set(dyn_data['vertex_bones'])
                    print(f"    DEBUG: All bones in connector 8: {sorted(unique_bones)}")
                    
                    # Count vertices per bone
                    bone_counts = {}
                    for bone in dyn_data['vertex_bones']:
                        bone_counts[bone] = bone_counts.get(bone, 0) + 1
                    print(f"    DEBUG: Vertex counts per bone: {bone_counts}")
                elif i == 10:  # socks_vp - should contain leg-to-foot connectors!
                    bone_breakdown = {}
                    for bone in dyn_data['vertex_bones']:
                        bone_breakdown[bone] = bone_breakdown.get(bone, 0) + 1
                    print(f"    DEBUG: Connector 10 (socks_vp) bone breakdown: {bone_breakdown}")
                    # Check if it has foot bones (the missing connection!)
                    foot_bones = [b for b in bone_breakdown.keys() if 'foot' in b]
                    leg_bones = [b for b in bone_breakdown.keys() if 'leg' in b]
                    print(f"    DEBUG: Connector 10 foot bones: {foot_bones}, leg bones: {leg_bones}")
                    
                    # Analyze Y-coordinates for connector 10
                    y_coords = []
                    for vertex_tuple, bone_name in zip(vertices, dyn_data['vertex_bones']):
                        pos1, pos2 = vertex_tuple
                        bone_pos = world.get(bone_name, (0.0, 0.0, 0.0))
                        candidate_y = pos2[1] + bone_pos[1]
                        y_coords.append((candidate_y, bone_name))
                    
                    y_coords.sort()  # Sort by Y coordinate
                    print(f"    DEBUG: Connector 10 Y-coordinate range: {y_coords[0][0]:.1f} to {y_coords[-1][0]:.1f}")
                    leg2_coords = [(y, bone) for y, bone in y_coords if 'leg2' in bone]
                    foot_coords = [(y, bone) for y, bone in y_coords if 'foot' in bone]
                    print(f"    DEBUG: Connector 10 leg2 Y-range: {[f'{y:.1f}' for y, _ in leg2_coords]}")
                    print(f"    DEBUG: Connector 10 foot Y-range: {[f'{y:.1f}' for y, _ in foot_coords]}")
                
                # Create trimesh object
                try:
                    # Smart vertex snapping approach - snap DynamicVisual vertices to nearest existing mesh vertices
                    snapped_vertices = []
                    
                    for j, (vertex_tuple, bone_name) in enumerate(zip(vertices, dyn_data['vertex_bones'])):
                        pos1, pos2 = vertex_tuple  # Extract both positions
                        
                        # Get the bone's world position for reference
                        bone_pos = world.get(bone_name, (0.0, 0.0, 0.0))
                        
                        # Try pos2 positioned relative to bone (this was working better)
                        candidate_pos = [
                            pos2[0] + bone_pos[0],
                            pos2[1] + bone_pos[1], 
                            pos2[2] + bone_pos[2]
                        ]
                        
                        # Find the closest existing mesh vertex to snap to
                        if len(all_mesh_vertices) > 0:
                            # For DynamicVisual mesh 1 (torso connector), use bone-aware snapping
                            if i == 1:
                                if j < 3:  # Debug first few vertices
                                    print(f"    DEBUG: Mesh {i} vertex {j} ({bone_name}) entering bone-aware snapping")
                                # Define which RESOURCE TYPES each bone should prefer to connect to
                                bone_to_preferred_resources = {
                                    'body': ['female.body', 'female.l_breast', 'female.r_breast'],  # Connect to core body parts, NOT hair
                                    'l_breast': ['female.l_breast', 'female.body'],                  # Connect to left breast and body
                                    'r_breast': ['female.r_breast', 'female.body'],                  # Connect to right breast and body  
                                    'l_arm1': ['female.l_arm1', 'female.body', 'female.l_breast'],  # Connect to left arm, body, and breast (shoulder area)
                                    'r_arm1': ['female.r_arm1', 'female.body'],                      # Connect to right arm and body (shoulder)
                                    'waist': ['female.waist', 'female.body']                         # Connect to waist and body
                                }
                                
                                preferred_resources = bone_to_preferred_resources.get(bone_name, [])
                                
                                # Debug l_arm1 processing
                                if bone_name == 'l_arm1' and j < 15:
                                    print(f"    DEBUG: Processing vertex {j} ({bone_name}) with preferred resources: {preferred_resources}")
                                
                                # Try to snap to vertices from preferred resource types first
                                best_distance = float('inf')
                                best_idx = None
                                
                                # Try both pos1 and pos2 for each preferred resource and pick the best
                                best_candidates = []
                                
                                for pos_type, pos_candidate in [("pos2", candidate_pos), ("pos1", [pos1[0] + bone_pos[0], pos1[1] + bone_pos[1], pos1[2] + bone_pos[2]])]:
                                    for resource_type in preferred_resources:
                                        # Find vertices belonging to meshes of this resource type
                                        mesh_vertices_mask = np.array([mesh_vertex_map.get(idx, "unknown") == resource_type for idx in range(len(all_mesh_vertices))])
                                        if np.any(mesh_vertices_mask):
                                            mesh_specific_vertices = all_mesh_vertices[mesh_vertices_mask]
                                            mesh_distances = np.linalg.norm(mesh_specific_vertices - pos_candidate, axis=1)
                                            min_distance = np.min(mesh_distances)
                                            
                                            # Map back to global index
                                            local_best_idx = np.argmin(mesh_distances)
                                            global_indices = np.where(mesh_vertices_mask)[0]
                                            candidate_idx = global_indices[local_best_idx]
                                            
                                            best_candidates.append({
                                                'distance': min_distance,
                                                'idx': candidate_idx,
                                                'pos_type': pos_type,
                                                'resource': resource_type,
                                                'pos': pos_candidate
                                            })
                                
                                # Pick the best candidate overall
                                if best_candidates:
                                    # For l_arm1 (shoulder) vertices, prefer candidates that create better shoulder geometry
                                    if bone_name == 'l_arm1':
                                        # Filter to candidates with reasonable distance (< 0.5)
                                        good_candidates = [c for c in best_candidates if c['distance'] < 0.5]
                                        if good_candidates:
                                            # Among good candidates, prefer those that are higher up (more positive Y)
                                            # This creates more natural convex shoulder curves
                                            best_candidate = max(good_candidates, key=lambda x: all_mesh_vertices[x['idx']][1])
                                            if j < 15:
                                                print(f"    DEBUG: Vertex {j} ({bone_name}) chose higher vertex for better shoulder curve (Y={all_mesh_vertices[best_candidate['idx']][1]:.3f})")
                                        else:
                                            # Fallback to closest if no good candidates
                                            best_candidate = min(best_candidates, key=lambda x: x['distance'])
                                    else:
                                        # For non-shoulder vertices, use closest distance
                                        best_candidate = min(best_candidates, key=lambda x: x['distance'])
                                    
                                    best_distance = best_candidate['distance']
                                    best_idx = best_candidate['idx']
                                    
                                    # Use the position that gave the best result
                                    if best_candidate['pos_type'] == 'pos1':
                                        candidate_pos = best_candidate['pos']
                                        if bone_name == 'l_arm1' and j < 15:
                                            print(f"    DEBUG: Vertex {j} ({bone_name}) using pos1 for {best_candidate['resource']} (distance: {best_distance:.3f})")
                                    else:
                                        if bone_name == 'l_arm1' and j < 15:
                                            print(f"    DEBUG: Vertex {j} ({bone_name}) using pos2 for {best_candidate['resource']} (distance: {best_distance:.3f})")
                                
                                if best_idx is not None:
                                    closest_idx = best_idx
                                    closest_distance = best_distance
                                else:
                                    # Fallback to global closest if no preferred mesh found
                                    distances = np.linalg.norm(all_mesh_vertices - candidate_pos, axis=1)
                                    closest_idx = np.argmin(distances)
                                    closest_distance = distances[closest_idx]
                            else:
                                # Use global closest for other meshes
                                distances = np.linalg.norm(all_mesh_vertices - candidate_pos, axis=1)
                                closest_idx = np.argmin(distances)
                                closest_distance = distances[closest_idx]
                            
                            # Debug skirt_r vertices specifically
                            if i == 8 and bone_name == 'skirt_r':
                                closest_mesh = mesh_vertex_map.get(closest_idx, "unknown")
                                print(f"    DEBUG: skirt_r vertex {j} at {candidate_pos} - snapping to {closest_mesh} (distance: {closest_distance:.3f})")
                            
                            # For mesh 0 (the problematic one), try a more refined approach
                            if i == 0 and closest_distance > 0.5:
                                # Try using pos1 instead of pos2 for vertices that don't snap well
                                alt_candidate_pos = [
                                    pos1[0] + bone_pos[0],
                                    pos1[1] + bone_pos[1], 
                                    pos1[2] + bone_pos[2]
                                ]
                                alt_distances = np.linalg.norm(all_mesh_vertices - alt_candidate_pos, axis=1)
                                alt_closest_idx = np.argmin(alt_distances)
                                alt_closest_distance = alt_distances[alt_closest_idx]
                                
                                # Use pos1 if it gives a better snap
                                if alt_closest_distance < closest_distance:
                                    closest_idx = alt_closest_idx
                                    closest_distance = alt_closest_distance
                                    candidate_pos = alt_candidate_pos
                                    if j < 10:  # Only debug first 10 vertices to avoid spam
                                        print(f"    Vertex {j} ({bone_name}) using pos1 instead of pos2 (better distance: {closest_distance:.3f})")
                            

                            
                            # Only snap if the distance is reasonable (within 2 units) 
                            # For mesh 1 (torso connector), be more lenient with l_arm1 vertices
                            distance_threshold = 3.0 if (i == 1 and bone_name == 'l_arm1') else 2.0
                            if closest_distance < distance_threshold:
                                snapped_vertex = all_mesh_vertices[closest_idx].tolist()
                                closest_mesh = mesh_vertex_map.get(closest_idx, "unknown")
                                # Debug connector 5 snapping in detail
                                if i == 5:
                                    print(f"    DEBUG: Connector 5 Vertex {j} ({bone_name}) at {candidate_pos} snapped to {closest_mesh} (distance: {closest_distance:.3f})")
                                    # Show the actual position it snapped to
                                    snapped_pos = all_mesh_vertices[closest_idx].tolist()
                                    print(f"    DEBUG: Snapped from {candidate_pos} to {snapped_pos}")
                                # Only print problematic vertices (distance > 0.5) for other meshes
                                elif closest_distance > 0.5:
                                    print(f"    Vertex {j} ({bone_name}) snapped to {closest_mesh} (distance: {closest_distance:.3f}) - potential alignment issue")
                            else:
                                snapped_vertex = candidate_pos
                                print(f"    Vertex {j} ({bone_name}) too far from existing vertices (distance: {closest_distance:.3f}), using calculated position")
                        else:
                            snapped_vertex = candidate_pos
                        
                        snapped_vertices.append(snapped_vertex)
                    
                    # Create the mesh with snapped vertices
                    snapped_vertices = np.array(snapped_vertices)
                    dyn_mesh = trimesh.Trimesh(vertices=snapped_vertices, faces=faces, process=False)
                    
                    # Special handling for skirt mesh (mesh 8) - check if we need mirroring
                    if i == 8:
                        print(f"  DEBUG: Skirt mesh has {len(snapped_vertices)} vertices and {len(faces)} faces")
                        # Check if vertices are mostly on one side (indicating need for mirroring)
                        x_coords = snapped_vertices[:, 0]
                        left_side_count = np.sum(x_coords < -1.0)  # Vertices on left side (X < -1)
                        right_side_count = np.sum(x_coords > 1.0)   # Vertices on right side (X > 1)
                        print(f"  DEBUG: Skirt vertex distribution: {left_side_count} left, {right_side_count} right")
                        
                        # If there's significant asymmetry, try mirroring to complete the skirt
                        if abs(left_side_count - right_side_count) > 10:
                            print(f"  DEBUG: Detected asymmetric skirt, attempting to mirror for completeness")
                            # Create mirrored vertices (flip X coordinate)
                            mirrored_vertices = snapped_vertices.copy()
                            mirrored_vertices[:, 0] *= -1  # Mirror across YZ plane
                            
                            # Combine original and mirrored vertices
                            combined_vertices = np.vstack([snapped_vertices, mirrored_vertices])
                            
                            # Create faces for mirrored part (offset indices by original vertex count)
                            offset_faces = faces + len(snapped_vertices)
                            # Flip face winding for mirrored geometry
                            offset_faces = offset_faces[:, [0, 2, 1]]  # Reverse winding order
                            
                            combined_faces = np.vstack([faces, offset_faces])
                            
                            dyn_mesh = trimesh.Trimesh(vertices=combined_vertices, faces=combined_faces, process=False)
                            print(f"  DEBUG: Created mirrored skirt with {len(combined_vertices)} vertices and {len(combined_faces)} faces")
                    
                    scene.add_geometry(dyn_mesh, node_name=f"dynamic_connector_{i}")
                    print(f"  Added DynamicVisual connector mesh {i} with {len(vertices)} vertices using vertex snapping")
                except Exception as e:
                    print(f"  Failed to create DynamicVisual mesh {i}: {e}")

    return {
        'scene': scene,
        'materials': all_materials,
        'textures': all_textures
    }


def export_glb(scene: trimesh.Scene, out_path: str) -> None:
    # trimesh can export to glb via pygltflib backend if available
    ext = os.path.splitext(out_path)[1].lower()
    if ext not in ('.glb', '.gltf'):
        raise ValueError('Output path must end with .glb or .gltf')

    
    # Check if scene has any geometry
    if not scene.geometry:
        raise ValueError("Scene has no geometry to export!")
    
    print(f"Exporting scene with {len(scene.geometry)} geometries to {out_path}")
    scene.export(out_path)


if __name__ == '__main__':

    from vf3_loader import (
        read_descriptor,
        parse_frame_bones,
        parse_skin_entries,
        parse_defaultcos,
        resolve_identifier_to_attachments,
        parse_attachment_block_lines,
        collect_active_attachments,
        find_mesh_file,
        build_world_transforms,
        parse_dynamic_visual_mesh,
    )
    import argparse

    base_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description='VF3 character to glTF exporter')
    parser.add_argument('--desc', default=os.path.join(base_dir, 'data', 'CIEL.TXT'), help='Path to descriptor TXT (e.g., data/CIEL.TXT)')
    parser.add_argument('--out', default=None, help='Output GLB/GLTF path')
    # Export mode options (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--skin-only', action='store_true', help='Export only skin/body parts (no clothing)')
    mode_group.add_argument('--naked', action='store_true', help='Export completely naked body (skin only, minimal coverage)')
    mode_group.add_argument('--base-costume', action='store_true', help='Export with default costume from <defaultcos> block')
    mode_group.add_argument('--items-only', action='store_true', help='Include only costume items from defaultcos, no base skin')
    # Default behavior (no flag) = full outfit with all available items
    parser.add_argument('--merge-body', action='store_true', help='Merge all female body parts into a single unified mesh to fill gaps')
    args = parser.parse_args()

    descriptor = args.desc
    if args.out:
        out = args.out
    else:
        char_name = os.path.splitext(os.path.basename(descriptor))[0]
        out = os.path.join(base_dir, f'{char_name.lower()}_default.glb')

    # Determine export mode
    include_skin = True
    include_items = True
    
    if args.naked:
        # Completely naked - skin only, minimal coverage
        include_skin, include_items = True, False
        print("Export mode: NAKED - skin/body parts only")
    elif args.skin_only:
        # Skin only - body parts but no clothing
        include_skin, include_items = True, False
        print("Export mode: SKIN-ONLY - body parts without clothing")
    elif args.base_costume:
        # Base costume - skin + default costume items
        include_skin, include_items = True, True
        print("Export mode: BASE-COSTUME - skin + default costume from <defaultcos>")
    elif args.items_only:
        # Items only - costume without base skin
        include_skin, include_items = False, True
        print("Export mode: ITEMS-ONLY - costume items without base skin")
    else:
        # Default - full outfit with all available items
        include_skin, include_items = True, True
        print("Export mode: FULL-OUTFIT - complete character with all items")

    scene_data = assemble_scene(descriptor, include_skin=include_skin, include_items=include_items, merge_female_body=args.merge_body)
    scene = scene_data['scene']
    materials = scene_data['materials'] 
    textures = scene_data['textures']
    
    print(f"Scene assembled with {len(scene.geometry)} geometries, {len(materials)} materials, {len(textures)} unique textures")
    
    # For now, export the scene without materials (will add material support next)
    export_glb(scene, out)
    print(f'Exported: {out}')



