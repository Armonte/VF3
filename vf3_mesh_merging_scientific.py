"""
VF3 Scientific Mesh Merging System
Simple principle: Only merge meshes that belong to the same anatomical group.
Zero contamination tolerance.
"""

import os
import sys
from typing import List, Dict, Any


def create_anatomical_mesh_groups_scientific(mesh_objects):
    """
    Scientific approach to anatomical mesh grouping:
    1. Split all meshes by bone assignments
    2. Merge only same-group mesh parts
    3. Validate zero contamination
    """
    try:
        import bpy
    except ImportError:
        return
    
    print("🔬 SCIENTIFIC ANATOMICAL GROUPING: Starting bone-based analysis")
    
    # Import our scientific splitting system
    from vf3_bone_based_splitting import split_all_meshes_by_bones
    
    # Step 1: Split all meshes (including connectors) by bone assignments
    anatomical_groups = split_all_meshes_by_bones(mesh_objects)
    
    # Step 2: Merge each anatomical group separately
    print("\n🔬 SCIENTIFIC MERGING: Merging same-group mesh parts")
    
    final_meshes = []
    
    for group_name, mesh_parts in anatomical_groups.items():
        if not mesh_parts:
            continue
            
        # Skip empty bridge_connectors group (bridge parts are now distributed to anatomical groups)
        if group_name == 'bridge_connectors':
            continue
            
        print(f"\n  🔧 Merging {group_name} group: {len(mesh_parts)} parts")
        
        if len(mesh_parts) == 1:
            # Single mesh - just rename it and add armature binding
            mesh_parts[0].name = f"VF3_{group_name.title()}"
            add_armature_modifier_to_merged_group(mesh_parts[0])
            final_meshes.append(mesh_parts[0])
            print(f"    ✅ Renamed single mesh to VF3_{group_name.title()}")
        else:
            # Multiple mesh parts - merge them scientifically
            merged_mesh = merge_same_group_meshes(mesh_parts, group_name)
            if merged_mesh:
                final_meshes.append(merged_mesh)
    
    # Step 3: Final validation
    print("\n🔬 FINAL VALIDATION:")
    validate_final_anatomical_groups(final_meshes)
    
    print("🎉 SCIENTIFIC ANATOMICAL GROUPING COMPLETE!")
    return final_meshes


def apply_z_fighting_prevention(mesh_parts: List, group_name: str):
    """
    Apply Z-fighting prevention by offsetting overlapping mesh layers.
    Clothing should be slightly forward of skin to prevent Z-fighting.
    """
    try:
        import bpy
        from mathutils import Vector
    except ImportError:
        return
    
    if group_name not in ['body', 'left_arm', 'right_arm', 'left_leg', 'right_leg']:
        return  # Only apply to body parts that might have overlapping layers
    
    print(f"        🔧 Applying Z-fighting prevention to {group_name} parts")
    
    # Define layer priorities (higher number = more forward)
    layer_priorities = {
        'female': 0,      # Base skin layer (furthest back)
        'stocking': 1,    # Stockings on top of skin
        'maid': 2,        # Maid outfit on top of everything
        'default': 1      # Default priority for unknown items
    }
    
    # Sort mesh parts by priority
    prioritized_parts = []
    for mesh_part in mesh_parts:
        priority = layer_priorities.get('default', 1)
        
        # Determine priority based on mesh name
        mesh_name_lower = mesh_part.name.lower()
        for layer_type, layer_priority in layer_priorities.items():
            if layer_type in mesh_name_lower:
                priority = layer_priority
                break
        
        prioritized_parts.append((mesh_part, priority))
    
    # Sort by priority (lowest first)
    prioritized_parts.sort(key=lambda x: x[1])
    
    # Apply offset based on priority
    offset_distance = 0.001  # Small offset to prevent Z-fighting
    
    for i, (mesh_part, priority) in enumerate(prioritized_parts):
        if priority > 0:  # Don't offset base skin layer
            offset_vector = Vector((0, 0, priority * offset_distance))
            
            # Apply offset to mesh vertices
            bpy.context.view_layer.objects.active = mesh_part
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.transform.translate(value=offset_vector)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"          Applied {offset_vector} offset to {mesh_part.name} (priority {priority})")


def merge_same_group_meshes(mesh_parts: List, group_name: str):
    """
    Merge mesh parts that belong to the same anatomical group.
    This is safe because all parts contain only compatible bones.
    """
    try:
        import bpy
    except ImportError:
        return None
    
    if not mesh_parts:
        return None
    
    print(f"    🔧 Merging {len(mesh_parts)} {group_name} parts:")
    
    # DISABLED: Z-fighting prevention - was causing mesh corruption and "black texture" issues
    # apply_z_fighting_prevention(mesh_parts, group_name)
    
    # Log what we're merging
    for i, mesh_part in enumerate(mesh_parts):
        try:
            bones = [vg.name for vg in mesh_part.vertex_groups]
            print(f"      Part {i+1}: {mesh_part.name} (bones: {bones})")
        except (ReferenceError, AttributeError):
            print(f"      Part {i+1}: Invalid mesh object")
            continue
    
    # Select all mesh parts for merging
    bpy.ops.object.select_all(action='DESELECT')
    
    valid_parts = []
    for mesh_part in mesh_parts:
        try:
            mesh_part.select_set(True)
            valid_parts.append(mesh_part)
        except (ReferenceError, AttributeError):
            print(f"        ⚠️ Skipping invalid mesh part")
            continue
    
    if not valid_parts:
        print(f"        ❌ No valid mesh parts to merge")
        return None
    
    # Set the first valid part as active
    bpy.context.view_layer.objects.active = valid_parts[0]
    
    try:
        # Merge all selected meshes
        bpy.ops.object.join()
        
        # Get the merged result
        merged_mesh = bpy.context.active_object
        merged_mesh.name = f"VF3_{group_name.title()}"
        
        # Clean up the merged mesh
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge overlapping vertices
        
        # CRITICAL FIX: Apply smooth shading after merging (lost during join operation)
        bpy.ops.mesh.faces_shade_smooth()
        
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"        🎨 Applied smooth shading to merged {group_name}")
        
        # Log the merge result
        final_bones = [vg.name for vg in merged_mesh.vertex_groups]
        print(f"        ✅ Merged into {merged_mesh.name}")
        print(f"        📦 Final bones: {final_bones}")
        
        # CRITICAL FIX: Add armature modifier to merged anatomical groups
        add_armature_modifier_to_merged_group(merged_mesh)
        
        # Validate the merged result
        validate_merged_group(merged_mesh, group_name)
        
        return merged_mesh
        
    except Exception as e:
        print(f"        ❌ Failed to merge {group_name} parts: {e}")
        return None


def add_armature_modifier_to_merged_group(merged_mesh):
    """
    Add armature modifier to merged anatomical group so it's bound to VF3_Armature.
    """
    try:
        import bpy
    except ImportError:
        return
    
    # Find the VF3_Armature
    armature_obj = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE' and 'VF3' in obj.name:
            armature_obj = obj
            break
    
    if not armature_obj:
        print(f"        ❌ Could not find VF3_Armature for {merged_mesh.name}")
        return
    
    # Add armature modifier
    armature_modifier = merged_mesh.modifiers.new(name="Armature", type='ARMATURE')
    armature_modifier.object = armature_obj
    armature_modifier.use_vertex_groups = True
    
    print(f"        🔗 Added armature modifier to {merged_mesh.name} -> {armature_obj.name}")


def validate_merged_group(merged_mesh, expected_group: str):
    """
    Validate that a merged anatomical group contains only appropriate bones.
    """
    try:
        import bpy
    except ImportError:
        return
    
    bones = [vg.name for vg in merged_mesh.vertex_groups]
    
    print(f"    🔍 CONTAMINATION CHECK for {expected_group}:")
    
    contamination_errors = []
    
    if expected_group == 'left_arm':
        # Left arm should only have left arm bones
        forbidden_bones = [bone for bone in bones if bone.startswith('r_') or 'right' in bone.lower()]
        if forbidden_bones:
            contamination_errors.append(f"Right bones in left_arm: {forbidden_bones}")
            
    elif expected_group == 'right_arm':
        # Right arm should only have right arm bones  
        forbidden_bones = [bone for bone in bones if bone.startswith('l_') or 'left' in bone.lower()]
        if forbidden_bones:
            contamination_errors.append(f"Left bones in right_arm: {forbidden_bones}")
            
    elif expected_group == 'left_leg':
        # Left leg should only have left leg bones
        forbidden_bones = [bone for bone in bones if bone.startswith('r_') or 'right' in bone.lower()]
        if forbidden_bones:
            contamination_errors.append(f"Right bones in left_leg: {forbidden_bones}")
            
    elif expected_group == 'right_leg':
        # Right leg should only have right leg bones
        forbidden_bones = [bone for bone in bones if bone.startswith('l_') or 'left' in bone.lower()]
        if forbidden_bones:
            contamination_errors.append(f"Left bones in right_leg: {forbidden_bones}")
    
    # Body and head can have mixed bones, so no validation needed
    
    if contamination_errors:
        print(f"        🚨 CONTAMINATION DETECTED:")
        for error in contamination_errors:
            print(f"          ❌ {error}")
        print(f"        🚨 THIS SHOULD NEVER HAPPEN WITH SCIENTIFIC SPLITTING!")
    else:
        print(f"        ✅ No contamination detected in {expected_group}")


def validate_final_anatomical_groups(final_meshes):
    """
    Final validation of all anatomical groups for contamination.
    """
    print("  🔍 FINAL CONTAMINATION ANALYSIS:")
    
    total_contamination = 0
    
    for mesh in final_meshes:
        try:
            group_name = mesh.name.replace('VF3_', '').lower()
            bones = [vg.name for vg in mesh.vertex_groups]
            
            print(f"    {mesh.name}: {len(bones)} bones")
            
            # Check for cross-contamination
            if 'leftarm' in group_name or 'left_arm' in group_name:
                right_bones = [bone for bone in bones if bone.startswith('r_')]
                if right_bones:
                    print(f"      🚨 LEFT ARM contaminated with RIGHT bones: {right_bones}")
                    total_contamination += len(right_bones)
                else:
                    print(f"      ✅ Left arm clean")
                    
            elif 'rightarm' in group_name or 'right_arm' in group_name:
                left_bones = [bone for bone in bones if bone.startswith('l_')]
                if left_bones:
                    print(f"      🚨 RIGHT ARM contaminated with LEFT bones: {left_bones}")
                    total_contamination += len(left_bones)
                else:
                    print(f"      ✅ Right arm clean")
                    
            elif 'leftleg' in group_name or 'left_leg' in group_name:
                right_bones = [bone for bone in bones if bone.startswith('r_')]
                if right_bones:
                    print(f"      🚨 LEFT LEG contaminated with RIGHT bones: {right_bones}")
                    total_contamination += len(right_bones)
                else:
                    print(f"      ✅ Left leg clean")
                    
            elif 'rightleg' in group_name or 'right_leg' in group_name:
                left_bones = [bone for bone in bones if bone.startswith('l_')]
                if left_bones:
                    print(f"      🚨 RIGHT LEG contaminated with LEFT bones: {left_bones}")
                    total_contamination += len(left_bones)
                else:
                    print(f"      ✅ Right leg clean")
                    
            elif 'skirt' in group_name:
                # Skirt should only have skirt bones, not body/arm/leg bones
                invalid_bones = [bone for bone in bones if not (bone.startswith('skirt_') or bone in ['waist'])]
                if invalid_bones:
                    print(f"      🚨 SKIRT contaminated with non-skirt bones: {invalid_bones}")
                    total_contamination += len(invalid_bones)
                else:
                    print(f"      ✅ Skirt clean")
            else:
                print(f"      ℹ️ {group_name} (neutral group - no contamination check)")
                
        except (ReferenceError, AttributeError):
            print(f"    ❌ Invalid mesh: {mesh}")
    
    if total_contamination == 0:
        print(f"  🎉 PERFECT: ZERO contamination detected across all groups!")
    else:
        print(f"  🚨 TOTAL CONTAMINATION: {total_contamination} misplaced bones")
        print(f"  🚨 THIS INDICATES A BUG IN THE SCIENTIFIC SPLITTING SYSTEM!")


# For backwards compatibility, alias the main function
def _create_anatomical_mesh_groups(mesh_objects):
    """Backwards compatibility wrapper for the scientific grouping system."""
    return create_anatomical_mesh_groups_scientific(mesh_objects)