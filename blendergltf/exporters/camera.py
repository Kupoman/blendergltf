from .base import BaseExporter


class CameraExporter(BaseExporter):
    gltf_key = 'cameras'
    blender_key = 'cameras'

    @classmethod
    def export(cls, state, blender_data):
        camera_gltf = {}
        if blender_data.type == 'ORTHO':
            xmag = 0.5 * blender_data.ortho_scale
            ymag = xmag * state['aspect_ratio']
            camera_gltf = {
                'orthographic': {
                    'xmag': ymag,
                    'ymag': xmag,
                    'zfar': blender_data.clip_end,
                    'znear': blender_data.clip_start,
                },
                'type': 'orthographic',
            }
        else:
            angle_y = blender_data.angle_y if blender_data.angle_y != 0.0 else 1e-6
            camera_gltf = {
                'perspective': {
                    'aspectRatio': blender_data.angle_x / angle_y,
                    'yfov': angle_y,
                    'zfar': blender_data.clip_end,
                    'znear': blender_data.clip_start,
                },
                'type': 'perspective',
            }
        camera_gltf['name'] = blender_data.name
        extras = cls.get_custom_properties(blender_data)
        if extras:
            camera_gltf['extras'] = extras
        return camera_gltf
