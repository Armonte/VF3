#!/usr/bin/env python3
"""
Test different Blender glTF export settings to preserve UV coordinates
"""

import bpy
import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_gltf_export_settings():
    """Test different glTF export settings to preserve UVs"""
    print("=== TESTING BLENDER GLTF EXPORT SETTINGS ===")
    
    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    from vf3_mesh_loader import load_mesh_with_full_materials
    from vf3_uv_handler import preserve_and_apply_uv_coordinates
    from vf3_blender_exporter_modular import _apply_trimesh_materials
    
    # Load and prepare Satsuki head (same as before)
    print("Loading Satsuki head...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    trimesh_mesh = mesh_info['mesh']
    
    if 'materials' in mesh_info and mesh_info['materials']:
        trimesh_mesh = _apply_trimesh_materials(trimesh_mesh, mesh_info['materials'], mesh_info)
    
    # Create Blender mesh and apply UVs
    blender_mesh = bpy.data.meshes.new("test_head")
    vertices = trimesh_mesh.vertices.tolist()
    faces = trimesh_mesh.faces.tolist()
    blender_mesh.from_pydata(vertices, [], faces)
    blender_mesh.update()
    
    preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, "test_head", mesh_info)
    
    # Create mesh object
    mesh_obj = bpy.data.objects.new("test_head", blender_mesh)
    bpy.context.collection.objects.link(mesh_obj)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    
    # Verify UV layer exists
    if blender_mesh.uv_layers and blender_mesh.uv_layers.active:
        print(f"✅ UV layer exists: {blender_mesh.uv_layers.active.name}")
        print(f"   UV data points: {len(blender_mesh.uv_layers.active.data)}")
    else:
        print("❌ No UV layer found in Blender mesh")
        return
    
    # Test different export configurations
    export_configs = [
        {
            'name': 'Basic Export',
            'filename': 'test_basic.glb',
            'settings': {
                'filepath': 'test_basic.glb',
                'export_format': 'GLB',
                'use_selection': True,
                'export_materials': 'EXPORT',
            }
        },
        {
            'name': 'Full Export (current settings)',
            'filename': 'test_full.glb', 
            'settings': {
                'filepath': 'test_full.glb',
                'check_existing': False,
                'export_format': 'GLB',
                'use_selection': True,
                'export_apply': True,
                'export_yup': True,
                'export_materials': 'EXPORT',
                'export_colors': True,
                'export_cameras': False,
                'export_extras': False,
                'export_lights': False,
                'export_skins': True,
                'export_def_bones': False,
                'export_rest_position_armature': False,
                'export_anim_slide_to_zero': False,
                'export_animations': False
            }
        },
        {
            'name': 'Minimal Export',
            'filename': 'test_minimal.glb',
            'settings': {
                'filepath': 'test_minimal.glb',
                'export_format': 'GLB',
                'use_selection': True,
                'export_apply': False,  # Don't apply transforms
                'export_materials': 'EXPORT',
                'export_colors': True
            }
        }
    ]
    
    for config in export_configs:
        print(f"\nTesting: {config['name']}")
        
        try:
            bpy.ops.export_scene.gltf(**config['settings'])
            
            # Check if file was created
            if os.path.exists(config['filename']):
                print(f"✅ Export successful: {config['filename']}")
                
                # Analyze the exported file
                try:
                    import trimesh
                    scene = trimesh.load(config['filename'])
                    
                    if isinstance(scene, trimesh.Trimesh):
                        # Single mesh
                        if hasattr(scene.visual, 'uv') and scene.visual.uv is not None:
                            print(f"   ✅ UVs preserved: {len(scene.visual.uv)} coordinates")
                        else:
                            print(f"   ❌ UVs lost")
                    elif hasattr(scene, 'geometry'):
                        # Multiple meshes
                        for mesh_name, mesh in scene.geometry.items():
                            if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                                print(f"   ✅ {mesh_name}: UVs preserved ({len(mesh.visual.uv)} coordinates)")
                            else:
                                print(f"   ❌ {mesh_name}: UVs lost")
                    
                except Exception as e:
                    print(f"   Error analyzing file: {e}")
            else:
                print(f"❌ Export failed - file not created")
                
        except Exception as e:
            print(f"❌ Export failed: {e}")

def debug_uv_layer_details():
    """Debug UV layer details in Blender"""
    print("\n=== DEBUGGING UV LAYER DETAILS ===")
    
    # Get the active object
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        print("❌ No active mesh object")
        return
    
    mesh = obj.data
    print(f"Mesh: {mesh.name}")
    print(f"Vertices: {len(mesh.vertices)}")
    print(f"Faces: {len(mesh.polygons)}")
    print(f"Loops: {len(mesh.loops)}")
    
    # Check UV layers
    print(f"UV layers: {len(mesh.uv_layers)}")
    for i, uv_layer in enumerate(mesh.uv_layers):
        print(f"  Layer {i}: {uv_layer.name} (active: {uv_layer.active})")
        print(f"    Data points: {len(uv_layer.data)}")
        
        # Sample first few UV coordinates
        sample_size = min(5, len(uv_layer.data))
        sample_uvs = []
        for j in range(sample_size):
            uv = uv_layer.data[j].uv
            sample_uvs.append((uv[0], uv[1]))
        print(f"    Sample UVs: {sample_uvs}")

if __name__ == "__main__":
    test_gltf_export_settings()
    debug_uv_layer_details()
    
    print("\n=== CONCLUSION ===")
    print("Check which export configuration preserves UV coordinates correctly")