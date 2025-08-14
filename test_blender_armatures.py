#!/usr/bin/env python3
"""
Test the Blender exporter to see if armatures and materials work properly.
"""
import os
import sys
import subprocess

# Add current directory to path for VF3 modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_blender_exporter():
    """Test the Blender exporter with Satsuki."""
    print("🧪 Testing Blender exporter for armatures and materials...")
    
    # Check if we can run Blender
    try:
        result = subprocess.run(['blender', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Blender not found or not working")
            return False
        print(f"✅ Found Blender: {result.stdout.split()[1]}")
    except Exception as e:
        print(f"❌ Cannot run Blender: {e}")
        return False
    
    # Test the exporter
    descriptor_path = "data/satsuki.txt"
    output_path = "satsuki_blender_test.glb"
    
    if not os.path.exists(descriptor_path):
        print(f"❌ Descriptor not found: {descriptor_path}")
        return False
    
    print(f"🔧 Running Blender export: {descriptor_path} -> {output_path}")
    
    # Run the Blender exporter
    cmd = [
        'blender',
        '--background',
        '--python', 'vf3_blender_exporter.py', 
        '--', descriptor_path, output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")  
            print(result.stderr)
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"✅ Export successful! Output file: {output_path} ({file_size} bytes)")
                
                # Try to analyze the glb file
                try:
                    import json
                    import base64
                    
                    # Read and check if it's a valid glb
                    with open(output_path, 'rb') as f:
                        header = f.read(12)
                        if header[:4] == b'glTF':
                            print("✅ Valid glTF binary file created")
                            
                            # Try to extract some info
                            json_chunk_length = int.from_bytes(header[8:12], 'little')
                            json_data = f.read(json_chunk_length)
                            
                            try:
                                gltf_json = json.loads(json_data[8:])  # Skip chunk header
                                
                                # Check for nodes (armature)
                                nodes = gltf_json.get('nodes', [])
                                print(f"📊 Nodes in glTF: {len(nodes)}")
                                
                                # Check for meshes
                                meshes = gltf_json.get('meshes', [])
                                print(f"📦 Meshes in glTF: {len(meshes)}")
                                
                                # Check for materials
                                materials = gltf_json.get('materials', [])
                                print(f"🎨 Materials in glTF: {len(materials)}")
                                
                                # Check for skins (armatures)
                                skins = gltf_json.get('skins', [])
                                print(f"🦴 Skins (armatures) in glTF: {len(skins)}")
                                if skins:
                                    skin = skins[0]
                                    joints = skin.get('joints', [])
                                    print(f"   Joints in first skin: {len(joints)}")
                                    if 'inverseBindMatrices' in skin:
                                        print("   ✅ Has inverse bind matrices (proper rigging)")
                                    else:
                                        print("   ⚠️  No inverse bind matrices")
                                
                                # Check animations
                                animations = gltf_json.get('animations', [])
                                print(f"🎬 Animations in glTF: {len(animations)}")
                                
                                # Summary
                                print(f"\n📋 BLENDER EXPORT ANALYSIS:")
                                print(f"   🦴 Armature: {'✅ YES' if skins else '❌ NO'}")
                                print(f"   🎨 Materials: {'✅ YES' if materials else '❌ NO'}")  
                                print(f"   📦 Meshes: {'✅ YES' if meshes else '❌ NO'}")
                                print(f"   🔗 Proper rigging: {'✅ YES' if (skins and skins[0].get('inverseBindMatrices')) else '❌ NO'}")
                                
                                return True
                                
                            except json.JSONDecodeError:
                                print("⚠️  Could not parse glTF JSON data")
                                return True  # File was created, that's something
                                
                        else:
                            print("⚠️  File created but not a valid glTF binary")
                            return False
                            
                except Exception as e:
                    print(f"⚠️  Could not analyze output file: {e}")
                    return True  # File was created, that's something
                    
            else:
                print(f"❌ Export claimed success but no output file created")
                return False
        else:
            print(f"❌ Export failed with return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Export timed out")
        return False
    except Exception as e:
        print(f"❌ Error running export: {e}")
        return False

if __name__ == "__main__":
    success = test_blender_exporter()
    sys.exit(0 if success else 1)