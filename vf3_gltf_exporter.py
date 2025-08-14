"""
VF3 Direct glTF Exporter
Export VF3 characters to glTF with proper skeletal animation using pygltflib.
This bypasses trimesh which silently drops bone data.
"""

import numpy as np
import struct
from typing import Dict, List, Tuple, Any
from pygltflib import GLTF2, Scene, Node, Mesh, Primitive, Accessor, BufferView, Buffer
from pygltflib import Material, Skin
from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER
from pygltflib import FLOAT, UNSIGNED_SHORT, UNSIGNED_INT
from pygltflib import TRIANGLES

def create_gltf_with_skeleton(bones: Dict, attachments: List, world_transforms: Dict, 
                             mesh_data: Dict[str, Any]) -> GLTF2:
    """Create a complete glTF file with proper skeletal animation.
    
    Args:
        bones: Bone hierarchy from .TXT file
        attachments: Mesh attachments to bones
        world_transforms: World positions of bones
        mesh_data: Dictionary mapping attachment resource_id to mesh data
        
    Returns:
        Complete GLTF2 object ready for export
    """
    
    print("? Creating glTF with proper skeletal animation using pygltflib...")
    
    gltf = GLTF2()
    
    # Step 1: Create buffers for all data
    all_vertex_data = bytearray()
    all_index_data = bytearray()
    
    # Step 2: Build bone hierarchy
    bone_order = _get_bone_hierarchy_order(bones)
    joint_indices = {bone_name: i for i, bone_name in enumerate(bone_order)}
    
    print(f"? Creating {len(bone_order)} joints in hierarchy order")
    
    # Step 3: Create nodes for joints
    joint_nodes = []
    for i, bone_name in enumerate(bone_order):
        bone = bones[bone_name]
        
        # Create node with LOCAL transform
        node = Node()
        node.name = f"joint_{bone_name}"
        
        # Set translation (local transform relative to parent)
        node.translation = list(bone.translation)
        
        # Set parent relationship
        if bone.parent and bone.parent in joint_indices:
            parent_idx = joint_indices[bone.parent]
            if not hasattr(joint_nodes[parent_idx], 'children'):
                joint_nodes[parent_idx].children = []
            joint_nodes[parent_idx].children.append(i)
        
        joint_nodes.append(node)
        print(f"  Joint {i}: {bone_name} at {bone.translation}")
    
    # Step 4: Create armature root node
    armature_node = Node()
    armature_node.name = "Armature"
    armature_node.translation = [0.0, 0.0, 0.0]
    armature_node.rotation = [0.0, 0.0, 0.0, 1.0]
    armature_node.scale = [1.0, 1.0, 1.0]
    
    # Parent root joints to armature
    armature_node.children = []
    for i, bone_name in enumerate(bone_order):
        bone = bones[bone_name]
        if not bone.parent or bone.parent not in bones:
            armature_node.children.append(len(joint_nodes) + i)  # Offset for armature
    
    # Step 5: Create inverse bind matrices
    inverse_bind_matrices = []
    for bone_name in bone_order:
        if bone_name in world_transforms:
            world_pos = world_transforms[bone_name]
            # Create bind pose matrix
            bind_matrix = np.eye(4, dtype=np.float32)
            bind_matrix[:3, 3] = np.array(world_pos, dtype=np.float32)
            # Inverse bind matrix
            inv_bind = np.linalg.inv(bind_matrix)
            inverse_bind_matrices.extend(inv_bind.flatten().tolist())
        else:
            # Identity matrix
            inverse_bind_matrices.extend(np.eye(4, dtype=np.float32).flatten().tolist())
    
    # Step 6: Create meshes with proper skinning
    mesh_nodes = []
    primitives = []
    
    vertex_offset = 0
    index_offset = 0
    
    for att in attachments:
        if att.resource_id not in mesh_data:
            continue
            
        mesh_info = mesh_data[att.resource_id]
        trimesh_mesh = mesh_info['mesh']
        
        if not trimesh_mesh:
            continue
        
        # Apply world transform to vertices
        vertices = trimesh_mesh.vertices.copy()
        if att.attach_bone in world_transforms:
            world_pos = world_transforms[att.attach_bone]
            vertices += np.array(world_pos)
        
        # Create vertex buffer data
        vertex_data = bytearray()
        
        # Positions (3 floats per vertex)
        for vertex in vertices:
            vertex_data.extend(struct.pack('<fff', *vertex))
        
        # Normals (3 floats per vertex, use face normals)
        normals = trimesh_mesh.vertex_normals
        for normal in normals:
            vertex_data.extend(struct.pack('<fff', *normal))
        
        # Joint indices and weights (4 shorts + 4 floats per vertex)
        joint_idx = joint_indices.get(att.attach_bone, 0)
        for _ in range(len(vertices)):
            # Joint indices (bind all vertices to this bone)
            vertex_data.extend(struct.pack('<HHHH', joint_idx, 0, 0, 0))
            # Weights (full weight to first joint)
            vertex_data.extend(struct.pack('<ffff', 1.0, 0.0, 0.0, 0.0))
        
        # Indices
        indices = trimesh_mesh.faces.flatten()
        index_data = bytearray()
        for idx in indices:
            index_data.extend(struct.pack('<H', idx + vertex_offset // (3*4 + 3*4 + 4*2 + 4*4)))
        
        # Create primitive
        primitive = Primitive()
        primitive.attributes = {
            'POSITION': len(gltf.accessors),
            'NORMAL': len(gltf.accessors) + 1,
            'JOINTS_0': len(gltf.accessors) + 2,
            'WEIGHTS_0': len(gltf.accessors) + 3,
        }
        primitive.indices = len(gltf.accessors) + 4
        primitive.mode = TRIANGLES
        
        # Create accessors for this mesh
        _create_accessors_for_mesh(gltf, len(vertices), len(indices), vertex_offset, index_offset)
        
        primitives.append(primitive)
        
        # Update offsets
        all_vertex_data.extend(vertex_data)
        all_index_data.extend(index_data)
        vertex_offset += len(vertex_data)
        index_offset += len(index_data)
        
        print(f"  Added mesh {att.resource_id} with {len(vertices)} vertices, bound to joint {joint_idx}")
    
    # Step 7: Create glTF structure
    # Buffer
    buffer = Buffer()
    buffer.byteLength = len(all_vertex_data) + len(all_index_data) + len(inverse_bind_matrices) * 4
    gltf.buffers.append(buffer)
    
    # BufferViews
    # Vertex data
    vertex_buffer_view = BufferView()
    vertex_buffer_view.buffer = 0
    vertex_buffer_view.byteOffset = 0
    vertex_buffer_view.byteLength = len(all_vertex_data)
    vertex_buffer_view.target = ARRAY_BUFFER
    gltf.bufferViews.append(vertex_buffer_view)
    
    # Index data
    index_buffer_view = BufferView()
    index_buffer_view.buffer = 0
    index_buffer_view.byteOffset = len(all_vertex_data)
    index_buffer_view.byteLength = len(all_index_data)
    index_buffer_view.target = ELEMENT_ARRAY_BUFFER
    gltf.bufferViews.append(index_buffer_view)
    
    # Inverse bind matrices
    ibm_buffer_view = BufferView()
    ibm_buffer_view.buffer = 0
    ibm_buffer_view.byteOffset = len(all_vertex_data) + len(all_index_data)
    ibm_buffer_view.byteLength = len(inverse_bind_matrices) * 4
    gltf.bufferViews.append(ibm_buffer_view)
    
    # Create mesh
    mesh = Mesh()
    mesh.name = "character_mesh"
    mesh.primitives = primitives
    gltf.meshes.append(mesh)
    
    # Create skin
    skin = Skin()
    skin.name = "character_skin"
    skin.joints = list(range(len(joint_nodes)))
    skin.inverseBindMatrices = len(gltf.accessors)
    gltf.skins.append(skin)
    
    # Create accessor for inverse bind matrices
    ibm_accessor = Accessor()
    ibm_accessor.bufferView = 2
    ibm_accessor.byteOffset = 0
    ibm_accessor.componentType = FLOAT
    ibm_accessor.count = len(joint_nodes)
    ibm_accessor.type = "MAT4"
    gltf.accessors.append(ibm_accessor)
    
    # Create character node (uses the mesh and skin)
    character_node = Node()
    character_node.name = "Character"
    character_node.mesh = 0
    character_node.skin = 0
    
    # Add all nodes to glTF
    gltf.nodes.extend(joint_nodes)
    gltf.nodes.append(armature_node)
    gltf.nodes.append(character_node)
    
    # Create scene
    scene = Scene()
    scene.name = "VF3_Character"
    scene.nodes = [len(gltf.nodes) - 2, len(gltf.nodes) - 1]  # Armature + Character
    gltf.scenes.append(scene)
    gltf.scene = 0
    
    # Set binary data
    all_data = all_vertex_data + all_index_data + bytearray(struct.pack(f'<{len(inverse_bind_matrices)}f', *inverse_bind_matrices))
    gltf.set_binary_blob(bytes(all_data))
    
    print(f"? Created glTF with {len(joint_nodes)} joints, {len(primitives)} primitives, and proper skinning")
    return gltf


def _get_bone_hierarchy_order(bones: Dict) -> List[str]:
    """Get bones in hierarchical order (parents before children)."""
    roots = [name for name, bone in bones.items() if not bone.parent or bone.parent not in bones]
    
    ordered = []
    visited = set()
    
    def visit_bone(bone_name: str):
        if bone_name in visited or bone_name not in bones:
            return
        visited.add(bone_name)
        ordered.append(bone_name)
        
        children = [name for name, bone in bones.items() if bone.parent == bone_name]
        for child in sorted(children):
            visit_bone(child)
    
    for root in sorted(roots):
        visit_bone(root)
    
    return ordered


def _create_accessors_for_mesh(gltf: GLTF2, vertex_count: int, index_count: int, vertex_offset: int, index_offset: int):
    """Create accessors for position, normal, joints, weights, and indices."""
    
    # Position accessor
    pos_accessor = Accessor()
    pos_accessor.bufferView = 0
    pos_accessor.byteOffset = vertex_offset
    pos_accessor.componentType = FLOAT
    pos_accessor.count = vertex_count
    pos_accessor.type = "VEC3"
    gltf.accessors.append(pos_accessor)
    
    # Normal accessor
    norm_accessor = Accessor()
    norm_accessor.bufferView = 0
    norm_accessor.byteOffset = vertex_offset + vertex_count * 3 * 4
    norm_accessor.componentType = FLOAT
    norm_accessor.count = vertex_count
    norm_accessor.type = "VEC3"
    gltf.accessors.append(norm_accessor)
    
    # Joints accessor
    joints_accessor = Accessor()
    joints_accessor.bufferView = 0
    joints_accessor.byteOffset = vertex_offset + vertex_count * 6 * 4
    joints_accessor.componentType = UNSIGNED_SHORT
    joints_accessor.count = vertex_count
    joints_accessor.type = "VEC4"
    gltf.accessors.append(joints_accessor)
    
    # Weights accessor
    weights_accessor = Accessor()
    weights_accessor.bufferView = 0
    weights_accessor.byteOffset = vertex_offset + vertex_count * 6 * 4 + vertex_count * 4 * 2
    weights_accessor.componentType = FLOAT
    weights_accessor.count = vertex_count
    weights_accessor.type = "VEC4"
    gltf.accessors.append(weights_accessor)
    
    # Index accessor
    index_accessor = Accessor()
    index_accessor.bufferView = 1
    index_accessor.byteOffset = index_offset
    index_accessor.componentType = UNSIGNED_SHORT
    index_accessor.count = index_count
    index_accessor.type = "SCALAR"
    gltf.accessors.append(index_accessor)
