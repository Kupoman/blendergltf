from ..blendergltf import Reference


class BlenderPhysics:
    ext_meta = {
        'name': 'BLENDER_physics',
        'url': (
            'https://github.com/Kupoman/blendergltf/tree/master/extensions/'
            'BLENDER_physics'
        ),
        'isDraft': True,
    }

    def export_physics(self, state, obj, gltf_node):
        body = obj.rigid_body
        bounds = [obj.dimensions[i] / gltf_node['scale'][i] for i in range(3)]
        collision_layers = sum(layer << i for i, layer in enumerate(body.collision_groups))
        physics = {
            'collisionShapes': [{
                'shapeType': body.collision_shape.upper(),
                'boundingBox': bounds,
                'primaryAxis': "Z",
            }],
            'mass': body.mass,
            'static': body.type == 'PASSIVE',
            'collisionGroups': collision_layers,
            'collisionMasks': collision_layers,
        }

        if body.collision_shape in ('CONVEX_HULL', 'MESH'):
            mesh = state['mod_meshes'].get(obj.name, obj.data)
            meshref = Reference('meshes', mesh.name, physics['collisionShapes'][0], 'mesh')
            physics['collisionShapes'][0]['mesh'] = meshref
            state['references'].append(meshref)

        return physics

    def export(self, state):
        state['extensions_used'].append('BLENDER_physics')

        obj_pairs = [
            (obj, state['output']['nodes'][state['refmap'][('objects', obj.name)]])
            for obj in state['input']['objects']
            if getattr(obj, 'rigid_body', False)
        ]
        for obj, node in obj_pairs:
            node['extensions'] = node.get('extensions', {})
            node['extensions']['BLENDER_physics'] = self.export_physics(state, obj, node)

        scene_pairs = [
            (scene, state['output']['scenes'][state['refmap'][('scenes', scene.name)]])
            for scene in state['input']['scenes']
        ]
        for scene, gltf in scene_pairs:
            gltf['extensions'] = gltf.get('extensions', {})
            gltf['extensions']['BLENDER_physics'] = {
                'gravity': scene.gravity.z
            }
