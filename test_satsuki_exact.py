#!/usr/bin/env python3
"""
Test Satsuki head export using the EXACT working approach from commit 702507a3
"""

import os
import sys
import numpy as np
import trimesh

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from vf3_mesh_loader import load_mesh_with_full_materials

def test_satsuki_head():
    """Test loading Satsuki's head with exact UV preservation"""
    
    head_path = "/mnt/c/dev/loot/vf3/data/satsuki/head.X"
    
    print(f"Loading Satsuki head: {head_path}")
    
    # Load the mesh using our loader
    mesh_data = load_mesh_with_full_materials(head_path)
    print(f"Mesh data keys: {mesh_data.keys()}")
    mesh = mesh_data['mesh']
    
    print(f"Loaded mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    
    # Check UV coordinates
    if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
        uv_coords = mesh.visual.uv
        print(f"UV coordinates: {len(uv_coords)} UVs")
        print(f"UV shape: {uv_coords.shape}")
        print(f"UV range U: {uv_coords[:, 0].min():.4f} to {uv_coords[:, 0].max():.4f}")
        print(f"UV range V: {uv_coords[:, 1].min():.4f} to {uv_coords[:, 1].max():.4f}")
        
        # Show first few UV coordinates
        print("First 10 UV coordinates:")
        for i in range(min(10, len(uv_coords))):
            print(f"  UV[{i}]: ({uv_coords[i][0]:.6f}, {uv_coords[i][1]:.6f})")
    else:
        print("No UV coordinates found!")
    
    # Export directly using trimesh - this should work perfectly
    output_path = "satsuki_head_test_exact.glb"
    
    # Apply the EXACT working approach: preserve UV coordinates exactly
    if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
        existing_uv = mesh.visual.uv.copy()
        print(f"Preserving existing UV coordinates from .X file ({existing_uv.shape})")
        
        # This is what the working version does - preserve UVs exactly
        mesh.visual.uv = existing_uv
        print("Restored UV coordinates from .X file")
    
    # Export directly
    mesh.export(output_path)
    print(f"✅ Exported: {output_path}")
    
    return mesh

if __name__ == "__main__":
    test_satsuki_head()