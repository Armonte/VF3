"""
VF3 Complete Character to glTF Exporter
Modular version with ALL functionality from the original 2000+ line script.
"""

import os
import sys
import argparse
import numpy as np
import trimesh
from typing import Dict, List, Any, Optional

# Import all modular components
from vf3_loader import (
    read_descriptor, parse_frame_bones, parse_skin_entries, parse_defaultcos,
    resolve_identifier_to_attachments, parse_attachment_block_lines,
    parse_dynamic_visual_mesh, build_world_transforms, find_mesh_file
)
from vf3_occupancy import filter_attachments_by_occupancy_with_dynamic, parse_occupancy_vector
from vf3_materials import (
    apply_materials_to_mesh, split_mesh_by_materials, merge_body_meshes, 
    determine_dynamic_visual_material
)
from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_scene_assembly import (
    create_bone_hierarchy, create_child_attachment_nodes, is_core_body_part
)
from vf3_dynamic_visual import process_dynamic_visual_meshes


def process_attachments(attachments: List, world_transforms: Dict, scene: trimesh.Scene, 
                       scene_graph_nodes: Dict, merge_female_body: bool = False) -> Dict[str, Any]:
    """Process all mesh attachments with proper material handling and scene graph parenting."""
    mesh_count = 0
    prefix_counts: Dict[str, int] = {}
    female_body_meshes: List[trimesh.Trimesh] = []
    processed_attachments: Dict[str, List[str]] = {}
    geometry_to_attachment_map: Dict[str, str] = {}
    all_materials = []
    all_textures = []
    
    for att in attachments:
        # Handle duplicate attachments for the same bone
        bone_key = att.attach_bone
        if bone_key not in processed_attachments:
            processed_attachments[bone_key] = []
        
        existing_resources = processed_attachments[bone_key]
        
        # Check for conflicts only among core body parts
        should_skip = False
        if is_core_body_part(att.resource_id):
            for existing_resource in existing_resources:
                if is_core_body_part(existing_resource):
                    if existing_resource.startswith('female.') and not att.resource_id.startswith('female.'):
                        print(f"Replacing core body part {existing_resource} with character-specific {att.resource_id} for bone {bone_key}")
                        processed_attachments[bone_key].remove(existing_resource)
                        break
                    elif not existing_resource.startswith('female.') and att.resource_id.startswith('female.'):
                        print(f"Skipping generic core body part {att.resource_id} - already have character-specific {existing_resource} for bone {bone_key}")
                        should_skip = True
                        break
                    else:
                        print(f"Skipping duplicate core body part {att.resource_id} for bone {bone_key} - already have {existing_resource}")
                        should_skip = True
                        break
        else:
            if att.resource_id in existing_resources:
                print(f"Skipping duplicate accessory {att.resource_id} for bone {bone_key}")
                should_skip = True
        
        if should_skip:
            continue
        
        processed_attachments[bone_key].append(att.resource_id)
        mesh_path = find_mesh_file(att.resource_id)
        if not mesh_path:
            print(f"Could not find mesh file for {att.resource_id}")
            continue

        print(f"Found mesh file: {mesh_path}")
        try:
            node_name = att.child_name or att.attach_bone
            name = os.path.basename(mesh_path)
            
            mesh_data = load_mesh_with_full_materials(mesh_path)
            if not mesh_data['mesh']:
                print(f"Failed to load mesh from {mesh_path}")
                continue
                
            mesh = mesh_data['mesh']
            
            # Store materials for this mesh
            if mesh_data['materials']:
                all_materials.extend(mesh_data['materials'])
                print(f"  Loaded {len(mesh_data['materials'])} materials from {mesh_path}")
            
            if mesh_data['textures']:
                all_textures.extend([tex for tex in mesh_data['textures'] if tex not in all_textures])
                print(f"  Found textures: {mesh_data['textures']}")
            
            # Handle multi-material meshes by splitting them
            if mesh_data.get('face_materials') and len(set(mesh_data['face_materials'])) > 1:
                print(f"Multi-material mesh detected, splitting into {len(set(mesh_data['face_materials']))} parts")
                split_meshes = split_mesh_by_materials(mesh_data)
                mesh_data['split_meshes'] = split_meshes
                mesh_data['is_split'] = True
            else:
                # Single material mesh - apply materials now
                if mesh_data['materials'] or mesh_data['textures']:
                    base_path = os.path.dirname(mesh_path)
                    mesh = apply_materials_to_mesh(mesh, mesh_data['materials'], mesh_data['textures'], base_path)
                    mesh_data['mesh'] = mesh

            mesh_count += 1
        except Exception as e:
            print(f"Failed to load mesh {mesh_path}: {e}")
            continue

        # Count by resource prefix
        if '.' in att.resource_id:
            pref = att.resource_id.split('.', 1)[0]
            prefix_counts[pref] = prefix_counts.get(pref, 0) + 1

        # Apply world transforms to position mesh correctly
        if att.attach_bone in world_transforms:
            world_pos = world_transforms[att.attach_bone]
            world_T = np.eye(4)
            world_T[:3, 3] = np.array(world_pos, dtype=float)
        else:
            world_T = np.eye(4)
            print(f"WARNING: No world transform found for bone {att.attach_bone}")
        
        # Check if this mesh was split into multiple parts
        if mesh_data.get('is_split'):
            split_meshes = mesh_data['split_meshes']
            for split_data in split_meshes:
                split_mesh = split_data['mesh']
                
                if split_data['materials'] or split_data['textures']:
                    base_path = os.path.dirname(mesh_path)
                    split_mesh = apply_materials_to_mesh(split_mesh, split_data['materials'], split_data['textures'], base_path)
                
                split_mesh = split_mesh.copy()
                split_mesh.apply_transform(world_T)
                
                split_name = f"{name}_mat{split_data['material_index']}"
                if merge_female_body and att.resource_id.startswith('female.'):
                    female_body_meshes.append(split_mesh)
                    print(f"Collected female body part {split_name} for merging")
                else:
                    scene.add_geometry(split_mesh, node_name=split_name)
                    if node_name in scene_graph_nodes:
                        scene.graph.update(frame_from=split_name, frame_to=node_name)
                    geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = att.resource_id
                    print(f"Added split mesh {split_name} to scene under parent bone {node_name}")
        else:
            mesh = mesh_data['mesh']
            mesh = mesh.copy()
            mesh.apply_transform(world_T)

            if merge_female_body and att.resource_id.startswith('female.'):
                female_body_meshes.append(mesh)
                print(f"Collected female body part {name} for merging")
            else:
                scene.add_geometry(mesh, node_name=name)
                if node_name in scene_graph_nodes:
                    scene.graph.update(frame_from=name, frame_to=node_name)
                geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = att.resource_id
                print(f"Added mesh {name} to scene under parent bone {node_name}")
    
    # Merge female body parts if requested
    if merge_female_body and female_body_meshes:
        print(f"Merging {len(female_body_meshes)} female body parts into unified mesh...")
        merged_body = merge_body_meshes(female_body_meshes)
        scene.add_geometry(merged_body, node_name="female_body_merged")
        geometry_to_attachment_map[f"geometry_{len(scene.geometry) - 1}"] = "female_body_merged"
        print(f"Added merged female body with {len(merged_body.vertices)} vertices and {len(merged_body.faces)} faces")

    print(f"Total meshes added to scene: {mesh_count}")
    if prefix_counts:
        print("Meshes by source prefix:")
        for k, v in sorted(prefix_counts.items()):
            print(f"  - {k}: {v}")
    
    return {
        'mesh_count': mesh_count,
        'geometry_to_attachment_map': geometry_to_attachment_map,
        'materials': all_materials,
        'textures': all_textures,
        'prefix_counts': prefix_counts
    }


def assemble_complete_scene(descriptor_path: str, include_skin: bool = True, include_items: bool = True, 
                           merge_female_body: bool = False) -> dict:
    """Complete scene assembly with all functionality from the original export_ciel_to_gltf.py."""
    print(f"Reading descriptor: {descriptor_path}")
    desc = read_descriptor(descriptor_path)
    print(f"Descriptor blocks: {list(desc.blocks.keys())}")
    
    bones = parse_frame_bones(desc)
    print(f"Found {len(bones)} bones: {list(bones.keys())}")
    
    # Parse attachments with occupancy information for proper filtering
    skin_attachments_with_occupancy = []
    clothing_attachments_with_occupancy = []
    
    # Parse skin attachments with occupancy vectors
    if include_skin:
        for occ_str, ident in parse_skin_entries(desc):
            occupancy = parse_occupancy_vector(occ_str)
            atts, dynamic_mesh = resolve_identifier_to_attachments(ident, desc)
            
            skin_attachments_with_occupancy.append({
                'occupancy': occupancy,
                'attachments': atts,
                'source': ident,
                'dynamic_mesh': dynamic_mesh
            })
    
    # Parse clothing attachments with occupancy vectors
    if include_items:
        for full in parse_defaultcos(desc):
            if '.' not in full:
                continue
            prefix, item = full.split('.', 1)
            item_block = desc.blocks.get(item)
            if not item_block:
                continue
            for raw in item_block:
                s = raw.strip()
                if not s or ':' not in s or s.startswith('class:'):
                    continue
                occ_str, vp_ident = s.split(':', 1)
                occupancy = parse_occupancy_vector(occ_str.strip())
                vp_ident = vp_ident.strip()
                
                if '.' in vp_ident:
                    _, vp_name = vp_ident.split('.', 1)
                else:
                    vp_name = vp_ident
                vp_block = desc.blocks.get(vp_name)
                if vp_block:
                    atts = parse_attachment_block_lines(vp_block)
                    clothing_dyn_mesh = parse_dynamic_visual_mesh(vp_block)
                    
                    clothing_attachments_with_occupancy.append({
                        'occupancy': occupancy,
                        'attachments': atts,
                        'source': f"{full} ({occ_str})",
                        'dynamic_mesh': clothing_dyn_mesh
                    })
                    
                    if clothing_dyn_mesh:
                        print(f"DEBUG: Found clothing DynamicVisual mesh in {vp_name} with {len(clothing_dyn_mesh['vertices'])} vertices")
                break
    
    # Apply occupancy-based filtering to resolve conflicts
    print(f"DEBUG: Before filtering - {len(skin_attachments_with_occupancy)} skin, {len(clothing_attachments_with_occupancy)} clothing")
    filtered_result = filter_attachments_by_occupancy_with_dynamic(skin_attachments_with_occupancy, clothing_attachments_with_occupancy)
    attachments = filtered_result['attachments']
    dynamic_meshes = filtered_result['dynamic_meshes']
    print(f"DEBUG: After filtering - {len(attachments)} final attachments, {len(dynamic_meshes)} dynamic meshes")
    
    # Process additional *_vp blocks with DynamicVisual data that aren't in defaultcos
    if include_items:
        processed_vp_blocks = set()
        
        # Track which *_vp blocks were already processed in defaultcos
        for full in parse_defaultcos(desc):
            if '.' in full:
                prefix, item = full.split('.', 1)
                item_block = desc.blocks.get(item)
                if item_block:
                    for raw in item_block:
                        s = raw.strip()
                        if ':' in s and not s.startswith('class:'):
                            _, vp_ident = s.split(':', 1)
                            vp_ident = vp_ident.strip()
                            if '.' in vp_ident:
                                _, vp_name = vp_ident.split('.', 1)
                            else:
                                vp_name = vp_ident
                            if vp_name.endswith('_vp'):
                                processed_vp_blocks.add(vp_name)
                            break
        
        print(f"DEBUG: Already processed *_vp blocks: {processed_vp_blocks}")
        
        # Process remaining *_vp blocks with DynamicVisual data
        additional_dynamic_count = 0
        for block_name, block_lines in desc.blocks.items():
            if (block_name.endswith('_vp') and 
                block_name not in processed_vp_blocks and 
                any('DynamicVisual:' in line for line in block_lines)):
                
                additional_dyn_mesh = parse_dynamic_visual_mesh(block_lines)
                if additional_dyn_mesh:
                    additional_dynamic_count += 1
                    print(f"DEBUG: Found additional DynamicVisual mesh in {block_name} with {len(additional_dyn_mesh['vertices'])} vertices")
                    dynamic_meshes.append(additional_dyn_mesh)
        
        if additional_dynamic_count > 0:
            print(f"DEBUG: Found {additional_dynamic_count} additional *_vp blocks with DynamicVisual data")
    
    print(f"Found {len(attachments)} attachments, {len(dynamic_meshes)} dynamic meshes")
    
    world_transforms = build_world_transforms(bones, attachments)
    print(f"Built {len(world_transforms)} world transforms")

    # Create scene and set up bone hierarchy
    scene = trimesh.Scene()
    scene_graph_nodes = create_bone_hierarchy(bones, scene)
    create_child_attachment_nodes(attachments, scene_graph_nodes, scene)
    
    # Process all mesh attachments
    attachment_results = process_attachments(attachments, world_transforms, scene, scene_graph_nodes, merge_female_body)
    
    # Collect all existing mesh vertices for snapping
    all_mesh_vertices = []
    for geom_name, geom in scene.geometry.items():
        if hasattr(geom, 'vertices') and len(geom.vertices) > 0:
            all_mesh_vertices.extend(geom.vertices.tolist())
    all_mesh_vertices = np.array(all_mesh_vertices) if all_mesh_vertices else np.array([]).reshape(0, 3)
    
    # Process DynamicVisual meshes with bone splitting
    connectors_created = process_dynamic_visual_meshes(
        dynamic_meshes, world_transforms, all_mesh_vertices,
        attachment_results['materials'], attachment_results['geometry_to_attachment_map'], scene
    )
    
    print(f"\n? BONE SPLITTING SUCCESS: Created {connectors_created} bone-specific connectors (vs {len(dynamic_meshes)} original cross-bone meshes)")
    print(f"Scene created with {len(scene.geometry)} geometries")

    return {
        'scene': scene,
        'materials': attachment_results['materials'],
        'textures': attachment_results['textures']
    }


def export_glb(scene: trimesh.Scene, out_path: str) -> None:
    """Export scene to GLB/GLTF format"""
    ext = os.path.splitext(out_path)[1].lower()
    if ext not in ('.glb', '.gltf'):
        raise ValueError('Output path must end with .glb or .gltf')
    
    if not scene.geometry:
        raise ValueError("Scene has no geometry to export!")
    
    print(f"Exporting scene with {len(scene.geometry)} geometries to {out_path}")
    scene.export(out_path)


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description='VF3 character to glTF exporter - COMPLETE VERSION')
    parser.add_argument('--desc', default=os.path.join(base_dir, 'data', 'CIEL.TXT'), help='Path to descriptor TXT')
    parser.add_argument('--out', default=None, help='Output GLB/GLTF path')
    
    # Export mode options
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--skin-only', action='store_true', help='Export only skin/body parts (no clothing)')
    mode_group.add_argument('--naked', action='store_true', help='Export completely naked body (skin only)')
    mode_group.add_argument('--base-costume', action='store_true', help='Export with default costume from <defaultcos> block')
    mode_group.add_argument('--items-only', action='store_true', help='Include only costume items, no base skin')
    
    parser.add_argument('--merge-body', action='store_true', help='Merge all female body parts into a single unified mesh')
    args = parser.parse_args()

    descriptor = args.desc
    if args.out:
        out = args.out
    else:
        char_name = os.path.splitext(os.path.basename(descriptor))[0]
        out = os.path.join(base_dir, f'{char_name.lower()}_complete.glb')

    # Determine export mode
    include_skin = True
    include_items = True
    
    if args.naked:
        include_skin, include_items = True, False
        print("Export mode: NAKED - skin/body parts only")
    elif args.skin_only:
        include_skin, include_items = True, False
        print("Export mode: SKIN-ONLY - body parts without clothing")
    elif args.base_costume:
        include_skin, include_items = True, True
        print("Export mode: BASE-COSTUME - skin + default costume from <defaultcos>")
    elif args.items_only:
        include_skin, include_items = False, True
        print("Export mode: ITEMS-ONLY - costume items without base skin")
    else:
        include_skin, include_items = True, True
        print("Export mode: FULL-OUTFIT - complete character with all items")

    scene_data = assemble_complete_scene(descriptor, include_skin=include_skin, include_items=include_items, merge_female_body=args.merge_body)
    scene = scene_data['scene']
    materials = scene_data['materials'] 
    textures = scene_data['textures']
    
    print(f"Scene assembled with {len(scene.geometry)} geometries, {len(materials)} materials, {len(textures)} unique textures")
    
    export_glb(scene, out)
    print(f'Exported: {out}')
