"""
VF3 Blender Exporter
Use Blender's Python API to create proper armatures and export to glTF.
This should handle skeletal animation much better than manual glTF creation.
"""

import os
import sys
from typing import Dict, List, Any

def create_vf3_character_in_blender(bones: Dict, attachments: List, world_transforms: Dict, 
                                   mesh_data: Dict[str, Any], output_path: str):
    """Create a VF3 character in Blender with proper armature and export to glTF.
    
    Args:
        bones: Bone hierarchy from .TXT file
        attachments: Mesh attachments to bones  
        world_transforms: World positions of bones
        mesh_data: Dictionary mapping attachment resource_id to mesh data
        output_path: Where to save the .glb file
    """
    
    try:
        import bpy
        import bmesh
        from mathutils import Vector, Matrix
    except ImportError:
        print("? Blender Python API not available. Run this script inside Blender or install bpy module.")
        return False
    
    print("? Creating VF3 character in Blender...")
    
    # Step 1: Clear existing scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Step 2: Create armature
    print("? Creating armature...")
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature_obj = bpy.context.active_object
    armature_obj.name = "VF3_Armature"
    armature = armature_obj.data
    armature.name = "VF3_Armature"
    
    # Get bone hierarchy order
    bone_order = _get_bone_hierarchy_order(bones)
    
    # Clear default bone
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.delete()
    
    # Step 3: Create bones in Edit mode
    created_bones = {}
    for bone_name in bone_order:
        bone = bones[bone_name]
        
        # Create bone
        edit_bone = armature.edit_bones.new(bone_name)
        
        # Set bone position (head at world position, tail slightly offset)
        if bone_name in world_transforms:
            world_pos = world_transforms[bone_name]
            head_pos = Vector(world_pos)
        else:
            head_pos = Vector((0, 0, 0))
        
        edit_bone.head = head_pos
        edit_bone.tail = head_pos + Vector((0, 0, 1))  # Arbitrary tail direction
        
        # Set parent relationship
        if bone.parent and bone.parent in created_bones:
            edit_bone.parent = created_bones[bone.parent]
            # Use connected bones for proper hierarchy
            edit_bone.use_connect = False
        
        created_bones[bone_name] = edit_bone
        print(f"  Created bone '{bone_name}' at {head_pos}")
    
    # Step 4: Exit Edit mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Step 5: Create meshes and bind to armature
    print("? Creating and binding meshes...")
    mesh_objects = []
    
    for att in attachments:
        if att.resource_id not in mesh_data:
            continue
            
        mesh_info = mesh_data[att.resource_id]
        trimesh_mesh = mesh_info['mesh']
        
        if not trimesh_mesh:
            continue
        
        # Create Blender mesh
        mesh_name = f"{att.attach_bone}_{att.resource_id}"
        blender_mesh = bpy.data.meshes.new(mesh_name)
        
        # Apply world transform to vertices
        vertices = trimesh_mesh.vertices.copy()
        if att.attach_bone in world_transforms:
            world_pos = world_transforms[att.attach_bone]
            vertices += world_pos
        
        # Set mesh data
        faces = trimesh_mesh.faces.tolist()
        blender_mesh.from_pydata(vertices.tolist(), [], faces)
        blender_mesh.update()
        
        # Create mesh object
        mesh_obj = bpy.data.objects.new(mesh_name, blender_mesh)
        bpy.context.collection.objects.link(mesh_obj)
        
        # Step 6: Create vertex groups and bind to armature
        if att.attach_bone in created_bones:
            # Create vertex group for this bone
            vertex_group = mesh_obj.vertex_groups.new(name=att.attach_bone)
            
            # Assign all vertices to this bone with weight 1.0
            vertex_indices = list(range(len(vertices)))
            vertex_group.add(vertex_indices, 1.0, 'REPLACE')
            
            # Add armature modifier
            armature_modifier = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
            armature_modifier.object = armature_obj
            armature_modifier.use_vertex_groups = True
            
            print(f"  Created mesh '{mesh_name}' with {len(vertices)} vertices, bound to bone '{att.attach_bone}'")
        
        mesh_objects.append(mesh_obj)
    
    # Step 7: Select all objects for export
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(True)
    
    bpy.context.view_layer.objects.active = armature_obj
    
    # Step 8: Export to glTF
    print(f"? Exporting to {output_path}...")
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            export_selected=True,
            export_apply=True,
            export_animations=False,  # No animations yet
            export_skins=True,        # Include armature/skinning
            export_morph=False,
            export_force_sampling=False
        )
        print(f"? Successfully exported VF3 character to {output_path}")
        return True
        
    except Exception as e:
        print(f"? Export failed: {e}")
        return False


def _get_bone_hierarchy_order(bones: Dict) -> List[str]:
    """Get bones in hierarchical order (parents before children)."""
    roots = [name for name, bone in bones.items() if not bone.parent or bone.parent not in bones]
    
    ordered = []
    visited = set()
    
    def visit_bone(bone_name: str):
        if bone_name in visited or bone_name not in bones:
            return
        visited.add(bone_name)
        ordered.append(bone_name)
        
        children = [name for name, bone in bones.items() if bone.parent == bone_name]
        for child in sorted(children):
            visit_bone(child)
    
    for root in sorted(roots):
        visit_bone(root)
    
    return ordered


def run_blender_export_script(script_path: str, descriptor_path: str, output_path: str):
    """Run the Blender export script using Blender's Python interpreter.
    
    Args:
        script_path: Path to this Python script
        descriptor_path: Path to VF3 .TXT descriptor
        output_path: Where to save the .glb file
    """
    
    # Try to find Blender executable
    blender_paths = [
        "/usr/bin/blender",
        "/usr/local/bin/blender", 
        "/opt/blender/blender",
        "C:\\Program Files\\Blender Foundation\\Blender*\\blender.exe",
        "blender"  # Hope it's in PATH
    ]
    
    blender_exe = None
    for path in blender_paths:
        if os.path.exists(path) or path == "blender":
            blender_exe = path
            break
    
    if not blender_exe:
        print("? Could not find Blender executable. Please install Blender or add it to PATH.")
        return False
    
    # Create command to run Blender in background with our script
    cmd = [
        blender_exe,
        "--background",  # No GUI
        "--python", script_path,
        "--", descriptor_path, output_path  # Pass arguments to script
    ]
    
    print(f"? Running Blender export: {' '.join(cmd)}")
    
    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("? Blender export completed successfully")
            return True
        else:
            print(f"? Blender export failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("? Blender export timed out")
        return False
    except Exception as e:
        print(f"? Error running Blender: {e}")
        return False


if __name__ == "__main__":
    # This script can be run directly by Blender
    if len(sys.argv) >= 3:
        descriptor_path = sys.argv[-2]
        output_path = sys.argv[-1]
        
        print(f"? Blender VF3 Export: {descriptor_path} -> {output_path}")
        
        # Import VF3 modules (make sure they're in path)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        
        from vf3_loader import read_descriptor, parse_frame_bones, build_world_transforms
        from vf3_mesh_loader import load_mesh_with_full_materials
        
        # Load VF3 data
        desc = read_descriptor(descriptor_path)
        bones = parse_frame_bones(desc)
        
        # For now, just load skin attachments (simplified)
        attachments = []
        if 'defaultvisual' in desc.blocks:
            for line in desc.blocks['defaultvisual']:
                if ':' in line:
                    bone_name, resource_id = line.split(':', 1)
                    # Create a simple attachment object
                    class SimpleAttachment:
                        def __init__(self, bone, resource):
                            self.attach_bone = bone.strip()
                            self.resource_id = resource.strip()
                    
                    attachments.append(SimpleAttachment(bone_name, resource_id))
        
        world_transforms = build_world_transforms(bones, [])
        
        # Load mesh data
        mesh_data = {}
        base_dir = os.path.dirname(descriptor_path)
        
        for att in attachments:
            if '.' in att.resource_id:
                prefix, suffix = att.resource_id.split('.', 1)
                char_dir = os.path.join(base_dir, prefix)
                
                for ext in ['.X', '.x']:
                    mesh_path = os.path.join(char_dir, suffix + ext)
                    if os.path.exists(mesh_path):
                        try:
                            mesh_info = load_mesh_with_full_materials(mesh_path)
                            if mesh_info['mesh']:
                                mesh_data[att.resource_id] = mesh_info
                                break
                        except Exception as e:
                            print(f"Failed to load {mesh_path}: {e}")
        
        # Create character in Blender
        success = create_vf3_character_in_blender(bones, attachments, world_transforms, mesh_data, output_path)
        
        if success:
            print("? VF3 character created successfully in Blender!")
        else:
            print("? Failed to create VF3 character")
    else:
        print("Usage: Run this script with Blender: blender --background --python vf3_blender_exporter.py -- input.TXT output.glb")


