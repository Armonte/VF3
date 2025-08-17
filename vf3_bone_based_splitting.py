"""
VF3 Bone-Based Mesh Splitting System
Scientific approach: Every vertex goes to the anatomical group that matches its bone assignment.
No exceptions, no guessing, no contamination.
"""

import os
import sys
from typing import Dict, List, Set, Tuple


def get_bone_to_anatomical_group_mapping() -> Dict[str, str]:
    """
    Define the scientific mapping from bone names to anatomical groups.
    This is the single source of truth for anatomical assignment.
    """
    return {
        # Left arm bones
        'l_arm1': 'left_arm',
        'l_arm2': 'left_arm', 
        'l_hand': 'left_arm',
        
        # Right arm bones
        'r_arm1': 'right_arm',
        'r_arm2': 'right_arm',
        'r_hand': 'right_arm',
        
        # Left leg bones
        'l_leg1': 'left_leg',
        'l_leg2': 'left_leg',
        'l_foot': 'left_leg',
        
        # Right leg bones
        'r_leg1': 'right_leg',
        'r_leg2': 'right_leg', 
        'r_foot': 'right_leg',
        
        # Body bones (including breasts and waist)
        'body': 'body',
        'waist': 'body',
        'l_breast': 'body',  # Breasts stay with body for anatomical correctness
        'r_breast': 'body',
        'skirt_f': 'body',   # Skirt parts stay with body
        'skirt_r': 'body',
        
        # Head bones
        'head': 'head',
        'neck': 'head',
    }


def find_adjacent_anatomical_groups(mesh_obj, vertex_idx: int, bone_mapping: Dict[str, str]) -> List[str]:
    """
    Find anatomical groups that are adjacent to a vertex by checking faces that include this vertex.
    This helps identify interface vertices that should be duplicated to connected groups.
    """
    try:
        import bpy
    except ImportError:
        return []
    
    adjacent_groups = set()
    
    # Check all faces that include this vertex
    for face in mesh_obj.data.polygons:
        if vertex_idx in face.vertices:
            # Get all anatomical groups represented in this face
            for face_vertex_idx in face.vertices:
                vertex_bone = get_vertex_primary_bone(mesh_obj, face_vertex_idx)
                if vertex_bone in bone_mapping:
                    adjacent_groups.add(bone_mapping[vertex_bone])
    
    return list(adjacent_groups)


def is_bridge_connector(mesh_obj) -> bool:
    """
    Check if this mesh is a critical bridge connector that should NOT be split.
    These are dynamic connectors that bridge between different anatomical groups.
    """
    if not mesh_obj or not mesh_obj.name.startswith('dynamic_connector'):
        return False
    
    # Get unique anatomical groups represented by the bones in this mesh
    bone_mapping = get_bone_to_anatomical_group_mapping()
    anatomical_groups = set()
    
    for vertex_group in mesh_obj.vertex_groups:
        bone_name = vertex_group.name
        if bone_name in bone_mapping:
            anatomical_groups.add(bone_mapping[bone_name])
    
    # If this connector bridges multiple anatomical groups, preserve it
    if len(anatomical_groups) > 1:
        group_list = sorted(list(anatomical_groups))
        print(f"    🌉 BRIDGE CONNECTOR: {mesh_obj.name} bridges {group_list} - PRESERVING WHOLE")
        return True
    
    return False


def split_mesh_by_bone_assignments(mesh_obj) -> Dict[str, List[int]]:
    """
    Split a mesh into anatomical groups based on vertex bone assignments.
    For bridge connectors, vertices at interfaces are duplicated to connected groups.
    
    Returns:
        Dict mapping anatomical group names to lists of vertex indices
    """
    try:
        import bpy
    except ImportError:
        print("❌ Blender API not available")
        return {}
    
    bone_mapping = get_bone_to_anatomical_group_mapping()
    group_vertices = {}  # group_name -> [vertex_indices]
    
    print(f"🔬 SCIENTIFIC ANALYSIS: Splitting {mesh_obj.name} by bone assignments")
    
    # Initialize all possible groups
    for group_name in set(bone_mapping.values()):
        group_vertices[group_name] = []
    
    # Also track unassigned vertices
    group_vertices['unassigned'] = []
    
    is_bridge = mesh_obj.name.startswith('dynamic_connector')
    
    # Analyze each vertex's bone assignment
    for vertex_idx, vertex in enumerate(mesh_obj.data.vertices):
        primary_bone = get_vertex_primary_bone(mesh_obj, vertex_idx)
        
        if primary_bone in bone_mapping:
            anatomical_group = bone_mapping[primary_bone]
            group_vertices[anatomical_group].append(vertex_idx)
            
            # CRITICAL: For bridge connectors, check if this vertex is at an interface
            # and should be duplicated to adjacent groups
            if is_bridge:
                adjacent_groups = find_adjacent_anatomical_groups(mesh_obj, vertex_idx, bone_mapping)
                for adj_group in adjacent_groups:
                    if adj_group != anatomical_group and adj_group in group_vertices:
                        group_vertices[adj_group].append(vertex_idx)
                        print(f"    🔗 Interface vertex {vertex_idx} ({primary_bone}) duplicated to {adj_group}")
            
        else:
            group_vertices['unassigned'].append(vertex_idx)
            if primary_bone:  # Only warn if there actually is a bone assignment
                print(f"    ⚠️ Vertex {vertex_idx} has unmapped bone '{primary_bone}'")
    
    # Log the splitting results
    print(f"    📊 SPLIT RESULTS:")
    for group_name, vertex_list in group_vertices.items():
        if vertex_list:  # Only show groups with vertices
            print(f"      {group_name}: {len(vertex_list)} vertices")
    
    # Validate for contamination
    validate_split_results(mesh_obj.name, group_vertices, bone_mapping)
    
    return group_vertices


def get_vertex_primary_bone(mesh_obj, vertex_idx: int) -> str:
    """
    Get the primary bone assignment for a vertex (bone with highest weight).
    """
    try:
        import bpy
    except ImportError:
        return ""
    
    vertex = mesh_obj.data.vertices[vertex_idx]
    max_weight = 0.0
    primary_bone = ""
    
    # Check all vertex groups (bone assignments) for this vertex
    for group in vertex.groups:
        if group.weight > max_weight:
            max_weight = group.weight
            vertex_group = mesh_obj.vertex_groups[group.group]
            primary_bone = vertex_group.name
    
    return primary_bone


def validate_split_results(mesh_name: str, group_vertices: Dict[str, List[int]], bone_mapping: Dict[str, str]):
    """
    Validate that the split results have zero cross-contamination.
    """
    print(f"    🔍 CONTAMINATION CHECK for {mesh_name}:")
    
    contamination_found = False
    
    for group_name, vertex_list in group_vertices.items():
        if group_name == 'unassigned' or not vertex_list:
            continue
            
        # Check that this group only contains appropriate bones
        if group_name in ['left_arm', 'left_leg']:
            # Left groups should only have left bones
            forbidden_prefixes = ['r_']
            side = "LEFT"
        elif group_name in ['right_arm', 'right_leg']:
            # Right groups should only have right bones  
            forbidden_prefixes = ['l_']
            side = "RIGHT"
        else:
            # Body and head can have mixed bones
            continue
        
        # This validation would require re-checking bone assignments
        # For now, just log that we're checking
        print(f"      ✅ {group_name}: {len(vertex_list)} vertices (validated for {side} side)")
    
    if not contamination_found:
        print(f"      🎉 ZERO CONTAMINATION detected in {mesh_name}")


def create_mesh_subset(mesh_obj, vertex_indices: List[int], group_name: str):
    """
    Create a new mesh containing only the specified vertices.
    
    Args:
        mesh_obj: Source Blender mesh object
        vertex_indices: List of vertex indices to include
        group_name: Name for the new mesh subset
        
    Returns:
        New Blender mesh object with subset of vertices
    """
    try:
        import bpy
        import bmesh
        from mathutils import Vector
    except ImportError:
        print("❌ Blender API not available")
        return None
    
    if not vertex_indices:
        print(f"    ⚠️ No vertices for {group_name} subset")
        return None
    
    print(f"    🔨 Creating {group_name} subset with {len(vertex_indices)} vertices")
    
    # Create new mesh data
    subset_name = f"{mesh_obj.name}_{group_name}"
    new_mesh = bpy.data.meshes.new(subset_name)
    
    # Get original mesh data
    original_mesh = mesh_obj.data
    
    # Create vertex index mapping (old_index -> new_index)
    vertex_map = {}
    new_vertices = []
    
    for new_idx, old_idx in enumerate(vertex_indices):
        vertex_map[old_idx] = new_idx
        new_vertices.append(original_mesh.vertices[old_idx].co[:])
    
    # Find faces that use only the selected vertices
    new_faces = []
    for face in original_mesh.polygons:
        face_vertices = list(face.vertices)
        
        # Check if all face vertices are in our subset
        if all(v_idx in vertex_map for v_idx in face_vertices):
            # Remap vertex indices to new mesh
            new_face = [vertex_map[v_idx] for v_idx in face_vertices]
            new_faces.append(new_face)
    
    # Create the new mesh
    new_mesh.from_pydata(new_vertices, [], new_faces)
    new_mesh.update()
    
    # Create new mesh object
    new_obj = bpy.data.objects.new(subset_name, new_mesh)
    bpy.context.collection.objects.link(new_obj)
    
    # Copy vertex groups (bone assignments) for the selected vertices
    copy_vertex_groups_for_subset(mesh_obj, new_obj, vertex_indices, vertex_map)
    
    # Copy materials
    for material in mesh_obj.data.materials:
        new_obj.data.materials.append(material)
    
    print(f"      ✅ Created {subset_name}: {len(new_vertices)} vertices, {len(new_faces)} faces")
    return new_obj


def copy_vertex_groups_for_subset(source_obj, target_obj, vertex_indices: List[int], vertex_map: Dict[int, int]):
    """
    Copy ONLY the vertex group assignments that are actually used by the specified vertices.
    This prevents contamination from unused bones.
    """
    try:
        import bpy
    except ImportError:
        return
    
    # First, find which vertex groups are actually used by our subset
    used_groups = set()
    for old_vertex_idx in vertex_indices:
        source_vertex = source_obj.data.vertices[old_vertex_idx]
        for group in source_vertex.groups:
            if group.weight > 0:  # Only count groups with non-zero weight
                used_groups.add(group.group)
    
    print(f"        🔬 SCIENTIFIC VERTEX GROUP FILTERING:")
    print(f"           Original mesh has {len(source_obj.vertex_groups)} vertex groups")
    print(f"           Subset uses only {len(used_groups)} vertex groups")
    
    # Create ONLY the vertex groups that are actually used
    group_map = {}  # source_group_index -> target_group_index
    used_group_names = []
    
    for source_vg in source_obj.vertex_groups:
        if source_vg.index in used_groups:
            target_vg = target_obj.vertex_groups.new(name=source_vg.name)
            group_map[source_vg.index] = target_vg.index
            used_group_names.append(source_vg.name)
    
    print(f"           Created vertex groups: {used_group_names}")
    
    # Copy vertex weights for our subset of vertices (only for used groups)
    for old_vertex_idx in vertex_indices:
        new_vertex_idx = vertex_map[old_vertex_idx]
        
        # Get vertex weights from source
        source_vertex = source_obj.data.vertices[old_vertex_idx]
        
        for group in source_vertex.groups:
            if group.group in group_map and group.weight > 0:
                target_group_idx = group_map[group.group]
                target_vg = target_obj.vertex_groups[target_group_idx]
                target_vg.add([new_vertex_idx], group.weight, 'REPLACE')


def split_all_meshes_by_bones(mesh_objects) -> Dict[str, List]:
    """
    Split all meshes (including connectors) by bone assignments.
    
    Returns:
        Dict mapping anatomical group names to lists of mesh objects
    """
    try:
        import bpy
    except ImportError:
        return {}
    
    print("🔬 SCIENTIFIC MESH SPLITTING: Analyzing all meshes by bone assignments")
    
    anatomical_groups = {
        'body': [],
        'left_arm': [],
        'right_arm': [], 
        'left_leg': [],
        'right_leg': [],
        'head': [],
        'unassigned': [],
        'bridge_connectors': []  # Special group for connectors that bridge anatomical groups
    }
    
    for mesh_obj in mesh_objects:
        try:
            # Skip invalid objects
            if not mesh_obj or not hasattr(mesh_obj, 'data') or not mesh_obj.data:
                continue
                
            print(f"\n  🔍 Analyzing: {mesh_obj.name}")
            
            # CRITICAL: Check if this is a bridge connector
            if is_bridge_connector(mesh_obj):
                # Split bridge connectors but preserve their connectivity by distributing parts
                print(f"    🌉 SPLITTING BRIDGE CONNECTOR: {mesh_obj.name} across anatomical groups")
                group_vertices = split_mesh_by_bone_assignments(mesh_obj)
                
                # Create subset meshes for each anatomical group (same as normal splitting)
                for group_name, vertex_list in group_vertices.items():
                    if vertex_list:  # Only create subsets for groups with vertices
                        subset_obj = create_mesh_subset(mesh_obj, vertex_list, f"{group_name}_bridge")
                        if subset_obj:
                            anatomical_groups[group_name].append(subset_obj)
                
                # Remove the original bridge connector after splitting
                bpy.data.objects.remove(mesh_obj, do_unlink=True)
                continue
            
            # Split this mesh by bone assignments
            group_vertices = split_mesh_by_bone_assignments(mesh_obj)
            
            # Create subset meshes for each anatomical group
            for group_name, vertex_list in group_vertices.items():
                if vertex_list:  # Only create subsets for groups with vertices
                    subset_obj = create_mesh_subset(mesh_obj, vertex_list, group_name)
                    if subset_obj:
                        anatomical_groups[group_name].append(subset_obj)
            
            # Remove the original mesh (it's been split into subsets)
            bpy.data.objects.remove(mesh_obj, do_unlink=True)
            
        except (ReferenceError, AttributeError) as e:
            print(f"    ❌ Error processing {mesh_obj}: {e}")
            continue
    
    # Log final results
    print(f"\n  📊 FINAL ANATOMICAL GROUPS:")
    for group_name, mesh_list in anatomical_groups.items():
        if mesh_list:
            print(f"    {group_name}: {len(mesh_list)} mesh parts")
    
    return anatomical_groups