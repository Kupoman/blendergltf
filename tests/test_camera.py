def test_camera_default(blendergltf, state, bpy_camera_default, gltf_camera_default):
    output = blendergltf.export_camera(state, bpy_camera_default)
    assert output == gltf_camera_default


def test_camera_ortho(blendergltf, state, bpy_camera_default):
    bpy_camera_default.type = 'ORTHO'

    output = blendergltf.export_camera(state, bpy_camera_default)
    assert output == {
        "name": "Camera",
        "orthographic": {
            "xmag": 6.501587337917751,
            "ymag": 3.6571428775787354,
            "zfar": 100.0,
            "znear": 0.10000000149011612
        },
        "type": "orthographic"
    }


def test_camera_custom_props(blendergltf, state, bpy_camera_default):
    # pylint: disable=protected-access
    blendergltf._get_custom_properties.return_value = {'foo': 'bar'}
    output = blendergltf.export_camera(state, bpy_camera_default)
    assert output['extras'] == {'foo': 'bar'}


def test_camera_angle_y_zero(blendergltf, state, bpy_camera_default, gltf_camera_default):
    bpy_camera_default.angle_y = 0
    gltf_camera_default['perspective']['aspectRatio'] = 857556.0450553894
    gltf_camera_default['perspective']['yfov'] = 1e-6

    output = blendergltf.export_camera(state, bpy_camera_default)
    assert output == gltf_camera_default
