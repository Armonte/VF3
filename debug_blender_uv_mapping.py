#!/usr/bin/env python3
"""
Debug the Blender UV mapping process to see exactly what's happening
"""

import bpy
import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def debug_blender_uv_conversion():
    """Debug the exact UV mapping process in Blender"""
    print("=== DEBUGGING BLENDER UV CONVERSION ===")
    
    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    from vf3_mesh_loader import load_mesh_with_full_materials
    from vf3_uv_handler import preserve_and_apply_uv_coordinates
    from vf3_blender_exporter_modular import _apply_trimesh_materials
    
    # Load Satsuki head and apply materials
    print("Loading and processing Satsuki head...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    trimesh_mesh = mesh_info['mesh']
    
    # Apply materials like the main exporter does
    if 'materials' in mesh_info and mesh_info['materials']:
        trimesh_mesh = _apply_trimesh_materials(trimesh_mesh, mesh_info['materials'], mesh_info)
    
    print(f"Trimesh mesh: {len(trimesh_mesh.vertices)} vertices, {len(trimesh_mesh.faces)} faces")
    
    # Check trimesh UV coordinates
    if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
        trimesh_uvs = trimesh_mesh.visual.uv
        print(f"Trimesh UVs: {len(trimesh_uvs)} coordinates")
        print(f"  First 5 trimesh UVs: {trimesh_uvs[:5].tolist()}")
    else:
        print("❌ No UV coordinates in trimesh")
        return
    
    # Create Blender mesh
    blender_mesh = bpy.data.meshes.new("debug_head")
    vertices = trimesh_mesh.vertices.tolist()
    faces = trimesh_mesh.faces.tolist()
    blender_mesh.from_pydata(vertices, [], faces)
    blender_mesh.update()
    
    print(f"Blender mesh: {len(blender_mesh.vertices)} vertices, {len(blender_mesh.polygons)} faces")
    
    # Debug the UV application process step by step
    print("\n=== DEBUGGING UV APPLICATION ===")
    
    # Create UV layer
    if not blender_mesh.uv_layers:
        blender_mesh.uv_layers.new(name="UVMap")
    
    uv_layer = blender_mesh.uv_layers.active.data
    print(f"Created UV layer with {len(uv_layer)} loops")
    
    # Apply UV coordinates using our current method
    preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, "debug_head", mesh_info)
    
    # Sample and verify UV coordinates after application
    print("\n=== VERIFYING APPLIED UV COORDINATES ===")
    sample_uvs = []
    for i in range(min(10, len(uv_layer))):
        loop_uv = uv_layer[i]
        vertex_index = blender_mesh.loops[i].vertex_index
        sample_uvs.append({
            'loop_index': i,
            'vertex_index': vertex_index,
            'uv': (loop_uv.uv[0], loop_uv.uv[1]),
            'trimesh_uv': trimesh_uvs[vertex_index].tolist() if vertex_index < len(trimesh_uvs) else None
        })
    
    print("Sample UV mappings (first 10 loops):")
    for sample in sample_uvs:
        loop_idx = sample['loop_index']
        vert_idx = sample['vertex_index']
        blender_uv = sample['uv']
        trimesh_uv = sample['trimesh_uv']
        
        if trimesh_uv:
            diff_u = abs(blender_uv[0] - trimesh_uv[0])
            diff_v = abs(blender_uv[1] - trimesh_uv[1])
            status = "✅" if (diff_u < 1e-6 and diff_v < 1e-6) else "❌"
            print(f"  Loop {loop_idx} (vertex {vert_idx}): Blender={blender_uv} Trimesh={trimesh_uv} {status}")
        else:
            print(f"  Loop {loop_idx} (vertex {vert_idx}): Blender={blender_uv} Trimesh=None ❌")
    
    # Create mesh object and export
    mesh_obj = bpy.data.objects.new("debug_head", blender_mesh)
    bpy.context.collection.objects.link(mesh_obj)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    
    # Export to GLB
    debug_output = "debug_blender_head.glb"
    print(f"\nExporting Blender mesh to {debug_output}...")
    
    try:
        bpy.ops.export_scene.gltf(
            filepath=debug_output,
            check_existing=False,
            export_format='GLB',
            use_selection=True,
            export_apply=True,
            export_materials='EXPORT',
            export_colors=True
        )
        
        if os.path.exists(debug_output):
            file_size = os.path.getsize(debug_output)
            print(f"✅ Blender export successful: {debug_output} ({file_size} bytes)")
        else:
            print("❌ Blender export failed - no file created")
            
    except Exception as e:
        print(f"❌ Blender export failed: {e}")

def compare_file_sizes():
    """Compare file sizes between different exports"""
    print("\n=== COMPARING FILE SIZES ===")
    
    files_to_check = [
        "satsuki_head_direct_trimesh.glb",
        "debug_blender_head.glb", 
        "satsuki_uv_fixed.glb"
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"  {filename}: {size:,} bytes")
        else:
            print(f"  {filename}: NOT FOUND")

if __name__ == "__main__":
    debug_blender_uv_conversion()
    compare_file_sizes()
    
    print("\n=== NEXT STEPS ===")
    print("1. Check if UV coordinates are correctly applied in Blender")
    print("2. Compare GLB files in a viewer to see visual differences")  
    print("3. If Blender UVs are wrong, fix the loop-to-vertex mapping logic")