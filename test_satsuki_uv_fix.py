#!/usr/bin/env python3
"""
Test script to verify Satsuki UV mismatch fix is working
"""

import bpy
import sys
import os

# Clear existing mesh objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_uv_handler import preserve_and_apply_uv_coordinates

def test_satsuki_head_uv():
    """Test Satsuki head UV fix"""
    
    print("🔧 Testing Satsuki head UV mismatch fix...")
    
    # Load Satsuki head
    head_path = "data/satsuki/head.X"
    result = load_mesh_with_full_materials(head_path)
    
    if not result['mesh']:
        print("❌ Failed to load Satsuki head mesh")
        return False
    
    trimesh_mesh = result['mesh']
    print(f"📊 Trimesh mesh: {len(trimesh_mesh.vertices)} vertices")
    
    # Check UV coordinates
    uv_coords = None
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        uv_coords = trimesh_mesh.visual.uv
        print(f"📊 UV coordinates: {len(uv_coords)} UVs")
    else:
        print("❌ No UV coordinates found")
        return False
    
    # Create Blender mesh
    mesh_name = "satsuki_head_test"
    vertices = [(v[0], v[1], v[2]) for v in trimesh_mesh.vertices]
    faces = [(f[0], f[1], f[2]) for f in trimesh_mesh.faces]
    
    # Create mesh
    mesh = bpy.data.meshes.new(mesh_name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    
    print(f"📊 Blender mesh: {len(mesh.vertices)} vertices, {len(mesh.loops)} loops")
    
    # Test UV application
    try:
        preserve_and_apply_uv_coordinates(mesh, trimesh_mesh, "head_satsuki_head_material0_0")
        print("✅ UV application completed successfully")
        return True
    except Exception as e:
        print(f"❌ UV application failed: {e}")
        return False

if __name__ == "__main__":
    success = test_satsuki_head_uv()
    print(f"🎯 Test result: {'SUCCESS' if success else 'FAILED'}")