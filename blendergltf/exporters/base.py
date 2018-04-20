import json


def _is_serializable(value):
    try:
        json.dumps(value)
        return True
    except TypeError:
        return False


_IGNORED_CUSTOM_PROPS = [
    '_RNA_UI',
    'cycles',
    'cycles_visibility',
]


# pylint: disable=unused-argument
class BaseExporter:
    gltf_key = ''
    blender_key = ''

    @classmethod
    def get_custom_properties(cls, blender_data):
        custom_props = {
            key: value.to_list() if hasattr(value, 'to_list') else value
            for key, value in blender_data.items()
            if key not in _IGNORED_CUSTOM_PROPS
        }

        custom_props = {
            key: value for key, value in custom_props.items()
            if _is_serializable(value)
        }

        return custom_props

    @classmethod
    def check(cls, state, blender_data):
        return True

    @classmethod
    def default(cls, state, blender_data):
        return {
            'name': blender_data.name
        }

    @classmethod
    def export(cls, state, blender_data):
        return {}
