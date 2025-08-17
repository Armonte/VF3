#!/usr/bin/env python3
"""
Fix Satsuki textures by NOT splitting the mesh by materials
"""

import bpy
import sys
import os
import bmesh
import numpy as np
from PIL import Image

# Add the VF3 directory to path
vf3_path = '/mnt/c/dev/loot/VF3'
if vf3_path not in sys.path:
    sys.path.append(vf3_path)

# Clear the default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

from vf3_xfile_parser import parse_directx_x_file_with_materials

def create_unified_satsuki_head():
    """Create Satsuki head as a SINGLE mesh with primary texture (like the working approach)"""
    
    head_path = '/mnt/c/dev/loot/vf3/data/satsuki/head.X'
    mesh_info = parse_directx_x_file_with_materials(head_path)
    trimesh_mesh = mesh_info['mesh']
    
    print(f"Original mesh: {len(trimesh_mesh.vertices)} vertices, {len(trimesh_mesh.faces)} faces")
    
    # Convert to Blender as a SINGLE unified mesh (don't split by materials!)
    bm = bmesh.new()
    
    # Add all vertices
    for v in trimesh_mesh.vertices:
        bm.verts.new(v)
    bm.verts.ensure_lookup_table()
    
    # Add all faces
    for face in trimesh_mesh.faces:
        try:
            bm.faces.new([bm.verts[i] for i in face])
        except:
            pass  # Skip invalid faces
    
    # Create Blender mesh
    blender_mesh = bpy.data.meshes.new('satsuki_head_unified')
    bm.to_mesh(blender_mesh)
    bm.free()
    
    # Create mesh object
    mesh_obj = bpy.data.objects.new('satsuki_head_unified', blender_mesh)
    bpy.context.collection.objects.link(mesh_obj)
    
    print(f"Blender mesh: {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} faces")
    
    # Apply UV coordinates EXACTLY as they are (don't modify!)
    if 'uv_coords' in mesh_info and mesh_info['uv_coords']:
        uv_coords = mesh_info['uv_coords']
        print(f"Applying {len(uv_coords)} UV coordinates...")
        
        # Create UV layer
        if not blender_mesh.uv_layers:
            blender_mesh.uv_layers.new(name="UVMap")
        uv_layer = blender_mesh.uv_layers.active.data
        
        # Apply UV coordinates per-vertex (simple mapping)
        loop_index = 0
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                
                if vertex_idx < len(uv_coords):
                    u, v = uv_coords[vertex_idx]
                    # Use coordinates EXACTLY as they are (no modifications!)
                    uv_layer[loop_index].uv = (float(u), float(v))
                
                loop_index += 1
        
        print(f"✅ Applied UV coordinates to unified mesh")
    
    # Create a SINGLE material with the primary texture (stkface.bmp)
    material = bpy.data.materials.new(name="satsuki_face_unified")
    material.use_nodes = True
    
    # Get the Principled BSDF node
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    
    # Find the main face texture
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
        if main_texture_path:
            break
    
    if main_texture_path and os.path.exists(main_texture_path):
        print(f"Loading main texture: {main_texture_path}")
        
        # Load image in Blender
        image = bpy.data.images.load(main_texture_path)
        
        # Create UV Map node (CRITICAL!)
        uv_map_node = material.node_tree.nodes.new(type='ShaderNodeUVMap')
        uv_map_node.uv_map = 'UVMap'
        
        # Create texture node
        texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.image = image
        texture_node.interpolation = 'Closest'  # Pixel-perfect
        
        # Connect UV Map -> Texture -> BSDF
        material.node_tree.links.new(uv_map_node.outputs['UV'], texture_node.inputs['Vector'])
        material.node_tree.links.new(texture_node.outputs['Color'], bsdf.inputs['Base Color'])
        
        print("✅ Created unified material with main texture")
    else:
        print(f"❌ Main texture not found: {main_texture_path}")
        # Use a simple color material
        bsdf.inputs['Base Color'].default_value = [0.8, 0.6, 0.4, 1.0]  # Skin tone
    
    # Apply the single material to the entire mesh
    mesh_obj.data.materials.append(material)
    
    print(f"✅ Created unified Satsuki head with single material")
    
    return mesh_obj

# Create the unified head
satsuki_obj = create_unified_satsuki_head()

# Export with correct parameters
try:
    bpy.ops.export_scene.gltf(
        filepath='satsuki_head_unified_fixed.glb',
        export_format='GLB',
        export_materials='EXPORT',
        export_texcoords=True,
        export_animations=False
    )
    print('✅ Export successful: satsuki_head_unified_fixed.glb')
except Exception as e:
    print(f'❌ Export failed: {e}')

print("🎯 Unified approach test complete!")