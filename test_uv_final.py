#!/usr/bin/env python3
"""
Final UV test - check if UV coordinates are preserved in export
"""

import bpy
import sys
import os
import bmesh

# Add the VF3 directory to path
vf3_path = '/mnt/c/dev/loot/VF3'
if vf3_path not in sys.path:
    sys.path.append(vf3_path)

# Clear the default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Import modules and parse head
from vf3_xfile_parser import parse_directx_x_file_with_materials
from vf3_uv_materials import assign_uv_coordinates, _create_blender_materials

head_path = '/mnt/c/dev/loot/vf3/data/satsuki/head.X'
mesh_info = parse_directx_x_file_with_materials(head_path)
trimesh_mesh = mesh_info['mesh']

# Convert to Blender
bm = bmesh.new()
for v in trimesh_mesh.vertices:
    bm.verts.new(v)
bm.verts.ensure_lookup_table()
for face in trimesh_mesh.faces:
    try:
        bm.faces.new([bm.verts[i] for i in face])
    except:
        pass

blender_mesh = bpy.data.meshes.new('satsuki_head_final')
bm.to_mesh(blender_mesh)
bm.free()

mesh_obj = bpy.data.objects.new('satsuki_head_final', blender_mesh)
bpy.context.collection.objects.link(mesh_obj)

# Apply UV coordinates and materials
assign_uv_coordinates(blender_mesh, trimesh_mesh, mesh_info, 'satsuki_head_final')
_create_blender_materials(mesh_obj, mesh_info['materials'], trimesh_mesh, mesh_info)

print(f"🔍 FINAL TEST:")
print(f"✅ Mesh: {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} faces")
print(f"✅ Materials: {len(mesh_obj.data.materials)}")
print(f"✅ UV layer: {len(blender_mesh.uv_layers.active.data)} coordinates")

# Export with correct parameters for Blender 4.x
try:
    bpy.ops.export_scene.gltf(
        filepath='test_satsuki_head_final.glb',
        export_format='GLB',
        export_materials='EXPORT',
        export_texcoords=True,
        export_animations=False
    )
    print('✅ Export successful: test_satsuki_head_final.glb')
except Exception as e:
    print(f'❌ Export failed: {e}')