import importlib

from . import _lights_common

if '__IMPORTED__' in locals():
    importlib.reload(locals()['_lights_common'])
else:
    __IMPORTED__ = True


class KhrLights:
    ext_meta = {
        'name': 'KHR_lights',
        'url': (
            'https://github.com/andreasplesch/glTF/blob/ec6f61d73bcd58d59d4a4ea9ac009f973c693c5f/'
            'extensions/Khronos/KHR_lights/README.md'
        ),
        'isDraft': True,
    }

    def export(self, state):
        state['extensions_used'].append('KHR_lights')
        _lights_common.export_lights(state, 'KHR_lights')
