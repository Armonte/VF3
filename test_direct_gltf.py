#!/usr/bin/env python3
"""
Test script for direct glTF export with proper skeletal animation.
"""

import os
from vf3_loader import read_descriptor, parse_frame_bones, build_world_transforms
from export_ciel_to_gltf_complete import assemble_complete_scene
from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_gltf_exporter import create_gltf_with_skeleton

def test_direct_gltf_export(descriptor_path: str, output_path: str):
    """Test the direct glTF export pipeline."""
    
    print(f"? Testing direct glTF export: {descriptor_path} -> {output_path}")
    
    # Step 1: Read descriptor
    desc = read_descriptor(descriptor_path)
    bones = parse_frame_bones(desc)
    
    # Step 2: Get attachments (using base costume)
    include_skin = True
    include_items = True
    
    skin_attachments, clothing_attachments, dynamic_meshes = filter_attachments_by_occupancy_with_dynamic(
        desc, include_skin=include_skin, include_items=include_items
    )
    
    attachments = skin_attachments + clothing_attachments
    print(f"Found {len(attachments)} attachments")
    
    # Step 3: Build world transforms
    world_transforms = build_world_transforms(bones, attachments)
    print(f"Built {len(world_transforms)} world transforms")
    
    # Step 4: Load mesh data
    mesh_data = {}
    base_dir = os.path.dirname(descriptor_path)
    
    for att in attachments:
        mesh_path = None
        
        # Find mesh file
        if '.' in att.resource_id:
            prefix, suffix = att.resource_id.split('.', 1)
            
            # Try character-specific directory first
            char_dir = os.path.join(base_dir, prefix)
            if os.path.exists(char_dir):
                for ext in ['.X', '.x']:
                    candidate = os.path.join(char_dir, suffix + ext)
                    if os.path.exists(candidate):
                        mesh_path = candidate
                        break
        
        if mesh_path and os.path.exists(mesh_path):
            try:
                mesh_info = load_mesh_with_full_materials(mesh_path)
                if mesh_info['mesh']:
                    mesh_data[att.resource_id] = mesh_info
                    print(f"  Loaded {att.resource_id} from {mesh_path}")
            except Exception as e:
                print(f"  Failed to load {mesh_path}: {e}")
        else:
            print(f"  Could not find mesh for {att.resource_id}")
    
    print(f"Loaded {len(mesh_data)} meshes")
    
    # Step 5: Create glTF with skeleton
    gltf = create_gltf_with_skeleton(bones, attachments, world_transforms, mesh_data)
    
    # Step 6: Save glTF
    gltf.save(output_path)
    print(f"? Exported glTF to {output_path}")


if __name__ == "__main__":
    test_direct_gltf_export("data/aistrobot.TXT", "aistrobot_direct.glb")
