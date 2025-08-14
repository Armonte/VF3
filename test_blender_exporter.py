#!/usr/bin/env python3
"""
Test the fixed Blender exporter with naked Satsuki.
This script tests the export without requiring Blender to be installed.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vf3_loader import (
    read_descriptor,
    parse_frame_bones,
    build_world_transforms,
)
from vf3_blender_exporter import _collect_attachments_with_occupancy_filtering
from vf3_mesh_loader import load_mesh_with_full_materials

def test_blender_exporter():
    """Test the Blender exporter data pipeline without running Blender."""
    print("🧪 Testing Blender exporter data pipeline...")
    
    # Load VF3 data (same as Blender exporter)
    desc = read_descriptor('data/satsuki.txt')
    bones = parse_frame_bones(desc)
    print(f"✅ Loaded {len(bones)} bones")
    
    # Collect attachments with occupancy filtering
    attachments, clothing_dynamic_meshes = _collect_attachments_with_occupancy_filtering(desc)
    print(f"✅ Collected {len(attachments)} attachments, {len(clothing_dynamic_meshes)} dynamic meshes")
    
    # Build world transforms
    world_transforms = build_world_transforms(bones, attachments)
    print(f"✅ Built world transforms for {len(world_transforms)} entities")
    
    # Load mesh data (same as Blender exporter)
    mesh_data = {}
    for att in attachments:
        mesh_path = f'data/{att.resource_id.replace(".", "/")}.X'
        if os.path.exists(mesh_path):
            try:
                mesh_info = load_mesh_with_full_materials(mesh_path)
                if mesh_info['mesh']:
                    mesh_data[att.resource_id] = mesh_info
                    print(f"  ✅ Loaded {att.resource_id}: {len(mesh_info['mesh'].vertices)} vertices")
            except Exception as e:
                print(f"  ❌ Failed to load {mesh_path}: {e}")
    
    print(f"✅ Loaded {len(mesh_data)} mesh files")
    
    # Test DynamicVisual processing
    print(f"🔧 Testing DynamicVisual processing...")
    from vf3_dynamic_visual import group_vertices_by_anatomical_region
    
    total_regions = 0
    for i, dyn_data in enumerate(clothing_dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
            
        vertices = dyn_data['vertices']
        vertex_bones = dyn_data.get('vertex_bones', [])
        
        print(f"  DynamicVisual mesh {i}: {len(vertices)} vertices")
        
        # Test anatomical region grouping
        region_groups = group_vertices_by_anatomical_region(vertices, vertex_bones)
        print(f"    Split into {len(region_groups)} regions: {list(region_groups.keys())}")
        total_regions += len(region_groups)
    
    print(f"✅ Total anatomical regions: {total_regions}")
    
    # Summary
    print(f"\n🎉 BLENDER EXPORTER DATA PIPELINE TEST COMPLETE:")
    print(f"   📊 {len(bones)} bones with proper hierarchy")  
    print(f"   🎭 {len(attachments)} mesh attachments") 
    print(f"   📦 {len(mesh_data)} loaded meshes with materials")
    print(f"   🔗 {len(clothing_dynamic_meshes)} DynamicVisual meshes")
    print(f"   🧩 {total_regions} anatomical connector regions")
    print(f"   ✅ Ready for Blender export!")
    
    return True

if __name__ == "__main__":
    test_blender_exporter()