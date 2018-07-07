def test_get_custom_properties(exporters, mocker):
    blender_data = mocker.MagicMock()
    vector = mocker.MagicMock()
    vector.to_list.return_value = [0.0, 0.0, 1.0]
    blender_data.items.return_value = [
        ['str', 'spam'],
        ['float', 1.0],
        ['int', 42],
        ['bool', False],
        ['vector', vector],
    ]
    assert exporters.BaseExporter.get_custom_properties(blender_data) == {
        'str': 'spam',
        'float': 1.0,
        'int': 42,
        'bool': False,
        'vector': [0.0, 0.0, 1.0]
    }


def test_ignore_properties(exporters, mocker):
    blender_data = mocker.MagicMock()
    blender_data.items.return_value = [
        ['_RNA_UI', None],
        ['cycles', None],
        ['cycles_visibility', None],
        ['str', 'remains'],
    ]
    assert exporters.BaseExporter.get_custom_properties(blender_data) == {
        'str': 'remains',
    }


def test_invalid_properties(exporters, mocker):
    blender_data = mocker.MagicMock()
    blender_data.items.return_value = [
        ['unserializable', set()],
        ['str', 'remains'],
    ]
    assert exporters.BaseExporter.get_custom_properties(blender_data) == {
        'str': 'remains',
    }


def test_check(exporters):
    assert exporters.BaseExporter.check(None, None)


def test_default(exporters, mocker):
    blender_data = mocker.MagicMock()
    blender_data.name = 'Name'
    assert exporters.BaseExporter.default(None, blender_data) == {'name': 'Name'}


def test_export(exporters):
    assert exporters.BaseExporter.export(None, None) == {}
