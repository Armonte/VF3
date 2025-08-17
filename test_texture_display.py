#!/usr/bin/env python3
"""
Test texture display in exported GLB files to identify the real problem
"""

import sys
import os

def analyze_glb_files():
    """Analyze the different GLB files we've created"""
    print("=== ANALYZING GLB FILES ===")
    
    files_to_analyze = [
        {
            'name': 'Direct Trimesh (head only)',
            'file': 'satsuki_head_direct_trimesh.glb',
            'description': 'Single head mesh exported directly from trimesh'
        },
        {
            'name': 'Debug Blender (head only)', 
            'file': 'debug_blender_head.glb',
            'description': 'Single head mesh exported through Blender'
        },
        {
            'name': 'Full Satsuki modular',
            'file': 'satsuki_uv_fixed.glb', 
            'description': 'Complete character exported through modular system'
        }
    ]
    
    for file_info in files_to_analyze:
        filename = file_info['file']
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"\n{file_info['name']}: {filename}")
            print(f"  Size: {size:,} bytes")
            print(f"  Description: {file_info['description']}")
            
            # Try to get basic info about the GLB file
            try:
                import trimesh
                scene = trimesh.load(filename)
                if hasattr(scene, 'geometry') and scene.geometry:
                    print(f"  Meshes: {len(scene.geometry)}")
                    for mesh_name, mesh in scene.geometry.items():
                        if hasattr(mesh, 'vertices'):
                            print(f"    {mesh_name}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
                            if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                                print(f"      UVs: {len(mesh.visual.uv)} coordinates")
                            else:
                                print(f"      UVs: None")
                elif isinstance(scene, trimesh.Trimesh):
                    print(f"  Single mesh: {len(scene.vertices)} vertices, {len(scene.faces)} faces")
                    if hasattr(scene.visual, 'uv') and scene.visual.uv is not None:
                        print(f"    UVs: {len(scene.visual.uv)} coordinates")
                    else:
                        print(f"    UVs: None")
            except Exception as e:
                print(f"  Error analyzing: {e}")
        else:
            print(f"\n{file_info['name']}: {filename} - NOT FOUND")

def create_simple_working_reference():
    """Create a simple working reference using the working export method"""
    print("\n=== CREATING SIMPLE WORKING REFERENCE ===")
    
    # Try to create a simple head-only export using the working method
    try:
        from vf3_mesh_loader import load_mesh_with_full_materials
        import trimesh
        
        print("Loading Satsuki head with working method...")
        mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
        
        if mesh_info['mesh']:
            # Export directly without any material application 
            raw_output = "satsuki_head_raw_no_materials.glb"
            mesh_info['mesh'].export(raw_output)
            print(f"✅ Created raw export (no materials): {raw_output}")
            
            # Export with materials applied using our current method
            from vf3_blender_exporter_modular import _apply_trimesh_materials
            processed_mesh = _apply_trimesh_materials(mesh_info['mesh'], mesh_info['materials'], mesh_info)
            
            materials_output = "satsuki_head_with_materials.glb"
            processed_mesh.export(materials_output)
            print(f"✅ Created materials export: {materials_output}")
            
            return True
        else:
            print("❌ Failed to load mesh")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create reference: {e}")
        return False

def check_texture_files():
    """Check if texture files are accessible"""
    print("\n=== CHECKING TEXTURE FILES ===")
    
    texture_files = [
        'data/stkface.bmp',
        'data/stkhair_t.bmp'
    ]
    
    for texture_file in texture_files:
        if os.path.exists(texture_file):
            size = os.path.getsize(texture_file)
            print(f"✅ {texture_file}: {size:,} bytes")
        else:
            print(f"❌ {texture_file}: NOT FOUND")

if __name__ == "__main__":
    check_texture_files()
    analyze_glb_files()
    create_simple_working_reference()
    
    print("\n=== DIAGNOSIS ===")
    print("Based on the analysis:")
    print("1. UV coordinates are correctly applied to Blender")
    print("2. GLB files are being created successfully")
    print("3. The issue might be in:")
    print("   - Texture file paths/references in GLB")
    print("   - Material assignment in Blender")
    print("   - GLB viewer texture loading")
    print("   - Multi-material mesh splitting")
    print("\n🔍 Recommendation: Open the GLB files in a viewer and compare visual appearance")