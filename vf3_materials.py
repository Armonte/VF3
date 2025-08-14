"""
VF3 Material System
Handles PBR materials, gamma correction, texture loading, and material assignment.
"""

import os
import numpy as np
import trimesh
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image


def gamma_correct_color(color: Tuple[float, float, float, float]) -> List[float]:
    """Apply gamma correction to convert from sRGB to linear color space."""
    gamma = 2.2
    corrected = []
    for i, component in enumerate(color):
        if i < 3:  # RGB components
            corrected.append(pow(component, gamma))
        else:  # Alpha component
            corrected.append(component)
    return corrected


def load_texture_with_fallback(texture_path: str) -> Optional[Image.Image]:
    """Load texture with fallback to different formats."""
    if not os.path.exists(texture_path):
        # Try different extensions
        base_path = os.path.splitext(texture_path)[0]
        for ext in ['.png', '.jpg', '.jpeg', '.tga']:
            alt_path = base_path + ext
            if os.path.exists(alt_path):
                texture_path = alt_path
                break
        else:
            return None
    
    try:
        return Image.open(texture_path)
    except Exception:
        return None


def create_pbr_material(name: str, diffuse_color: List[float], texture_path: Optional[str] = None) -> trimesh.visual.material.PBRMaterial:
    """Create a PBR material with proper color and optional texture."""
    material = trimesh.visual.material.PBRMaterial()
    material.name = name
    material.baseColorFactor = diffuse_color
    
    if texture_path and os.path.exists(texture_path):
        try:
            texture_image = load_texture_with_fallback(texture_path)
            if texture_image:
                material.baseColorTexture = texture_image
        except Exception as e:
            print(f"Warning: Failed to load texture {texture_path}: {e}")
    
    return material


def apply_materials_to_mesh(mesh: trimesh.Trimesh, materials: List[Dict], textures: List[str], base_path: str) -> trimesh.Trimesh:
    """Apply materials to a mesh, handling both textured and colored materials."""
    if not materials:
        return mesh
    
    # Create PBR materials for each material
    pbr_materials = []
    for i, mat in enumerate(materials):
        diffuse = mat.get('diffuse', [1.0, 1.0, 1.0, 1.0])
        
        # Apply gamma correction
        corrected_diffuse = gamma_correct_color(diffuse)
        print(f"  DEBUG: Raw diffuse from .X file: {diffuse} (type: {type(diffuse)})")
        print(f"  DEBUG: Gamma-corrected diffuse: {corrected_diffuse}")
        
        # Create PBR material
        material_name = f"material{i}"
        texture_path = None
        
        if i < len(textures) and textures[i]:
            texture_path = os.path.join(base_path, textures[i])
        
        pbr_material = create_pbr_material(material_name, corrected_diffuse, texture_path)
        pbr_materials.append(pbr_material)
    
    # Apply materials to mesh
    if len(pbr_materials) == 1:
        # Single material
        mesh.visual.material = pbr_materials[0]
    else:
        # Multiple materials - use face materials
        mesh.visual.material = pbr_materials
    
    return mesh


def determine_material_type_from_bones(bone_names: List[str]) -> str:
    """Determine if bones represent skin or clothing based on bone names."""
    clothing_bones = {'body', 'waist', 'l_breast', 'r_breast'}  # Core torso bones often have clothing
    skin_bones = {'head', 'l_hand', 'r_hand', 'l_foot', 'r_foot'}  # Extremities are usually skin
    
    clothing_count = sum(1 for bone in bone_names if any(cb in bone for cb in clothing_bones))
    skin_count = sum(1 for bone in bone_names if any(sb in bone for sb in skin_bones))
    
    return 'clothing' if clothing_count > skin_count else 'skin'


def get_skin_material_data(all_materials: Dict[str, Any]) -> Dict[str, Any]:
    """Get skin tone material data from available materials."""
    # Look for skin-toned materials (beige/peach colors)
    for mesh_name, mesh_materials in all_materials.items():
        if 'female' in mesh_name.lower() or 'skin' in mesh_name.lower():
            for material in mesh_materials:
                if 'diffuse' in material:
                    color = material['diffuse']
                    # Check if it's skin-toned (warm, peachy colors)
                    if (isinstance(color, (list, tuple)) and len(color) >= 3 and
                        0.7 <= color[0] <= 1.0 and  # Red component
                        0.5 <= color[1] <= 0.9 and  # Green component  
                        0.4 <= color[2] <= 0.8):    # Blue component
                        return {
                            'type': 'skin tone',
                            'color': gamma_correct_color(color)
                        }
    
    # Fallback to default skin tone
    return {
        'type': 'default skin tone',
        'color': [0.95, 0.76, 0.65, 1.0]  # Peachy skin tone
    }


def get_clothing_material_data(all_materials: Dict[str, Any], source_info: Optional[Dict] = None) -> Dict[str, Any]:
    """Get clothing fabric material data, prioritizing the specific source if provided."""
    target_sources = []
    
    # If we have source info, prioritize materials from that source
    if source_info and 'source' in source_info:
        source = source_info['source']
        if '.' in source:
            prefix = source.split('.')[0]  # e.g., 'satsuki' from 'satsuki.blazer'
            target_sources.append(prefix)
    
    # Look for clothing materials, prioritizing target sources
    for mesh_name, mesh_materials in all_materials.items():
        # Check if this mesh matches our target source
        is_target_source = any(ts in mesh_name.lower() for ts in target_sources)
        
        # Skip skin/body materials
        if any(skip in mesh_name.lower() for skip in ['female.body', 'female.arms', 'female.legs', 'female.waist']):
            continue
            
        for material in mesh_materials:
            if 'diffuse' in material:
                color = material['diffuse']
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    # Prioritize materials from target source
                    if is_target_source:
                        return {
                            'type': f'clothing fabric from {target_sources[0]}',
                            'color': gamma_correct_color(color)
                        }
                    # Otherwise, use any non-skin material
                    elif not (0.7 <= color[0] <= 1.0 and 0.5 <= color[1] <= 0.9 and 0.4 <= color[2] <= 0.8):
                        return {
                            'type': 'clothing fabric material',
                            'color': gamma_correct_color(color)
                        }
    
    # Fallback to default fabric color
    return {
        'type': 'default fabric',
        'color': [0.8, 0.8, 0.8, 1.0]  # Light gray fabric
    }


def determine_dynamic_visual_material(dyn_data: Dict, geometry_to_mesh_map: Dict, all_materials: Dict, connector_idx: int) -> Dict[str, Any]:
    """Determine appropriate material for a DynamicVisual connector based on source and bones."""
    # Check if we have source information
    source_info = dyn_data.get('source_info')
    
    if source_info and 'source' in source_info:
        source = source_info['source']
        print(f"  DEBUG: DynamicVisual connector {connector_idx} source: {source}")
        
        # Determine material type based on source
        if any(clothing in source.lower() for clothing in ['blazer', 'skirt', 'shoes', 'clothes']):
            material_data = get_clothing_material_data(all_materials, source_info)
            print(f"  Applied {material_data['type']} to DynamicVisual connector {connector_idx}")
            return material_data
        else:
            material_data = get_skin_material_data(all_materials)
            print(f"  Applied {material_data['type']} to DynamicVisual connector {connector_idx}")
            return material_data
    
    # Fallback: analyze bones if no source info
    vertex_bones = dyn_data.get('vertex_bones', [])
    material_type = determine_material_type_from_bones(vertex_bones)
    
    if material_type == 'clothing':
        material_data = get_clothing_material_data(all_materials)
    else:
        material_data = get_skin_material_data(all_materials)
    
    print(f"  Applied {material_data['type']} to DynamicVisual connector {connector_idx} (from bone analysis)")
    return material_data
