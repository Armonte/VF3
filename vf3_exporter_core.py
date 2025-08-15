#!/usr/bin/env python3
"""
VF3 Blender Exporter - Core Module
Simplified, modular approach based on working export_ciel_to_gltf.py
"""

import os
import sys
import bpy
import bmesh
import trimesh
import numpy as np
from typing import List, Dict, Any, Optional
from mathutils import Vector, Matrix

# Add the project directory to Python path for imports
sys.path.append(os.path.dirname(__file__))

from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_materials import apply_simple_materials_to_mesh
from vf3_uv_handler import preserve_and_apply_uv_coordinates

def create_vf3_character_simple(bones, attachments, world_transforms, mesh_data, output_path):
    """
    Simplified VF3 character creation based on the working approach from export_ciel_to_gltf.py
    """
    print("🎌 Creating VF3 character in Blender (simplified approach)...")
    
    # Clear existing scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Step 1: Create armature first
    armature_obj = create_simple_armature(bones, world_transforms)
    
    # Step 2: Process each attachment - use the working approach
    mesh_objects = []
    
    for att in attachments:
        if att.resource_id not in mesh_data:
            continue
            
        mesh_info = mesh_data[att.resource_id]
        trimesh_mesh = mesh_info['mesh']
        
        if not trimesh_mesh:
            continue
        
        print(f"  Processing: {att.resource_id} → {att.attach_bone}")
        
        # Apply materials the WORKING way (like export_ciel_to_gltf.py)
        base_path = os.path.dirname(mesh_info.get('source_path', ''))
        processed_mesh = apply_simple_materials_to_mesh(
            trimesh_mesh, 
            mesh_info.get('materials', []), 
            mesh_info.get('textures', []), 
            base_path
        )
        
        # Create Blender mesh object
        mesh_obj = create_blender_mesh_from_trimesh(processed_mesh, att.resource_id, att.attach_bone)
        
        # Bind to armature
        bind_mesh_to_armature(mesh_obj, armature_obj, att.attach_bone)
        
        mesh_objects.append(mesh_obj)
    
    # Step 3: Export
    return export_to_glb_simple(armature_obj, mesh_objects, output_path)


def create_simple_armature(bones, world_transforms):
    """Create armature with simple bone hierarchy"""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    armature_obj = bpy.context.active_object
    armature_obj.name = "VF3_Armature"
    
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Clear default bone
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.delete()
    
    # Create bones
    created_bones = {}
    for bone_name, bone_data in bones.items():
        bone = armature_obj.data.edit_bones.new(bone_name)
        
        # Set bone position from world transforms
        if bone_name in world_transforms:
            pos = world_transforms[bone_name]  # This is already a (x,y,z) tuple
            bone.head = Vector(pos)
            bone.tail = Vector(pos) + Vector((0, 0, 1))  # Point upward
        
        created_bones[bone_name] = bone
        print(f"  Created bone '{bone_name}'")
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature_obj


def create_blender_mesh_from_trimesh(trimesh_mesh, mesh_name, bone_name):
    """Convert trimesh to Blender mesh - simplified approach"""
    
    # Create Blender mesh
    blender_mesh = bpy.data.meshes.new(mesh_name)
    
    # Get vertices and faces from trimesh
    vertices = trimesh_mesh.vertices
    faces = trimesh_mesh.faces
    
    # Create mesh data
    blender_mesh.from_pydata(vertices.tolist(), [], faces.tolist())
    blender_mesh.update()
    
    # Preserve UV coordinates the WORKING way (like export_ciel_to_gltf.py)
    preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, mesh_name)
    
    # Apply materials from trimesh to Blender
    apply_trimesh_materials_to_blender(blender_mesh, trimesh_mesh, mesh_name)
    
    # Create mesh object
    mesh_obj = bpy.data.objects.new(mesh_name, blender_mesh)
    bpy.context.collection.objects.link(mesh_obj)
    
    # Enable smooth shading
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.shade_smooth()
    
    return mesh_obj


def apply_trimesh_materials_to_blender(blender_mesh, trimesh_mesh, mesh_name):
    """Apply materials from trimesh to Blender mesh - simplified"""
    
    if not hasattr(trimesh_mesh.visual, 'material'):
        print(f"  No materials for {mesh_name}")
        return
    
    # Get material from trimesh
    trimesh_material = trimesh_mesh.visual.material
    
    # Create Blender material
    blender_mat = bpy.data.materials.new(name=f"{mesh_name}_material")
    blender_mat.use_nodes = True
    bsdf = blender_mat.node_tree.nodes.get("Principled BSDF")
    
    if hasattr(trimesh_material, 'baseColorTexture') and trimesh_material.baseColorTexture:
        # Has texture - convert PIL image to Blender texture
        texture_image = bpy.data.images.new(f"{mesh_name}_texture", 
                                          width=trimesh_material.baseColorTexture.width,
                                          height=trimesh_material.baseColorTexture.height)
        
        # Convert PIL image to Blender format
        pixels = np.array(trimesh_material.baseColorTexture).flatten() / 255.0
        texture_image.pixels = pixels
        
        # Create texture node
        tex_node = blender_mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = texture_image
        
        # Connect to BSDF
        blender_mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        
        # Handle alpha
        if hasattr(trimesh_material, 'alphaMode') and trimesh_material.alphaMode in ['MASK', 'BLEND']:
            blender_mat.node_tree.links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            blender_mat.blend_method = 'CLIP' if trimesh_material.alphaMode == 'MASK' else 'BLEND'
            if hasattr(trimesh_material, 'alphaCutoff'):
                blender_mat.alpha_threshold = trimesh_material.alphaCutoff
        
        print(f"  Applied texture material to {mesh_name}")
    
    elif hasattr(trimesh_material, 'baseColorFactor'):
        # Color-only material
        bsdf.inputs['Base Color'].default_value = trimesh_material.baseColorFactor
        print(f"  Applied color material to {mesh_name}")
    
    # Assign material to mesh
    blender_mesh.materials.append(blender_mat)


def bind_mesh_to_armature(mesh_obj, armature_obj, bone_name):
    """Bind mesh to specific bone"""
    
    # Create vertex group
    vertex_group = mesh_obj.vertex_groups.new(name=bone_name)
    vertex_indices = list(range(len(mesh_obj.data.vertices)))
    vertex_group.add(vertex_indices, 1.0, 'REPLACE')
    
    # Add armature modifier
    modifier = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    modifier.object = armature_obj
    modifier.use_vertex_groups = True
    
    print(f"  Bound {mesh_obj.name} to bone {bone_name}")


def export_to_glb_simple(armature_obj, mesh_objects, output_path):
    """Export to GLB with correct parameters"""
    
    # Select objects for export
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(True)
    
    bpy.context.view_layer.objects.active = armature_obj
    
    # Export with working parameters
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            use_selection=True,
            export_materials='EXPORT',
            export_colors=True,
            export_skins=True,
            export_animations=False,
            export_yup=True
        )
        print(f"✅ Export successful: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False