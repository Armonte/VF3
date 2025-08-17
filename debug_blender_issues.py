#!/usr/bin/env python3
"""
Debug actual issues in the Blender file:
1. Check if meshes actually have smooth shading
2. Check dynamic connector materials
3. Check texture visibility and alpha settings
"""

import bpy
import bmesh
import sys
import os

def debug_smooth_shading():
    """Check if meshes actually have smooth shading applied."""
    print("🔍 SMOOTH SHADING DEBUG:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            smooth_faces = 0
            total_faces = len(mesh.polygons)
            
            for poly in mesh.polygons:
                if poly.use_smooth:
                    smooth_faces += 1
            
            smooth_percentage = (smooth_faces / total_faces * 100) if total_faces > 0 else 0
            
            if smooth_percentage < 100:
                print(f"  ❌ {obj.name}: {smooth_faces}/{total_faces} faces smooth ({smooth_percentage:.1f}%)")
            else:
                print(f"  ✅ {obj.name}: All {total_faces} faces smooth")

def debug_dynamic_connector_materials():
    """Check dynamic connector materials for wrong colors."""
    print("\n🎨 DYNAMIC CONNECTOR MATERIALS DEBUG:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'dynamic_connector' in obj.name.lower():
            print(f"\n  Connector: {obj.name}")
            
            if obj.data.materials:
                for i, mat in enumerate(obj.data.materials):
                    if mat and mat.use_nodes:
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            base_color = bsdf.inputs['Base Color'].default_value
                            print(f"    Material {i}: {mat.name}")
                            print(f"      Base Color: {[f'{c:.3f}' for c in base_color]}")
                            
                            # Check if it's skin colored when it shouldn't be
                            r, g, b, a = base_color
                            if r > 0.8 and g > 0.7 and b > 0.5:  # Skin-like color
                                if 'blazer' in obj.name.lower() or 'clothing' in obj.name.lower():
                                    print(f"      ⚠️  POTENTIAL ISSUE: Clothing connector has skin-like color!")
            else:
                print(f"    ❌ No materials assigned to {obj.name}")

def debug_texture_visibility():
    """Check texture nodes and alpha settings."""
    print("\n🖼️  TEXTURE VISIBILITY DEBUG:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'head' in obj.name.lower():
            print(f"\n  Head mesh: {obj.name}")
            
            if obj.data.materials:
                for i, mat in enumerate(obj.data.materials):
                    if mat and mat.use_nodes:
                        print(f"    Material {i}: {mat.name}")
                        
                        # Check for texture nodes
                        texture_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
                        if texture_nodes:
                            for tex_node in texture_nodes:
                                if tex_node.image:
                                    print(f"      Texture: {tex_node.image.name}")
                                    print(f"        Interpolation: {tex_node.interpolation}")
                                    print(f"        Image size: {tex_node.image.size}")
                                    print(f"        Color space: {tex_node.image.colorspace_settings.name}")
                                    
                                    # Check connections
                                    color_connected = any(link.to_socket.name == 'Base Color' for link in tex_node.outputs['Color'].links)
                                    alpha_connected = any(link.to_socket.name == 'Alpha' for link in tex_node.outputs['Alpha'].links)
                                    
                                    print(f"        Color connected: {color_connected}")
                                    print(f"        Alpha connected: {alpha_connected}")
                                    
                                    if not color_connected:
                                        print(f"        ❌ TEXTURE NOT CONNECTED TO BASE COLOR!")
                        else:
                            print(f"      ❌ No texture nodes found")
                        
                        # Check material settings
                        print(f"      Blend method: {mat.blend_method}")
                        if hasattr(mat, 'alpha_threshold'):
                            print(f"      Alpha threshold: {mat.alpha_threshold}")

def debug_face_material_assignments():
    """Check if face materials are properly assigned."""
    print("\n🎭 FACE MATERIAL ASSIGNMENTS DEBUG:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'head' in obj.name.lower():
            mesh = obj.data
            print(f"\n  Head mesh: {obj.name}")
            print(f"    Total faces: {len(mesh.polygons)}")
            print(f"    Total materials: {len(mesh.materials)}")
            
            # Count material usage
            material_usage = {}
            for poly in mesh.polygons:
                mat_idx = poly.material_index
                material_usage[mat_idx] = material_usage.get(mat_idx, 0) + 1
            
            print(f"    Material usage:")
            for mat_idx, count in sorted(material_usage.items()):
                mat_name = mesh.materials[mat_idx].name if mat_idx < len(mesh.materials) else "INVALID"
                print(f"      Material {mat_idx} ({mat_name}): {count} faces")

def fix_smooth_shading():
    """Force apply smooth shading to all mesh objects."""
    print("\n🔧 FIXING SMOOTH SHADING:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            # Select the object
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            
            # Enter edit mode and select all
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            
            # Apply smooth shading
            bpy.ops.mesh.faces_shade_smooth()
            
            # Back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
            print(f"  ✅ Applied smooth shading to {obj.name}")

def fix_texture_connections():
    """Fix texture node connections that might be broken."""
    print("\n🔧 FIXING TEXTURE CONNECTIONS:")
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data.materials:
            for mat in obj.data.materials:
                if mat and mat.use_nodes:
                    # Find texture nodes and BSDF
                    texture_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    
                    if texture_nodes and bsdf:
                        for tex_node in texture_nodes:
                            # Ensure color is connected
                            if not any(link.to_socket.name == 'Base Color' for link in tex_node.outputs['Color'].links):
                                mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                                print(f"  🔗 Connected {tex_node.image.name} Color -> Base Color in {mat.name}")
                            
                            # Connect alpha if image has alpha channel
                            if tex_node.image.depth == 32:  # RGBA
                                if not any(link.to_socket.name == 'Alpha' for link in tex_node.outputs['Alpha'].links):
                                    mat.node_tree.links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
                                    print(f"  🔗 Connected {tex_node.image.name} Alpha -> Alpha in {mat.name}")

if __name__ == "__main__":
    print("🎮 BLENDER MATERIAL & SHADING DEBUG")
    print("=" * 50)
    
    # Debug current state
    debug_smooth_shading()
    debug_dynamic_connector_materials()
    debug_texture_visibility()
    debug_face_material_assignments()
    
    # Apply fixes
    print("\n" + "=" * 50)
    print("🛠️  APPLYING FIXES")
    print("=" * 50)
    
    fix_smooth_shading()
    fix_texture_connections()
    
    print("\n✅ Debug and fixes complete!")