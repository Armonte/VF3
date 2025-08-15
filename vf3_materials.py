#!/usr/bin/env python3

import os
import numpy as np
import trimesh
from PIL import Image

def apply_simple_materials_to_mesh(mesh: trimesh.Trimesh, materials: list, textures: list, base_path: str) -> trimesh.Trimesh:
    """Apply materials using the WORKING approach from export_ciel_to_gltf.py"""
    
    if not materials:
        return mesh
    
    # Find material with texture
    material_with_texture = None
    for mat in materials:
        if mat.get('textures'):
            material_with_texture = mat
            break
    
    if not material_with_texture:
        return apply_color_only_material(mesh, materials)
    
    return apply_texture_material(mesh, material_with_texture, base_path)


def apply_color_only_material(mesh: trimesh.Trimesh, materials: list) -> trimesh.Trimesh:
    """Apply color-only material"""
    
    mat = materials[0]
    color = mat.get('diffuse', [0.7, 0.7, 0.7, 1.0])[:4]
    if len(color) == 3:
        color.append(1.0)
    
    material = trimesh.visual.material.PBRMaterial()
    material.name = mat.get('name', 'material')
    material.baseColorFactor = color
    
    try:
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
    except:
        mesh.visual.face_colors = color
    
    return mesh


def apply_texture_material(mesh: trimesh.Trimesh, material_with_texture: dict, base_path: str) -> trimesh.Trimesh:
    """Apply texture material with UV preservation"""
    
    texture_name = material_with_texture['textures'][0]
    
    # Find texture file
    texture_paths = [
        os.path.join(base_path, texture_name),
        os.path.join(os.path.dirname(base_path), texture_name),
        os.path.join('data', texture_name)
    ]
    
    texture_path = None
    for path in texture_paths:
        if os.path.exists(path):
            texture_path = path
            break
    
    if not texture_path:
        return apply_color_only_material(mesh, [material_with_texture])
    
    # Create PBR material
    material = trimesh.visual.material.PBRMaterial()
    material.name = material_with_texture.get('name', 'textured_material')
    
    # Set base color
    if 'diffuse' in material_with_texture:
        material.baseColorFactor = material_with_texture['diffuse'][:4]
        if len(material.baseColorFactor) == 3:
            material.baseColorFactor.append(1.0)
    
    # Load texture with black-as-alpha
    try:
        img = Image.open(texture_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Black-as-alpha processing
        data = np.array(img)
        black_mask = np.all(data[:, :, :3] < 10, axis=2)
        data[black_mask, 3] = 0
        
        img = Image.fromarray(data, 'RGBA')
        material.baseColorTexture = img
        material.alphaMode = 'MASK'
        material.alphaCutoff = 0.1
        
        # CRITICAL: Preserve UV coordinates
        existing_uv = None
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            existing_uv = mesh.visual.uv.copy()
        
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
        
        # Restore UV coordinates
        if existing_uv is not None:
            mesh.visual.uv = existing_uv
            
    except Exception as e:
        print(f"Texture loading failed: {e}")
        return apply_color_only_material(mesh, [material_with_texture])
    
    return mesh