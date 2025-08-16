"""
VF3 Dynamic Visual Processing - Extracted from working vf3_blender_exporter.py
Handles DynamicVisual mesh data and connector creation.
"""

import os
import sys
from typing import List, Dict, Any


def _create_dynamic_visual_meshes(clothing_dynamic_meshes, world_transforms, created_bones, 
                                 armature_obj, mesh_objects, mesh_data):
    """Create DynamicVisual connector meshes in Blender with proper bone binding."""
    try:
        import bpy
        import bmesh
        import numpy as np
        from mathutils import Vector
    except ImportError:
        print("  Blender imports not available")
        return 0
    
    if not clothing_dynamic_meshes:
        print("  No DynamicVisual meshes to process")
        return 0
    
    connector_count = 0
    created_regions = set()  # Track regions already created to prevent duplicates
    
    # Collect all mesh vertices for snapping (with safety checks for deleted objects)
    all_mesh_vertices = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            _ = mesh_obj.name
            if hasattr(mesh_obj.data, 'vertices'):
                for v in mesh_obj.data.vertices:
                    world_co = mesh_obj.matrix_world @ v.co
                    all_mesh_vertices.append(world_co)
        except (ReferenceError, AttributeError):
            # Object has been deleted during merging, skip it
            continue
    
    all_mesh_vertices = np.array([[v.x, v.y, v.z] for v in all_mesh_vertices])
    print(f"  Collected {len(all_mesh_vertices)} vertices from existing meshes for snapping")
    
    for dyn_idx, dyn_data in enumerate(clothing_dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
            
        vertices = dyn_data['vertices']  # List of (pos1, pos2) tuples
        vertex_bones = dyn_data.get('vertex_bones', [])
        faces = np.array(dyn_data['faces'])
        face_materials = dyn_data.get('face_materials', [])  # Face-to-material mapping from FaceArray
        materials = dyn_data.get('materials', [])  # Pre-defined materials from Material: section
        
        if len(vertices) == 0 or len(faces) == 0:
            continue
            
        print(f"  Processing DynamicVisual mesh {dyn_idx}: {len(vertices)} vertices, {len(faces)} faces")
        
        # Use TRUE VF3-accurate approach: Create ONE mesh per DynamicVisual block using EXACT FaceArray
        # This is exactly how VF3 works - no anatomical grouping, just one geometry per block
        print(f"    Using TRUE VF3-accurate approach: ONE mesh with {len(faces)} exact faces")
        
        # Use faces EXACTLY as provided by VF3 FaceArray (no reconstruction)
        connector_faces = faces  # Use exact face connectivity from VF3
        
        # Process vertices with their bone binding information + snap to eliminate seams
        processed_vertices = []
        vertex_bone_names = []
        
        for i, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
            pos1, pos2 = vertex_tuple
            
            # Get bone's world position
            bone_pos = world_transforms.get(bone_name, (0.0, 0.0, 0.0))
            
            # Use pos1 + bone transform (like regular meshes) - back to original simple logic
            candidate_pos = [
                pos1[0] + bone_pos[0],
                pos1[1] + bone_pos[1], 
                pos1[2] + bone_pos[2]
            ]
            
            # Snap to nearest existing mesh vertex to eliminate seams/gaps  
            snapped_pos = _snap_vertex_to_nearest_mesh(candidate_pos, all_mesh_vertices, snap_threshold=0.5)
            
            processed_vertices.append(snapped_pos)
            vertex_bone_names.append(bone_name)
        
        # Create ONE Blender mesh for this entire DynamicVisual block (like VF3)
        connector_name = f"dynamic_connector_{connector_count}_vf3mesh"
        blender_mesh = bpy.data.meshes.new(connector_name)
        
        # Create mesh with EXACT VF3 faces - no modifications
        vertices_list = [[v[0], v[1], v[2]] for v in processed_vertices]
        faces_list = connector_faces  # Use exact faces from VF3 FaceArray
        
        blender_mesh.from_pydata(vertices_list, [], faces_list)
        blender_mesh.update()
        
        # Enable smooth shading
        for poly in blender_mesh.polygons:
            poly.use_smooth = True
        
        # Create mesh object
        connector_obj = bpy.data.objects.new(connector_name, blender_mesh)
        bpy.context.collection.objects.link(connector_obj)
        
        # CRITICAL FIX: Use actual VF3-defined materials instead of guessing from bone content
        if materials and face_materials:
            _assign_vf3_materials_to_connector(connector_obj, materials, face_materials)
            print(f"      ✅ Applied {len(materials)} VF3-defined materials to connector {connector_name}")
        else:
            # Fallback for connectors without materials (shouldn't happen with proper parsing)
            _assign_anatomical_material_to_connector(connector_obj, vertex_bone_names, mesh_objects)
            print(f"      ⚠️ Fallback: Created anatomical material for connector {connector_name} (no VF3 materials found)")
        
        # Bind vertices to their respective bones (like VF3 does with bone flags)
        created_vertex_groups = set()
        for vertex_idx, bone_name in enumerate(vertex_bone_names):
            if bone_name in created_bones and bone_name not in created_vertex_groups:
                vertex_group = connector_obj.vertex_groups.new(name=bone_name)
                created_vertex_groups.add(bone_name)
            
            # Bind this vertex to its bone with full weight
            if bone_name in created_vertex_groups:
                vertex_group = connector_obj.vertex_groups[bone_name]
                vertex_group.add([vertex_idx], 1.0, 'REPLACE')
        
        # Add armature modifier
        armature_modifier = connector_obj.modifiers.new(name="Armature", type='ARMATURE')
        armature_modifier.object = armature_obj
        armature_modifier.use_vertex_groups = True
        
        # Try to merge this connector with adjacent body meshes to eliminate seams completely
        print(f"      DEBUG: Attempting to merge connector {connector_name} with available meshes:")
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name
                materials = [mat.name for mat in mesh_obj.data.materials] if mesh_obj.data.materials else ['NO_MATERIALS']
                bone_groups = [vg.name for vg in mesh_obj.vertex_groups]
                print(f"        Available mesh: {mesh_name}, materials: {materials}, bones: {bone_groups[:5]}...")
            except (ReferenceError, AttributeError):
                print(f"        Invalid mesh object (deleted)")
        
        # DISABLED: Old connector merging - now handled by anatomical grouping system
        # from vf3_mesh_merging import _try_merge_connector_with_body_mesh
        # merged_with_existing, merged_mesh_names = _try_merge_connector_with_body_mesh(connector_obj, mesh_objects, vertex_bone_names)
        merged_with_existing = False
        merged_mesh_names = []
        
        if not merged_with_existing:
            # Add to mesh objects list for export only if not merged
            mesh_objects.append(connector_obj)
            connector_materials = [mat.name for mat in connector_obj.data.materials] if connector_obj.data.materials else ['NO_MATERIALS']
            print(f"    ✅ Created standalone VF3 connector: {connector_name} with {len(vertices_list)} vertices, {len(faces_list)} faces, materials: {connector_materials}")
        else:
            # Remove merged meshes from mesh_objects list to prevent issues with subsequent connectors
            if merged_mesh_names:
                # Be careful with object filtering - check if objects are still valid
                valid_objects = []
                for m in mesh_objects:
                    try:
                        mesh_name = m.name
                        if mesh_name not in merged_mesh_names:
                            valid_objects.append(m)
                    except (ReferenceError, AttributeError):
                        # Object has been deleted, skip it
                        pass
                mesh_objects[:] = valid_objects
                print(f"    ✅ Merged VF3 connector: {connector_name} with existing body mesh, removed {len(merged_mesh_names)} merged meshes from list")
            else:
                print(f"    ✅ Merged VF3 connector: {connector_name} with existing body mesh")
            
            # DEBUG: Check final material on remaining merged mesh
            remaining_meshes = [obj for obj in mesh_objects if obj.type == 'MESH']
            for mesh_obj in remaining_meshes:
                try:
                    if any(vg.name == 'body' for vg in mesh_obj.vertex_groups):
                        final_materials = [mat.name for mat in mesh_obj.data.materials] if mesh_obj.data.materials else ['NO_MATERIALS']
                        print(f"      Final merged mesh {mesh_obj.name} materials: {final_materials}")
                        break
                except (ReferenceError, AttributeError):
                    continue
        
        connector_count += 1
    return connector_count


def _snap_vertex_to_nearest_mesh(candidate_pos: List[float], all_mesh_vertices, snap_threshold: float = 0.5) -> List[float]:
    """Snap a vertex to the nearest mesh vertex if within threshold."""
    try:
        import numpy as np
    except ImportError:
        return candidate_pos
    
    if len(all_mesh_vertices) == 0:
        return candidate_pos
    
    # Calculate distances to all mesh vertices
    candidate_array = np.array(candidate_pos)
    distances = np.linalg.norm(all_mesh_vertices - candidate_array, axis=1)
    
    # Find the nearest vertex
    nearest_idx = np.argmin(distances)
    nearest_distance = distances[nearest_idx]
    
    # Snap if within threshold
    if nearest_distance <= snap_threshold:
        snapped_pos = all_mesh_vertices[nearest_idx].tolist()
        return snapped_pos
    else:
        return candidate_pos


# Legacy functions for compatibility
def process_vf3_dynamic_visual_faces(vertices, vertex_bones, faces, dyn_idx, world_transforms, 
                                    created_bones, armature_obj, mesh_objects, base_connector_count):
    """Legacy function - redirects to new implementation."""
    print("⚠️ Using legacy dynamic visual processing - this is not the correct approach")
    return base_connector_count

def _snap_connector_vertices_to_meshes(connector_vertices, mesh_objects, snap_threshold=1.5):
    """Legacy function for compatibility."""
    return connector_vertices

def _assign_vf3_materials_to_connector(connector_obj, materials, face_materials):
    """Assign VF3-defined materials to connector faces using exact FaceArray mapping."""
    try:
        import bpy
    except ImportError:
        return
    
    print(f"        Creating {len(materials)} VF3 materials from DynamicVisual Material: section")
    
    # Parse and create Blender materials from VF3 material strings
    blender_materials = []
    for i, mat_str in enumerate(materials):
        material_name = f"VF3_DynamicVisual_Material_{i}"
        
        # Parse VF3 material format: (r,g,b,a)::
        rgba = _parse_vf3_material_color(mat_str)
        if rgba:
            # Create Blender material with parsed color
            blender_mat = bpy.data.materials.new(name=material_name)
            blender_mat.use_nodes = True
            bsdf = blender_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                # Convert from 0-255 to 0-1 range and apply VF3 gamma correction
                corrected_color = [
                    pow(rgba[0] / 255.0, 2.2),  # VF3 uses gamma 2.2
                    pow(rgba[1] / 255.0, 2.2), 
                    pow(rgba[2] / 255.0, 2.2),
                    rgba[3] / 255.0  # Alpha stays linear
                ]
                bsdf.inputs['Base Color'].default_value = corrected_color
                bsdf.inputs['Alpha'].default_value = corrected_color[3]
            
            blender_materials.append(blender_mat)
            connector_obj.data.materials.append(blender_mat)
            print(f"          Material {i}: {rgba} -> {material_name}")
        else:
            print(f"          ❌ Failed to parse material {i}: {mat_str}")
    
    # Assign materials to faces using FaceArray mapping
    if len(face_materials) == len(connector_obj.data.polygons):
        for face_idx, material_index in enumerate(face_materials):
            if 0 <= material_index < len(blender_materials):
                connector_obj.data.polygons[face_idx].material_index = material_index
            else:
                print(f"          ⚠️ Face {face_idx} material index {material_index} out of range (0-{len(blender_materials)-1})")
        print(f"        ✅ Assigned per-face materials: {len(face_materials)} faces mapped to {len(blender_materials)} materials")
    else:
        print(f"        ❌ Face material count mismatch: {len(face_materials)} mappings vs {len(connector_obj.data.polygons)} faces")


def _parse_vf3_material_color(mat_str):
    """Parse VF3 material string like '(255,255,255,255)::' to RGBA tuple."""
    import re
    match = re.search(r'\((\d+),(\d+),(\d+),(\d+)\)', mat_str)
    if match:
        return tuple(int(x) for x in match.groups())
    return None


def _assign_anatomical_material_to_connector(connector_obj, vertex_bone_names, mesh_objects):
    """Assign anatomically appropriate material to connector based on bone content."""
    try:
        import bpy
    except ImportError:
        return
    
    # Analyze bone content to determine anatomical region
    bone_counts = {}
    for bone_name in vertex_bone_names:
        bone_counts[bone_name] = bone_counts.get(bone_name, 0) + 1
    
    # Determine primary anatomical region based on dominant bones
    if any('body' in bone or 'waist' in bone for bone in bone_counts):
        material_type = 'skin'  # Body/waist connectors should be skin tone
    elif any('leg' in bone or 'foot' in bone for bone in bone_counts):
        material_type = 'skin'  # Leg connectors should be skin tone
    elif any('arm' in bone or 'hand' in bone for bone in bone_counts):
        material_type = 'skin'  # Arm connectors should be skin tone
    elif any('blazer' in bone or 'coat' in bone for bone in bone_counts):
        material_type = 'clothing'  # Clothing connectors inherit clothing materials
    else:
        material_type = 'skin'  # Default to skin tone for unknown regions
    
    # Find appropriate material from existing meshes
    target_material = None
    
    if material_type == 'skin':
        # Look for skin-tone materials in female body parts
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if ('female' in mesh_name or 'hand' in mesh_name or 'leg' in mesh_name) and mesh_obj.data.materials:
                    for mat in mesh_obj.data.materials:
                        if mat and _is_skin_material(mat):
                            target_material = mat
                            break
                    if target_material:
                        break
            except (ReferenceError, AttributeError):
                continue
    else:
        # Look for clothing materials in blazer/costume parts
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower() 
                if ('blazer' in mesh_name or 'coat' in mesh_name) and mesh_obj.data.materials:
                    for mat in mesh_obj.data.materials:
                        if mat and not _is_skin_material(mat):
                            target_material = mat
                            break
                    if target_material:
                        break
            except (ReferenceError, AttributeError):
                continue
    
    # Apply the material to the connector
    if target_material:
        connector_obj.data.materials.append(target_material)
        print(f"        Assigned {material_type} material '{target_material.name}' to connector")
    else:
        # Create a default skin-tone material
        default_mat = bpy.data.materials.new(name=f"Connector_Default_{material_type}")
        default_mat.use_nodes = True
        bsdf = default_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if material_type == 'skin':
                bsdf.inputs['Base Color'].default_value = (0.8, 0.7, 0.6, 1.0)  # Skin tone
            else:
                bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.7, 1.0)  # Neutral
        connector_obj.data.materials.append(default_mat)
        print(f"        Created default {material_type} material for connector")


def _is_skin_material(material):
    """Check if a material appears to be skin-tone based on color."""
    try:
        if not material.use_nodes:
            return False
        
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            return False
            
        color = bsdf.inputs['Base Color'].default_value
        if len(color) < 3:
            return False
            
        # Check if color is in skin tone range
        r, g, b = color[0], color[1], color[2]
        
        # Skin tones are typically:
        # - Higher red than blue
        # - Moderate to high brightness
        # - Not pure white, black, or highly saturated colors
        if (r > 0.4 and g > 0.3 and b > 0.2 and  # Minimum skin tone values
            r > b and g > b * 0.8 and  # More red than blue, similar green/blue ratio
            max(r, g, b) > 0.5 and  # Not too dark
            max(r, g, b) < 0.95):  # Not pure white
            return True
            
        return False
    except:
        return False


def _bind_connector_to_bone(connector_obj, armature_obj, bone_name, created_bones):
    """Legacy function for compatibility."""
    pass

def _get_joint_bone_weights_for_region(region_name: str, region_vertex_bones: List[str], created_bones: Dict) -> Dict[str, float]:
    """Legacy function for compatibility."""
    return {}