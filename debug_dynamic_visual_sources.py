#!/usr/bin/env python3
"""
Debug script to understand why we're getting 6 dynamic visual meshes for Satsuki
when the source file only shows 3 DynamicVisual blocks.
"""

import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from vf3_loader import (
    read_descriptor, 
    parse_dynamic_visual_mesh,
    collect_active_attachments
)

def debug_dynamic_visual_sources(descriptor_path):
    """Debug all sources of DynamicVisual data."""
    print(f"🔍 Debugging DynamicVisual sources in: {descriptor_path}")
    print("=" * 80)
    
    desc = read_descriptor(descriptor_path)
    
    # 1. Find ALL blocks with DynamicVisual data
    print("\n📋 ALL blocks containing 'DynamicVisual:' in source file:")
    blocks_with_dynamic = []
    for block_name, block_lines in desc.blocks.items():
        if any('DynamicVisual:' in line for line in block_lines):
            blocks_with_dynamic.append(block_name)
            
            # Count vertices in this block
            vertex_count = 0
            in_dynamic_section = False
            for line in block_lines:
                if line.strip() == 'DynamicVisual:':
                    in_dynamic_section = True
                    continue
                elif line.strip() in ['Material:', 'FaceArray:'] or line.strip().startswith('<'):
                    in_dynamic_section = False
                    continue
                    
                if in_dynamic_section and ':' in line:
                    vertex_count += 1
            
            print(f"  - {block_name}: {vertex_count} vertices")
    
    print(f"\nTotal blocks with DynamicVisual: {len(blocks_with_dynamic)}")
    
    # 2. Use collect_active_attachments to see what gets loaded
    print("\n🔧 What collect_active_attachments() loads:")
    attachments, clothing_dynamic_meshes = collect_active_attachments(desc)
    
    print(f"Total dynamic meshes collected: {len(clothing_dynamic_meshes)}")
    for i, dyn_mesh in enumerate(clothing_dynamic_meshes):
        vertex_count = len(dyn_mesh.get('vertices', []))
        face_count = len(dyn_mesh.get('faces', []))
        vertex_bones = dyn_mesh.get('vertex_bones', [])
        unique_bones = list(set(vertex_bones))
        print(f"  Dynamic Mesh {i}: {vertex_count} vertices, {face_count} faces")
        print(f"    Bones: {unique_bones}")
    
    # 3. Parse each individual block manually to see what's in them
    print("\n📖 Manual parsing of each DynamicVisual block:")
    for block_name in blocks_with_dynamic:
        block_lines = desc.blocks[block_name]
        parsed_mesh = parse_dynamic_visual_mesh(block_lines)
        
        if parsed_mesh:
            vertices = parsed_mesh.get('vertices', [])
            faces = parsed_mesh.get('faces', [])
            vertex_bones = parsed_mesh.get('vertex_bones', [])
            unique_bones = list(set(vertex_bones))
            
            print(f"  {block_name}:")
            print(f"    {len(vertices)} vertices, {len(faces)} faces")
            print(f"    Bones: {unique_bones}")
            
            # Show first few vertex entries to see the structure
            print(f"    First 3 vertices:")
            for i, (vertex_tuple, bone) in enumerate(zip(vertices[:3], vertex_bones[:3])):
                pos1, pos2 = vertex_tuple
                print(f"      {i}: {bone} -> pos1={pos1}, pos2={pos2}")
        else:
            print(f"  {block_name}: Failed to parse")
    
    print("\n" + "=" * 80)
    print("🎯 ANALYSIS:")
    print(f"Source file has {len(blocks_with_dynamic)} blocks with DynamicVisual data")
    print(f"collect_active_attachments() returns {len(clothing_dynamic_meshes)} dynamic meshes")
    
    if len(blocks_with_dynamic) != len(clothing_dynamic_meshes):
        print("⚠️  MISMATCH! The number of source blocks doesn't match collected meshes!")
        print("   This suggests the loader is either:")
        print("   1. Splitting single blocks into multiple meshes")
        print("   2. Loading from multiple sources (skin + costume + additional)")
        print("   3. Duplicating or processing blocks multiple times")
    else:
        print("✅ Source blocks match collected meshes - this is expected")

if __name__ == "__main__":
    debug_dynamic_visual_sources("data/satsuki.TXT")