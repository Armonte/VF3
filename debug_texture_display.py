#!/usr/bin/env python3
"""
Debug exactly what makes textures display correctly
"""

import sys
import os
import trimesh
import numpy as np
from PIL import Image

vf3_path = '/mnt/c/dev/loot/VF3'
if vf3_path not in sys.path:
    sys.path.append(vf3_path)

from vf3_xfile_parser import parse_directx_x_file_with_materials

def test_different_approaches():
    """Test different approaches to see what actually works for texture display"""
    
    head_path = '/mnt/c/dev/loot/vf3/data/satsuki/head.X'
    print(f"Testing texture approaches with: {head_path}")
    
    # Parse the mesh
    mesh_info = parse_directx_x_file_with_materials(head_path)
    mesh = mesh_info['mesh']
    
    print(f"Original mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    print(f"Materials: {len(mesh_info['materials'])}")
    print(f"UV coordinates: {len(mesh_info['uv_coords']) if 'uv_coords' in mesh_info else 'None'}")
    
    # Test 1: Export original mesh directly (like working version)
    print("\n=== TEST 1: Original mesh (no modifications) ===")
    test1_mesh = mesh.copy()
    test1_mesh.export('test1_original.glb')
    check_exported_textures('test1_original.glb', 'Test 1')
    
    # Test 2: Apply UV coordinates explicitly
    print("\n=== TEST 2: With explicit UV coordinates ===")
    test2_mesh = mesh.copy()
    if 'uv_coords' in mesh_info and mesh_info['uv_coords']:
        # Apply UV coordinates directly to the mesh
        test2_mesh.visual.uv = np.array(mesh_info['uv_coords'][:len(mesh.vertices)])
        print(f"Applied {len(test2_mesh.visual.uv)} UV coordinates")
    test2_mesh.export('test2_with_uv.glb')
    check_exported_textures('test2_with_uv.glb', 'Test 2')
    
    # Test 3: Create single material with main texture
    print("\n=== TEST 3: Single material with main texture ===")
    test3_mesh = mesh.copy()
    
    # Find the main face texture (stkface.bmp)
    main_texture_path = None
    for mat in mesh_info['materials']:
        if 'textures' in mat and mat['textures']:
            for tex in mat['textures']:
                if 'stkface' in tex.lower():
                    # Find the texture file
                    for root, dirs, files in os.walk('/mnt/c/dev/loot/vf3/data'):
                        if tex in files:
                            main_texture_path = os.path.join(root, tex)
                            break
                    break
    
    if main_texture_path and os.path.exists(main_texture_path):
        print(f"Found main texture: {main_texture_path}")
        
        # Load and apply texture
        try:
            image = Image.open(main_texture_path)
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Create material with texture
            material = trimesh.visual.material.PBRMaterial(
                baseColorTexture=image,
                baseColorFactor=[1.0, 1.0, 1.0, 1.0]
            )
            
            # Apply material and UV coordinates
            test3_mesh.visual = trimesh.visual.TextureVisuals(material=material)
            if 'uv_coords' in mesh_info and mesh_info['uv_coords']:
                test3_mesh.visual.uv = np.array(mesh_info['uv_coords'][:len(mesh.vertices)])
                print(f"Applied texture and {len(test3_mesh.visual.uv)} UV coordinates")
            
        except Exception as e:
            print(f"Failed to apply texture: {e}")
    else:
        print(f"Main texture not found: {main_texture_path}")
    
    test3_mesh.export('test3_single_material.glb')
    check_exported_textures('test3_single_material.glb', 'Test 3')
    
    # Test 4: Use vertex colors instead of textures (like working version might have)
    print("\n=== TEST 4: Vertex colors (like working version) ===")
    test4_mesh = mesh.copy()
    
    # Create vertex colors based on face materials
    if 'face_materials' in mesh_info and mesh_info['face_materials']:
        face_materials = mesh_info['face_materials']
        materials = mesh_info['materials']
        
        # Create vertex colors based on material diffuse colors
        vertex_colors = np.ones((len(test4_mesh.vertices), 4))  # Default white
        
        for face_idx, face in enumerate(test4_mesh.faces):
            if face_idx < len(face_materials):
                mat_idx = face_materials[face_idx]
                if mat_idx < len(materials) and 'diffuse' in materials[mat_idx]:
                    color = materials[mat_idx]['diffuse']
                    if len(color) >= 3:
                        # Apply color to all vertices of this face
                        for vertex_idx in face:
                            vertex_colors[vertex_idx] = color[:4] if len(color) >= 4 else list(color[:3]) + [1.0]
        
        test4_mesh.visual.vertex_colors = vertex_colors
        print(f"Applied vertex colors to {len(vertex_colors)} vertices")
    
    test4_mesh.export('test4_vertex_colors.glb')
    check_exported_textures('test4_vertex_colors.glb', 'Test 4')


def check_exported_textures(filename, test_name):
    """Check what's in the exported file"""
    try:
        scene = trimesh.load(filename)
        print(f"{test_name} export: {len(scene.geometry)} geometries")
        
        for name, mesh in scene.geometry.items():
            print(f"  {name}:")
            print(f"    Visual type: {type(mesh.visual).__name__}")
            
            if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                print(f"    UV coords: {len(mesh.visual.uv)} ✅")
            else:
                print(f"    UV coords: None ❌")
            
            if hasattr(mesh.visual, 'material') and mesh.visual.material:
                print(f"    Material: {type(mesh.visual.material).__name__}")
                if hasattr(mesh.visual.material, 'baseColorTexture') and mesh.visual.material.baseColorTexture:
                    print(f"    Texture: Yes ✅")
                else:
                    print(f"    Texture: No ❌")
            
            if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
                print(f"    Vertex colors: {len(mesh.visual.vertex_colors)} ✅")
            else:
                print(f"    Vertex colors: None")
    
    except Exception as e:
        print(f"{test_name} failed to load: {e}")


if __name__ == "__main__":
    test_different_approaches()