def test_mesh_export(exporters, state, bpy_mesh_default, gltf_mesh_default):
    output = exporters.MeshExporter.export(state, bpy_mesh_default)
    assert output == gltf_mesh_default


def test_mesh_export_primitive(blendergltf, exporters, state):
    output = exporters.MeshExporter.export_primitive(
        state,
        blendergltf.Buffer('test'),
        None,
        [0, 1, 2],
        blendergltf.Buffer.UNSIGNED_INT,
        'attrs',
        None,
    )

    for ref in state['references']:
        ref.source[ref.prop] = ref.blender_name

    assert output == {
        'attributes': 'attrs',
        'mode': 4,
        'indices': 'accessor_buffer_test_0',
    }


def test_mesh_export_primitive_mat(blendergltf, exporters, state):
    output = exporters.MeshExporter.export_primitive(
        state,
        blendergltf.Buffer('test'),
        'Material',
        [0, 1, 2],
        blendergltf.Buffer.UNSIGNED_INT,
        'attrs',
        None,
    )

    for ref in state['references']:
        print(ref.blender_name)
        ref.source[ref.prop] = ref.blender_name

    assert output == {
        'attributes': 'attrs',
        'mode': 4,
        'indices': 'accessor_buffer_test_0',
        'material': 'Material'
    }


def test_mesh_export_prim_targets(blendergltf, exporters, state):
    output = exporters.MeshExporter.export_primitive(
        state,
        blendergltf.Buffer('test'),
        None,
        [0, 1, 2],
        blendergltf.Buffer.UNSIGNED_INT,
        'attrs',
        ['one', 'two'],
    )

    for ref in state['references']:
        ref.source[ref.prop] = ref.blender_name

    assert output == {
        'attributes': 'attrs',
        'mode': 4,
        'indices': 'accessor_buffer_test_0',
        'targets': ['one', 'two']
    }
