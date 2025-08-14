"""
VF3 Materials System
Complete PBR material handling, texture loading, and gamma correction.
Extracted from export_ciel_to_gltf.py lines 954-1159
"""

import os
import numpy as np
import trimesh
from typing import Dict, List, Any, Optional
from PIL import Image


def split_mesh_by_materials(mesh_data: dict) -> List[dict]:
    """Split a mesh into separate meshes by material for proper GLTF multi-material support"""
    mesh = mesh_data['mesh']
    materials = mesh_data['materials']
    face_materials = mesh_data.get('face_materials', [])
    uv_coords = mesh_data.get('uv_coords', [])
    
    if not face_materials or len(face_materials) != len(mesh.faces):
        print("No face materials or mismatch, returning single mesh")
        return [mesh_data]
    
    # Group faces by material
    material_faces = {}
    for face_idx, mat_idx in enumerate(face_materials):
        if mat_idx not in material_faces:
            material_faces[mat_idx] = []
        material_faces[mat_idx].append(face_idx)
    
    print(f"Splitting mesh into {len(material_faces)} material groups")
    
    # Create separate meshes for each material
    split_meshes = []
    for mat_idx, face_indices in material_faces.items():
        if mat_idx >= len(materials):
            print(f"Warning: Material index {mat_idx} out of range, skipping")
            continue
            
        # Extract faces for this material
        faces_subset = mesh.faces[face_indices]
        
        # Find unique vertices used by these faces
        unique_vertices = np.unique(faces_subset.flatten())
        vertex_map = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_vertices)}
        
        # Extract vertices and remap faces
        new_vertices = mesh.vertices[unique_vertices]
        new_faces = np.array([[vertex_map[v] for v in face] for face in faces_subset])
        
        # Create new mesh
        new_mesh = trimesh.Trimesh(vertices=new_vertices, faces=new_faces, process=False)
        
        # Copy UV coordinates if available
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            new_mesh.visual.uv = mesh.visual.uv[unique_vertices]
            print(f"Copied UV coordinates for material {mat_idx} ({len(unique_vertices)} vertices)")
        
        # Create mesh data with single material
        split_mesh_data = {
            'mesh': new_mesh,
            'materials': [materials[mat_idx]],
            'textures': materials[mat_idx]['textures'],
            'material_index': mat_idx
        }
        
        split_meshes.append(split_mesh_data)
        print(f"Created mesh for material {mat_idx}: {len(new_vertices)} vertices, {len(new_faces)} faces, textures: {materials[mat_idx]['textures']}")
    
    return split_meshes


def apply_materials_to_mesh(mesh: trimesh.Trimesh, materials: List[dict], textures: List[str], base_path: str) -> trimesh.Trimesh:
    """Apply materials and textures to a mesh"""
    if not materials:
        return mesh
    
    try:
        # For now, use the first material that has a texture
        material_with_texture = None
        for mat in materials:
            if mat['textures']:
                material_with_texture = mat
                break
        
        if not material_with_texture:
            # Use first material for color - create proper PBR material
            if materials:
                mat = materials[0]
                # Apply diffuse color as PBR material
                if 'diffuse' in mat and len(mat['diffuse']) >= 3:
                    color = mat['diffuse'][:4]  # RGBA
                    if len(color) == 3:
                        color.append(1.0)  # Add alpha
                    
                    # Create PBR material for color-only mesh
                    material = trimesh.visual.material.PBRMaterial()
                    material.name = mat.get('name', 'material')
                    material.baseColorFactor = color
                    
                    # Handle transparency for black pixels (alpha masking)
                    if color[3] < 1.0:  # If material has transparency
                        material.alphaMode = 'BLEND'
                    
                    # Create material visuals for color-only mesh (similar to texture approach)
                    try:
                        # Try to create TextureVisuals with material but no texture
                        mesh.visual = trimesh.visual.TextureVisuals(material=material)
                        print(f"Applied PBR material with diffuse color {color} to mesh")
                    except Exception as e:
                        # Fallback to face colors if TextureVisuals fails
                        mesh.visual.face_colors = color
                        print(f"Applied diffuse color {color} to mesh (fallback)")
            return mesh
        
        # Try to load texture
        texture_name = material_with_texture['textures'][0]
        # Try multiple possible locations for texture files
        texture_paths = [
            os.path.join(base_path, texture_name),  # Same directory as mesh
            os.path.join(os.path.dirname(base_path), texture_name),  # Parent directory (data/)
            os.path.join('data', texture_name)  # Relative to project root
        ]
        
        texture_path = None
        for path in texture_paths:
            if os.path.exists(path):
                texture_path = path
                break
        
        if texture_path and os.path.exists(texture_path):
            print(f"Loading texture: {texture_path}")
            
            # Create PBR material with texture
            material = trimesh.visual.material.PBRMaterial()
            material.name = material_with_texture['name']
            
            # Set base color from diffuse
            if 'diffuse' in material_with_texture and len(material_with_texture['diffuse']) >= 3:
                material.baseColorFactor = material_with_texture['diffuse'][:4]
                if len(material.baseColorFactor) == 3:
                    material.baseColorFactor.append(1.0)
            
            # Load texture image
            try:
                img = Image.open(texture_path)
                
                # Handle black-as-alpha transparency
                # Convert black pixels to transparent
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Create alpha channel based on black pixels
                data = np.array(img)
                # Check for pixels that are very close to black (RGB < 10)
                black_mask = np.all(data[:, :, :3] < 10, axis=2)
                # Set alpha to 0 for black pixels
                data[black_mask, 3] = 0
                
                # Update image with alpha channel
                img = Image.fromarray(data, 'RGBA')
                material.baseColorTexture = img
                
                # Set material to handle transparency
                material.alphaMode = 'MASK'  # Use alpha masking for sharp edges
                material.alphaCutoff = 0.1   # Pixels with alpha < 0.1 are discarded
                
                print(f"Successfully loaded texture {texture_name} with black-as-alpha transparency")
                
                # Preserve existing UV coordinates before creating TextureVisuals
                existing_uv = None
                if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                    existing_uv = mesh.visual.uv.copy()
                    print(f"Preserving existing UV coordinates from .X file ({existing_uv.shape})")
                
                # Create texture visuals for the mesh
                mesh.visual = trimesh.visual.TextureVisuals(material=material)
                
                # Restore or generate UV coordinates
                if existing_uv is not None:
                    mesh.visual.uv = existing_uv
                    print("Restored UV coordinates from .X file")
                else:
                    print("Generating UV coordinates for mesh (no UV data from .X file)")
                    # Simple planar UV mapping as fallback
                    vertices = mesh.vertices
                    bounds = mesh.bounds
                    width = bounds[1][0] - bounds[0][0]
                    height = bounds[1][1] - bounds[0][1]
                    
                    uv = np.zeros((len(vertices), 2))
                    uv[:, 0] = (vertices[:, 0] - bounds[0][0]) / width if width > 0 else 0
                    uv[:, 1] = (vertices[:, 1] - bounds[0][1]) / height if height > 0 else 0
                    
                    mesh.visual.uv = uv
                
            except ImportError:
                print("PIL not available, cannot load texture images")
                # Fall back to color
                if 'diffuse' in material_with_texture:
                    mesh.visual.face_colors = material_with_texture['diffuse'][:4]
            except Exception as e:
                print(f"Failed to load texture {texture_path}: {e}")
                # Fall back to color
                if 'diffuse' in material_with_texture:
                    mesh.visual.face_colors = material_with_texture['diffuse'][:4]
        else:
            print(f"Texture not found: {texture_name}")
            # Apply color only
            if 'diffuse' in material_with_texture:
                mesh.visual.face_colors = material_with_texture['diffuse'][:4]
                
    except Exception as e:
        print(f"Error applying materials to mesh: {e}")
    
    return mesh


def get_skin_material_data() -> dict:
    """Get skin material data with gamma correction"""
    raw_skin_color = [1.0, 0.8823530077934265, 0.7843137979507446, 1.0]
    skin_color = raw_skin_color.copy()
    # Apply gamma correction to match the corrected colors from .X files
    for color_i in range(3):  # Only RGB, not alpha
        skin_color[color_i] = pow(skin_color[color_i], 2.2)
    
    return {
        'color': skin_color,
        'type': 'skin tone'
    }


def get_clothing_material_data(all_materials: list, bone_counts: dict) -> dict:
    """Get clothing material data based on connected meshes"""
    # Try to find a suitable clothing color from the materials
    # Look for non-skin colors (avoid flesh tones)
    
    clothing_colors = []
    for material in all_materials:
        if 'diffuse' in material:
            color = material['diffuse']
            # Skip skin-like colors (high red, moderate green, low blue)
            if len(color) >= 3:
                r, g, b = color[0], color[1], color[2]
                # Avoid skin tones: high red (>0.7), moderate green (0.4-0.9), low blue (<0.7)
                if not (r > 0.7 and 0.4 < g < 0.9 and b < 0.7):
                    clothing_colors.append(color)
    
    if clothing_colors:
        # Use the first non-skin color found
        chosen_color = clothing_colors[0]
        print(f"    DEBUG: Using clothing color: {chosen_color}")
        return {
            'color': chosen_color,
            'type': 'clothing fabric'
        }
    else:
        # Fallback to a generic clothing color (dark blue/gray)
        clothing_color = [0.2, 0.2, 0.4, 1.0]  # Dark blue-gray
        print(f"    DEBUG: Using fallback clothing color: {clothing_color}")
        return {
            'color': clothing_color,
            'type': 'clothing fabric (fallback)'
        }


def determine_material_from_bones(bone_counts: dict, all_materials: list, connector_index: int) -> dict:
    """Fallback material determination based on bone names"""
    clothing_indicators = ['skirt', 'blazer', 'shoe', 'sock', 'shirt', 'dress', 'jacket']
    skin_indicators = ['body', 'breast', 'arm', 'hand', 'leg', 'foot', 'head', 'waist']
    
    clothing_score = 0
    skin_score = 0
    
    for bone_name in bone_counts.keys():
        bone_lower = bone_name.lower()
        
        # Check for clothing indicators in bone names
        for indicator in clothing_indicators:
            if indicator in bone_lower:
                clothing_score += bone_counts[bone_name]
                print(f"    DEBUG: Bone '{bone_name}' indicates clothing (+{bone_counts[bone_name]})")
        
        # Check for skin indicators in bone names  
        for indicator in skin_indicators:
            if indicator in bone_lower:
                skin_score += bone_counts[bone_name]
                print(f"    DEBUG: Bone '{bone_name}' indicates skin (+{bone_counts[bone_name]})")
    
    print(f"    DEBUG: Connector {connector_index} scores - clothing: {clothing_score}, skin: {skin_score}")
    
    if clothing_score > skin_score:
        print(f"    DEBUG: Connector {connector_index} determined to be CLOTHING connector (bone-based)")
        return get_clothing_material_data(all_materials, bone_counts)
    else:
        print(f"    DEBUG: Connector {connector_index} determined to be SKIN connector (bone-based)")
        return get_skin_material_data()


def determine_dynamic_visual_material(dyn_data: dict, geometry_to_mesh_map: dict, all_materials: list, connector_index: int) -> dict:
    """
    Determine the appropriate material for a DynamicVisual connector based on its source.
    
    Logic:
    - Check the source of the DynamicVisual (from occupancy filtering)
    - If from clothing source (satsuki.blazer, etc.): use clothing color
    - If from skin source (female.*): use skin color
    """
    if not dyn_data or 'vertex_bones' not in dyn_data:
        # Fallback to skin color
        return get_skin_material_data()
    
    # Check if we have source information in the dyn_data
    source_info = dyn_data.get('source_info', {})
    source_name = source_info.get('source', '')
    
    print(f"    DEBUG: Connector {connector_index} source: '{source_name}'")
    
    # Analyze which bones this connector uses
    bone_counts = {}
    for bone_name in dyn_data['vertex_bones']:
        bone_counts[bone_name] = bone_counts.get(bone_name, 0) + 1
    
    print(f"    DEBUG: Connector {connector_index} bone usage: {bone_counts}")
    
    # Determine material based on SOURCE rather than bone names
    clothing_sources = ['blazer', 'skirt', 'shoe', 'sock', 'shirt', 'dress', 'jacket', 'coat', 'pants', 'top']
    skin_sources = ['female.', 'body', 'arms', 'legs', 'hands', 'foots', 'waist']
    
    source_lower = source_name.lower()
    is_clothing_source = any(indicator in source_lower for indicator in clothing_sources)
    is_skin_source = any(indicator in source_lower for indicator in skin_sources)
    
    print(f"    DEBUG: Source analysis - clothing: {is_clothing_source}, skin: {is_skin_source}")
    
    # Determine material type based on source
    if is_clothing_source:
        print(f"    DEBUG: Connector {connector_index} determined to be CLOTHING connector (source-based)")
        return get_clothing_material_data(all_materials, bone_counts)
    elif is_skin_source:
        print(f"    DEBUG: Connector {connector_index} determined to be SKIN connector (source-based)")
        return get_skin_material_data()
    else:
        # Fallback to bone name analysis if source is unclear
        print(f"    DEBUG: Connector {connector_index} using fallback bone analysis")
        return determine_material_from_bones(bone_counts, all_materials, connector_index)


def merge_body_meshes(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Merge multiple body part meshes into a single unified mesh.
    This helps fill gaps between modular body parts.
    """
    if not meshes:
        return trimesh.Trimesh()
    
    if len(meshes) == 1:
        return meshes[0]
    
    # Combine all meshes
    combined = trimesh.util.concatenate(meshes)
    
    # Try to merge duplicate vertices to create a more unified mesh
    combined.merge_vertices()
    
    # Remove duplicate faces
    combined.remove_duplicate_faces()
    
    # Fill small holes if possible (this is experimental)
    try:
        combined.fill_holes()
    except:
        pass  # Fill holes might fail on complex geometry
    
    return combined