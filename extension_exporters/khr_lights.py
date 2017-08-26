from ..blendergltf import Reference


class KhrLights:
    ext_meta = {
        'name': 'KHR_lights',
        'url': (
            'https://github.com/andreasplesch/glTF/blob/ec6f61d73bcd58d59d4a4ea9ac009f973c693c5f/'
            'extensions/Khronos/KHR_lights/README.md'
        ),
        'isDraft': True,
    }

    def export_light(self, light):
        def calc_att():
            linear_factor = 0
            quad_factor = 0

            if light.falloff_type == 'INVERSE_LINEAR':
                linear_factor = 1 / light.distance
            elif light.falloff_type == 'INVERSE_SQUARE':
                quad_factor = 1 / light.distance
            elif light.falloff_type == 'LINEAR_QUADRATIC_WEIGHTED':
                linear_factor = light.linear_attenuation * (1 / light.distance)
                quad_factor = light.quadratic_attenuation * (1 / (light.distance * light.distance))

            return linear_factor, quad_factor

        gltf_light = {}
        if light.type == 'SUN':
            gltf_light = {
                'directional': {
                    'color': (light.color * light.energy)[:],
                },
                'type': 'directional',
            }
        elif light.type == 'POINT':
            linear_factor, quad_factor = calc_att()
            gltf_light = {
                'point': {
                    'color': (light.color * light.energy)[:],

                    # TODO: grab values from Blender lamps
                    'constantAttenuation': 1,
                    'linearAttenuation': linear_factor,
                    'quadraticAttenuation': quad_factor,
                },
                'type': 'point',
            }
        elif light.type == 'SPOT':
            linear_factor, quad_factor = calc_att()
            gltf_light = {
                'spot': {
                    'color': (light.color * light.energy)[:],

                    # TODO: grab values from Blender lamps
                    'constantAttenuation': 1.0,
                    'fallOffAngle': 3.14159265,
                    'fallOffExponent': 0.0,
                    'linearAttenuation': linear_factor,
                    'quadraticAttenuation': quad_factor,
                },
                'type': 'spot',
            }
        else:
            print("Unsupported lamp type on {}: {}".format(light.name, light.type))
            gltf_light = {'type': 'unsupported'}

        gltf_light['name'] = light.name

        return gltf_light

    def export(self, state):
        state['extensions_used'].append('KHR_lights')

        # Export lights
        state['output']['extensions'] = state['output'].get('extensions', {})
        state['output']['extensions']['KHR_lights'] = {
            'lights': [self.export_light(lamp) for lamp in state['input'].get('lamps', [])]
        }

        # Add light references to nodes
        obj_pairs = [
            (obj, state['output']['nodes'][state['refmap'][('objects', obj.name)]])
            for obj in state['input']['objects']
        ]

        for obj, node in obj_pairs:
            if obj.type == 'LAMP':
                node['extensions'] = node.get('extensions', {})
                ext = node['extensions']['KHR_lights'] = {}
                ext['light'] = Reference('lamps', obj.data.name, ext, 'light')
                state['references'].append(ext['light'])
