import base64
import os
import re

import bpy
import gpu

LAMP_TYPES = [
    gpu.GPU_DYNAMIC_LAMP_DYNVEC,
    gpu.GPU_DYNAMIC_LAMP_DYNCO,
    gpu.GPU_DYNAMIC_LAMP_DYNIMAT,
    gpu.GPU_DYNAMIC_LAMP_DYNPERSMAT,
    gpu.GPU_DYNAMIC_LAMP_DYNENERGY,
    gpu.GPU_DYNAMIC_LAMP_DYNENERGY,
    gpu.GPU_DYNAMIC_LAMP_DYNCOL,
    gpu.GPU_DYNAMIC_LAMP_DISTANCE,
    gpu.GPU_DYNAMIC_LAMP_ATT1,
    gpu.GPU_DYNAMIC_LAMP_ATT2,
    gpu.GPU_DYNAMIC_LAMP_SPOTSIZE,
    gpu.GPU_DYNAMIC_LAMP_SPOTBLEND,
]

MIST_TYPES = [
    gpu.GPU_DYNAMIC_MIST_ENABLE,
    gpu.GPU_DYNAMIC_MIST_START,
    gpu.GPU_DYNAMIC_MIST_DISTANCE,
    gpu.GPU_DYNAMIC_MIST_INTENSITY,
    gpu.GPU_DYNAMIC_MIST_TYPE,
    gpu.GPU_DYNAMIC_MIST_COLOR,
]

WORLD_TYPES = [
    gpu.GPU_DYNAMIC_HORIZON_COLOR,
    gpu.GPU_DYNAMIC_AMBIENT_COLOR,
]

MATERIAL_TYPES = [
    gpu.GPU_DYNAMIC_MAT_DIFFRGB,
    gpu.GPU_DYNAMIC_MAT_REF,
    gpu.GPU_DYNAMIC_MAT_SPECRGB,
    gpu.GPU_DYNAMIC_MAT_SPEC,
    gpu.GPU_DYNAMIC_MAT_HARD,
    gpu.GPU_DYNAMIC_MAT_EMIT,
    gpu.GPU_DYNAMIC_MAT_AMB,
    gpu.GPU_DYNAMIC_MAT_ALPHA,
]

TYPE_TO_NAME = {
    gpu.GPU_DYNAMIC_OBJECT_VIEWMAT: 'view_mat',
    gpu.GPU_DYNAMIC_OBJECT_MAT: 'model_mat',
    gpu.GPU_DYNAMIC_OBJECT_VIEWIMAT: 'inv_view_mat',
    gpu.GPU_DYNAMIC_OBJECT_IMAT: 'inv_model_mat',
    gpu.GPU_DYNAMIC_OBJECT_COLOR: 'color',
    gpu.GPU_DYNAMIC_OBJECT_AUTOBUMPSCALE: 'auto_bump_scale',

    gpu.GPU_DYNAMIC_MIST_ENABLE: 'use_mist',
    gpu.GPU_DYNAMIC_MIST_START: 'start',
    gpu.GPU_DYNAMIC_MIST_DISTANCE: 'depth',
    gpu.GPU_DYNAMIC_MIST_INTENSITY: 'intensity',
    gpu.GPU_DYNAMIC_MIST_TYPE: 'falloff',
    gpu.GPU_DYNAMIC_MIST_COLOR: 'color',

    gpu.GPU_DYNAMIC_HORIZON_COLOR: 'horizon_color',
    gpu.GPU_DYNAMIC_AMBIENT_COLOR: 'ambient_color',

    gpu.GPU_DYNAMIC_LAMP_DYNVEC: 'dynvec',
    gpu.GPU_DYNAMIC_LAMP_DYNCO: 'dynco',
    gpu.GPU_DYNAMIC_LAMP_DYNIMAT: 'dynimat',
    gpu.GPU_DYNAMIC_LAMP_DYNPERSMAT: 'dynpersmat',
    gpu.GPU_DYNAMIC_LAMP_DYNENERGY: 'energy',
    gpu.GPU_DYNAMIC_LAMP_DYNCOL: 'color',
    gpu.GPU_DYNAMIC_LAMP_DISTANCE: 'distance',
    gpu.GPU_DYNAMIC_LAMP_ATT1: 'linear_attenuation',
    gpu.GPU_DYNAMIC_LAMP_ATT2: 'quadratic_attenuation',
    gpu.GPU_DYNAMIC_LAMP_SPOTSIZE: 'spot_size',
    gpu.GPU_DYNAMIC_LAMP_SPOTBLEND: 'spot_blend',

    gpu.GPU_DYNAMIC_MAT_DIFFRGB: 'diffuse_color',
    gpu.GPU_DYNAMIC_MAT_REF: 'diffuse_intensity',
    gpu.GPU_DYNAMIC_MAT_SPECRGB: 'specular_color',
    gpu.GPU_DYNAMIC_MAT_SPEC: 'specular_intensity',
    gpu.GPU_DYNAMIC_MAT_HARD: 'specular_hardness',
    gpu.GPU_DYNAMIC_MAT_EMIT: 'emit',
    gpu.GPU_DYNAMIC_MAT_AMB: 'ambient',
    gpu.GPU_DYNAMIC_MAT_ALPHA: 'alpha',
}

TYPE_TO_SEMANTIC = {
    gpu.GPU_DYNAMIC_LAMP_DYNVEC: 'BL_DYNVEC',
    gpu.GPU_DYNAMIC_LAMP_DYNCO: 'MODELVIEW',  # dynco gets extracted from the matrix
    gpu.GPU_DYNAMIC_LAMP_DYNIMAT: 'BL_DYNIMAT',
    gpu.GPU_DYNAMIC_LAMP_DYNPERSMAT: 'BL_DYNPERSMAT',
    gpu.CD_ORCO: 'POSITION',
    gpu.CD_MTFACE: 'TEXCOORD_0',
    -1: 'NORMAL'        # Hack until the gpu module has something for normals
}

DATATYPE_TO_CONVERTER = {
    gpu.GPU_DATA_1I: lambda x: x,
    gpu.GPU_DATA_1F: lambda x: x,
    gpu.GPU_DATA_2F: list,
    gpu.GPU_DATA_3F: list,
    gpu.GPU_DATA_4F: list,
}

DATATYPE_TO_GLTF_TYPE = {
    gpu.GPU_DATA_1I: 5124,  # INT
    gpu.GPU_DATA_1F: 5126,  # FLOAT
    gpu.GPU_DATA_2F: 35664,  # FLOAT_VEC2
    gpu.GPU_DATA_3F: 35665,  # FLOAT_VEC3
    gpu.GPU_DATA_4F: 35666,  # FLOAT_VEC4
    gpu.GPU_DATA_9F: 35675,  # FLOAT_MAT3
    gpu.GPU_DATA_16F: 35676,  # FLOAT_MAT4
}


def vs_to_130(data):
    data['attributes'].append({
        'varname': 'bl_Vertex',
        'type': gpu.CD_ORCO,
        'datatype': gpu.GPU_DATA_4F
    })
    data['attributes'].append({
        'varname': 'bl_Normal',
        'type': -1,
        'datatype': gpu.GPU_DATA_3F
    })
    data['uniforms'].append({
        'varname': 'bl_ModelViewMatrix',
        'type': 0,
        'datatype': gpu.GPU_DATA_16F,
    })
    data['uniforms'].append({
        'varname': 'bl_ProjectionMatrix',
        'type': 0,
        'datatype': gpu.GPU_DATA_16F,
    })
    data['uniforms'].append({
        'varname': 'bl_NormalMatrix',
        'type': 0,
        'datatype': gpu.GPU_DATA_9F,
    })

    src = '#version 130\n'
    src += 'in vec4 bl_Vertex;\n'
    src += 'in vec3 bl_Normal;\n'
    src += 'uniform mat4 bl_ModelViewMatrix;\n'
    src += 'uniform mat4 bl_ProjectionMatrix;\n'
    src += 'uniform mat3 bl_NormalMatrix;\n'

    src += data['vertex']

    src = re.sub(r'#ifdef USE_OPENSUBDIV([^#]*)#endif', '', src)
    src = re.sub(r'#ifndef USE_OPENSUBDIV([^#]*)#endif', r'\1', src)
    src = re.sub(r'#ifdef CLIP_WORKAROUND(.*?)#endif', '', src, 0, re.DOTALL)
    src = re.sub(r'\bvarying\b', 'out', src)
    src = re.sub(r'\bgl_(?!Position)(.*?)\b', r'bl_\1', src)

    data['vertex'] = src


def fs_to_130(data):
    src = '#version 130\n'
    src += 'out vec4 frag_color;\n'
    src += 'uniform mat4 bl_ProjectionMatrix;\n'
    src += 'uniform mat4 bl_ModelViewMatrix;\n'
    src += 'uniform mat4 bl_ModelViewMatrixInverse;\n'
    src += 'uniform mat3 bl_NormalMatrix;\n'
    src += 'uniform mat4 bl_ProjectionMatrixInverse;\n'

    src += data['fragment']

    src = re.sub(r'\bvarying\b', 'in', src)
    src = re.sub(r'\bgl_FragColor\b', 'frag_color', src)
    src = re.sub(r'\bgl_(?!FrontFacing)(.*?)\b', r'bl_\1', src)

    # Cannot support node_bsdf functions without resolving use of gl_Light
    src = re.sub(r'void node_((bsdf)|(subsurface))_.*?^}', '', src, 0, re.DOTALL | re.MULTILINE)

    # Need to gather light data from more general uniforms
    light_count = 0
    light_map = {}
    decl_start_str = 'void main()\n{\n'
    for uniform in data['uniforms']:
        if uniform['type'] == gpu.GPU_DYNAMIC_LAMP_DYNCO:
            lamp_name = uniform['lamp'].name
            if lamp_name not in light_map:
                light_map[lamp_name] = light_count
                light_count += 1
            light_index = light_map[lamp_name]
            varname = 'light{}_transform'.format(light_index)
            uniform['datatype'] = gpu.GPU_DATA_16F
            src = src.replace(
                'uniform vec3 {};'.format(uniform['varname']),
                'uniform mat4 {};'.format(varname)
            )
            var_decl_start = src.find(decl_start_str) + len(decl_start_str)
            decl_str = '\tvec3 {} = {}[3].xyz;\n'.format(uniform['varname'], varname)
            src = src[:var_decl_start] + decl_str + src[var_decl_start:]
            uniform['varname'] = varname

    data['fragment'] = src.replace('\r\r\n', '')


def vs_to_web(data):
    src = data['vertex']

    precision_block = '\n'
    for data_type in ('float', 'int'):
        precision_block += 'precision mediump {};\n'.format(data_type)

    src = src.replace('#version 130', '#version 100\n' + precision_block)
    src = re.sub(r'\bin\b', 'attribute', src)
    src = re.sub(r'\bout\b', 'varying', src)

    data['vertex'] = src


def fs_to_web(data):
    src = data['fragment']

    precision_block = '\n'
    for data_type in ('float', 'int'):
        precision_block += 'precision mediump {};\n'.format(data_type)

    header = '#version 100\n'
    header += '#extension GL_OES_standard_derivatives: enable\n'
    header += precision_block
    src = src.replace('#version 130', header)
    src = re.sub(r'\bin\b', 'varying', src)
    src = src.replace('out vec4 frag_color;\n', '')
    src = re.sub(r'\bfrag_color\b', 'gl_FragColor', src)

    # TODO: This should be fixed in Blender
    src = src.replace('blend = (normalize(vec).z + 1)', 'blend = (normalize(vec).z + 1.0)')

    # TODO: This likely breaks shadows
    src = src.replace('sampler2DShadow', 'sampler2D')
    src = src.replace('shadow2DProj', 'texture2DProj')

    data['fragment'] = src


def to_130(data):
    vs_to_130(data)
    fs_to_130(data)


def to_web(data):
    to_130(data)
    vs_to_web(data)
    fs_to_web(data)


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
                description='Embed shader data into the glTF file instead of a separate file',
                default=False
            )
        }
    }
    settings = None

    def export_material(self, state, material):
        shader_data = gpu.export_shader(bpy.context.scene, material)
        if state['settings']['asset_profile'] == 'DESKTOP':
            to_130(shader_data)
        else:
            to_web(shader_data)

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

        state['output']['shaders'].append({
            'type': 35632,
            'uri': fs_uri,
            'name': material.name + 'FS',
        })
        state['output']['shaders'].append({
            'type': 35633,
            'uri': vs_uri,
            'name': material.name + 'VS',
        })

        # Handle programs
        state['output']['programs'].append({
            'attributes': [a['varname'] for a in shader_data['attributes']],
            'fragmentShader': 'shaders_{}FS'.format(material.name),
            'vertexShader': 'shaders_{}VS'.format(material.name),
            'name': material.name,
        })

        # Handle parameters/values
        values = {}
        parameters = {}
        for attribute in shader_data['attributes']:
            name = attribute['varname']
            semantic = TYPE_TO_SEMANTIC[attribute['type']]
            _type = DATATYPE_TO_GLTF_TYPE[attribute['datatype']]
            parameters[name] = {'semantic': semantic, 'type': _type}

        for uniform in shader_data['uniforms']:
            valname = TYPE_TO_NAME.get(uniform['type'], uniform['varname'])
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
                if uniform['type'] in LAMP_TYPES:
                    node = uniform['lamp'].name
                    valname = node + '_' + valname
                    semantic = TYPE_TO_SEMANTIC.get(uniform['type'], None)
                    if not semantic:
                        lamp_obj = bpy.data.objects[node]
                        value = getattr(lamp_obj.data, rnaname)
                elif uniform['type'] in MIST_TYPES:
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
                elif uniform['type'] in WORLD_TYPES:
                    world = bpy.context.scene.world
                    value = getattr(world, rnaname)
                elif uniform['type'] in MATERIAL_TYPES:
                    converter = DATATYPE_TO_CONVERTER[uniform['datatype']]
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
                parameter['value'] = DATATYPE_TO_CONVERTER[uniform['datatype']](value)
            else:
                parameter['value'] = None

            if uniform['type'] == gpu.GPU_DYNAMIC_SAMPLER_2DIMAGE:
                parameter['type'] = 35678  # SAMPLER_2D
            else:
                parameter['type'] = DATATYPE_TO_GLTF_TYPE[uniform['datatype']]
            parameters[valname] = parameter
            uniform['valname'] = valname

        # Handle techniques
        tech_name = 'techniques_' + material.name
        state['output']['techniques'].append({
            'parameters': parameters,
            'program': 'programs_' + material.name,
            'attributes': {a['varname']: a['varname'] for a in shader_data['attributes']},
            'uniforms': {u['varname']: u['valname'] for u in shader_data['uniforms']},
            'name': material.name,
        })

        return {'technique': tech_name, 'values': values, 'name': material.name}

    def export(self, state):
        state['output']['techniques'] = []
        state['output']['shaders'] = []
        state['output']['programs'] = []
        state['output']['materials'] = [
            self.export_material(state, bl_mat) for bl_mat in state['input']['materials']
        ]
