#!/usr/bin/env python3
"""
Debug script to test UV extraction from head meshes
"""

import os
import sys
import numpy as np

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vf3_xfile_parser import load_mesh_with_materials

def debug_head_uv_extraction():
    """Debug UV extraction from head meshes"""
    
    # Test head files
    head_files = [
        'data/satsuki/head.X',
        'data/hisui/head.X',
        'data/arcueid/head.X'
    ]
    
    for head_path in head_files:
        if not os.path.exists(head_path):
            print(f"? File not found: {head_path}")
            continue
            
        print(f"\n? Testing UV extraction from: {head_path}")
        print(f"{'='*60}")
        
        try:
            # Load with materials
            result = load_mesh_with_materials(head_path)
            
            if result and result['mesh']:
                mesh = result['mesh']
                uv_coords = result.get('uv_coords', [])
                
                print(f"? Mesh loaded successfully")
                print(f"  Vertices: {len(mesh.vertices)}")
                print(f"  Faces: {len(mesh.faces)}")
                print(f"  UV coordinates: {len(uv_coords)}")
                
                # Check if UVs are attached to mesh
                if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                    mesh_uvs = mesh.visual.uv
                    print(f"  Mesh.visual.uv: {len(mesh_uvs)} UVs")
                    
                    if len(mesh_uvs) > 0:
                        uv_array = np.array(mesh_uvs)
                        min_u, min_v = uv_array.min(axis=0)
                        max_u, max_v = uv_array.max(axis=0)
                        mean_u, mean_v = uv_array.mean(axis=0)
                        
                        print(f"  UV Range: U({min_u:.4f}-{max_u:.4f}) V({min_v:.4f}-{max_v:.4f})")
                        print(f"  UV Center: U({mean_u:.4f}) V({mean_v:.4f})")
                        print(f"  First 5 UVs: {mesh_uvs[:5].tolist()}")
                        
                        # Check if UVs match vertex count
                        if len(mesh_uvs) == len(mesh.vertices):
                            print(f"  ? UV count matches vertex count")
                        else:
                            print(f"  ? UV count mismatch: {len(mesh_uvs)} UVs vs {len(mesh.vertices)} vertices")
                    else:
                        print(f"  ? No UV coordinates in mesh.visual.uv")
                else:
                    print(f"  ? No mesh.visual.uv attribute")
                
                # Check raw UV coordinates from parser
                if uv_coords:
                    print(f"  Raw UVs from parser: {len(uv_coords)}")
                    if len(uv_coords) > 0:
                        raw_uv_array = np.array(uv_coords)
                        raw_min_u, raw_min_v = raw_uv_array.min(axis=0)
                        raw_max_u, raw_max_v = raw_uv_array.max(axis=0)
                        print(f"  Raw UV Range: U({raw_min_u:.4f}-{raw_max_u:.4f}) V({raw_min_v:.4f}-{raw_max_v:.4f})")
                        
                        # Compare with mesh UVs
                        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                            mesh_uvs = mesh.visual.uv
                            if len(mesh_uvs) > 0 and len(uv_coords) > 0:
                                if np.array_equal(mesh_uvs, uv_coords):
                                    print(f"  ? UVs match between parser and mesh")
                                else:
                                    print(f"  ? UV mismatch between parser and mesh!")
                                    print(f"    Parser first 3: {uv_coords[:3]}")
                                    print(f"    Mesh first 3: {mesh_uvs[:3].tolist()}")
                else:
                    print(f"  ? No raw UV coordinates from parser")
                    
            else:
                print(f"? Failed to load mesh")
                
        except Exception as e:
            print(f"? Error loading {head_path}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    debug_head_uv_extraction()
