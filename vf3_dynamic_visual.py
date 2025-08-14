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
    
    print(f"\nProcessing {len(dynamic_meshes)} DynamicVisual mesh sections...")
    
    total_connectors = 0
    
    for i, dyn_data in enumerate(dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
        
        vertices = dyn_data['vertices']
        faces = np.array(dyn_data['faces'])
        vertex_bones = dyn_data.get('vertex_bones', [])
        
        print(f"  DynamicVisual mesh {i}: {len(vertices)} vertices, {len(faces)} faces")
        
        # CRITICAL: Group vertices by bone to create separate meshes for skeletal animation
        bone_vertex_groups = group_dynamic_visual_by_bone(dyn_data)
        print(f"    Split into {len(bone_vertex_groups)} bone groups: {list(bone_vertex_groups.keys())}")
        
        # Create separate mesh for each bone group
        for bone_idx, (bone_name, bone_group) in enumerate(bone_vertex_groups.items()):
            bone_mesh = create_bone_dynamic_visual_mesh(
                bone_name, bone_group, world_transforms, 
                all_mesh_vertices, i, bone_idx
            )
            
            if bone_mesh is None:
                continue
            
            # Determine material for this connector
            connector_material = determine_dynamic_visual_material(dyn_data, geometry_to_mesh_map, all_materials, total_connectors)
            
            # Create PBR material
            material = trimesh.visual.material.PBRMaterial()
            material.name = f"dynamic_connector_{total_connectors}_{bone_name}_material"
            material.baseColorFactor = connector_material['color']
            
            # Apply material to mesh
            try:
                bone_mesh.visual = trimesh.visual.TextureVisuals(material=material)
                print(f"  Applied {connector_material['type']} to DynamicVisual connector {total_connectors} ({bone_name})")
            except Exception:
                # Fallback to face colors
                bone_mesh.visual.face_colors = connector_material['color']
                print(f"  Applied {connector_material['type']} to DynamicVisual connector {total_connectors} ({bone_name}) (fallback)")
            
            # Add to scene with bone-specific naming
            connector_name = f"dynamic_connector_{total_connectors}_{bone_name}"
            scene.add_geometry(bone_mesh, node_name=connector_name)
            print(f"  Added DynamicVisual connector mesh {total_connectors} for bone {bone_name} with {len(bone_group['vertices'])} vertices")
            
            total_connectors += 1
    
    return total_connectors
