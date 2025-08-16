#!/usr/bin/env python3
"""
Fix body connector contamination by splitting arm vertices from body connector.
"""

def create_arm_targeting_fix():
    """Create a fix for the body connector containing arm geometry."""
    print("=== FIXING BODY CONNECTOR CONTAMINATION ===")
    print()
    
    print("PROBLEM IDENTIFIED:")
    print("  - Connector 0 (body, 124 vertices) contains:")
    print("    * 36 body vertices ✅ (correct)")
    print("    * 13+13 = 26 breast vertices ✅ (correct)")
    print("    * 12+12 = 24 arm1/arm2 vertices ❌ (should target arms)")
    print("    * 4+4 = 8 hand vertices ❌ (should target hands)")
    print("    * 6 waist vertices ❌ (should target waist)")
    print("    * TOTAL: 36 + 26 + 24 + 8 + 6 = 100 problematic vertices")
    print()
    
    print("SOLUTION: Split connector 0 by bone groups during merge")
    print("  1. Extract arm vertices (l_arm1, r_arm1, l_arm2, r_arm2) -> target arm meshes")
    print("  2. Extract hand vertices (l_hand, r_hand) -> target hand meshes")  
    print("  3. Extract waist vertices (waist) -> target waist meshes")
    print("  4. Keep body/breast vertices (body, l_breast, r_breast) -> target body mesh")
    print()
    
    print("IMPLEMENTATION APPROACH:")
    print("  - Modify the connector merging logic to split by bone groups")
    print("  - Create bone-based vertex filtering in the merge function")
    print("  - Target each bone group to appropriate existing meshes")

def generate_fix_code():
    """Generate the code fix for body connector splitting."""
    print("=== CONNECTOR SPLITTING IMPLEMENTATION ===")
    print()
    
    fix_code = '''
def _split_connector_by_bone_groups(connector_obj, vertex_bone_names, mesh_objects):
    """
    Split a connector mesh by bone groups and merge each group with appropriate targets.
    This fixes the issue where body connector contains arm/hand/waist geometry.
    """
    try:
        import bpy
        import bmesh
        from mathutils import Vector
    except ImportError:
        return False
    
    # Group vertices by bone
    bone_groups = {}
    for i, bone_name in enumerate(vertex_bone_names):
        if bone_name not in bone_groups:
            bone_groups[bone_name] = []
        bone_groups[bone_name].append(i)
    
    print(f"      🔧 SPLITTING: Found {len(bone_groups)} bone groups in connector")
    for bone, vertices in bone_groups.items():
        print(f"        {bone}: {len(vertices)} vertices")
    
    # Define bone group targeting
    bone_group_targets = {
        'body': ['body_satsuki.blazer', 'body_female'],
        'l_breast': ['body_satsuki.blazer', 'l_breast_satsuki.blazer_lb'],
        'r_breast': ['body_satsuki.blazer', 'r_breast_satsuki.blazer_rb'],
        'l_arm1': ['l_arm1_satsuki.l_blazer1', 'l_arm1_female'],
        'r_arm1': ['r_arm1_satsuki.r_blazer1', 'r_arm1_female'],
        'l_arm2': ['l_arm2_satsuki.l_blazer2', 'l_arm2_female'],
        'r_arm2': ['r_arm2_satsuki.r_blazer2', 'r_arm2_female'],
        'l_hand': ['l_hand_satsuki.l_blazer3', 'l_hand_female.l_hand'],
        'r_hand': ['r_hand_satsuki.r_blazer3', 'r_hand_female.r_hand'],
        'waist': ['waist_satsuki.blazer2', 'waist_female.waist', 'waist_satsuki.skirta']
    }
    
    # Get existing mesh names for targeting
    existing_mesh_names = [mesh_obj.name for mesh_obj in mesh_objects if hasattr(mesh_obj, 'name')]
    
    successful_merges = []
    
    # Process each bone group
    for bone_name, vertex_indices in bone_groups.items():
        target_patterns = bone_group_targets.get(bone_name, [])
        if not target_patterns:
            print(f"        ⚠️  No targeting pattern for bone {bone_name}")
            continue
        
        # Find target meshes for this bone group
        target_meshes = []
        for mesh_obj in mesh_objects:
            mesh_name_lower = mesh_obj.name.lower()
            for pattern in target_patterns:
                if pattern.lower() in mesh_name_lower:
                    target_meshes.append(mesh_obj)
                    break
        
        if not target_meshes:
            print(f"        ❌ No target meshes found for bone group {bone_name}")
            continue
        
        # Create sub-mesh for this bone group
        bone_group_mesh = _extract_vertices_to_new_mesh(
            connector_obj, vertex_indices, f"{connector_obj.name}_{bone_name}"
        )
        
        if bone_group_mesh:
            # Merge with target
            success = _merge_submesh_with_targets(bone_group_mesh, target_meshes)
            if success:
                successful_merges.append(bone_name)
                print(f"        ✅ Merged {bone_name} group ({len(vertex_indices)} vertices) with {len(target_meshes)} targets")
            else:
                print(f"        ❌ Failed to merge {bone_name} group")
    
    return len(successful_merges) > 0

def _extract_vertices_to_new_mesh(source_obj, vertex_indices, new_name):
    """Extract specific vertices to create a new mesh."""
    # Implementation would create a new mesh containing only the specified vertices
    # This is a complex operation involving bmesh operations
    pass

def _merge_submesh_with_targets(submesh_obj, target_meshes):
    """Merge a submesh with target meshes."""
    # Implementation would merge the submesh with the first available target
    # Similar to existing merge logic but for smaller submeshes
    pass
'''
    
    print("Code structure for fixing body connector contamination:")
    print("```python")
    print(fix_code)
    print("```")
    print()
    
    print("INTEGRATION POINT:")
    print("  - Add this to _try_merge_connector_with_body_mesh()")
    print("  - Check if connector is connector_0 and has mixed bone groups")
    print("  - If so, use splitting approach instead of direct merge")

if __name__ == "__main__":
    create_arm_targeting_fix()
    print()
    generate_fix_code()