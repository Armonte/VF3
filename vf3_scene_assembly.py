"""
VF3 Scene Assembly
Handles scene graph creation, bone hierarchy setup, and mesh attachment.
"""

import os
import numpy as np
import trimesh
from typing import Dict, List, Any, Optional
from vf3_loader import build_world_transforms
from vf3_materials import apply_materials_to_mesh


def create_bone_hierarchy(bones: Dict, scene: trimesh.Scene) -> Dict[str, Any]:
    """
    Create proper bone hierarchy with local transforms and parent-child relationships.
    Returns a dictionary of scene graph nodes.
    """
    scene_graph_nodes = {}
    
    # First pass: Create all bone nodes with LOCAL transforms
    for bone_name, bone in bones.items():
        local_tf = np.eye(4)
        local_tf[:3, 3] = np.array(bone.translation, dtype=float)
        scene_graph_nodes[bone_name] = scene.graph.update(frame_to=bone_name, matrix=local_tf)
        print(f"Created bone node '{bone_name}' with local transform {bone.translation}")
    
    # Second pass: Set up parent-child relationships
    for bone_name, bone in bones.items():
        if bone.parent and bone.parent in scene_graph_nodes:
            # Set parent relationship in scene graph
            scene.graph.update(frame_from=bone_name, frame_to=bone.parent)
            print(f"Set bone '{bone_name}' as child of '{bone.parent}'")
        elif bone.parent:
            print(f"WARNING: Parent bone '{bone.parent}' not found for bone '{bone_name}'")
    
    return scene_graph_nodes


def create_child_attachment_nodes(attachments: List, bones: Dict, scene: trimesh.Scene, scene_graph_nodes: Dict) -> None:
    """Create child attachment nodes (like skirt_f, skirt_r) with their local offsets."""
    # Third pass: Add child attachment nodes with their local offsets
    for att in attachments:
        if att.child_name and att.parent_bone and att.child_offset is not None:
            # Create child node with local offset
            child_tf = np.eye(4)
            child_tf[:3, 3] = np.array(att.child_offset, dtype=float)
            scene_graph_nodes[att.child_name] = scene.graph.update(frame_to=att.child_name, matrix=child_tf)
            
            # Set parent relationship
            if att.parent_bone in scene_graph_nodes:
                scene.graph.update(frame_from=att.child_name, frame_to=att.parent_bone)
                print(f"Created child node '{att.child_name}' under parent '{att.parent_bone}' with offset {att.child_offset}")
            else:
                print(f"WARNING: Parent bone '{att.parent_bone}' not found for child node '{att.child_name}'")


def attach_mesh_to_scene(mesh_data: Dict, attachment, mesh_path: str, bones: Dict, attachments: List,
                        scene: trimesh.Scene, scene_graph_nodes: Dict, merge_female_body: bool,
                        female_body_meshes: List, geometry_to_attachment_map: Dict, 
                        prefix_counts: Dict[str, int]) -> None:
    """Attach a mesh to the scene with proper world transform and bone hierarchy."""
    name = attachment.resource_id.replace('.', '_')
    
    # Count by resource prefix (e.g., 'female', 'ciel')
    if '.' in attachment.resource_id:
        pref = attachment.resource_id.split('.', 1)[0]
        prefix_counts[pref] = prefix_counts.get(pref, 0) + 1

    # HYBRID APPROACH: Use world transforms for mesh positioning, keep bone hierarchy for structure
    # Get the world transform for this mesh's bone
    world_transforms = build_world_transforms(bones, attachments)
    if attachment.attach_bone in world_transforms:
        world_pos = world_transforms[attachment.attach_bone]
        T = np.eye(4)
        T[:3, 3] = np.array(world_pos, dtype=float)
        print(f"    DEBUG: Applying world transform to mesh {name} at bone {attachment.attach_bone}: {world_pos}")
    else:
        T = np.eye(4)
        print(f"    DEBUG: No world transform found for bone {attachment.attach_bone}, using identity")
    
    # Check if this mesh was split into multiple parts
    if mesh_data.get('is_split'):
        # Handle split meshes
        split_meshes = mesh_data['split_meshes']
        for split_data in split_meshes:
            split_mesh = split_data['mesh']
            
            # Apply materials to this split mesh
            if split_data['materials'] or split_data['textures']:
                base_path = os.path.dirname(mesh_path)
                split_mesh = apply_materials_to_mesh(split_mesh, split_data['materials'], split_data['textures'], base_path)
            
            # Apply world transform to position mesh correctly in world space
            split_mesh = split_mesh.copy()
            split_mesh.apply_transform(T)
            
            # Add to scene with proper parent bone relationship
            split_name = f"{name}_mat{split_data['material_index']}"
            if merge_female_body and attachment.resource_id.startswith('female.'):
                female_body_meshes.append(split_mesh)
                print(f"Collected female body part {split_name} for merging")
            else:
                scene.add_geometry(split_mesh, node_name=split_name)
                node_name = attachment.child_name if attachment.child_name else attachment.attach_bone
                if node_name in scene_graph_nodes:
                    scene.graph.update(frame_from=split_name, frame_to=node_name)
                geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = attachment.resource_id
                print(f"Added split mesh {split_name} to scene under parent bone {node_name}")
    else:
        # Handle single mesh with world transform positioning
        mesh = mesh_data['mesh']
        mesh = mesh.copy()
        # Apply world transform to position mesh correctly in world space
        mesh.apply_transform(T)

        # If merging female body parts, collect them instead of adding individually
        if merge_female_body and attachment.resource_id.startswith('female.'):
            female_body_meshes.append(mesh)
            print(f"Collected female body part {name} for merging")
        else:
            scene.add_geometry(mesh, node_name=name)
            node_name = attachment.child_name if attachment.child_name else attachment.attach_bone
            if node_name in scene_graph_nodes:
                scene.graph.update(frame_from=name, frame_to=node_name)
            geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = attachment.resource_id
            print(f"Added mesh {name} to scene under parent bone {node_name}")


def merge_female_body_parts(female_body_meshes: List, scene: trimesh.Scene, 
                           scene_graph_nodes: Dict, geometry_to_attachment_map: Dict) -> None:
    """Merge collected female body parts into a single mesh."""
    if female_body_meshes:
        print(f"\nMerging {len(female_body_meshes)} female body parts...")
        try:
            # Combine all female body meshes
            combined_mesh = trimesh.util.concatenate(female_body_meshes)
            scene.add_geometry(combined_mesh, node_name="female_body_combined")
            
            # Parent to body bone
            if 'body' in scene_graph_nodes:
                scene.graph.update(frame_from="female_body_combined", frame_to='body')
            
            geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = "female.body_combined"
            print(f"Created combined female body mesh with {len(combined_mesh.vertices)} vertices")
        except Exception as e:
            print(f"Failed to merge female body parts: {e}")
            # Add them individually as fallback
            for i, mesh in enumerate(female_body_meshes):
                scene.add_geometry(mesh, node_name=f"female_body_part_{i}")
                if 'body' in scene_graph_nodes:
                    scene.graph.update(frame_from=f"female_body_part_{i}", frame_to='body')
