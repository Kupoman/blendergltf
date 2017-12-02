from distutils.version import StrictVersion as Version


def test_material_default(blendergltf, state, bpy_material_default, gltf_material_default):
    output = blendergltf.export_material(state, bpy_material_default)
    assert output == gltf_material_default


def test_material_1_0(blendergltf, state, bpy_material_default):
    state['version'] = Version('1.0')
    output = blendergltf.export_material(state, bpy_material_default)
    assert output == {'name': 'Material'}


def test_material_no_pbr(blendergltf, state, bpy_material_default):
    del bpy_material_default.pbr_export_settings
    output = blendergltf.export_material(state, bpy_material_default)
    assert output == {'name': 'Material'}


def test_material_textured(mocker, blendergltf, state, bpy_material_default, gltf_material_default):
    pbr = bpy_material_default.pbr_export_settings
    pbr.base_color_texture = 'base_color'
    pbr.base_color_text_index = 0
    pbr.metal_roughness_texture = 'metal_roughness'
    pbr.metal_rough_text_index = 1
    pbr.emissive_texture = 'emissive'
    pbr.emissive_text_index = 2
    pbr.normal_texture = 'normal'
    pbr.normal_text_index = 3
    pbr.occlusion_texture = 'occlusion'
    pbr.occlusion_text_index = 4

    gltf_material_default['pbrMetallicRoughness']['baseColorTexture'] = {
        'texCoord': 0,
        'index': 'base_color'
    }
    gltf_material_default['pbrMetallicRoughness']['metallicRoughnessTexture'] = {
        'texCoord': 1,
        'index': 'metal_roughness'
    }
    gltf_material_default['emissiveTexture'] = {
        'texCoord': 2,
        'index': 'emissive'
    }
    gltf_material_default['normalTexture'] = {
        'texCoord': 3,
        'index': 'normal'
    }
    gltf_material_default['occlusionTexture'] = {
        'texCoord': 4,
        'index': 'occlusion'
    }

    texture_names = ('base_color', 'metal_roughness', 'emissive', 'normal', 'occlusion')
    state['input']['textures'] = []
    for name in texture_names:
        texture = mocker.MagicMock()
        texture.name = name
        state['input']['textures'].append(texture)
    output = blendergltf.export_material(state, bpy_material_default)

    ref_names = [ref.blender_name for ref in state['references']]
    assert set(ref_names) == set(texture_names)
    for ref in state['references']:
        assert ref.blender_type == 'textures'
        ref.source[ref.prop] = ref.blender_name

    assert output == gltf_material_default
