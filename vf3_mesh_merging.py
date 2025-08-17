"""
VF3 Mesh Merging - Extracted from working vf3_blender_exporter.py
Handles merging of body parts to create seamless character models.
"""

import os
import sys
from typing import List, Dict, Any


def _create_anatomical_mesh_groups(mesh_objects):
    """
    Create proper anatomical mesh groups for smooth character export.
    Groups meshes into: Body, Left Arm, Right Arm, Left Leg, Right Leg, Head
    Also merges dynamic connectors with their target anatomical groups.
    """
    try:
        import bpy
    except ImportError:
        return
    
    print("  🎯 Creating anatomical mesh groups...")
    
    # Step 1: Group meshes by anatomical region using vertex groups
    body_meshes = []
    left_arm_meshes = []
    right_arm_meshes = []
    left_leg_meshes = []
    right_leg_meshes = []
    head_meshes = []
    connector_meshes = []
    other_meshes = []
    
    for mesh_obj in mesh_objects:
        try:
            mesh_name = mesh_obj.name.lower()
            vg_names = [vg.name for vg in mesh_obj.vertex_groups]
            
            # Classify dynamic connectors separately
            if 'dynamic_connector' in mesh_name:
                connector_meshes.append(mesh_obj)
                print(f"    🔌 Connector: {mesh_obj.name}")
                continue
            
            # Classify by dominant vertex groups (bone assignments)
            if any(vg.name in ['body', 'l_breast', 'r_breast', 'waist', 'skirt_f', 'skirt_r'] for vg in mesh_obj.vertex_groups):
                body_meshes.append(mesh_obj)
                print(f"    🫀 Body: {mesh_obj.name} (vertex groups: {vg_names})")
            elif any(vg.name in ['l_arm1', 'l_arm2', 'l_hand'] for vg in mesh_obj.vertex_groups):
                left_arm_meshes.append(mesh_obj)
                print(f"    🫲 Left Arm: {mesh_obj.name} (vertex groups: {vg_names})")
            elif any(vg.name in ['r_arm1', 'r_arm2', 'r_hand'] for vg in mesh_obj.vertex_groups):
                right_arm_meshes.append(mesh_obj)
                print(f"    🫱 Right Arm: {mesh_obj.name} (vertex groups: {vg_names})")
            elif any(vg.name in ['l_leg1', 'l_leg2', 'l_foot'] for vg in mesh_obj.vertex_groups):
                left_leg_meshes.append(mesh_obj)
                print(f"    🦵 Left Leg: {mesh_obj.name} (vertex groups: {vg_names})")
            elif any(vg.name in ['r_leg1', 'r_leg2', 'r_foot'] for vg in mesh_obj.vertex_groups):
                right_leg_meshes.append(mesh_obj)
                print(f"    🦵 Right Leg: {mesh_obj.name} (vertex groups: {vg_names})")
            elif any(vg.name in ['head', 'neck'] for vg in mesh_obj.vertex_groups):
                head_meshes.append(mesh_obj)
                print(f"    🗣️ Head: {mesh_obj.name} (vertex groups: {vg_names})")
            else:
                other_meshes.append(mesh_obj)
                print(f"    ❓ Other: {mesh_obj.name} (vertex groups: {vg_names})")
                
        except (ReferenceError, AttributeError):
            continue
    
    # Step 2: Merge connectors with their target anatomical groups first
    print("  🔌 Merging connectors with target anatomical groups...")
    for connector_obj in connector_meshes:
        _merge_connector_with_anatomical_groups(
            connector_obj, 
            {
                'body': body_meshes,
                'left_arm': left_arm_meshes, 
                'right_arm': right_arm_meshes,
                'left_leg': left_leg_meshes,
                'right_leg': right_leg_meshes,
                'head': head_meshes
            }
        )
    
    # Step 3: Merge each anatomical group into a single mesh
    _merge_anatomical_group(body_meshes, "Body")
    _merge_anatomical_group(left_arm_meshes, "LeftArm") 
    _merge_anatomical_group(right_arm_meshes, "RightArm")
    _merge_anatomical_group(left_leg_meshes, "LeftLeg")
    _merge_anatomical_group(right_leg_meshes, "RightLeg")
    _merge_anatomical_group(head_meshes, "Head")
    _merge_anatomical_group(other_meshes, "Other")
    
    print("  ✅ Anatomical mesh grouping complete!")


def _merge_connector_with_anatomical_groups(connector_obj, anatomical_groups):
    """Merge a dynamic connector with the most appropriate anatomical group using source-based assignment."""
    try:
        import bpy
    except ImportError:
        return False
    
    if not connector_obj:
        return False
    
    connector_name = connector_obj.name.lower()
    
    print(f"\n🔍 CONNECTOR ANALYSIS: {connector_obj.name}")
    print(f"=" * 60)
    
    # Enhanced logging: Check source information
    source_info = connector_obj.get("connector_source_info", "Unknown")
    if source_info and source_info != "Unknown":
        print(f"📍 Source Info: {source_info}")
        
        # CRITICAL FIX: Use source-based assignment instead of bone analysis
        # This prevents bilateral connectors from contaminating single anatomical groups
        target_group = _determine_target_group_from_source(source_info)
        
        # ADDITIONAL CHECK: Even if source suggests a target, verify it's not bilateral by bone content
        connector_bones = [vg.name for vg in connector_obj.vertex_groups]
        has_left_bones = any('l_' in bone for bone in connector_bones)
        has_right_bones = any('r_' in bone for bone in connector_bones)
        
        if has_left_bones and has_right_bones:
            print(f"🚨 BILATERAL BONE CONTENT DETECTED: Left={[b for b in connector_bones if 'l_' in b]}, Right={[b for b in connector_bones if 'r_' in b]}")
            print(f"🌐 OVERRIDING source assignment - keeping {connector_obj.name} as standalone bilateral connector")
            return False  # Don't merge any bilateral connectors regardless of source
        elif target_group:
            print(f"✅ SOURCE-BASED ASSIGNMENT: {target_group} (from source: {source_info})")
            return _assign_connector_to_group(connector_obj, target_group, anatomical_groups)
        elif target_group is None:
            print(f"🌐 BILATERAL SOURCE: Keeping {connector_obj.name} as standalone connector")
            return False  # Don't merge bilateral connectors
        else:
            print(f"⚠️  Could not determine target group from source, falling back to bone analysis")
    else:
        print(f"⚠️  No source info available for {connector_obj.name}, using bone analysis")
    
    # Analyze connector's vertex groups to determine target
    vg_names = [vg.name for vg in connector_obj.vertex_groups]
    print(f"🦴 Vertex Groups ({len(vg_names)}): {vg_names}")
    
    # Enhanced debugging: Analyze vertex distribution per bone
    bone_vertex_counts = {}
    for vg in connector_obj.vertex_groups:
        vertex_count = 0
        for vertex in connector_obj.data.vertices:
            for group in vertex.groups:
                if group.group == vg.index and group.weight > 0:
                    vertex_count += 1
                    break
        bone_vertex_counts[vg.name] = vertex_count
    
    print(f"📊 Bone Vertex Distribution: {bone_vertex_counts}")
    
    # Check available anatomical groups
    available_groups = {name: len(meshes) for name, meshes in anatomical_groups.items() if meshes}
    print(f"🎯 Available Target Groups: {available_groups}")
    
    # CRITICAL DEBUGGING: Check for bilateral contamination
    has_left = any(bone for bone in bone_vertex_counts.keys() if 'l_' in bone or 'left' in bone.lower())
    has_right = any(bone for bone in bone_vertex_counts.keys() if 'r_' in bone or 'right' in bone.lower())
    
    if has_left and has_right:
        print(f"🚨 BILATERAL CONTAMINATION DETECTED in {connector_obj.name}!")
        left_bones = [bone for bone in bone_vertex_counts.keys() if 'l_' in bone or 'left' in bone.lower()]
        right_bones = [bone for bone in bone_vertex_counts.keys() if 'r_' in bone or 'right' in bone.lower()]
        print(f"   Left bones: {left_bones}")
        print(f"   Right bones: {right_bones}")
        print(f"   This connector should be split or handled specially!")
        
        # For now, log this and continue with original logic
        # TODO: Implement proper bilateral splitting
    elif has_left:
        print(f"🔵 LEFT-SIDE connector detected: {[bone for bone in bone_vertex_counts.keys() if 'l_' in bone]}")
    elif has_right:
        print(f"🔴 RIGHT-SIDE connector detected: {[bone for bone in bone_vertex_counts.keys() if 'r_' in bone]}")
    else:
        print(f"⚪ NEUTRAL connector (no left/right bones): {list(bone_vertex_counts.keys())}")
    
    # FALLBACK: Analyze bone patterns only when source info unavailable
    # Use bone-specific weights and pattern analysis
    
    # Define bone weights (more important bones get higher weights)
    bone_weights = {
        # Upper body
        'body': 3, 'waist': 2, 'l_breast': 2, 'r_breast': 2,
        # Arms (upper arm is most defining)
        'l_arm1': 3, 'l_arm2': 2, 'l_hand': 1,
        'r_arm1': 3, 'r_arm2': 2, 'r_hand': 1,
        # Legs (upper leg is most defining)
        'l_leg1': 3, 'l_leg2': 2, 'l_foot': 1,
        'r_leg1': 3, 'r_leg2': 2, 'r_foot': 1,
        # Head
        'head': 3, 'neck': 2
    }
    
    # Calculate weighted region scores
    region_weighted_scores = {
        'body': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['body', 'l_breast', 'r_breast', 'waist']),
        'left_arm': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['l_arm1', 'l_arm2', 'l_hand']),
        'right_arm': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['r_arm1', 'r_arm2', 'r_hand']),
        'left_leg': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['l_leg1', 'l_leg2', 'l_foot']),
        'right_leg': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['r_leg1', 'r_leg2', 'r_foot']),
        'head': sum(bone_weights.get(bone, 1) for bone in vg_names if bone in ['head', 'neck'])
    }
    
    # Also keep simple bone type counts for reference
    region_counts = {
        'body': sum(1 for vg in vg_names if vg in ['body', 'l_breast', 'r_breast', 'waist']),
        'left_arm': sum(1 for vg in vg_names if vg in ['l_arm1', 'l_arm2', 'l_hand']),
        'right_arm': sum(1 for vg in vg_names if vg in ['r_arm1', 'r_arm2', 'r_hand']),
        'left_leg': sum(1 for vg in vg_names if vg in ['l_leg1', 'l_leg2', 'l_foot']),
        'right_leg': sum(1 for vg in vg_names if vg in ['r_leg1', 'r_leg2', 'r_foot']),
        'head': sum(1 for vg in vg_names if vg in ['head', 'neck'])
    }
    
    print(f"📈 Region Weighted Scores: {region_weighted_scores}")
    print(f"📊 Region Bone Counts: {region_counts}")
    
    # Find the dominant region (most bone types present)
    target_group = None
    target_meshes = []
    max_count = 0
    
    # SMART BILATERAL DISTRIBUTION: Count bones per region, handle bilateral ties intelligently
    
    # Simple bone counting (no weighted scores, just raw counts)
    region_bone_counts = {
        'body': sum(1 for vg in vg_names if vg in ['body', 'l_breast', 'r_breast', 'waist', 'skirt_f', 'skirt_r']),
        'left_arm': sum(1 for vg in vg_names if vg in ['l_arm1', 'l_arm2', 'l_hand']),
        'right_arm': sum(1 for vg in vg_names if vg in ['r_arm1', 'r_arm2', 'r_hand']),
        'left_leg': sum(1 for vg in vg_names if vg in ['l_leg1', 'l_leg2', 'l_foot']),
        'right_leg': sum(1 for vg in vg_names if vg in ['r_leg1', 'r_leg2', 'r_foot']),
        'head': sum(1 for vg in vg_names if vg in ['head', 'neck'])
    }
    
    print(f"🧮 Simple Bone Counts: {region_bone_counts}")
    
    # Find the maximum bone count
    max_bones = max(region_bone_counts.values())
    print(f"🎯 Max Bone Count: {max_bones}")
    
    # Find all regions with maximum bone count
    tied_regions = [region for region, count in region_bone_counts.items() if count == max_bones and count > 0]
    
    print(f"🏆 Tied regions with {max_bones} bones: {tied_regions}")
    
    # SPECIAL CASE: Mixed body/arm connectors - prefer arm assignment
    if (region_bone_counts['body'] > 0 and 
        (region_bone_counts['left_arm'] > 0 or region_bone_counts['right_arm'] > 0)):
        
        total_arm_bones = region_bone_counts['left_arm'] + region_bone_counts['right_arm']
        body_bones = region_bone_counts['body']
        
        print(f"🔀 BODY/ARM MIXED CONNECTOR DETECTED:")
        print(f"   Body bones: {body_bones}, Left arm: {region_bone_counts['left_arm']}, Right arm: {region_bone_counts['right_arm']}")
        
        # Check if this is bilateral (has both left and right arm bones)
        has_bilateral_arms = region_bone_counts['left_arm'] > 0 and region_bone_counts['right_arm'] > 0
        
        if has_bilateral_arms:
            print(f"   🌐 BILATERAL ARM CONNECTOR - using alternating assignment")
            # Bilateral connector - use alternating assignment to distribute evenly
            if not hasattr(_merge_connector_with_anatomical_groups, '_body_arm_counter'):
                _merge_connector_with_anatomical_groups._body_arm_counter = 0
            
            _merge_connector_with_anatomical_groups._body_arm_counter += 1
            connector_id = _merge_connector_with_anatomical_groups._body_arm_counter
            
            # Alternate between left and right arms for bilateral connectors
            target_group = 'left_arm' if connector_id % 2 == 1 else 'right_arm'
            print(f"   ✅ DECISION: {target_group} (connector_id={connector_id})")
            
        elif total_arm_bones >= body_bones * 0.6:
            # Non-bilateral but arms have significant representation - prefer the arm side with bones
            if region_bone_counts['left_arm'] > region_bone_counts['right_arm']:
                target_group = 'left_arm'
                print(f"    Body/arm connector assigned to left_arm (left={region_bone_counts['left_arm']}, right={region_bone_counts['right_arm']})")
            else:
                target_group = 'right_arm'
                print(f"    Body/arm connector assigned to right_arm (left={region_bone_counts['left_arm']}, right={region_bone_counts['right_arm']})")
        else:
            # Body dominates - assign to body
            target_group = 'body'
            print(f"    Mixed connector with body dominance: body={body_bones}, arms={total_arm_bones} -> body")
    
    # SPECIAL CASE: Mixed body/leg connectors - prefer leg assignment  
    elif (region_bone_counts['body'] > 0 and 
          (region_bone_counts['left_leg'] > 0 or region_bone_counts['right_leg'] > 0)):
        
        print(f"🔀 BODY/LEG MIXED CONNECTOR DETECTED:")
        
        total_leg_bones = region_bone_counts['left_leg'] + region_bone_counts['right_leg']
        body_bones = region_bone_counts['body']
        
        # Check if this is bilateral (has both left and right leg bones)
        has_bilateral_legs = region_bone_counts['left_leg'] > 0 and region_bone_counts['right_leg'] > 0
        
        if has_bilateral_legs:
            # Bilateral connector - use alternating assignment to distribute evenly
            if not hasattr(_merge_connector_with_anatomical_groups, '_body_leg_counter'):
                _merge_connector_with_anatomical_groups._body_leg_counter = 0
            
            _merge_connector_with_anatomical_groups._body_leg_counter += 1
            connector_id = _merge_connector_with_anatomical_groups._body_leg_counter
            
            # Alternate between left and right legs for bilateral connectors
            target_group = 'left_leg' if connector_id % 2 == 1 else 'right_leg'
            print(f"    Body/leg bilateral connector assigned to {target_group} (connector_id={connector_id})")
            
        elif total_leg_bones >= body_bones * 0.6:
            # Non-bilateral but legs have significant representation - prefer the leg side with bones
            if region_bone_counts['left_leg'] > region_bone_counts['right_leg']:
                target_group = 'left_leg'
                print(f"    Body/leg connector assigned to left_leg (left={region_bone_counts['left_leg']}, right={region_bone_counts['right_leg']})")
            else:
                target_group = 'right_leg'
                print(f"    Body/leg connector assigned to right_leg (left={region_bone_counts['left_leg']}, right={region_bone_counts['right_leg']})")
        else:
            # Body dominates - assign to body
            target_group = 'body'
            print(f"    Mixed connector with body dominance: body={body_bones}, legs={total_leg_bones} -> body")
    
    # Handle assignment with smart bilateral distribution
    elif len(tied_regions) == 1:
        target_group = tied_regions[0]
        print(f"    Clear winner: {target_group} ({max_bones} bones)")
    elif len(tied_regions) == 2 and set(tied_regions) in [{'left_arm', 'right_arm'}, {'left_leg', 'right_leg'}]:
        # BILATERAL TIE: Use separate counters for arms vs legs to distribute evenly
        # This ensures we don't assign all mixed connectors to the same side
        
        if set(tied_regions) == {'left_arm', 'right_arm'}:
            # Use separate counter for arm bilateral ties
            if not hasattr(_merge_connector_with_anatomical_groups, '_arm_bilateral_counter'):
                _merge_connector_with_anatomical_groups._arm_bilateral_counter = 0
            
            _merge_connector_with_anatomical_groups._arm_bilateral_counter += 1
            connector_id = _merge_connector_with_anatomical_groups._arm_bilateral_counter
            
            # For arm ties, alternate assignment based on connector counter
            target_group = 'left_arm' if connector_id % 2 == 1 else 'right_arm'
            print(f"    Bilateral arm tie: assigned to {target_group} (connector_id={connector_id})")
            
        elif set(tied_regions) == {'left_leg', 'right_leg'}:
            # Use separate counter for leg bilateral ties
            if not hasattr(_merge_connector_with_anatomical_groups, '_leg_bilateral_counter'):
                _merge_connector_with_anatomical_groups._leg_bilateral_counter = 0
            
            _merge_connector_with_anatomical_groups._leg_bilateral_counter += 1
            connector_id = _merge_connector_with_anatomical_groups._leg_bilateral_counter
            
            # For leg ties, alternate assignment based on connector counter
            target_group = 'left_leg' if connector_id % 2 == 1 else 'right_leg'
            print(f"    Bilateral leg tie: assigned to {target_group} (connector_id={connector_id})")
    else:
        # Multi-way tie or complex case: use original priority system
        # Priority: body > left_arm > right_arm > left_leg > right_leg > head
        priority_order = ['body', 'left_arm', 'right_arm', 'left_leg', 'right_leg', 'head']
        
        for priority_region in priority_order:
            if priority_region in tied_regions:
                target_group = priority_region
                print(f"    Multi-way tie broken by priority: {target_group} ({max_bones} bones, tied with {tied_regions})")
                break
        
        # If somehow no priority match (shouldn't happen)
        if not target_group:
            target_group = tied_regions[0]
            print(f"    Fallback: {target_group} ({max_bones} bones)")
    
    if target_group:
        target_meshes = anatomical_groups[target_group]
        print(f"✅ FINAL ASSIGNMENT: {target_group} group")
        
    else:
        # Final fallback to bone type counts if all else fails
        print(f"⚠️  FALLBACK ASSIGNMENT NEEDED")
        for region, count in region_counts.items():
            if count > max_count:
                max_count = count
                target_group = region
                target_meshes = anatomical_groups[region]
        
        if target_group:
            print(f"🔄 Fallback: connector -> {target_group} (bone count: {max_count})")
        else:
            print(f"❌ ERROR: No valid assignment found for connector!")
    
    if target_group and target_meshes:
        print(f"🎯 MERGING: {connector_obj.name} → {target_group} group ({len(target_meshes)} meshes)")
        
        # Choose the first target mesh to merge with
        target_mesh = target_meshes[0]
        print(f"   Target mesh: {target_mesh.name}")
        print(f"   Target mesh bones: {[vg.name for vg in target_mesh.vertex_groups][:5]}...")
        print(f"   Target mesh materials: {[mat.name for mat in target_mesh.data.materials] if target_mesh.data.materials else ['NO_MATERIALS']}")
        
        # Select target mesh and connector
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        connector_obj.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        
        try:
            # Join the meshes (connector into target)
            bpy.ops.object.join()
            
            # Enter Edit mode and merge overlapping vertices to eliminate seams
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"      ✅ Successfully merged connector {connector_name} with {target_mesh.name}")
            return True
            
        except Exception as e:
            print(f"      ❌ Failed to merge connector {connector_name}: {e}")
            return False
    else:
        print(f"    ❓ No target group found for connector {connector_obj.name}")
        return False


def _determine_target_group_from_source(source_info):
    """Determine target anatomical group from source information."""
    try:
        # Parse source info string like "{'source': 'costume:satsuki.blazer:blazer_vp'}"
        import ast
        if isinstance(source_info, str):
            source_dict = ast.literal_eval(source_info)
        else:
            source_dict = source_info
        
        source_string = source_dict.get('source', '').lower()
        print(f"   🔍 Analyzing source string: {source_string}")
        
        # CRITICAL: For bilateral sources (containing both left and right elements),
        # keep as standalone connectors rather than merging into single anatomical groups
        if _is_bilateral_source(source_string):
            print(f"   🌐 BILATERAL SOURCE DETECTED - keeping as standalone connector")
            return None  # Don't merge bilateral connectors
        
        # Source-based assignment rules
        if 'blazer' in source_string and 'vp' in source_string:
            # Blazer connectors typically connect body/chest areas
            return 'body'
        elif 'female.arms' in source_string or 'female.l_hand' in source_string or 'female.r_hand' in source_string:
            # Female body part sources - use alternating assignment for bilateral parts
            if 'l_hand' in source_string or 'l_arm' in source_string:
                return 'left_arm'
            elif 'r_hand' in source_string or 'r_arm' in source_string:
                return 'right_arm'
            else:
                # Generic arms source - keep as standalone
                return None
        elif 'female.body' in source_string or 'female.waist' in source_string:
            return 'body'
        elif 'female.legs' in source_string or 'female.foots' in source_string:
            # Generic bilateral legs/feet - keep as standalone
            return None
        elif 'head' in source_string:
            return 'head'
        else:
            # Unknown source - fallback to bone analysis
            return None
            
    except Exception as e:
        print(f"   ❌ Error parsing source info: {e}")
        return None


def _is_bilateral_source(source_string):
    """Check if source represents bilateral (left+right) content."""
    # Check for patterns that indicate bilateral content
    bilateral_indicators = [
        ('left' in source_string or 'l_' in source_string) and ('right' in source_string or 'r_' in source_string),
        'arms' in source_string,  # female.arms contains both left and right
        'legs' in source_string,  # female.legs contains both left and right
        'foots' in source_string,  # female.foots contains both left and right
        'hands' in source_string,  # female.hands contains both left and right
    ]
    
    return any(bilateral_indicators)


def _assign_connector_to_group(connector_obj, target_group, anatomical_groups):
    """Assign connector to specific anatomical group."""
    try:
        import bpy
    except ImportError:
        return False
    
    if target_group not in anatomical_groups or not anatomical_groups[target_group]:
        print(f"   ❌ Target group '{target_group}' not available or empty")
        return False
    
    target_meshes = anatomical_groups[target_group]
    target_mesh = target_meshes[0]  # Use first mesh in group
    
    print(f"🎯 ASSIGNING: {connector_obj.name} → {target_group} group")
    print(f"   Target mesh: {target_mesh.name}")
    
    # DETAILED LOGGING: What bones are being merged into what group
    connector_bones = [vg.name for vg in connector_obj.vertex_groups]
    target_bones = [vg.name for vg in target_mesh.vertex_groups]
    
    print(f"   📦 MERGING BONES INTO {target_group.upper()}:")
    print(f"      From connector: {connector_bones}")
    print(f"      Existing target: {target_bones[:10]}..." if len(target_bones) > 10 else f"      Existing target: {target_bones}")
    
    # Check for problematic merges
    connector_left = [bone for bone in connector_bones if 'l_' in bone or 'left' in bone.lower()]
    connector_right = [bone for bone in connector_bones if 'r_' in bone or 'right' in bone.lower()]
    
    if connector_left and connector_right:
        print(f"   🚨 WARNING: Merging bilateral connector into single group {target_group}!")
        print(f"      Left bones: {connector_left}")
        print(f"      Right bones: {connector_right}")
    elif target_group in ['left_arm', 'left_leg'] and connector_right:
        print(f"   🚨 ERROR: Merging RIGHT bones {connector_right} into LEFT group {target_group}!")
    elif target_group in ['right_arm', 'right_leg'] and connector_left:
        print(f"   🚨 ERROR: Merging LEFT bones {connector_left} into RIGHT group {target_group}!")
    
    # Select target mesh and connector
    bpy.ops.object.select_all(action='DESELECT')
    target_mesh.select_set(True)
    connector_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_mesh
    
    try:
        # Join the meshes (connector into target)
        bpy.ops.object.join()
        
        # Enter Edit mode and merge overlapping vertices to eliminate seams
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print(f"      ✅ Successfully merged connector {connector_obj.name} with {target_mesh.name}")
        return True
        
    except Exception as e:
        print(f"      ❌ Failed to merge connector {connector_obj.name}: {e}")
        return False


def _merge_anatomical_group(mesh_group, group_name):
    """Merge all meshes in an anatomical group into a single smooth mesh."""
    try:
        import bpy
    except ImportError:
        return
    
    if not mesh_group or len(mesh_group) <= 1:
        if len(mesh_group) == 1:
            mesh_group[0].name = f"VF3_{group_name}"
            print(f"    ✅ Renamed single mesh to VF3_{group_name}")
        return
    
    print(f"  🔧 Merging {len(mesh_group)} meshes into {group_name} group...")
    
    # Select all meshes in the group
    primary_mesh = mesh_group[0]
    bpy.ops.object.select_all(action='DESELECT')
    
    for mesh_obj in mesh_group:
        try:
            mesh_obj.select_set(True)
        except (ReferenceError, AttributeError):
            continue
    
    bpy.context.view_layer.objects.active = primary_mesh
    
    try:
        # Join all meshes in the group
        bpy.ops.object.join()
        
        # Rename the merged mesh
        primary_mesh.name = f"VF3_{group_name}"
        
        # Enter Edit mode and merge overlapping vertices to create smooth connections
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.mesh.normals_make_consistent(inside=False)  # Fix normals
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print(f"    ✅ Successfully created VF3_{group_name} with merged geometry")
        
    except Exception as e:
        print(f"    ❌ Failed to merge {group_name} group: {e}")


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
        
        # Enter Edit mode and merge overlapping vertices to eliminate seams
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print("  ✅ Successfully merged breast meshes with body and welded vertices")
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
                
                # Enter Edit mode and merge overlapping vertices to eliminate seams
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
                bpy.ops.object.mode_set(mode='OBJECT')
                
                print(f"  ✅ Successfully merged {side} foot with leg2 and welded vertices")
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
                
                # Enter Edit mode and merge overlapping vertices to eliminate seams
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
                bpy.ops.object.mode_set(mode='OBJECT')
                
                print(f"  ✅ Successfully merged {side} leg2 with leg1 and welded vertices")
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
        
        # Enter Edit mode and merge overlapping vertices to eliminate seams
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print("  ✅ Successfully merged legs with body and welded vertices")
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
                
                # Enter Edit mode and merge overlapping vertices to eliminate seams
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
                bpy.ops.object.mode_set(mode='OBJECT')
                
                print(f"  ✅ Successfully merged {side} forearm with arm and welded vertices")
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
                
                # Enter Edit mode and merge overlapping vertices to eliminate seams
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
                bpy.ops.object.mode_set(mode='OBJECT')
                
                print(f"  ✅ Successfully merged {side} hand with arm and welded vertices")
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
        
        # Enter Edit mode and merge overlapping vertices to eliminate seams
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print("  ✅ Successfully merged arms with body and welded vertices")
    except Exception as e:
        print(f"  ❌ Failed to merge arms: {e}")


def _try_merge_connector_with_body_mesh(connector_obj, mesh_objects, vertex_bone_names):
    """
    Try to merge a DynamicVisual connector with the most appropriate body mesh.
    Simple approach: Find the best target mesh based on connector content and merge the whole thing.
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
    
    connector_name = connector_obj.name.lower()
    
    # Extract connector number from name (e.g., "dynamic_connector_0_vf3mesh" -> "0")
    import re
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    connector_number = None
    if match:
        connector_number = match.group(1)
        print(f"      Connector {connector_number} -> using SIMPLE SMART TARGETING")
    
    # Analyze bone content to choose the best target
    bone_counts = {}
    for bone_name in vertex_bone_names:
        bone_counts[bone_name] = bone_counts.get(bone_name, 0) + 1
    
    print(f"      Connector {connector_name} bone content: {bone_counts}")
    
    # Find the best target mesh based on connector content and type
    target_mesh = _find_best_target_mesh_simple(connector_number, bone_counts, mesh_objects)
    
    if not target_mesh:
        print(f"      ❌ No suitable target mesh found for connector {connector_name}")
        return False, []
    
    print(f"      ✅ Selected target mesh: {target_mesh.name}")
    
    # Simple merge: just merge the entire connector with the chosen target
    try:
        # Select target mesh and connector
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        connector_obj.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        
        # Join the meshes (connector into target)
        bpy.ops.object.join()
        
        # CRITICAL FIX: Filter vertex groups based on target mesh type
        target_group = _determine_anatomical_group_from_mesh_name(target_mesh.name)
        _filter_vertex_groups_by_anatomical_region(target_mesh, target_group)
        
        # Enter Edit mode and merge overlapping vertices to eliminate seams
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge vertices within 0.001 units
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print(f"      ✅ Successfully merged connector {connector_name} with {target_mesh.name} and welded vertices")
        return True, []
        
    except Exception as e:
        print(f"      ❌ Failed to merge connector {connector_name}: {e}")
        return False, []


def _find_best_target_mesh_simple(connector_number, bone_counts, mesh_objects):
    """Find the best target mesh using simple rules based on connector type and bone content."""
    
    # Get the dominant bone (most vertices)
    if not bone_counts:
        return None
    
    dominant_bone = max(bone_counts.keys(), key=lambda b: bone_counts[b])
    print(f"        Dominant bone: {dominant_bone} ({bone_counts[dominant_bone]} vertices)")
    
    # CRITICAL FIX: For connector 0, prioritize waist meshes if waist vertices are present
    # BUT only if we don't have a complete body blazer mesh (indicating costume mode)
    if connector_number == "0" and 'waist' in bone_counts and bone_counts['waist'] > 0:
        print(f"        ⚠️ Connector 0 contains {bone_counts['waist']} waist vertices - checking if waist priority needed")
        
        # Check if we have a blazer body mesh (indicates costume mode where waist priority is needed)
        has_blazer_body = False
        has_female_waist = False
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if 'body' in mesh_name and 'blazer' in mesh_name:
                    has_blazer_body = True
                if 'waist' in mesh_name and 'female' in mesh_name:
                    has_female_waist = True
            except (ReferenceError, AttributeError):
                continue
        
        # Only use waist priority if we have blazer body (costume) but no complete female waist
        # In naked mode (has female waist), connector 0 should go to body mesh for proper hierarchy
        if has_blazer_body and not has_female_waist:
            print(f"        🔄 COSTUME MODE: Blazer body detected, no female waist - applying waist priority")
            for mesh_obj in mesh_objects:
                try:
                    mesh_name = mesh_obj.name.lower()
                    if 'waist' in mesh_name and ('blazer' in mesh_name):
                        print(f"        🎯 WAIST PRIORITY: Targeting waist mesh {mesh_obj.name} for connector 0 waist geometry")
                        return mesh_obj
                except (ReferenceError, AttributeError):
                    continue
            print(f"        ⚠️ No blazer waist mesh found for waist vertices, falling back to body mesh")
        else:
            print(f"        ✅ NAKED/COMPLETE MODE: Female waist exists ({has_female_waist}), using normal body targeting")
    
    # Standard targeting rules based on dominant bone and connector number
    for mesh_obj in mesh_objects:
        try:
            mesh_name = mesh_obj.name.lower()
            
            # Connector 0 (body/chest) - target body blazer mesh
            if connector_number == "0":
                if dominant_bone in ['body', 'l_breast', 'r_breast']:
                    if 'body' in mesh_name and 'blazer' in mesh_name:
                        return mesh_obj
                        
            # Connector 1 (elbow/wrist) - target arm-specific meshes ONLY, DO NOT merge with body!
            elif connector_number == "1": 
                if dominant_bone in ['l_arm1', 'r_arm1']:
                    # ELBOW CONNECTORS: Target upper arm (arm1) meshes specifically
                    if 'arm1' in mesh_name and ('blazer' in mesh_name or 'female' in mesh_name):
                        print(f"        🎯 ELBOW CONNECTOR: Targeting upper arm mesh {mesh_obj.name} for connector 1 arm1 geometry")
                        return mesh_obj
                elif dominant_bone in ['l_arm2', 'r_arm2']:
                    # FOREARM CONNECTORS: Target forearm (arm2) meshes specifically  
                    if 'arm2' in mesh_name and ('blazer' in mesh_name or 'female' in mesh_name):
                        print(f"        🎯 FOREARM CONNECTOR: Targeting forearm mesh {mesh_obj.name} for connector 1 arm2 geometry")
                        return mesh_obj
                elif dominant_bone in ['l_hand', 'r_hand']:
                    # WRIST CONNECTORS: Target hand meshes for wrist connectors
                    if 'hand' in mesh_name and ('blazer' in mesh_name or 'female' in mesh_name):
                        print(f"        🎯 WRIST CONNECTOR: Targeting hand mesh {mesh_obj.name} for connector 1 hand geometry")
                        return mesh_obj
                elif dominant_bone == 'body':
                    # CRITICAL FIX: Body connectors (shoulder connectors) should NOT merge with body
                    # Instead, keep them as separate connectors for proper anatomical grouping
                    print(f"        🎯 SHOULDER CONNECTOR: Keeping body connectors separate from body mesh for proper grouping")
                    return None  # Don't merge, keep as standalone connector
                        
            # Connector 2 (skirt/waist) - target waist/skirt meshes  
            elif connector_number == "2":
                if dominant_bone == 'waist':
                    if 'waist' in mesh_name or ('skirt' in mesh_name and 'waist' not in mesh_name):
                        return mesh_obj
                        
            # Connector 3 (knee) - target leg meshes
            elif connector_number == "3":
                if dominant_bone in ['l_leg1', 'r_leg1']:
                    if 'leg1' in mesh_name and 'female' in mesh_name:
                        return mesh_obj
                        
            # Connector 4 (ankle) - target foot meshes
            elif connector_number == "4":
                if dominant_bone in ['l_foot', 'r_foot']:
                    if 'foot' in mesh_name:
                        return mesh_obj
                        
        except (ReferenceError, AttributeError):
            continue
    
    # Fallback: find body mesh for body-only connectors (exclude arm connectors)
    if connector_number == "0" and dominant_bone in ['body', 'l_breast', 'r_breast']:
        # First try blazer body meshes  
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if 'body' in mesh_name and 'blazer' in mesh_name:
                    print(f"        Fallback: using blazer body mesh for connector {connector_number}")
                    return mesh_obj
            except (ReferenceError, AttributeError):
                continue
        
        # If no blazer, try female body meshes (naked mode)
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if 'body' in mesh_name and 'female' in mesh_name:
                    print(f"        Fallback: using female body mesh for connector {connector_number}")
                    return mesh_obj
            except (ReferenceError, AttributeError):
                continue
                
    # Fallback for arm connectors: find separate arm/hand meshes (not body!) - including body bone connectors
    elif connector_number == "1" and dominant_bone in ['l_arm1', 'r_arm1', 'l_arm2', 'r_arm2', 'l_hand', 'r_hand', 'body']:
        # Try to find any arm or hand mesh - CRITICAL: Include body bone connectors for shoulder connections
        for mesh_obj in mesh_objects:
            try:
                mesh_name = mesh_obj.name.lower()
                if (('arm' in mesh_name or 'hand' in mesh_name) and 
                    ('blazer' in mesh_name or 'female' in mesh_name)):
                    print(f"        Fallback: using arm/hand mesh {mesh_obj.name} for connector {connector_number} (including shoulder connections)")
                    return mesh_obj
            except (ReferenceError, AttributeError):
                continue
    
    return None


def _find_target_mesh_for_bone_group(bone_name, mesh_objects, connector_number):
    """Find the appropriate target mesh for a specific bone group using name patterns."""
    for mesh_obj in mesh_objects:
        try:
            _ = mesh_obj.name
            mesh_name = mesh_obj.name.lower()
            
            # Map bone names to target mesh patterns
            if bone_name in ['body', 'neck']:
                # Body/neck bones -> body blazer mesh
                if 'body' in mesh_name and 'blazer' in mesh_name and 'arm' not in mesh_name and 'hand' not in mesh_name:
                    print(f"        Found body target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
            elif bone_name in ['l_breast', 'r_breast']:
                # Breast bones -> body blazer mesh (they merge with body)
                if 'body' in mesh_name and 'blazer' in mesh_name and 'arm' not in mesh_name and 'hand' not in mesh_name:
                    print(f"        Found body target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
            elif bone_name in ['l_arm1', 'r_arm1']:
                # Arm bones -> arm blazer meshes
                bone_side = bone_name.split('_')[0]  # 'l' or 'r'
                if f'{bone_side}_arm1' in mesh_name and 'blazer' in mesh_name and 'hand' not in mesh_name and 'body' not in mesh_name:
                    print(f"        Found arm target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
            elif bone_name in ['l_hand', 'r_hand']:
                # Hand bones -> hand meshes
                bone_side = bone_name.split('_')[0]  # 'l' or 'r'
                if f'{bone_side}_hand' in mesh_name and 'arm' not in mesh_name:
                    print(f"        Found hand target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
            elif bone_name in ['waist']:
                # Waist bones -> skirt or waist meshes
                if ('skirt' in mesh_name and 'waist' in mesh_name) or ('waist' in mesh_name):
                    print(f"        Found waist target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
            elif bone_name in ['l_leg1', 'r_leg1']:
                # Leg bones -> leg skin meshes
                bone_side = bone_name.split('_')[0]  # 'l' or 'r'
                if f'{bone_side}_leg1' in mesh_name and 'female' in mesh_name:
                    print(f"        Found leg target for {bone_name}: {mesh_obj.name}")
                    return mesh_obj
                    
        except (ReferenceError, AttributeError):
            continue
    
    return None


def _merge_bone_group_with_target(connector_obj, bone_name, vertex_indices, face_indices, target_mesh, connector_name):
    """Create a sub-mesh from bone group vertices/faces and merge with target mesh."""
    try:
        import bpy
        import bmesh
    except ImportError:
        return False, []
    
    # Create a new temporary mesh containing only this bone group's geometry
    temp_mesh_name = f"{connector_name}_{bone_name}_part"
    temp_mesh = bpy.data.meshes.new(temp_mesh_name)
    
    # Extract vertices and faces for this bone group
    original_mesh = connector_obj.data
    
    # Get vertex coordinates for this bone group
    bone_vertices = []
    vertex_map = {}  # Map from original index to new index
    for new_idx, orig_idx in enumerate(vertex_indices):
        if orig_idx < len(original_mesh.vertices):
            vertex = original_mesh.vertices[orig_idx]
            bone_vertices.append([vertex.co.x, vertex.co.y, vertex.co.z])
            vertex_map[orig_idx] = new_idx
    
    # Get faces that belong to this bone group and remap vertex indices
    bone_faces = []
    for face_idx in face_indices:
        if face_idx < len(original_mesh.polygons):
            face = original_mesh.polygons[face_idx]
            # Check if ALL vertices of this face are in our bone group
            remapped_face = []
            valid_face = True
            for vertex_id in face.vertices:
                if vertex_id in vertex_map:
                    remapped_face.append(vertex_map[vertex_id])
                else:
                    # This vertex is not in our bone group - skip this face
                    valid_face = False
                    break
            
            if valid_face and len(remapped_face) >= 3:
                bone_faces.append(remapped_face)
    
    # DEBUG: Show what we found for this bone group
    print(f"        DEBUG: Bone group {bone_name} has {len(bone_vertices)} vertices, {len(bone_faces)} valid faces from {len(face_indices)} assigned faces")
    
    if not bone_vertices or not bone_faces:
        print(f"        ❌ No valid geometry for bone group {bone_name}")
        return False, []
    
    # Create the temporary mesh
    temp_mesh.from_pydata(bone_vertices, [], bone_faces)
    temp_mesh.update()
    
    # Create temporary mesh object
    temp_obj = bpy.data.objects.new(temp_mesh_name, temp_mesh)
    bpy.context.collection.objects.link(temp_obj)
    
    # Copy vertex groups from original connector
    for vg in connector_obj.vertex_groups:
        if vg.name == bone_name:
            new_vg = temp_obj.vertex_groups.new(name=vg.name)
            # Assign all vertices in the temp mesh to this bone group
            new_vg.add(list(range(len(bone_vertices))), 1.0, 'REPLACE')
            break
    
    # Now merge this temporary mesh with the target mesh
    try:
        # Select target mesh and temporary mesh
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        temp_obj.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        
        # Join the meshes
        bpy.ops.object.join()
        
        print(f"        ✅ Merged {bone_name} bone group ({len(bone_vertices)} vertices, {len(bone_faces)} faces) with {target_mesh.name}")
        return True, []
        
    except Exception as e:
        print(f"        ❌ Failed to merge bone group {bone_name}: {e}")
        # Clean up temporary object
        try:
            bpy.data.objects.remove(temp_obj, do_unlink=True)
        except:
            pass
        return False, []


def _legacy_try_merge_connector_with_body_mesh_OLD(connector_obj, mesh_objects, vertex_bone_names):
    """
    LEGACY FUNCTION - Try to merge a DynamicVisual connector with an appropriate body mesh based on its bone assignments.
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




def _determine_anatomical_group_from_mesh_name(mesh_name):
    """
    Determine the anatomical group from a mesh name.
    """
    mesh_lower = mesh_name.lower()
    
    if any(keyword in mesh_lower for keyword in ['head', 'face', 'hair', 'eye']):
        return 'head'
    elif any(keyword in mesh_lower for keyword in ['l_arm', 'left_arm', 'l_hand', 'left_hand']):
        return 'left_arm'
    elif any(keyword in mesh_lower for keyword in ['r_arm', 'right_arm', 'r_hand', 'right_hand']):
        return 'right_arm'
    elif any(keyword in mesh_lower for keyword in ['l_leg', 'left_leg', 'l_foot', 'left_foot']):
        return 'left_leg'
    elif any(keyword in mesh_lower for keyword in ['r_leg', 'right_leg', 'r_foot', 'right_foot']):
        return 'right_leg'
    elif any(keyword in mesh_lower for keyword in ['body', 'waist', 'breast', 'chest', 'torso', 'blazer', 'skirt']):
        return 'body'
    else:
        return 'body'  # Default fallback


