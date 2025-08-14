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


def group_vertices_by_anatomical_region(vertices: List[Tuple], vertex_bones: List[str], allow_torso: bool = True) -> Dict[str, Dict]:
    """
    Group vertices by anatomical regions to create separate connectors.
    CRITICAL: Each bone maps to exactly ONE region to avoid duplicates.
    """
# Debug output removed - fix confirmed working
    # Define bone-to-region mapping (each bone appears exactly once)
    # Based on user feedback: waist is handled by regular mesh, l_leg1/r_leg1 are HIPS not knees, merge breast connectors
    bone_to_region = {
        # Merged breast connector (both sides go to same region)
        'l_breast': 'breast_connection',
        'r_breast': 'breast_connection',
        # Arm joint connectors - CORRECTED
        'l_arm1': 'left_shoulder',   # l_arm1 is shoulder/upper arm 
        'r_arm1': 'right_shoulder',  # r_arm1 is shoulder/upper arm
        # Elbow should only be created when BOTH l_arm1 AND l_arm2 are present
        # 'l_arm2': handled by special logic below
        # 'r_arm2': handled by special logic below
        'l_hand': 'left_wrist',      # Hand connects to wrist
        'r_hand': 'right_wrist',     # Hand connects to wrist
        # Leg joint connectors - CORRECTED ANATOMY
        'l_leg1': 'left_hip',        # l_leg1 is thigh = HIP connector (waist to thigh)
        'r_leg1': 'right_hip',       # r_leg1 is thigh = HIP connector (waist to thigh)
        'l_leg2': 'left_knee',       # l_leg2 is shin = KNEE connector (thigh to shin) 
        'r_leg2': 'right_knee',      # r_leg2 is shin = KNEE connector (thigh to shin)
        'l_foot': 'left_ankle',      # Foot connects to ankle
        'r_foot': 'right_ankle',     # Foot connects to ankle
        # Core body - SPECIAL LOGIC: only create torso if waist is nearby
        # 'body': handled by special logic below
        # 'waist': REMOVED - waist is handled by waist_female.waist mesh
    }
    
    # Group vertices by region using strict mapping
    regions = {}
    
    # Check if this mesh has both body and waist bones (indicates midriff connection)
    unique_bones = set(vertex_bones)
    has_body = 'body' in unique_bones
    has_waist = 'waist' in unique_bones
    has_arm1 = 'l_arm1' in unique_bones or 'r_arm1' in unique_bones
    has_arm2 = 'l_arm2' in unique_bones or 'r_arm2' in unique_bones
    
    # Only create torso connector if allowed and has body+waist
    create_torso_connector = allow_torso and has_body and has_waist
    
# Debug output removed - bilateral merging fix confirmed working
    
    # Check if this is a bilateral merge (has both left and right hand bones)
    has_both_hands = 'l_hand' in unique_bones and 'r_hand' in unique_bones
    has_both_arm2 = 'l_arm2' in unique_bones and 'r_arm2' in unique_bones
    
    for i, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
        # Skip waist bone - it's handled by regular waist mesh
        if bone_name == 'waist':
            continue
            
        # Special handling for body bone
        if bone_name == 'body':
            if create_torso_connector:
                assigned_region = 'torso'  # This is the midriff connection area
            else:
                continue  # Skip body vertices that aren't part of the midriff connection
        # Special handling for l_arm2/r_arm2 - only create elbow if both arm bones present
        elif bone_name == 'l_arm2':
            if 'l_arm1' in unique_bones:
                assigned_region = 'left_elbow'  # True elbow joint (l_arm1 + l_arm2)
            elif has_both_hands and has_both_arm2:
                assigned_region = 'left_forearm'  # Bilateral merge: create both forearms
            else:
                assigned_region = 'left_forearm'  # Just forearm, not elbow joint
        elif bone_name == 'r_arm2':
            if 'r_arm1' in unique_bones:
                assigned_region = 'right_elbow'  # True elbow joint (r_arm1 + r_arm2)
            elif has_both_hands and has_both_arm2:
                assigned_region = 'right_forearm'  # Bilateral merge: create both forearms
            else:
                assigned_region = 'right_forearm'  # Just forearm, not elbow joint
        # Special handling for hands in bilateral merges
        elif bone_name == 'l_hand':
            if has_both_hands:
                assigned_region = 'left_wrist'  # Bilateral merge: separate left wrist
            else:
                assigned_region = bone_to_region.get(bone_name, f"misc_{bone_name}")
        elif bone_name == 'r_hand':
            if has_both_hands:
                assigned_region = 'right_wrist'  # Bilateral merge: separate right wrist
            else:
                assigned_region = bone_to_region.get(bone_name, f"misc_{bone_name}")
        else:
            # Get region for this bone (no overlaps possible)
            assigned_region = bone_to_region.get(bone_name, f"misc_{bone_name}")
        
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
    
    print(f"\n🔧 DEBUG: Processing {len(dynamic_meshes)} DynamicVisual mesh sections...")
    print(f"🔧 DEBUG: This is from the UPDATED vf3_dynamic_visual.py file!")
    
    total_connectors = 0
    torso_connector_created = False  # Simple flag to prevent multiple torso connectors
    
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
        allow_torso = not torso_connector_created  # Only create one torso connector
        bone_groups = group_vertices_by_anatomical_region(vertices, vertex_bones, allow_torso)
        print(f"    Split into {len(bone_groups)} anatomical regions: {list(bone_groups.keys())}")
        
        # Create separate connector for each anatomical region
        for region_name, region_data in bone_groups.items():
            region_vertices = region_data['vertices']
            region_vertex_bones = region_data['vertex_bones'] 
            region_indices = region_data['indices']
            
            print(f"    Processing region '{region_name}' with {len(region_vertices)} vertices from bones: {set(region_vertex_bones)}")
            if region_name == 'torso':
                print(f"        TORSO DEBUG: Starting with {len(region_vertices)} vertices")
                print(f"        TORSO DEBUG: vertex_mapping has {len(vertex_mapping)} vertices: {list(vertex_mapping.keys())[:10]}...")
            initial_vertex_count = len(region_vertices)
            
            # Filter faces using MAJORITY RULE (>=2 vertices belong to this region)
            region_faces = []
            vertex_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(region_indices)}
            
            if region_name == 'torso':
                print(f"        ⚠️  TORSO FACE PROCESSING: Starting with {len(region_vertices)} vertices, {len(faces)} faces to process")
            
            face_count = 0
            for face in faces:
                # Count how many vertices in this face belong to this region
                vertices_in_region = [v_idx in vertex_mapping for v_idx in face]
                vertices_in_region_count = sum(vertices_in_region)
                
                if region_name == 'torso' and face_count < 5:  # Debug first 5 faces for torso
                    face_bones = [vertex_bones[v_idx] for v_idx in face if v_idx < len(vertex_bones)]
                    print(f"        TORSO FACE {face_count}: vertices {face} -> {vertices_in_region_count}/{len(face)} in region, bones: {face_bones}")
                face_count += 1
                
                # Special handling for torso region - STRICT ISOLATION like breasts  
                if region_name == 'torso':
                    # For torso, NEVER expand beyond original body vertices - be as strict as breast connectors
                    if vertices_in_region_count == len(face):
                        # ALL vertices in this face belong to torso region - safe to include
                        new_face = [vertex_mapping[v_idx] for v_idx in face]
                        region_faces.append(new_face)
                    else:
                        # Face has vertices from other regions - skip to prevent contamination
                        face_bones = [vertex_bones[v_idx] for v_idx in face if v_idx < len(vertex_bones)]
                        print(f"        TORSO: Skipping cross-region face with bones: {set(face_bones)}")
                        continue
                elif region_name == 'breast_connection':
                    # For breast connections, STRICT ISOLATION to prevent merging issues
                    if vertices_in_region_count == len(face):
                        # ALL vertices in this face belong to breast region - safe to include  
                        new_face = [vertex_mapping[v_idx] for v_idx in face]
                        region_faces.append(new_face)
                    else:
                        # Face has vertices from other regions - skip to prevent breast separation
                        face_bones = [vertex_bones[v_idx] for v_idx in face if v_idx < len(vertex_bones)]
                        print(f"        BREAST: Skipping cross-region face with bones: {set(face_bones)}")
                        continue
                else:
                    # For other regions, use majority rule (>=2 vertices belong to this region)
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
                
            final_vertex_count = len(region_vertices)
            added_vertices = final_vertex_count - initial_vertex_count
            print(f"      Region {region_name}: {final_vertex_count} vertices ({initial_vertex_count} initial + {added_vertices} added), {len(region_faces)} faces")
            
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
                
                connector_mesh = trimesh.Trimesh(vertices=np.array(snapped_vertices), faces=region_faces_array, process=True)
                
                # Ensure smooth vertex normals for Gouraud shading
                _ = connector_mesh.vertex_normals  # Force computation of smooth normals
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
                
                # Set flag if this was a torso connector
                if region_name == 'torso':
                    torso_connector_created = True
                
            except Exception as e:
                print(f"      ❌ Failed to create {region_name} connector: {e}")
                continue
    
    return total_connectors
