from distutils.version import StrictVersion as Version

from ..blendergltf import Reference
from ..exporters import BaseExporter


def export_light(light):
    def calc_att():
        constant_factor = 1
        linear_factor = 0
        quad_factor = 0

        if light.falloff_type == 'INVERSE_LINEAR':
            linear_factor = 1 / light.distance
        elif light.falloff_type == 'INVERSE_SQUARE':
            quad_factor = 1 / light.distance
        elif light.falloff_type == 'LINEAR_QUADRATIC_WEIGHTED':
            linear_factor = light.linear_attenuation * (1 / light.distance)
            quad_factor = light.quadratic_attenuation * (1 / (light.distance * light.distance))
        elif light.falloff_type == 'INVERSE_COEFFICIENTS':
            constant_factor = light.constant_coefficient
            linear_factor = light.linear_coefficient * (1 / light.distance)
            quad_factor = light.quadratic_coefficient * (1 / (light.distance * light.distance))

        return constant_factor, linear_factor, quad_factor

    gltf_light = {}
    if light.type == 'SUN':
        gltf_light = {
            'directional': {
                'color': (light.color * light.energy)[:],
            },
            'type': 'directional',
        }
    elif light.type == 'POINT':
        constant_factor, linear_factor, quad_factor = calc_att()
        gltf_light = {
            'point': {
                'color': (light.color * light.energy)[:],

                'constantAttenuation': constant_factor,
                'linearAttenuation': linear_factor,
                'quadraticAttenuation': quad_factor,
            },
            'type': 'point',
        }
    elif light.type == 'SPOT':
        constant_factor, linear_factor, quad_factor = calc_att()
        gltf_light = {
            'spot': {
                'color': (light.color * light.energy)[:],

                'fallOffAngle': light.spot_size,
                'fallOffExponent': 128.0 * light.spot_blend,
                'constantAttenuation': constant_factor,
                'linearAttenuation': linear_factor,
                'quadraticAttenuation': quad_factor,
            },
            'type': 'spot',
        }
    else:
        print("Unsupported lamp type on {}: {}".format(light.name, light.type))
        gltf_light = {'type': 'unsupported'}

    gltf_light['name'] = light.name

    extras = BaseExporter.get_custom_properties(light)
    if extras:
        gltf_light['extras'] = extras

    return gltf_light


def export_lights(state, extension_name):
    # Export lights
    state['output']['extensions'] = state['output'].get('extensions', {})
    state['output']['extensions'][extension_name] = {
        'lights': [export_light(lamp) for lamp in state['input'].get('lamps', [])]
    }

    # Add light references to nodes
    obj_pairs = [
        (obj, state['output']['nodes'][state['refmap'][('objects', obj.name)]])
        for obj in state['input']['objects']
    ]

    for obj, node in obj_pairs:
        if getattr(obj, 'type', '') == 'LAMP':
            node['extensions'] = node.get('extensions', {})
            ext = node['extensions'][extension_name] = {}
            ext['light'] = Reference('lamps', obj.data.name, ext, 'light')
            state['references'].append(ext['light'])

    # Convert light list to dictionary for glTF 1.0
    if state['version'] < Version('2.0'):
        extension = state['output']['extensions'][extension_name]
        extension['lights'] = {
            'lights_' + light['name']: light for light in extension['lights']
        }
