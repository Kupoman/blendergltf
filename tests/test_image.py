def test_image_export(exporters, state, bpy_image_default, gltf_image_default):
    state['settings']['images_data_storage'] = 'bad'
    output = exporters.ImageExporter.export(state, bpy_image_default)
    assert output == gltf_image_default


def test_image_to_data_uri(exporters, bpy_image_default):
    image_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\r'
        b'IHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x08'
        b'IDATx\xda\x03\x00\x00\x00\x00\x01o\xdd\xc9\x91\x00\x00\x00\x00'
        b'IEND\xaeB`\x82'
    )

    assert exporters.ImageExporter.image_to_data_uri(bpy_image_default) == image_data


def test_image_check(exporters, state, bpy_image_default):
    assert exporters.ImageExporter.check(state, bpy_image_default)


def test_image_default(exporters, state, bpy_image_default):
    assert exporters.ImageExporter.default(state, bpy_image_default) == {
        'name': 'Image',
        'uri': '',
    }


def test_image_check_0_x(exporters, state, bpy_image_default):
    bpy_image_default.size = [0, 1]
    assert exporters.ImageExporter.check(state, bpy_image_default) is not True


def test_image_check_0_y(exporters, state, bpy_image_default):
    bpy_image_default.size = [1, 0]
    assert exporters.ImageExporter.check(state, bpy_image_default) is not True


def test_image_check_type(exporters, state, bpy_image_default):
    bpy_image_default.type = 'NOT_IMAGE'
    assert exporters.ImageExporter.check(state, bpy_image_default) is not True
