#!/usr/bin/env python3
"""
Debug script to compare head UV coordinates between Satsuki and working characters
"""

import os
import sys
from vf3_xfile_parser import load_mesh_simple

def compare_head_uvs():
    """Compare UV coordinates between different character heads"""
    
    # Head files to compare
    head_files = {
        'satsuki': 'data/satsuki/head.X',
        'hisui': 'data/hisui/head.X', 
        'arcueid': 'data/arcueid/head.X',
        'ciel': 'data/CIEL/head.X'
    }
    
    results = {}
    
    for char_name, head_path in head_files.items():
        if os.path.exists(head_path):
            print(f"\n🔍 Loading {char_name} head: {head_path}")
            try:
                mesh = load_mesh_simple(head_path)
                if mesh and hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                    uv_coords = mesh.visual.uv
                    import numpy as np
                    
                    min_u, min_v = uv_coords.min(axis=0)
                    max_u, max_v = uv_coords.max(axis=0)
                    mean_u, mean_v = uv_coords.mean(axis=0)
                    
                    results[char_name] = {
                        'count': len(uv_coords),
                        'min_u': min_u, 'max_u': max_u, 'mean_u': mean_u,
                        'min_v': min_v, 'max_v': max_v, 'mean_v': mean_v,
                        'sample': uv_coords[:5].tolist(),
                        'vertices': len(mesh.vertices) if hasattr(mesh, 'vertices') else 0
                    }
                    
                    print(f"  ✅ {char_name}: {len(uv_coords)} UVs, {len(mesh.vertices)} vertices")
                    print(f"    UV Range: U({min_u:.4f}-{max_u:.4f}) V({min_v:.4f}-{max_v:.4f})")
                    print(f"    UV Center: U({mean_u:.4f}) V({mean_v:.4f})")
                    
                else:
                    print(f"  ❌ {char_name}: No UV coordinates found")
                    results[char_name] = {'error': 'No UV coordinates'}
                    
            except Exception as e:
                print(f"  ❌ {char_name}: Failed to load - {e}")
                results[char_name] = {'error': str(e)}
        else:
            print(f"  ❌ {char_name}: File not found - {head_path}")
            results[char_name] = {'error': 'File not found'}
    
    # Compare results
    print(f"\n📊 COMPARISON SUMMARY:")
    print(f"{'Character':<10} {'UVs':<6} {'Vertices':<8} {'U Range':<15} {'V Range':<15} {'Status'}")
    print(f"{'-'*80}")
    
    for char_name, data in results.items():
        if 'error' in data:
            print(f"{char_name:<10} {'ERROR':<6} {'ERROR':<8} {'ERROR':<15} {'ERROR':<15} {data['error']}")
        else:
            u_range = f"{data['min_u']:.3f}-{data['max_u']:.3f}"
            v_range = f"{data['min_v']:.3f}-{data['max_v']:.3f}"
            status = "✅ OK" if char_name != 'satsuki' else "❌ BROKEN"
            print(f"{char_name:<10} {data['count']:<6} {data['vertices']:<8} {u_range:<15} {v_range:<15} {status}")
    
    # Look for patterns
    print(f"\n🔍 PATTERN ANALYSIS:")
    
    working_chars = [name for name in results if name != 'satsuki' and 'error' not in results[name]]
    if working_chars and 'satsuki' in results and 'error' not in results['satsuki']:
        satsuki_data = results['satsuki']
        
        for working_char in working_chars:
            working_data = results[working_char]
            print(f"\nSatsuki vs {working_char}:")
            print(f"  UV Count: {satsuki_data['count']} vs {working_data['count']}")
            print(f"  Vertex Count: {satsuki_data['vertices']} vs {working_data['vertices']}")
            print(f"  U Range: {satsuki_data['max_u']-satsuki_data['min_u']:.4f} vs {working_data['max_u']-working_data['min_u']:.4f}")
            print(f"  V Range: {satsuki_data['max_v']-satsuki_data['min_v']:.4f} vs {working_data['max_v']-working_data['min_v']:.4f}")
            
            # Check if UVs are totally different
            if abs(satsuki_data['mean_u'] - working_data['mean_u']) > 0.3:
                print(f"  ⚠️ U coordinates very different!")
            if abs(satsuki_data['mean_v'] - working_data['mean_v']) > 0.3:
                print(f"  ⚠️ V coordinates very different!")

if __name__ == '__main__':
    compare_head_uvs()