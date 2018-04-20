import base64
import os
import struct
import zlib

import bpy

from .base import BaseExporter
from .common import (
    Buffer,
    Reference,
    SimpleID,
)


EXT_MAP = {'BMP': 'bmp', 'JPEG': 'jpg', 'PNG': 'png', 'TARGA': 'tga'}


class ImageExporter(BaseExporter):
    gltf_key = 'images'
    blender_key = 'images'

    @classmethod
    def check(cls, state, blender_data):
        errors = []
        if blender_data.size[0] == 0:
            errors.append('x dimension is 0')
        if blender_data.size[1] == 0:
            errors.append('y dimension is 0')
        if blender_data.type != 'IMAGE':
            errors.append('not an image {}'.format(blender_data.type))

        if errors:
            err_list = '\n\t'.join(errors)
            print(
                'Unable to export image {} due to the following errors:\n\t{}'
                .format(blender_data.name, err_list)
            )
            return False

        return True

    @classmethod
    def default(cls, state, blender_data):
        return {
            'name': blender_data.name,
            'uri': ''
        }

    @classmethod
    def image_to_data_uri(cls, image):
        width = image.size[0]
        height = image.size[1]
        buf = bytearray([int(p * 255) for p in image.pixels])

        # reverse the vertical line order and add null bytes at the start
        width_byte_4 = width * 4
        raw_data = b''.join(b'\x00' + buf[span:span + width_byte_4]
                            for span in range((height - 1) * width_byte_4, -1, - width_byte_4))

        def png_pack(png_tag, data):
            chunk_head = png_tag + data
            return (struct.pack("!I", len(data)) +
                    chunk_head +
                    struct.pack("!I", 0xFFFFFFFF & zlib.crc32(chunk_head)))

        png_bytes = b''.join([
            b'\x89PNG\r\n\x1a\n',
            png_pack(b'IHDR', struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)),
            png_pack(b'IDAT', zlib.compress(raw_data, 9)),
            png_pack(b'IEND', b'')])

        return png_bytes

    @classmethod
    def export(cls, state, blender_data):
        path = ''
        data = None

        gltf = {'name': blender_data.name}

        storage_setting = state['settings']['images_data_storage']
        image_packed = blender_data.packed_file is not None
        if image_packed and storage_setting in ['COPY', 'REFERENCE']:
            if blender_data.file_format in EXT_MAP:
                # save the file to the output directory
                gltf['uri'] = '.'.join([blender_data.name, EXT_MAP[blender_data.file_format]])
                temp = blender_data.filepath
                blender_data.filepath = os.path.join(
                    state['settings']['gltf_output_dir'],
                    gltf['uri']
                )
                blender_data.save()
                with open(bpy.path.abspath(blender_data.filepath), 'rb') as fin:
                    data = fin.read()
                blender_data.filepath = temp
            else:
                # convert to png and save
                gltf['uri'] = '.'.join([blender_data.name, 'png'])
                data = cls.image_to_data_uri(blender_data)
            path = os.path.join(state['settings']['gltf_output_dir'], gltf['uri'])

        elif storage_setting == 'COPY':
            with open(bpy.path.abspath(blender_data.filepath), 'rb') as fin:
                data = fin.read()
            gltf['uri'] = bpy.path.basename(blender_data.filepath)
            path = os.path.join(state['settings']['gltf_output_dir'], gltf['uri'])
        elif storage_setting == 'REFERENCE':
            gltf['uri'] = blender_data.filepath.replace('//', '')
        elif storage_setting == 'EMBED':
            png_bytes = cls.image_to_data_uri(blender_data)
            gltf['mimeType'] = 'image/png'
            if state['settings']['gltf_export_binary']:
                buf = Buffer(blender_data.name)
                view_key = buf.add_view(len(png_bytes), 0, None)
                view = buf.buffer_views[view_key]
                view['data'] = png_bytes

                pad = 4 - len(png_bytes) % 4
                if pad not in [0, 4]:
                    buf.add_view(pad, 0, None)

                gltf['bufferView'] = Reference('bufferViews', view_key, gltf, 'bufferView')
                state['references'].append(gltf['bufferView'])

                state['buffers'].append(buf)
                state['input']['buffers'].append(SimpleID('buffer_' + blender_data.name))
            else:
                gltf['uri'] = 'data:image/png;base64,' + base64.b64encode(png_bytes).decode()
        else:
            print(
                'Encountered unknown option ({}) for images_data_storage setting'
                .format(storage_setting)
            )

        if path:
            state['files'][path] = data

        return gltf
