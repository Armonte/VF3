#!/usr/bin/env python3
"""Debug materials in the exported GLB file."""

import json
import os

def debug_materials():
    """Debug what materials were actually exported."""
    glb_file = "satsuki_blender_test.glb"
    
    if not os.path.exists(glb_file):
        print(f"File not found: {glb_file}")
        return
    
    with open(glb_file, 'rb') as f:
        # Skip GLB header
        f.seek(12)
        
        # Read JSON chunk
        json_chunk_header = f.read(8)
        json_chunk_length = int.from_bytes(json_chunk_header[:4], 'little')
        json_data = f.read(json_chunk_length)
        gltf_json = json.loads(json_data.decode('utf-8'))
        
        print("🎨 MATERIAL DEBUG:")
        
        # Check materials
        materials = gltf_json.get('materials', [])
        print(f"\nFound {len(materials)} materials:")
        
        for i, material in enumerate(materials[:10]):  # Show first 10
            name = material.get('name', f'Material_{i}')
            print(f"  {i}: {name}")
            
            # Check PBR settings
            pbr = material.get('pbrMetallicRoughness', {})
            base_color = pbr.get('baseColorFactor', [1,1,1,1])
            print(f"     Base Color: {base_color}")
            
            # Check for texture
            if 'baseColorTexture' in pbr:
                texture_index = pbr['baseColorTexture']['index']
                print(f"     Texture Index: {texture_index}")
            else:
                print(f"     No texture (color-only material)")
            
            # Check alpha mode
            alpha_mode = material.get('alphaMode', 'OPAQUE')
            if alpha_mode != 'OPAQUE':
                print(f"     Alpha Mode: {alpha_mode}")
        
        if len(materials) > 10:
            print(f"  ... and {len(materials) - 10} more materials")
        
        # Check textures
        textures = gltf_json.get('textures', [])
        print(f"\nFound {len(textures)} textures:")
        for i, texture in enumerate(textures):
            source_idx = texture.get('source', 'N/A')
            print(f"  {i}: Image index {source_idx}")
        
        # Check images  
        images = gltf_json.get('images', [])
        print(f"\nFound {len(images)} images:")
        for i, image in enumerate(images):
            name = image.get('name', f'Image_{i}')
            mime_type = image.get('mimeType', 'unknown')
            if 'bufferView' in image:
                print(f"  {i}: {name} ({mime_type}) - embedded")
            elif 'uri' in image:
                print(f"  {i}: {name} ({mime_type}) - external: {image['uri']}")
            else:
                print(f"  {i}: {name} ({mime_type}) - unknown source")
        
        # Check if meshes have material assignments
        meshes = gltf_json.get('meshes', [])
        print(f"\nMaterial assignments in {len(meshes)} meshes:")
        materials_used = set()
        for i, mesh in enumerate(meshes[:5]):  # Check first 5 meshes
            primitives = mesh.get('primitives', [])
            print(f"  Mesh {i}: {len(primitives)} primitives")
            for j, primitive in enumerate(primitives):
                mat_idx = primitive.get('material')
                if mat_idx is not None:
                    materials_used.add(mat_idx)
                    mat_name = materials[mat_idx].get('name', f'Mat_{mat_idx}') if mat_idx < len(materials) else 'Invalid'
                    print(f"    Primitive {j}: Material {mat_idx} ({mat_name})")
                else:
                    print(f"    Primitive {j}: No material assigned")
        
        print(f"\nUnique materials used: {len(materials_used)} out of {len(materials)} total")
        
        # Summary
        textured_count = sum(1 for mat in materials if 'pbrMetallicRoughness' in mat and 'baseColorTexture' in mat['pbrMetallicRoughness'])
        print(f"\n📊 SUMMARY:")
        print(f"  Total materials: {len(materials)}")
        print(f"  Textured materials: {textured_count}")
        print(f"  Color-only materials: {len(materials) - textured_count}")
        print(f"  Total textures: {len(textures)}")
        print(f"  Total images: {len(images)}")
        print(f"  Materials actually used: {len(materials_used)}")

if __name__ == "__main__":
    debug_materials()