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
    
    # Find body and breast meshes using bone-based detection (costume-agnostic)
    body_mesh = None
    breast_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            # Look for body mesh - check if bound to 'body' bone by checking vertex groups
            if any(vg.name == 'body' for vg in mesh_obj.vertex_groups):
                body_mesh = mesh_obj
                print(f"  Found body mesh: {mesh_obj.name}")
            # Look for breast meshes - check for breast bone groups
            elif any(vg.name in ['l_breast', 'r_breast'] for vg in mesh_obj.vertex_groups):
                breast_meshes.append(mesh_obj)
                print(f"  Found breast mesh: {mesh_obj.name}")
        except (ReferenceError, AttributeError):
            continue
    
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
    """Merge foot meshes with leg2 meshes using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        foot_mesh = None
        leg2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                # Use bone groups instead of name patterns (costume-agnostic)
                if any(vg.name == f'{side}_foot' for vg in mesh_obj.vertex_groups):
                    foot_mesh = mesh_obj
                elif any(vg.name == f'{side}_leg2' for vg in mesh_obj.vertex_groups):
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
    """Merge leg2 meshes with leg1 meshes using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        leg1_mesh = None
        leg2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                # Use bone groups instead of name patterns (costume-agnostic)
                if any(vg.name == f'{side}_leg1' for vg in mesh_obj.vertex_groups):
                    leg1_mesh = mesh_obj
                elif any(vg.name == f'{side}_leg2' for vg in mesh_obj.vertex_groups):
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
    """Merge complete leg assemblies with body using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    body_mesh = None
    leg_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            # Use bone groups instead of name patterns (costume-agnostic)
            if any(vg.name == 'body' for vg in mesh_obj.vertex_groups):
                body_mesh = mesh_obj
            elif any(vg.name in ['l_leg1', 'r_leg1'] for vg in mesh_obj.vertex_groups):
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
    """Merge forearm meshes with upper arm meshes using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        arm1_mesh = None
        arm2_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                # Use bone groups instead of name patterns (costume-agnostic)
                if any(vg.name == f'{side}_arm1' for vg in mesh_obj.vertex_groups):
                    arm1_mesh = mesh_obj
                elif any(vg.name == f'{side}_arm2' for vg in mesh_obj.vertex_groups):
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
    """Merge hand meshes with arm assemblies using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    for side in ['l', 'r']:
        arm_mesh = None
        hand_mesh = None
        
        for mesh_obj in mesh_objects:
            try:
                # Use bone groups instead of name patterns (costume-agnostic)
                if any(vg.name == f'{side}_arm1' for vg in mesh_obj.vertex_groups):
                    arm_mesh = mesh_obj
                elif any(vg.name == f'{side}_hand' for vg in mesh_obj.vertex_groups):
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
    """Merge complete arm assemblies with body using bone-based detection."""
    try:
        import bpy
    except ImportError:
        return
    
    body_mesh = None
    arm_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            # Use bone groups instead of name patterns (costume-agnostic)
            if any(vg.name == 'body' for vg in mesh_obj.vertex_groups):
                body_mesh = mesh_obj
            elif any(vg.name in ['l_arm1', 'r_arm1'] for vg in mesh_obj.vertex_groups):
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
    
    # Define merging candidates based on connector number using bone groups (costume-agnostic)
    # Order is based on the occupancy slot processing: body, arms, hands, waist, legs, foots
    merge_bone_groups_by_number = {
        '0': ['body'],  # Body/torso connectors (breasts already merged with body)
        '1': ['l_arm1', 'r_arm1', 'l_arm2', 'r_arm2'],  # Arm connectors
        '2': ['l_hand', 'r_hand'],  # Hand/wrist connectors  
        '3': ['waist', 'body'],  # Waist connectors
        '4': ['l_leg1', 'r_leg1', 'l_leg2', 'r_leg2'],  # Leg connectors (hips/knees/thighs)
        '5': ['l_foot', 'r_foot', 'l_leg2', 'r_leg2']  # Foot/ankle connectors
    }
    
    # Extract connector number from name (e.g., "dynamic_connector_0_vf3mesh" -> "0")
    target_bone_groups = []
    import re
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    if match:
        connector_number = match.group(1)
        target_bone_groups = merge_bone_groups_by_number.get(connector_number, [])
        print(f"      Connector {connector_number} -> merge bone groups: {target_bone_groups}")
    else:
        # Fallback to old logic for non-numbered connectors using bone groups
        merge_bone_groups = {
            'breast': ['l_breast', 'r_breast', 'body'],
            'shoulder': ['l_arm1', 'r_arm1', 'body'],  
            'elbow': ['l_arm1', 'r_arm1', 'l_arm2', 'r_arm2'],
            'wrist': ['l_arm2', 'r_arm2', 'l_hand', 'r_hand'],
            'hip': ['waist', 'l_leg1', 'r_leg1'],
            'knee': ['l_leg1', 'r_leg1', 'l_leg2', 'r_leg2'],
            'ankle': ['l_leg2', 'r_leg2', 'l_foot', 'r_foot'],
            'thigh': ['l_leg1', 'r_leg1', 'waist'],
            'torso': ['body', 'waist']
        }
        
        for category, bone_groups in merge_bone_groups.items():
            if category in connector_name:
                target_bone_groups = bone_groups
                break
    
    if not target_bone_groups:
        print(f"      ❌ No merge bone groups found for connector: {connector_name}")
        return False, []
    
    # Find all target mesh objects that match the bone groups (costume-agnostic)
    target_meshes = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            _ = mesh_obj.name
            # Check if mesh has any of the target bone groups in its vertex groups
            for bone_group in target_bone_groups:
                if any(vg.name == bone_group for vg in mesh_obj.vertex_groups):
                    target_meshes.append(mesh_obj)
                    print(f"      Found target mesh {mesh_obj.name} with bone group {bone_group}")
                    break
        except (ReferenceError, AttributeError):
            # Object has been deleted, skip it
            continue
    
    if not target_meshes:
        # If no specific targets found, try to merge with the unified body mesh
        # This handles cases where limbs have been merged into the body
        for mesh_obj in mesh_objects:
            try:
                _ = mesh_obj.name
                # Look for any mesh with 'body' bone group (works for both naked and costume)
                if any(vg.name == 'body' for vg in mesh_obj.vertex_groups):
                    target_meshes.append(mesh_obj)
                    print(f"      Fallback: merging connector {connector_name} with unified body mesh {mesh_obj.name}")
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
            
            # CRITICAL FIX: Choose the BEST target mesh for this connector type, then inherit its material
            # This ensures connectors inherit from the specific part they're connecting (arms, skirt, etc.)
            best_target_mesh = _choose_best_target_mesh_for_connector(target_meshes, connector_name)
            if best_target_mesh and best_target_mesh.data.materials and connector_obj.data.materials:
                # Get the most appropriate material from the chosen target mesh
                target_material = _choose_best_material_for_connector(best_target_mesh, connector_name)
                if target_material:
                    print(f"      ✅ Inheriting SPECIFIC material from chosen target {best_target_mesh.name}: {target_material.name}")
                    
                    # Replace connector's skin-tone material with target's costume material
                    connector_obj.data.materials.clear()
                    connector_obj.data.materials.append(target_material)
                    
                    # Update face material assignments to use the inherited material
                    for face in connector_obj.data.polygons:
                        face.material_index = 0
                        
                    final_materials = [mat.name for mat in connector_obj.data.materials]
                    print(f"      ✅ Connector {connector_name} final materials after specific target inheritance: {final_materials}")
                else:
                    print(f"      ❌ Could not find suitable material from chosen target {best_target_mesh.name}")
            else:
                print(f"      ❌ Could not find suitable target mesh for connector {connector_name}")
                
            # Use the best target as primary for merging
            if best_target_mesh:
                primary_target = best_target_mesh
                merged_names = [m.name for m in target_meshes if m != primary_target]
            
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
            # Single target mesh - use the same specific targeting logic
            target_mesh = target_meshes[0]
            
            # CRITICAL FIX: For single target, just use that target directly
            if target_mesh.data.materials and connector_obj.data.materials:
                # Smart material selection from the single target
                target_material = _choose_best_material_for_connector(target_mesh, connector_name)
                if target_material:
                    print(f"      ✅ Inheriting SPECIFIC material from single target {target_mesh.name}: {target_material.name}")
                    
                    # Replace connector's skin-tone material with target's costume material
                    connector_obj.data.materials.clear()
                    connector_obj.data.materials.append(target_material)
                    
                    # Update face material assignments to use the inherited material
                    for face in connector_obj.data.polygons:
                        face.material_index = 0
                        
                    final_materials = [mat.name for mat in connector_obj.data.materials]
                    print(f"      ✅ Connector {connector_name} final materials after single target inheritance: {final_materials}")
                else:
                    print(f"      ❌ Could not find suitable material from {target_mesh.name}")
            
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


def _choose_best_material_for_connector(target_mesh, connector_name):
    """Choose the best material from target mesh for connector inheritance.
    Simple approach: just inherit the most dominant non-flesh material from the target.
    """
    try:
        import bpy
    except ImportError:
        return None
    
    if not target_mesh.data.materials:
        return None
    
    print(f"        Simple material inheritance for connector {connector_name} from {target_mesh.name}")
    
    # Define flesh color range (skin tones to avoid)
    def is_flesh_color(color):
        if len(color) < 3:
            return False
        r, g, b = color[:3]
        return (r > 0.7 and g > 0.5 and b > 0.3 and r >= g and g >= b * 1.2)
    
    # Find the first non-flesh material, or use first material if all are flesh
    for i, material in enumerate(target_mesh.data.materials):
        if not material.use_nodes:
            continue
            
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            continue
            
        base_color = bsdf.inputs['Base Color'].default_value[:3]
        
        if not is_flesh_color(base_color):
            print(f"        Using non-flesh material: {material.name}, color: {base_color}")
            return material
    
    # Fallback to first material
    first_material = target_mesh.data.materials[0]
    print(f"        Fallback to first material: {first_material.name}")
    return first_material


def _choose_best_target_mesh_for_connector(target_meshes, connector_name):
    """Choose the best target mesh for a connector based on connector type and mesh specificity.
    Returns the most relevant mesh for this connector to inherit materials from.
    """
    if not target_meshes:
        return None
    
    # Extract connector number for type detection
    import re
    connector_number = "unknown"
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    if match:
        connector_number = match.group(1)
    
    print(f"        Choosing best target mesh for connector {connector_name} (type {connector_number}) from {len(target_meshes)} options")
    
    # Score each target mesh based on relevance to connector type
    mesh_scores = []
    
    for mesh in target_meshes:
        try:
            mesh_name = mesh.name.lower()
            score = 0
            reason = ""
            
            # Connector-specific scoring
            if connector_number == "0":  # Body/torso connectors
                if 'blazer' in mesh_name and 'arm' not in mesh_name and 'hand' not in mesh_name:
                    score = 100
                    reason = "body blazer mesh"
                elif 'body' in mesh_name:
                    score = 80
                    reason = "body mesh"
                    
            elif connector_number == "1":  # Arm connectors
                if 'arm' in mesh_name or 'blazer' in mesh_name:
                    if 'l_' in mesh_name or 'r_' in mesh_name:  # Specific arm
                        score = 100
                        reason = "specific arm mesh"
                    else:
                        score = 70
                        reason = "general arm mesh"
                        
            elif connector_number == "2":  # Hand/wrist connectors
                if 'hand' in mesh_name or 'blazer3' in mesh_name:
                    score = 100
                    reason = "hand mesh"
                elif 'arm' in mesh_name:
                    score = 60
                    reason = "arm mesh (hand fallback)"
                    
            elif connector_number == "3":  # Waist connectors  
                if 'skirt' in mesh_name:
                    score = 100
                    reason = "skirt mesh (primary waist - should be blue)"
                elif 'waist' in mesh_name:
                    score = 90
                    reason = "waist mesh"
                elif 'blazer' in mesh_name and 'arm' not in mesh_name:
                    score = 50
                    reason = "blazer mesh (waist fallback)"
                    
            elif connector_number == "4":  # Leg connectors
                if 'leg' in mesh_name or 'shoe' in mesh_name:
                    score = 100
                    reason = "leg/shoe mesh"
                elif 'skirt' in mesh_name:
                    score = 70
                    reason = "skirt mesh (leg area)"
                    
            # General penalties
            if 'body_satsuki.blazer' == mesh_name:
                score -= 30  # Prefer specific parts over unified body
                reason += " (unified body penalty)"
                
            mesh_scores.append((mesh, score, reason))
            print(f"          {mesh_name}: score {score} ({reason})")
            
        except (ReferenceError, AttributeError):
            continue
    
    # Sort by score and return best mesh
    if mesh_scores:
        mesh_scores.sort(key=lambda x: x[1], reverse=True)
        best_mesh, best_score, best_reason = mesh_scores[0]
        print(f"        Selected best target: {best_mesh.name} (score: {best_score}, {best_reason})")
        return best_mesh
    
    # Fallback to first mesh
    return target_meshes[0]