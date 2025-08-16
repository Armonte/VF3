#!/usr/bin/env python3
"""
Debug script to trace connector merging logic and identify why connectors are merging with wrong meshes.
"""

import sys
import os
sys.path.append('/mnt/c/dev/loot/VF3')

def debug_connector_merging():
    """Debug the connector merging logic step by step."""
    print("=== CONNECTOR MERGING DEBUG ===")
    
    # Simulate the mesh names that exist after occupancy filtering
    simulated_mesh_names = [
        'head_satsuki.head',
        'body_satsuki.blazer',
        'l_breast_satsuki.blazer_lb', 
        'r_breast_satsuki.blazer_rb',
        'l_arm1_satsuki.l_blazer1',
        'l_arm2_satsuki.l_blazer2', 
        'l_hand_satsuki.l_blazer3',
        'r_arm1_satsuki.r_blazer1',
        'r_arm2_satsuki.r_blazer2',
        'r_hand_satsuki.r_blazer3',
        'waist_satsuki.blazer2',
        'l_hand_female.l_hand',
        'r_hand_female.r_hand', 
        'waist_female.waist',
        'waist_satsuki.skirta',
        'skirt_f_satsuki.skirta_f',
        'skirt_r_satsuki.skirta_r',
        'l_leg1_female.l_leg1',
        'l_leg2_female.l_leg2',
        'r_leg1_female.r_leg1',
        'r_leg2_female.r_leg2',
        'l_leg2_satsuki.l_shoea2',
        'l_foot_satsuki.l_shoea',
        'r_leg2_satsuki.r_shoea2',
        'r_foot_satsuki.r_shoea'
    ]
    
    print(f"Simulated mesh names: {len(simulated_mesh_names)} meshes")
    for name in sorted(simulated_mesh_names):
        print(f"  {name}")
    
    print("\n=== TESTING CONNECTOR 1 (WRIST) TARGETING ===")
    
    # Test the dynamic targeting for connector 1 (wrist)
    def get_dynamic_merge_candidates(connector_number, existing_mesh_names):
        """Copy of the targeting function for testing."""
        existing_names_lower = [name.lower() for name in existing_mesh_names]
        
        if connector_number == '1':  # WRIST connectors 
            # Prefer blazer hands, fallback to female hands
            candidates = []
            for name in existing_names_lower:
                if 'hand' in name and ('blazer' in name or 'female' in name):
                    candidates.append(name)
            return candidates or ['l_hand_female', 'r_hand_female']
        
        return []
    
    connector_1_targets = get_dynamic_merge_candidates('1', simulated_mesh_names)
    print(f"Connector 1 targets: {connector_1_targets}")
    
    # Simulate the mesh matching logic
    target_meshes = []
    for mesh_name in simulated_mesh_names:
        mesh_name_lower = mesh_name.lower()
        for candidate in connector_1_targets:
            if candidate.lower() in mesh_name_lower:
                target_meshes.append(mesh_name)
                break
    
    print(f"Matched target meshes: {target_meshes}")
    
    # Check if fallback logic would trigger
    if not target_meshes:
        print("❌ NO TARGET MESHES FOUND - FALLBACK TO BODY WOULD TRIGGER!")
        # Look for body mesh
        for mesh_name in simulated_mesh_names:
            mesh_name_lower = mesh_name.lower()
            if 'body_female.body' in mesh_name_lower or 'body_satsuki.blazer' in mesh_name_lower:
                print(f"  Fallback would merge with: {mesh_name}")
                break
    else:
        print(f"✅ Target meshes found: {target_meshes}")
    
    print("\n=== TESTING ALL CONNECTORS ===")
    
    # Test all connector targeting
    def test_all_connectors():
        for connector_num in ['0', '1', '2', '3', '4']:
            print(f"\n--- Connector {connector_num} ---")
            
            def get_full_targeting(connector_number, existing_mesh_names):
                existing_names_lower = [name.lower() for name in existing_mesh_names]
                
                if connector_number == '0':  # Body/torso connectors
                    candidates = []
                    for name in existing_names_lower:
                        if 'body' in name and ('blazer' in name or 'female' in name):
                            candidates.append(name)
                    return candidates or ['body_female']
                    
                elif connector_number == '1':  # WRIST connectors
                    candidates = []
                    for name in existing_names_lower:
                        if 'hand' in name and ('blazer' in name or 'female' in name):
                            candidates.append(name)
                    return candidates or ['l_hand_female', 'r_hand_female']
                    
                elif connector_number == '2':  # SKIRT/WAIST connectors
                    candidates = []
                    for name in existing_names_lower:
                        if ('waist' in name or 'skirt' in name) and ('satsuki' in name or 'female' in name):
                            candidates.append(name)
                    return candidates or ['waist_female', 'body_female']
                    
                elif connector_number == '3':  # KNEE connectors
                    candidates = []
                    for name in existing_names_lower:
                        if ('leg1' in name or 'leg2' in name) and 'female' in name:
                            candidates.append(name)
                    return candidates or ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female']
                    
                elif connector_number == '4':  # ANKLE connectors
                    candidates = []
                    for name in existing_names_lower:
                        if ('foot' in name or 'shoe' in name) and ('satsuki' in name or 'female' in name):
                            candidates.append(name)
                    return candidates or ['l_foot_female', 'r_foot_female', 'l_leg2_female', 'r_leg2_female']
                    
                return []
            
            targets = get_full_targeting(connector_num, simulated_mesh_names)
            print(f"  Targets: {targets}")
            
            # Check matches
            matched = []
            for mesh_name in simulated_mesh_names:
                mesh_name_lower = mesh_name.lower()
                for candidate in targets:
                    if candidate.lower() in mesh_name_lower:
                        matched.append(mesh_name)
                        break
            
            if matched:
                print(f"  ✅ Matched: {matched}")
            else:
                print(f"  ❌ NO MATCHES - would fallback to body!")
    
    test_all_connectors()
    
    print("\n=== WAIST MESH ANALYSIS ===")
    
    # Check waist-related meshes specifically
    waist_meshes = [name for name in simulated_mesh_names if 'waist' in name.lower()]
    print(f"Waist-related meshes: {waist_meshes}")
    
    # Check what female.waist should contain
    print("\nExpected waist components from occupancy analysis:")
    print("  - waist_female.waist (underwear/panties)")
    print("  - waist_satsuki.blazer2 (blazer waist part)")  
    print("  - waist_satsuki.skirta (main skirt)")
    print("  - skirt_f_satsuki.skirta_f (front skirt part)")
    print("  - skirt_r_satsuki.skirta_r (rear skirt part)")
    
    missing_waist_parts = []
    expected_parts = ['waist_female.waist', 'waist_satsuki.blazer2', 'waist_satsuki.skirta', 'skirt_f_satsuki.skirta_f', 'skirt_r_satsuki.skirta_r']
    for part in expected_parts:
        if part not in simulated_mesh_names:
            missing_waist_parts.append(part)
    
    if missing_waist_parts:
        print(f"❌ Missing waist parts: {missing_waist_parts}")
    else:
        print("✅ All expected waist parts present")

if __name__ == "__main__":
    debug_connector_merging()