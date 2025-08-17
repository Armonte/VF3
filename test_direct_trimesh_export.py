#!/usr/bin/env python3
"""
Test direct trimesh export bypassing Blender entirely
This will help isolate if the problem is in Blender or in the UV data itself
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_direct_trimesh_export():
    """Test exporting Satsuki head directly from trimesh without Blender"""
    print("=== TESTING DIRECT TRIMESH EXPORT (NO BLENDER) ===")
    
    from vf3_mesh_loader import load_mesh_with_full_materials
    import trimesh
    
    # Load Satsuki head
    print("Loading Satsuki head...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    
    if not mesh_info['mesh']:
        print("❌ Failed to load mesh")
        return False
    
    trimesh_mesh = mesh_info['mesh']
    print(f"✅ Loaded mesh: {len(trimesh_mesh.vertices)} vertices, {len(trimesh_mesh.faces)} faces")
    
    # Apply materials like our current system does
    if 'materials' in mesh_info and mesh_info['materials']:
        print(f"Applying {len(mesh_info['materials'])} materials...")
        
        # Import the material application function
        sys.path.append('/mnt/c/dev/loot/VF3')
        from vf3_blender_exporter_modular import _apply_trimesh_materials
        
        trimesh_mesh = _apply_trimesh_materials(trimesh_mesh, mesh_info['materials'], mesh_info)
        print("✅ Applied materials")
    
    # Check UV coordinates after material application
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        uv_coords = trimesh_mesh.visual.uv
        print(f"✅ UV coordinates preserved: {len(uv_coords)} UVs")
        print(f"   First 5 UVs: {uv_coords[:5].tolist()}")
    else:
        print("❌ UV coordinates lost during material application")
        return False
    
    # Export directly from trimesh
    output_path = "satsuki_head_direct_trimesh.glb"
    print(f"Exporting directly from trimesh to {output_path}...")
    
    try:
        trimesh_mesh.export(output_path)
        print(f"✅ Direct trimesh export successful: {output_path}")
        
        # Check file size
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"   File size: {file_size} bytes")
            return True
        else:
            print("❌ Export file not created")
            return False
            
    except Exception as e:
        print(f"❌ Direct trimesh export failed: {e}")
        return False

def compare_with_working_export():
    """Compare with working export_ciel_to_gltf.py for just the head"""
    print("\n=== RUNNING WORKING EXPORT FOR COMPARISON ===")
    
    # Run working export for Satsuki
    import subprocess
    try:
        result = subprocess.run([
            'python3', 'export_ciel_to_gltf.py', 
            '--desc', 'data/satsuki.TXT', 
            '--out', 'satsuki_working_comparison.glb'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Working export completed")
            if os.path.exists('satsuki_working_comparison.glb'):
                file_size = os.path.getsize('satsuki_working_comparison.glb')
                print(f"   Working export file size: {file_size} bytes")
            return True
        else:
            print(f"❌ Working export failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to run working export: {e}")
        return False

if __name__ == "__main__":
    # Test direct trimesh export
    direct_success = test_direct_trimesh_export()
    
    # Compare with working export
    working_success = compare_with_working_export()
    
    print("\n=== SUMMARY ===")
    if direct_success:
        print("✅ Direct trimesh export: SUCCESS")
    else:
        print("❌ Direct trimesh export: FAILED")
        
    if working_success:
        print("✅ Working export: SUCCESS")
    else:
        print("❌ Working export: FAILED")
        
    if direct_success and working_success:
        print("\n🔍 Next step: Compare the GLB files to see if UV coordinates are preserved correctly")
    elif not direct_success:
        print("\n🚨 Problem is in trimesh material application or mesh handling")
    else:
        print("\n🤔 Issue is in Blender conversion or GLB export process")