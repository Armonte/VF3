#!/usr/bin/env python3
"""
VF3 UV Handler - Preserves UV coordinates like the working export_ciel_to_gltf.py
"""

import bpy
import numpy as np

def preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, mesh_name):
    """
    Preserve UV coordinates from trimesh and apply to Blender mesh
    Based on the WORKING approach from export_ciel_to_gltf.py lines 1113-1124
    """
    
    # Check if trimesh has UV coordinates
    existing_uv = None
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        existing_uv = trimesh_mesh.visual.uv.copy()
        print(f"  Found existing UV coordinates from .X file: {existing_uv.shape}")
    else:
        print(f"  No UV coordinates found for {mesh_name}, will generate simple mapping")
    
    # Create UV layer in Blender
    if not blender_mesh.uv_layers:
        blender_mesh.uv_layers.new(name="UVMap")
    
    uv_layer = blender_mesh.uv_layers.active.data
    
    if existing_uv is not None:
        # Use the WORKING approach: preserve original UV coordinates
        apply_existing_uv_coordinates(blender_mesh, uv_layer, existing_uv, mesh_name)
    else:
        # Generate simple planar UV mapping as fallback
        generate_simple_uv_mapping(blender_mesh, uv_layer, mesh_name)


def apply_existing_uv_coordinates(blender_mesh, uv_layer, uv_coords, mesh_name):
    """
    Apply existing UV coordinates to Blender mesh
    This is the WORKING approach - don't overthink it!
    """
    
    print(f"  Applying {len(uv_coords)} UV coordinates to {mesh_name}")
    print(f"  Mesh has {len(blender_mesh.vertices)} vertices, {len(blender_mesh.loops)} loops")
    
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