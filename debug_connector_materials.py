#!/usr/bin/env python3
"""
Debug dynamic connector material issues
Test on multi.txt to see what's wrong with the materials
"""

import bpy
import sys
import os

def debug_connector_materials():
    """Debug the materials on dynamic connectors."""
    print("🔍 DYNAMIC CONNECTOR MATERIAL DEBUG:")
    
    # Find all objects that look like connectors
    connector_objects = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'dynamic_connector' in obj.name.lower():
            connector_objects.append(obj)
    
    print(f"Found {len(connector_objects)} dynamic connector objects")
    
    for obj in connector_objects:
        print(f"\n📦 Connector: {obj.name}")
        
        if not obj.data.materials:
            print("  ❌ NO MATERIALS ASSIGNED")
            continue
            
        print(f"  Materials ({len(obj.data.materials)}):")
        for i, mat in enumerate(obj.data.materials):
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    base_color = bsdf.inputs['Base Color'].default_value
                    r, g, b, a = base_color
                    print(f"    [{i}] {mat.name}: RGB({r:.3f}, {g:.3f}, {b:.3f}) Alpha({a:.3f})")
                    
                    # Check if this looks like skin color when it shouldn't be
                    if r > 0.7 and g > 0.6 and b > 0.5:  # Skin-like
                        if 'sailor' in obj.name.lower() or 'blazer' in obj.name.lower():
                            print(f"        ⚠️ POTENTIAL CONTAMINATION: Clothing connector has skin-like color!")
                else:
                    print(f"    [{i}] {mat.name}: No Principled BSDF")
            else:
                print(f"    [{i}] {mat.name if mat else 'None'}: Not using nodes")
        
        # Check face material assignments
        face_material_counts = {}
        for face in obj.data.polygons:
            mat_idx = face.material_index
            face_material_counts[mat_idx] = face_material_counts.get(mat_idx, 0) + 1
        
        print(f"  Face Material Distribution:")
        for mat_idx, count in sorted(face_material_counts.items()):
            mat_name = obj.data.materials[mat_idx].name if mat_idx < len(obj.data.materials) else "INVALID"
            print(f"    Material {mat_idx} ({mat_name}): {count} faces")
        
        # Check bone assignments
        vertex_groups = [vg.name for vg in obj.vertex_groups]
        print(f"  Bone Groups: {vertex_groups}")

def debug_main_mesh_materials():
    """Debug the materials on main body meshes."""
    print("\n🔍 MAIN MESH MATERIAL DEBUG:")
    
    # Find body/clothing meshes
    main_objects = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'dynamic_connector' not in obj.name.lower():
            main_objects.append(obj)
    
    print(f"Found {len(main_objects)} main mesh objects")
    
    for obj in main_objects:
        if 'body' in obj.name.lower() or 'sailor' in obj.name.lower() or 'blazer' in obj.name.lower():
            print(f"\n📦 Main Mesh: {obj.name}")
            
            if not obj.data.materials:
                print("  ❌ NO MATERIALS ASSIGNED")
                continue
                
            print(f"  Materials ({len(obj.data.materials)}):")
            for i, mat in enumerate(obj.data.materials):
                if mat and mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        base_color = bsdf.inputs['Base Color'].default_value
                        r, g, b, a = base_color
                        print(f"    [{i}] {mat.name}: RGB({r:.3f}, {g:.3f}, {b:.3f}) Alpha({a:.3f})")
                else:
                    print(f"    [{i}] {mat.name if mat else 'None'}: Not using nodes")

if __name__ == "__main__":
    debug_connector_materials()
    debug_main_mesh_materials()