def test_get_bone_name(blendergltf, mocker):
    bone = mocker.MagicMock()
    bone.name = 'Bone'

    armature = mocker.MagicMock()
    armature.name = 'Armature'

    bone.id_data = armature

    bone_name = 'Armature_Bone'

    assert blendergltf.get_bone_name(bone) == bone_name
