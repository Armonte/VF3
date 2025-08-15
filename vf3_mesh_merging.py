"""
VF3 Mesh Merging - Extracted from working vf3_blender_exporter.py
Handles merging of body parts to create seamless character models.
"""

import os
import sys
from typing import List, Dict, Any


def _merge_breast_meshes_with_body(mesh_objects):
    """
    Merge breast meshes with the body mesh to create a unified torso mesh.
    This eliminates seams between breasts and body.
    """
    try:
        import bpy
    except ImportError:
        return
    
    # Find body and breast meshes
    body_mesh = None
    breast_meshes = []
    
    for mesh_obj in mesh_objects:
        if hasattr(mesh_obj, 'name'):
            mesh_name = mesh_obj.name.lower()
            if 'body_female' in mesh_name:
                body_mesh = mesh_obj
            elif any(breast in mesh_name for breast in ['l_breast_female', 'r_breast_female', 'breast']):
                breast_meshes.append(mesh_obj)
    
    if not body_mesh:
        print("  No body mesh found for breast merging")
        return
    
    if not breast_meshes:
        print("  No breast meshes found for merging")
        return
    
    print(f"  Merging {len(breast_meshes)} breast meshes with body...")
    
    # Select body mesh as active, breast meshes as selected
    bpy.context.view_layer.objects.active = body_mesh
    bpy.ops.object.select_all(action='DESELECT')
    body_mesh.select_set(True)
    for breast_mesh in breast_meshes:
        breast_mesh.select_set(True)
    
    try:
        # Join breast meshes into body
        bpy.ops.object.join()
        print("  ✅ Successfully merged breast meshes with body")
    except Exception as e:
        print(f"  ❌ Failed to merge breast meshes: {e}")


def _merge_feet_meshes_with_legs(mesh_objects):
    """Merge foot meshes with leg2 meshes."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        foot_mesh = None
        leg2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if f'{side}_foot_female' in mesh_name:
                    foot_mesh = mesh_obj
                elif f'{side}_leg2_female' in mesh_name:
                    leg2_mesh = mesh_obj
            except (ReferenceError, AttributeError):
                continue
        
        if foot_mesh and leg2_mesh:
            print(f"  Merging {foot_mesh.name} with {leg2_mesh.name}...")
            bpy.context.view_layer.objects.active = leg2_mesh
            bpy.ops.object.select_all(action='DESELECT')
            leg2_mesh.select_set(True)
            foot_mesh.select_set(True)
            
            try:
                bpy.ops.object.join()
                print(f"  ✅ Successfully merged {side} foot with leg2")
            except Exception as e:
                print(f"  ❌ Failed to merge {side} foot: {e}")


def _merge_lower_legs_meshes_with_thighs(mesh_objects):
    """Merge leg2 meshes with leg1 meshes."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        leg1_mesh = None
        leg2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if f'{side}_leg1_female' in mesh_name:
                    leg1_mesh = mesh_obj
                elif f'{side}_leg2_female' in mesh_name:
                    leg2_mesh = mesh_obj
            except (ReferenceError, AttributeError):
                continue
        
        if leg1_mesh and leg2_mesh:
            print(f"  Merging {leg2_mesh.name} with {leg1_mesh.name}...")
            bpy.context.view_layer.objects.active = leg1_mesh
            bpy.ops.object.select_all(action='DESELECT')
            leg1_mesh.select_set(True)
            leg2_mesh.select_set(True)
            
            try:
                bpy.ops.object.join()
                print(f"  ✅ Successfully merged {side} leg2 with leg1")
            except Exception as e:
                print(f"  ❌ Failed to merge {side} leg2: {e}")


def _merge_legs_meshes_with_body(mesh_objects):
    """Merge complete leg assemblies with body."""
    try:
        import bpy
    except ImportError:
        return
    
    body_mesh = None
    leg_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            mesh_name = mesh_obj.name.lower()
            if 'body_female' in mesh_name:
                body_mesh = mesh_obj
            elif any(leg in mesh_name for leg in ['l_leg1_female', 'r_leg1_female']):
                leg_meshes.append(mesh_obj)
        except (ReferenceError, AttributeError):
            continue
    
    if not body_mesh or not leg_meshes:
        print("  No body or leg meshes found for merging")
        return
    
    print(f"  Merging {len(leg_meshes)} leg assemblies with body...")
    
    bpy.context.view_layer.objects.active = body_mesh
    bpy.ops.object.select_all(action='DESELECT')
    body_mesh.select_set(True)
    for leg_mesh in leg_meshes:
        leg_mesh.select_set(True)
    
    try:
        bpy.ops.object.join()
        print("  ✅ Successfully merged legs with body")
    except Exception as e:
        print(f"  ❌ Failed to merge legs: {e}")


def _merge_forearms_meshes_with_arms(mesh_objects):
    """Merge forearm meshes with upper arm meshes."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        arm1_mesh = None
        arm2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if f'{side}_arm1_female' in mesh_name:
                    arm1_mesh = mesh_obj
                elif f'{side}_arm2_female' in mesh_name:
                    arm2_mesh = mesh_obj
            except (ReferenceError, AttributeError):
                continue
        
        if arm1_mesh and arm2_mesh:
            print(f"  Merging {arm2_mesh.name} with {arm1_mesh.name}...")
            bpy.context.view_layer.objects.active = arm1_mesh
            bpy.ops.object.select_all(action='DESELECT')
            arm1_mesh.select_set(True)
            arm2_mesh.select_set(True)
            
            try:
                bpy.ops.object.join()
                print(f"  ✅ Successfully merged {side} forearm with arm")
            except Exception as e:
                print(f"  ❌ Failed to merge {side} forearm: {e}")


def _merge_hands_meshes_with_arms(mesh_objects):
    """Merge hand meshes with arm assemblies."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        arm_mesh = None
        hand_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if f'{side}_arm1_female' in mesh_name:
                    arm_mesh = mesh_obj
                elif f'{side}_hand_female' in mesh_name:
                    hand_mesh = mesh_obj
            except (ReferenceError, AttributeError):
                continue
        
        if arm_mesh and hand_mesh:
            print(f"  Merging {hand_mesh.name} with {arm_mesh.name}...")
            bpy.context.view_layer.objects.active = arm_mesh
            bpy.ops.object.select_all(action='DESELECT')
            arm_mesh.select_set(True)
            hand_mesh.select_set(True)
            
            try:
                bpy.ops.object.join()
                print(f"  ✅ Successfully merged {side} hand with arm")
            except Exception as e:
                print(f"  ❌ Failed to merge {side} hand: {e}")


def _merge_arms_meshes_with_body(mesh_objects):
    """Merge complete arm assemblies with body."""
    try:
        import bpy
    except ImportError:
        return
    
    body_mesh = None
    arm_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            mesh_name = mesh_obj.name.lower()
            if 'body_female' in mesh_name:
                body_mesh = mesh_obj
            elif any(arm in mesh_name for arm in ['l_arm1_female', 'r_arm1_female']):
                arm_meshes.append(mesh_obj)
        except (ReferenceError, AttributeError):
            continue
    
    if not body_mesh or not arm_meshes:
        print("  No body or arm meshes found for merging")
        return
    
    print(f"  Merging {len(arm_meshes)} arm assemblies with body...")
    
    bpy.context.view_layer.objects.active = body_mesh
    bpy.ops.object.select_all(action='DESELECT')
    body_mesh.select_set(True)
    for arm_mesh in arm_meshes:
        arm_mesh.select_set(True)
    
    try:
        bpy.ops.object.join()
        print("  ✅ Successfully merged arms with body")
    except Exception as e:
        print(f"  ❌ Failed to merge arms: {e}")


def _try_merge_connector_with_body_mesh(connector_obj, mesh_objects, vertex_bone_names):
    """
    Try to merge a DynamicVisual connector with an appropriate body mesh based on its bone assignments.
    This eliminates separate mesh instances and creates seamless connections.
    Returns: (success, merged_mesh_names) - success bool and list of mesh names that were merged and removed
    """
    try:
        import bpy
        import bmesh
        from mathutils import Vector
    except ImportError:
        return False, []
    
    if not connector_obj or not mesh_objects:
        return False, []
    
    # Determine which body mesh this connector should merge with based on bone names
    target_mesh = None
    connector_name = connector_obj.name.lower()
    
    # Define merging candidates based on connector number (determined from DynamicVisual processing order)
    # Order is based on the occupancy slot processing: body, arms, hands, waist, legs, foots
    merge_candidates_by_number = {
        '0': ['body_female'],  # Body/torso connectors (breasts already merged with body)
        '1': ['l_arm1_female', 'r_arm1_female', 'l_arm2_female', 'r_arm2_female'],  # Arm connectors
        '2': ['l_hand_female', 'r_hand_female'],  # Hand/wrist connectors  
        '3': ['waist_female', 'body_female'],  # Waist connectors
        '4': ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female'],  # Leg connectors (hips/knees/thighs)
        '5': ['l_foot_female', 'r_foot_female', 'l_leg2_female', 'r_leg2_female']  # Foot/ankle connectors
    }
    
    # Extract connector number from name (e.g., "dynamic_connector_0_vf3mesh" -> "0")
    target_categories = []
    import re
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    if match:
        connector_number = match.group(1)
        target_categories = merge_candidates_by_number.get(connector_number, [])
        print(f"      Connector {connector_number} -> merge targets: {target_categories}")
    else:
        # Fallback to old logic for non-numbered connectors
        merge_candidates = {
            'breast': ['l_breast_female', 'r_breast_female', 'breast'],
            'shoulder': ['l_arm1_female', 'r_arm1_female', 'torso'],  
            'elbow': ['l_arm1_female', 'r_arm1_female', 'l_arm2_female', 'r_arm2_female'],
            'wrist': ['l_arm2_female', 'r_arm2_female', 'l_hand_female', 'r_hand_female'],
            'hip': ['waist_female', 'l_leg1_female', 'r_leg1_female'],
            'knee': ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female'],
            'ankle': ['l_leg2_female', 'r_leg2_female', 'l_foot_female', 'r_foot_female'],
            'thigh': ['l_leg1_female', 'r_leg1_female', 'waist_female'],
            'torso': ['body_female', 'waist_female']
        }
        
        for category, candidates in merge_candidates.items():
            if category in connector_name:
                target_categories = candidates
                break
    
    if not target_categories:
        print(f"      No merge candidates found for connector: {connector_name}")
        return False, []
    
    # Find all target mesh objects that match the categories
    target_meshes = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            mesh_name_lower = mesh_obj.name.lower()
            for candidate in target_categories:
                if candidate.lower() in mesh_name_lower:
                    target_meshes.append(mesh_obj)
                    break
        except (ReferenceError, AttributeError):
            # Object has been deleted, skip it
            continue
    
    if not target_meshes:
        # If no specific targets found, try to merge with the unified body mesh
        # This handles cases where limbs have been merged into the body
        for mesh_obj in mesh_objects:
            try:
                mesh_name_lower = mesh_obj.name.lower()
                if 'body_female.body' in mesh_name_lower:
                    target_meshes.append(mesh_obj)
                    print(f"      Fallback: merging connector {connector_name} with unified body mesh")
                    break
            except (ReferenceError, AttributeError):
                continue
        
        if not target_meshes:
            print(f"      No suitable body mesh found to merge connector: {connector_name}")
            return False, []
    
    # Perform the actual mesh merging
    try:
        # For breast connectors (connector 0), merge with all breast meshes first, then merge everything
        if len(target_meshes) > 1:
            print(f"      Found {len(target_meshes)} target meshes: {[m.name for m in target_meshes]}")
            
            # Collect names of meshes that will be merged (all except primary target) BEFORE merging
            primary_target = target_meshes[0]  # Use first mesh as primary target
            merged_names = [m.name for m in target_meshes[1:]]  # Exclude primary target which still exists
            
            # Select all target meshes and the connector
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select all meshes to be merged
            for mesh in target_meshes:
                mesh.select_set(True)
            connector_obj.select_set(True)
            
            # Set primary target as active object
            bpy.context.view_layer.objects.active = primary_target
            
            # Join all selected meshes into the primary target
            bpy.ops.object.join()
            
            # Clean up seams
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge very close vertices
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"      ✅ Successfully merged connector {connector_name} with {len(target_meshes)} meshes into {primary_target.name}")
            return True, merged_names
        else:
            # Single target mesh - use original logic
            target_mesh = target_meshes[0]
            
            # Select both meshes
            bpy.context.view_layer.objects.active = target_mesh
            bpy.ops.object.select_all(action='DESELECT')
            target_mesh.select_set(True)
            connector_obj.select_set(True)
            
            # Join the meshes (connector into target)
            bpy.context.view_layer.objects.active = target_mesh
            bpy.ops.object.join()
            
            # Clean up any duplicate vertices at the seam
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge very close vertices
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"      ✅ Successfully merged connector {connector_name} with {target_mesh.name}")
            return True, []  # No additional meshes were removed in single target merge
        
    except Exception as e:
        print(f"      ❌ Failed to merge connector {connector_name}: {e}")
        return False, []