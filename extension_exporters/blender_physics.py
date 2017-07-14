class BlenderPhysics:
    ext_meta = {
        'name': 'BLENDER_physics',
    }

    def export_physics(self, obj):
        body = obj.rigid_body
        physics = {
            'collisionShape': body.collision_shape.upper(),
            'mass': body.mass,
            'static': body.type == 'PASSIVE',
            'dimensions': obj.dimensions[:],
        }

        if body.collision_shape in ('CONVEX_HULL', 'MESH'):
            physics['mesh'] = 'mesh_' + obj.data.name

        return physics

    def export(self, state):
        state['extensions_used'].append('BLENDER_physics')

        obj_pairs = [
            (obj, state['output']['nodes'][state['refmap'][('objects', obj.name)]])
            for obj in state['input']['objects']
            if obj.rigid_body
        ]
        for obj, node in obj_pairs:
            node['extensions'] = node.get('extensions', {})
            node['extensions']['BLENDER_physics'] = self.export_physics(obj)

        scene_pairs = [
            (scene, state['output']['scenes'][state['refmap'][('scenes', scene.name)]])
            for scene in state['input']['scenes']
        ]
        for scene, gltf in scene_pairs:
            gltf['extensions'] = gltf.get('extensions', {})
            gltf['extensions']['BLENDER_physics'] = {
                'gravity': scene.gravity.z
            }
