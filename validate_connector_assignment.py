#!/usr/bin/env python3
"""
VF3 Connector Assignment Validation System
Validates that dynamic connectors are properly assigned to anatomical groups.
"""

import os
import sys


def validate_connector_assignments(mesh_objects):
    """
    Validate that connectors have been properly assigned to anatomical groups.
    Returns a report of assignment correctness.
    """
    try:
        import bpy
    except ImportError:
        print("🚫 Blender Python API not available")
        return False
    
    print("🔍 VALIDATING CONNECTOR ASSIGNMENTS")
    print("=" * 50)
    
    # Find all anatomical group meshes
    anatomical_meshes = {}
    standalone_connectors = []
    
    for obj in mesh_objects:
        try:
            obj_name = obj.name.lower()
            
            # Identify anatomical groups
            if obj_name.startswith('vf3_'):
                group_name = obj_name.replace('vf3_', '')
                anatomical_meshes[group_name] = obj
                print(f"📦 Found anatomical group: {group_name} ({obj.name})")
            elif 'dynamic_connector' in obj_name:
                standalone_connectors.append(obj)
                print(f"🔌 Found standalone connector: {obj.name}")
                
        except (ReferenceError, AttributeError):
            continue
    
    # Validate assignments
    validation_results = {
        'correctly_assigned': [],
        'incorrectly_assigned': [],
        'bilateral_preserved': [],
        'assignment_errors': []
    }
    
    # Check anatomical group compositions
    for group_name, group_mesh in anatomical_meshes.items():
        print(f"\n🔍 Validating {group_name} group:")
        
        # Analyze vertex groups in the merged mesh
        vertex_groups = [vg.name for vg in group_mesh.vertex_groups]
        print(f"   Vertex groups: {vertex_groups}")
        
        # Check for cross-contamination
        contamination = _check_group_contamination(group_name, vertex_groups)
        if contamination:
            validation_results['incorrectly_assigned'].append({
                'group': group_name,
                'contamination': contamination,
                'mesh': group_mesh.name
            })
            print(f"   ❌ CONTAMINATION DETECTED: {contamination}")
        else:
            validation_results['correctly_assigned'].append({
                'group': group_name,
                'mesh': group_mesh.name,
                'vertex_groups': vertex_groups
            })
            print(f"   ✅ Group composition is correct")
    
    # Check standalone connectors (should be bilateral ones)
    for connector in standalone_connectors:
        print(f"\n🔌 Validating standalone connector: {connector.name}")
        
        # Check if this should be standalone (bilateral)
        source_info = connector.get("connector_source_info", "Unknown")
        vertex_groups = [vg.name for vg in connector.vertex_groups]
        
        is_bilateral = _check_if_bilateral(vertex_groups, source_info)
        if is_bilateral:
            validation_results['bilateral_preserved'].append({
                'connector': connector.name,
                'source': source_info,
                'vertex_groups': vertex_groups
            })
            print(f"   ✅ Correctly preserved as bilateral connector")
        else:
            validation_results['assignment_errors'].append({
                'connector': connector.name,
                'issue': 'Should have been merged with anatomical group',
                'source': source_info,
                'vertex_groups': vertex_groups
            })
            print(f"   ⚠️ Should have been merged with anatomical group")
    
    # Generate validation report
    _print_validation_report(validation_results)
    
    # Return overall validation status
    has_errors = (len(validation_results['incorrectly_assigned']) > 0 or 
                  len(validation_results['assignment_errors']) > 0)
    
    return not has_errors


def _check_group_contamination(group_name, vertex_groups):
    """Check if anatomical group contains bones from other anatomical regions."""
    
    # Define expected bones for each anatomical group
    expected_bones = {
        'body': ['body', 'waist', 'l_breast', 'r_breast', 'skirt_f', 'skirt_r'],
        'leftarm': ['l_arm1', 'l_arm2', 'l_hand'],
        'rightarm': ['r_arm1', 'r_arm2', 'r_hand'],
        'leftleg': ['l_leg1', 'l_leg2', 'l_foot'],
        'rightleg': ['r_leg1', 'r_leg2', 'r_foot'],
        'head': ['head', 'neck']
    }
    
    # Check for forbidden bones (cross-contamination)
    forbidden_patterns = {
        'body': ['l_arm', 'r_arm', 'l_hand', 'r_hand', 'l_leg', 'r_leg', 'l_foot', 'r_foot'],
        'leftarm': ['r_arm', 'r_hand', 'body', 'waist', 'breast', 'leg', 'foot', 'head'],
        'rightarm': ['l_arm', 'l_hand', 'body', 'waist', 'breast', 'leg', 'foot', 'head'],
        'leftleg': ['r_leg', 'r_foot', 'body', 'waist', 'breast', 'arm', 'hand', 'head'],
        'rightleg': ['l_leg', 'l_foot', 'body', 'waist', 'breast', 'arm', 'hand', 'head'],
        'head': ['body', 'waist', 'breast', 'arm', 'hand', 'leg', 'foot']
    }
    
    contamination = []
    forbidden = forbidden_patterns.get(group_name, [])
    
    for vg in vertex_groups:
        for forbidden_pattern in forbidden:
            if forbidden_pattern in vg.lower():
                contamination.append(f"{vg} (contains {forbidden_pattern})")
                break
    
    return contamination


def _check_if_bilateral(vertex_groups, source_info):
    """Check if connector should be bilateral based on vertex groups and source."""
    
    # Check vertex groups for bilateral indicators
    has_left = any('l_' in vg for vg in vertex_groups)
    has_right = any('r_' in vg for vg in vertex_groups)
    
    if has_left and has_right:
        return True
    
    # Check source info for bilateral indicators
    if source_info and source_info != "Unknown":
        source_lower = str(source_info).lower()
        bilateral_sources = ['arms', 'legs', 'hands', 'foots']
        
        for bilateral_source in bilateral_sources:
            if bilateral_source in source_lower:
                return True
    
    return False


def _print_validation_report(results):
    """Print a comprehensive validation report."""
    
    print("\n" + "=" * 60)
    print("🔍 CONNECTOR ASSIGNMENT VALIDATION REPORT")
    print("=" * 60)
    
    # Correctly assigned groups
    print(f"\n✅ CORRECTLY ASSIGNED GROUPS ({len(results['correctly_assigned'])}):")
    for assignment in results['correctly_assigned']:
        print(f"   {assignment['group']}: {len(assignment['vertex_groups'])} bone types")
    
    # Contamination issues
    print(f"\n❌ CONTAMINATION ISSUES ({len(results['incorrectly_assigned'])}):")
    for issue in results['incorrectly_assigned']:
        print(f"   {issue['group']}: {issue['contamination']}")
    
    # Bilateral connectors preserved
    print(f"\n🌐 BILATERAL CONNECTORS PRESERVED ({len(results['bilateral_preserved'])}):")
    for bilateral in results['bilateral_preserved']:
        print(f"   {bilateral['connector']}: {len(bilateral['vertex_groups'])} bone types")
    
    # Assignment errors
    print(f"\n⚠️ ASSIGNMENT ERRORS ({len(results['assignment_errors'])}):")
    for error in results['assignment_errors']:
        print(f"   {error['connector']}: {error['issue']}")
    
    # Summary
    total_issues = len(results['incorrectly_assigned']) + len(results['assignment_errors'])
    total_correct = len(results['correctly_assigned']) + len(results['bilateral_preserved'])
    
    print(f"\n📊 SUMMARY:")
    print(f"   Correct assignments: {total_correct}")
    print(f"   Issues found: {total_issues}")
    
    if total_issues == 0:
        print(f"   🎉 ALL CONNECTOR ASSIGNMENTS ARE CORRECT!")
    else:
        print(f"   ⚠️ {total_issues} issues need to be addressed")


def validate_export_success():
    """Validate that the export process completed successfully."""
    try:
        import bpy
    except ImportError:
        return False
    
    # Check that we have the expected anatomical groups
    scene_objects = list(bpy.context.scene.objects)
    mesh_objects = [obj for obj in scene_objects if obj.type == 'MESH']
    
    expected_groups = ['VF3_Body', 'VF3_LeftArm', 'VF3_RightArm', 'VF3_Head']
    found_groups = []
    
    for obj in mesh_objects:
        if obj.name in expected_groups:
            found_groups.append(obj.name)
    
    print(f"🔍 Expected groups: {expected_groups}")
    print(f"🔍 Found groups: {found_groups}")
    
    # Basic validation
    has_body = 'VF3_Body' in found_groups
    has_arms = 'VF3_LeftArm' in found_groups or 'VF3_RightArm' in found_groups
    has_head = 'VF3_Head' in found_groups
    
    if has_body and has_arms and has_head:
        print("✅ Export validation: Basic anatomical groups found")
        
        # Validate assignments
        return validate_connector_assignments(mesh_objects)
    else:
        print("❌ Export validation: Missing essential anatomical groups")
        return False


if __name__ == "__main__":
    # Can be run from Blender to validate current scene
    success = validate_export_success()
    if success:
        print("🎉 Validation passed!")
        sys.exit(0)
    else:
        print("❌ Validation failed!")
        sys.exit(1)