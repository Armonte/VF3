#!/usr/bin/env python3
"""
VF3 Simple Blender Exporter
Modular, clean approach based on the working export_ciel_to_gltf.py
"""

import os
import sys

# Blender imports
try:
    import bpy
    print("✅ Blender Python API available")
except ImportError:
    print("❌ This script must be run within Blender")
    sys.exit(1)

# Add project directory to path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# VF3 imports - use existing modules
from vf3_loader import read_descriptor, parse_frame_bones, collect_active_attachments, build_world_transforms, find_mesh_file
from vf3_mesh_loader import load_mesh_with_full_materials
from vf3_exporter_core import create_vf3_character_simple

def parse_vf3_descriptor(descriptor_path):
    """Parse VF3 descriptor file and return bones and attachments"""
    descriptor = read_descriptor(descriptor_path)
    bones = parse_frame_bones(descriptor)
    attachments, clothing_dynamic_meshes = collect_active_attachments(descriptor)
    return bones, attachments

def process_occupancy_filtering(attachments):
    """Simple passthrough - no filtering needed for simple exporter"""
    return attachments, []

def main():
    """Main export function"""
    
    if len(sys.argv) < 3:
        print("Usage: blender --background --python export_vf3_simple.py -- <character.TXT> <output.glb>")
        return False
    
    # Get arguments after the -- separator
    try:
        separator_idx = sys.argv.index('--')
        script_args = sys.argv[separator_idx + 1:]
    except ValueError:
        script_args = sys.argv[1:]  # Fallback if no -- found
    
    if len(script_args) < 2:
        print("❌ Missing arguments: need <character.TXT> <output.glb>")
        return False
    
    descriptor_path = script_args[0]
    output_path = script_args[1]
    
    print(f"🎌 VF3 Simple Export: {descriptor_path} → {output_path}")
    
    if not os.path.exists(descriptor_path):
        print(f"❌ Character file not found: {descriptor_path}")
        return False
    
    try:
        # Step 1: Load character data using existing loaders
        print("📋 Loading character data...")
        bones, attachments = parse_vf3_descriptor(descriptor_path)
        attachments, clothing_dynamic_meshes = process_occupancy_filtering(attachments)
        world_transforms = build_world_transforms(bones, attachments)
        print(f"✅ Loaded {len(attachments)} attachments, {len(bones)} bones")
        
        # Step 2: Load mesh data
        print("🔧 Loading mesh data...")
        mesh_data = {}
        for att in attachments:
            # Use existing mesh finder
            mesh_path = find_mesh_file(att.resource_id)
            
            if mesh_path and os.path.exists(mesh_path):
                try:
                    mesh_info = load_mesh_with_full_materials(mesh_path)
                    if mesh_info['mesh']:
                        mesh_data[att.resource_id] = mesh_info
                        print(f"  ✅ {att.resource_id}: {len(mesh_info['mesh'].vertices)} vertices")
                except Exception as e:
                    print(f"  ❌ Failed to load {mesh_path}: {e}")
            else:
                print(f"  ⚠️ Mesh not found: {att.resource_id}")
        
        print(f"✅ Loaded {len(mesh_data)} meshes")
        
        # Step 3: Create character in Blender using simplified approach
        print("🎭 Creating character in Blender...")
        success = create_vf3_character_simple(bones, attachments, world_transforms, mesh_data, output_path)
        
        if success:
            print(f"🎉 Export completed successfully: {output_path}")
            return True
        else:
            print("❌ Export failed")
            return False
            
    except Exception as e:
        print(f"❌ Export failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)