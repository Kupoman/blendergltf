from distutils.version import StrictVersion as Version

import bpy

from .base import BaseExporter
from .common import (
    Reference,
    SimpleID,
)


# Texture formats
GL_ALPHA = 6406
GL_RGB = 6407
GL_RGBA = 6408
GL_LUMINANCE = 6409
GL_LUMINANCE_ALPHA = 6410

# Texture filtering
GL_NEAREST = 9728
GL_LINEAR = 9729
GL_LINEAR_MIPMAP_LINEAR = 9987

# Texture wrapping
GL_CLAMP_TO_EDGE = 33071
GL_MIRRORED_REPEAT = 33648
GL_REPEAT = 10497

# sRGB texture formats (not actually part of WebGL 1.0 or glTF 1.0)
GL_SRGB = 0x8C40
GL_SRGB_ALPHA = 0x8C42


class TextureExporter(BaseExporter):
    gltf_key = 'textures'
    blender_key = 'textures'

    @classmethod
    def check(cls, state, blender_data):
        errors = []
        if not isinstance(blender_data, bpy.types.ImageTexture):
            errors.append('is not an ImageTexture')
        elif blender_data.image is None:
            errors.append('has no image reference')
        elif blender_data.image.channels not in [3, 4]:
            errors.append(
                'points to {}-channel image (must be 3 or 4)'
                .format(blender_data.image.channels)
            )

        if errors:
            err_list = '\n\t'.join(errors)
            print(
                'Unable to export texture {} due to the following errors:\n\t{}'
                .format(blender_data.name, err_list)
            )
            return False

        return True

    @classmethod
    def export_sampler(cls, blender_data):
        gltf_sampler = {
            'name': blender_data.name,
        }

        # Handle wrapS and wrapT
        if blender_data.extension in ('REPEAT', 'CHECKER', 'EXTEND'):
            if blender_data.use_mirror_x:
                gltf_sampler['wrapS'] = GL_MIRRORED_REPEAT
            else:
                gltf_sampler['wrapS'] = GL_REPEAT

            if blender_data.use_mirror_y:
                gltf_sampler['wrapT'] = GL_MIRRORED_REPEAT
            else:
                gltf_sampler['wrapT'] = GL_REPEAT
        elif blender_data.extension in ('CLIP', 'CLIP_CUBE'):
            gltf_sampler['wrapS'] = GL_CLAMP_TO_EDGE
            gltf_sampler['wrapT'] = GL_CLAMP_TO_EDGE
        else:
            print('Warning: Unknown texture extension option:', blender_data.extension)

        # Handle minFilter and magFilter
        if blender_data.use_mipmap:
            gltf_sampler['minFilter'] = GL_LINEAR_MIPMAP_LINEAR
            gltf_sampler['magFilter'] = GL_LINEAR
        else:
            gltf_sampler['minFilter'] = GL_NEAREST
            gltf_sampler['magFilter'] = GL_NEAREST

        return gltf_sampler

    @classmethod
    def export(cls, state, blender_data):
        gltf_texture = {
            'name': blender_data.name,
        }

        gltf_sampler = cls.export_sampler(blender_data)
        state['input']['samplers'].append(SimpleID(blender_data.name))
        state['samplers'].append(gltf_sampler)

        gltf_texture['sampler'] = Reference('samplers', blender_data.name, gltf_texture, 'sampler')
        state['references'].append(gltf_texture['sampler'])

        gltf_texture['source'] = Reference(
            'images',
            blender_data.image.name,
            gltf_texture,
            'source'
        )
        state['references'].append(gltf_texture['source'])

        if state['version'] < Version('2.0'):
            tformat = None
            channels = blender_data.image.channels
            image_is_srgb = blender_data.image.colorspace_settings.name == 'sRGB'
            use_srgb = state['settings']['images_allow_srgb'] and image_is_srgb

            if channels == 3:
                if use_srgb:
                    tformat = GL_SRGB
                else:
                    tformat = GL_RGB
            elif channels == 4:
                if use_srgb:
                    tformat = GL_SRGB_ALPHA
                else:
                    tformat = GL_RGBA

            gltf_texture['format'] = gltf_texture['internalFormat'] = tformat

        return gltf_texture
