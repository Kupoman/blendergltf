from distutils.version import StrictVersion as Version

import pytest


# pylint: disable=redefined-outer-name

class ImageTexture:
    pass


def update_sys(mocker):
    import sys

    bpy = mocker.MagicMock()
    bpy.types.ImageTexture = ImageTexture

    sys.modules['bpy'] = bpy
    sys.modules['idprop'] = mocker.MagicMock()
    sys.modules['mathutils'] = mocker.MagicMock()


@pytest.fixture
def blendergltf(mocker):
    update_sys(mocker)
    import blendergltf.blendergltf as _blendergltf
    return _blendergltf


@pytest.fixture
def exporters(mocker):
    update_sys(mocker)
    import blendergltf.exporters as exporters
    return exporters


@pytest.fixture
def state(blendergltf):
    scene_delta = {
        'actions': [],
        'cameras': [],
        'lamps': [],
        'images': [],
        'materials': [],
        'meshes': [],
        'objects': [],
        'scenes': [],
        'textures': [],
    }

    _state = blendergltf.initialize_state()

    def _decompose(_):
        return (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
            (1.0, 1.0, 1.0),
        )

    _state['input'].update({key: list(value) for key, value in scene_delta.items()})
    _state['animation_dt'] = 1 / 24
    _state['aspect_ratio'] = 1920 / 1080
    _state['decompose_fn'] = _decompose
    _state['decompose_mesh_fn'] = _decompose

    return _state


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
        'name': 'Camera',
        'perspective': {
            'aspectRatio': 1.703595982340029,
            'yfov': 0.5033799409866333,
            'zfar': 100.0,
            'znear': 0.10000000149011612
        },
        'type': 'perspective'
    }


@pytest.fixture
def bpy_image_default(mocker):
    image = mocker.MagicMock()

    image.name = 'Image'
    image.type = 'IMAGE'
    image.channels = 4
    image.packed_file = None
    image.pixels = [0.0, 0.0, 0.0, 1.0]
    image.filepath = '../filepath.png'

    return image


@pytest.fixture
def gltf_image_default():
    return {
        'name': 'Image',
    }


@pytest.fixture
def bpy_material_default(mocker):
    material = mocker.MagicMock()

    material.name = 'Material'

    material.pbr_export_settings = mocker.MagicMock()
    material.pbr_export_settings.alpha_mode = 'OPAQUE'
    material.pbr_export_settings.alpha_cutoff = 0.5
    material.pbr_export_settings.base_color_factor = [
        0.64000004529953,
        0.64000004529953,
        0.64000004529953,
        1.0
    ]
    material.pbr_export_settings.metallic_factor = 0.0
    material.pbr_export_settings.roughness_factor = 1.0
    material.pbr_export_settings.emissive_factor = [0.0, 0.0, 0.0]

    return material


@pytest.fixture
def gltf_material_default():
    return {
        'alphaMode': 'OPAQUE',
        'doubleSided': False,
        'emissiveFactor': [
            0.0,
            0.0,
            0.0
        ],
        'name': 'Material',
        'pbrMetallicRoughness': {
            'baseColorFactor': [
                0.64000004529953,
                0.64000004529953,
                0.64000004529953,
                1.0
            ],
            'metallicFactor': 0.0,
            'roughnessFactor': 1.0
        }
    }


@pytest.fixture
def bpy_mesh_default(mocker):
    mesh = mocker.MagicMock()

    mesh.name = 'Mesh'

    return mesh


@pytest.fixture
def gltf_mesh_default():
    return {
        'name': 'Mesh',
        'primitives': [],
    }


@pytest.fixture
def bpy_object_default(mocker):
    obj = mocker.MagicMock()

    obj.name = 'Object'
    obj.parent = None
    obj.type = 'EMPTY'
    obj.children = []
    obj.dupli_group = None

    return obj


@pytest.fixture
def gltf_node_default():
    return {
        'name': 'Object',
        'translation': (0.0, 0.0, 0.0),
        'rotation': (0.0, 0.0, 0.0, 1.0),
        'scale': (1.0, 1.0, 1.0),
    }


@pytest.fixture
def bpy_scene_default(mocker):
    scene = mocker.MagicMock()

    scene.name = 'Scene'

    scene.world = mocker.MagicMock()
    scene.world.horizon_color = [0.05087608844041824, 0.05087608844041824, 0.05087608844041824]

    scene.render = mocker.MagicMock()
    scene.render.fps = 24

    return scene


@pytest.fixture
def gltf_scene_default():
    return {
        "extras": {
            "background_color": [
                0.05087608844041824,
                0.05087608844041824,
                0.05087608844041824
            ],
            "frames_per_second": 24
        },
        "name": "Scene",
        "nodes": []
    }


@pytest.fixture
def bpy_texture_default(bpy_image_default, mocker):
    texture = mocker.MagicMock()
    texture.__class__ = ImageTexture

    texture.name = 'Texture'

    texture.extension = 'REPEAT'
    texture.use_mipmap = False
    texture.use_mirror_x = False
    texture.use_mirror_y = False

    texture.image = bpy_image_default

    return texture


@pytest.fixture
def gltf_sampler_default():
    return {
        'name': 'Texture',
        'wrapS': 10497,
        'wrapT': 10497,
        'minFilter': 9728,
        'magFilter': 9728
    }


@pytest.fixture
def gltf_texture_default():
    return {
        'name': 'Texture',
        'sampler': 'Texture',
        'source': 'Image',
    }
