"""
VF3 DynamicVisual System
Handles DynamicVisual mesh processing, bone grouping, and vertex snapping.
"""

import numpy as np
import trimesh
from typing import Dict, List, Any, Optional, Tuple
from vf3_materials import determine_dynamic_visual_material


def group_dynamic_visual_by_bone(dyn_data: Dict) -> Dict[str, Dict]:
    """
    CRITICAL: Group DynamicVisual vertices by bone to create separate meshes.
    This fixes the cross-bone binding issue for skeletal animation.
    """
    vertices = dyn_data['vertices']  # List of (pos1, pos2) tuples
    vertex_bones = dyn_data.get('vertex_bones', [])
    faces = np.array(dyn_data['faces'])
    
    # Group vertices by bone
    bone_vertex_groups = {}
    for v_idx, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
        if bone_name not in bone_vertex_groups:
            bone_vertex_groups[bone_name] = {
                'vertices': [],
                'vertex_indices': [],  # Original indices for face mapping
                'bone': bone_name
            }
        bone_vertex_groups[bone_name]['vertices'].append(vertex_tuple)
        bone_vertex_groups[bone_name]['vertex_indices'].append(v_idx)
    
    # Create face groups for each bone using MAJORITY RULE
    for bone_name, bone_group in bone_vertex_groups.items():
        original_indices = bone_group['vertex_indices']
        bone_vertices = bone_group['vertices']
        
        # Create mapping from original vertex index to new bone-local index
        index_mapping = {orig_idx: new_idx for new_idx, orig_idx in enumerate(original_indices)}
        
        # Filter faces using majority rule (>=2 vertices belong to this bone)
        bone_faces = []
        for face in faces:
            # Count how many vertices in this face belong to this bone
            bone_vertex_count = sum(1 for v_idx in face if v_idx in index_mapping)
            
            # Assign face to this bone if it has majority (>=2) vertices
            if bone_vertex_count >= 2:  # Majority rule - same as working export_minimal.py
                # For vertices not in this bone, add them temporarily to this bone's vertex list
                new_face = []
                for v_idx in face:
                    if v_idx in index_mapping:
                        new_face.append(index_mapping[v_idx])
                    else:
                        # Add vertex from other bone to this bone's vertex list
                        other_vertex = vertices[v_idx]  # vertices is from the outer scope
                        bone_vertices.append(other_vertex)
                        new_idx = len(bone_vertices) - 1
                        new_face.append(new_idx)
                        # Update the index mapping for future faces
                        index_mapping[v_idx] = new_idx
                
                bone_faces.append(new_face)
        
        # Update the bone group with the expanded vertex list and faces
        bone_group['vertices'] = bone_vertices
        bone_group['faces'] = np.array(bone_faces) if bone_faces else np.array([]).reshape(0, 3)
    
    return bone_vertex_groups


def group_vertices_by_anatomical_region(vertices: List[Tuple], vertex_bones: List[str]) -> Dict[str, Dict]:
    """
    Group vertices by anatomical regions to create separate connectors.
    E.g. l_arm1+l_arm2 = left_elbow, r_arm1+r_arm2 = right_elbow
    """
    # Define anatomical region mappings
    region_mappings = {
        # Arms
        'left_elbow': ['l_arm1', 'l_arm2'],
        'right_elbow': ['r_arm1', 'r_arm2'], 
        # Legs
        'left_knee': ['l_leg1', 'l_leg2'],
        'right_knee': ['r_leg1', 'r_leg2'],
        # Hands
        'left_wrist': ['l_arm2', 'l_hand'],
        'right_wrist': ['r_arm2', 'r_hand'],
        # Feet
        'left_ankle': ['l_leg2', 'l_foot'],
        'right_ankle': ['r_leg2', 'r_foot'],
        # Body connections
        'torso_waist': ['body', 'waist'],
        'left_shoulder': ['body', 'l_arm1', 'l_breast'],
        'right_shoulder': ['body', 'r_arm1', 'r_breast'],
        # Hip connections (MISSING - CRITICAL)
        'left_hip': ['waist', 'l_leg1'],
        'right_hip': ['waist', 'r_leg1'],
        # Breast connections (MISSING - CRITICAL) 
        'left_breast_connection': ['body', 'l_breast'],
        'right_breast_connection': ['body', 'r_breast'],
    }
    
    # Group vertices by region
    regions = {}
    
    for i, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
        # Find which region this bone belongs to
        assigned_region = None
        for region_name, bone_list in region_mappings.items():
            if bone_name in bone_list:
                assigned_region = region_name
                break
        
        # If no specific region found, use bone name as region
        if assigned_region is None:
            assigned_region = f"misc_{bone_name}"
        
        # Add to region
        if assigned_region not in regions:
            regions[assigned_region] = {
                'vertices': [],
                'vertex_bones': [],
                'indices': []
            }
        
        regions[assigned_region]['vertices'].append(vertex_tuple)
        regions[assigned_region]['vertex_bones'].append(bone_name)
        regions[assigned_region]['indices'].append(i)
    
    return regions


def snap_vertex_to_mesh(candidate_pos: List[float], all_mesh_vertices: np.ndarray, snap_threshold: float = 1.0) -> List[float]:
    """Snap a vertex to the nearest existing mesh vertex if within threshold."""
    if len(all_mesh_vertices) == 0:
        return candidate_pos
    
    # Find closest vertex
    distances = np.linalg.norm(all_mesh_vertices - candidate_pos, axis=1)
    min_distance = np.min(distances)
    
    if min_distance <= snap_threshold:
        closest_idx = np.argmin(distances)
        snapped_pos = all_mesh_vertices[closest_idx].tolist()
        return snapped_pos
    else:
        return candidate_pos


def create_bone_dynamic_visual_mesh(bone_name: str, bone_group: Dict, world_transforms: Dict, 
                                  all_mesh_vertices: np.ndarray, connector_idx: int, bone_idx: int) -> Optional[trimesh.Trimesh]:
    """Create a DynamicVisual mesh for a specific bone group."""
    bone_vertices = bone_group['vertices']
    bone_faces = bone_group['faces']
    
    if len(bone_faces) == 0:
        print(f"    WARNING: No faces for bone {bone_name}, skipping")
        return None
    
    # Get bone's world position
    bone_pos = world_transforms.get(bone_name, (0.0, 0.0, 0.0))
    
    # Process vertices
    snapped_vertices = []
    for vertex_tuple in bone_vertices:
        pos1, pos2 = vertex_tuple
        
        # Use pos2 positioned relative to bone (this was working better in original code)
        candidate_pos = [
            pos2[0] + bone_pos[0],
            pos2[1] + bone_pos[1],
            pos2[2] + bone_pos[2]
        ]
        
        # Snap to nearest existing mesh vertex
        snapped_pos = snap_vertex_to_mesh(candidate_pos, all_mesh_vertices)
        snapped_vertices.append(snapped_pos)
    
    # Create mesh
    try:
        bone_mesh = trimesh.Trimesh(vertices=np.array(snapped_vertices), faces=bone_faces)
        
        # Apply world transform to position mesh correctly
        world_T = np.eye(4)
        world_T[:3, 3] = np.array(bone_pos, dtype=float)
        bone_mesh.apply_transform(world_T)
        
        print(f"    Created bone mesh for {bone_name}: {len(snapped_vertices)} vertices, {len(bone_faces)} faces")
        return bone_mesh
        
    except Exception as e:
        print(f"    Failed to create bone mesh for {bone_name}: {e}")
        return None


def process_dynamic_visual_meshes(dynamic_meshes: List[Dict], world_transforms: Dict, 
                                all_mesh_vertices: np.ndarray, all_materials: Dict, 
                                geometry_to_mesh_map: Dict, scene: trimesh.Scene) -> int:
    """
    Process DynamicVisual meshes, creating separate meshes for each bone group.
    Returns the number of connector meshes created.
    """
    if not dynamic_meshes:
        return 0
    
    print(f"\nDEBUG: Processing {len(dynamic_meshes)} DynamicVisual mesh sections...")
    
    total_connectors = 0
    
    # Process ALL DynamicVisual meshes for complete naked character export
    for i, dyn_data in enumerate(dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
        
        vertices = dyn_data['vertices']
        faces = np.array(dyn_data['faces'])
        vertex_bones = dyn_data.get('vertex_bones', [])
        
        print(f"  DynamicVisual mesh {i}: {len(vertices)} vertices, {len(faces)} faces")
        
        # FIXED: Group by bone pairs/regions to avoid stretching across the body
        # Each anatomical connector (left elbow, right elbow, etc.) should be separate
        bone_groups = group_vertices_by_anatomical_region(vertices, vertex_bones)
        print(f"    Split into {len(bone_groups)} anatomical regions: {list(bone_groups.keys())}")
        
        # Create separate connector for each anatomical region
        for region_name, region_data in bone_groups.items():
            region_vertices = region_data['vertices']
            region_vertex_bones = region_data['vertex_bones'] 
            region_indices = region_data['indices']
            
            print(f"    Processing region '{region_name}' with {len(region_vertices)} vertices from bones: {set(region_vertex_bones)}")
            
            # Filter faces using MAJORITY RULE (>=2 vertices belong to this region)
            region_faces = []
            vertex_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(region_indices)}
            
            for face in faces:
                # Count how many vertices in this face belong to this region
                vertices_in_region = [v_idx in vertex_mapping for v_idx in face]
                vertices_in_region_count = sum(vertices_in_region)
                
                # Use majority rule: face belongs to this region if >= 2 vertices are in it
                if vertices_in_region_count >= 2:
                    # Create new face, adding missing vertices from other regions to this region
                    new_face = []
                    for v_idx in face:
                        if v_idx in vertex_mapping:
                            # Vertex already in this region
                            new_face.append(vertex_mapping[v_idx])
                        else:
                            # Add vertex from another region to this region's vertex list
                            other_vertex = vertices[v_idx]
                            other_bone = vertex_bones[v_idx] if v_idx < len(vertex_bones) else 'unknown'
                            region_vertices.append(other_vertex)
                            region_vertex_bones.append(other_bone)
                            region_indices.append(v_idx)
                            new_idx = len(region_vertices) - 1
                            new_face.append(new_idx)
                            # Update mapping for future faces
                            vertex_mapping[v_idx] = new_idx
                    
                    region_faces.append(new_face)
            
            if len(region_faces) == 0:
                print(f"      No faces for region {region_name}, skipping")
                continue
                
            print(f"      Region {region_name}: {len(region_vertices)} vertices, {len(region_faces)} faces")
            
            try:
                # Process vertices with proper bone-relative positioning
                snapped_vertices = []
                for idx, (vertex_tuple, bone_name) in enumerate(zip(region_vertices, region_vertex_bones)):
                    pos1, pos2 = vertex_tuple
                    
                    # Get bone's world position for this vertex
                    bone_pos = world_transforms.get(bone_name, (0.0, 0.0, 0.0))
                    
                    # Use pos1 + bone_transform (like regular meshes)
                    candidate_pos = [pos1[0] + bone_pos[0], pos1[1] + bone_pos[1], pos1[2] + bone_pos[2]]
                    
                    # Skip snapping to preserve connector shape
                    snapped_pos = candidate_pos
                    snapped_vertices.append(snapped_pos)
                
                # Create region-specific trimesh
                region_faces_array = np.array(region_faces)
                print(f"      Creating region trimesh: {len(snapped_vertices)} vertices, {len(region_faces_array)} faces")
                
                connector_mesh = trimesh.Trimesh(vertices=np.array(snapped_vertices), faces=region_faces_array)
                print(f"      ✅ Created {region_name} connector: {len(snapped_vertices)} vertices, {len(region_faces_array)} faces")
                
                # Determine material for this connector
                connector_material = determine_dynamic_visual_material(dyn_data, geometry_to_mesh_map, all_materials, total_connectors)
                
                # Create PBR material
                material = trimesh.visual.material.PBRMaterial()
                material.name = f"dynamic_connector_{total_connectors}_{region_name}_material"
                material.baseColorFactor = connector_material['color']
                
                # Apply material to mesh
                try:
                    connector_mesh.visual = trimesh.visual.TextureVisuals(material=material)
                    print(f"        Applied {connector_material['type']} to {region_name} connector")
                except Exception:
                    # Fallback to face colors
                    connector_mesh.visual.face_colors = connector_material['color']
                    print(f"        Applied {connector_material['type']} to {region_name} connector (fallback)")
                
                # Add to scene
                connector_name = f"dynamic_connector_{total_connectors}_{region_name}"
                scene.add_geometry(connector_mesh, node_name=connector_name)
                print(f"        ✅ Added {region_name} connector to scene")
                
                total_connectors += 1
                
            except Exception as e:
                print(f"      ❌ Failed to create {region_name} connector: {e}")
                continue
    
    return total_connectors
