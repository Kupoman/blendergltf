import collections
import bpy
import os
import base64
from .Accessor import Accessor

class Buffer:
    ARRAY_BUFFER = 34962
    ELEMENT_ARRAY_BUFFER = 34963

    BYTE = 5120
    UNSIGNED_BYTE = 5121
    SHORT = 5122
    UNSIGNED_SHORT = 5123
    INT = 5124
    UNSIGNED_INT = 5125

    FLOAT = 5126

    MAT4 = 'MAT4'
    VEC4 = 'VEC4'
    VEC3 = 'VEC3'
    VEC2 = 'VEC2'
    SCALAR = 'SCALAR'


    __slots__ = (
        "name",
        "buffer_type",
        "bytelength",
        "buffer_views",
        "accessors",
        )

    def __init__(self, name):
        self.name = 'buffer_{}'.format(name)
        self.buffer_type = 'arraybuffer'
        self.bytelength = 0
        self.buffer_views = collections.OrderedDict()
        self.accessors = {}

    def export_buffer(self, state):
        data = bytearray()
        for view in self.buffer_views.values():
            data.extend(view['data'])

        if state['settings']['buffers_embed_data']:
            uri = 'data:text/plain;base64,' + base64.b64encode(data).decode('ascii')
        else:
            uri = bpy.path.clean_name(self.name) + '.bin'
            with open(os.path.join(state['settings']['gltf_output_dir'], uri), 'wb') as fout:
                fout.write(data)

        return {
            'byteLength': self.bytelength,
            'type': self.buffer_type,
            'uri': uri,
        }

    def add_view(self, bytelength, target):
        buffer_name = 'bufferView_{}_{}'.format(self.name, len(self.buffer_views))
        self.buffer_views[buffer_name] = {
            'data': bytearray(bytelength),
            'target': target,
            'bytelength': bytelength,
            'byteoffset': self.bytelength,
        }
        self.bytelength += bytelength
        return buffer_name

    def export_views(self):
        gltf = {}

        for key, value in self.buffer_views.items():
            gltf[key] = {
                'buffer': self.name,
                'byteLength': value['bytelength'],
                'byteOffset': value['byteoffset'],
            }

            if value['target'] is not None:
                gltf[key]['target'] = value['target']

        return gltf

    def get_buffer_data(self, buffer_view):
        return self.buffer_views[buffer_view]['data']

    def add_accessor(self,
                     buffer_view,
                     byte_offset,
                     byte_stride,
                     component_type,
                     count,
                     data_type):

        accessor_name = 'accessor_{}_{}'.format(self.name, len(self.accessors))
        self.accessors[accessor_name] = Accessor(
            accessor_name,
            self,
            buffer_view,
            byte_offset,
            byte_stride,
            component_type,
            count,
            data_type
        )
        return self.accessors[accessor_name]

    def export_accessors(self):
        gltf = {}

        for key, value in self.accessors.items():
            # Do not export an empty accessor
            if value.count == 0:
                continue

            gltf[key] = {
                'bufferView': value.buffer_view,
                'byteOffset': value.byte_offset,
                'byteStride': value.byte_stride,
                'componentType': value.component_type,
                'count': value.count,
                'min': value.min[:value.type_size],
                'max': value.max[:value.type_size],
                'type': value.data_type,
            }

        return gltf

    def __add__(self, other):
        # Handle the simple stuff
        combined = Buffer('combined')
        combined.bytelength = self.bytelength + other.bytelength
        combined.accessors = {**self.accessors, **other.accessors}

        # Need to update byte offsets in buffer views
        combined.buffer_views = self.buffer_views.copy()
        other_views = other.buffer_views.copy()
        for key in other_views.keys():
            other_views[key]['byteoffset'] += self.bytelength
        combined.buffer_views.update(other_views)

        return combined
