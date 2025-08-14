"""
VF3 Scene Assembly Module
Complete scene graph creation, bone hierarchy setup, and mesh attachment.
Extracted from export_ciel_to_gltf.py lines 1422-2092
"""

import os
import numpy as np
import trimesh
from typing import Dict, List, Any, Optional

from vf3_loader import build_world_transforms
from vf3_materials import apply_materials_to_mesh, split_mesh_by_materials, merge_body_meshes, determine_dynamic_visual_material
from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_loader import find_mesh_file


def create_bone_hierarchy(bones: Dict, scene: trimesh.Scene) -> Dict[str, Any]:
    """Create proper bone hierarchy with LOCAL transforms and parent relationships."""
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
            scene.graph.update(frame_from=bone_name, frame_to=bone.parent)
            print(f"Set bone '{bone_name}' as child of '{bone.parent}'")
        elif bone.parent:
            print(f"WARNING: Parent bone '{bone.parent}' not found for bone '{bone_name}'")
    
    return scene_graph_nodes


def create_child_attachment_nodes(attachments: List, scene_graph_nodes: Dict, scene: trimesh.Scene):
    """Create child attachment nodes (like skirt_f, skirt_r) with their local offsets."""
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


def is_core_body_part(resource_id: str) -> bool:
    """Check if a resource represents a core body part vs an accessory"""
    CORE_BODY_PARTS = {
        'body', 'head', 'l_breast', 'r_breast', 'l_arm1', 'l_arm2', 'l_hand', 
        'r_arm1', 'r_arm2', 'r_hand', 'waist', 'l_leg1', 'l_leg2', 'l_foot', 
        'r_leg1', 'r_leg2', 'r_foot'
    }
    
    if resource_id.startswith('female.'):
        part_name = resource_id.split('.', 1)[1]
        return part_name in CORE_BODY_PARTS
    return False