import re

import gpu


def vs_to_130(data):
    data['attributes'].append({'varname': 'bl_Vertex', 'type': gpu.CD_ORCO, 'datatype': gpu.GPU_DATA_3F})
    data['attributes'].append({'varname': 'bl_Normal', 'type': -1, 'datatype': gpu.GPU_DATA_3F})
    src = data['vertex']
    src = '#version 130\nin vec4 bl_Vertex;\nin vec3 bl_Normal;\nuniform mat4 bl_ModelViewMatrix;\nuniform mat4 bl_ProjectionMatrix;\nuniform mat3 bl_NormalMatrix;\n' + src
    src = re.sub(r'#ifdef USE_OPENSUBDIV([^#]*)#endif', '', src)
    src = re.sub(r'#ifndef USE_OPENSUBDIV([^#]*)#endif', r'\1', src)
    src = re.sub(r'#ifdef CLIP_WORKAROUND(.*?)#endif', '', src, 0, re.DOTALL)
    src = re.sub(r'\bvarying\b', 'out', src)
    src = re.sub(r'\bgl_(?!Position)(.*?)\b', r'bl_\1', src)

    data['vertex'] = src


def fs_to_130(data):
    src = data['fragment']
    src = '#version 130\nout vec4 frag_color;\nuniform mat4 bl_ProjectionMatrix;\nuniform mat4 bl_ModelViewMatrix;\nuniform mat4 bl_ModelViewMatrixInverse;\nuniform mat3 bl_NormalMatrix;\nuniform mat4 bl_ProjectionMatrixInverse;\n' + src
    src = re.sub(r'\bvarying\b', 'in', src)
    src = re.sub(r'\bgl_FragColor\b', 'frag_color', src)
    src = re.sub(r'\bgl_(?!FrontFacing)(.*?)\b', r'bl_\1', src)

    # Cannot support node_bsdf functions without resolving use of gl_Light
    src = re.sub(r'void node_((bsdf)|(subsurface))_.*?^}', '', src, 0, re.DOTALL|re.MULTILINE)

    data['fragment'] = src


def to_130(data):
    vs_to_130(data)
    fs_to_130(data)
