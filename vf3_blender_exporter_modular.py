"""
VF3 Blender Exporter - MODULAR VERSION
Split from the 2300-line vf3_blender_exporter.py while preserving exact working logic.

This maintains the same functionality as the original but in smaller, manageable modules:
- vf3_uv_materials.py - UV mapping and material handling
- vf3_mesh_merging.py - Body part merging logic  
- vf3_dynamic_visual.py - DynamicVisual connector processing
- vf3_trimesh_materials.py - Trimesh material application (extracted below)

Usage: Same as original - run with Blender
blender --background --python vf3_blender_exporter_modular.py -- input.TXT output.glb
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
        print("🚫 Blender Python API not available. Run this script inside Blender or install bpy module.")
        return False
    
    print("🎌 Creating VF3 character in Blender...")
    
    # Step 1: Clear existing scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Step 2: Create armature
    print("🦴 Creating armature...")
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
    print("🔧 Creating and binding meshes...")
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

        # Clean up mesh to reduce z-fighting FIRST
        blender_mesh.validate()  # Fix invalid geometry
        
        # DISABLE vertex deduplication entirely - like working export_ciel_to_gltf.py
        # The working version doesn't do vertex deduplication at all
        print(f"  Preserving exact vertex count for {mesh_name} (no deduplication)")
        
        # Assign UVs with exact preservation like working export_ciel_to_gltf.py
        from vf3_uv_handler import preserve_and_apply_uv_coordinates
        preserve_and_apply_uv_coordinates(blender_mesh, trimesh_mesh, mesh_name, mesh_info)
        
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
            from vf3_uv_materials import _create_blender_materials
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
    
    # Step 6: Create DynamicVisual connectors FIRST (before merging)
    # This allows connectors to inherit materials from individual costume parts
    print("🔧 Creating DynamicVisual connectors (before merging)...")
    
    from vf3_dynamic_visual import _create_dynamic_visual_meshes
    connector_count = _create_dynamic_visual_meshes(
        clothing_dynamic_meshes, world_transforms, created_bones, 
        armature_obj, mesh_objects, mesh_data
    )
    print(f"🔧 Created {connector_count} DynamicVisual connector meshes")
    
    # Filter out any deleted/invalid objects from mesh_objects list after connector creation
    valid_mesh_objects = []
    for mesh_obj in mesh_objects:
        try:
            # Test if object is still valid by accessing its name
            _ = mesh_obj.name
            valid_mesh_objects.append(mesh_obj)
        except (ReferenceError, AttributeError):
            # Object has been deleted during connector merging, skip it
            continue
    mesh_objects = valid_mesh_objects
    print(f"  Filtered mesh objects after connector creation: {len(mesh_objects)} valid objects")
    
    # Step 7: Selective merging for better object hierarchy
    # Only merge connectors and closely related parts, keep major limbs separate
    
    print("🔧 Merging breast meshes with body...")
    from vf3_mesh_merging import _merge_breast_meshes_with_body
    _merge_breast_meshes_with_body(mesh_objects)
    
    # Build leg chains but keep them as separate leg objects (don't merge to body)
    print("🔧 Merging feet with lower legs...")
    from vf3_mesh_merging import _merge_feet_meshes_with_legs
    _merge_feet_meshes_with_legs(mesh_objects)
    
    print("🔧 Merging lower legs with thighs...")
    from vf3_mesh_merging import _merge_lower_legs_meshes_with_thighs
    _merge_lower_legs_meshes_with_thighs(mesh_objects)
    
    # Skip: Don't merge complete legs with body - keep as separate l_leg1/r_leg1 objects
    print("🔧 Keeping leg assemblies separate from body for better hierarchy")
    
    # Build arm chains but keep them as separate arm objects (don't merge to body)  
    print("🔧 Merging forearms with upper arms...")
    from vf3_mesh_merging import _merge_forearms_meshes_with_arms
    _merge_forearms_meshes_with_arms(mesh_objects)
    
    # Skip: Don't merge hands with arms - keep hands separate
    print("🔧 Keeping hands separate from arms for better hierarchy")
    
    # Skip: Don't merge arms with body - keep as separate l_arm1/r_arm1 objects
    print("🔧 Keeping arm assemblies separate from body for better hierarchy")
    
    # Connectors were already created before merging (moved above)
    
    # Step 8: Configure viewport for texture display and select all objects for export
    try:
        # Set viewport shading to Material Preview to show textures
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL_PREVIEW'
                        print("🔧 Set viewport to Material Preview mode for texture display")
                        break
    except:
        print("🔧 Could not set viewport mode (running headless)")
    
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    
    # Select only valid mesh objects that still exist in the scene after merging
    current_mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for mesh_obj in current_mesh_objects:
        try:
            mesh_obj.select_set(True)
        except ReferenceError:
            # Object was deleted during merging, skip it
            continue
    
    print(f"  Selected {len(current_mesh_objects)} mesh objects for export")
    
    bpy.context.view_layer.objects.active = armature_obj
    
    # Step 8.5: Save .blend file for debugging (optional)
    blend_path = output_path.replace('.glb', '_debug.blend')
    try:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print(f"🔧 Saved debug .blend file: {blend_path}")
    except Exception as e:
        print(f"🔧 Could not save .blend file: {e}")
    
    # Step 9: Export to glTF
    print(f"📦 Exporting to {output_path}...")
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            check_existing=False,
            export_format='GLB',
            use_selection=True,
            export_apply=True,
            export_yup=True,
            export_materials='EXPORT',
            export_colors=True,
            export_cameras=False,
            export_extras=False,
            export_lights=False,
            export_skins=True,
            export_def_bones=False,
            export_rest_position_armature=False,
            export_anim_slide_to_zero=False,
            export_animations=False
        )
        print(f"🎉 Export completed successfully: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False


def _apply_trimesh_materials(mesh: 'trimesh.Trimesh', materials: List[dict], mesh_info: dict = None) -> 'trimesh.Trimesh':
    """Apply trimesh materials using the exact logic from the working exporter."""
    import trimesh
    import numpy as np
    from PIL import Image
    
    if not materials:
        return mesh
    
    print(f"      Applying trimesh materials: {len(materials)} materials")
    
    # Find material with texture first (same as original)
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
    material.name = material_with_texture.get('name', 'textured_material')
    
    # Set base color from material
    if 'diffuse' in material_with_texture:
        color = list(material_with_texture['diffuse'][:4])
        if len(color) == 3:
            color.append(1.0)  # Add alpha
        material.baseColorFactor = color
    
    # Load and process texture
    try:
        img = Image.open(texture_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Black-as-alpha processing (same as original)
        data = np.array(img)
        black_mask = np.all(data[:, :, :3] < 10, axis=2)
        data[black_mask, 3] = 0
        
        img = Image.fromarray(data, 'RGBA')
        material.baseColorTexture = img
        material.alphaMode = 'MASK'
        material.alphaCutoff = 0.1
        
        # Preserve existing UV coordinates (CRITICAL!)
        existing_uv = None
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            existing_uv = mesh.visual.uv.copy()
            print(f"        Preserving existing UV coordinates from .X file ({existing_uv.shape})")
        
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
        
        if existing_uv is not None:
            mesh.visual.uv = existing_uv
            print("        Restored UV coordinates from .X file")
        
        print(f"      ✅ Applied trimesh texture material: {texture_name}")
        
    except Exception as e:
        print(f"      ❌ Failed to process texture {texture_name}: {e}")
    
    return mesh


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


def _collect_attachments_with_occupancy_filtering(desc, include_skin=True, include_items=True):
    """
    Collect attachments with proper occupancy-based filtering to prevent clothing/body conflicts.
    
    Args:
        desc: Descriptor object
        include_skin: Include base skin/female body parts (default True)
        include_items: Include costume items from defaultcos (default True)
    
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
    
    print(f"OCCUPANCY: Collecting attachments with include_skin={include_skin}, include_items={include_items}")
    
    # Parse skin attachments with occupancy vectors
    skin_attachments_with_occupancy = []
    skin_dynamic_meshes = []
    
    if include_skin:
        print("👤 SKIN MODE: Loading base female body parts")
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
    else:
        print("👤 SKIN MODE: Skipping base female body parts")
    
    # Parse costume attachments with occupancy vectors
    costume_attachments_with_occupancy = []
    
    if include_items:
        print("👘 COSTUME MODE: Loading costume items")
        for costume_resource in parse_defaultcos(desc):
            if '.' not in costume_resource:
                continue
            
            prefix, item = costume_resource.split('.', 1)
            item_block = desc.blocks.get(item)
            if not item_block:
                continue
                
            # Find vp target on the first mapping line in the item block
            for raw in item_block:
                s = raw.strip()
                if not s or ':' not in s or s.startswith('class:'):
                    continue
                parts = s.split(':', 1)
                if len(parts) != 2:
                    continue
                    
                occ_str, vp_ident = parts
                occupancy_vector = parse_occupancy_vector(occ_str)
                vp_ident = vp_ident.strip()
                
                # vp_ident like 'ciel.blazer_vp' 
                if '.' in vp_ident:
                    _, vp_name = vp_ident.split('.', 1)
                else:
                    vp_name = vp_ident
                    
                vp_block = desc.blocks.get(vp_name)
                if vp_block:
                    vp_attachments = parse_attachment_block_lines(vp_block)
                    costume_dyn_mesh = parse_dynamic_visual_mesh(vp_block)
                    
                    if vp_attachments:
                        costume_attachments_with_occupancy.append({
                            'occupancy': occupancy_vector,
                            'source': f'costume:{costume_resource}:{vp_name}',
                            'attachments': vp_attachments,
                            'dynamic_mesh': costume_dyn_mesh
                        })
                        print(f"  COSTUME: {costume_resource} -> {vp_name}, occupancy {occupancy_vector}, {len(vp_attachments)} attachments")
                break
    else:
        print("👘 COSTUME MODE: Skipping costume items")
    
    # Apply occupancy filtering using existing logic
    filter_result = filter_attachments_by_occupancy_with_dynamic(
        skin_attachments_with_occupancy + costume_attachments_with_occupancy,
        []  # Dynamic meshes are already included in the attachment data
    )
    
    # Extract results from dict
    filtered_attachments = filter_result.get('attachments', [])
    filtered_dynamic_meshes = filter_result.get('dynamic_meshes', [])
    
    print(f"OCCUPANCY: Filtered to {len(filtered_attachments)} attachments ({len(filtered_dynamic_meshes)} dynamic meshes)")
    
    return filtered_attachments, filtered_dynamic_meshes


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


if __name__ == "__main__":
    # This script can be run directly by Blender
    if len(sys.argv) >= 3:
        # Parse command line arguments, excluding flags
        args = [arg for arg in sys.argv if not arg.startswith('--')]
        descriptor_path = args[-2] if len(args) >= 2 else None
        output_path = args[-1] if len(args) >= 1 else None
        
        if not descriptor_path or not output_path:
            print("❌ Invalid arguments. Usage: blender --background --python vf3_blender_exporter_modular.py -- input.TXT output.glb [--naked]")
            sys.exit(1)
        
        print(f"🎌 Blender VF3 Export: {descriptor_path} -> {output_path}")
        
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
        # Check for --naked flag in command line arguments
        include_skin = True
        include_items = True
        for arg in sys.argv:
            if arg == '--naked':
                include_skin, include_items = True, False
                print("🔧 NAKED MODE: Loading only base female body parts (no costume items)")
                break
        
        attachments, _clothing_dynamic_meshes = _collect_attachments_with_occupancy_filtering(desc, include_skin, include_items)
        print(f"🎌 Total attachments collected: {len(attachments)} (after occupancy filtering)")
        
        # DISABLED: Don't add both head variants - this was causing UV confusion and Z-fighting
        # The main head should handle both textures properly
        if False and "satsuki" in descriptor_path.lower():
            print("🎌 Adding both head variants for Satsuki (stkface + stkface2)...")
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
                        print(f"🎌 Added head_k bone to hierarchy")
                    
                    print(f"🎌 Added {len(head_k_atts)} head_k attachments for stkface2 texture")
            except Exception as e:
                print(f"🚫 Failed to add head_k variant: {e}")

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
            print("🎉 VF3 character created successfully in Blender!")
        else:
            print("❌ Failed to create VF3 character")
    else:
        print("Usage: Run this script with Blender: blender --background --python vf3_blender_exporter_modular.py -- input.TXT output.glb")