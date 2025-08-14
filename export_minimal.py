#!/usr/bin/env python3
"""
VF3 Character Exporter - Minimal Working Version
Focus: Get basic export working, then add DynamicVisual bone splitting
"""

import argparse
import os
import sys
import trimesh
import numpy as np
from typing import Dict, List, Any

from vf3_loader import (
    read_descriptor,
    parse_frame_bones,
    collect_active_attachments,
    build_world_transforms,
    find_mesh_file
)
from vf3_mesh_loader import load_mesh_with_full_materials


def process_dynamic_visual_with_bone_splitting(dynamic_meshes: List[Dict], world_transforms: Dict, 
                                             all_mesh_vertices: np.ndarray, all_materials: Dict, 
                                             geometry_to_mesh_map: Dict, scene: trimesh.Scene) -> int:
    """
    CRITICAL: Process DynamicVisual meshes with bone splitting for skeletal animation.
    This is the clean implementation of the bone splitting fix.
    """
    if not dynamic_meshes:
        return 0
    
    total_connectors = 0
    
    for i, dyn_data in enumerate(dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
        
        vertices = dyn_data['vertices']  # List of (pos1, pos2) tuples
        faces = np.array(dyn_data['faces'])
        vertex_bones = dyn_data.get('vertex_bones', [])
        
        print(f"  ? DynamicVisual mesh {i}: {len(vertices)} vertices, {len(faces)} faces")
        
        # CRITICAL: Group vertices by bone to create separate meshes for skeletal animation
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
        
        print(f"    ? SPLIT: {len(bone_vertex_groups)} bone groups: {list(bone_vertex_groups.keys())}")
        
        # Create separate mesh for each bone group
        for bone_name, bone_group in bone_vertex_groups.items():
            bone_vertices = bone_group['vertices']
            original_indices = bone_group['vertex_indices']
            
            # Create face mapping for this bone's vertices
            index_mapping = {orig_idx: new_idx for new_idx, orig_idx in enumerate(original_indices)}
            bone_faces = []
            for face in faces:
                # Count how many vertices in this face belong to this bone
                bone_vertex_count = sum(1 for v_idx in face if v_idx in index_mapping)
                
                # Assign face to this bone if it has majority (>=2) or all (3) vertices
                if bone_vertex_count >= 2:  # Majority rule
                    # For vertices not in this bone, we'll need to add them temporarily
                    face_vertices_needed = []
                    new_face = []
                    for v_idx in face:
                        if v_idx in index_mapping:
                            new_face.append(index_mapping[v_idx])
                        else:
                            # Add vertex from other bone to this bone's vertex list
                            other_vertex = vertices[v_idx]
                            bone_vertices.append(other_vertex)
                            new_idx = len(bone_vertices) - 1
                            new_face.append(new_idx)
                            face_vertices_needed.append((v_idx, new_idx))
                    
                    bone_faces.append(new_face)
            
            if len(bone_faces) == 0:
                print(f"      ??  No faces for bone {bone_name}, skipping")
                continue
            
            try:
                # Process vertices for this bone - SIMPLIFIED to avoid double transforms
                snapped_vertices = []
                
                for vertex_tuple in bone_vertices:
                    pos1, pos2 = vertex_tuple
                    
                    # FIXED: Use pos2 directly without adding bone position (avoid double transform)
                    candidate_pos = [pos2[0], pos2[1], pos2[2]]
                    
                    # Simple vertex snapping to nearest existing mesh vertex
                    if len(all_mesh_vertices) > 0:
                        distances = np.linalg.norm(all_mesh_vertices - candidate_pos, axis=1)
                        min_distance = np.min(distances)
                        if min_distance <= 0.5:  # Reduced snap threshold
                            closest_idx = np.argmin(distances)
                            snapped_pos = all_mesh_vertices[closest_idx].tolist()
                        else:
                            snapped_pos = candidate_pos
                    else:
                        snapped_pos = candidate_pos
                    
                    snapped_vertices.append(snapped_pos)
                
                # Create mesh for this bone - NO world transform applied here
                bone_mesh = trimesh.Trimesh(vertices=np.array(snapped_vertices), faces=np.array(bone_faces))
                
                # Simple material assignment (skin tone for now)
                bone_mesh.visual.face_colors = [0.95, 0.76, 0.65, 1.0]  # Skin tone
                
                # Add to scene with bone-specific naming
                connector_name = f"dynamic_connector_{total_connectors}_{bone_name}"
                scene.add_geometry(bone_mesh, node_name=connector_name)
                print(f"      ? Added connector {total_connectors} for bone {bone_name}: {len(snapped_vertices)} vertices, {len(bone_faces)} faces")
                
                total_connectors += 1
                
            except Exception as e:
                print(f"      ? Failed to create mesh for bone {bone_name}: {e}")
    
    print(f"? BONE SPLITTING SUCCESS: Created {total_connectors} bone-specific connectors (vs {len(dynamic_meshes)} original cross-bone meshes)")
    return total_connectors


def create_basic_scene(descriptor, bones: Dict) -> Dict:
    """Create a basic working scene without DynamicVisual for now."""
    print("Creating basic scene...")
    
    # Get attachments using the working function
    attachments, dynamic_meshes = collect_active_attachments(descriptor)
    print(f"Found {len(attachments)} attachments, {len(dynamic_meshes)} dynamic meshes")
    
    # Create scene
    scene = trimesh.Scene()
    
    # Create simple bone hierarchy (local transforms)
    for bone_name, bone in bones.items():
        local_tf = np.eye(4)
        local_tf[:3, 3] = np.array(bone.translation, dtype=float)
        scene.graph.update(frame_to=bone_name, matrix=local_tf)
        print(f"Created bone '{bone_name}' at {bone.translation}")
    
    # Set up parent-child relationships
    for bone_name, bone in bones.items():
        if bone.parent and bone.parent in bones:
            scene.graph.update(frame_from=bone_name, frame_to=bone.parent)
            print(f"Set '{bone_name}' as child of '{bone.parent}'")
    
    # Load and attach meshes with world transforms
    world_transforms = build_world_transforms(bones, attachments)
    all_materials = {}
    
    for att in attachments:
        mesh_path = find_mesh_file(att.resource_id)
        if not mesh_path or not os.path.exists(mesh_path):
            continue
            
        try:
            # Load mesh using our complete modular loader (supports .X files with materials)
            mesh_data = load_mesh_with_full_materials(mesh_path)
            if mesh_data['mesh'] is None:
                continue
            if mesh_data and 'mesh' in mesh_data:
                mesh = mesh_data['mesh'].copy()
                
                # Apply world transform
                if att.attach_bone in world_transforms:
                    world_pos = world_transforms[att.attach_bone]
                    T = np.eye(4)
                    T[:3, 3] = np.array(world_pos, dtype=float)
                    mesh.apply_transform(T)
                    print(f"Attached {att.resource_id} to {att.attach_bone} at {world_pos}")
                
                # Add to scene
                name = att.resource_id.replace('.', '_')
                scene.add_geometry(mesh, node_name=name)
                
                # Store materials for later
                all_materials[att.resource_id] = mesh_data.get('materials', [])
                
        except Exception as e:
            print(f"Failed to load {mesh_path}: {e}")
    
    # NOW ADD: DynamicVisual processing with bone splitting
    print(f"\n? Processing {len(dynamic_meshes)} DynamicVisual meshes with BONE SPLITTING...")
    
    # Collect all mesh vertices for snapping
    all_mesh_vertices = []
    for geom_name, geom in scene.geometry.items():
        if hasattr(geom, 'vertices'):
            all_mesh_vertices.extend(geom.vertices.tolist())
    all_mesh_vertices = np.array(all_mesh_vertices)
    print(f"Collected {len(all_mesh_vertices)} vertices for DynamicVisual snapping")
    
    connector_count = process_dynamic_visual_with_bone_splitting(
        dynamic_meshes, world_transforms, all_mesh_vertices, 
        all_materials, {}, scene
    )
    
    return {
        'scene': scene,
        'materials': all_materials,
        'textures': set(),
        'dynamic_meshes': dynamic_meshes,
        'world_transforms': world_transforms,
        'connector_count': connector_count
    }


def main():
    parser = argparse.ArgumentParser(description='VF3 Minimal Exporter')
    parser.add_argument('--desc', required=True, help='Descriptor file')
    parser.add_argument('--out', required=True, help='Output file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.desc):
        print(f"Error: File not found: {args.desc}")
        sys.exit(1)
    
    print("=== VF3 Minimal Exporter ===")
    print(f"Reading: {args.desc}")
    
    try:
        # Load descriptor and bones
        descriptor = read_descriptor(args.desc)
        bones = parse_frame_bones(descriptor)
        print(f"Found {len(bones)} bones")
        
        # Create basic scene
        scene_data = create_basic_scene(descriptor, bones)
        scene = scene_data['scene']
        
        print(f"Scene created with {len(scene.geometry)} geometries")
        
        # Export
        scene.export(args.out)
        print(f"Exported: {args.out}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
