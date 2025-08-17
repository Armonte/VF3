#!/usr/bin/env python3
"""
Test script to verify UV coordinate application is working correctly
"""

import bpy
import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_uv_handler import preserve_and_apply_uv_coordinates

def test_uv_coordinates():
    """Test that UV coordinates are being applied correctly"""
    
    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Load Satsuki head mesh
    print("Loading Satsuki head mesh...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    
    if not mesh_info['mesh']:
        print("❌ Failed to load mesh")
        return False
        
    trimesh_mesh = mesh_info['mesh']
    print(f"✅ Loaded mesh: {len(trimesh_mesh.vertices)} vertices")
    
    # Check trimesh UV coordinates
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        print(f"✅ Trimesh has UV coordinates: {len(trimesh_mesh.visual.uv)}")
        print(f"   First 3 UVs: {trimesh_mesh.visual.uv[:3]}")
        print(f"   UV range: U({trimesh_mesh.visual.uv[:, 0].min():.3f}-{trimesh_mesh.visual.uv[:, 0].max():.3f}) V({trimesh_mesh.visual.uv[:, 1].min():.3f}-{trimesh_mesh.visual.uv[:, 1].max():.3f})")
    else:
        print("❌ No UV coordinates in trimesh")
        return False
    
    # Create Blender mesh
    blender_mesh = bpy.data.meshes.new("test_head")
    vertices = trimesh_mesh.vertices.tolist()
    faces = trimesh_mesh.faces.tolist()
    blender_mesh.from_pydata(vertices, [], faces)
    blender_mesh.update()
    
    print(f"✅ Created Blender mesh: {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} faces")
    
    # Apply UV coordinates
    preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, "test_head", mesh_info)
    
    # Verify UV coordinates were applied
    if blender_mesh.uv_layers:
        uv_layer = blender_mesh.uv_layers.active.data
        print(f"✅ Blender mesh has UV layer: {len(uv_layer)} loops")
        
        # Sample some UV coordinates
        sample_uvs = []
        for i in range(min(10, len(uv_layer))):
            sample_uvs.append((uv_layer[i].uv[0], uv_layer[i].uv[1]))
        
        print(f"   Sample UVs: {sample_uvs[:5]}")
        
        # Check UV ranges
        all_u = [uv.uv[0] for uv in uv_layer]
        all_v = [uv.uv[1] for uv in uv_layer]
        print(f"   Blender UV range: U({min(all_u):.3f}-{max(all_u):.3f}) V({min(all_v):.3f}-{max(all_v):.3f})")
        
        # Create mesh object and save as .blend for inspection
        mesh_obj = bpy.data.objects.new("test_head", blender_mesh)
        bpy.context.collection.objects.link(mesh_obj)
        
        # Save .blend file for manual inspection
        bpy.ops.wm.save_as_mainfile(filepath="satsuki_head_uv_test.blend")
        print("✅ Saved satsuki_head_uv_test.blend for manual inspection")
        
        return True
    else:
        print("❌ No UV layer created in Blender mesh")
        return False

if __name__ == "__main__":
    result = test_uv_coordinates()
    if result:
        print("🎉 UV coordinate application test PASSED")
    else:
        print("❌ UV coordinate application test FAILED")