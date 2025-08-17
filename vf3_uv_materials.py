"""
VF3 UV and Material Handling - Extracted from working vf3_blender_exporter.py
Preserves the exact working logic for UV mapping and Blender material creation.
"""

import os
import sys
from typing import List, Dict, Any
import numpy as np
from PIL import Image


def assign_uv_coordinates(blender_mesh, trimesh_mesh, mesh_info, mesh_name):
    """
    Assign UV coordinates using the WORKING approach from export_ciel_to_gltf.py
    Key insight: Don't overcomplicate it - just preserve the original UV coordinates!
    """
    try:
        # Check for existing UV coordinates (same as working export_ciel_to_gltf.py)
        existing_uv = None
        if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
            existing_uv = trimesh_mesh.visual.uv.copy()
            print(f"  Preserving UV coordinates from .X file: {existing_uv.shape}")
        
        # Create UV layer
        if not blender_mesh.uv_layers:
            blender_mesh.uv_layers.new(name="UVMap")
        uv_layer = blender_mesh.uv_layers.active.data
        
        if existing_uv is not None:
            # Apply UV coordinates - use simple per-vertex mapping like the working code
            print(f"  Applying {len(existing_uv)} UV coordinates to {mesh_name}")
            
            loop_index = 0
            for poly in blender_mesh.polygons:
                for loop_idx in poly.loop_indices:
                    vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                    
                    # Use vertex index to get UV (most common case)
                    if vertex_idx < len(existing_uv):
                        u, v = existing_uv[vertex_idx]
                        # Use original UV coordinates directly (working approach)
                        uv_layer[loop_index].uv = (float(u), float(v))
                    else:
                        # Fallback: wrap around
                        uv_idx = vertex_idx % len(existing_uv)
                        u, v = existing_uv[uv_idx]
                        # Use original UV coordinates directly (working approach)
                        uv_layer[loop_index].uv = (float(u), float(v))
                    
                    loop_index += 1
            
            print(f"  ✅ Successfully applied UV coordinates to {mesh_name}")
        else:
            # Generate simple planar UV mapping as fallback (same as working code)
            print(f"  Generating simple UV mapping for {mesh_name}")
            vertices = [v.co for v in blender_mesh.vertices]
            if vertices:
                bounds = [min(vertices, key=lambda v: v[i])[i] for i in range(3)] + \
                        [max(vertices, key=lambda v: v[i])[i] for i in range(3)]
                width = bounds[3] - bounds[0]
                height = bounds[4] - bounds[1]
                
                loop_index = 0
                for poly in blender_mesh.polygons:
                    for loop_idx in poly.loop_indices:
                        vertex_idx = blender_mesh.loops[loop_idx].vertex_index
                        vertex = blender_mesh.vertices[vertex_idx]
                        
                        u = (vertex.co.x - bounds[0]) / width if width > 0 else 0.5
                        v = (vertex.co.y - bounds[1]) / height if height > 0 else 0.5
                        u = max(0.0, min(1.0, u))
                        v = max(0.0, min(1.0, v))
                        
                        uv_layer[loop_index].uv = (u, v)
                        loop_index += 1
            
            print(f"  ✅ Generated simple UV mapping for {mesh_name}")
        
    except Exception as e:
        print(f"  ❌ UV assignment failed for {mesh_name}: {e}")


def _create_blender_materials(mesh_obj, materials: List, trimesh_mesh, mesh_info: dict = None):
    """Create Blender materials from VF3 material data.
    
    CRITICAL FIX: For multi-material meshes, use unified approach to preserve UV coordinates.
    """
    try:
        import bpy
        from mathutils import Vector
    except ImportError:
        print("  ERROR: bpy not available for material creation")
        return
    
    # CRITICAL FIX: For multi-material meshes, create a SINGLE unified material
    # This preserves UV coordinates which get broken when splitting meshes by materials
    if len(materials) > 1:
        print(f"    Multi-material mesh detected: using unified approach with primary texture")
        _create_unified_material(mesh_obj, materials, mesh_info)
        return
    
    print(f"    Creating {len(materials)} materials for mesh")
    
    # Single material case - proceed as normal
    for i, material_data in enumerate(materials):
        # Create Blender material with UNIQUE name per mesh to avoid conflicts
        mesh_name = mesh_obj.name.replace('.', '_').replace(':', '_')  # Sanitize mesh name for material name
        mat_name = f"{mesh_name}_Material_{i}"
        if material_data.get('name'):
            mat_name = f"{mesh_name}_{material_data['name']}_{i}"  # Add index to ensure uniqueness
        
        # Check if material already exists to avoid duplicates (using unique name now)
        if mat_name in bpy.data.materials:
            existing_mat = bpy.data.materials[mat_name]
            mesh_obj.data.materials.append(existing_mat)
            continue
        
        material = bpy.data.materials.new(name=mat_name)
        material.use_nodes = True
        
        # Get the Principled BSDF node
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            continue
        
        # Set base color from diffuse
        if 'diffuse' in material_data:
            color = material_data['diffuse']
            # Ensure we have 4 components (RGBA)
            if len(color) == 3:
                color = list(color) + [1.0]
            elif len(color) < 3:
                color = [0.8, 0.8, 0.8, 1.0]  # Default gray
            else:
                color = list(color[:4])  # Take first 4 components
            
            bsdf.inputs['Base Color'].default_value = color
            print(f"      Set base color: {color}")
            
            # Handle transparency
            if color[3] < 1.0:
                material.blend_method = 'BLEND'
                bsdf.inputs['Alpha'].default_value = color[3]
        
        # Handle textures if present
        if material_data.get('textures'):
            texture_name = material_data['textures'][0]
            
            # Find texture file (same search logic as original)
            texture_path = _find_texture_file(texture_name, mesh_info)
            
            if texture_path and os.path.exists(texture_path):
                print(f"      Loading texture: {texture_path}")
                
                # Process texture for black-as-alpha if needed
                processed_texture_path = _ensure_alpha_from_black(texture_path)
                
                # Load image in Blender
                try:
                    image = _load_image_with_black_as_alpha(processed_texture_path, 
                                                          make_alpha='hair' in texture_name.lower())
                    
                    if image:
                        # CRITICAL FIX: Create UV Map node to properly connect UV coordinates
                        uv_map_node = material.node_tree.nodes.new(type='ShaderNodeUVMap')
                        uv_map_node.uv_map = 'UVMap'  # Reference the UV layer we created
                        
                        # Create texture node and connect it
                        texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
                        texture_node.image = image
                        
                        # CRITICAL: Set texture interpolation to Closest (nearest neighbor) for pixel-perfect textures
                        # This fixes the UV mapping "golden ratio spiral" issue for Satsuki's head
                        texture_node.interpolation = 'Closest'
                        
                        # CRITICAL CONNECTIONS: Connect UV Map -> Image Texture -> BSDF
                        # This ensures UV coordinates are properly referenced and exported
                        material.node_tree.links.new(uv_map_node.outputs['UV'], texture_node.inputs['Vector'])
                        material.node_tree.links.new(texture_node.outputs['Color'], bsdf.inputs['Base Color'])
                        
                        # Handle alpha if texture has it
                        if image.depth == 32:  # RGBA
                            material.node_tree.links.new(texture_node.outputs['Alpha'], bsdf.inputs['Alpha'])
                            material.blend_method = 'CLIP'
                            material.alpha_threshold = 0.1
                        
                        print(f"      ✅ Texture applied: {texture_name}")
                    
                except Exception as e:
                    print(f"      ❌ Failed to load texture {texture_name}: {e}")
            else:
                print(f"      ❌ Texture file not found for material {i}: {texture_name} (searched: {texture_path})")
        
        # Add material to mesh
        mesh_obj.data.materials.append(material)
    
    # CRITICAL: Assign face materials if available (missing from modular version!)
    _assign_face_materials_to_mesh(mesh_obj, materials, mesh_info, trimesh_mesh)
    
    print(f"    ✅ Created {len(materials)} Blender materials")


def _create_unified_material(mesh_obj, materials: List, mesh_info: dict = None):
    """Create a unified material approach that preserves face material assignments but maintains UV coordinates."""
    try:
        import bpy
    except ImportError:
        return
    
    mesh_name = mesh_obj.name.replace('.', '_').replace(':', '_')
    
    # REVISED APPROACH: Create ALL materials but use proper face assignment
    # This preserves UV coordinates while respecting material differences
    print(f"    Creating {len(materials)} materials with unified UV approach")
    
    for i, material_data in enumerate(materials):
        # Create Blender material with unique name
        mat_name = f"{mesh_name}_Unified_{i}"
        if material_data.get('name'):
            mat_name = f"{mesh_name}_{material_data['name']}_Unified_{i}"
        
        material = bpy.data.materials.new(name=mat_name)
        material.use_nodes = True
        
        # Get the Principled BSDF node
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            continue
        
        # Set base color from material data
        if 'diffuse' in material_data:
            color = material_data['diffuse']
            if len(color) >= 3:
                bsdf.inputs['Base Color'].default_value = list(color[:4]) if len(color) >= 4 else list(color[:3]) + [1.0]
                print(f"      Material {i}: Set base color {color}")
        
        # Apply texture if available (respect what .X file specifies)
        if material_data.get('textures'):
            texture_name = material_data['textures'][0]
            texture_path = _find_texture_file(texture_name, mesh_info)
            
            if texture_path and os.path.exists(texture_path):
                print(f"      Material {i}: Loading texture {texture_name}")
                
                try:
                    # Load image in Blender
                    image = _load_image_with_black_as_alpha(texture_path, 'hair' in texture_name.lower())
                    
                    if image:
                        # CRITICAL: Create UV Map node for EACH material
                        uv_map_node = material.node_tree.nodes.new(type='ShaderNodeUVMap')
                        uv_map_node.uv_map = 'UVMap'
                        
                        # Create texture node
                        texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
                        texture_node.image = image
                        texture_node.interpolation = 'Closest'
                        
                        # Connect UV Map -> Texture -> BSDF (simple and working)
                        material.node_tree.links.new(uv_map_node.outputs['UV'], texture_node.inputs['Vector'])
                        material.node_tree.links.new(texture_node.outputs['Color'], bsdf.inputs['Base Color'])
                        
                        print(f"      ✅ Material {i}: Applied texture {texture_name}")
                    
                except Exception as e:
                    print(f"      ❌ Material {i}: Failed to load texture {texture_name}: {e}")
            else:
                print(f"      Material {i}: No texture or texture not found")
        
        # Add material to mesh
        mesh_obj.data.materials.append(material)
    
    # CRITICAL: Assign face materials properly while preserving UV coordinates
    _assign_face_materials_to_unified_mesh(mesh_obj, materials, mesh_info)
    
    print(f"    ✅ Created {len(materials)} unified materials with proper face assignments")


def _assign_face_materials_to_unified_mesh(mesh_obj, materials, mesh_info):
    """Assign face materials to unified mesh while preserving UV coordinates."""
    try:
        import bpy
    except ImportError:
        return
    
    # Get face material assignments from mesh_info
    face_materials = None
    if mesh_info and 'face_materials' in mesh_info:
        face_materials = mesh_info['face_materials']
        print(f"    Assigning face materials to unified mesh: {len(face_materials)} assignments")
    
    if face_materials and len(face_materials) > 0 and len(mesh_obj.data.polygons) > 0:
        # Ensure face count matches
        if len(face_materials) == len(mesh_obj.data.polygons):
            # Direct assignment (face order preserved)
            for face_idx, mat_idx in enumerate(face_materials):
                if face_idx < len(mesh_obj.data.polygons) and mat_idx < len(materials):
                    mesh_obj.data.polygons[face_idx].material_index = mat_idx
            
            print(f"    ✅ Assigned face materials to unified mesh: {len(face_materials)} faces")
        else:
            print(f"    ⚠️ Face count mismatch: {len(face_materials)} materials vs {len(mesh_obj.data.polygons)} faces")
    else:
        print(f"    ⚠️ No face material data available for unified mesh")


def _find_texture_file(texture_name: str, mesh_info: dict = None) -> str:
    """Find texture file using the same search logic as the original."""
    if not texture_name:
        return None
    
    # Try multiple locations (same as original)
    candidates = []
    
    if mesh_info and 'source_path' in mesh_info:
        base_path = os.path.dirname(mesh_info['source_path'])
        candidates.extend([
            os.path.join(base_path, texture_name),
            _find_in_data_root(texture_name, mesh_info)
        ])
    
    # Add more fallback locations
    candidates.extend([
        os.path.join('data', texture_name),
        texture_name  # Direct path
    ])
    
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    
    return None


def _find_in_data_root(filename: str, mesh_info: dict) -> str:
    """Find file in data directory tree (same as original)."""
    if not filename or not mesh_info:
        return None
    
    # Start from the mesh's directory and work up to find 'data' root
    if 'source_path' not in mesh_info:
        return None
    
    current_dir = os.path.dirname(mesh_info['source_path'])
    
    # Walk up the directory tree to find 'data' root
    while current_dir and current_dir != os.path.dirname(current_dir):
        if os.path.basename(current_dir) == 'data':
            # Search recursively in data directory
            for root, dirs, files in os.walk(current_dir):
                if filename in files:
                    return os.path.join(root, filename)
            break
        current_dir = os.path.dirname(current_dir)
    
    return None


def _ensure_alpha_from_black(image_path: str) -> str:
    """Process image to convert black pixels to transparent (same as original)."""
    if not image_path or not os.path.exists(image_path):
        return image_path
    
    try:
        # Generate processed filename
        base, ext = os.path.splitext(image_path)
        processed_path = f"{base}_alpha{ext}"
        
        # Check if already processed
        if os.path.exists(processed_path):
            return processed_path
        
        # Process image
        with Image.open(image_path) as img:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Convert to numpy for processing
            data = np.array(img)
            
            # Make black pixels transparent (same threshold as original)
            black_mask = np.all(data[:, :, :3] < 10, axis=2)
            data[black_mask, 3] = 0  # Set alpha to 0 for black pixels
            
            # Save processed image
            processed_img = Image.fromarray(data, 'RGBA')
            processed_img.save(processed_path)
            
            return processed_path
    
    except Exception as e:
        print(f"      Warning: Failed to process image {image_path}: {e}")
        return image_path


def _assign_face_materials_to_mesh(mesh_obj, materials, mesh_info, trimesh_mesh):
    """Assign face materials using the EXACT logic from working original."""
    try:
        import bpy
    except ImportError:
        return
    
    # CRITICAL FIX: Only apply face material assignment to meshes that actually need it
    # Single-material meshes should NOT get face material assignment
    if len(materials) <= 1:
        print(f"    ⚠️ Single material mesh {mesh_obj.name} - skipping face material assignment")
        return
    
    face_materials = None
    
    # FIRST: Check mesh_info dictionary (this is where our .X parser stores face materials!)
    if mesh_info and 'face_materials' in mesh_info:
        face_materials = mesh_info['face_materials']
        print(f"    ✅ Found face materials in mesh_info: {len(face_materials)}")
    
    # Fallback: Check multiple possible locations on trimesh object
    elif hasattr(trimesh_mesh, 'visual'):
        if hasattr(trimesh_mesh.visual, 'face_materials'):
            face_materials = trimesh_mesh.visual.face_materials
            print(f"    Found face materials in visual.face_materials: {len(face_materials)}")
        elif hasattr(trimesh_mesh.visual, 'material'):
            # Check if it's a TextureVisuals with face materials
            if hasattr(trimesh_mesh.visual.material, 'face_materials'):
                face_materials = trimesh_mesh.visual.material.face_materials
                print(f"    Found face materials in visual.material.face_materials: {len(face_materials)}")
    
    # Also check if trimesh has face materials directly
    elif hasattr(trimesh_mesh, 'face_materials'):
        face_materials = trimesh_mesh.face_materials
        print(f"    Found face materials directly on mesh: {len(face_materials)}")
    
    if face_materials is not None and len(face_materials) > 0:
        print(f"    Assigning face materials: {len(face_materials)} face assignments to {len(mesh_obj.data.polygons)} polygons")
        
        mesh_obj.data.update()
        if len(mesh_obj.data.polygons) > 0:
            # CRITICAL FIX: Handle potential face reordering by from_pydata()
            # Verify that the face count matches exactly
            if len(face_materials) != len(mesh_obj.data.polygons):
                print(f"    ❌ FACE COUNT MISMATCH: {len(face_materials)} materials but {len(mesh_obj.data.polygons)} polygons")
                print(f"    This indicates face reordering or loss during from_pydata() - cannot assign materials safely")
                return
            
            # Check if trimesh face order matches Blender polygon order by comparing face vertices
            trimesh_faces = trimesh_mesh.faces if trimesh_mesh else None
            if trimesh_faces is not None and len(trimesh_faces) == len(mesh_obj.data.polygons):
                # Create mapping from Blender polygon index to original trimesh face index
                face_mapping = {}
                for blender_poly_idx, blender_poly in enumerate(mesh_obj.data.polygons):
                    blender_verts = tuple(sorted(blender_poly.vertices))
                    # Find matching trimesh face
                    for trimesh_face_idx, trimesh_face in enumerate(trimesh_faces):
                        trimesh_verts = tuple(sorted(trimesh_face))
                        if blender_verts == trimesh_verts:
                            face_mapping[blender_poly_idx] = trimesh_face_idx
                            break
                
                # Apply materials using the correct mapping
                assigned_count = 0
                material_usage = {}
                for blender_poly_idx in range(len(mesh_obj.data.polygons)):
                    if blender_poly_idx in face_mapping:
                        original_face_idx = face_mapping[blender_poly_idx]
                        if original_face_idx < len(face_materials):
                            mat_idx = face_materials[original_face_idx]
                            if mat_idx < len(materials):
                                mesh_obj.data.polygons[blender_poly_idx].material_index = mat_idx
                                assigned_count += 1
                                material_usage[mat_idx] = material_usage.get(mat_idx, 0) + 1
                
                print(f"    ✅ Assigned materials to {assigned_count}/{len(face_materials)} faces (with face mapping)")
                if assigned_count != len(face_materials):
                    print(f"    ⚠️ Some faces could not be mapped - this may indicate mesh corruption")
            else:
                # Fallback: assume face order is preserved (old behavior)
                print(f"    Using direct face mapping (assuming preserved order)")
                assigned_count = 0
                material_usage = {}
                for face_idx, mat_idx in enumerate(face_materials):
                    if face_idx < len(mesh_obj.data.polygons) and mat_idx < len(materials):
                        mesh_obj.data.polygons[face_idx].material_index = mat_idx
                        assigned_count += 1
                        material_usage[mat_idx] = material_usage.get(mat_idx, 0) + 1
                print(f"    ✅ Assigned materials to {assigned_count}/{len(face_materials)} faces (direct mapping)")
            if 'head' in mesh_obj.name.lower():
                print(f"    Debug: Material usage for {mesh_obj.name}: {material_usage}")
    else:
        print(f"    ⚠️ No face material mapping found for multi-material mesh {mesh_obj.name} - all faces will use first material")


def _load_image_with_black_as_alpha(image_path: str, make_alpha: bool) -> 'bpy.types.Image':
    """Load image in Blender with black-as-alpha processing (same as original)."""
    try:
        import bpy
    except ImportError:
        return None
    
    if not os.path.exists(image_path):
        return None
    
    try:
        # Check if image already loaded
        image_name = os.path.basename(image_path)
        if image_name in bpy.data.images:
            return bpy.data.images[image_name]
        
        # Load image
        image = bpy.data.images.load(image_path)
        image.name = image_name
        
        # Set color space - ALWAYS use sRGB for textures to be visible
        # Non-Color makes textures invisible in viewport/renders
        image.colorspace_settings.name = 'sRGB'
        
        return image
    
    except Exception as e:
        print(f"      Error loading image {image_path}: {e}")
        return None