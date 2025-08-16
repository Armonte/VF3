#!/usr/bin/env python3
"""
Debug script to analyze UV coordinates directly from .X files
to understand why Satsuki's head has wrong UV mapping.
"""

import trimesh
import numpy as np

def analyze_x_file_uvs(file_path, character_name):
    """Analyze UV coordinates from a .X file"""
    print(f"\n=== Analyzing {character_name} head.X ===")
    print(f"File: {file_path}")
    
    try:
        # Load the mesh using trimesh
        mesh = trimesh.load(file_path)
        
        print(f"Mesh type: {type(mesh)}")
        print(f"Vertices: {len(mesh.vertices)}")
        print(f"Faces: {len(mesh.faces)}")
        
        # Check UV coordinates
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            uv_coords = mesh.visual.uv
            print(f"UV coordinates: {len(uv_coords)}")
            print(f"UV shape: {uv_coords.shape}")
            
            # Analyze UV statistics
            u_coords = uv_coords[:, 0]
            v_coords = uv_coords[:, 1]
            
            print(f"U range: {u_coords.min():.4f} to {u_coords.max():.4f}")
            print(f"V range: {v_coords.min():.4f} to {v_coords.max():.4f}")
            print(f"U mean: {u_coords.mean():.4f}")
            print(f"V mean: {v_coords.mean():.4f}")
            
            # Check for out-of-range coordinates
            out_of_range = np.sum((uv_coords < 0) | (uv_coords > 1))
            print(f"Out-of-range UVs: {out_of_range}/{len(uv_coords)}")
            
            # Sample UV coordinates
            print(f"First 5 UVs: {uv_coords[:5].tolist()}")
            print(f"Last 5 UVs: {uv_coords[-5:].tolist()}")
            
            # Check for duplicate UV coordinates
            unique_uvs = np.unique(uv_coords, axis=0)
            print(f"Unique UVs: {len(unique_uvs)} (duplicates: {len(uv_coords) - len(unique_uvs)})")
            
            # Check for UV coordinate clustering
            u_range = u_coords.max() - u_coords.min()
            v_range = v_coords.max() - v_coords.min()
            print(f"UV spread: U={u_range:.4f}, V={v_range:.4f}")
            
            if u_range < 0.1 or v_range < 0.1:
                print(f"⚠️ UV coordinates are very clustered!")
                
            # Check for spiral patterns (large jumps between consecutive UVs)
            if len(uv_coords) > 1:
                diffs = np.diff(uv_coords, axis=0)
                distances = np.linalg.norm(diffs, axis=1)
                large_jumps = np.sum(distances > 0.5)
                max_jump = distances.max()
                print(f"Large UV jumps (>0.5): {large_jumps}/{len(distances)}")
                print(f"Max UV jump: {max_jump:.4f}")
                
                if large_jumps > len(distances) * 0.05:
                    print(f"⚠️ Potential spiral pattern detected!")
            
        else:
            print("❌ No UV coordinates found!")
            
        # Check material information
        if hasattr(mesh.visual, 'material'):
            print(f"Material: {mesh.visual.material}")
            
        print("-" * 50)
        
        return {
            'vertices': len(mesh.vertices),
            'faces': len(mesh.faces),
            'uv_count': len(uv_coords) if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None else 0,
            'uv_coords': uv_coords if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None else None
        }
        
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None

def main():
    """Compare UV data between working and broken characters"""
    
    characters = [
        ("/mnt/c/dev/loot/vf3/data/CIEL/head.X", "CIEL (WORKING)"),
        ("/mnt/c/dev/loot/vf3/data/hisui/head.X", "HISUI (WORKING)"),
        ("/mnt/c/dev/loot/vf3/data/satsuki/head.X", "SATSUKI (BROKEN)")
    ]
    
    results = {}
    
    for file_path, name in characters:
        results[name] = analyze_x_file_uvs(file_path, name)
    
    # Compare results
    print("\n=== COMPARISON ===")
    for name, data in results.items():
        if data:
            print(f"{name}: {data['vertices']} vertices, {data['uv_count']} UVs")
            if data['vertices'] != data['uv_count']:
                print(f"  ⚠️ MISMATCH: {data['uv_count'] - data['vertices']} extra UVs")
    
    # Check if the issue is in the .X file itself or our processing
    if results.get("SATSUKI (BROKEN)") and results.get("CIEL (WORKING)"):
        satsuki_data = results["SATSUKI (BROKEN)"]
        ciel_data = results["CIEL (WORKING)"]
        
        print(f"\n=== ROOT CAUSE ANALYSIS ===")
        print(f"Satsuki .X file: {satsuki_data['vertices']} vertices, {satsuki_data['uv_count']} UVs")
        print(f"Ciel .X file: {ciel_data['vertices']} vertices, {ciel_data['uv_count']} UVs")
        
        if satsuki_data['vertices'] == satsuki_data['uv_count']:
            print("✅ Satsuki .X file has matching vertex/UV counts - issue is in our processing!")
        else:
            print("❌ Satsuki .X file itself has UV/vertex mismatch - issue is in the source data!")

if __name__ == "__main__":
    main()