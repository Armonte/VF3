#!/usr/bin/env python3
"""
Debug script to compare UV coordinates between working and current systems
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_working_system():
    """Test UV coordinates from working export_ciel_to_gltf.py"""
    print("=== TESTING WORKING SYSTEM (export_ciel_to_gltf.py) ===")
    
    from vf3_xfile_parser import load_mesh_with_materials
    
    # Load Satsuki head using the same parser
    print("Loading Satsuki head with working system...")
    mesh_info = load_mesh_with_materials('data/satsuki/head.x')
    
    if mesh_info['mesh'] and hasattr(mesh_info['mesh'].visual, 'uv') and mesh_info['mesh'].visual.uv is not None:
        uv_coords = mesh_info['mesh'].visual.uv
        print(f"  Working system UV count: {len(uv_coords)}")
        print(f"  Working system first 10 UVs: {uv_coords[:10].tolist()}")
        print(f"  Working system UV range: U({uv_coords[:, 0].min():.6f}-{uv_coords[:, 0].max():.6f}) V({uv_coords[:, 1].min():.6f}-{uv_coords[:, 1].max():.6f})")
        return uv_coords
    else:
        print("  ERROR: No UV coordinates in working system")
        return None

def test_current_system():
    """Test UV coordinates from current modular system"""
    print("\n=== TESTING CURRENT SYSTEM (vf3_blender_exporter_modular.py) ===")
    
    from vf3_mesh_loader import load_mesh_with_full_materials
    
    # Load Satsuki head using current system
    print("Loading Satsuki head with current system...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    
    if mesh_info['mesh'] and hasattr(mesh_info['mesh'].visual, 'uv') and mesh_info['mesh'].visual.uv is not None:
        uv_coords = mesh_info['mesh'].visual.uv
        print(f"  Current system UV count: {len(uv_coords)}")
        print(f"  Current system first 10 UVs: {uv_coords[:10].tolist()}")
        print(f"  Current system UV range: U({uv_coords[:, 0].min():.6f}-{uv_coords[:, 0].max():.6f}) V({uv_coords[:, 1].min():.6f}-{uv_coords[:, 1].max():.6f})")
        return uv_coords
    else:
        print("  ERROR: No UV coordinates in current system")
        return None

def compare_uv_coordinates(working_uvs, current_uvs):
    """Compare UV coordinates between systems"""
    print("\n=== COMPARISON ===")
    
    if working_uvs is None or current_uvs is None:
        print("Cannot compare - one or both systems failed to load UVs")
        return
    
    if len(working_uvs) != len(current_uvs):
        print(f"⚠️ UV count mismatch: working={len(working_uvs)}, current={len(current_uvs)}")
        return
    
    # Compare first 10 coordinates exactly
    print("Comparing first 10 UV coordinates:")
    for i in range(min(10, len(working_uvs))):
        w_u, w_v = working_uvs[i]
        c_u, c_v = current_uvs[i]
        diff_u = abs(w_u - c_u)
        diff_v = abs(w_v - c_v)
        print(f"  UV {i}: working=({w_u:.6f}, {w_v:.6f}) current=({c_u:.6f}, {c_v:.6f}) diff=({diff_u:.8f}, {diff_v:.8f})")
        
        if diff_u > 1e-6 or diff_v > 1e-6:
            print(f"    ⚠️ SIGNIFICANT DIFFERENCE detected at UV {i}")
    
    # Overall statistics
    import numpy as np
    working_arr = np.array(working_uvs)
    current_arr = np.array(current_uvs)
    
    diff_arr = np.abs(working_arr - current_arr)
    max_diff = np.max(diff_arr)
    mean_diff = np.mean(diff_arr)
    
    print(f"\nOverall UV difference statistics:")
    print(f"  Maximum difference: {max_diff:.8f}")
    print(f"  Mean difference: {mean_diff:.8f}")
    
    if max_diff < 1e-6:
        print("✅ UV coordinates are IDENTICAL between systems")
    else:
        print("❌ UV coordinates DIFFER between systems")

if __name__ == "__main__":
    working_uvs = test_working_system()
    current_uvs = test_current_system()
    compare_uv_coordinates(working_uvs, current_uvs)