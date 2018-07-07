def test_node_default(exporters, state, bpy_object_default, gltf_node_default):
    output = exporters.NodeExporter.export(state, bpy_object_default)
    assert output == gltf_node_default


def test_node_camera(exporters, state, bpy_object_default, gltf_node_default, bpy_camera_default):
    bpy_object_default.type = 'CAMERA'
    bpy_object_default.data = bpy_camera_default

    gltf_node_default['camera'] = 'Camera'

    output = exporters.NodeExporter.export(state, bpy_object_default)
    for ref in state['references']:
        ref.source[ref.prop] = ref.blender_name

    assert output == gltf_node_default


def test_node_bone_parent(exporters, mocker, state, bpy_object_default):
    bone = mocker.MagicMock()
    bone.name = 'Bone'
    bone.id_data.name = 'Armature'

    bpy_object_default.parent = mocker.MagicMock()
    bpy_object_default.parent.data.bones = {'Bone': bone}
    bpy_object_default.parent_bone = 'Bone'

    exporters.NodeExporter.export(state, bpy_object_default)

    assert state['bone_children']['Armature_Bone'] == ['Object']
