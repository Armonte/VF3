"""
VF3 Blender Exporter
Use Blender's Python API to create proper armatures and export to glTF.
This should handle skeletal animation much better than manual glTF creation.
"""

import os
import sys
from typing import Dict, List, Any

def create_vf3_character_in_blender(bones: Dict, attachments: List, world_transforms: Dict, 
                                   mesh_data: Dict[str, Any], clothing_dynamic_meshes: List, output_path: str):
    """Create a VF3 character in Blender with proper armature and export to glTF.
    
    Args:
        bones: Bone hierarchy from .TXT file
        attachments: Mesh attachments to bones  
        world_transforms: World positions of bones
        mesh_data: Dictionary mapping attachment resource_id to mesh data
        output_path: Where to save the .glb file
    """
    
    try:
        import bpy
        import bmesh
        from mathutils import Vector, Matrix
    except ImportError:
        print("? Blender Python API not available. Run this script inside Blender or install bpy module.")
        return False
    
    print("? Creating VF3 character in Blender...")
    
    # Step 1: Clear existing scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Step 2: Create armature
    print("? Creating armature...")
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature_obj = bpy.context.active_object
    armature_obj.name = "VF3_Armature"
    armature = armature_obj.data
    armature.name = "VF3_Armature"
    
    # Get bone hierarchy order
    bone_order = _get_bone_hierarchy_order(bones)
    
    # Clear default bone
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.delete()
    
    # Step 3: Create bones using original VF3 bone system (like working commit c021d46)
    created_bones = {}
    
    for bone_name in bone_order:
        bone = bones[bone_name]
        
        # Create bone
        edit_bone = armature.edit_bones.new(bone_name)
        
        # Set bone position (head at world position, tail slightly offset)
        if bone_name in world_transforms:
            world_pos = world_transforms[bone_name]
            head_pos = Vector(world_pos)
        else:
            head_pos = Vector((0, 0, 0))
        
        edit_bone.head = head_pos
        
        # Set bone tail to point toward first child for natural rotation
        child_bones = [n for n, b in bones.items() if b.parent == bone_name]
        if child_bones:
            # Point bone toward first child
            first_child_name = child_bones[0]
            if first_child_name in world_transforms:
                child_pos = Vector(world_transforms[first_child_name])
                tail_direction = (child_pos - head_pos).normalized()
                # Make sure bone has reasonable length
                bone_length = max((child_pos - head_pos).length * 0.8, 1.0)
                edit_bone.tail = head_pos + (tail_direction * bone_length)
            else:
                edit_bone.tail = head_pos + Vector((0, 0, 1))  # Fallback
        else:
            # Leaf bone: use reasonable default
            edit_bone.tail = head_pos + Vector((0, 0, 1))
        
        # Set parent relationship
        if bone.parent and bone.parent in created_bones:
            edit_bone.parent = created_bones[bone.parent]
            edit_bone.use_connect = False  # Don't connect - allow independent rotation
        
        created_bones[bone_name] = edit_bone
        print(f"  Created bone '{bone_name}' at {head_pos}")
    
    # Step 4: Exit Edit mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Step 5: Create meshes and bind to armature
    print("? Creating and binding meshes...")
    mesh_objects = []
    
    for att in attachments:
        if att.resource_id not in mesh_data:
            continue
            
        mesh_info = mesh_data[att.resource_id]
        trimesh_mesh = mesh_info['mesh']
        
        if not trimesh_mesh:
            continue
            
        # Apply trimesh materials BEFORE converting to Blender (like original script)
        if 'materials' in mesh_info and mesh_info['materials']:
            trimesh_mesh = _apply_trimesh_materials(trimesh_mesh, mesh_info['materials'], mesh_info)
        
        # Create Blender mesh
        mesh_name = f"{att.attach_bone}_{att.resource_id}"
        blender_mesh = bpy.data.meshes.new(mesh_name)
        
        # Apply world transform to vertices
        vertices = trimesh_mesh.vertices.copy()
        if att.attach_bone in world_transforms:
            world_pos = world_transforms[att.attach_bone]
            vertices += world_pos
        
        # Set mesh data
        faces = trimesh_mesh.faces.tolist()
        blender_mesh.from_pydata(vertices.tolist(), [], faces)
        blender_mesh.update()

        # Assign UVs if available
        try:
            if hasattr(trimesh_mesh.visual, 'uv') and trimesh_mesh.visual.uv is not None:
                import numpy as np
                uv = trimesh_mesh.visual.uv
                if len(uv) == len(blender_mesh.vertices):
                    blender_mesh.uv_layers.new(name="UVMap")
                    uv_layer = blender_mesh.uv_layers.active.data
                    # Map per-loop UVs
                    loop_index = 0
                    for poly in blender_mesh.polygons:
                        for li in poly.loop_indices:
                            vidx = blender_mesh.loops[li].vertex_index
                            if vidx < len(uv):
                                # DirectX uses V=0 at top, Blender uses V=0 at bottom, so flip V
                                uv_layer[loop_index].uv = (uv[vidx][0], 1.0 - uv[vidx][1])
                            loop_index += 1
        except Exception as e:
            print(f"  UV assignment failed for {mesh_name}: {e}")
        
        # Clean up mesh to reduce z-fighting
        blender_mesh.validate()  # Fix invalid geometry
        # Remove doubles/duplicates to prevent z-fighting
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)  # Very small threshold
        bm.to_mesh(blender_mesh)
        bm.free()
        blender_mesh.update()
        
        # Enable smooth shading for Gouraud-like appearance (same as VF3)
        for poly in blender_mesh.polygons:
            poly.use_smooth = True
        print(f"  Enabled smooth shading for {mesh_name} (Gouraud rendering like VF3)")
        
        # Create mesh object
        mesh_obj = bpy.data.objects.new(mesh_name, blender_mesh)
        bpy.context.collection.objects.link(mesh_obj)
        
        # Step 5.5: Create and assign Blender materials (needed for glTF export)
        if 'materials' in mesh_info and mesh_info['materials']:
            print(f"  Creating Blender materials for {mesh_name}: {len(mesh_info['materials'])} materials")
            _create_blender_materials(mesh_obj, mesh_info['materials'], trimesh_mesh, mesh_info)
        else:
            print(f"  No materials found for {mesh_name}")
            # Create a default material so it's not completely gray
            default_mat = bpy.data.materials.new(name=f"Default_{mesh_name}")
            default_mat.use_nodes = True
            bsdf = default_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                # Set a default color based on bone name
                if 'body' in att.attach_bone.lower():
                    bsdf.inputs['Base Color'].default_value = (0.8, 0.7, 0.6, 1.0)  # Skin tone
                else:
                    bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.7, 1.0)  # Light gray
            mesh_obj.data.materials.append(default_mat)
        
        # Step 6: Create vertex groups and bind to armature (like working commit c021d46)
        if att.attach_bone in created_bones:
            # Create vertex group for this bone
            vertex_group = mesh_obj.vertex_groups.new(name=att.attach_bone)
            
            # Assign all vertices to this bone with weight 1.0
            vertex_indices = list(range(len(vertices)))
            vertex_group.add(vertex_indices, 1.0, 'REPLACE')
            
            # Add armature modifier
            armature_modifier = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
            armature_modifier.object = armature_obj
            armature_modifier.use_vertex_groups = True
            
            print(f"  Created mesh '{mesh_name}' with {len(vertices)} vertices, bound to bone '{att.attach_bone}'")
        else:
            print(f"  WARNING: No bone found for '{att.attach_bone}', mesh '{mesh_name}' will not be rigged")
        
        mesh_objects.append(mesh_obj)
    
    # Step 6: Merge breast meshes with body mesh for seamless torso
    print("? Merging breast meshes with body...")
    _merge_breast_meshes_with_body(mesh_objects)
    
    # Step 6.5: Process DynamicVisual connector meshes
    print("? Creating DynamicVisual connectors...")
    connector_count = _create_dynamic_visual_meshes(
        clothing_dynamic_meshes, world_transforms, created_bones, 
        armature_obj, mesh_objects, mesh_data
    )
    print(f"? Created {connector_count} DynamicVisual connector meshes")
    
    # Step 7: Select all objects for export
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(True)
    
    bpy.context.view_layer.objects.active = armature_obj
    
    # Step 8: Export to glTF
    print(f"? Exporting to {output_path}...")
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            export_apply=True,
            export_animations=False,  # No animations yet
            export_skins=True,        # Include armature/skinning
            export_morph=False,
            export_force_sampling=False,
            export_materials='EXPORT',  # Ensure materials are exported
            export_colors=True,        # Export vertex colors
            export_normals=True,       # Export normals to help with z-fighting
            export_tangents=True,      # Export tangents for better lighting
            export_texcoords=True,     # Export UV coordinates
            export_yup=True           # Use Y-up convention
        )
        print(f"? Successfully exported VF3 character to {output_path}")
        return True
        
    except Exception as e:
        print(f"? Export failed: {e}")
        return False


def _create_blender_materials(mesh_obj, materials: List, trimesh_mesh, mesh_info: dict = None):
    """Create Blender materials from VF3 material data."""
    try:
        import bpy
        from mathutils import Vector
    except ImportError:
        print("  ERROR: bpy not available for material creation")
        return
    
    print(f"    Creating {len(materials)} materials for mesh")
    
    # Always create materials, even if we don't have face material mapping
    for i, material_data in enumerate(materials):
        # Create Blender material
        mat_name = f"Material_{i}"
        if material_data.get('name'):
            mat_name = material_data['name']
        
        print(f"    Material {i}: {mat_name}")
        
        blender_mat = bpy.data.materials.new(name=f"{mesh_obj.name}_{mat_name}")
        blender_mat.use_nodes = True
        nodes = blender_mat.node_tree.nodes
        links = blender_mat.node_tree.links
        
        # Clear default nodes
        nodes.clear()
        
        # Create principled BSDF
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        output = nodes.new(type='ShaderNodeOutputMaterial')
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        # Set material properties to reduce z-fighting
        blender_mat.use_backface_culling = True  # Enable backface culling
        blender_mat.blend_method = 'OPAQUE'      # Use opaque blending (no alpha issues)
        
        # Set material properties
        if 'diffuse' in material_data:
            diffuse = material_data['diffuse']
            if len(diffuse) >= 3:
                color = (*diffuse[:3], 1.0)
                bsdf.inputs['Base Color'].default_value = color
                print(f"      Diffuse: {color}")
        else:
            # Default color if no diffuse
            bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
        
        if 'specular' in material_data:
            specular = material_data['specular']
            if len(specular) >= 3:
                # Use specular intensity as metallic factor
                metallic = sum(specular[:3]) / 3.0
                bsdf.inputs['Metallic'].default_value = min(metallic, 1.0)
                print(f"      Metallic: {metallic}")
        
        # Handle texture
        # Try texture list from .X materials or resolved absolute paths
        texture_path = None
        if 'texture' in material_data and material_data['texture']:
            texture_path = material_data['texture']
        elif 'textures' in material_data and material_data['textures']:
            # Use the first texture
            texture_path = material_data['textures'][0]

        if texture_path:
            # Resolve relative texture path against mesh source directory, if needed
            resolved_path = texture_path
            if not os.path.isabs(resolved_path):
                base_dir = None
                if mesh_info and 'source_path' in mesh_info:
                    base_dir = os.path.dirname(mesh_info['source_path'])
                if base_dir:
                    candidate = os.path.join(base_dir, resolved_path)
                    if os.path.exists(candidate):
                        resolved_path = candidate
                    else:
                        # Also try data root for character textures (e.g., data/stkface.bmp)
                        fallback = _find_in_data_root(os.path.basename(resolved_path), mesh_info)
                        if fallback:
                            resolved_path = fallback
            print(f"      Texture: {resolved_path}")
            if os.path.exists(resolved_path):
                # Create texture node and load image (packed) with optional black->alpha conversion, without writing files
                tex_image = nodes.new(type='ShaderNodeTexImage')
                try:
                    img = _load_image_with_black_as_alpha(resolved_path, make_alpha=('hair' in mesh_obj.name.lower() or 'head' in mesh_obj.name.lower() or 'face' in mesh_obj.name.lower()))
                    tex_image.image = img
                    # Set texture interpolation to Closest for sharp pixelated look like VF3
                    tex_image.interpolation = 'Closest'
                    # Base Color
                    links.new(tex_image.outputs['Color'], bsdf.inputs['Base Color'])
                    # Alpha hookup - use gentler settings to avoid white sheen
                    if 'hair' in mesh_obj.name.lower() or 'head' in mesh_obj.name.lower() or 'face' in mesh_obj.name.lower():
                        blender_mat.blend_method = 'CLIP'
                        blender_mat.alpha_threshold = 0.1  # Lower threshold to avoid white edges
                        blender_mat.shadow_method = 'CLIP'
                        blender_mat.use_backface_culling = True  # Enable backface culling for hair
                        if 'Alpha' in [s.name for s in tex_image.outputs]:
                            links.new(tex_image.outputs['Alpha'], bsdf.inputs['Alpha'])
                    print(f"      ? Loaded texture (packed): {img.name}")
                except Exception as e:
                    print(f"      ? Failed to load texture: {resolved_path} - {e}")
            else:
                print(f"      ? Texture file not found: {resolved_path}")
        else:
            # Try to auto-discover textures near mesh
            auto_tex = _auto_discover_texture(mesh_info, mesh_obj.name)
            if auto_tex and os.path.exists(auto_tex):
                print(f"      ? Auto texture: {auto_tex}")
                tex_image = nodes.new(type='ShaderNodeTexImage')
                try:
                    img = _load_image_with_black_as_alpha(auto_tex, make_alpha=('hair' in mesh_obj.name.lower() or 'head' in mesh_obj.name.lower() or 'face' in mesh_obj.name.lower()))
                    tex_image.image = img
                    # Set texture interpolation to Closest for sharp pixelated look like VF3
                    tex_image.interpolation = 'Closest'
                    links.new(tex_image.outputs['Color'], bsdf.inputs['Base Color'])
                    if 'hair' in mesh_obj.name.lower() or 'head' in mesh_obj.name.lower() or 'face' in mesh_obj.name.lower():
                        blender_mat.blend_method = 'CLIP'
                        blender_mat.alpha_threshold = 0.1  # Lower threshold to avoid white edges
                        blender_mat.shadow_method = 'CLIP'
                        blender_mat.use_backface_culling = True  # Enable backface culling for hair
                        if 'Alpha' in [s.name for s in tex_image.outputs]:
                            links.new(tex_image.outputs['Alpha'], bsdf.inputs['Alpha'])
                    print(f"      ? Loaded texture (packed): {img.name}")
                except Exception as e:
                    print(f"      ? Failed to load texture: {auto_tex} - {e}")
        
        # Add material to mesh
        mesh_obj.data.materials.append(blender_mat)
        print(f"      ? Added material {mat_name} to mesh")
    
    # Try to assign face materials if available
    face_materials = None
    
    # FIRST: Check mesh_info dictionary (this is where our .X parser stores face materials!)
    if mesh_info and 'face_materials' in mesh_info:
        face_materials = mesh_info['face_materials']
        print(f"    ? Found face materials in mesh_info: {len(face_materials)}")
    
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
    
    # Debug: print what we have available
    if mesh_info:
        print(f"    mesh_info keys: {list(mesh_info.keys())}")
    if hasattr(trimesh_mesh, 'visual'):
        print(f"    Visual type: {type(trimesh_mesh.visual)}")
        visual_attrs = [attr for attr in dir(trimesh_mesh.visual) if not attr.startswith('_')]
        print(f"    Visual attributes: {visual_attrs}")
    
    if face_materials is not None and len(face_materials) > 0:
        print(f"    Assigning face materials: {len(face_materials)} face assignments to {len(mesh_obj.data.polygons)} polygons")
        
        mesh_obj.data.update()
        if len(mesh_obj.data.polygons) > 0:
            assigned_count = 0
            for face_idx, mat_idx in enumerate(face_materials):
                if face_idx < len(mesh_obj.data.polygons) and mat_idx < len(materials):
                    mesh_obj.data.polygons[face_idx].material_index = mat_idx
                    assigned_count += 1
            print(f"    ? Assigned materials to {assigned_count}/{len(face_materials)} faces")
    else:
        print("    ? No face material mapping found - all faces will use first material (white)")


def _find_in_data_root(filename: str, mesh_info: dict) -> str:
    try:
        # Ascend until a directory named 'data' is found
        start = os.path.dirname(mesh_info['source_path']) if mesh_info and 'source_path' in mesh_info else ''
        cur = start
        data_dir = ''
        while cur and os.path.dirname(cur) != cur:
            if os.path.basename(cur).lower() == 'data' and os.path.isdir(cur):
                data_dir = cur
                break
            cur = os.path.dirname(cur)
        if not data_dir:
            return ''
        # Direct match first
        candidate = os.path.join(data_dir, filename)
        if os.path.exists(candidate):
            return candidate
        # Recursive search case-insensitive
        target = filename.lower()
        for root, _dirs, files in os.walk(data_dir):
            for fn in files:
                if fn.lower() == target:
                    return os.path.join(root, fn)
        return ''
    except Exception:
        return ''


def _auto_discover_texture(mesh_info: dict, mesh_name: str) -> str:
    try:
        if not mesh_info or 'source_path' not in mesh_info:
            return ''
        base_dir = os.path.dirname(mesh_info['source_path'])
        if not os.path.isdir(base_dir):
            return ''
        # Prioritize likely names
        priorities = ['hair', 'face', 'head', 'skin']
        exts = ['.png', '.jpg', '.jpeg', '.bmp', '.tga']
        candidates = []
        for fn in os.listdir(base_dir):
            lower = fn.lower()
            if any(lower.endswith(e) for e in exts):
                # Score by priority keyword and mesh name overlap
                score = 0
                for p in priorities:
                    if p in lower:
                        score += 10
                for token in mesh_name.lower().split('_'):
                    if token and token in lower:
                        score += 1
                candidates.append((score, os.path.join(base_dir, fn)))
        if not candidates:
            return ''
        candidates.sort(reverse=True)
        return candidates[0][1]
    except Exception:
        return ''


def _ensure_alpha_from_black(image_path: str) -> str:
    """If image lacks alpha (e.g., BMP), generate a PNG with alpha where near-black becomes transparent."""
    try:
        import bpy
        # Load
        img = bpy.data.images.load(image_path)
        # If already has alpha data that isn't fully opaque, keep
        has_alpha = img.channels == 4
        if has_alpha:
            # Inspect a small sample
            px = list(img.pixels)
            if any(px[i+3] < 0.999 for i in range(0, min(len(px), 4000), 4)):
                return image_path
        # Ensure 4 channels
        if img.channels < 4:
            img.colorspace_settings.name = 'sRGB'
        # Build alpha from black threshold - be more aggressive for hair textures
        px = list(img.pixels)  # RGBA floats 0..1
        n = len(px)
        # Use gentler threshold for hair to avoid white sheen
        threshold = 0.05 if make_alpha else 0.05  # Same threshold for both
        for i in range(0, n, 4):
            r, g, b, a = px[i], px[i+1], px[i+2], 1.0
            # Near-black threshold - higher for hair textures
            if r < threshold and g < threshold and b < threshold:
                a = 0.0
            px[i], px[i+1], px[i+2], px[i+3] = r, g, b, a
        img.pixels[:] = px
        # Save as PNG next to source
        base_dir = os.path.dirname(image_path)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        out_path = os.path.join(base_dir, f"{base_name}_alpha.png")
        img.filepath_raw = out_path
        img.file_format = 'PNG'
        img.save()
        return out_path if os.path.exists(out_path) else image_path
    except Exception:
        return image_path


def _load_image_with_black_as_alpha(image_path: str, make_alpha: bool) -> 'bpy.types.Image':
    """Load image with proper black-as-alpha processing using PIL approach from original script."""
    import bpy
    
    try:
        from PIL import Image
        import numpy as np
        
        # Check if image already loaded in Blender to avoid duplicates
        img_name = os.path.basename(image_path)
        existing_img = bpy.data.images.get(img_name)
        if existing_img:
            print(f"      ? Reusing existing image: {img_name}")
            return existing_img
        
        # Use PIL to load and process the image (same as original script)
        pil_img = Image.open(image_path)
        
        # Handle black-as-alpha transparency (from original script)
        if make_alpha:
            # Convert to RGBA if needed
            if pil_img.mode != 'RGBA':
                pil_img = pil_img.convert('RGBA')
            
            # Create alpha channel based on black pixels
            data = np.array(pil_img)
            # Check for pixels that are very close to black (RGB < 5) - gentler to avoid white sheen
            black_mask = np.all(data[:, :, :3] < 5, axis=2)
            # Set alpha to 0 for black pixels
            data[black_mask, 3] = 0
            
            # Update image with alpha channel
            pil_img = Image.fromarray(data, 'RGBA')
        
        # Convert PIL image to Blender image
        width, height = pil_img.size
        
        # Create new Blender image with alpha if needed
        has_alpha = make_alpha or pil_img.mode == 'RGBA'
        blender_img = bpy.data.images.new(name=img_name, width=width, height=height, alpha=has_alpha)
        
        # Convert PIL image to Blender pixel format
        if has_alpha:
            # RGBA format
            if pil_img.mode != 'RGBA':
                pil_img = pil_img.convert('RGBA')
            pixels = np.array(pil_img).astype(np.float32) / 255.0  # Convert to 0-1 range
            # Blender expects flattened RGBA (no Y flip to match original)
            pixels = pixels.flatten()
        else:
            # RGB format
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            pixels = np.array(pil_img).astype(np.float32) / 255.0  # Convert to 0-1 range
            # Blender expects flattened RGB (no Y flip to match original)
            pixels = pixels.flatten()
        
        # Assign pixels to Blender image
        blender_img.pixels[:] = pixels
        
        # Update image to ensure changes are applied
        blender_img.update()
        
        # Pack image to embed in .blend and glTF
        blender_img.pack()
        
        print(f"      ? Processed texture with PIL: {img_name} ({'RGBA' if has_alpha else 'RGB'})")
        return blender_img
        
    except ImportError:
        print("      ?? PIL not available, falling back to direct Blender loading")
        # Fallback to direct Blender loading
        img = bpy.data.images.load(image_path)
        img.pack()
        return img
    except Exception as e:
        print(f"      ? Failed to process texture with PIL: {e}, falling back to direct loading")
        # Fallback to direct Blender loading
        img = bpy.data.images.load(image_path)
        img.pack()
        return img


def process_vf3_dynamic_visual_faces(vertices, vertex_bones, faces, dyn_idx, world_transforms, 
                                    created_bones, armature_obj, mesh_objects, base_connector_count):
    """
    Process DynamicVisual data using VF3-accurate approach with original FaceArray.
    This preserves the exact face connectivity that VF3 uses.
    """
    import bpy
    import bmesh
    import numpy as np
    from mathutils import Vector
    
    print(f"    VF3-accurate processing: {len(vertices)} vertices, {len(faces)} faces, {len(set(vertex_bones))} unique bones")
    
    # Group vertices by bone (like VF3 does)
    bone_vertex_groups = {}
    for v_idx, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
        if bone_name not in bone_vertex_groups:
            bone_vertex_groups[bone_name] = {
                'vertices': [],
                'vertex_indices': [],
                'bone': bone_name
            }
        bone_vertex_groups[bone_name]['vertices'].append(vertex_tuple)
        bone_vertex_groups[bone_name]['vertex_indices'].append(v_idx)
    
    print(f"    VF3 bone groups: {list(bone_vertex_groups.keys())}")
    
    # Create one connector per bone (like original VF3) - this fixes missing faces issue
    connectors_created = []
    connector_count = base_connector_count
    
    for bone_name, bone_group in bone_vertex_groups.items():
        if bone_name not in created_bones:
            print(f"      Skipping bone {bone_name} - not in armature")
            continue
            
        # Get ALL vertices for this bone
        bone_vertex_indices = set(bone_group['vertex_indices'])
        bone_vertices = bone_group['vertices']
        
        # Create vertex mapping: original index -> new bone-local index
        vertex_mapping = {}
        final_vertices = []
        
        # Add all vertices that belong to this bone
        for orig_idx in bone_vertex_indices:
            vertex_mapping[orig_idx] = len(final_vertices)
            final_vertices.append(vertices[orig_idx])
        
        # Get faces that involve this bone's vertices
        bone_faces = []
        for face in faces:
            face_vertices_in_bone = [v_idx for v_idx in face if v_idx in bone_vertex_indices]
            
            if face_vertices_in_bone:  # Face has at least one vertex from this bone
                # Add any missing vertices from this face to our vertex list
                new_face = []
                for v_idx in face:
                    if v_idx in vertex_mapping:
                        # Already have this vertex
                        new_face.append(vertex_mapping[v_idx])
                    else:
                        # Add vertex from another bone
                        vertex_mapping[v_idx] = len(final_vertices)
                        final_vertices.append(vertices[v_idx])
                        new_face.append(vertex_mapping[v_idx])
                
                bone_faces.append(new_face)
        
        if not bone_faces:
            print(f"      No faces for bone {bone_name}")
            continue
            
        print(f"      Creating connector for {bone_name}: {len(final_vertices)} vertices, {len(bone_faces)} faces")
        
        # Create the connector mesh using exact VF3 vertex positioning
        try:
            mesh_name = f"dynamic_connector_{connector_count}_{bone_name}"
            mesh = bpy.data.meshes.new(mesh_name)
            
            # Process vertices with VF3-accurate positioning
            blender_vertices = []
            vertex_bone_names = []
            
            bone_pos = world_transforms.get(bone_name, (0.0, 0.0, 0.0))
            
            for i, vertex_tuple in enumerate(final_vertices):
                pos1, pos2 = vertex_tuple
                
                # Use pos1 with bone world transform (like regular meshes)
                world_pos = [
                    pos1[0] + bone_pos[0],
                    pos1[1] + bone_pos[1], 
                    pos1[2] + bone_pos[2]
                ]
                
                blender_vertices.append(world_pos)
                # Determine which bone this vertex should be bound to
                if i < len(bone_vertex_indices):
                    vertex_bone_names.append(bone_name)
                else:
                    # Vertex was added from another bone - find which one
                    orig_idx = list(vertex_mapping.keys())[list(vertex_mapping.values()).index(i)]
                    if orig_idx < len(vertex_bones):
                        vertex_bone_names.append(vertex_bones[orig_idx])
                    else:
                        vertex_bone_names.append(bone_name)  # Fallback
            
            # Create mesh
            mesh.from_pydata(blender_vertices, [], bone_faces)
            mesh.update()
            
            # Create mesh object
            mesh_obj = bpy.data.objects.new(mesh_name, mesh)
            bpy.context.collection.objects.link(mesh_obj)
            mesh_objects.append(mesh_obj)
            
            # Create vertex groups and bind to bones
            created_vertex_groups = set()
            for vertex_idx, bone_bind_name in enumerate(vertex_bone_names):
                if bone_bind_name in created_bones and bone_bind_name not in created_vertex_groups:
                    vg = mesh_obj.vertex_groups.new(name=bone_bind_name)
                    created_vertex_groups.add(bone_bind_name)
                
                # Assign vertex to its bone group with full weight
                if bone_bind_name in created_vertex_groups:
                    vg = mesh_obj.vertex_groups[bone_bind_name]
                    vg.add([vertex_idx], 1.0, 'REPLACE')
            
            # Parent to armature with automatic weights disabled (we set exact weights)
            mesh_obj.parent = armature_obj
            mesh_obj.parent_type = 'ARMATURE'
            
            print(f"      ✅ Created VF3-accurate connector: {mesh_name} with {len(final_vertices)} vertices, {len(bone_faces)} faces")
            connectors_created.append(mesh_name)
            connector_count += 1
            
        except Exception as e:
            print(f"      ❌ Failed to create VF3 connector for {bone_name}: {e}")
            continue
    
    return connectors_created


def _snap_vertex_to_nearest_mesh(candidate_pos: List[float], all_mesh_vertices: 'np.ndarray', snap_threshold: float = 1.5) -> List[float]:
    """Snap a vertex to the nearest existing mesh vertex if within threshold to eliminate seams."""
    import numpy as np
    
    if len(all_mesh_vertices) == 0:
        return candidate_pos
    
    candidate_array = np.array(candidate_pos)
    
    # Find closest vertex using vectorized distance calculation
    distances = np.linalg.norm(all_mesh_vertices - candidate_array, axis=1)
    min_distance = np.min(distances)
    
    if min_distance <= snap_threshold:
        closest_idx = np.argmin(distances)
        snapped_pos = all_mesh_vertices[closest_idx].tolist()
        # print(f"      Snapped vertex: distance {min_distance:.3f} -> snapped to existing vertex")
        return snapped_pos
    else:
        return candidate_pos


def _merge_breast_meshes_with_body(mesh_objects):
    """
    Merge breast meshes with the body mesh to create a unified torso mesh.
    This eliminates seams between breasts and body.
    """
    try:
        import bpy
    except ImportError:
        return
    
    # Find body and breast meshes
    body_mesh = None
    breast_meshes = []
    
    for mesh_obj in mesh_objects:
        if hasattr(mesh_obj, 'name'):
            mesh_name = mesh_obj.name.lower()
            if 'body_female.body' in mesh_name:
                body_mesh = mesh_obj
            elif 'breast_female' in mesh_name:
                breast_meshes.append(mesh_obj)
    
    if not body_mesh or not breast_meshes:
        print(f"  Body mesh: {body_mesh.name if body_mesh else 'Not found'}")
        print(f"  Breast meshes: {len(breast_meshes)} found")
        return
    
    print(f"  Found body mesh: {body_mesh.name}")
    print(f"  Found {len(breast_meshes)} breast meshes: {[m.name for m in breast_meshes]}")
    
    # Store names BEFORE join operation since objects will become invalid
    merged_names = [m.name for m in breast_meshes]
    
    try:
        # Select all meshes to be merged
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select body mesh as primary target
        body_mesh.select_set(True)
        
        # Select all breast meshes
        for breast_mesh in breast_meshes:
            breast_mesh.select_set(True)
        
        # Set body mesh as active object
        bpy.context.view_layer.objects.active = body_mesh
        
        # Join all selected meshes into the body mesh
        bpy.ops.object.join()
        
        # Clean up seams between merged parts
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge very close vertices
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Remove merged breast meshes from mesh_objects list since they no longer exist
        
        # Filter out merged meshes - be careful with object validity 
        valid_objects = []
        for m in mesh_objects:
            try:
                # Test if object is still valid by accessing its name
                mesh_name = m.name
                if mesh_name not in merged_names:
                    valid_objects.append(m)
            except (ReferenceError, AttributeError):
                # Object has been deleted, skip it
                pass
        mesh_objects[:] = valid_objects
        
        print(f"  ✅ Successfully merged {len(breast_meshes)} breast meshes with body mesh")
        print(f"  Removed {len(merged_names)} merged meshes from export list")
        
    except Exception as e:
        print(f"  ❌ Failed to merge breast meshes: {e}")


def _try_merge_connector_with_body_mesh(connector_obj, mesh_objects, vertex_bone_names):
    """
    Try to merge a DynamicVisual connector mesh with an adjacent body mesh to create unified geometry.
    This eliminates separate mesh instances and creates seamless connections.
    Returns: (success, merged_mesh_names) - success bool and list of mesh names that were merged and removed
    """
    try:
        import bpy
        import bmesh
        from mathutils import Vector
    except ImportError:
        return False, []
    
    if not connector_obj or not mesh_objects:
        return False, []
    
    # Determine which body mesh this connector should merge with based on bone names
    target_mesh = None
    connector_name = connector_obj.name.lower()
    
    # Define merging candidates based on connector number (determined from DynamicVisual processing order)
    # Order is based on the occupancy slot processing: body, arms, hands, waist, legs, foots
    merge_candidates_by_number = {
        '0': ['body_female'],  # Body/torso connectors (breasts already merged with body)
        '1': ['l_arm1_female', 'r_arm1_female', 'l_arm2_female', 'r_arm2_female'],  # Arm connectors
        '2': ['l_hand_female', 'r_hand_female'],  # Hand/wrist connectors  
        '3': ['waist_female', 'body_female'],  # Waist connectors
        '4': ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female'],  # Leg connectors (hips/knees/thighs)
        '5': ['l_foot_female', 'r_foot_female', 'l_leg2_female', 'r_leg2_female']  # Foot/ankle connectors
    }
    
    # Extract connector number from name (e.g., "dynamic_connector_0_vf3mesh" -> "0")
    target_categories = []
    import re
    match = re.search(r'dynamic_connector_(\d+)_', connector_name)
    if match:
        connector_number = match.group(1)
        target_categories = merge_candidates_by_number.get(connector_number, [])
        print(f"      Connector {connector_number} -> merge targets: {target_categories}")
    else:
        # Fallback to old logic for non-numbered connectors
        merge_candidates = {
            'breast': ['l_breast_female', 'r_breast_female', 'breast'],
            'shoulder': ['l_arm1_female', 'r_arm1_female', 'torso'],  
            'elbow': ['l_arm1_female', 'r_arm1_female', 'l_arm2_female', 'r_arm2_female'],
            'wrist': ['l_arm2_female', 'r_arm2_female', 'l_hand_female', 'r_hand_female'],
            'hip': ['waist_female', 'l_leg1_female', 'r_leg1_female'],
            'knee': ['l_leg1_female', 'r_leg1_female', 'l_leg2_female', 'r_leg2_female'],
            'ankle': ['l_leg2_female', 'r_leg2_female', 'l_foot_female', 'r_foot_female'],
            'thigh': ['l_leg1_female', 'r_leg1_female', 'waist_female'],
            'torso': ['body_female', 'waist_female']
        }
        
        for category, candidates in merge_candidates.items():
            if category in connector_name:
                target_categories = candidates
                break
    
    if not target_categories:
        print(f"      No merge candidates found for connector: {connector_name}")
        return False, []
    
    # Find all target mesh objects that match the categories
    target_meshes = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            mesh_name_lower = mesh_obj.name.lower()
            for candidate in target_categories:
                if candidate.lower() in mesh_name_lower:
                    target_meshes.append(mesh_obj)
                    break
        except (ReferenceError, AttributeError):
            # Object has been deleted, skip it
            continue
    
    if not target_meshes:
        print(f"      No suitable body mesh found to merge connector: {connector_name}")
        return False, []
    
    # Perform the actual mesh merging
    try:
        # For breast connectors (connector 0), merge with all breast meshes first, then merge everything
        if len(target_meshes) > 1:
            print(f"      Found {len(target_meshes)} target meshes: {[m.name for m in target_meshes]}")
            
            # Collect names of meshes that will be merged (all except primary target) BEFORE merging
            primary_target = target_meshes[0]  # Use first mesh as primary target
            merged_names = [m.name for m in target_meshes[1:]]  # Exclude primary target which still exists
            
            # Select all target meshes and the connector
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select all meshes to be merged
            for mesh in target_meshes:
                mesh.select_set(True)
            connector_obj.select_set(True)
            
            # Set primary target as active object
            bpy.context.view_layer.objects.active = primary_target
            
            # Join all selected meshes into the primary target
            bpy.ops.object.join()
            
            # Clean up seams
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge very close vertices
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"      ✅ Successfully merged connector {connector_name} with {len(target_meshes)} meshes into {primary_target.name}")
            return True, merged_names
        else:
            # Single target mesh - use original logic
            target_mesh = target_meshes[0]
            
            # Select both meshes
            bpy.context.view_layer.objects.active = target_mesh
            bpy.ops.object.select_all(action='DESELECT')
            target_mesh.select_set(True)
            connector_obj.select_set(True)
            
            # Join the meshes (connector into target)
            bpy.context.view_layer.objects.active = target_mesh
            bpy.ops.object.join()
            
            # Clean up any duplicate vertices at the seam
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.001)  # Merge very close vertices
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"      ✅ Successfully merged connector {connector_name} with {target_mesh.name}")
            return True, []  # No additional meshes were removed in single target merge
        
    except Exception as e:
        print(f"      ❌ Failed to merge connector {connector_name}: {e}")
        return False, []


def _create_dynamic_visual_meshes(clothing_dynamic_meshes, world_transforms, created_bones, 
                                armature_obj, mesh_objects, mesh_data):
    """Create DynamicVisual connector meshes in Blender with proper bone binding."""
    try:
        import bpy
        import bmesh
        import numpy as np
        from mathutils import Vector
    except ImportError:
        print("  Blender imports not available")
        return 0
    
    if not clothing_dynamic_meshes:
        print("  No DynamicVisual meshes to process")
        return 0
    
    connector_count = 0
    created_regions = set()  # Track regions already created to prevent duplicates
    
    # Collect all mesh vertices for snapping
    all_mesh_vertices = []
    for mesh_obj in mesh_objects:
        if hasattr(mesh_obj.data, 'vertices'):
            for v in mesh_obj.data.vertices:
                world_co = mesh_obj.matrix_world @ v.co
                all_mesh_vertices.append(world_co)
    
    all_mesh_vertices = np.array([[v.x, v.y, v.z] for v in all_mesh_vertices])
    print(f"  Collected {len(all_mesh_vertices)} vertices from existing meshes for snapping")
    
    for dyn_idx, dyn_data in enumerate(clothing_dynamic_meshes):
        if not (dyn_data and 'vertices' in dyn_data and 'faces' in dyn_data):
            continue
            
        vertices = dyn_data['vertices']  # List of (pos1, pos2) tuples
        vertex_bones = dyn_data.get('vertex_bones', [])
        faces = np.array(dyn_data['faces'])
        
        if len(vertices) == 0 or len(faces) == 0:
            continue
            
        print(f"  Processing DynamicVisual mesh {dyn_idx}: {len(vertices)} vertices, {len(faces)} faces")
        
        # Use TRUE VF3-accurate approach: Create ONE mesh per DynamicVisual block using EXACT FaceArray
        # This is exactly how VF3 works - no anatomical grouping, just one geometry per block
        print(f"    Using TRUE VF3-accurate approach: ONE mesh with {len(faces)} exact faces")
        
        # Use faces EXACTLY as provided by VF3 FaceArray (no reconstruction)
        connector_faces = faces  # Use exact face connectivity from VF3
        
        # Process vertices with their bone binding information + snap to eliminate seams
        processed_vertices = []
        vertex_bone_names = []
        
        for i, (vertex_tuple, bone_name) in enumerate(zip(vertices, vertex_bones)):
            pos1, pos2 = vertex_tuple
            
            # Get bone's world position
            bone_pos = world_transforms.get(bone_name, (0.0, 0.0, 0.0))
            
            # Use pos1 + bone transform (like regular meshes) - this is what VF3 does
            candidate_pos = [
                pos1[0] + bone_pos[0],
                pos1[1] + bone_pos[1], 
                pos1[2] + bone_pos[2]
            ]
            
            # Snap to nearest existing mesh vertex to eliminate seams/gaps  
            snapped_pos = _snap_vertex_to_nearest_mesh(candidate_pos, all_mesh_vertices, snap_threshold=0.5)
            
            processed_vertices.append(snapped_pos)
            vertex_bone_names.append(bone_name)
        
        # Create ONE Blender mesh for this entire DynamicVisual block (like VF3)
        connector_name = f"dynamic_connector_{connector_count}_vf3mesh"
        blender_mesh = bpy.data.meshes.new(connector_name)
        
        # Create mesh with EXACT VF3 faces - no modifications
        vertices_list = [[v[0], v[1], v[2]] for v in processed_vertices]
        faces_list = connector_faces  # Use exact faces from VF3 FaceArray
        
        blender_mesh.from_pydata(vertices_list, [], faces_list)
        blender_mesh.update()
        
        # Enable smooth shading
        for poly in blender_mesh.polygons:
            poly.use_smooth = True
        
        # Create mesh object
        connector_obj = bpy.data.objects.new(connector_name, blender_mesh)
        bpy.context.collection.objects.link(connector_obj)
        
        # Create material using actual VF3 material data
        material = bpy.data.materials.new(name=f"{connector_name}_material")
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Use actual material color from DynamicVisual Material section
            skin_color = (1.000, 0.759, 0.586)  # Standard skin tone from regular meshes
            applied_color = skin_color  # Default to skin tone for all connectors
            
            if 'materials' in dyn_data and len(dyn_data['materials']) > 0:
                # Parse the first material entry: (r,g,b,a)::
                material_line = dyn_data['materials'][0]
                try:
                    # Extract color values from "(r,g,b,a)::" format
                    if material_line.startswith('(') and ')' in material_line:
                        color_part = material_line[material_line.find('(')+1:material_line.find(')')]
                        color_values = [float(x.strip()) for x in color_part.split(',')]
                        if len(color_values) >= 3:
                            # Convert from 0-255 range to 0-1 range and apply gamma correction like regular meshes
                            r = (color_values[0] / 255.0) ** 2.2
                            g = (color_values[1] / 255.0) ** 2.2  
                            b = (color_values[2] / 255.0) ** 2.2
                            a = color_values[3] / 255.0 if len(color_values) > 3 else 1.0
                            
                            # Only use parsed color if it's not pure white (which often means "use default")
                            if not (r > 0.95 and g > 0.95 and b > 0.95):
                                applied_color = (r, g, b)
                                print(f"      Applied VF3 material color: ({r:.3f}, {g:.3f}, {b:.3f})")
                            else:
                                print(f"      VF3 material is white, using skin tone instead: ({applied_color[0]:.3f}, {applied_color[1]:.3f}, {applied_color[2]:.3f})")
                        else:
                            print(f"      Invalid material values, using skin tone: ({applied_color[0]:.3f}, {applied_color[1]:.3f}, {applied_color[2]:.3f})")
                    else:
                        print(f"      Invalid material format, using skin tone: ({applied_color[0]:.3f}, {applied_color[1]:.3f}, {applied_color[2]:.3f})")
                except:
                    print(f"      Failed to parse material, using skin tone: ({applied_color[0]:.3f}, {applied_color[1]:.3f}, {applied_color[2]:.3f})")
            else:
                print(f"      No material data, using skin tone: ({applied_color[0]:.3f}, {applied_color[1]:.3f}, {applied_color[2]:.3f})")
                
            bsdf.inputs['Base Color'].default_value = (*applied_color, 1.0)
        connector_obj.data.materials.append(material)
        
        # Bind vertices to their respective bones (like VF3 does with bone flags)
        created_vertex_groups = set()
        for vertex_idx, bone_name in enumerate(vertex_bone_names):
            if bone_name in created_bones and bone_name not in created_vertex_groups:
                vertex_group = connector_obj.vertex_groups.new(name=bone_name)
                created_vertex_groups.add(bone_name)
            
            # Bind this vertex to its bone with full weight
            if bone_name in created_vertex_groups:
                vertex_group = connector_obj.vertex_groups[bone_name]
                vertex_group.add([vertex_idx], 1.0, 'REPLACE')
        
        # Add armature modifier
        armature_modifier = connector_obj.modifiers.new(name="Armature", type='ARMATURE')
        armature_modifier.object = armature_obj
        armature_modifier.use_vertex_groups = True
        
        # Try to merge this connector with adjacent body meshes to eliminate seams completely
        merged_with_existing, merged_mesh_names = _try_merge_connector_with_body_mesh(connector_obj, mesh_objects, vertex_bone_names)
        
        if not merged_with_existing:
            # Add to mesh objects list for export only if not merged
            mesh_objects.append(connector_obj)
            print(f"    ✅ Created standalone VF3 connector: {connector_name} with {len(vertices_list)} vertices, {len(faces_list)} faces")
        else:
            # Remove merged meshes from mesh_objects list to prevent issues with subsequent connectors
            if merged_mesh_names:
                # Be careful with object filtering - check if objects are still valid
                valid_objects = []
                for m in mesh_objects:
                    try:
                        mesh_name = m.name
                        if mesh_name not in merged_mesh_names:
                            valid_objects.append(m)
                    except (ReferenceError, AttributeError):
                        # Object has been deleted, skip it
                        pass
                mesh_objects[:] = valid_objects
                print(f"    ✅ Merged VF3 connector: {connector_name} with existing body mesh, removed {len(merged_mesh_names)} merged meshes from list")
            else:
                print(f"    ✅ Merged VF3 connector: {connector_name} with existing body mesh")
        
        connector_count += 1
    return connector_count


def _get_joint_bone_weights_for_region(region_name: str, region_vertex_bones: List[str], created_bones: Dict) -> Dict[str, float]:
    """
    Determine which bones should influence a connector region and with what weights.
    This enables proper joint deformation (e.g., elbow connectors bend with elbow rotation).
    """
    # Define joint bone weights for each region type - CORRECTED ANATOMY
    joint_weight_mappings = {
        # Shoulder joints: mostly body connection to upper arm
        'left_shoulder': {'body': 0.7, 'l_arm1': 0.3},
        'right_shoulder': {'body': 0.7, 'r_arm1': 0.3},
        
        # Elbow joints: blend between upper arm (l_arm1) and forearm (l_arm2)
        'left_elbow': {'l_arm1': 0.5, 'l_arm2': 0.5},
        'right_elbow': {'r_arm1': 0.5, 'r_arm2': 0.5},
        
        # Forearm regions (when not part of elbow joint)
        'left_forearm': {'l_arm2': 1.0},
        'right_forearm': {'r_arm2': 1.0},
        
        # Wrist joints: blend between forearm and hand
        'left_wrist': {'l_arm2': 0.7, 'l_hand': 0.3},
        'right_wrist': {'r_arm2': 0.7, 'r_hand': 0.3},
        
        # Hip joints: blend between waist and thigh (l_leg1 = thigh bone)
        'left_hip': {'waist': 0.6, 'l_leg1': 0.4},
        'right_hip': {'waist': 0.6, 'r_leg1': 0.4},
        
        # Knee joints: blend between thigh (l_leg1) and shin (l_leg2)  
        'left_knee': {'l_leg1': 0.5, 'l_leg2': 0.5},
        'right_knee': {'r_leg1': 0.5, 'r_leg2': 0.5},
        
        # Ankle joints: blend between shin and foot
        'left_ankle': {'l_leg2': 0.7, 'l_foot': 0.3},
        'right_ankle': {'r_leg2': 0.7, 'r_foot': 0.3},
        
        # Breast connection: merged connector with both breast bones
        'breast_connection': {'body': 0.6, 'l_breast': 0.2, 'r_breast': 0.2},
        
        # Torso connection: only body (waist handled by separate mesh)
        'torso': {'body': 1.0},
    }
    
    # Return the bone weights for this region, filtered by available bones
    if region_name in joint_weight_mappings:
        weights = joint_weight_mappings[region_name]
        # Only return weights for bones that actually exist in the armature
        return {bone: weight for bone, weight in weights.items() if bone in created_bones}
    else:
        # Unknown region - no specific weighting
        return {}


def _collect_attachments_with_occupancy_filtering(desc):
    """
    Collect attachments with proper occupancy-based filtering to prevent clothing/body conflicts.
    
    This implements the VF3 replacement logic where higher occupancy values override lower ones:
    - Blazer (3,3) REPLACES female.body (1) and female.arms (1) 
    - SkirtA (2) REPLACES female.waist (1)
    - ShoesA (3) REPLACES female.foots (1)
    """
    try:
        from vf3_loader import (
            parse_attachment_block_lines, 
            resolve_identifier_to_attachments,
            parse_defaultcos,
            parse_dynamic_visual_mesh
        )
        from vf3_occupancy import filter_attachments_by_occupancy_with_dynamic, parse_occupancy_vector
    except ImportError as e:
        print(f"Failed to import VF3 modules: {e}")
        return [], []
    
    print("OCCUPANCY: Collecting attachments with proper clothing replacement logic...")
    
    # Parse skin attachments with occupancy vectors
    skin_attachments_with_occupancy = []
    skin_dynamic_meshes = []
    
    skin_lines = desc.blocks.get('skin', [])
    for line in skin_lines:
        if not line.strip() or ':' not in line:
            continue
        
        # Parse line format: "occupancy_vector:resource_id"
        parts = line.strip().split(':', 1)
        if len(parts) != 2:
            continue
            
        occ_str, resource_id = parts
        occupancy_vector = parse_occupancy_vector(occ_str)
        
        # Resolve the resource ID to attachments and DynamicVisual data
        skin_attachments, skin_dyn_mesh = resolve_identifier_to_attachments(resource_id.strip(), desc)
        
        if skin_attachments:
            skin_attachments_with_occupancy.append({
                'occupancy': occupancy_vector,
                'source': f'skin:{resource_id}',
                'attachments': skin_attachments,
                'dynamic_mesh': skin_dyn_mesh
            })
            print(f"  SKIN: {resource_id} -> occupancy {occupancy_vector}, {len(skin_attachments)} attachments")
    
    # Parse clothing attachments from defaultcos with occupancy vectors
    clothing_attachments_with_occupancy = []
    clothing_dynamic_meshes = []
    
    # TEMP: Disable clothing to focus on naked base body DynamicVisual connectors
    default_costume = []  # parse_defaultcos(desc)
    print(f"  DEBUG: NAKED MODE - Disabled clothing, only loading base skin")
    for costume_item in default_costume:
        # Look for the costume item definition
        # Handle namespace: "satsuki.blazer" -> try both "satsuki.blazer" and "blazer"
        block_name = None
        if costume_item in desc.blocks:
            block_name = costume_item
        elif '.' in costume_item:
            # Try without namespace prefix
            short_name = costume_item.split('.', 1)[1]
            if short_name in desc.blocks:
                block_name = short_name
                print(f"    DEBUG: Found block '{short_name}' for costume item '{costume_item}'")
        
        if block_name:
            print(f"    DEBUG: Processing costume block '{block_name}' for item '{costume_item}'")
            costume_lines = desc.blocks[block_name]
            print(f"    DEBUG: Block has {len(costume_lines)} lines: {costume_lines}")
            for line in costume_lines:
                if not line.strip() or ':' not in line:
                    continue
                if line.strip().startswith('class:'):
                    continue
                
                # Parse line format: "occupancy_vector:vp_block_name"
                parts = line.strip().split(':', 1) 
                if len(parts) != 2:
                    continue
                    
                occ_str, vp_block_name = parts
                occupancy_vector = parse_occupancy_vector(occ_str)
                
                # Get attachments from the *_vp block (handle namespace)
                vp_block = desc.blocks.get(vp_block_name)
                if not vp_block and '.' in vp_block_name:
                    # Try without namespace prefix
                    short_vp_name = vp_block_name.split('.', 1)[1]
                    vp_block = desc.blocks.get(short_vp_name)
                    if vp_block:
                        print(f"      DEBUG: Found vp_block '{short_vp_name}' for '{vp_block_name}'")
                if vp_block:
                    clothing_attachments = parse_attachment_block_lines(vp_block)
                    clothing_dyn_mesh = parse_dynamic_visual_mesh(vp_block)
                    
                    if clothing_attachments:
                        clothing_attachments_with_occupancy.append({
                            'occupancy': occupancy_vector,
                            'source': f'clothing:{costume_item}',
                            'attachments': clothing_attachments,
                            'dynamic_mesh': clothing_dyn_mesh
                        })
                        print(f"  CLOTHING: {costume_item} -> occupancy {occupancy_vector}, {len(clothing_attachments)} attachments")
                    else:
                        print(f"      DEBUG: No attachments found in vp_block '{vp_block_name}'")
                else:
                    print(f"      DEBUG: vp_block '{vp_block_name}' not found in descriptor blocks")
                break
    
    # Apply occupancy-based filtering to resolve conflicts
    print(f"OCCUPANCY: Before filtering - {len(skin_attachments_with_occupancy)} skin, {len(clothing_attachments_with_occupancy)} clothing")
    filtered_result = filter_attachments_by_occupancy_with_dynamic(skin_attachments_with_occupancy, clothing_attachments_with_occupancy)
    
    final_attachments = filtered_result['attachments']
    final_dynamic_meshes = filtered_result['dynamic_meshes']
    
    print(f"OCCUPANCY: After filtering - {len(final_attachments)} final attachments, {len(final_dynamic_meshes)} dynamic meshes")
    print("OCCUPANCY: Clothing replacement logic applied successfully!")
    
    return final_attachments, final_dynamic_meshes


def _apply_trimesh_materials(mesh: 'trimesh.Trimesh', materials: List[dict], mesh_info: dict = None) -> 'trimesh.Trimesh':
    """Apply materials to trimesh using the same approach as the original working script."""
    if not materials:
        return mesh
    
    try:
        import trimesh
        from PIL import Image
        import numpy as np
        
        # Find first material with texture (same logic as original)
        material_with_texture = None
        for mat in materials:
            if mat.get('textures'):
                material_with_texture = mat
                break
        
        if not material_with_texture:
            # Color-only material
            if materials:
                mat = materials[0]
                if 'diffuse' in mat:
                    color = list(mat['diffuse'][:4])
                    if len(color) == 3:
                        color.append(1.0)  # Add alpha
                    
                    # Create PBR material for color-only mesh
                    material = trimesh.visual.material.PBRMaterial()
                    material.name = mat.get('name', 'material')
                    material.baseColorFactor = color
                    
                    if color[3] < 1.0:  # If material has transparency
                        material.alphaMode = 'BLEND'
                    
                    # Create TextureVisuals with material
                    mesh.visual = trimesh.visual.TextureVisuals(material=material)
                    print(f"      Applied PBR color material: {color}")
            return mesh
        
        # Material with texture - find texture file
        texture_name = material_with_texture['textures'][0]
        texture_path = None
        
        # Try multiple locations (same as original)
        if mesh_info and 'source_path' in mesh_info:
            base_path = os.path.dirname(mesh_info['source_path'])
            candidates = [
                os.path.join(base_path, texture_name),
                _find_in_data_root(texture_name, mesh_info)
            ]
            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    texture_path = candidate
                    break
        
        if not texture_path or not os.path.exists(texture_path):
            print(f"      Texture not found: {texture_name}")
            return mesh
        
        print(f"      Applying trimesh texture: {texture_path}")
        
        # Create PBR material with texture (same as original)
        material = trimesh.visual.material.PBRMaterial()
        material.name = material_with_texture['name']
        
        # Set base color from diffuse
        if 'diffuse' in material_with_texture and len(material_with_texture['diffuse']) >= 3:
            material.baseColorFactor = material_with_texture['diffuse'][:4]
            if len(material.baseColorFactor) == 3:
                material.baseColorFactor.append(1.0)
        
        # Load texture image with black-as-alpha (same as original)
        img = Image.open(texture_path)
        
        # Handle black-as-alpha transparency
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Create alpha channel based on black pixels
        data = np.array(img)
        # Check for pixels that are very close to black (RGB < 5) - gentler to avoid white sheen
        black_mask = np.all(data[:, :, :3] < 5, axis=2)
        # Set alpha to 0 for black pixels
        data[black_mask, 3] = 0
        
        # Update image with alpha channel (no flip - try original like working script)
        img = Image.fromarray(data, 'RGBA')
        material.baseColorTexture = img  # Direct assignment like original!
        
        # Set material to handle transparency
        material.alphaMode = 'MASK'  # Use alpha masking for sharp edges
        material.alphaCutoff = 0.1   # Pixels with alpha < 0.1 are discarded
        
        # Preserve existing UV coordinates before creating TextureVisuals
        existing_uv = None
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            existing_uv = mesh.visual.uv.copy()
            print(f"      Preserving UV coordinates: {existing_uv.shape}")
        
        # Create texture visuals for the mesh (same as original)
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
        
        # Restore UV coordinates (no flipping - same as original working script)
        if existing_uv is not None:
            mesh.visual.uv = existing_uv
            print(f"      Restored original UV coordinates")
        
        print(f"      Applied trimesh texture material: {texture_name}")
        return mesh
        
    except Exception as e:
        print(f"      Failed to apply trimesh materials: {e}")
        return mesh


def _get_bone_hierarchy_order(bones: Dict) -> List[str]:
    """Get bones in hierarchical order (parents before children)."""
    roots = [name for name, bone in bones.items() if not bone.parent or bone.parent not in bones]
    
    ordered = []
    visited = set()
    
    def visit_bone(bone_name: str):
        if bone_name in visited or bone_name not in bones:
            return
        visited.add(bone_name)
        ordered.append(bone_name)
        
        children = [name for name, bone in bones.items() if bone.parent == bone_name]
        for child in sorted(children):
            visit_bone(child)
    
    for root in sorted(roots):
        visit_bone(root)
    
    return ordered


def run_blender_export_script(script_path: str, descriptor_path: str, output_path: str):
    """Run the Blender export script using Blender's Python interpreter.
    
    Args:
        script_path: Path to this Python script
        descriptor_path: Path to VF3 .TXT descriptor
        output_path: Where to save the .glb file
    """
    
    # Try to find Blender executable
    blender_paths = [
        "/usr/bin/blender",
        "/usr/local/bin/blender", 
        "/opt/blender/blender",
        "C:\\Program Files\\Blender Foundation\\Blender*\\blender.exe",
        "blender"  # Hope it's in PATH
    ]
    
    blender_exe = None
    for path in blender_paths:
        if os.path.exists(path) or path == "blender":
            blender_exe = path
            break
    
    if not blender_exe:
        print("? Could not find Blender executable. Please install Blender or add it to PATH.")
        return False
    
    # Create command to run Blender in background with our script
    cmd = [
        blender_exe,
        "--background",  # No GUI
        "--python", script_path,
        "--", descriptor_path, output_path  # Pass arguments to script
    ]
    
    print(f"? Running Blender export: {' '.join(cmd)}")
    
    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("? Blender export completed successfully")
            return True
        else:
            print(f"? Blender export failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("? Blender export timed out")
        return False
    except Exception as e:
        print(f"? Error running Blender: {e}")
        return False


if __name__ == "__main__":
    # This script can be run directly by Blender
    if len(sys.argv) >= 3:
        descriptor_path = sys.argv[-2]
        output_path = sys.argv[-1]
        
        print(f"? Blender VF3 Export: {descriptor_path} -> {output_path}")
        
        # Import VF3 modules (make sure they're in path)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        
        from vf3_loader import (
            read_descriptor,
            parse_frame_bones,
            build_world_transforms,
            collect_active_attachments,
            find_mesh_file,
        )
        from vf3_mesh_loader import load_mesh_with_full_materials
        
        # Load VF3 data
        desc = read_descriptor(descriptor_path)
        bones = parse_frame_bones(desc)
        
        # Collect active attachments with occupancy filtering (base skin + default costume, expanded across referenced descriptors)
        attachments, _clothing_dynamic_meshes = _collect_attachments_with_occupancy_filtering(desc)
        print(f"? Total attachments collected: {len(attachments)} (after occupancy filtering)")
        
        # For Satsuki, add both head variants to get both stkface.bmp and stkface2.bmp
        if "satsuki" in descriptor_path.lower():
            print("? Adding both head variants for Satsuki (stkface + stkface2)...")
            try:
                from vf3_loader import resolve_identifier_to_attachments
                # Add the alternative head_k variant
                head_k_atts, head_k_dyn = resolve_identifier_to_attachments('satsuki.head_k', desc)
                if head_k_atts:
                    # Rename to avoid conflict with existing head bone
                    for att in head_k_atts:
                        att.attach_bone = att.attach_bone + "_k"  # head -> head_k
                    attachments.extend(head_k_atts)
                    
                    # Add head_k bone to bone hierarchy (same position as head)
                    if 'head' in bones:
                        import copy
                        head_k_bone = copy.deepcopy(bones['head'])
                        bones['head_k'] = head_k_bone
                        print(f"? Added head_k bone to hierarchy")
                    
                    print(f"? Added {len(head_k_atts)} head_k attachments for stkface2 texture")
            except Exception as e:
                print(f"? Failed to add head_k variant: {e}")

        # Build world transforms, including any child frames introduced by attachments
        world_transforms = build_world_transforms(bones, attachments)
        
        # Load mesh data
        mesh_data = {}
        for att in attachments:
            mesh_path = find_mesh_file(att.resource_id)
            if not mesh_path:
                continue
            try:
                mesh_info = load_mesh_with_full_materials(mesh_path)
                if mesh_info['mesh']:
                    mesh_data[att.resource_id] = mesh_info
            except Exception as e:
                print(f"Failed to load {mesh_path}: {e}")
        
        # Create character in Blender
        success = create_vf3_character_in_blender(bones, attachments, world_transforms, mesh_data, _clothing_dynamic_meshes, output_path)
        
        if success:
            print("? VF3 character created successfully in Blender!")
        else:
            print("? Failed to create VF3 character")
    else:
        print("Usage: Run this script with Blender: blender --background --python vf3_blender_exporter.py -- input.TXT output.glb")


