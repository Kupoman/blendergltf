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
