import pytest


@pytest.fixture
def blendergltf(mocker):
    # pylint: disable=protected-access
    import sys
    sys.modules['bpy'] = mocker.MagicMock()
    sys.modules['idprop'] = mocker.MagicMock()
    sys.modules['mathutils'] = mocker.MagicMock()

    import blendergltf as _blendergltf
    mocker.patch.object(_blendergltf, '_get_custom_properties')
    _blendergltf._get_custom_properties.return_value = {}
    return _blendergltf


@pytest.fixture
def state(mocker):
    return mocker.MagicMock()


@pytest.fixture
def bpy_camera_default(mocker):
    camera = mocker.MagicMock()

    camera.name = 'Camera'
    camera.type = 'PERSP'
    camera.angle_x = 0.8575560450553894
    camera.angle_y = 0.5033799409866333
    camera.clip_end = 100.0
    camera.clip_start = 0.10000000149011612
    camera.ortho_scale = 7.314285755157471

    return camera


@pytest.fixture
def gltf_camera_default():
    return {
        "name": "Camera",
        "perspective": {
            "aspectRatio": 1.703595982340029,
            "yfov": 0.5033799409866333,
            "zfar": 100.0,
            "znear": 0.10000000149011612
        },
        "type": "perspective"
    }
