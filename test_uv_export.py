#!/usr/bin/env python3
"""
Test script to verify UV Map nodes are properly created and connected
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

print("🔍 Testing UV Map node creation and connections...")

# Import our modules
try:
    from vf3_xfile_parser import parse_directx_x_file_with_materials
    from vf3_uv_materials import assign_uv_coordinates, _create_blender_materials
    print("✅ Modules imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test Satsuki head only
head_path = '/mnt/c/dev/loot/vf3/data/satsuki/head.X'
if not os.path.exists(head_path):
    print(f'❌ Head file not found: {head_path}')
    sys.exit(1)

print(f'Loading {head_path}...')
mesh_info = parse_directx_x_file_with_materials(head_path)

if not mesh_info:
    print('❌ Failed to parse head.X')
    sys.exit(1)

trimesh_mesh = mesh_info.get('mesh')
if not trimesh_mesh:
    print('❌ No mesh in mesh_info')
    sys.exit(1)

print(f'Head mesh: {len(trimesh_mesh.vertices)} vertices, {len(trimesh_mesh.faces)} faces')

# Check UV coordinates in trimesh
if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
    print(f'Trimesh UVs: {len(trimesh_mesh.visual.uv)} coordinates')
else:
    print('❌ No UV coordinates in trimesh')
    sys.exit(1)

# Convert to Blender mesh
bm = bmesh.new()

# Add vertices and faces
for v in trimesh_mesh.vertices:
    bm.verts.new(v)

bm.verts.ensure_lookup_table()
for face in trimesh_mesh.faces:
    try:
        bm.faces.new([bm.verts[i] for i in face])
    except:
        pass  # Skip invalid faces

# Create Blender mesh
blender_mesh = bpy.data.meshes.new('satsuki_head_test')
bm.to_mesh(blender_mesh)
bm.free()

# Create mesh object
mesh_obj = bpy.data.objects.new('satsuki_head_test', blender_mesh)
bpy.context.collection.objects.link(mesh_obj)

print(f'Blender mesh: {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} faces')

# Apply UV coordinates
assign_uv_coordinates(blender_mesh, trimesh_mesh, mesh_info, 'satsuki_head_test')

# Check UV coordinates in Blender
if blender_mesh.uv_layers and blender_mesh.uv_layers.active:
    uv_data = blender_mesh.uv_layers.active.data
    print(f'Blender UV layer: {len(uv_data)} UV coords')
    
    # Sample first few UV coordinates
    sample_uvs = [(uv_data[i].uv[0], uv_data[i].uv[1]) for i in range(min(5, len(uv_data)))]
    print(f'Sample UV coords: {sample_uvs}')
else:
    print('❌ No UV layer in Blender mesh')

# Create materials
materials_created = 0
uv_connections_created = 0

if 'materials' in mesh_info and mesh_info['materials']:
    print(f"Creating {len(mesh_info['materials'])} materials...")
    _create_blender_materials(mesh_obj, mesh_info['materials'], trimesh_mesh, mesh_info)
    
    # Check that UV Map nodes were created and connected
    for mat in mesh_obj.data.materials:
        if mat and mat.use_nodes:
            materials_created += 1
            uv_map_nodes = [n for n in mat.node_tree.nodes if n.type == 'UVMAP']
            tex_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
            uv_links = [l for l in mat.node_tree.links if l.from_node.type == 'UVMAP' and l.to_node.type == 'TEX_IMAGE']
            tex_links = [l for l in mat.node_tree.links if l.from_node.type == 'TEX_IMAGE' and l.to_node.type == 'BSDF_PRINCIPLED']
            
            print(f'  Material {mat.name}:')
            print(f'    - UV Map nodes: {len(uv_map_nodes)}')
            print(f'    - Texture nodes: {len(tex_nodes)}')
            print(f'    - UV->Texture links: {len(uv_links)}')
            print(f'    - Texture->BSDF links: {len(tex_links)}')
            
            if len(uv_links) > 0:
                uv_connections_created += 1
                print(f'    ✅ UV Map properly connected')
            else:
                print(f'    ❌ UV Map NOT connected')

print(f"\n📊 SUMMARY:")
print(f"✅ Materials created: {materials_created}")
print(f"✅ UV connections: {uv_connections_created}")

# Export to GLB to test if UV coordinates are preserved
try:
    bpy.ops.export_scene.gltf(filepath='test_satsuki_head_uv.glb',
                             export_format='GLB',
                             export_selected=False,
                             export_animations=False)
    print('✅ Test export completed: test_satsuki_head_uv.glb')
except Exception as e:
    print(f'❌ Export failed: {e}')

print("🔍 Test completed!")