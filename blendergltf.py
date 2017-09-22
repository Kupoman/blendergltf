import base64
import collections
from distutils.version import StrictVersion as Version
import functools
import itertools
import json
import math
import os
import shutil
import struct
import zlib

import bpy
import idprop
import mathutils


__all__ = ['export_gltf']


DEFAULT_SETTINGS = {
    'gltf_output_dir': '',
    'buffers_embed_data': True,
    'buffers_combine_data': False,
    'nodes_export_hidden': False,
    'nodes_global_matrix': mathutils.Matrix.Identity(4),
    'nodes_selected_only': False,
    'blocks_prune_unused': True,
    'meshes_apply_modifiers': True,
    'meshes_interleave_vertex_data': True,
    'images_data_storage': 'COPY',
    'asset_version': '1.0',
    'asset_profile': 'WEB',
    'images_allow_srgb': False,
    'extension_exporters': [],
}


# Texture formats
GL_ALPHA = 6406
GL_RGB = 6407
GL_RGBA = 6408
GL_LUMINANCE = 6409
GL_LUMINANCE_ALPHA = 6410

# sRGB texture formats (not actually part of WebGL 1.0 or glTF 1.0)
GL_SRGB = 0x8C40
GL_SRGB_ALPHA = 0x8C42

OES_ELEMENT_INDEX_UINT = 'OES_element_index_uint'

PROFILE_MAP = {
    'WEB': {'api': 'WebGL', 'version': '1.0'},
    'DESKTOP': {'api': 'OpenGL', 'version': '3.0'}
}


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


class Vertex:
    __slots__ = (
        "co",
        "normal",
        "uvs",
        "colors",
        "loop_indices",
        "index",
        "weights",
        "joint_indexes",
        )

    def __init__(self, mesh, loop):
        vert_idx = loop.vertex_index
        loop_idx = loop.index
        self.co = mesh.vertices[vert_idx].co[:]
        self.normal = loop.normal[:]
        self.uvs = tuple(layer.data[loop_idx].uv[:] for layer in mesh.uv_layers)
        self.colors = tuple(layer.data[loop_idx].color[:] for layer in mesh.vertex_colors)
        self.loop_indices = [loop_idx]

        # Take the four most influential groups
        groups = sorted(
            mesh.vertices[vert_idx].groups,
            key=lambda group: group.weight,
            reverse=True
        )
        if len(groups) > 4:
            groups = groups[:4]

        self.weights = [group.weight for group in groups]
        self.joint_indexes = [group.group for group in groups]

        if len(self.weights) < 4:
            for _ in range(len(self.weights), 4):
                self.weights.append(0.0)
                self.joint_indexes.append(0)

        self.index = 0

    def __hash__(self):
        return hash((self.co, self.normal, self.uvs, self.colors))

    def __eq__(self, other):
        equals = (
            (self.co == other.co) and
            (self.normal == other.normal) and
            (self.uvs == other.uvs) and
            (self.colors == other.colors)
        )

        if equals:
            indices = self.loop_indices + other.loop_indices
            self.loop_indices = indices
            other.loop_indices = indices
        return equals


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
            self.max = [0 for i in range(16)]
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

        if state['settings']['buffers_embed_data']:
            uri = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode('ascii')
        else:
            uri = bpy.path.clean_name(self.name) + '.bin'
            with open(os.path.join(state['settings']['gltf_output_dir'], uri), 'wb') as fout:
                fout.write(data)

        gltf = {
            'byteLength': self.bytelength,
            'uri': uri,
            'name': self.name,
        }

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


def togl(matrix):
    return [i for col in matrix.col for i in col]


def decompose(matrix):
    loc, rot, scale = matrix.decompose()
    loc = loc.to_tuple()
    rot = (rot.x, rot.y, rot.z, rot.w)
    scale = scale.to_tuple()

    return loc, rot, scale


_IGNORED_CUSTOM_PROPS = [
    '_RNA_UI',
    'cycles',
    'cycles_visibility',
]


def _get_custom_properties(data):
    return {
        k: v for k, v in data.items()
        if k not in _IGNORED_CUSTOM_PROPS and not isinstance(v, idprop.types.IDPropertyGroup)
    }


def _get_bone_name(bone):
    return '{}_{}'.format(bone.id_data.name, bone.name)


def export_camera(_, camera):
    camera_gltf = {}
    if camera.type == 'ORTHO':
        camera_gltf = {
            'orthographic': {
                'xmag': camera.ortho_scale,
                'ymag': camera.ortho_scale,
                'zfar': camera.clip_end,
                'znear': camera.clip_start,
            },
            'type': 'orthographic',
        }
    else:
        camera_gltf = {
            'perspective': {
                'aspectRatio': camera.angle_x / camera.angle_y,
                'yfov': camera.angle_y,
                'zfar': camera.clip_end,
                'znear': camera.clip_start,
            },
            'type': 'perspective',
        }
    camera_gltf['name'] = camera.name
    extras = _get_custom_properties(camera)
    if extras:
        camera_gltf['extras'] = extras
    return camera_gltf


def export_material(state, material):
    gltf = {
        'name': material.name,
    }

    if state['version'] < Version('2.0'):
        return gltf

    if hasattr(material, 'pbr_export_settings'):
        pbr_settings = material.pbr_export_settings
        pbr = {
            'baseColorFactor': pbr_settings.base_color_factor[:],
            'metallicFactor': pbr_settings.metallic_factor,
            'roughnessFactor': pbr_settings.roughness_factor,
        }

        if pbr_settings.base_color_texture:
            pbr['baseColorTexture'] = {
                'texCoord': pbr_settings.base_color_text_index,
            }
            pbr['baseColorTexture']['index'] = Reference(
                'textures',
                pbr_settings.base_color_texture,
                pbr['baseColorTexture'],
                'index'
            )
            state['references'].append(pbr['baseColorTexture']['index'])

        if pbr_settings.metal_roughness_texture:
            pbr['metallicRoughnessTexture'] = {
                'texCoord': pbr_settings.metal_rough_text_index,
            }
            pbr['metallicRoughnessTexture']['index'] = Reference(
                'textures',
                pbr_settings.metal_roughness_texture,
                pbr['metallicRoughnessTexture'],
                'index'
            )
            state['references'].append(pbr['metallicRoughnessTexture']['index'])

        gltf['pbrMetallicRoughness'] = pbr

        gltf['emissiveFactor'] = pbr_settings.emissive_factor[:]

        if pbr_settings.emissive_texture:
            gltf['emissiveTexture'] = {
                'texCoord': pbr_settings.emissive_text_index,
            }
            gltf['emissiveTexture']['index'] = Reference(
                'textures',
                pbr_settings.emissive_texture,
                gltf['emissiveTexture'],
                'index'
            )
            state['references'].append(gltf['emissiveTexture']['index'])

        if pbr_settings.normal_texture:
            gltf['normalTexture'] = {
                'texCoord': pbr_settings.normal_text_index,
            }
            gltf['normalTexture']['index'] = Reference(
                'textures',
                pbr_settings.normal_texture,
                gltf['normalTexture'],
                'index'
            )
            state['references'].append(gltf['normalTexture']['index'])

        if pbr_settings.occlusion_texture:
            gltf['occlusionTexture'] = {
                'texCoord': pbr_settings.occlusion_text_index,
            }
            gltf['occlusionTexture']['index'] = Reference(
                'textures',
                pbr_settings.occlusion_texture,
                gltf['occlusionTexture'],
                'index'
            )
            state['references'].append(gltf['occlusionTexture']['index'])

    return gltf


def export_mesh(state, mesh):
    # glTF data
    gltf_mesh = {
        'name': mesh.name,
        'primitives': [],
    }

    extras = _get_custom_properties(mesh)
    if extras:
        gltf_mesh['extras'] = extras

    is_skinned = mesh.name in state['skinned_meshes']

    mesh.calc_normals_split()
    mesh.calc_tessface()

    num_uv_layers = len(mesh.uv_layers)
    num_col_layers = len(mesh.vertex_colors)
    vertex_size = (3 + 3 + num_uv_layers * 2 + num_col_layers * 3) * 4

    buf = Buffer(mesh.name)
    skin_buf = Buffer('{}_skin'.format(mesh.name))

    # Vertex data

    vert_list = {Vertex(mesh, loop): 0 for loop in mesh.loops}.keys()
    num_verts = len(vert_list)

    # Interleave
    if state['settings']['meshes_interleave_vertex_data']:
        view = buf.add_view(vertex_size * num_verts, vertex_size, Buffer.ARRAY_BUFFER)
        vdata = buf.add_accessor(view, 0, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
        ndata = buf.add_accessor(view, 12, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
        tdata = [
            buf.add_accessor(
                view,
                24 + 8 * i,
                vertex_size,
                Buffer.FLOAT,
                num_verts,
                Buffer.VEC2
            )
            for i in range(num_uv_layers)
        ]
        cdata = [
            buf.add_accessor(
                view,
                24 + 8 * num_uv_layers + 12 * i,
                vertex_size,
                Buffer.FLOAT,
                num_verts,
                Buffer.VEC3
            )
            for i in range(num_col_layers)
        ]
    else:
        view = buf.add_view(vertex_size * num_verts, 12, Buffer.ARRAY_BUFFER)
        vdata = buf.add_accessor(view, 0, 12, Buffer.FLOAT, num_verts, Buffer.VEC3)
        ndata = buf.add_accessor(view, num_verts*12, 12, Buffer.FLOAT, num_verts, Buffer.VEC3)
        tdata = [
            buf.add_accessor(
                view,
                num_verts * (24 + 8 * i),
                8,
                Buffer.FLOAT,
                num_verts,
                Buffer.VEC2
            )
            for i in range(num_uv_layers)
        ]
        cdata = [
            buf.add_accessor(
                view,
                num_verts * (24 + 8 * num_uv_layers + 12 * i),
                12,
                Buffer.FLOAT,
                num_verts,
                Buffer.VEC3
            )
            for i in range(num_col_layers)
        ]

    skin_vertex_size = (4 + 4) * 4
    skin_view = skin_buf.add_view(
        skin_vertex_size * num_verts,
        skin_vertex_size,
        Buffer.ARRAY_BUFFER
    )
    jdata = skin_buf.add_accessor(
        skin_view,
        0,
        skin_vertex_size,
        Buffer.UNSIGNED_BYTE,
        num_verts,
        Buffer.VEC4
    )
    wdata = skin_buf.add_accessor(
        skin_view,
        16,
        skin_vertex_size,
        Buffer.FLOAT,
        num_verts,
        Buffer.VEC4
    )

    # Copy vertex data
    for i, vtx in enumerate(vert_list):
        vtx.index = i
        co = vtx.co
        normal = vtx.normal

        for j in range(3):
            vdata[(i * 3) + j] = co[j]
            ndata[(i * 3) + j] = normal[j]

        for j, uv in enumerate(vtx.uvs):
            tdata[j][i * 2] = uv[0]
            if state['settings']['asset_profile'] == 'WEB':
                tdata[j][i * 2 + 1] = 1.0 - uv[1]
            else:
                tdata[j][i * 2 + 1] = uv[1]

        for j, col in enumerate(vtx.colors):
            cdata[j][i * 3] = col[0]
            cdata[j][i * 3 + 1] = col[1]
            cdata[j][i * 3 + 2] = col[2]

    if is_skinned:
        for i, vtx in enumerate(vert_list):
            joints = vtx.joint_indexes
            weights = vtx.weights

            for j in range(4):
                jdata[(i * 4) + j] = joints[j]
                wdata[(i * 4) + j] = weights[j]

    # For each material, make an empty primitive set.
    # This dictionary maps material names to list of indices that form the
    # part of the mesh that the material should be applied to.
    prims = {ma.name if ma else '': [] for ma in mesh.materials}
    if not prims:
        prims = {'': []}

    # Index data
    # Map loop indices to vertices
    vert_dict = {i: vertex for vertex in vert_list for i in vertex.loop_indices}

    max_vert_index = 0
    for poly in mesh.polygons:
        # Find the primitive that this polygon ought to belong to (by
        # material).
        if not mesh.materials:
            prim = prims['']
        else:
            try:
                mat = mesh.materials[poly.material_index]
            except IndexError:
                # Polygon has a bad material index, so skip it
                continue
            prim = prims[mat.name if mat else '']

        # Find the (vertex) index associated with each loop in the polygon.
        indices = [vert_dict[i].index for i in poly.loop_indices]

        # Used to determine whether a mesh must be split.
        max_vert_index = max(max_vert_index, max(indices))

        if len(indices) == 3:
            # No triangulation necessary
            prim += indices
        elif len(indices) > 3:
            # Triangulation necessary
            for i in range(len(indices) - 2):
                prim += (indices[-1], indices[i], indices[i + 1])
        else:
            # Bad polygon
            raise RuntimeError(
                "Invalid polygon with {} vertices.".format(len(indices))
            )

    if max_vert_index > 65535:
        # Use the integer index extension
        if OES_ELEMENT_INDEX_UINT not in state['gl_extensions_used']:
            state['gl_extensions_used'].append(OES_ELEMENT_INDEX_UINT)

    if state['version'] < Version('2.0'):
        joint_key = 'JOINT'
        weight_key = 'WEIGHT'
    else:
        joint_key = 'JOINTS_0'
        weight_key = 'WEIGHTS_0'

    for mat, prim in prims.items():
        # For each primitive set add an index buffer and accessor.

        if not prim:
            # This material has not verts, do not make a 0 length buffer
            continue

        # If we got this far use integers if we have to, if this is not
        # desirable we would have bailed out by now.
        if max_vert_index > 65535:
            itype = Buffer.UNSIGNED_INT
            istride = 4
        else:
            itype = Buffer.UNSIGNED_SHORT
            istride = 2

        index_view = buf.add_view(istride * len(prim), 0, Buffer.ELEMENT_ARRAY_BUFFER)
        idata = buf.add_accessor(index_view, 0, istride, itype, len(prim),
                                 Buffer.SCALAR)

        for i, index in enumerate(prim):
            idata[i] = index

        gltf_prim = {
            'mode': 4,
        }

        gltf_prim['indices'] = Reference('accessors', idata.name, gltf_prim, 'indices')
        state['references'].append(gltf_prim['indices'])

        # Handle attribute references
        gltf_attrs = {}
        gltf_attrs['POSITION'] = Reference('accessors', vdata.name, gltf_attrs, 'POSITION')
        state['references'].append(gltf_attrs['POSITION'])

        gltf_attrs['NORMAL'] = Reference('accessors', ndata.name, gltf_attrs, 'NORMAL')
        state['references'].append(gltf_attrs['NORMAL'])

        for i, accessor in enumerate(tdata):
            attr_name = 'TEXCOORD_' + str(i)
            gltf_attrs[attr_name] = Reference('accessors', accessor.name, gltf_attrs, attr_name)
            state['references'].append(gltf_attrs[attr_name])
        for i, accessor in enumerate(cdata):
            attr_name = 'COLOR_' + str(i)
            gltf_attrs[attr_name] = Reference('accessors', accessor.name, gltf_attrs, attr_name)
            state['references'].append(gltf_attrs[attr_name])
        if is_skinned:
            gltf_attrs[joint_key] = Reference('accessors', jdata.name, gltf_attrs, joint_key)
            state['references'].append(gltf_attrs[joint_key])
            gltf_attrs[weight_key] = Reference('accessors', wdata.name, gltf_attrs, weight_key)
            state['references'].append(gltf_attrs[weight_key])

        gltf_prim['attributes'] = gltf_attrs

        # Add the material reference after checking that it is valid
        if mat:
            gltf_prim['material'] = Reference('materials', mat, gltf_prim, 'material')
            state['references'].append(gltf_prim['material'])

        gltf_mesh['primitives'].append(gltf_prim)

    state['buffers'].append(buf)
    state['input']['buffers'].append(SimpleID(buf.name))
    if is_skinned:
        state['buffers'].append(skin_buf)
        state['input']['buffers'].append(SimpleID(skin_buf.name))
        if state['version'] < Version('2.0'):
            gltf_mesh['skin'] = Reference('skins', mesh.name, gltf_mesh, 'skin')
            state['references'].append(gltf_mesh['skin'])

    return gltf_mesh


def export_skins(state):
    def export_skin(obj, mesh_name):
        if state['version'] < Version('2.0'):
            joints_key = 'jointNames'
        else:
            joints_key = 'joints'

        arm = obj.find_armature()

        bind_shape_mat = obj.matrix_world * arm.matrix_world.inverted()
        bone_groups = [group for group in obj.vertex_groups if group.name in arm.data.bones]

        gltf_skin = {
            'name': obj.name,
        }
        gltf_skin[joints_key] = [
            Reference('objects', _get_bone_name(arm.data.bones[group.name]), None, None)
            for group in bone_groups
        ]
        for i, ref in enumerate(gltf_skin[joints_key]):
            ref.source = gltf_skin[joints_key]
            ref.prop = i
            state['references'].append(ref)

        if state['version'] < Version('2.0'):
            gltf_skin['bindShapeMatrix'] = togl(bind_shape_mat)
            bind_shape_mat = mathutils.Matrix.Identity(4)
        else:
            bone_names = [_get_bone_name(b) for b in arm.data.bones if b.parent is None]
            if len(bone_names) > 1:
                print('Warning: Armature {} has no root node'.format(arm.data.name))
            gltf_skin['skeleton'] = Reference('objects', bone_names[0], gltf_skin, 'skeleton')
            state['references'].append(gltf_skin['skeleton'])

        element_size = 16 * 4
        num_elements = len(bone_groups)
        buf = Buffer('IBM_{}_skin'.format(obj.name))
        buf_view = buf.add_view(element_size * num_elements, element_size, None)
        idata = buf.add_accessor(buf_view, 0, element_size, Buffer.FLOAT, num_elements, Buffer.MAT4)

        for i, group in enumerate(bone_groups):
            bone = arm.data.bones[group.name]
            mat = togl(bone.matrix_local.inverted() * bind_shape_mat)
            for j in range(16):
                idata[(i * 16) + j] = mat[j]

        gltf_skin['inverseBindMatrices'] = Reference(
            'accessors',
            idata.name,
            gltf_skin,
            'inverseBindMatrices'
        )
        state['references'].append(gltf_skin['inverseBindMatrices'])
        state['buffers'].append(buf)
        state['input']['buffers'].append(SimpleID(buf.name))

        state['input']['skins'].append(SimpleID(mesh_name))

        return gltf_skin

    return [export_skin(obj, mesh_name) for mesh_name, obj in state['skinned_meshes'].items()]


def export_node(state, obj):
    node = {
        'name': obj.name,
    }
    if obj.children:
        node['children'] = []
    for i, child in enumerate(obj.children):
        node['children'].append(Reference('objects', child.name, node['children'], i))
        state['references'].append(node['children'][-1])

    node['translation'], node['rotation'], node['scale'] = decompose(obj.matrix_local)

    extras = _get_custom_properties(obj)
    extras.update({
        prop.name: prop.value for prop in obj.game.properties.values()
    })
    if extras:
        node['extras'] = extras

    if obj.type == 'MESH':
        mesh = state['mod_meshes'].get(obj.name, obj.data)
        if state['version'] < Version('2.0'):
            node['meshes'] = []
            node['meshes'].append(Reference('meshes', mesh.name, node['meshes'], 0))
            state['references'].append(node['meshes'][0])
        else:
            node['mesh'] = Reference('meshes', mesh.name, node, 'mesh')
            state['references'].append(node['mesh'])
        armature = obj.find_armature()
        if armature:
            state['skinned_meshes'][mesh.name] = obj
            if state['version'] < Version('2.0'):
                bone_names = [_get_bone_name(b) for b in armature.data.bones if b.parent is None]
                node['skeletons'] = []
                node['skeletons'].extend([
                    Reference('objects', bone, node['skeletons'], i)
                    for i, bone in enumerate(bone_names)
                ])
                for ref in node['skeletons']:
                    state['references'].append(ref)
            else:
                node['skin'] = Reference('skins', mesh.name, node, 'skin')
                state['references'].append(node['skin'])
    elif obj.type == 'CAMERA':
        node['camera'] = Reference('cameras', obj.data.name, node, 'camera')
        state['references'].append(node['camera'])
    elif obj.type == 'EMPTY' and obj.dupli_group is not None:
        # Expand dupli-groups
        node['children'] = node.get('children', [])
        dupli_refs = [
            Reference('objects', dupli.name, node['children'], i + len(node['children']))
            for i, dupli in enumerate(obj.dupli_group.objects)
        ]
        node['children'].extend(dupli_refs)
        state['references'].extend(dupli_refs)
    elif obj.type == 'ARMATURE':
        for i, bone in enumerate(obj.data.bones):
            state['input']['bones'].append(SimpleID(_get_bone_name(bone), bone))
        if not node['children']:
            node['children'] = []
        offset = len(node['children'])
        root_bones = [
            Reference('objects', _get_bone_name(b), node['children'], i + offset)
            for i, b in enumerate(obj.data.bones) if b.parent is None
        ]
        for bone in root_bones:
            state['references'].append(bone)
        node['children'].extend(root_bones)

    return node


def export_joint(state, bone):
    matrix = bone.matrix_local
    if bone.parent:
        matrix = bone.parent.matrix_local.inverted() * matrix

    gltf_joint = {
        'name': _get_bone_name(bone),
    }
    if state['version'] < Version('2.0'):
        gltf_joint['jointName'] = Reference(
            'objects',
            _get_bone_name(bone),
            gltf_joint,
            'jointName'
        )
        state['references'].append(gltf_joint['jointName'])
    if bone.children:
        gltf_joint['children'] = [
            Reference('objects', _get_bone_name(child), None, None) for child in bone.children
        ]
    for i, ref in enumerate(gltf_joint.get('children', [])):
        ref.source = gltf_joint['children']
        ref.prop = i
        state['references'].append(ref)

    gltf_joint['translation'], gltf_joint['rotation'], gltf_joint['scale'] = decompose(matrix)

    return gltf_joint


def export_scene(state, scene):
    result = {
        'extras': {
            'background_color': scene.world.horizon_color[:] if scene.world else [0.05]*3,
            'active_camera': 'camera_'+scene.camera.name if scene.camera else None,
            'frames_per_second': scene.render.fps,
        },
        'name': scene.name,
    }

    if scene.camera:
        result['extras']['active_camera'] = Reference(
            'cameras',
            scene.camera.name,
            result['extras'],
            'active_camera'
        )
        state['references'].append(result['extras']['active_camera'])

    extras = _get_custom_properties(scene)
    if extras:
        result['extras'].update(_get_custom_properties(scene))

    result['nodes'] = [
        Reference('objects', ob.name, None, None)
        for ob in scene.objects
        if ob in state['input']['objects'] and ob.parent is None and ob.is_visible(scene)
    ]
    for i, ref in enumerate(result['nodes']):
        ref.source = result['nodes']
        ref.prop = i
    state['references'].extend(result['nodes'])

    hidden_nodes = [
        Reference('objects', ob.name, None, None)
        for ob in scene.objects
        if ob in state['input']['objects'] and not ob.is_visible(scene)
    ]

    if hidden_nodes:
        result['extras']['hidden_nodes'] = hidden_nodes
        for i, ref in enumerate(hidden_nodes):
            ref.source = result['extras']['hidden_nodes']
            ref.prop = i
        state['references'].extend(result['extras']['hidden_nodes'])

    return result


def export_buffers(state):
    if state['settings']['buffers_combine_data']:
        buffers = [functools.reduce(lambda x, y: x+y, state['buffers'], Buffer('empty'))]
        state['buffers'] = buffers
        state['input']['buffers'] = [SimpleID(buffers[0].name)]
    else:
        buffers = state['buffers']

    gltf = {}
    gltf['buffers'] = [buf.export_buffer(state) for buf in buffers]
    gltf['bufferViews'] = list(itertools.chain(*[buf.export_views(state) for buf in buffers]))
    gltf['accessors'] = list(itertools.chain(*[buf.export_accessors(state) for buf in buffers]))

    return gltf


def image_to_data_uri(image, as_bytes=False):
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

    if as_bytes:
        return png_bytes
    else:
        return 'data:image/png;base64,' + base64.b64encode(png_bytes).decode()


def check_image(image):
    errors = []
    if image.size[0] == 0:
        errors.append('x dimension is 0')
    if image.size[1] == 0:
        errors.append('y dimension is 0')
    if image.type != 'IMAGE':
        errors.append('not an image')

    if errors:
        err_list = '\n\t'.join(errors)
        print(
            'Unable to export image {} due to the following errors:\n\t{}'
            .format(image.name, err_list)
        )
        return False

    return True


EXT_MAP = {'BMP': 'bmp', 'JPEG': 'jpg', 'PNG': 'png', 'TARGA': 'tga'}


def export_image(state, image):
    uri = ''

    storage_setting = state['settings']['images_data_storage']
    image_packed = image.packed_file is not None
    if image_packed and storage_setting in ['COPY', 'REFERENCE']:
        if image.file_format in EXT_MAP:
            # save the file to the output directory
            uri = '.'.join([image.name, EXT_MAP[image.file_format]])
            temp = image.filepath
            image.filepath = os.path.join(state['settings']['gltf_output_dir'], uri)
            image.save()
            image.filepath = temp
        else:
            # convert to png and save
            uri = '.'.join([image.name, 'png'])
            png = image_to_data_uri(image, as_bytes=True)
            with open(os.path.join(state['settings']['gltf_output_dir'], uri), 'wb') as outfile:
                outfile.write(png)

    elif storage_setting == 'COPY':
        try:
            shutil.copy(bpy.path.abspath(image.filepath), state['settings']['gltf_output_dir'])
        except shutil.SameFileError:
            # If the file already exists, no need to copy
            pass
        uri = bpy.path.basename(image.filepath)
    elif storage_setting == 'REFERENCE':
        uri = image.filepath.replace('//', '')
    elif storage_setting == 'EMBED':
        uri = image_to_data_uri(image)
    else:
        print(
            'Encountered unknown option ({}) for images_data_storage setting'
            .format(storage_setting)
        )

    return {
        'uri': uri,
        'name': image.name,
    }


def check_texture(texture):
    if not isinstance(texture, bpy.types.ImageTexture):
        return False

    errors = []
    if texture.image is None:
        errors.append('has no image reference')
    elif texture.image.channels not in [3, 4]:
        errors.append(
            'points to {}-channel image (must be 3 or 4)'
            .format(texture.image.channels)
        )

    if errors:
        err_list = '\n\t'.join(errors)
        print(
            'Unable to export texture {} due to the following errors:\n\t{}'
            .format(texture.name, err_list)
        )
        return False

    return True


def export_texture(state, texture):
    gltf_texture = {
        'sampler': 'sampler_default',
        'source': 'image_' + texture.image.name,
        'name': texture.name,
    }

    gltf_texture['sampler'] = Reference('samplers', 'default', gltf_texture, 'sampler')
    state['references'].append(gltf_texture['sampler'])

    gltf_texture['source'] = Reference('images', texture.image.name, gltf_texture, 'source')
    state['references'].append(gltf_texture['source'])

    tformat = None
    channels = texture.image.channels
    image_is_srgb = texture.image.colorspace_settings.name == 'sRGB'
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

    if state['version'] < Version('2.0'):
        gltf_texture['format'] = gltf_texture['internalFormat'] = tformat

    return gltf_texture


def _can_object_use_action(obj, action):
    for fcurve in action.fcurves:
        path = fcurve.data_path
        if not path.startswith('pose'):
            return obj.animation_data is not None

        if obj.type == 'ARMATURE':
            path = path.split('["')[-1]
            path = path.split('"]')[0]
            if path in [bone.name for bone in obj.data.bones]:
                return True

    return False


def export_animations(state, actions):
    def export_animation(obj, action):
        if state['version'] < Version('2.0'):
            target_key = 'id'
        else:
            target_key = 'node'

        channels = {}

        sce = bpy.context.scene
        prev_frame = sce.frame_current
        prev_action = obj.animation_data.action

        frame_start, frame_end = [int(x) for x in action.frame_range]
        num_frames = frame_end - frame_start + 1
        obj.animation_data.action = action

        channels[obj.name] = []

        if obj.type == 'ARMATURE':
            for pbone in obj.pose.bones:
                channels[pbone.name] = []

        for frame in range(frame_start, frame_end + 1):
            sce.frame_set(frame)

            channels[obj.name].append(obj.matrix_local)

            if obj.type == 'ARMATURE':
                for pbone in obj.pose.bones:
                    if pbone.parent:
                        mat = pbone.parent.matrix.inverted() * pbone.matrix
                    else:
                        mat = pbone.matrix.copy()
                    channels[pbone.name].append(mat)

        gltf_channels = []
        gltf_parameters = {}
        gltf_samplers = []

        tbuf = Buffer('{}_time'.format(action.name))
        tbv = tbuf.add_view(num_frames * 1 * 4, 1 * 4, None)
        tdata = tbuf.add_accessor(tbv, 0, 1 * 4, Buffer.FLOAT, num_frames, Buffer.SCALAR)
        time = 0
        for i in range(num_frames):
            tdata[i] = time
            time += state['animation_dt']
        state['buffers'].append(tbuf)
        state['input']['buffers'].append(SimpleID(tbuf.name))
        time_parameter_name = '{}_time_parameter'.format(action.name)
        ref = Reference('accessors', tdata.name, gltf_parameters, time_parameter_name)
        gltf_parameters[time_parameter_name] = ref
        state['references'].append(ref)

        sampler_keys = []
        for targetid, chan in channels.items():
            buf = Buffer('{}_{}'.format(targetid, action.name))
            lbv = buf.add_view(num_frames * 3 * 4, 3 * 4, None)
            ldata = buf.add_accessor(lbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)
            rbv = buf.add_view(num_frames * 4 * 4, 4 * 4, None)
            rdata = buf.add_accessor(rbv, 0, 4 * 4, Buffer.FLOAT, num_frames, Buffer.VEC4)
            sbv = buf.add_view(num_frames * 3 * 4, 3 * 4, None)
            sdata = buf.add_accessor(sbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)

            for i in range(num_frames):
                loc, rot, scale = decompose(chan[i])
                for j in range(3):
                    ldata[(i * 3) + j] = loc[j]
                    sdata[(i * 3) + j] = scale[j]
                for j in range(4):
                    rdata[(i * 4) + j] = rot[j]

            state['buffers'].append(buf)
            state['input']['buffers'].append(SimpleID(buf.name))

            is_bone = False
            if targetid != obj.name:
                is_bone = True
                targetid = _get_bone_name(bpy.data.armatures[obj.data.name].bones[targetid])

            for path in ('translation', 'rotation', 'scale'):
                sampler_name = '{}_{}_{}_sampler'.format(action.name, targetid, path)
                sampler_keys.append(sampler_name)
                parameter_name = '{}_{}_{}_parameter'.format(action.name, targetid, path)

                gltf_channel = {
                    'sampler': sampler_name,
                    'target': {
                        target_key: targetid,
                        'path': path,
                    }
                }
                gltf_channels.append(gltf_channel)
                id_ref = Reference(
                    'objects' if is_bone else 'objects',
                    targetid,
                    gltf_channel['target'],
                    target_key
                )
                state['references'].append(id_ref)
                state['input']['anim_samplers'].append(SimpleID(sampler_name))
                sampler_ref = Reference('anim_samplers', sampler_name, gltf_channel, 'sampler')
                state['references'].append(sampler_ref)

                gltf_sampler = {
                    'input': None,
                    'interpolation': 'LINEAR',
                    'output': None,
                }
                gltf_samplers.append(gltf_sampler)

                accessor_name = {
                    'translation': ldata.name,
                    'rotation': rdata.name,
                    'scale': sdata.name,
                }[path]

                if state['version'] < Version('2.0'):
                    gltf_sampler['input'] = time_parameter_name
                    gltf_sampler['output'] = parameter_name
                    accessor_ref = Reference(
                        'accessors',
                        accessor_name,
                        gltf_parameters,
                        parameter_name
                    )
                    gltf_parameters[parameter_name] = accessor_ref
                else:
                    time_ref = Reference(
                        'accessors',
                        tdata.name,
                        gltf_sampler,
                        'input'
                    )
                    gltf_sampler['input'] = time_ref
                    state['references'].append(time_ref)
                    accessor_ref = Reference(
                        'accessors',
                        accessor_name,
                        gltf_sampler,
                        'output'
                    )
                    gltf_sampler['output'] = accessor_ref

                state['references'].append(accessor_ref)

        gltf_action = {
            'name': action.name,
            'channels': gltf_channels,
            'samplers': gltf_samplers,
        }

        if state['version'] < Version('2.0'):
            gltf_action['samplers'] = {
                i[0]: i[1] for i in zip(sampler_keys, gltf_action['samplers'])
            }
            gltf_action['parameters'] = gltf_parameters

        obj.animation_data.action = prev_action
        sce.frame_set(prev_frame)

        return gltf_action

    gltf_actions = []
    for obj in state['input']['objects']:
        gltf_actions.extend([
            export_animation(obj, action)
            for action in actions
            if _can_object_use_action(obj, action)
        ])

    return gltf_actions


def insert_root_nodes(state, root_matrix):
    for i, scene in enumerate(state['output']['scenes']):
        # Generate a new root node for each scene
        root_node = {
            'children': scene['nodes'],
            'matrix': root_matrix,
            'name': '{}_root'.format(scene['name']),
        }
        state['output']['nodes'].append(root_node)
        ref_name = '__scene_root_{}_'.format(i)
        state['input']['objects'].append(SimpleID(ref_name))

        # Replace scene node lists to just point to the new root nodes
        scene['nodes'] = []
        scene['nodes'].append(Reference('objects', ref_name, scene['nodes'], 0))
        state['references'].append(scene['nodes'][0])


def build_string_refmap(input_data):
    in_out_map = {
        'objects': 'nodes',
        'bones': 'nodes',
        'lamps': 'lights'
    }
    refmap = {}
    for key, value in input_data.items():
        refmap.update({
            (key, data.name): '{}_{}'.format(in_out_map.get(key, key), data.name)
            for data in value
        })
    return refmap


def build_int_refmap(input_data):
    refmap = {}
    for key, value in input_data.items():
        refmap.update({(key, data.name): i for i, data in enumerate(value)})
    return refmap


def export_gltf(scene_delta, settings=None):
    # Fill in any missing settings with defaults
    if not settings:
        settings = {}
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)

    # Initialize export state
    state = {
        'version': Version(settings['asset_version']),
        'settings': settings,
        'animation_dt': 1.0 / bpy.context.scene.render.fps,
        'mod_meshes': {},
        'skinned_meshes': {},
        'extensions_used': [],
        'gl_extensions_used': [],
        'buffers': [],
        'input': {
            'buffers': [],
            'accessors': [],
            'bufferViews': [],
            'objects': [],
            'bones': [],
            'anim_samplers': [],
            'samplers': [SimpleID('default')],
            'scenes': [],
            'skins': [],
            'materials': [],
        },
        'output': {
            'extensions': [],
        },
        'references': [],
    }
    state['input'].update({key: list(value) for key, value in scene_delta.items()})

    # Apply modifiers
    mesh_list = []
    if settings['meshes_apply_modifiers']:
        scene = bpy.context.scene
        mod_obs = [ob for ob in state['input']['objects'] if ob.is_modified(scene, 'PREVIEW')]
        for mesh in scene_delta.get('meshes', []):
            mod_users = [ob for ob in mod_obs if ob.data == mesh]

            # Only convert meshes with modifiers, otherwise each non-modifier
            # user ends up with a copy of the mesh and we lose instancing
            state['mod_meshes'].update(
                {ob.name: ob.to_mesh(scene, True, 'PREVIEW') for ob in mod_users}
            )

            # Add unmodified meshes directly to the mesh list
            if len(mod_users) < mesh.users:
                mesh_list.append(mesh)
        mesh_list.extend(state['mod_meshes'].values())
    else:
        mesh_list = scene_delta.get('meshes', [])
    state['input']['meshes'] = mesh_list

    exporter = collections.namedtuple('exporter', [
        'gltf_key',
        'blender_key',
        'export_func',
        'check_func',
    ])
    exporters = [
        exporter('cameras', 'cameras', export_camera, lambda x: True),
        exporter('images', 'images', export_image, check_image),
        exporter('nodes', 'objects', export_node, lambda x: True),
        # Make sure meshes come after nodes to detect which meshes are skinned
        exporter('materials', 'materials', export_material, lambda x: True),
        exporter('meshes', 'meshes', export_mesh, lambda x: True),
        exporter('scenes', 'scenes', export_scene, lambda x: True),
        exporter('textures', 'textures', export_texture, check_texture),
    ]

    state['output'] = {
        exporter.gltf_key: [
            exporter.export_func(state, data)
            for data in state['input'].get(exporter.blender_key, [])
            if exporter.check_func(data)
        ] for exporter in exporters
    }

    # Export top level data
    gltf = {
        'asset': {
            'version': settings['asset_version'],
        }
    }
    if state['version'] < Version('2.0'):
        gltf['asset']['profile'] = PROFILE_MAP[settings['asset_profile']]

    # Export samplers
    state['output']['samplers'] = [{'name': 'default'}]

    # Export animations
    state['output']['animations'] = export_animations(state, scene_delta.get('actions', []))
    state['output']['skins'] = export_skins(state)
    state['output']['nodes'].extend([
        export_joint(state, sid.data) for sid in state['input']['bones']
    ])

    # Move bones to nodes for updating references
    state['input']['objects'].extend(state['input']['bones'])
    state['input']['bones'] = []

    # Export default scene
    default_scene = None
    for scene in state['input']['scenes']:
        if scene == bpy.context.scene:
            default_scene = scene
    if default_scene:
        scene_ref = Reference('scenes', bpy.context.scene.name, gltf, 'scene')
        scene_ref.value = 0
        state['references'].append(scene_ref)

    # Export extensions
    state['refmap'] = build_int_refmap(state['input'])
    for ext_exporter in settings['extension_exporters']:
        ext_exporter.export(state)

    # Insert root nodes if axis conversion is needed
    if settings['nodes_global_matrix'] != mathutils.Matrix.Identity(4):
        insert_root_nodes(state, togl(settings['nodes_global_matrix']))

    state['output'].update(export_buffers(state))
    state['output'] = {key: value for key, value in state['output'].items() if value != []}
    if state['extensions_used']:
        gltf.update({'extensionsUsed': state['extensions_used']})
    if state['version'] < Version('2.0'):
        gltf.update({'glExtensionsUsed': state['gl_extensions_used']})

    # Convert lists to dictionaries
    if state['version'] < Version('2.0'):
        extensions = state['output'].get('extensions', [])
        state['output'] = {
            key: {
                '{}_{}'.format(key, data['name']): data for data in value
            } for key, value in state['output'].items()
            if key != 'extensions'
        }
        if extensions:
            state['output']['extensions'] = extensions
    gltf.update(state['output'])

    # Resolve references
    if state['version'] < Version('2.0'):
        refmap = build_string_refmap(state['input'])
    else:
        refmap = build_int_refmap(state['input'])
    for ref in state['references']:
        ref.source[ref.prop] = refmap[(ref.blender_type, ref.blender_name)]

    # Remove any temporary meshes from applying modifiers
    for mesh in state['mod_meshes'].values():
        bpy.data.meshes.remove(mesh)

    return gltf
