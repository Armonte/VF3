import bpy

# Clear existing scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import the GLB file
bpy.ops.import_scene.gltf(filepath='satsuki_fixed_connector_scoping.glb')

print('=== MESH ANALYSIS ===')
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f'Mesh: {obj.name}')
        if obj.data.materials:
            for i, mat in enumerate(obj.data.materials):
                print(f'  Material {i}: {mat.name}')
                if mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get('Principled BSDF')
                    if bsdf:
                        color = bsdf.inputs['Base Color'].default_value[:3]
                        print(f'    Color: {color}')
        print()