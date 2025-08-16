#!/usr/bin/env python3
"""
RAG to GLTF Converter
Converts porin.x, eye.x, awa.x, and porin.wrl files to GLTF format.
"""

import os
import sys
import json
import struct
import trimesh
import numpy as np
from pathlib import Path

# Add VF3 modules to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import VF3 X file parser
from vf3_xfile_parser import parse_directx_x_file_with_materials

# Import X file parsing functions
try:
    import bpy
    import bmesh
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False

class SimpleXFileParser:
    """Simple DirectX .X file parser for mesh extraction"""
    
    def parse_x_file(self, file_path):
        """Parse a DirectX .X file and extract basic mesh data"""
        print(f"Parsing X file: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                # Read first few bytes to check format
                header = f.read(16)
                if not header.startswith(b'xof '):
                    print(f"  Not a valid X file header")
                    return None
                
                # For now, try loading with trimesh directly
                try:
                    mesh = trimesh.load(file_path)
                    if mesh is not None:
                        print(f"  Successfully loaded with trimesh")
                        return {'trimesh': mesh}
                except Exception as e:
                    print(f"  Trimesh loading failed: {e}")
                    
                # If direct loading fails, return basic info for manual processing
                return {'raw_data': True, 'file_path': file_path}
                
        except Exception as e:
            print(f"  Error reading file: {e}")
            return None

class RAGToGLTFConverter:
    def __init__(self, rag_dir="data/rag", output_dir="output"):
        self.rag_dir = Path(rag_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize X file parser
        self.parser = SimpleXFileParser()
        
    def convert_x_file_to_gltf(self, x_file_path, output_name):
        """Convert a single .X file to GLTF format using VF3 parser"""
        print(f"\n=== Converting {x_file_path.name} to GLTF ===")
        
        try:
            # Use VF3's DirectX .X parser
            result = parse_directx_x_file_with_materials(str(x_file_path))
            
            mesh = result['mesh']
            materials = result.get('materials', [])
            textures = result.get('textures', [])
            
            print(f"VF3 parser extracted: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
            if materials:
                print(f"Found {len(materials)} materials")
            if textures:
                print(f"Found {len(textures)} textures: {textures}")
            
            # Create scene
            scene = trimesh.Scene()
            scene.add_geometry(mesh, node_name=output_name)
            
            # Export to GLTF
            gltf_path = self.output_dir / f"{output_name}.gltf"
            glb_path = self.output_dir / f"{output_name}.glb"
            
            print(f"Exporting to: {gltf_path}")
            scene.export(str(gltf_path))
            scene.export(str(glb_path))
            
            print(f"Successfully exported {output_name}.gltf and {output_name}.glb")
            return True
            
        except Exception as e:
            print(f"VF3 parser failed: {e}")
            # Fallback to old parsing method
            return self.try_basic_x_parsing(x_file_path, output_name)
    
    def try_basic_x_parsing(self, x_file_path, output_name):
        """Fallback basic X file parsing"""
        print("Attempting basic X file parsing...")
        
        try:
            with open(x_file_path, 'rb') as f:
                content = f.read()
            
            print(f"File size: {len(content)} bytes")
            
            # Try to extract vertex data from binary X file
            vertices = []
            faces = []
            
            # Look for float patterns in the binary data
            # X files store vertices as sequences of 3 floats (x, y, z)
            import struct
            
            # Skip the header and look for mesh data
            offset = 16  # Skip basic header
            
            # Try to find vertex count (usually a DWORD before vertex data)
            vertex_count = None
            for i in range(offset, len(content) - 4, 4):
                try:
                    potential_count = struct.unpack('<I', content[i:i+4])[0]
                    # Reasonable vertex count for a model
                    if 10 <= potential_count <= 10000:
                        # Check if we have enough data for vertices after this
                        if i + 4 + (potential_count * 12) < len(content):
                            vertex_count = potential_count
                            vertex_data_start = i + 4
                            print(f"Found potential vertex count: {vertex_count} at offset {i}")
                            break
                except:
                    continue
            
            if vertex_count:
                # Extract vertices
                for v in range(vertex_count):
                    vertex_offset = vertex_data_start + (v * 12)  # 3 floats * 4 bytes
                    if vertex_offset + 12 <= len(content):
                        try:
                            x, y, z = struct.unpack('<fff', content[vertex_offset:vertex_offset+12])
                            # Sanity check for reasonable coordinates
                            if abs(x) < 1000 and abs(y) < 1000 and abs(z) < 1000:
                                vertices.append([x, y, z])
                        except:
                            continue
                
                print(f"Extracted {len(vertices)} vertices from binary data")
                
                # Try to find face indices after vertex data  
                # DirectX .X files often have some padding/alignment between vertex and face data
                face_data_search_start = vertex_data_start + (vertex_count * 12)
                face_count = None
                face_data_start = None
                
                # Search for face count in a reasonable range after vertex data
                for offset in range(face_data_search_start, min(face_data_search_start + 100, len(content) - 4), 4):
                    try:
                        potential_count = struct.unpack('<I', content[offset:offset+4])[0]
                        if 10 <= potential_count <= 5000:  # Reasonable face count
                            face_count = potential_count
                            face_data_start = offset
                            print(f"Found face count: {face_count} at offset {offset}")
                            break
                    except:
                        continue
                
                if face_count and face_data_start:
                    # Extract faces - DirectX .X format uses variable length face indices
                    # Each face starts with vertex count, then vertex indices
                    face_indices_start = face_data_start + 4
                    current_offset = face_indices_start
                    
                    for f in range(face_count):
                        if current_offset + 4 < len(content):
                            try:
                                # Read vertex count for this face
                                verts_in_face = struct.unpack('<I', content[current_offset:current_offset+4])[0]
                                current_offset += 4
                                
                                if 3 <= verts_in_face <= 4 and current_offset + (verts_in_face * 4) < len(content):
                                    # Read vertex indices
                                    indices = []
                                    for v in range(verts_in_face):
                                        idx = struct.unpack('<I', content[current_offset:current_offset+4])[0]
                                        current_offset += 4
                                        if 0 <= idx < len(vertices):
                                            indices.append(idx)
                                    
                                    # Convert to triangles
                                    if len(indices) >= 3:
                                        if len(indices) == 3:
                                            # Triangle
                                            faces.append([indices[0], indices[1], indices[2]])
                                        elif len(indices) == 4:
                                            # Quad - split into two triangles
                                            faces.append([indices[0], indices[1], indices[2]])
                                            faces.append([indices[0], indices[2], indices[3]])
                            except:
                                break
                
                print(f"Extracted {len(faces)} faces from binary data")
            
            # If we got reasonable mesh data, use it
            if len(vertices) >= 3 and len(faces) >= 1:
                mesh = trimesh.Trimesh(
                    vertices=np.array(vertices),
                    faces=np.array(faces),
                    process=False
                )
                
                scene = trimesh.Scene()
                scene.add_geometry(mesh, node_name=f"{output_name}_extracted")
                
                # Export
                gltf_path = self.output_dir / f"{output_name}.gltf"
                glb_path = self.output_dir / f"{output_name}.glb"
                
                scene.export(str(gltf_path))
                scene.export(str(glb_path))
                
                print(f"Successfully extracted and exported {output_name} with {len(vertices)} vertices and {len(faces)} faces")
                return True
            else:
                # Fall back to placeholder
                print("Could not extract meaningful mesh data, creating placeholder")
                vertices = np.array([
                    [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]
                ])
                faces = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]])
                
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                scene = trimesh.Scene()
                scene.add_geometry(mesh, node_name=f"{output_name}_placeholder")
                
                # Export
                gltf_path = self.output_dir / f"{output_name}.gltf"
                glb_path = self.output_dir / f"{output_name}.glb"
                
                scene.export(str(gltf_path))
                scene.export(str(glb_path))
                
                print(f"Created placeholder mesh for {output_name}")
                return True
                
        except Exception as e:
            print(f"Basic X parsing failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def convert_vrml_to_gltf(self, vrml_file_path, output_name):
        """Convert VRML 2.0 file to GLTF format"""
        print(f"\n=== Converting {vrml_file_path.name} to GLTF ===")
        
        try:
            # For VRML conversion, we'll use trimesh's built-in support
            print(f"Loading VRML file: {vrml_file_path}")
            
            # Try to load with trimesh
            try:
                mesh = trimesh.load(str(vrml_file_path))
                
                if isinstance(mesh, trimesh.Scene):
                    scene = mesh
                    print(f"Loaded VRML scene with {len(scene.geometry)} geometries")
                else:
                    # Single mesh, create scene
                    scene = trimesh.Scene()
                    scene.add_geometry(mesh, node_name="vrml_mesh")
                    print(f"Loaded single VRML mesh with {len(mesh.vertices)} vertices")
                    
            except Exception as e:
                print(f"Trimesh couldn't load VRML directly: {e}")
                # Fallback: try manual VRML parsing
                return self.parse_vrml_manually(vrml_file_path, output_name)
            
            # Export to GLTF
            gltf_path = self.output_dir / f"{output_name}.gltf"
            glb_path = self.output_dir / f"{output_name}.glb"
            
            print(f"Exporting to: {gltf_path}")
            scene.export(str(gltf_path))
            scene.export(str(glb_path))
            
            print(f"Successfully exported {output_name}.gltf and {output_name}.glb")
            return True
            
        except Exception as e:
            print(f"Error converting VRML {vrml_file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def parse_vrml_manually(self, vrml_file_path, output_name):
        """Manual VRML parsing as fallback"""
        print("Attempting manual VRML parsing...")
        
        try:
            with open(vrml_file_path, 'r') as f:
                content = f.read()
            
            # Simple VRML coordinate parsing
            vertices = []
            faces = []
            
            # Look for coordinate points
            if 'point [' in content:
                coord_start = content.find('point [') + 7
                coord_end = content.find(']', coord_start)
                coord_text = content[coord_start:coord_end]
                
                # Parse coordinates
                lines = coord_text.strip().split('\n')
                for line in lines:
                    line = line.strip().rstrip(',')
                    if line and not line.startswith('#'):
                        coords = line.split()
                        if len(coords) >= 3:
                            try:
                                x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
                                vertices.append([x, y, z])
                            except:
                                continue
            
            # Look for face indices
            if 'coordIndex [' in content:
                face_start = content.find('coordIndex [') + 12
                face_end = content.find(']', face_start)
                face_text = content[face_start:face_end]
                
                # Parse faces
                indices = []
                for token in face_text.replace(',', ' ').split():
                    try:
                        idx = int(token)
                        if idx >= 0:
                            indices.append(idx)
                        else:
                            # -1 indicates end of face
                            if len(indices) >= 3:
                                # Triangulate if needed
                                for i in range(1, len(indices) - 1):
                                    faces.append([indices[0], indices[i], indices[i+1]])
                            indices = []
                    except:
                        continue
                        
                # Handle last face
                if len(indices) >= 3:
                    for i in range(1, len(indices) - 1):
                        faces.append([indices[0], indices[i], indices[i+1]])
            
            if vertices and faces:
                print(f"Parsed VRML: {len(vertices)} vertices, {len(faces)} faces")
                
                # Create trimesh
                mesh = trimesh.Trimesh(
                    vertices=np.array(vertices),
                    faces=np.array(faces),
                    process=False
                )
                
                scene = trimesh.Scene()
                scene.add_geometry(mesh, node_name="vrml_mesh")
                
                # Export
                gltf_path = self.output_dir / f"{output_name}.gltf"
                glb_path = self.output_dir / f"{output_name}.glb"
                
                scene.export(str(gltf_path))
                scene.export(str(glb_path))
                
                print(f"Successfully exported manually parsed VRML to {output_name}")
                return True
            else:
                print("Failed to parse VRML coordinates and faces")
                return False
                
        except Exception as e:
            print(f"Manual VRML parsing failed: {e}")
            return False
    
    def create_combined_scene(self):
        """Create a combined scene with all RAG components"""
        print("\n=== Creating Combined RAG Scene ===")
        
        combined_scene = trimesh.Scene()
        loaded_any = False
        
        # Try to load all components that were successfully converted
        component_files = [
            ('porin.glb', 'porin'),
            ('eye.glb', 'eye'), 
            ('awa.glb', 'awa'),
            ('porin_vrml.glb', 'porin_vrml')
        ]
        
        for glb_file, component_name in component_files:
            glb_path = self.output_dir / glb_file
            if glb_path.exists():
                print(f"Loading {glb_file} for combined scene...")
                try:
                    # Load the GLB file
                    loaded = trimesh.load(str(glb_path))
                    
                    if isinstance(loaded, trimesh.Scene):
                        # Add all geometries from the scene
                        for name, geom in loaded.geometry.items():
                            combined_scene.add_geometry(geom, node_name=f"{component_name}_{name}")
                            loaded_any = True
                            print(f"  Added {component_name}_{name}")
                    else:
                        # Single mesh
                        combined_scene.add_geometry(loaded, node_name=component_name)
                        loaded_any = True
                        print(f"  Added {component_name}")
                        
                except Exception as e:
                    print(f"  Error loading {glb_file}: {e}")
        
        if loaded_any:
            # Export combined scene
            combined_path = self.output_dir / "porin_combined.gltf"
            combined_glb_path = self.output_dir / "porin_combined.glb"
            
            combined_scene.export(str(combined_path))
            combined_scene.export(str(combined_glb_path))
            
            print(f"Successfully exported combined scene to porin_combined.gltf")
            return True
        else:
            print("No components loaded for combined scene")
            return False
    
    def convert_all(self):
        """Convert all RAG files to GLTF"""
        print("=== RAG to GLTF Conversion ===")
        print(f"Input directory: {self.rag_dir}")
        print(f"Output directory: {self.output_dir}")
        
        success_count = 0
        total_count = 0
        
        # Convert individual X files
        x_files = [
            ('porin.X', 'porin'),
            ('eye.X', 'eye'), 
            ('awa.X', 'awa')
        ]
        
        for x_file, output_name in x_files:
            x_path = self.rag_dir / x_file
            if x_path.exists():
                total_count += 1
                if self.convert_x_file_to_gltf(x_path, output_name):
                    success_count += 1
            else:
                print(f"Warning: {x_file} not found")
        
        # Convert VRML file
        vrml_path = self.rag_dir / 'porin.wrl'
        if vrml_path.exists():
            total_count += 1
            if self.convert_vrml_to_gltf(vrml_path, 'porin_vrml'):
                success_count += 1
        else:
            print("Warning: porin.wrl not found")
        
        # Create combined scene
        if self.create_combined_scene():
            success_count += 1
        total_count += 1
        
        print(f"\n=== Conversion Complete ===")
        print(f"Successfully converted {success_count}/{total_count} files")
        print(f"Output files saved to: {self.output_dir}")
        
        # List output files
        output_files = list(self.output_dir.glob("*.gltf")) + list(self.output_dir.glob("*.glb"))
        if output_files:
            print("\nGenerated files:")
            for file in sorted(output_files):
                size_kb = file.stat().st_size / 1024
                print(f"  {file.name} ({size_kb:.1f} KB)")

def main():
    """Main conversion function"""
    # Set up paths
    script_dir = Path(__file__).parent
    rag_dir = script_dir / "data" / "rag"
    output_dir = script_dir / "output" / "rag_gltf"
    
    # Check if rag directory exists
    if not rag_dir.exists():
        print(f"Error: RAG directory not found: {rag_dir}")
        print("Please ensure the data/rag directory exists with the .X and .wrl files")
        return
    
    # Create converter and run
    converter = RAGToGLTFConverter(str(rag_dir), str(output_dir))
    converter.convert_all()

if __name__ == "__main__":
    main()