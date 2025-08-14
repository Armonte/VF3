# VF3 Blender Texture Debug Instructions

## Current Issue
- Blender VF3 export creates GLB with embedded textures (file size 657KB vs 1KB before)
- Colors work correctly on meshes
- Textures are processed with PIL and packed into Blender images
- BUT: Textures are not appearing on materials in the final GLB (showing "BASE COLOR" instead of texture)

## Key Files
- `vf3_blender_exporter.py` - Main Blender export script
- `test_satsuki_blender.py` - Test script for Satsuki character
- `export_ciel_to_gltf.py` - Original 2000-line script with working BMP+alpha support

## What Works (Original Script)
In `export_ciel_to_gltf.py` lines 1087-1110:
```python
from PIL import Image
img = Image.open(texture_path)
# Handle black-as-alpha transparency
if img.mode != 'RGBA':
    img = img.convert('RGBA')
# Create alpha channel based on black pixels
data = np.array(img)
black_mask = np.all(data[:, :, :3] < 10, axis=2)
data[black_mask, 3] = 0
img = Image.fromarray(data, 'RGBA')
material.baseColorTexture = img  # Direct assignment to trimesh material
```

## Current Blender Approach
In `vf3_blender_exporter.py` lines 484-555:
- Uses PIL to load BMP and process black-as-alpha (? Working)
- Converts PIL image to Blender pixel format with `np.flipud(pixels).flatten()` 
- Creates `bpy.data.images.new()` and assigns `blender_img.pixels[:]`
- Calls `blender_img.update()` and `blender_img.pack()`
- Creates texture node with `tex_image.image = blender_img`
- Links to BSDF: `links.new(tex_image.outputs['Color'], bsdf.inputs['Base Color'])`

## Debug Commands Needed

### 1. Check if textures are being processed
```bash
cd /mnt/c/dev/loot/VF3
python3 -u test_satsuki_blender.py 2>&1 | grep -E "head_satsuki|Creating materials.*head|Processed texture.*PIL"
```

### 2. Check for texture loading errors
```bash
python3 -u test_satsuki_blender.py 2>&1 | grep -E "Failed to load texture|Texture file not found|PIL not available"
```

### 3. Check Blender export warnings
```bash
python3 -u test_satsuki_blender.py 2>&1 | grep -E "WARNING.*shader node tex image|More than one shader"
```

### 4. Check if UV coordinates are assigned
```bash
python3 -u test_satsuki_blender.py 2>&1 | grep -E "UV coordinates|uv_layer|UVMap"
```

## Expected Behavior
- Should see: "? Processed texture with PIL: stkface.bmp (RGBA)"
- Should see: "? Processed texture with PIL: stkhair_t.bmp (RGBA)" 
- Head mesh should have face texture (stkface.bmp) visible
- Hair should have transparent cutouts from black-as-alpha

## Potential Issues to Check

1. **Multiple texture nodes**: Blender warning suggests multiple texture nodes for same image
2. **UV coordinate assignment**: May not be properly mapped from trimesh to Blender
3. **Material node linking**: TextureÅ®BSDF connection might be wrong
4. **Image format**: Blender might not handle our PIL-processed RGBA correctly

## Quick Fix Ideas

### Option A: Simplify texture loading
```python
# Instead of complex PIL processing, try direct Blender loading first
img = bpy.data.images.load(image_path)
img.pack()
```

### Option B: Check UV assignment
```python
# Ensure UVs are properly assigned before material creation
if hasattr(trimesh_mesh.visual, 'uv'):
    print(f"UV data shape: {trimesh_mesh.visual.uv.shape}")
```

### Option C: Debug material node setup
```python
# Add debug prints in _create_blender_materials
print(f"Created texture node: {tex_image.name}")
print(f"Linked to BSDF Base Color: {bsdf.inputs['Base Color'].is_linked}")
```

## Test Command
```bash
cd /mnt/c/dev/loot/VF3 && python3 -u test_satsuki_blender.py
```

Expected output file: `satsuki_naked_blender.glb` (should show textures in Blender when opened)
