from .base import BaseExporter
from .common import (
    Reference,
)


class SceneExporter(BaseExporter):
    gltf_key = 'scenes'
    blender_key = 'scenes'

    @classmethod
    def export(cls, state, blender_data):
        bg_color = blender_data.world.horizon_color[:] if blender_data.world else [0.05]*3
        result = {
            'extras': {
                'background_color': bg_color,
                'frames_per_second': blender_data.render.fps,
            },
            'name': blender_data.name,
        }

        if blender_data.camera and blender_data.camera.data in state['input']['cameras']:
            result['extras']['active_camera'] = Reference(
                'cameras',
                blender_data.camera.name,
                result['extras'],
                'active_camera'
            )
            state['references'].append(result['extras']['active_camera'])

        extras = BaseExporter.get_custom_properties(blender_data)
        if extras:
            result['extras'].update(BaseExporter.get_custom_properties(blender_data))

        result['nodes'] = [
            Reference('objects', ob.name, None, None)
            for ob in blender_data.objects
            if ob in state['input']['objects'] and ob.parent is None and ob.is_visible(blender_data)
        ]
        for i, ref in enumerate(result['nodes']):
            ref.source = result['nodes']
            ref.prop = i
        state['references'].extend(result['nodes'])

        hidden_nodes = [
            Reference('objects', ob.name, None, None)
            for ob in blender_data.objects
            if ob in state['input']['objects'] and not ob.is_visible(blender_data)
        ]

        if hidden_nodes:
            result['extras']['hidden_nodes'] = hidden_nodes
            for i, ref in enumerate(hidden_nodes):
                ref.source = result['extras']['hidden_nodes']
                ref.prop = i
            state['references'].extend(result['extras']['hidden_nodes'])

        return result
