import base64
import os

import bpy
import gpu


if '_IMPORTED' not in locals():
    _IMPORTED = True
    from .. import gpu_luts
    from .. import shader_converter
else:
    import imp
    imp.reload(gpu_luts)
    imp.reload(shader_converter)


class KhrTechniqueWebgl:
    ext_meta = {
        'name': 'KHR_technique_webgl',
        'url': (
            'https://github.com/KhronosGroup/glTF/tree/master/extensions/'
            'Khronos/KHR_technique_webgl'
        ),
        'isDraft': True,
        'settings': {
            'embed_shaders': bpy.props.BoolProperty(
                name='Embed Shader Data',
                description='Embed shader data into the glTF file',
                default=False
            )
        }
    }
    settings = None

    def export_material(self, state, material):
        shader_data = gpu.export_shader(bpy.context.scene, material)
        if state['settings']['asset_profile'] == 'DESKTOP':
            shader_converter.to_130(shader_data)
        else:
            shader_converter.to_web(shader_data)

        if self.settings.embed_shaders is True:
            fs_bytes = shader_data['fragment'].encode()
            fs_uri = 'data:text/plain;base64,' + base64.b64encode(fs_bytes).decode('ascii')
            vs_bytes = shader_data['vertex'].encode()
            vs_uri = 'data:text/plain;base64,' + base64.b64encode(vs_bytes).decode('ascii')
        else:
            names = [
                bpy.path.clean_name(name) + '.glsl'
                for name in (material.name+'VS', material.name+'FS')
            ]
            data = (shader_data['vertex'], shader_data['fragment'])
            for name, data in zip(names, data):
                filename = os.path.join(state['settings']['gltf_output_dir'], name)
                with open(filename, 'w') as fout:
                    fout.write(data)
            vs_uri, fs_uri = names

        state['shaders'].append({'type': 35632, 'uri': fs_uri})
        state['shaders'].append({'type': 35633, 'uri': vs_uri})

        # Handle programs
        state['programs'].append({
            'attributes': [a['varname'] for a in shader_data['attributes']],
            'fragmentShader': 'shader_{}_FS'.format(material.name),
            'vertexShader': 'shader_{}_VS'.format(material.name),
        })

        # Handle parameters/values
        values = {}
        parameters = {}
        for attribute in shader_data['attributes']:
            name = attribute['varname']
            semantic = gpu_luts.TYPE_TO_SEMANTIC[attribute['type']]
            _type = gpu_luts.DATATYPE_TO_GLTF_TYPE[attribute['datatype']]
            parameters[name] = {'semantic': semantic, 'type': _type}

        for uniform in shader_data['uniforms']:
            valname = gpu_luts.TYPE_TO_NAME.get(uniform['type'], uniform['varname'])
            rnaname = valname
            semantic = None
            node = None
            value = None

            if uniform['varname'] == 'bl_ModelViewMatrix':
                semantic = 'MODELVIEW'
            elif uniform['varname'] == 'bl_ProjectionMatrix':
                semantic = 'PROJECTION'
            elif uniform['varname'] == 'bl_NormalMatrix':
                semantic = 'MODELVIEWINVERSETRANSPOSE'
            else:
                if uniform['type'] in gpu_luts.LAMP_TYPES:
                    node = uniform['lamp'].name
                    valname = node + '_' + valname
                    semantic = gpu_luts.TYPE_TO_SEMANTIC.get(uniform['type'], None)
                    if not semantic:
                        lamp_obj = bpy.data.objects[node]
                        value = getattr(lamp_obj.data, rnaname)
                elif uniform['type'] in gpu_luts.MIST_TYPES:
                    valname = 'mist_' + valname
                    mist_settings = bpy.context.scene.world.mist_settings
                    if valname == 'mist_color':
                        value = bpy.context.scene.world.horizon_color
                    else:
                        value = getattr(mist_settings, rnaname)

                    if valname == 'mist_falloff':
                        if value == 'QUADRATIC':
                            value = 0.0
                        elif value == 'LINEAR':
                            value = 1.0
                        else:
                            value = 2.0
                elif uniform['type'] in gpu_luts.WORLD_TYPES:
                    world = bpy.context.scene.world
                    value = getattr(world, rnaname)
                elif uniform['type'] in gpu_luts.MATERIAL_TYPES:
                    converter = gpu_luts.DATATYPE_TO_CONVERTER[uniform['datatype']]
                    value = converter(getattr(material, rnaname))
                    values[valname] = value
                elif uniform['type'] == gpu.GPU_DYNAMIC_SAMPLER_2DIMAGE:
                    texture_slots = [
                        slot for slot in material.texture_slots
                        if slot and slot.texture.type == 'IMAGE'
                    ]
                    for slot in texture_slots:
                        if slot.texture.image.name == uniform['image'].name:
                            value = 'texture_' + slot.texture.name
                            values[uniform['varname']] = value
                else:
                    print('Unconverted uniform:', uniform)

            parameter = {}
            if semantic:
                parameter['semantic'] = semantic
                if node:
                    parameter['node'] = 'node_' + node
            elif value:
                parameter['value'] = gpu_luts.DATATYPE_TO_CONVERTER[uniform['datatype']](value)
            else:
                parameter['value'] = None

            if uniform['type'] == gpu.GPU_DYNAMIC_SAMPLER_2DIMAGE:
                parameter['type'] = 35678  # SAMPLER_2D
            else:
                parameter['type'] = gpu_luts.DATATYPE_TO_GLTF_TYPE[uniform['datatype']]
            parameters[valname] = parameter
            uniform['valname'] = valname

        # Handle techniques
        tech_name = 'technique_' + material.name
        state['techniques'].append({
            'parameters': parameters,
            'program': 'program_' + material.name,
            'attributes': {a['varname']: a['varname'] for a in shader_data['attributes']},
            'uniforms': {u['varname']: u['valname'] for u in shader_data['uniforms']},
        })

        return {'technique': tech_name, 'values': values}

    def export(self, state):
        state['output']['materials'] = [
            self.export_material(state, bl_mat) for bl_mat in state['input']['materials']
        ]
        state['output']['programs'] = state['programs']
        state['output']['shaders'] = state['shaders']
        state['output']['techniques'] = state['techniques']
