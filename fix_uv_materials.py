#!/usr/bin/env python3
"""
Fix UV materials by ensuring UV coordinates are properly connected to material nodes
"""

import bpy
import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def fix_blender_material_uv_connections():
    """Fix Blender materials to properly reference UV coordinates"""
    print("=== FIXING BLENDER MATERIAL UV CONNECTIONS ===")
    
    # Clear scene and load test mesh
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    from vf3_mesh_loader import load_mesh_with_full_materials
    from vf3_uv_handler import preserve_and_apply_uv_coordinates
    from vf3_blender_exporter_modular import _apply_trimesh_materials
    
    # Load Satsuki head
    print("Loading Satsuki head...")
    mesh_info = load_mesh_with_full_materials('data/satsuki/head.x')
    trimesh_mesh = mesh_info['mesh']
    
    if 'materials' in mesh_info and mesh_info['materials']:
        trimesh_mesh = _apply_trimesh_materials(trimesh_mesh, mesh_info['materials'], mesh_info)
    
    # Create Blender mesh and apply UVs
    blender_mesh = bpy.data.meshes.new("fixed_head")
    vertices = trimesh_mesh.vertices.tolist()
    faces = trimesh_mesh.faces.tolist()
    blender_mesh.from_pydata(vertices, [], faces)
    blender_mesh.update()
    
    preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, "fixed_head", mesh_info)
    
    # Create mesh object
    mesh_obj = bpy.data.objects.new("fixed_head", blender_mesh)
    bpy.context.collection.objects.link(mesh_obj)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    
    # Create materials with PROPER UV connections
    print("Creating materials with proper UV connections...")
    
    if 'materials' in mesh_info and mesh_info['materials']:
        create_fixed_blender_materials(mesh_obj, mesh_info['materials'], trimesh_mesh, mesh_info)
    
    # Export with UV connections
    output_file = "satsuki_head_fixed_uvs.glb"
    print(f"Exporting with fixed UV connections to {output_file}...")
    
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_file,
            export_format='GLB',
            use_selection=True,
            export_materials='EXPORT',
            export_colors=True
        )
        
        print(f"✅ Export successful: {output_file}")
        
        # Verify UV preservation
        import trimesh
        scene = trimesh.load(output_file)
        if isinstance(scene, trimesh.Trimesh):
            if hasattr(scene.visual, 'uv') and scene.visual.uv is not None:
                print(f"✅ UVs preserved in export: {len(scene.visual.uv)} coordinates")
                return True
            else:
                print(f"❌ UVs still lost in export")
                return False
        elif hasattr(scene, 'geometry'):
            for mesh_name, mesh in scene.geometry.items():
                if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                    print(f"✅ {mesh_name}: UVs preserved ({len(mesh.visual.uv)} coordinates)")
                    return True
                else:
                    print(f"❌ {mesh_name}: UVs lost")
            return False
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def create_fixed_blender_materials(mesh_obj, materials, trimesh_mesh, mesh_info):
    """Create Blender materials with proper UV connections"""
    import bpy
    
    print(f"Creating {len(materials)} materials with UV connections...")
    
    for i, material_data in enumerate(materials):
        mat_name = f"fixed_material_{i}"
        material = bpy.data.materials.new(name=mat_name)
        material.use_nodes = True
        
        # Clear default nodes
        material.node_tree.nodes.clear()
        
        # Create nodes
        bsdf = material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        output = material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        
        # Position nodes
        bsdf.location = (0, 0)
        output.location = (300, 0)
        
        # Connect BSDF to output
        material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        # Set base color
        if 'diffuse' in material_data:
            color = material_data['diffuse'][:3]
            bsdf.inputs['Base Color'].default_value = (*color, 1.0)
            print(f"  Material {i}: Base color {color}")
        
        # Add texture if available
        if 'textures' in material_data and material_data['textures']:
            texture_name = material_data['textures'][0]
            texture_path = find_texture_path(texture_name, mesh_info)
            
            if texture_path and os.path.exists(texture_path):
                print(f"  Material {i}: Adding texture {texture_name}")
                
                # Create UV Map node (CRITICAL!)
                uv_map_node = material.node_tree.nodes.new(type='ShaderNodeUVMap')
                uv_map_node.uv_map = 'UVMap'  # Use the UV layer we created
                uv_map_node.location = (-400, 0)
                
                # Create Image Texture node
                image_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
                image_node.location = (-200, 0)
                
                # Load image
                try:
                    image = bpy.data.images.load(texture_path)
                    image_node.image = image
                    print(f"    ✅ Loaded texture: {texture_path}")
                except Exception as e:
                    print(f"    ❌ Failed to load texture: {e}")
                    continue
                
                # CRITICAL CONNECTIONS for UV mapping
                material.node_tree.links.new(uv_map_node.outputs['UV'], image_node.inputs['Vector'])
                material.node_tree.links.new(image_node.outputs['Color'], bsdf.inputs['Base Color'])
                
                # Handle alpha
                if image.depth == 32:
                    material.node_tree.links.new(image_node.outputs['Alpha'], bsdf.inputs['Alpha'])
                    material.blend_method = 'CLIP'
                    material.alpha_threshold = 0.1
                
                print(f"    ✅ Connected UV mapping: UVMap -> Image Texture -> BSDF")
        
        # Add material to mesh
        mesh_obj.data.materials.append(material)
        print(f"  ✅ Created material {mat_name}")

def find_texture_path(texture_name, mesh_info):
    """Find texture file path"""
    if not texture_name or not mesh_info:
        return None
    
    # Try multiple locations
    candidates = [
        f"data/{texture_name}",
        f"data/satsuki/{texture_name}",
        os.path.join(os.path.dirname(mesh_info.get('source_path', '')), texture_name)
    ]
    
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    
    return None

if __name__ == "__main__":
    success = fix_blender_material_uv_connections()
    
    print("\n=== RESULT ===")
    if success:
        print("✅ UV coordinates successfully preserved in GLB export!")
        print("The fix was to properly connect UV Map nodes to Image Texture nodes in materials.")
    else:
        print("❌ UV coordinates still being lost.")
        print("Need to investigate further - might be a Blender version issue.")