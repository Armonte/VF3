#!/usr/bin/env python3
"""
VF3 Character Exporter to glTF - Modular Version
Exports VF3 character models with full clothing system, materials, and bone hierarchy.
"""

import argparse
import os
import sys
import trimesh
from typing import Dict, List, Any

# Import our modular components  
from vf3_loader import (
    read_descriptor,
    parse_frame_bones, 
    parse_skin_entries,
    parse_defaultcos,
    resolve_identifier_to_attachments,
    collect_active_attachments,
    build_world_transforms
)
from vf3_occupancy import filter_attachments_by_occupancy_with_dynamic, parse_occupancy_vector
from vf3_dynamic_visual import process_dynamic_visual_meshes
from vf3_scene_assembly import create_bone_hierarchy, create_child_attachment_nodes, attach_mesh_to_scene, merge_female_body_parts
from vf3_materials import apply_materials_to_mesh


def collect_attachments_with_occupancy(descriptor, include_skin=True, include_items=True):
    """Collect attachments with their occupancy data for filtering."""
    skin_attachments_with_occupancy = []
    clothing_attachments_with_occupancy = []
    
    # Collect skin attachments
    if include_skin and hasattr(descriptor, 'skin_attachments'):
        for att in descriptor.skin_attachments:
            occupancy = parse_occupancy_vector(att.occupancy_str) if hasattr(att, 'occupancy_str') else [0,0,0,0,0,0,0]
            skin_attachments_with_occupancy.append({
                'occupancy': occupancy,
                'source': att.resource_id,
                'attachments': [att],
                'dynamic_mesh': getattr(att, 'dynamic_mesh', None)
            })
    
    # Collect clothing attachments
    if include_items and hasattr(descriptor, 'item_attachments'):
        for att in descriptor.item_attachments:
            occupancy = parse_occupancy_vector(att.occupancy_str) if hasattr(att, 'occupancy_str') else [0,0,0,0,0,0,0]
            clothing_attachments_with_occupancy.append({
                'occupancy': occupancy,
                'source': att.resource_id,
                'attachments': [att],
                'dynamic_mesh': getattr(att, 'dynamic_mesh', None)
            })
    
    return skin_attachments_with_occupancy, clothing_attachments_with_occupancy


def assemble_scene(descriptor, include_skin=True, include_items=True, merge_female_body=False):
    """Assemble the complete character scene with modular components."""
    print("=== VF3 Character Assembly (Modular) ===")
    
    # Get bones
    bones = descriptor.bones
    print(f"Found {len(bones)} bones: {list(bones.keys())}")
    
    # Collect attachments with occupancy data
    skin_attachments, clothing_attachments = collect_attachments_with_occupancy(
        descriptor, include_skin, include_items
    )
    
    # Apply occupancy-based filtering
    filtered_results = filter_attachments_by_occupancy_with_dynamic(skin_attachments, clothing_attachments)
    final_attachments = filtered_results['attachments']
    final_dynamic_meshes = filtered_results['dynamic_meshes']
    
    print(f"Found {len(final_attachments)} attachments after occupancy filtering")
    for att in final_attachments:
        print(f"  - {att.attach_bone} -> {att.resource_id}")
    
    # Create scene
    scene = trimesh.Scene()
    
    # Create bone hierarchy
    scene_graph_nodes = create_bone_hierarchy(bones, scene)
    
    # Create child attachment nodes
    create_child_attachment_nodes(final_attachments, bones, scene, scene_graph_nodes)
    
    # Load and attach meshes
    print(f"\nLoading {len(final_attachments)} meshes...")
    all_materials = {}
    all_textures = set()
    female_body_meshes = []
    geometry_to_attachment_map = {}
    prefix_counts = {}
    
    # Collect mesh vertices for DynamicVisual snapping
    all_mesh_vertices = []
    
    for att in final_attachments:
        mesh_path = att.get_mesh_path()
        if not mesh_path or not os.path.exists(mesh_path):
            print(f"Mesh file not found: {mesh_path}")
            continue
            
        print(f"Found mesh file: {mesh_path}")
        
        # Load mesh with materials
        try:
            mesh_data = att.load_mesh_with_materials()
            if mesh_data and 'mesh' in mesh_data:
                # Collect vertices for DynamicVisual snapping
                if mesh_data.get('is_split'):
                    for split_data in mesh_data['split_meshes']:
                        all_mesh_vertices.extend(split_data['mesh'].vertices.tolist())
                else:
                    all_mesh_vertices.extend(mesh_data['mesh'].vertices.tolist())
                
                # Store materials
                all_materials[att.resource_id] = mesh_data.get('materials', [])
                if 'textures' in mesh_data:
                    all_textures.update(mesh_data['textures'])
                
                # Attach mesh to scene
                attach_mesh_to_scene(
                    mesh_data, att, mesh_path, bones, final_attachments,
                    scene, scene_graph_nodes, merge_female_body,
                    female_body_meshes, geometry_to_attachment_map, prefix_counts
                )
                
        except Exception as e:
            print(f"Failed to load mesh {mesh_path}: {e}")
    
    # Merge female body parts if requested
    merge_female_body_parts(female_body_meshes, scene, scene_graph_nodes, geometry_to_attachment_map)
    
    # Process DynamicVisual meshes with bone splitting
    world_transforms = build_world_transforms(bones, final_attachments)
    geometry_to_mesh_map = {f"geometry_{i}": name for i, name in enumerate(geometry_to_attachment_map.values())}
    
    connector_count = process_dynamic_visual_meshes(
        final_dynamic_meshes, world_transforms, all_mesh_vertices,
        all_materials, geometry_to_mesh_map, scene
    )
    
    print(f"\nScene assembled with {len(scene.geometry)} geometries, created {connector_count} DynamicVisual connectors")
    
    return {
        'scene': scene,
        'materials': all_materials,
        'textures': all_textures
    }


def main():
    parser = argparse.ArgumentParser(description='Export VF3 character to glTF with modular architecture')
    parser.add_argument('--desc', required=True, help='Path to character descriptor file')
    parser.add_argument('--out', required=True, help='Output glTF/glb file path')
    parser.add_argument('--base-costume', action='store_true', help='Export with base costume from <defaultcos>')
    parser.add_argument('--merge-body', action='store_true', help='Merge female body parts into single mesh')
    parser.add_argument('--skin-only', action='store_true', help='Export skin only (no clothing items)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.desc):
        print(f"Error: Descriptor file not found: {args.desc}")
        sys.exit(1)
    
    # Load descriptor (simplified for now)
    print(f"Reading descriptor: {args.desc}")
    print("ERROR: Modular version not fully implemented yet. Use original export_ciel_to_gltf.py")
    sys.exit(1)
    
    # Determine what to include
    include_skin = True
    include_items = not args.skin_only
    
    if args.base_costume:
        print("Export mode: BASE-COSTUME - skin + default costume from <defaultcos>")
    elif args.skin_only:
        print("Export mode: SKIN-ONLY - skin meshes only")
    else:
        print("Export mode: FULL - skin + all available items")
    
    # Assemble scene
    scene_data = assemble_scene(descriptor, include_skin=include_skin, include_items=include_items, merge_female_body=args.merge_body)
    scene = scene_data['scene']
    
    # Export
    print(f"Exporting scene with {len(scene.geometry)} geometries to {args.out}")
    scene.export(args.out)
    print(f"Exported: {args.out}")


if __name__ == '__main__':
    main()
