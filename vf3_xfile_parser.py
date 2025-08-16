"""
VF3 DirectX .X File Parser Module
Complete implementation with materials, textures, and both binary/text format support.
Extracted from export_ciel_to_gltf.py lines 25-833
"""

import os
import sys
import struct
import types
import importlib.util
import trimesh
import numpy as np
from typing import Dict, List, Any, Optional, Tuple


# Try to import external XFileParser with comprehensive fallback logic
ExternalXFileParser = None

def setup_xfile_parser():
    """Setup XFileParser with the same fallback logic as original"""
    global ExternalXFileParser
    
    try:
        # Ensure package path contains this directory so `xfile` is importable
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
        from xfile.xfile_parser import XFileParser as ExternalXFileParser
        print("Loaded external XFileParser successfully")
        return ExternalXFileParser
    except Exception as _x_import_err:
        print(f"Falling back to inline XFileParser, external import failed: {_x_import_err}")

    # Try loading robust parser by directly loading modules from the xfile folder
    if ExternalXFileParser is None:
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
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
                return ExternalXFileParser
        except Exception as _x_direct_err:
            print(f"Direct xfile loader failed: {_x_direct_err}")

    # Fallback to inline parser (from original file lines 64-620)
    return None


# DirectX .X file parser classes (copied from original export_ciel_to_gltf.py)
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
        ExternalParser = setup_xfile_parser()
        ParserClass = ExternalParser or XFileParser
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
                # Debug material properties
                raw_diffuse = getattr(mat, 'diffuse', [1.0, 1.0, 1.0, 1.0])
                print(f"  DEBUG: Raw diffuse from .X file: {raw_diffuse} (type: {type(raw_diffuse)})")
                
                # Apply gamma correction for better color accuracy (sRGB -> linear)
                # Gamma correction: color^2.2 for RGB components (makes colors darker/more saturated)
                corrected_diffuse = list(raw_diffuse)
                if len(corrected_diffuse) >= 3:
                    for color_i in range(3):  # Only apply to RGB, not alpha
                        corrected_diffuse[color_i] = pow(corrected_diffuse[color_i], 2.2)
                print(f"  DEBUG: Gamma-corrected diffuse: {corrected_diffuse}")
                
                # Gather texture filenames robustly
                extracted_textures = []
                # Case 1: array attribute 'textures'
                if hasattr(mat, 'textures') and mat.textures:
                    for tex in mat.textures:
                        # Try multiple attribute names
                        for attr in ('name', 'fileName', 'filename', 'path'):
                            if hasattr(tex, attr):
                                val = getattr(tex, attr)
                                if isinstance(val, (bytes, bytearray)):
                                    try:
                                        val = val.decode('utf-8', errors='ignore')
                                    except Exception:
                                        pass
                                if isinstance(val, str) and val:
                                    extracted_textures.append(val)
                                    break
                # Case 2: direct attributes on material
                for attr in ('textureFilename', 'texFileName', 'texture', 'file'):
                    if hasattr(mat, attr):
                        val = getattr(mat, attr)
                        if isinstance(val, (bytes, bytearray)):
                            try:
                                val = val.decode('utf-8', errors='ignore')
                            except Exception:
                                pass
                        if isinstance(val, str) and val:
                            extracted_textures.append(val)

                material_data = {
                    'name': getattr(mat, 'name', f'Material_{i}'),
                    'diffuse': corrected_diffuse,
                    'specular': list(getattr(mat, 'specular', [0.0, 0.0, 0.0])),
                    'emissive': list(getattr(mat, 'emissive', [0.0, 0.0, 0.0])),
                    'power': getattr(mat, 'specularExponent', 1.0),
                    'textures': extracted_textures
                }
                
                # Add to unique textures list
                for tex_name in material_data['textures']:
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
                
                # DEBUG: Check UV coordinates for head meshes
                if "head" in file_path.lower():
                    import numpy as np
                    uv_array = np.array(uv_coords)
                    min_u, min_v = uv_array.min(axis=0) if len(uv_coords) > 0 else (0, 0)
                    max_u, max_v = uv_array.max(axis=0) if len(uv_coords) > 0 else (0, 0)
                    print(f"  🔍 HEAD UV EXTRACTION: U({min_u:.4f}-{max_u:.4f}) V({min_v:.4f}-{max_v:.4f})")
                    if len(uv_coords) > 0:
                        print(f"  🔍 First 5 extracted UVs: {uv_coords[:5]}")
            
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
                        # Debug material properties
                        raw_diffuse = getattr(mat, 'diffuse', [1.0, 1.0, 1.0, 1.0])
                        print(f"    DEBUG: Raw diffuse from .X file: {raw_diffuse} (type: {type(raw_diffuse)})")
                        
                        # Apply gamma correction for better color accuracy (sRGB -> linear)
                        corrected_diffuse = list(raw_diffuse)
                        if len(corrected_diffuse) >= 3:
                            for color_i in range(3):  # Only apply to RGB, not alpha
                                corrected_diffuse[color_i] = pow(corrected_diffuse[color_i], 2.2)
                        print(f"    DEBUG: Gamma-corrected diffuse: {corrected_diffuse}")
                        
                        # Gather texture filenames robustly
                        extracted_textures = []
                        if hasattr(mat, 'textures') and mat.textures:
                            for tex in mat.textures:
                                for attr in ('name', 'fileName', 'filename', 'path'):
                                    if hasattr(tex, attr):
                                        val = getattr(tex, attr)
                                        if isinstance(val, (bytes, bytearray)):
                                            try:
                                                val = val.decode('utf-8', errors='ignore')
                                            except Exception:
                                                pass
                                        if isinstance(val, str) and val:
                                            extracted_textures.append(val)
                                            break
                        for attr in ('textureFilename', 'texFileName', 'texture', 'file'):
                            if hasattr(mat, attr):
                                val = getattr(mat, attr)
                                if isinstance(val, (bytes, bytearray)):
                                    try:
                                        val = val.decode('utf-8', errors='ignore')
                                    except Exception:
                                        pass
                                if isinstance(val, str) and val:
                                    extracted_textures.append(val)

                        material_data = {
                            'name': getattr(mat, 'name', f'Material_{len(materials)}'),
                            'diffuse': corrected_diffuse,
                            'specular': list(getattr(mat, 'specular', [0.0, 0.0, 0.0])),
                            'emissive': list(getattr(mat, 'emissive', [0.0, 0.0, 0.0])),
                            'power': getattr(mat, 'specularExponent', 1.0),
                            'textures': extracted_textures
                        }
                        
                        for tex_name in material_data['textures']:
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
        
        # Create trimesh with proper normals processing
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
        
        # Apply normals from .X file if available
        if scene.globalMeshes and scene.globalMeshes[0].normals:
            x_normals = scene.globalMeshes[0].normals
            if len(x_normals) == len(vertices):
                # Apply vertex normals directly from .X file
                mesh.vertex_normals = np.array(x_normals, dtype=np.float32)
                print(f"Applied {len(x_normals)} vertex normals from .X file")
            else:
                # Let trimesh compute smooth vertex normals
                mesh.vertex_normals
                print(f"Generated smooth vertex normals ({len(x_normals)} .X normals != {len(vertices)} vertices)")
        else:
            # Let trimesh compute smooth vertex normals for Gouraud shading
            mesh.vertex_normals
            print("Generated smooth vertex normals for Gouraud shading")
        
        # Add UV coordinates if available
        if uv_coords and len(uv_coords) == len(vertices):
            import numpy as np
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
        mesh = load_mesh_simple(path)
        return {
            'mesh': mesh,
            'materials': [],
            'textures': []
        }
    except Exception as e:
        print(f"Failed to load mesh {path}: {e}")
        raise


def load_mesh_simple(path: str) -> Optional[trimesh.Trimesh]:
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
    
    return None
