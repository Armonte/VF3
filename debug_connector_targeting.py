#!/usr/bin/env python3
"""
VF3 Connector Debugging Script
Isolates and tests connector targeting logic to identify why connectors are targeting wrong meshes.
"""

import sys
import os
sys.path.append('/mnt/c/dev/loot/VF3')

from vf3_loader import read_descriptor, parse_frame_bones, build_world_transforms
from vf3_occupancy import filter_attachments_by_occupancy_with_dynamic

def debug_connector_targeting():
    """Debug connector targeting logic step by step."""
    print("=== VF3 CONNECTOR TARGETING DEBUG ===")
    
    # Load Satsuki data
    desc = read_descriptor('data/satsuki.TXT')
    bones = parse_frame_bones(desc)
    
    # Import the collection function from blender exporter
    try:
        from vf3_blender_exporter import _collect_attachments_with_occupancy_filtering
        attachments, clothing_dynamic_meshes = _collect_attachments_with_occupancy_filtering(desc)
        print(f"✅ Loaded {len(attachments)} attachments, {len(clothing_dynamic_meshes)} dynamic meshes")
    except Exception as e:
        print(f"❌ Failed to load attachments: {e}")
        return
    
    print("\n=== PHASE 1: OCCUPANCY RESULTS ===")
    
    # Group attachments by bone
    bone_attachments = {}
    for att in attachments:
        bone = att.attach_bone
        if bone not in bone_attachments:
            bone_attachments[bone] = []
        bone_attachments[bone].append(att.resource_id)
    
    print("Attachments by bone:")
    for bone, resources in sorted(bone_attachments.items()):
        print(f"  {bone}: {resources}")
    
    print("\n=== PHASE 2: DYNAMIC MESH ANALYSIS ===")
    
    # Analyze dynamic meshes (connectors)
    for i, dynamic_mesh in enumerate(clothing_dynamic_meshes):
        print(f"\nDynamic Mesh {i}:")
        print(f"  Vertices: {len(dynamic_mesh.get('vertices', []))}")
        print(f"  Faces: {len(dynamic_mesh.get('faces', []))}")
        print(f"  Source: {dynamic_mesh.get('source_info', {}).get('source', 'unknown')}")
        
        # Analyze vertex bones to understand connector anatomy
        vertex_bones = dynamic_mesh.get('vertex_bones', [])
        if vertex_bones:
            bone_counts = {}
            for vb in vertex_bones:
                # Handle both string and dict formats
                if isinstance(vb, str):
                    bone = vb
                elif isinstance(vb, dict):
                    bone = vb.get('bone', 'unknown')
                else:
                    bone = str(vb)
                bone_counts[bone] = bone_counts.get(bone, 0) + 1
            
            print(f"  Vertex distribution by bone:")
            for bone, count in sorted(bone_counts.items()):
                print(f"    {bone}: {count} vertices")
                
            # Determine connector type based on bone distribution
            bones_involved = list(bone_counts.keys())
            connector_type = classify_connector_type(bones_involved)
            print(f"  🔍 PREDICTED TYPE: {connector_type}")
        
        # Check for material data
        if 'material' in dynamic_mesh:
            print(f"  Material data: {dynamic_mesh['material']}")

def classify_connector_type(bones_involved):
    """Classify what type of connector this should be based on bones involved."""
    bones_str = ' '.join(sorted(bones_involved)).lower()
    
    if 'body' in bones_str and ('l_breast' in bones_str or 'r_breast' in bones_str):
        return "BODY/CHEST connector (should target blazer body)"
    elif ('l_arm1' in bones_str or 'r_arm1' in bones_str) and ('l_arm2' in bones_str or 'r_arm2' in bones_str):
        return "ELBOW connector (should target blazer arms)"
    elif ('l_arm2' in bones_str or 'r_arm2' in bones_str) and ('l_hand' in bones_str or 'r_hand' in bones_str):
        return "WRIST connector (should target blazer hands)"
    elif 'waist' in bones_str and ('l_leg1' in bones_str or 'r_leg1' in bones_str):
        return "HIP connector (should target waist/skirt)"
    elif ('l_leg1' in bones_str or 'r_leg1' in bones_str) and ('l_leg2' in bones_str or 'r_leg2' in bones_str):
        return "KNEE connector (should target skin legs)"
    elif ('l_leg2' in bones_str or 'r_leg2' in bones_str) and ('l_foot' in bones_str or 'r_foot' in bones_str):
        return "ANKLE connector (should target shoes)"
    else:
        return f"UNKNOWN connector type (bones: {bones_involved})"

def debug_mesh_names_after_occupancy():
    """Debug what mesh names exist after occupancy filtering."""
    print("\n=== PHASE 3: SIMULATED MESH NAMES ===")
    
    # Simulate what mesh names would exist in Blender after our occupancy filtering
    desc = read_descriptor('data/satsuki.TXT')
    
    try:
        from vf3_blender_exporter import _collect_attachments_with_occupancy_filtering
        attachments, _ = _collect_attachments_with_occupancy_filtering(desc)
        
        # Generate expected mesh names
        expected_mesh_names = []
        for att in attachments:
            # Generate mesh name like: bone_resource_id
            mesh_name = f"{att.attach_bone}_{att.resource_id}"
            expected_mesh_names.append(mesh_name)
        
        print("Expected mesh names after occupancy filtering:")
        for name in sorted(expected_mesh_names):
            print(f"  {name}")
            
        print("\n=== PHASE 4: CONNECTOR TARGETING SIMULATION ===")
        
        # Test our dynamic targeting logic
        test_dynamic_targeting(expected_mesh_names)
        
    except Exception as e:
        print(f"❌ Failed to simulate mesh names: {e}")

def test_dynamic_targeting(mesh_names):
    """Test the dynamic targeting logic with simulated mesh names."""
    
    def get_dynamic_merge_candidates(connector_number, existing_mesh_names):
        """Copy of the dynamic targeting function for testing."""
        existing_names_lower = [name.lower() for name in existing_mesh_names]
        
        if connector_number == '0':  # Body/torso connectors
            candidates = []
            for name in existing_names_lower:
                if 'body' in name and ('blazer' in name or 'female' in name):
                    candidates.append(name)
            return candidates or ['body_female']
            
        elif connector_number == '1':  # Arm connectors (elbows)
            candidates = []
            for name in existing_names_lower:
                if ('arm1' in name or 'arm2' in name) and ('blazer' in name or 'female' in name):
                    candidates.append(name)
            return candidates or ['l_arm1_female', 'r_arm1_female', 'l_arm2_female', 'r_arm2_female']
            
        elif connector_number == '2':  # Hand/wrist connectors
            candidates = []
            for name in existing_names_lower:
                if 'hand' in name and ('blazer' in name or 'female' in name):
                    candidates.append(name)
            return candidates or ['l_hand_female', 'r_hand_female']
            
        elif connector_number == '3':  # Waist connectors
            candidates = []
            for name in existing_names_lower:
                if ('waist' in name or 'skirt' in name) and ('satsuki' in name or 'female' in name):
                    candidates.append(name)
            return candidates or ['waist_female', 'body_female']
            
        elif connector_number == '4':  # Leg connectors (knees)
            candidates = []
            for name in existing_names_lower:
                if ('leg1' in name or 'leg2' in name) and 'female' in name:
                    candidates.append(name)
            return candidates or ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female']
            
        return []
    
    # Test each connector number
    for connector_num in ['0', '1', '2', '3', '4']:
        targets = get_dynamic_merge_candidates(connector_num, mesh_names)
        print(f"Connector {connector_num} -> targets: {targets}")
        
        # Check if targets actually exist
        targets_lower = [t.lower() for t in targets]
        mesh_names_lower = [m.lower() for m in mesh_names]
        
        actual_matches = []
        for target in targets_lower:
            for mesh in mesh_names_lower:
                if target in mesh:
                    actual_matches.append(mesh)
        
        if actual_matches:
            print(f"  ✅ FOUND: {actual_matches}")
        else:
            print(f"  ❌ NO MATCHES FOUND")
            print(f"     Available meshes with relevant keywords:")
            keywords = ['body', 'arm', 'hand', 'waist', 'leg', 'blazer', 'female']
            for mesh in mesh_names_lower:
                if any(kw in mesh for kw in keywords):
                    print(f"       {mesh}")

if __name__ == "__main__":
    debug_connector_targeting()
    debug_mesh_names_after_occupancy()