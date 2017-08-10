from ..blendergltf import Reference


class KhrMaterialsCommon:
    ext_meta = {
        'name': 'KHR_materials_common',
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
        # extras = _get_custom_properties(light)
        # if extras:
            # gltf_light['extras'] = extras
        return gltf_light

    def export_material(self, state, material):
        all_textures = [
            slot for slot in material.texture_slots
            if slot and slot.texture.type == 'IMAGE'
        ]
        diffuse_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_diffuse
        ]
        emission_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_emit
        ]
        specular_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_spec
        ]

        diffuse_color = list((material.diffuse_color * material.diffuse_intensity)[:])
        diffuse_color += [material.alpha]
        emission_color = list((material.diffuse_color * material.emit)[:])
        emission_color += [material.alpha]
        specular_color = list((material.specular_color * material.specular_intensity)[:])
        specular_color += [material.specular_alpha]

        technique = 'PHONG'
        if material.use_shadeless:
            technique = 'CONSTANT'
            emission_textures = diffuse_textures
            emission_color = diffuse_color
        elif material.specular_intensity == 0.0:
            technique = 'LAMBERT'
        elif material.specular_shader == 'BLINN':
            technique = 'BLINN'

        gltf = {
            'technique': technique,
            'values': {
                'ambient': ([material.ambient]*3) + [1.0],
                'diffuse': diffuse_textures[-1] if diffuse_textures else diffuse_color,
                'doubleSided': not material.game_settings.use_backface_culling,
                'emission': emission_textures[-1] if emission_textures else emission_color,
                'specular': specular_textures[-1] if specular_textures else specular_color,
                'shininess': material.specular_hardness,
                'transparency': material.alpha,
                'transparent': material.use_transparency,
            }
        }

        for prop in ('diffuse', 'emission', 'specular'):
            if hasattr(gltf['values'][prop], 'blender_type'):
                ref = gltf['values'][prop]
                ref.source = gltf['values']
                ref.prop = prop
                state['references'].append(ref)

        return gltf

    def export(self, state):
        state['extensions_used'].append('KHR_materials_common')

        # Export materials
        material_pairs = [
            (material, state['output']['materials'][state['refmap'][('materials', material.name)]])
            for material in state['input']['materials']
        ]
        for bl_mat, gl_mat in material_pairs:
            gl_mat['extensions'] = gl_mat.get('extensions', {})
            gl_mat['extensions']['KHR_materials_common'] = self.export_material(state, bl_mat)

        # Export lights
        state['output']['extensions'] = state['output'].get('extensions', {})
        state['output']['extensions']['KHR_materials_common'] = {
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
                ext = node['extensions']['KHR_materials_common'] = {}
                ext['light'] = Reference('lamps', obj.data.name, ext, 'light')
                state['references'].append(ext['light'])

        # Convert light list to dictionary
        extension = state['output']['extensions']['KHR_materials_common']
        extension['lights'] = {
            'lights_' + str(i): light for i, light in enumerate(extension['lights'])
        }
