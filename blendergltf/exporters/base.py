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
        return {
            k: v.to_list() if hasattr(v, 'to_list') else v for k, v in blender_data.items()
            if k not in _IGNORED_CUSTOM_PROPS and _is_serializable(v)
        }

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
