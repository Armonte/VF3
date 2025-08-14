#!/usr/bin/env python3
"""Analyze the exported glb file to see what we got."""
import json
import os

def analyze_glb(filename):
    """Analyze a glb file to see what's inside."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return
    
    file_size = os.path.getsize(filename)
    print(f"📁 File: {filename} ({file_size:,} bytes)")
    
    with open(filename, 'rb') as f:
        # Read glTF header
        header = f.read(12)
        if header[:4] != b'glTF':
            print("❌ Not a valid glTF binary file")
            return
        
        version = int.from_bytes(header[4:8], 'little')
        length = int.from_bytes(header[8:12], 'little')
        print(f"✅ Valid glTF v{version}.0, total length: {length:,} bytes")
        
        # Read JSON chunk
        json_chunk_header = f.read(8)
        json_chunk_length = int.from_bytes(json_chunk_header[:4], 'little')
        json_chunk_type = json_chunk_header[4:8]
        
        if json_chunk_type != b'JSON':
            print(f"❌ Expected JSON chunk, got {json_chunk_type}")
            return
            
        json_data = f.read(json_chunk_length)
        gltf_json = json.loads(json_data.decode('utf-8'))
        
        print(f"\n📊 glTF Contents Analysis:")
        
        # Scenes
        scenes = gltf_json.get('scenes', [])
        print(f"   🎬 Scenes: {len(scenes)}")
        if scenes:
            scene = scenes[0]
            nodes = scene.get('nodes', [])
            print(f"      Root nodes: {len(nodes)}")
        
        # Nodes (bones/objects)
        nodes = gltf_json.get('nodes', [])
        print(f"   🎭 Nodes: {len(nodes)}")
        armature_nodes = []
        mesh_nodes = []
        for i, node in enumerate(nodes):
            if 'mesh' in node:
                mesh_nodes.append(i)
            else:
                armature_nodes.append(i)
        print(f"      Armature nodes: {len(armature_nodes)}")
        print(f"      Mesh nodes: {len(mesh_nodes)}")
        
        # Meshes
        meshes = gltf_json.get('meshes', [])
        print(f"   📦 Meshes: {len(meshes)}")
        total_primitives = sum(len(mesh.get('primitives', [])) for mesh in meshes)
        print(f"      Total primitives: {total_primitives}")
        
        # Materials
        materials = gltf_json.get('materials', [])
        print(f"   🎨 Materials: {len(materials)}")
        textured_materials = 0
        for mat in materials:
            if 'pbrMetallicRoughness' in mat:
                pbr = mat['pbrMetallicRoughness']
                if 'baseColorTexture' in pbr:
                    textured_materials += 1
        print(f"      With textures: {textured_materials}")
        print(f"      Color-only: {len(materials) - textured_materials}")
        
        # Textures and Images
        textures = gltf_json.get('textures', [])
        images = gltf_json.get('images', [])
        print(f"   🖼️  Textures: {len(textures)}")
        print(f"   📷 Images: {len(images)}")
        
        # Skins (armatures)
        skins = gltf_json.get('skins', [])
        print(f"   🦴 Skins (armatures): {len(skins)}")
        if skins:
            skin = skins[0]
            joints = skin.get('joints', [])
            print(f"      Joints in first skin: {len(joints)}")
            if 'inverseBindMatrices' in skin:
                print(f"      ✅ Has inverse bind matrices (proper rigging)")
            else:
                print(f"      ❌ No inverse bind matrices")
                
            # Print joint names
            if len(joints) <= 20:  # Don't spam if too many
                joint_names = []
                for joint_idx in joints:
                    if joint_idx < len(nodes):
                        node = nodes[joint_idx]
                        name = node.get('name', f'Joint_{joint_idx}')
                        joint_names.append(name)
                print(f"      Joint names: {', '.join(joint_names)}")
        
        # Animations
        animations = gltf_json.get('animations', [])
        print(f"   🎬 Animations: {len(animations)}")
        
        # Accessors (vertex data)
        accessors = gltf_json.get('accessors', [])
        print(f"   📈 Accessors: {len(accessors)}")
        
        # Buffer Views and Buffers
        buffer_views = gltf_json.get('bufferViews', [])
        buffers = gltf_json.get('buffers', [])
        print(f"   📋 Buffer Views: {len(buffer_views)}")
        print(f"   💾 Buffers: {len(buffers)}")
        if buffers:
            buffer_size = buffers[0].get('byteLength', 0)
            print(f"      First buffer size: {buffer_size:,} bytes")
        
        # Summary
        print(f"\n🎯 SUMMARY:")
        armature_working = len(skins) > 0 and skins[0].get('inverseBindMatrices') is not None
        materials_working = len(materials) > 0
        textures_working = textured_materials > 0
        
        print(f"   🦴 Armature: {'✅ WORKING' if armature_working else '❌ BROKEN'}")
        print(f"   🎨 Materials: {'✅ WORKING' if materials_working else '❌ BROKEN'}")  
        print(f"   🖼️  Textures: {'✅ WORKING' if textures_working else '❌ BROKEN'}")
        print(f"   📦 Meshes: {'✅ WORKING' if len(meshes) > 0 else '❌ BROKEN'}")
        
        if armature_working and materials_working:
            print(f"   🎉 OVERALL: ✅ SUCCESS - Both armature and materials are working!")
        else:
            print(f"   ⚠️  OVERALL: ❌ ISSUES - Check failed components above")

if __name__ == "__main__":
    analyze_glb("satsuki_blender_test.glb")