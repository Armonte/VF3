#!/usr/bin/env python3
"""
VF3 UV Handler - Preserves UV coordinates like the working export_ciel_to_gltf.py
"""

import bpy
import numpy as np

def preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, mesh_name, mesh_info=None):
    """
    Preserve UV coordinates EXACTLY as they are from trimesh - like working export_ciel_to_gltf.py
    NO MODIFICATIONS, NO FLIPS, NO COMPLEX LOGIC
    """
    
    # Check if trimesh has UV coordinates
    existing_uv = None
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        existing_uv = trimesh_mesh.visual.uv.copy()
        print(f"  UV coordinates from .X file: {len(existing_uv)} UVs for {len(blender_mesh.vertices)} vertices")
    else:
        print(f"  No UV coordinates found for {mesh_name}, will generate simple mapping")
    
    # Create UV layer in Blender
    if not blender_mesh.uv_layers:
        blender_mesh.uv_layers.new(name="UVMap")
    
    uv_layer = blender_mesh.uv_layers.active.data
    
    if existing_uv is not None:
        # Apply UV coordinates EXACTLY like working export_ciel_to_gltf.py
        apply_uv_coordinates_exact(blender_mesh, uv_layer, existing_uv, mesh_name)
    else:
        # Generate simple planar UV mapping as fallback
        generate_simple_uv_mapping(blender_mesh, uv_layer, mesh_name)


def apply_uv_coordinates_exact(blender_mesh, uv_layer, uv_coords, mesh_name):
    """
    Apply UV coordinates EXACTLY like the working export_ciel_to_gltf.py
    No modifications, no flips, just preserve exactly
    """
    
    print(f"  Exact UV mapping: {len(uv_coords)} UVs to {len(blender_mesh.vertices)} vertices")
    
    loop_index = 0
    
    # Simple per-vertex mapping - exactly like working version
    for poly in blender_mesh.polygons:
        for loop_idx in poly.loop_indices:
            vertex_idx = blender_mesh.loops[loop_idx].vertex_index
            
            # Use vertex index directly, wrap if needed
            if vertex_idx < len(uv_coords):
                u, v = uv_coords[vertex_idx]
            else:
                # Wrap around if vertex index exceeds UV count
                uv_idx = vertex_idx % len(uv_coords)
                u, v = uv_coords[uv_idx]
            
            # Apply UV coordinates EXACTLY as they are - no modifications
            uv_layer[loop_index].uv = (float(u), float(v))
            loop_index += 1
    
    print(f"  ✅ Applied exact UV mapping to {mesh_name}")


def apply_uv_coordinates_simple(blender_mesh, uv_layer, uv_coords, mesh_name):
    """
    Apply UV coordinates simply - just preserve them directly from .X file
    Works with post-deduplication vertex counts (fixes Satsuki)
    """
    
    print(f"  Simple UV mapping: {len(uv_coords)} UVs to {len(blender_mesh.vertices)} vertices")
    
    # Special debug for Satsuki head
    if "satsuki" in mesh_name.lower() and "head" in mesh_name.lower():
        print(f"  🔧 SATSUKI HEAD DEBUG:")
        print(f"    UV coords: {len(uv_coords)}, Vertices: {len(blender_mesh.vertices)}, Loops: {len(uv_layer)}")
        print(f"    First 5 UV coords: {uv_coords[:5]}")
        print(f"    Last 5 UV coords: {uv_coords[-5:]}")
    
    # If UV count matches vertex count, use direct mapping
    if len(uv_coords) == len(blender_mesh.vertices):
        print(f"  Perfect match: direct vertex->UV mapping")
        loop_index = 0
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                if vertex_idx < len(uv_coords):
                    u, v = uv_coords[vertex_idx]
                    # For Satsuki, don't flip V coordinate - try original first
                    if "satsuki" in mesh_name.lower() and "head" in mesh_name.lower():
                        uv_layer[loop_index].uv = (float(u), float(v))  # No flip for Satsuki
                    else:
                        uv_layer[loop_index].uv = (float(u), 1.0 - float(v))  # DirectX->Blender V-flip
                loop_index += 1
    
    # If UV count doesn't match, use per-loop mapping for Satsuki
    elif "satsuki" in mesh_name.lower() and "head" in mesh_name.lower():
        print(f"  🔧 SATSUKI SPECIAL: Using per-loop UV mapping")
        
        # Try per-loop mapping instead of per-vertex
        if len(uv_coords) >= len(uv_layer):
            for i in range(len(uv_layer)):
                u, v = uv_coords[i]
                uv_layer[i].uv = (float(u), 1.0 - float(v))  # DirectX->Blender V-flip
            print(f"    Applied {len(uv_layer)} UVs via per-loop mapping")
        else:
            print(f"    Not enough UVs for per-loop mapping, falling back to wrapped")
            loop_index = 0
            for poly in blender_mesh.polygons:
                for loop_idx in poly.loop_indices:
                    vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                    uv_idx = vertex_idx % len(uv_coords)
                    u, v = uv_coords[uv_idx]
                    # For Satsuki, try no V-flip first
                    if "satsuki" in mesh_name.lower() and "head" in mesh_name.lower():
                        uv_layer[loop_index].uv = (float(u), float(v))  # No flip for Satsuki
                    else:
                        uv_layer[loop_index].uv = (float(u), 1.0 - float(v))  # DirectX->Blender V-flip
                    loop_index += 1
    
    # Default: UV count doesn't match, use modulo mapping (most characters)
    else:
        print(f"  UV count mismatch: using wrapped mapping")
        loop_index = 0
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                uv_idx = vertex_idx % len(uv_coords)
                u, v = uv_coords[uv_idx]
                uv_layer[loop_index].uv = (float(u), 1.0 - float(v))  # DirectX->Blender V-flip
                loop_index += 1
    
    print(f"  ✅ Applied simple UV mapping to {mesh_name}")


def apply_simple_uv_coordinates(blender_mesh, uv_layer, uv_coords, mesh_name, mesh_info=None):
    """
    Apply UV coordinates SIMPLY - just preserve them from the .X file.
    No complex logic, no face materials, just basic UV mapping.
    """
    
    print(f"  Simple UV mapping: {len(uv_coords)} UVs to {len(blender_mesh.vertices)} vertices")
    
    loop_index = 0
    
    # Method 1: Per-vertex UV mapping (most common case)
    if len(uv_coords) == len(blender_mesh.vertices):
        print(f"  Perfect match: {len(uv_coords)} UVs = {len(blender_mesh.vertices)} vertices")
        
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                if vertex_idx < len(uv_coords):
                    u, v = uv_coords[vertex_idx]
                    uv_layer[loop_index].uv = (float(u), float(v))
                loop_index += 1
                
        print(f"  ✅ Applied simple UV coordinates to {mesh_name}")
        
    # Method 2: Per-loop UV mapping
    elif len(uv_coords) == len(uv_layer):
        print(f"  Loop mapping: {len(uv_coords)} UVs = {len(uv_layer)} loops")
        
        for i, uv_coord in enumerate(uv_coords):
            u, v = uv_coord
            uv_layer[i].uv = (float(u), float(v))
            
        print(f"  ✅ Applied simple UV coordinates to {mesh_name}")
        
    # Method 3: Handle mismatches intelligently 
    else:
        print(f"  Mismatch: {len(uv_coords)} UVs vs {len(blender_mesh.vertices)} vertices")
        
        # Special case: Satsuki head (384 UVs vs 382 vertices after deduplication)
        if "satsuki" in mesh_name.lower() and "head" in mesh_name.lower() and len(uv_coords) == 384 and len(blender_mesh.vertices) == 382:
            print(f"  🔧 SATSUKI FIX: Using face-based UV mapping for 384 UVs -> 382 vertices")
            # Use the original face-based approach since simple trimming isn't working
            
            # Get face materials if available
            face_materials = None
            if mesh_info and 'face_materials' in mesh_info:
                face_materials = mesh_info['face_materials']
                print(f"    Found {len(face_materials)} face materials for Satsuki")
            
            if face_materials and len(face_materials) > 0:
                # Use face-based UV mapping - this should handle the 384->382 mapping correctly
                apply_face_based_uv_coordinates(blender_mesh, uv_layer, uv_coords, face_materials, mesh_name)
            else:
                # Fallback: Per-loop UV mapping instead of per-vertex
                print(f"    Using per-loop UV mapping as fallback")
                if len(uv_coords) >= len(uv_layer):
                    for i in range(len(uv_layer)):
                        uv_coord = uv_coords[i % len(uv_coords)]
                        u, v = uv_coord
                        uv_layer[i].uv = (float(u), float(v))
                    print(f"  ✅ Applied per-loop UV coordinates to {mesh_name}")
                else:
                    print(f"  ⚠️ Not enough UVs for per-loop mapping")
            return  # Skip the regular wrapping logic
        else:
            # General wrapping for other mismatches
            for poly in blender_mesh.polygons:
                for loop_idx in poly.loop_indices:
                    vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                    # Use modulo to wrap around UV coordinates
                    uv_idx = vertex_idx % len(uv_coords)
                    u, v = uv_coords[uv_idx]
                    uv_layer[loop_index].uv = (float(u), float(v))
                    loop_index += 1
                    
            print(f"  ⚠️ Applied UV coordinates with wrapping to {mesh_name}")


def apply_face_based_uv_coordinates(blender_mesh, uv_layer, uv_coords, face_materials, mesh_name):
    """
    Apply UV coordinates using VF3-style per-face mapping based on face materials.
    This handles cases where different faces use different textures/UV regions.
    """
    
    print(f"  Applying face-based UV coordinates: {len(uv_coords)} UVs, {len(face_materials)} faces")
    print(f"  Mesh has {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} polygons")
    
    # Handle Satsuki's UV/vertex count mismatch specifically
    if "satsuki" in mesh_name.lower() and "head" in mesh_name.lower() and len(uv_coords) == 384 and len(blender_mesh.vertices) == 382:
        print(f"  🔧 FIXING SATSUKI UV MISMATCH: {len(uv_coords)} UVs vs {len(blender_mesh.vertices)} vertices")
        print(f"  Using face-based mapping to handle extra UVs correctly")
        # Don't trim - use all UVs and map them based on face materials
    
    # Build a mapping from original face indices to triangulated face indices
    face_mapping = {}
    blender_face_idx = 0
    
    for original_face_idx, material_idx in enumerate(face_materials):
        if original_face_idx < len(blender_mesh.polygons):
            face_mapping[original_face_idx] = blender_face_idx
            blender_face_idx += 1
    
    loop_index = 0
    uv_index = 0
    
    for poly_idx, poly in enumerate(blender_mesh.polygons):
        # Get the material for this face
        original_face_idx = poly_idx
        if original_face_idx < len(face_materials):
            material_idx = face_materials[original_face_idx]
        else:
            material_idx = 0
            
        # For each vertex in this face, assign UV coordinates
        for loop_idx in poly.loop_indices:
            vertex_idx = blender_mesh.loops[loop_idx].vertex_index
            
            # Use face-based UV assignment instead of just vertex index
            # This allows for different UV coordinates per face even for shared vertices
            if uv_index < len(uv_coords):
                u, v = uv_coords[uv_index]
                uv_layer[loop_index].uv = (float(u), float(v))
                uv_index += 1
            elif vertex_idx < len(uv_coords):
                # Fallback to vertex-based mapping
                u, v = uv_coords[vertex_idx]
                uv_layer[loop_index].uv = (float(u), float(v))
            else:
                # Wrap around if we run out of UVs
                uv_idx = vertex_idx % len(uv_coords)
                u, v = uv_coords[uv_idx]
                uv_layer[loop_index].uv = (float(u), float(v))
                
            loop_index += 1
    
    print(f"  ✅ Applied face-based UV mapping to {mesh_name} (used {uv_index}/{len(uv_coords)} UVs)")


def apply_existing_uv_coordinates_exact(blender_mesh, uv_layer, uv_coords, mesh_name):
    """
    Apply UV coordinates EXACTLY as they are from the .X file - the WORKING approach.
    No modifications, no normalization, no fixes - just preserve exactly.
    """
    
    print(f"  Applying {len(uv_coords)} UV coordinates to {mesh_name}")
    print(f"  Mesh has {len(blender_mesh.vertices)} vertices, {len(blender_mesh.loops)} loops")
    
    # DEBUG: Compare Satsuki vs working characters
    if "head" in mesh_name.lower():
        import numpy as np
        uv_array = np.array(uv_coords)
        min_u, min_v = uv_array.min(axis=0)
        max_u, max_v = uv_array.max(axis=0)
        mean_u, mean_v = uv_array.mean(axis=0)
        
        character_name = "UNKNOWN"
        if "satsuki" in mesh_name.lower():
            character_name = "SATSUKI"
        elif "hisui" in mesh_name.lower():
            character_name = "HISUI" 
        elif "ciel" in mesh_name.lower():
            character_name = "CIEL"
        elif "arcueid" in mesh_name.lower():
            character_name = "ARCUEID"
            
        print(f"  🔍 {character_name} HEAD UV STATS:")
        print(f"    UV Range: U({min_u:.4f} to {max_u:.4f}) V({min_v:.4f} to {max_v:.4f})")
        print(f"    UV Center: U({mean_u:.4f}) V({mean_v:.4f})")
        print(f"    Sample UVs: {uv_coords[:5]}")
        
        # Check for problematic patterns
        out_of_range = np.sum((uv_array < 0) | (uv_array > 1))
        if out_of_range > 0:
            print(f"    ⚠️ {out_of_range}/{len(uv_coords)} UV coords outside 0-1 range")
        
        # Check distribution
        if character_name == "SATSUKI":
            print(f"    🔧 SATSUKI DEBUG: Comparing against working characters...")
            # Sample more coordinates for analysis
            print(f"    First 10 UVs: {uv_coords[:10]}")
            print(f"    Last 10 UVs: {uv_coords[-10:]}")
            
            # Check if UVs are clustered weirdly
            u_range = max_u - min_u
            v_range = max_v - min_v
            if u_range < 0.1 or v_range < 0.1:
                print(f"    ⚠️ UV coordinates are too clustered! U range: {u_range:.4f}, V range: {v_range:.4f}")
            
            # Check for spiral patterns
            diffs = np.diff(uv_array, axis=0)
            large_jumps = np.sum(np.linalg.norm(diffs, axis=1) > 0.5)
            if large_jumps > len(uv_coords) * 0.05:
                print(f"    ⚠️ Potential spiral pattern: {large_jumps} large UV jumps")
    
    # Use the EXACT approach from the working export_ciel_to_gltf.py:
    # Just preserve the UV coordinates as they are from the .X file
    # Don't modify them AT ALL!
    
    loop_index = 0
    
    # Method 1: Per-vertex UV mapping (most common case)
    if len(uv_coords) == len(blender_mesh.vertices):
        print(f"  Using per-vertex UV mapping ({len(uv_coords)} UVs = {len(blender_mesh.vertices)} vertices)")
        
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                if vertex_idx < len(uv_coords):
                    u, v = uv_coords[vertex_idx]
                    # Use original UV coordinates directly (working approach)
                    uv_layer[loop_index].uv = (float(u), float(v))
                loop_index += 1
                
        print(f"  ✅ Successfully applied UV coordinates to {mesh_name}")
        
    # Method 2: Per-loop UV mapping
    elif len(uv_coords) == len(uv_layer):
        print(f"  Using per-loop UV mapping ({len(uv_coords)} UVs = {len(uv_layer)} loops)")
        
        for i, uv_coord in enumerate(uv_coords):
            u, v = uv_coord
            # Use original UV coordinates directly (working approach)
            uv_layer[i].uv = (float(u), float(v))
            
        print(f"  ✅ Successfully applied UV coordinates to {mesh_name}")
        
    # Method 3: Handle Satsuki's specific UV/vertex count mismatch
    elif "satsuki" in mesh_name.lower() and "head" in mesh_name.lower() and len(uv_coords) == 384 and len(blender_mesh.vertices) == 382:
        print(f"  🔧 FIXING SATSUKI UV MISMATCH: {len(uv_coords)} UVs vs {len(blender_mesh.vertices)} vertices")
        print(f"  Trimming UV coordinates to match vertex count")
        
        # Trim the UV coordinates to match vertex count (remove the 2 extra UVs)
        trimmed_uv_coords = uv_coords[:len(blender_mesh.vertices)]
        
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                if vertex_idx < len(trimmed_uv_coords):
                    u, v = trimmed_uv_coords[vertex_idx]
                    # Use original UV coordinates directly (working approach) 
                    uv_layer[loop_index].uv = (float(u), float(v))
                loop_index += 1
                
        print(f"  ✅ Fixed Satsuki UV mismatch by trimming to {len(trimmed_uv_coords)} UVs")
        
    # Method 4: Fallback with wrapping (for other mismatched counts)
    else:
        print(f"  UV count mismatch: {len(uv_coords)} UVs vs {len(blender_mesh.vertices)} vertices vs {len(uv_layer)} loops")
        print(f"  Using fallback: wrap UV coordinates to fit")
        
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                # Use modulo to wrap around UV coordinates
                uv_idx = vertex_idx % len(uv_coords)
                u, v = uv_coords[uv_idx]
                # Use original UV coordinates directly (working approach)
                uv_layer[loop_index].uv = (float(u), float(v))
                loop_index += 1
                
        print(f"  ⚠️ Applied UV coordinates with wrapping to {mesh_name}")


def apply_existing_uv_coordinates(blender_mesh, uv_layer, uv_coords, mesh_name):
    """
    Apply existing UV coordinates to Blender mesh
    This is the WORKING approach - don't overthink it!
    """
    
    print(f"  Applying {len(uv_coords)} UV coordinates to {mesh_name}")
    print(f"  Mesh has {len(blender_mesh.vertices)} vertices, {len(blender_mesh.loops)} loops")
    
    # CRITICAL FIX: Use the WORKING approach from export_ciel_to_gltf.py
    # Just preserve the UV coordinates EXACTLY as they are from the .X file
    # Don't modify them AT ALL - that's what was working before!
    
    # The working approach from export_ciel_to_gltf.py:
    # Just preserve the UV coordinates as they are from the .X file
    # trimesh handles this correctly, we just need to not break it
    
    loop_index = 0
    
    # Method 1: Per-vertex UV mapping (most common case)
    if len(uv_coords) == len(blender_mesh.vertices):
        print(f"  Using per-vertex UV mapping ({len(uv_coords)} UVs = {len(blender_mesh.vertices)} vertices)")
        
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                if vertex_idx < len(uv_coords):
                    u, v = uv_coords[vertex_idx]
                    # Don't flip or modify - use original coordinates
                    uv_layer[loop_index].uv = (u, v)
                loop_index += 1
                
        print(f"  ✅ Applied per-vertex UV coordinates to {mesh_name}")
        
    # Method 2: Per-loop UV mapping
    elif len(uv_coords) == len(uv_layer):
        print(f"  Using per-loop UV mapping ({len(uv_coords)} UVs = {len(uv_layer)} loops)")
        
        for i, uv_coord in enumerate(uv_coords):
            u, v = uv_coord
            uv_layer[i].uv = (u, v)
            
        print(f"  ✅ Applied per-loop UV coordinates to {mesh_name}")
        
    # Method 3: Try to handle the problematic case more simply
    else:
        print(f"  UV count mismatch: {len(uv_coords)} UVs vs {len(blender_mesh.vertices)} vertices vs {len(uv_layer)} loops")
        print(f"  Using fallback: wrap UV coordinates to fit")
        
        # Simple wrapping approach
        for poly in blender_mesh.polygons:
            for loop_idx in poly.loop_indices:
                vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                # Use modulo to wrap around UV coordinates
                uv_idx = vertex_idx % len(uv_coords)
                u, v = uv_coords[uv_idx]
                uv_layer[loop_index].uv = (u, v)
                loop_index += 1
                
        print(f"  ⚠️ Applied UV coordinates with wrapping to {mesh_name}")


def generate_simple_uv_mapping(blender_mesh, uv_layer, mesh_name):
    """
    Generate simple planar UV mapping as fallback
    Based on export_ciel_to_gltf.py lines 1127-1137
    """
    
    print(f"  Generating simple UV mapping for {mesh_name}")
    
    # Get mesh bounds for planar mapping
    vertices = [v.co for v in blender_mesh.vertices]
    if not vertices:
        return
    
    # Calculate bounds
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    
    width = max_x - min_x
    height = max_y - min_y
    
    # Apply planar mapping
    loop_index = 0
    for poly in blender_mesh.polygons:
        for loop_idx in poly.loop_indices:
            vertex_idx = blender_mesh.loops[loop_idx].vertex_index
            vertex = blender_mesh.vertices[vertex_idx]
            
            # Normalize to 0-1 range
            u = (vertex.co.x - min_x) / width if width > 0 else 0.5
            v = (vertex.co.y - min_y) / height if height > 0 else 0.5
            
            # Clamp to 0-1 range
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))
            
            uv_layer[loop_index].uv = (u, v)
            loop_index += 1
    
    print(f"  ✅ Generated planar UV mapping for {mesh_name}")


def _normalize_problematic_uv_coordinates(uv_coords):
    """
    Fix problematic UV coordinates that cause golden ratio spiral effect.
    Common issues: coordinates outside 0-1 range, wrong scaling, coordinate system differences.
    """
    import numpy as np
    
    uv_array = np.array(uv_coords)
    original_shape = uv_array.shape
    
    # Fix 1: Clamp coordinates to 0-1 range (fixes wrapping issues)
    clamped = np.clip(uv_array, 0.0, 1.0)
    
    # Fix 2: Check if coordinates need flipping (common DirectX vs OpenGL issue)
    # If most V coordinates are near 1, flip V axis
    v_coords = uv_array[:, 1]
    if np.mean(v_coords) > 0.7:  # Most coordinates in upper region
        print(f"    🔧 Flipping V coordinates (DirectX->OpenGL conversion)")
        clamped[:, 1] = 1.0 - clamped[:, 1]
    
    # Fix 3: Check for scale issues (coordinates clustered in small region)
    u_range = np.max(uv_array[:, 0]) - np.min(uv_array[:, 0])
    v_range = np.max(uv_array[:, 1]) - np.min(uv_array[:, 1])
    
    if u_range < 0.3 or v_range < 0.3:  # Coordinates too clustered
        print(f"    🔧 Expanding UV range (was U:{u_range:.3f}, V:{v_range:.3f})")
        
        # Expand to use more of the 0-1 space
        u_coords = clamped[:, 0]
        v_coords = clamped[:, 1]
        
        # Normalize to 0-1 range with some padding
        if u_range > 0:
            u_min, u_max = np.min(u_coords), np.max(u_coords)
            clamped[:, 0] = (u_coords - u_min) / (u_max - u_min) * 0.8 + 0.1
        
        if v_range > 0:
            v_min, v_max = np.min(v_coords), np.max(v_coords)
            clamped[:, 1] = (v_coords - v_min) / (v_max - v_min) * 0.8 + 0.1
    
    # Convert back to list of tuples
    return [(float(u), float(v)) for u, v in clamped]


def _normalize_satsuki_multi_texture_uvs(uv_coords, mesh_name):
    """
    Fix Satsuki's head UV coordinates which have multi-texture issues.
    Satsuki has stkface.bmp and stkface2.bmp textures, causing UV coordinate confusion.
    """
    import numpy as np
    
    uv_array = np.array(uv_coords)
    print(f"    🔍 Analyzing Satsuki multi-texture UV layout...")
    
    # Satsuki-specific fix: The UV coordinates seem to be mapped to two different texture sheets
    # The "golden ratio spiral" effect is likely caused by UV coordinates intended for 
    # different textures being applied to the same geometry
    
    # Strategy 1: Split UV coordinates into two regions and normalize each separately
    u_coords = uv_array[:, 0] 
    v_coords = uv_array[:, 1]
    
    # Check if there are two distinct UV clusters (indicating multi-texture regions)
    u_median = np.median(u_coords)
    v_median = np.median(v_coords)
    
    # Identify potential texture regions
    region1_mask = (u_coords <= u_median) | (v_coords <= v_median)
    region2_mask = ~region1_mask
    
    region1_count = np.sum(region1_mask)
    region2_count = np.sum(region2_mask)
    
    print(f"    🔍 UV region analysis: Region1={region1_count}, Region2={region2_count}")
    
    if region2_count > 10:  # If we have significant second region
        print(f"    🔧 Multi-texture detected: normalizing regions separately")
        
        # Normalize each region to fit in 0-1 space properly
        result_uv = uv_array.copy()
        
        # Region 1: Normalize to left/lower portion (primary face texture)
        if region1_count > 0:
            region1_u = u_coords[region1_mask]
            region1_v = v_coords[region1_mask]
            
            if len(region1_u) > 0:
                u_min, u_max = region1_u.min(), region1_u.max()
                v_min, v_max = region1_v.min(), region1_v.max()
                
                if u_max > u_min:
                    result_uv[region1_mask, 0] = (region1_u - u_min) / (u_max - u_min) * 0.45 + 0.02
                if v_max > v_min:
                    result_uv[region1_mask, 1] = (region1_v - v_min) / (v_max - v_min) * 0.45 + 0.02
        
        # Region 2: Normalize to right/upper portion (secondary details) 
        if region2_count > 0:
            region2_u = u_coords[region2_mask]
            region2_v = v_coords[region2_mask]
            
            if len(region2_u) > 0:
                u_min, u_max = region2_u.min(), region2_u.max()
                v_min, v_max = region2_v.min(), region2_v.max()
                
                if u_max > u_min:
                    result_uv[region2_mask, 0] = (region2_u - u_min) / (u_max - u_min) * 0.45 + 0.53
                if v_max > v_min:
                    result_uv[region2_mask, 1] = (region2_v - v_min) / (v_max - v_min) * 0.45 + 0.53
                    
        print(f"    ✅ Applied multi-texture UV normalization")
        return [(float(u), float(v)) for u, v in result_uv]
    
    else:
        # Fallback: Use standard normalization
        print(f"    🔧 Single texture detected: applying standard normalization")
        return _normalize_problematic_uv_coordinates(uv_coords)