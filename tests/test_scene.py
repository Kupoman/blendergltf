def test_scene_default(blendergltf, state, bpy_scene_default, gltf_scene_default):
    output = blendergltf.export_scene(state, bpy_scene_default)
    assert output == gltf_scene_default


def test_scene_camera(
        blendergltf,
        state,
        bpy_scene_default,
        gltf_scene_default,
        bpy_camera_default
):
    bpy_scene_default.camera = bpy_camera_default
    bpy_scene_default.camera.data = bpy_camera_default.name

    gltf_scene_default['extras']['active_camera'] = bpy_camera_default.name

    state['input']['cameras'].append(bpy_camera_default.name)
    output = blendergltf.export_scene(state, bpy_scene_default)

    ref_names = [ref.blender_name for ref in state['references']]
    assert set(ref_names) == set((bpy_scene_default.camera.name,))
    for ref in state['references']:
        ref.source[ref.prop] = ref.blender_name

    assert output == gltf_scene_default


def test_scene_custom_props(blendergltf, state, bpy_scene_default):
    bpy_scene_default.items.return_value = [['foo', 'bar']]
    output = blendergltf.export_scene(state, bpy_scene_default)
    assert ('foo', 'bar') in output['extras'].items()
