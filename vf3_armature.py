"""
VF3 glTF Armature Creation Module
Create proper glTF armatures/skins with real bones instead of scene nodes.
"""

import numpy as np
import trimesh
from typing import Dict, List, Any, Tuple, Optional

def create_gltf_armature(bones: Dict, scene: trimesh.Scene, world_transforms: Dict) -> Tuple[Any, Dict[str, int], np.ndarray]:
    """Create a proper glTF armature with real bones and skin binding.
    
    Based on https://lisyarus.github.io/blog/posts/gltf-animation.html
    
    Returns:
        - armature_node: The root armature node
        - joint_indices: Mapping from bone names to joint indices  
        - inverse_bind_matrices: Array of inverse bind matrices for skinning
    """
    
    print("? Creating glTF armature with proper skeletal animation...")
    
    # Step 1: Build bone hierarchy order (parents before children)
    bone_order = _get_bone_hierarchy_order(bones)
    joint_indices = {bone_name: i for i, bone_name in enumerate(bone_order)}
    
    # Step 2: Create inverse bind matrices 
    # These transform from mesh space to bone space
    inverse_bind_matrices = np.zeros((len(bone_order), 4, 4), dtype=np.float32)
    
    for i, bone_name in enumerate(bone_order):
        if bone_name in world_transforms:
            world_pos = world_transforms[bone_name]
            
            # Create bind pose matrix (world transform of bone in bind pose)
            bind_matrix = np.eye(4, dtype=np.float32)
            bind_matrix[:3, 3] = np.array(world_pos, dtype=np.float32)
            
            # Inverse bind matrix transforms from mesh space to bone space
            inverse_bind_matrices[i] = np.linalg.inv(bind_matrix)
            
            print(f"  Joint {i}: '{bone_name}' at {world_pos}, inverse bind computed")
        else:
            # Identity for bones without world transforms
            inverse_bind_matrices[i] = np.eye(4, dtype=np.float32)
            print(f"  Joint {i}: '{bone_name}' at origin, identity inverse bind")
    
    # Step 3: Create joint nodes with LOCAL transforms (not world)
    joint_nodes = []
    for i, bone_name in enumerate(bone_order):
        bone = bones[bone_name]
        
        # Use LOCAL transform relative to parent
        local_matrix = np.eye(4, dtype=np.float32)
        local_matrix[:3, 3] = np.array(bone.translation, dtype=np.float32)
        
        # Create joint node with local transform
        joint_node = scene.graph.update(
            frame_to=f"joint_{bone_name}",
            matrix=local_matrix
        )
        joint_nodes.append(joint_node)
        
        print(f"  Created joint {i}: '{bone_name}' with local transform {bone.translation}")
    
    # Step 4: Set up parent-child relationships for joints
    for i, bone_name in enumerate(bone_order):
        bone = bones[bone_name]
        if bone.parent and bone.parent in joint_indices:
            parent_joint = f"joint_{bone.parent}"
            child_joint = f"joint_{bone_name}"
            scene.graph.update(frame_from=child_joint, frame_to=parent_joint)
            print(f"  Parented {child_joint} to {parent_joint}")
    
    # Step 5: Create armature root and parent root joints to it
    armature_node = scene.graph.update(frame_to="Armature", matrix=np.eye(4))
    
    # Find root bones (no parent) and parent them to armature
    for bone_name in bone_order:
        bone = bones[bone_name]
        if not bone.parent or bone.parent not in bones:
            scene.graph.update(frame_from=f"joint_{bone_name}", frame_to="Armature")
            print(f"  Parented root joint_{bone_name} to Armature")
    
    print(f"? Created proper glTF armature with {len(joint_nodes)} joints and inverse bind matrices")
    return armature_node, joint_indices, inverse_bind_matrices


def create_mesh_skin(mesh: trimesh.Trimesh, bone_name: str, joint_indices: Dict[str, int], 
                     inverse_bind_matrices: np.ndarray) -> trimesh.Trimesh:
    """Create a skinned mesh bound to a specific bone using proper glTF skinning.
    
    Based on glTF specification for skeletal animation.
    
    Args:
        mesh: The mesh to skin
        bone_name: Name of the bone to bind to
        joint_indices: Mapping from bone names to joint indices
        inverse_bind_matrices: Inverse bind matrices for the skin
        
    Returns:
        Skinned mesh with proper glTF vertex attributes
    """
    
    if bone_name not in joint_indices:
        print(f"  WARNING: Bone '{bone_name}' not found in joint indices, skipping skinning")
        return mesh
    
    joint_idx = joint_indices[bone_name]
    vertex_count = len(mesh.vertices)
    
    # Create joint indices for each vertex (glTF JOINTS_0 attribute)
    # Each vertex can be influenced by up to 4 joints
    joint_ids = np.zeros((vertex_count, 4), dtype=np.uint16)
    joint_ids[:, 0] = joint_idx  # Bind all vertices to this joint
    # Other indices remain 0 (will be ignored due to zero weights)
    
    # Create vertex weights (glTF WEIGHTS_0 attribute)  
    # Each vertex has 4 weights corresponding to the 4 joint indices
    weights = np.zeros((vertex_count, 4), dtype=np.float32)
    weights[:, 0] = 1.0  # Full weight to the first (and only) joint
    # Other weights remain 0
    
    # Store glTF skinning attributes
    if not hasattr(mesh, 'vertex_attributes'):
        mesh.vertex_attributes = {}
    
    mesh.vertex_attributes['JOINTS_0'] = joint_ids
    mesh.vertex_attributes['WEIGHTS_0'] = weights
    
    # Store reference to the skin data (trimesh will use this for glTF export)
    if not hasattr(mesh, 'metadata'):
        mesh.metadata = {}
    
    mesh.metadata['skin_joints'] = list(joint_indices.keys())
    mesh.metadata['skin_joint_matrices'] = inverse_bind_matrices
    
    print(f"  ? Skinned mesh to joint {joint_idx} ('{bone_name}') with {vertex_count} vertices")
    return mesh


def _get_bone_hierarchy_order(bones: Dict) -> List[str]:
    """Get bones in hierarchical order (parents before children)."""
    
    # Find root bones (no parent)
    roots = [name for name, bone in bones.items() if not bone.parent or bone.parent not in bones]
    
    # Build hierarchy using depth-first traversal
    ordered = []
    visited = set()
    
    def visit_bone(bone_name: str):
        if bone_name in visited or bone_name not in bones:
            return
        
        visited.add(bone_name)
        ordered.append(bone_name)
        
        # Visit children
        children = [name for name, bone in bones.items() if bone.parent == bone_name]
        for child in sorted(children):  # Sort for consistent ordering
            visit_bone(child)
    
    # Visit all roots
    for root in sorted(roots):
        visit_bone(root)
    
    print(f"? Bone hierarchy order: {' -> '.join(ordered)}")
    return ordered


def create_inverse_bind_matrices(bones: Dict, world_transforms: Dict, joint_indices: Dict[str, int]) -> np.ndarray:
    """Create inverse bind matrices for the skin.
    
    Returns:
        Array of 4x4 inverse bind matrices, one per joint
    """
    
    num_joints = len(joint_indices)
    inverse_bind_matrices = np.zeros((num_joints, 4, 4), dtype=np.float32)
    
    for bone_name, joint_idx in joint_indices.items():
        if bone_name in world_transforms:
            world_pos = world_transforms[bone_name]
            
            # Create world transform matrix
            world_matrix = np.eye(4, dtype=np.float32)
            world_matrix[:3, 3] = np.array(world_pos, dtype=np.float32)
            
            # Inverse bind matrix is the inverse of the world transform
            inverse_bind_matrices[joint_idx] = np.linalg.inv(world_matrix)
        else:
            # Identity matrix for bones without world transforms
            inverse_bind_matrices[joint_idx] = np.eye(4, dtype=np.float32)
    
    print(f"? Created {num_joints} inverse bind matrices")
    return inverse_bind_matrices
