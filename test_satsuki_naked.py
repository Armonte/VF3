#!/usr/bin/env python3
"""
Test naked Satsuki with all DynamicVisual connectors.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vf3_loader import (
    read_descriptor,
    parse_frame_bones,
    build_world_transforms,
    resolve_identifier_to_attachments,
)
from vf3_occupancy import filter_attachments_by_occupancy_with_dynamic, parse_occupancy_vector
from vf3_dynamic_visual import process_dynamic_visual_meshes
from vf3_mesh_loader import load_mesh_with_full_materials
import numpy as np
import trimesh

def test_naked_satsuki():
    """Test naked Satsuki with complete body and DynamicVisual connectors."""
    print("🧪 Testing complete naked Satsuki model...")
    
    # Load descriptor
    desc = read_descriptor('data/satsuki.txt')
    bones = parse_frame_bones(desc)
    
    # Process skin attachments only (naked mode)
    skin_attachments_with_occupancy = []
    skin_lines = desc.blocks.get('skin', [])
    
    for line in skin_lines:
        if not line.strip() or ':' not in line:
            continue
        parts = line.strip().split(':', 1)
        if len(parts) != 2:
            continue
        occ_str, resource_id = parts
        occupancy_vector = parse_occupancy_vector(occ_str)
        skin_attachments, skin_dyn_mesh = resolve_identifier_to_attachments(resource_id.strip(), desc)
        
        if skin_attachments:
            skin_attachments_with_occupancy.append({
                'occupancy': occupancy_vector,
                'source': f'skin:{resource_id}',
                'attachments': skin_attachments,
                'dynamic_mesh': skin_dyn_mesh
            })
    
    # Apply occupancy filtering (no clothing)
    filtered_result = filter_attachments_by_occupancy_with_dynamic(skin_attachments_with_occupancy, [])
    final_attachments = filtered_result['attachments']
    final_dynamic_meshes = filtered_result['dynamic_meshes']
    
    print(f"Final: {len(final_attachments)} attachments, {len(final_dynamic_meshes)} dynamic meshes")
    
    # Build world transforms
    world_transforms = build_world_transforms(bones, final_attachments)
    
    # Create scene and load body parts
    scene = trimesh.Scene()
    all_materials = {}
    geometry_to_mesh_map = {}
    all_mesh_vertices_list = []
    
    # Load all body part meshes
    for attachment in final_attachments:
        resource_parts = attachment.resource_id.split('.')
        if len(resource_parts) >= 2:
            mesh_dir = resource_parts[0]
            mesh_name = resource_parts[1] 
            mesh_path = f'data/{mesh_dir}/{mesh_name}.X'
            node_name = attachment.attach_bone
            
            try:
                result = load_mesh_with_full_materials(mesh_path)
                mesh = result.get('mesh')
                materials = result.get('materials', [])
                if mesh:
                    bone_pos = world_transforms.get(node_name, (0.0, 0.0, 0.0))
                    vertices = mesh.vertices.copy()
                    vertices += bone_pos
                    context_mesh = trimesh.Trimesh(vertices=vertices, faces=mesh.faces, process=True)
                    
                    # Ensure smooth vertex normals for Gouraud shading
                    _ = context_mesh.vertex_normals  # Force computation of smooth normals
                    
                    # Apply material colors
                    if materials and len(materials) > 0:
                        first_material = materials[0]
                        if 'diffuse' in first_material:
                            diffuse_color = first_material['diffuse']
                            if len(diffuse_color) >= 3:
                                rgba = [int(c * 255) for c in diffuse_color[:3]] + [255]
                                context_mesh.visual.face_colors = rgba
                    else:
                        context_mesh.visual.face_colors = [200, 150, 100, 255]  # Skin color
                    
                    scene.add_geometry(context_mesh, node_name=f"body_{node_name}")
                    all_mesh_vertices_list.extend(vertices)
                    print(f"  Loaded {node_name}: {len(vertices)} vertices")
            except Exception as e:
                print(f"  Failed to load {node_name}: {e}")
    
    # Combine all mesh vertices for DynamicVisual processing
    if all_mesh_vertices_list:
        all_mesh_vertices = np.vstack(all_mesh_vertices_list)
    else:
        all_mesh_vertices = np.array([[0,0,0]])
    
    # Process DynamicVisual meshes
    print(f"\n🔧 Processing DynamicVisual connectors...")
    connector_count = process_dynamic_visual_meshes(
        final_dynamic_meshes, 
        world_transforms,
        all_mesh_vertices,
        all_materials,
        geometry_to_mesh_map,
        scene
    )
    
    print(f"✅ Created {connector_count} DynamicVisual connectors")
    print(f"✅ Complete model: {len(scene.geometry)} total geometries")
    print(f"   - Body parts: {len(final_attachments)}")
    print(f"   - DynamicVisual connectors: {connector_count}")
    
    # Export the complete model
    try:
        scene.export('satsuki_naked_complete.glb')
        print(f"✅ Exported complete naked Satsuki to satsuki_naked_complete.glb")
    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    test_naked_satsuki()