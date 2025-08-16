#!/usr/bin/env python3
"""
Debug script to understand exactly how connectors are being assigned.
"""

import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from vf3_loader import read_descriptor
from vf3_blender_exporter_modular import _collect_attachments_with_occupancy_filtering

def debug_connector_assignment(descriptor_path):
    """Debug connector assignment logic step by step."""
    print(f"🔍 Debugging connector assignment for: {descriptor_path}")
    print("=" * 80)
    
    desc = read_descriptor(descriptor_path)
    
    # Get filtered attachments and dynamic meshes
    attachments, clothing_dynamic_meshes = _collect_attachments_with_occupancy_filtering(desc, True, True)
    
    print(f"\n📊 FINAL RESULT: {len(attachments)} attachments, {len(clothing_dynamic_meshes)} dynamic meshes")
    print("\n🔌 DYNAMIC MESH ANALYSIS:")
    
    for i, dyn_mesh in enumerate(clothing_dynamic_meshes):
        vertices = dyn_mesh.get('vertices', [])
        faces = dyn_mesh.get('faces', [])
        vertex_bones = dyn_mesh.get('vertex_bones', [])
        
        # Count bones by anatomical region
        bone_counts = {}
        for bone in vertex_bones:
            bone_counts[bone] = bone_counts.get(bone, 0) + 1
        
        # Classify by anatomical region
        region_counts = {
            'body': sum(bone_counts.get(bone, 0) for bone in ['body', 'l_breast', 'r_breast', 'waist', 'skirt_f', 'skirt_r']),
            'left_arm': sum(bone_counts.get(bone, 0) for bone in ['l_arm1', 'l_arm2', 'l_hand']),
            'right_arm': sum(bone_counts.get(bone, 0) for bone in ['r_arm1', 'r_arm2', 'r_hand']),
            'left_leg': sum(bone_counts.get(bone, 0) for bone in ['l_leg1', 'l_leg2', 'l_foot']),
            'right_leg': sum(bone_counts.get(bone, 0) for bone in ['r_leg1', 'r_leg2', 'r_foot']),
            'head': sum(bone_counts.get(bone, 0) for bone in ['head', 'neck'])
        }
        
        # Determine target group using same logic as the actual system
        max_count = max(region_counts.values())
        tied_regions = [region for region, count in region_counts.items() if count == max_count and count > 0]
        
        # Apply priority: body > left_arm > right_arm > left_leg > right_leg > head
        priority_order = ['body', 'left_arm', 'right_arm', 'left_leg', 'right_leg', 'head']
        target_group = None
        
        if len(tied_regions) == 1:
            target_group = tied_regions[0]
        else:
            for priority_region in priority_order:
                if priority_region in tied_regions:
                    target_group = priority_region
                    break
            if not target_group:
                target_group = tied_regions[0]
        
        print(f"\n  Dynamic Mesh {i}:")
        print(f"    Vertices: {len(vertices)}, Faces: {len(faces)}")
        print(f"    All bones: {list(bone_counts.keys())}")
        print(f"    Bone counts per bone: {bone_counts}")
        print(f"    Region vertex counts: {region_counts}")
        print(f"    Target group: {target_group} (max_count={max_count}, tied={tied_regions})")
        
        # Identify mixed connectors (span multiple regions)
        regions_with_bones = [region for region, count in region_counts.items() if count > 0]
        if len(regions_with_bones) > 1:
            print(f"    ⚠️  MIXED CONNECTOR: spans {regions_with_bones}")
            
            # Suggest splitting logic
            if 'left_arm' in regions_with_bones and 'right_arm' in regions_with_bones:
                print(f"    💡 Suggestion: Split into left_arm and right_arm parts")
            elif 'left_leg' in regions_with_bones and 'right_leg' in regions_with_bones:
                print(f"    💡 Suggestion: Split into left_leg and right_leg parts")
            else:
                print(f"    💡 Suggestion: Assign to {target_group} (largest region)")
        else:
            print(f"    ✅ PURE CONNECTOR: belongs to {target_group}")
    
    print("\n" + "=" * 80)
    print("🎯 SUMMARY:")
    
    # Count connectors by target group
    group_assignments = {}
    mixed_connectors = 0
    
    for i, dyn_mesh in enumerate(clothing_dynamic_meshes):
        vertex_bones = dyn_mesh.get('vertex_bones', [])
        bone_counts = {}
        for bone in vertex_bones:
            bone_counts[bone] = bone_counts.get(bone, 0) + 1
        
        region_counts = {
            'body': sum(bone_counts.get(bone, 0) for bone in ['body', 'l_breast', 'r_breast', 'waist', 'skirt_f', 'skirt_r']),
            'left_arm': sum(bone_counts.get(bone, 0) for bone in ['l_arm1', 'l_arm2', 'l_hand']),
            'right_arm': sum(bone_counts.get(bone, 0) for bone in ['r_arm1', 'r_arm2', 'r_hand']),
            'left_leg': sum(bone_counts.get(bone, 0) for bone in ['l_leg1', 'l_leg2', 'l_foot']),
            'right_leg': sum(bone_counts.get(bone, 0) for bone in ['r_leg1', 'r_leg2', 'r_foot']),
            'head': sum(bone_counts.get(bone, 0) for bone in ['head', 'neck'])
        }
        
        regions_with_bones = [region for region, count in region_counts.items() if count > 0]
        
        # Determine target group
        max_count = max(region_counts.values())
        tied_regions = [region for region, count in region_counts.items() if count == max_count and count > 0]
        priority_order = ['body', 'left_arm', 'right_arm', 'left_leg', 'right_leg', 'head']
        
        target_group = None
        if len(tied_regions) == 1:
            target_group = tied_regions[0]
        else:
            for priority_region in priority_order:
                if priority_region in tied_regions:
                    target_group = priority_region
                    break
            if not target_group:
                target_group = tied_regions[0]
        
        group_assignments[target_group] = group_assignments.get(target_group, 0) + 1
        
        if len(regions_with_bones) > 1:
            mixed_connectors += 1
    
    print(f"  Connector assignments: {group_assignments}")
    print(f"  Mixed connectors: {mixed_connectors}/{len(clothing_dynamic_meshes)}")
    
    if mixed_connectors > 0:
        print(f"  ⚠️  {mixed_connectors} connectors span multiple regions - may cause assignment issues")
    else:
        print(f"  ✅ All connectors are pure (single region) - assignment should be clean")

if __name__ == "__main__":
    debug_connector_assignment("data/satsuki.TXT")