import base64
from distutils.version import StrictVersion as Version
import collections
import json
import math
import os
import struct

import bpy


def get_bone_name(bone):
    return '{}_{}'.format(bone.id_data.name, bone.name)


class AnimationPair:
    def __init__(self, target, action, is_shape_key=False):
        self.target = target
        self.action = action
        self.name = '{}_{}'.format(target.name, action.name)
        self.is_shape_key = is_shape_key


class Reference:
    __slots__ = (
        "blender_type",
        "blender_name",
        "source",
        "prop",
        "value",
    )

    def __init__(self, blender_type, blender_name, source, prop):
        self.blender_type = blender_type
        self.blender_name = blender_name
        self.source = source
        self.prop = prop
        self.value = None

    def __str__(self):
        return json.dumps([self.blender_type, self.blender_name, self.value])


class SimpleID:
    def __init__(self, name, data=None):
        self.name = name
        self.data = data


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

    class Accessor:
        __slots__ = (
            "name",
            "buffer",
            "buffer_view",
            "byte_offset",
            "byte_stride",
            "component_type",
            "count",
            "min",
            "max",
            "data_type",
            "type_size",
            "_ctype",
            "_ctype_size",
            "_buffer_data",
            )

        def __init__(self,
                     name,
                     buffer,
                     buffer_view,
                     byte_offset,
                     byte_stride,
                     component_type,
                     count,
                     data_type):
            self.name = name
            self.buffer = buffer
            self.buffer_view = buffer_view
            self.byte_offset = byte_offset
            self.byte_stride = byte_stride
            self.component_type = component_type
            self.count = count
            self.min = [math.inf for i in range(16)]
            self.max = [-math.inf for i in range(16)]
            self.data_type = data_type

            if self.data_type == Buffer.MAT4:
                self.type_size = 16
            elif self.data_type == Buffer.VEC4:
                self.type_size = 4
            elif self.data_type == Buffer.VEC3:
                self.type_size = 3
            elif self.data_type == Buffer.VEC2:
                self.type_size = 2
            else:
                self.type_size = 1

            if component_type == Buffer.BYTE:
                self._ctype = '<b'
            elif component_type == Buffer.UNSIGNED_BYTE:
                self._ctype = '<B'
            elif component_type == Buffer.SHORT:
                self._ctype = '<h'
            elif component_type == Buffer.UNSIGNED_SHORT:
                self._ctype = '<H'
            elif component_type == Buffer.INT:
                self._ctype = '<i'
            elif component_type == Buffer.UNSIGNED_INT:
                self._ctype = '<I'
            elif component_type == Buffer.FLOAT:
                self._ctype = '<f'
            else:
                raise ValueError("Bad component type")

            self._ctype_size = struct.calcsize(self._ctype)
            self._buffer_data = self.buffer.get_buffer_data(self.buffer_view)

        def __len__(self):
            return self.count

        def __getitem__(self, idx):
            if not isinstance(idx, int):
                raise TypeError("Expected an integer index")

            ptr = (
                (
                    (idx % self.type_size)
                    * self._ctype_size + idx // self.type_size * self.byte_stride
                ) + self.byte_offset
            )

            return struct.unpack_from(self._ctype, self._buffer_data, ptr)[0]

        def __setitem__(self, idx, value):
            if not isinstance(idx, int):
                raise TypeError("Expected an integer index")

            i = idx % self.type_size
            self.min[i] = value if value < self.min[i] else self.min[i]
            self.max[i] = value if value > self.max[i] else self.max[i]

            ptr = (
                (i * self._ctype_size + idx // self.type_size * self.byte_stride)
                + self.byte_offset
            )

            struct.pack_into(self._ctype, self._buffer_data, ptr, value)

    __slots__ = (
        "name",
        "bytelength",
        "buffer_views",
        "accessors",
        )

    def __init__(self, name):
        self.name = 'buffer_{}'.format(name)
        self.bytelength = 0
        self.buffer_views = collections.OrderedDict()
        self.accessors = {}

    def export_buffer(self, state):
        data = bytearray()
        for view in self.buffer_views.values():
            data.extend(view['data'])

        if state['settings']['buffers_embed_data'] and not state['settings']['gltf_export_binary']:
            uri = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode('ascii')
        else:
            uri = bpy.path.clean_name(self.name) + '.bin'
            path = os.path.join(state['settings']['gltf_output_dir'], uri)
            state['files'][path] = data

        gltf = {
            'byteLength': self.bytelength,
            'name': self.name,
        }

        embedded_binary = (
            state['settings']['buffers_embed_data']
            and state['settings']['gltf_export_binary']
        )
        if not embedded_binary:
            gltf['uri'] = uri

        if state['version'] < Version('2.0'):
            gltf['type'] = 'arraybuffer'

        return gltf

    def add_view(self, bytelength, bytestride, target):
        buffer_name = 'bufferView_{}_{}'.format(self.name, len(self.buffer_views))
        self.buffer_views[buffer_name] = {
            'data': bytearray(bytelength),
            'target': target,
            'bytelength': bytelength,
            'byteoffset': self.bytelength,
            'bytestride': bytestride,
        }
        self.bytelength += bytelength
        return buffer_name

    def export_views(self, state):
        gltf_views = []

        for key, value in self.buffer_views.items():
            gltf = {
                'byteLength': value['bytelength'],
                'byteOffset': value['byteoffset'],
                'name': key,
            }

            if state['version'] >= Version('2.0') and value['bytestride'] > 0:
                gltf['byteStride'] = value['bytestride']

            gltf['buffer'] = Reference('buffers', self.name, gltf, 'buffer')
            state['references'].append(gltf['buffer'])

            if value['target'] is not None:
                gltf['target'] = value['target']

            gltf_views.append(gltf)

            state['input']['bufferViews'].append(SimpleID(key))

        return gltf_views

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
        self.accessors[accessor_name] = self.Accessor(
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

    def export_accessors(self, state):
        gltf_accessors = []

        for key, value in self.accessors.items():
            # Do not export an empty accessor
            if value.count == 0:
                continue

            gltf = {
                'byteOffset': value.byte_offset,
                'componentType': value.component_type,
                'count': value.count,
                'min': value.min[:value.type_size],
                'max': value.max[:value.type_size],
                'type': value.data_type,
                'name': value.name,
            }

            if state['version'] < Version('2.0'):
                gltf['byteStride'] = value.byte_stride

            gltf['bufferView'] = Reference('bufferViews', value.buffer_view, gltf, 'bufferView')
            state['references'].append(gltf['bufferView'])

            gltf_accessors.append(gltf)

            state['input']['accessors'].append(SimpleID(key))

        return gltf_accessors

    def combine(self, other, state):
        # Handle the simple stuff
        combined = Buffer(state['settings']['gltf_name'])
        combined.bytelength = self.bytelength + other.bytelength
        combined.accessors = {**self.accessors, **other.accessors}

        # Need to update byte offsets in buffer views
        combined.buffer_views = self.buffer_views.copy()
        other_views = other.buffer_views.copy()
        for key in other_views.keys():
            other_views[key]['byteoffset'] += self.bytelength
        combined.buffer_views.update(other_views)

        return combined
