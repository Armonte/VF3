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
            mesh_name = mesh_obj.name.lower()
            vg_names = [vg.name for vg in mesh_obj.vertex_groups]
            
            # Look for body mesh - check if bound to 'body' bone by checking vertex groups OR mesh name
            if any(vg.name == 'body' for vg in mesh_obj.vertex_groups) or ('body' in mesh_name and 'blazer' in mesh_name):
                body_mesh = mesh_obj
                print(f"  Found body mesh: {mesh_obj.name} (vertex groups: {vg_names})")
            # Look for breast meshes - check for breast bone groups OR mesh name patterns
            elif (any(vg.name in ['l_breast', 'r_breast'] for vg in mesh_obj.vertex_groups) or 
                  ('breast' in mesh_name or 'blazer_lb' in mesh_name or 'blazer_rb' in mesh_name)):
                breast_meshes.append(mesh_obj)
                print(f"  Found breast mesh: {mesh_obj.name} (vertex groups: {vg_names})")
        except (ReferenceError, AttributeError):
            continue
    
    if not body_mesh:
        print("  No body mesh found for breast merging")
        print(f"  Available mesh names: {[mesh_obj.name for mesh_obj in mesh_objects if hasattr(mesh_obj, 'name')]}")
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
    
    # Extract connector number from name (e.g., "dynamic_connector_0_vf3mesh" -> "0")
    import re
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    connector_number = None
    if match:
        connector_number = match.group(1)
        print(f"      Connector {connector_number} -> using NAME PATTERN matching only (no bone groups)")
    
    # Find all target mesh objects using NAME PATTERNS instead of contaminated bone groups
    # This fixes the contamination issue where merged meshes get wrong bone groups
    target_meshes = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            _ = mesh_obj.name
            mesh_name = mesh_obj.name.lower()
            
            # Use mesh NAME PATTERNS to identify correct targets (immune to bone group contamination)
            mesh_matches_target = False
            
            # Only use name pattern matching for numbered connectors
            if connector_number and connector_number == "0":  # Body/chest connectors
                # Look for body blazer meshes
                if 'body' in mesh_name and 'blazer' in mesh_name:
                    mesh_matches_target = True
                    print(f"      Found body target: {mesh_obj.name}")
                    
            elif connector_number and connector_number == "1":  # ELBOW connectors
                # Look ONLY for arm1 blazer meshes, EXCLUDE hand and body blazer
                if ('l_arm1' in mesh_name or 'r_arm1' in mesh_name) and 'blazer' in mesh_name and 'hand' not in mesh_name and 'body' not in mesh_name:
                    mesh_matches_target = True
                    print(f"      Found arm1 target: {mesh_obj.name}")
                    
            elif connector_number and connector_number == "2":  # Hand/wrist connectors
                # Look ONLY for hand meshes, EXCLUDE arm meshes
                if ('l_hand' in mesh_name or 'r_hand' in mesh_name) and 'arm' not in mesh_name:
                    mesh_matches_target = True
                    print(f"      Found hand target: {mesh_obj.name}")
                    
            elif connector_number and connector_number == "3":  # SKIRT connectors
                # Look ONLY for main skirt waist mesh, EXCLUDE skirt_f and skirt_r parts
                if 'skirt' in mesh_name and 'waist' in mesh_name:
                    mesh_matches_target = True
                    print(f"      Found skirt target: {mesh_obj.name}")
                    
            elif connector_number and connector_number == "4":  # KNEE connectors
                # Look ONLY for leg1 skin meshes (female.leg), EXCLUDE clothing and leg2
                if ('l_leg1' in mesh_name or 'r_leg1' in mesh_name) and 'female' in mesh_name and 'leg2' not in mesh_name:
                    mesh_matches_target = True
                    print(f"      Found leg skin target: {mesh_obj.name}")
                    
            elif connector_number and connector_number == "5":  # Foot/ankle connectors
                # Look for foot meshes
                if ('l_foot' in mesh_name or 'r_foot' in mesh_name):
                    mesh_matches_target = True
                    print(f"      Found foot target: {mesh_obj.name}")
            
            if mesh_matches_target:
                target_meshes.append(mesh_obj)
                
        except (ReferenceError, AttributeError):
            # Object has been deleted, skip it
            continue
    
    if not target_meshes:
        # If no specific targets found, try to merge with the unified body mesh using NAME PATTERNS
        # This handles cases where limbs have been merged into the body
        for mesh_obj in mesh_objects:
            try:
                _ = mesh_obj.name
                mesh_name = mesh_obj.name.lower()
                # Look for body mesh using name patterns (immune to bone group contamination)
                if 'body' in mesh_name and ('blazer' in mesh_name or 'female' in mesh_name):
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
            target_material_name = None
            placeholder_material_name = f"{connector_name}_PLACEHOLDER"
            
            # Create a temporary placeholder material for the connector so we can identify its faces after merging
            if not connector_obj.data.materials:
                import bpy
                placeholder_material = bpy.data.materials.new(name=placeholder_material_name)
                placeholder_material.use_nodes = True
                bsdf = placeholder_material.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    # Use a distinctive color to help with debugging
                    bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 1.0, 1.0)  # Magenta
                connector_obj.data.materials.append(placeholder_material)
                
                # Set all connector faces to use the placeholder material
                for face in connector_obj.data.polygons:
                    face.material_index = 0
                
                print(f"      Created placeholder material for connector faces: {placeholder_material_name}")
            
            if best_target_mesh and best_target_mesh.data.materials:
                # Get the most appropriate material from the chosen target mesh
                target_material = _choose_best_material_for_connector(best_target_mesh, connector_name)
                if target_material:
                    target_material_name = target_material.name
                    print(f"      ✅ Will inherit material from chosen target {best_target_mesh.name}: {target_material.name}")
                else:
                    print(f"      ❌ Could not find suitable material from chosen target {best_target_mesh.name}")
            else:
                print(f"      ❌ Could not find suitable target mesh for connector {connector_name}")
                
            # CRITICAL FIX: Only merge with the single chosen target mesh, not all target meshes
            # This prevents contamination from other meshes with different materials
            if best_target_mesh:
                primary_target = best_target_mesh
                target_meshes_to_merge = [best_target_mesh]  # Only merge with the chosen target
                merged_names = []  # No other meshes will be merged
                print(f"      Merging connector ONLY with chosen target: {best_target_mesh.name}")
            else:
                # Fallback to original behavior if no best target found
                primary_target = target_meshes[0]
                target_meshes_to_merge = target_meshes
                merged_names = [m.name for m in target_meshes[1:]]
                print(f"      Fallback: merging connector with all {len(target_meshes)} target meshes")
            
            # Select only the chosen target mesh and the connector
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select only the target mesh we want to merge with
            for mesh in target_meshes_to_merge:
                mesh.select_set(True)
            connector_obj.select_set(True)
            
            # Set primary target as active object
            bpy.context.view_layer.objects.active = primary_target
            
            # Join all selected meshes into the primary target
            bpy.ops.object.join()
            
            # CRITICAL FIX: After merging, fix the connector material assignment
            # Find faces using the placeholder material and reassign them to the inherited material
            if target_material_name:
                # Find the placeholder material index and target material index in merged mesh
                placeholder_material_index = None
                target_material_index = None
                
                for i, material in enumerate(primary_target.data.materials):
                    if material.name == placeholder_material_name:
                        placeholder_material_index = i
                    elif material.name == target_material_name:
                        target_material_index = i
                
                if placeholder_material_index is not None and target_material_index is not None:
                    print(f"      ✅ Found placeholder material '{placeholder_material_name}' at index {placeholder_material_index}")
                    print(f"      ✅ Found target material '{target_material_name}' at index {target_material_index}")
                    
                    # Update all faces using the placeholder material to use the inherited material
                    updated_faces = 0
                    for face in primary_target.data.polygons:
                        if face.material_index == placeholder_material_index:
                            face.material_index = target_material_index
                            updated_faces += 1
                    
                    print(f"      ✅ Updated {updated_faces} connector faces from placeholder (index {placeholder_material_index}) to inherited material (index {target_material_index})")
                    
                    # DEBUG: Check what materials are actually being used by faces now
                    material_usage = {}
                    for face in primary_target.data.polygons:
                        idx = face.material_index
                        material_name = primary_target.data.materials[idx].name if idx < len(primary_target.data.materials) else f"INDEX_{idx}"
                        material_usage[material_name] = material_usage.get(material_name, 0) + 1
                    
                    print(f"      DEBUG: Material usage in {primary_target.name}: {material_usage}")
                    
                    # Remove the placeholder material from the material list (cleanup)
                    # Note: We can't easily remove materials from the list without affecting indices,
                    # so we'll leave it for now. It won't be used by any faces.
                    
                else:
                    print(f"      ❌ Could not find placeholder ({placeholder_material_index}) or target ({target_material_index}) materials in merged mesh")
            
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
            target_material_name = None
            placeholder_material_name = f"{connector_name}_PLACEHOLDER"
            
            # Create a temporary placeholder material for the connector so we can identify its faces after merging
            if not connector_obj.data.materials:
                import bpy
                placeholder_material = bpy.data.materials.new(name=placeholder_material_name)
                placeholder_material.use_nodes = True
                bsdf = placeholder_material.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    # Use a distinctive color to help with debugging
                    bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 1.0, 1.0)  # Magenta
                connector_obj.data.materials.append(placeholder_material)
                
                # Set all connector faces to use the placeholder material
                for face in connector_obj.data.polygons:
                    face.material_index = 0
                
                print(f"      Created placeholder material for connector faces: {placeholder_material_name}")
            
            # CRITICAL FIX: For single target, get the material name first
            if target_mesh.data.materials:
                # Smart material selection from the single target
                target_material = _choose_best_material_for_connector(target_mesh, connector_name)
                if target_material:
                    target_material_name = target_material.name
                    print(f"      ✅ Will inherit material from single target {target_mesh.name}: {target_material.name}")
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
            
            # CRITICAL FIX: After merging, fix the connector material assignment
            if target_material_name:
                # Find the placeholder material index and target material index in merged mesh
                placeholder_material_index = None
                target_material_index = None
                
                for i, material in enumerate(target_mesh.data.materials):
                    if material.name == placeholder_material_name:
                        placeholder_material_index = i
                    elif material.name == target_material_name:
                        target_material_index = i
                
                if placeholder_material_index is not None and target_material_index is not None:
                    print(f"      ✅ Found placeholder material '{placeholder_material_name}' at index {placeholder_material_index}")
                    print(f"      ✅ Found target material '{target_material_name}' at index {target_material_index}")
                    
                    # Update all faces using the placeholder material to use the inherited material
                    updated_faces = 0
                    for face in target_mesh.data.polygons:
                        if face.material_index == placeholder_material_index:
                            face.material_index = target_material_index
                            updated_faces += 1
                    
                    print(f"      ✅ Updated {updated_faces} connector faces from placeholder to inherited material")
                else:
                    print(f"      ❌ Could not find placeholder ({placeholder_material_index}) or target ({target_material_index}) materials in merged mesh")
            
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
    """Choose the best target mesh for a connector using simple deterministic rules.
    Connectors inherit from the most specific mesh they're connecting.
    """
    if not target_meshes:
        return None
    
    # Extract connector number for type detection
    import re
    connector_number = "unknown"
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    if match:
        connector_number = match.group(1)
    
    print(f"        Choosing target mesh for connector {connector_name} (type {connector_number}) from {len(target_meshes)} options")
    
    # Simple deterministic rules - no scoring, just priority order
    for mesh in target_meshes:
        try:
            mesh_name = mesh.name.lower()
            
            if connector_number and connector_number == "0":  # Body/chest connectors
                # Prefer non-arm, non-hand body blazer meshes
                if 'blazer' in mesh_name and 'arm' not in mesh_name and 'hand' not in mesh_name and 'body' in mesh_name:
                    print(f"        Selected: {mesh.name} (body blazer for chest connector)")
                    return mesh
                    
            elif connector_number and connector_number == "1":  # ELBOW connectors  
                # Prefer ONLY arm1 blazer meshes, EXCLUDE body and hand
                if 'arm1' in mesh_name and 'blazer' in mesh_name and 'body' not in mesh_name and 'hand' not in mesh_name:
                    print(f"        Selected: {mesh.name} (arm1 blazer mesh for elbow connector)")
                    return mesh
                    
            elif connector_number and connector_number == "2":  # Hand/wrist connectors
                # Prefer ONLY hand meshes, EXCLUDE arm meshes
                if 'hand' in mesh_name and 'arm' not in mesh_name:
                    print(f"        Selected: {mesh.name} (hand mesh for wrist connector)")
                    return mesh
                    
            elif connector_number and connector_number == "3":  # SKIRT connectors
                # Prefer ONLY main skirt waist mesh, EXCLUDE skirt parts
                if 'skirt' in mesh_name and 'waist' in mesh_name:
                    print(f"        Selected: {mesh.name} (skirt waist mesh for skirt connector)")
                    return mesh
                    
            elif connector_number and connector_number == "4":  # KNEE connectors
                # Prefer ONLY leg1 skin meshes, EXCLUDE clothing and leg2
                if 'leg1' in mesh_name and 'female' in mesh_name and 'leg2' not in mesh_name:
                    print(f"        Selected: {mesh.name} (skin leg mesh for knee connector)")
                    return mesh
                    
        except (ReferenceError, AttributeError):
            continue
    
    # Fallback: use first valid mesh
    for mesh in target_meshes:
        try:
            _ = mesh.name  # Test if mesh is still valid
            print(f"        Fallback: {mesh.name} (first available mesh)")
            return mesh
        except (ReferenceError, AttributeError):
            continue
    
    return None