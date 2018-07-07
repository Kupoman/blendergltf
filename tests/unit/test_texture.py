def test_sampler_export(exporters, bpy_texture_default, gltf_sampler_default):
    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default


def test_sampler_export_mirror_x(exporters, bpy_texture_default, gltf_sampler_default):
    bpy_texture_default.use_mirror_x = True
    gltf_sampler_default['wrapS'] = 33648

    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default


def test_sampler_export_mipmap(exporters, bpy_texture_default, gltf_sampler_default):
    bpy_texture_default.use_mipmap = True
    gltf_sampler_default['minFilter'] = 9987
    gltf_sampler_default['magFilter'] = 9729

    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default


def test_sampler_export_mirror_y(exporters, bpy_texture_default, gltf_sampler_default):
    bpy_texture_default.use_mirror_y = True
    gltf_sampler_default['wrapT'] = 33648

    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default


def test_sampler_export_clip(exporters, bpy_texture_default, gltf_sampler_default):
    bpy_texture_default.extension = 'CLIP'
    gltf_sampler_default['wrapS'] = 33071
    gltf_sampler_default['wrapT'] = 33071
    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default

    bpy_texture_default.extension = 'CLIP_CUBE'
    output = exporters.TextureExporter.export_sampler(bpy_texture_default)
    assert output == gltf_sampler_default


def test_texture_export(exporters, state, bpy_texture_default, gltf_texture_default):
    output = exporters.TextureExporter.export(state, bpy_texture_default)

    for ref in state['references']:
        ref.source[ref.prop] = ref.blender_name

    assert output == gltf_texture_default


def test_texture_check(exporters, state, bpy_texture_default):
    assert exporters.TextureExporter.check(state, bpy_texture_default)


def test_texture_check_type(exporters, state, bpy_texture_default):
    bpy_texture_default.__class__ = int
    assert exporters.TextureExporter.check(state, bpy_texture_default) is False


def test_texture_check_image(exporters, state, bpy_texture_default):
    bpy_texture_default.image = None
    assert exporters.TextureExporter.check(state, bpy_texture_default) is False


def test_texture_check_channels(exporters, state, bpy_texture_default):
    bpy_texture_default.image.channels = 0
    assert exporters.TextureExporter.check(state, bpy_texture_default) is False
