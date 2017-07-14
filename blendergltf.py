import base64
import collections
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
import gpu
import mathutils


if '_IMPORTED' not in locals():
    _IMPORTED = True
    from . import gpu_luts
    from . import shader_converter
    from .extension_exporters import blender_physics
else:
    import imp
    imp.reload(gpu_luts)
    imp.reload(shader_converter)
    imp.reload(blender_physics)


__all__ = ['export_gltf']


DEFAULT_SETTINGS = {
    'gltf_output_dir': '',
    'buffers_embed_data': True,
    'buffers_combine_data': False,
    'nodes_export_hidden': False,
    'nodes_global_matrix': mathutils.Matrix.Identity(4),
    'nodes_selected_only': False,
    'blocks_prune_unused': True,
    'shaders_data_storage': 'NONE',
    'meshes_apply_modifiers': True,
    'meshes_interleave_vertex_data': True,
    'images_data_storage': 'COPY',
    'asset_profile': 'WEB',
    'ext_export_physics': False,
    'images_allow_srgb': False
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
    'WEB': {'api': 'WebGL', 'version': '1.0.3'},
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
        self.co = mesh.vertices[vert_idx].co.freeze()
        self.normal = loop.normal.freeze()
        self.uvs = tuple(layer.data[loop_idx].uv.freeze() for layer in mesh.uv_layers)
        self.colors = tuple(layer.data[loop_idx].color.freeze() for layer in mesh.vertex_colors)
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

    def export_views(self, state):
        gltf_views = []

        for key, value in self.buffer_views.items():
            gltf = {
                'byteLength': value['bytelength'],
                'byteOffset': value['byteoffset'],
            }

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
                'byteStride': value.byte_stride,
                'componentType': value.component_type,
                'count': value.count,
                'min': value.min[:value.type_size],
                'max': value.max[:value.type_size],
                'type': value.data_type,
            }

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


def export_materials(state, materials):
    def export_material(material):
        all_textures = [
            slot for slot in material.texture_slots
            if slot and slot.texture.type == 'IMAGE'
        ]
        diffuse_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_diffuse
        ]
        emission_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_emit
        ]
        specular_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_spec
        ]

        diffuse_color = list((material.diffuse_color * material.diffuse_intensity)[:])
        diffuse_color += [material.alpha]
        emission_color = list((material.diffuse_color * material.emit)[:])
        emission_color += [material.alpha]
        specular_color = list((material.specular_color * material.specular_intensity)[:])
        specular_color += [material.specular_alpha]

        technique = 'PHONG'
        if material.use_shadeless:
            technique = 'CONSTANT'
            emission_textures = diffuse_textures
            emission_color = diffuse_color
        elif material.specular_intensity == 0.0:
            technique = 'LAMBERT'
        elif material.specular_shader == 'BLINN':
            technique = 'BLINN'

        gltf = {
            'extensions': {
                'KHR_materials_common': {
                    'technique': technique,
                    'values': {
                        'ambient': ([material.ambient]*3) + [1.0],
                        'diffuse': diffuse_textures[-1] if diffuse_textures else diffuse_color,
                        'doubleSided': not material.game_settings.use_backface_culling,
                        'emission': emission_textures[-1] if emission_textures else emission_color,
                        'specular': specular_textures[-1] if specular_textures else specular_color,
                        'shininess': material.specular_hardness,
                        'transparency': material.alpha,
                        'transparent': material.use_transparency,
                    }
                }
            },
            'name': material.name,
        }

        gltf_values = gltf['extensions']['KHR_materials_common']['values']
        for prop in ('diffuse', 'emission', 'specular'):
            if hasattr(gltf_values[prop], 'blender_type'):
                ref = gltf_values[prop]
                ref.source = gltf_values
                ref.prop = prop
                state['references'].append(ref)
        return gltf

    exp_materials = []
    for material in materials:
        if state['settings']['shaders_data_storage'] == 'NONE':
            exp_materials.append(export_material(material))
        else:
            # Handle shaders
            shader_data = gpu.export_shader(bpy.context.scene, material)
            if state['settings']['asset_profile'] == 'DESKTOP':
                shader_converter.to_130(shader_data)
            else:
                shader_converter.to_web(shader_data)

            storage_setting = state['settings']['shaders_data_storage']
            if storage_setting == 'EMBED':
                fs_bytes = shader_data['fragment'].encode()
                fs_uri = 'data:text/plain;base64,' + base64.b64encode(fs_bytes).decode('ascii')
                vs_bytes = shader_data['vertex'].encode()
                vs_uri = 'data:text/plain;base64,' + base64.b64encode(vs_bytes).decode('ascii')
            elif storage_setting == 'EXTERNAL':
                names = [
                    bpy.path.clean_name(name) + '.glsl'
                    for name in (material.name+'VS', material.name+'FS')
                ]
                data = (shader_data['vertex'], shader_data['fragment'])
                for name, data in zip(names, data):
                    filename = os.path.join(state['settings']['gltf_output_dir'], name)
                    with open(filename, 'w') as fout:
                        fout.write(data)
                vs_uri, fs_uri = names
            else:
                print(
                    'Encountered unknown option ({}) for shaders_data_storage setting'
                    .format(storage_setting)
                )

            state['shaders'].append({'type': 35632, 'uri': fs_uri})
            state['shaders'].append({'type': 35633, 'uri': vs_uri})

            # Handle programs
            state['programs'].append({
                'attributes': [a['varname'] for a in shader_data['attributes']],
                'fragmentShader': 'shader_{}_FS'.format(material.name),
                'vertexShader': 'shader_{}_VS'.format(material.name),
            })

            # Handle parameters/values
            values = {}
            parameters = {}
            for attribute in shader_data['attributes']:
                name = attribute['varname']
                semantic = gpu_luts.TYPE_TO_SEMANTIC[attribute['type']]
                _type = gpu_luts.DATATYPE_TO_GLTF_TYPE[attribute['datatype']]
                parameters[name] = {'semantic': semantic, 'type': _type}

            for uniform in shader_data['uniforms']:
                valname = gpu_luts.TYPE_TO_NAME.get(uniform['type'], uniform['varname'])
                rnaname = valname
                semantic = None
                node = None
                value = None

                if uniform['varname'] == 'bl_ModelViewMatrix':
                    semantic = 'MODELVIEW'
                elif uniform['varname'] == 'bl_ProjectionMatrix':
                    semantic = 'PROJECTION'
                elif uniform['varname'] == 'bl_NormalMatrix':
                    semantic = 'MODELVIEWINVERSETRANSPOSE'
                else:
                    if uniform['type'] in gpu_luts.LAMP_TYPES:
                        node = uniform['lamp'].name
                        valname = node + '_' + valname
                        semantic = gpu_luts.TYPE_TO_SEMANTIC.get(uniform['type'], None)
                        if not semantic:
                            lamp_obj = bpy.data.objects[node]
                            value = getattr(lamp_obj.data, rnaname)
                    elif uniform['type'] in gpu_luts.MIST_TYPES:
                        valname = 'mist_' + valname
                        mist_settings = bpy.context.scene.world.mist_settings
                        if valname == 'mist_color':
                            value = bpy.context.scene.world.horizon_color
                        else:
                            value = getattr(mist_settings, rnaname)

                        if valname == 'mist_falloff':
                            if value == 'QUADRATIC':
                                value = 0.0
                            elif value == 'LINEAR':
                                value = 1.0
                            else:
                                value = 2.0
                    elif uniform['type'] in gpu_luts.WORLD_TYPES:
                        world = bpy.context.scene.world
                        value = getattr(world, rnaname)
                    elif uniform['type'] in gpu_luts.MATERIAL_TYPES:
                        converter = gpu_luts.DATATYPE_TO_CONVERTER[uniform['datatype']]
                        value = converter(getattr(material, rnaname))
                        values[valname] = value
                    elif uniform['type'] == gpu.GPU_DYNAMIC_SAMPLER_2DIMAGE:
                        texture_slots = [
                            slot for slot in material.texture_slots
                            if slot and slot.texture.type == 'IMAGE'
                        ]
                        for slot in texture_slots:
                            if slot.texture.image.name == uniform['image'].name:
                                value = 'texture_' + slot.texture.name
                                values[uniform['varname']] = value
                    else:
                        print('Unconverted uniform:', uniform)

                parameter = {}
                if semantic:
                    parameter['semantic'] = semantic
                    if node:
                        parameter['node'] = 'node_' + node
                elif value:
                    parameter['value'] = gpu_luts.DATATYPE_TO_CONVERTER[uniform['datatype']](value)
                else:
                    parameter['value'] = None

                if uniform['type'] == gpu.GPU_DYNAMIC_SAMPLER_2DIMAGE:
                    parameter['type'] = 35678  # SAMPLER_2D
                else:
                    parameter['type'] = gpu_luts.DATATYPE_TO_GLTF_TYPE[uniform['datatype']]
                parameters[valname] = parameter
                uniform['valname'] = valname

            # Handle techniques
            tech_name = 'technique_' + material.name
            state['techniques'].append({
                'parameters': parameters,
                'program': 'program_' + material.name,
                'attributes': {a['varname']: a['varname'] for a in shader_data['attributes']},
                'uniforms': {u['varname']: u['valname'] for u in shader_data['uniforms']},
            })

            exp_materials.append({'technique': tech_name, 'values': values})
            # exp_materials[material.name] = {}

    return exp_materials


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
    view = buf.add_view(vertex_size * num_verts, Buffer.ARRAY_BUFFER)

    # Interleave
    if state['settings']['meshes_interleave_vertex_data']:
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
    skin_view = skin_buf.add_view(skin_vertex_size * num_verts, Buffer.ARRAY_BUFFER)
    jdata = skin_buf.add_accessor(
        skin_view,
        0,
        skin_vertex_size,
        Buffer.FLOAT,
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
            tdata[j][i * 2] = uv.x
            if state['settings']['asset_profile'] == 'WEB':
                tdata[j][i * 2 + 1] = 1.0 - uv.y
            else:
                tdata[j][i * 2 + 1] = uv.y

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
        if OES_ELEMENT_INDEX_UINT not in state['extensions_used']:
            state['extensions_used'].append(OES_ELEMENT_INDEX_UINT)

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

        index_view = buf.add_view(istride * len(prim), Buffer.ELEMENT_ARRAY_BUFFER)
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
            gltf_attrs['JOINT'] = Reference('accessors', jdata.name, gltf_attrs, 'JOINT')
            state['references'].append(gltf_attrs['JOINT'])
            gltf_attrs['WEIGHT'] = Reference('accessors', wdata.name, gltf_attrs, 'WEIGHT')
            state['references'].append(gltf_attrs['WEIGHT'])

        gltf_prim['attributes'] = gltf_attrs

        # Add the material reference after checking that it is valid
        if mat:
            gltf_prim['material'] = Reference('materials', mat, gltf_prim, 'material')
            state['references'].append(gltf_prim['material'])

        gltf_mesh['primitives'].append(gltf_prim)

    state['input']['buffers'].append(buf)
    if is_skinned:
        state['input']['buffers'].append(skin_buf)
        gltf_mesh['skin'] = Reference('skins', mesh.name, gltf_mesh, 'skin')
        state['references'].append(gltf_mesh['skin'])

    return gltf_mesh


def export_skins(state):
    def export_skin(obj, mesh_name):
        arm = obj.find_armature()

        bind_shape_mat = obj.matrix_world * arm.matrix_world.inverted()
        bone_groups = [group for group in obj.vertex_groups if group.name in arm.data.bones]

        gltf_skin = {
            'bindShapeMatrix': togl(bind_shape_mat),
            'name': obj.name,
        }
        gltf_skin['jointNames'] = [
            Reference('bones', arm.data.bones[group.name].as_pointer(), None, None)
            for group in bone_groups
        ]
        for i, ref in enumerate(gltf_skin['jointNames']):
            ref.source = gltf_skin['jointNames']
            ref.prop = i
            state['references'].append(ref)

        element_size = 16 * 4
        num_elements = len(bone_groups)
        buf = Buffer('IBM_{}_skin'.format(obj.name))
        buf_view = buf.add_view(element_size * num_elements, None)
        idata = buf.add_accessor(buf_view, 0, element_size, Buffer.FLOAT, num_elements, Buffer.MAT4)

        for i, group in enumerate(bone_groups):
            bone = arm.data.bones[group.name]
            mat = togl(bone.matrix_local.inverted())
            for j in range(16):
                idata[(i * 16) + j] = mat[j]

        gltf_skin['inverseBindMatrices'] = Reference(
            'accessors',
            idata.name,
            gltf_skin,
            'inverseBindMatrices'
        )
        state['references'].append(gltf_skin['inverseBindMatrices'])
        state['input']['buffers'].append(buf)

        state['input']['skins'].append(SimpleID(mesh_name))

        return gltf_skin

    return [export_skin(obj, mesh_name) for mesh_name, obj in state['skinned_meshes'].items()]


def export_light(light):
    def calc_att():
        linear_factor = 0
        quad_factor = 0

        if light.falloff_type == 'INVERSE_LINEAR':
            linear_factor = 1 / light.distance
        elif light.falloff_type == 'INVERSE_SQUARE':
            quad_factor = 1 / light.distance
        elif light.falloff_type == 'LINEAR_QUADRATIC_WEIGHTED':
            linear_factor = light.linear_attenuation * (1 / light.distance)
            quad_factor = light.quadratic_attenuation * (1 / (light.distance * light.distance))

        return linear_factor, quad_factor

    gltf_light = {}
    if light.type == 'SUN':
        gltf_light = {
            'directional': {
                'color': (light.color * light.energy)[:],
            },
            'type': 'directional',
        }
    elif light.type == 'POINT':
        linear_factor, quad_factor = calc_att()
        gltf_light = {
            'point': {
                'color': (light.color * light.energy)[:],

                # TODO: grab values from Blender lamps
                'constantAttenuation': 1,
                'linearAttenuation': linear_factor,
                'quadraticAttenuation': quad_factor,
            },
            'type': 'point',
        }
    elif light.type == 'SPOT':
        linear_factor, quad_factor = calc_att()
        gltf_light = {
            'spot': {
                'color': (light.color * light.energy)[:],

                # TODO: grab values from Blender lamps
                'constantAttenuation': 1.0,
                'fallOffAngle': 3.14159265,
                'fallOffExponent': 0.0,
                'linearAttenuation': linear_factor,
                'quadraticAttenuation': quad_factor,
            },
            'type': 'spot',
        }
    else:
        print("Unsupported lamp type on {}: {}".format(light.name, light.type))
        gltf_light = {'type': 'unsupported'}

    gltf_light['name'] = light.name
    extras = _get_custom_properties(light)
    if extras:
        gltf_light['extras'] = extras
    return gltf_light


def export_node(state, obj):
    node = {
        'name': obj.name,
        'children': [],
    }
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
        node['meshes'] = []
        node['meshes'].append(Reference('meshes', mesh.name, node['meshes'], 0))
        state['references'].append(node['meshes'][0])
        armature = obj.find_armature()
        if armature:
            bone_names = [b.as_pointer() for b in armature.data.bones if b.parent is None]
            node['skeletons'] = []
            node['skeletons'].extend([
                Reference('bones', bone, node['skeletons'], i)
                for i, bone in enumerate(bone_names)
            ])
            for ref in node['skeletons']:
                state['references'].append(ref)
            state['skinned_meshes'][mesh.name] = obj
    elif obj.type == 'LAMP':
        if state['settings']['shaders_data_storage'] == 'NONE':
            if 'extensions' not in node:
                node['extensions'] = {}
            ext = node['extensions']['KHR_materials_common'] = {}
            ext['light'] = Reference('lamps', obj.data.name, ext, 'light')
            state['references'].append(ext['light'])
    elif obj.type == 'CAMERA':
        node['camera'] = Reference('cameras', obj.data.name, node, 'camera')
        state['references'].append(node['camera'])
    elif obj.type == 'EMPTY' and obj.dupli_group is not None:
        # Expand dupli-groups
        # TODO: list of references
        node['children'] += ['node_' + i.name for i in obj.dupli_group.objects]
    elif obj.type == 'ARMATURE':
        for i, bone in enumerate(obj.data.bones):
            state['input']['bones'].append(SimpleID(bone.as_pointer(), bone))
        if not node['children']:
            node['children'] = []
        offset = len(node['children'])
        root_bones = [
            Reference('bones', b.as_pointer(), node['children'], i + offset)
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
        'name': bone.name,
    }
    gltf_joint['jointName'] = Reference('bones', bone.as_pointer(), gltf_joint, 'jointName')
    state['references'].append(gltf_joint['jointName'])
    gltf_joint['children'] = [
        Reference('bones', child.as_pointer(), None, None) for child in bone.children
    ]
    for i, ref in enumerate(gltf_joint['children']):
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
        state['references'].extend(result['estras']['hidden_nodes'])

    return result


def export_buffers(state):
    if state['settings']['buffers_combine_data']:
        buffers = [functools.reduce(lambda x, y: x+y, state['input']['buffers'], Buffer('empty'))]
        state['input']['buffers'] = buffers
    else:
        buffers = state['input']['buffers']

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
        gltf_samplers = {}

        tbuf = Buffer('{}_time'.format(action.name))
        tbv = tbuf.add_view(num_frames * 1 * 4, None)
        tdata = tbuf.add_accessor(tbv, 0, 1 * 4, Buffer.FLOAT, num_frames, Buffer.SCALAR)
        time = 0
        for i in range(num_frames):
            tdata[i] = time
            time += state['animation_dt']
        state['input']['buffers'].append(tbuf)
        time_parameter_name = '{}_time_parameter'.format(action.name)
        ref = Reference('accessors', tdata.name, gltf_parameters, time_parameter_name)
        gltf_parameters[time_parameter_name] = ref
        state['references'].append(ref)

        for targetid, chan in channels.items():
            buf = Buffer('{}_{}'.format(targetid, action.name))
            lbv = buf.add_view(num_frames * 3 * 4, None)
            ldata = buf.add_accessor(lbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)
            rbv = buf.add_view(num_frames * 4 * 4, None)
            rdata = buf.add_accessor(rbv, 0, 4 * 4, Buffer.FLOAT, num_frames, Buffer.VEC4)
            sbv = buf.add_view(num_frames * 3 * 4, None)
            sdata = buf.add_accessor(sbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)

            for i in range(num_frames):
                loc, rot, scale = decompose(chan[i])
                for j in range(3):
                    ldata[(i * 3) + j] = loc[j]
                    sdata[(i * 3) + j] = scale[j]
                for j in range(4):
                    rdata[(i * 4) + j] = rot[j]

            state['input']['buffers'].append(buf)

            is_bone = False
            if targetid != obj.name:
                is_bone = True
                targetid = bpy.data.armatures[obj.data.name].bones[targetid].as_pointer()

            for path in ('translation', 'rotation', 'scale'):
                sampler_name = '{}_{}_{}_sampler'.format(action.name, targetid, path)
                parameter_name = '{}_{}_{}_parameter'.format(action.name, targetid, path)

                id_ref = Reference('bones' if is_bone else 'objects', targetid, None, 'id')
                gltf_channels.append({
                    'sampler': sampler_name,
                    'target': {
                        'id': targetid,
                        'path': path,
                    }
                })
                id_ref.source = gltf_channels[-1]['target']
                state['references'].append(id_ref)

                gltf_samplers[sampler_name] = {
                    'input': time_parameter_name,
                    'interpolation': 'LINEAR',
                    'output': parameter_name,
                }

                accessor_name = {
                    'translation': ldata.name,
                    'rotation': rdata.name,
                    'scale': sdata.name,
                }[path]
                accessor_ref = Reference(
                    'accessors',
                    accessor_name,
                    gltf_parameters,
                    parameter_name
                )
                gltf_parameters[parameter_name] = accessor_ref
                state['references'].append(accessor_ref)

        gltf_action = {
            'name': action.name,
            'channels': gltf_channels,
            'samplers': gltf_samplers,
            'parameters': gltf_parameters,
        }

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


def insert_root_nodes(gltf_data, root_matrix):
    for name, scene in gltf_data['scenes'].items():
        node_name = 'node_{}_root'.format(name)
        # Generate a new root node for each scene
        gltf_data['nodes'][node_name] = {
            'children': scene['nodes'],
            'matrix': root_matrix,
            'name': node_name,
        }

        # Replace scene node lists to just point to the new root nodes
        scene['nodes'] = [node_name]


def build_string_refmap(input_data):
    in_out_map = {
        'objects': 'nodes',
        'bones': 'nodes',
        'lamps': 'lights'
    }
    refmap = {}
    node_offset = len(input_data['objects'])
    for key, value in input_data.items():
        refmap.update({
            (key, data.name): '{}_{}'.format(
                in_out_map.get(key, key),
                i + (node_offset if key == 'bones' else 0)
            )
            for i, data in enumerate(value)
        })
    return refmap


def build_int_refmap(input_data):
    refmap = {}
    node_offset = len(input_data['objects'])
    for key, value in input_data.items():
        refmap.update({
            (key, data.name): i + (node_offset if key == 'bones' else 0)
            for i, data in enumerate(value)})
    return refmap


def export_gltf(scene_delta, settings=None):
    # Fill in any missing settings with defaults
    if not settings:
        settings = {}
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)

    # Initialize export state
    state = {
        'settings': settings,
        'animation_dt': 1.0 / bpy.context.scene.render.fps,
        'shaders': [],
        'programs': [],
        'techniques': [],
        'mod_meshes': {},
        'skinned_meshes': {},
        'extensions_used': [],
        'input': {
            'buffers': [],
            'accessors': [],
            'bufferViews': [],
            'objects': [],
            'bones': [],
            'samplers': [SimpleID('default')],
            'skins': [],
        },
        'output': {},
        'references': [],
    }
    state['input'].update(scene_delta)

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
    state['output']['samplers'] = [{}]
    state['output']['animations'] = export_animations(state, scene_delta.get('actions', []))
    state['output']['materials'] = export_materials(state, scene_delta.get('materials', []))
    state['output']['skins'] = export_skins(state)
    state['output']['programs'] = state['programs']
    state['output']['shaders'] = state['shaders']
    state['output']['techniques'] = state['techniques']
    state['output']['nodes'].extend([
        export_joint(state, sid.data) for sid in state['input']['bones']
    ])

    gltf = {
        'asset': {
            'version': '1.0',
            'profile': PROFILE_MAP[settings['asset_profile']]
        },
        'extensions': {},
        'extensionsUsed': [],
    }
    scene_ref = Reference('scenes', bpy.context.scene.name, gltf, 'scene')
    scene_ref.value = 0
    state['references'].append(scene_ref)

    if settings['shaders_data_storage'] == 'NONE':
        gltf['extensionsUsed'].append('KHR_materials_common')
        gltf['extensions']['KHR_materials_common'] = {
            'lights': {
                'lights_{}'.format(i): export_light(lamp)
                for i, lamp in enumerate(scene_delta.get('lamps', []))
            }
        }

    state['refmap'] = build_int_refmap(state['input'])
    for ext_exporter in settings['extension_exporters']:
        ext_exporter.export(state)

    state['output'].update(export_buffers(state))
    state['output'] = {key: value for key, value in state['output'].items() if value != []}
    gltf.update({'glExtensionsUsed': state['extensions_used']})

    # Convert lists to dictionaries
    state['output'] = {
        key: {
            '{}_{}'.format(key, i): data for i, data in enumerate(value)
        } for key, value in state['output'].items()
    }
    gltf.update(state['output'])

    # Insert root nodes if axis conversion is needed
    if settings['nodes_global_matrix'] != mathutils.Matrix.Identity(4):
        insert_root_nodes(gltf, togl(settings['nodes_global_matrix']))

    # Resolve references
    refmap = build_string_refmap(state['input'])
    # refmap = build_string_refmap(scene_delta)
    for ref in state['references']:
        ref.source[ref.prop] = refmap[(ref.blender_type, ref.blender_name)]

    # Remove any temporary meshes from applying modifiers
    for mesh in state['mod_meshes'].values():
        bpy.data.meshes.remove(mesh)

    return gltf
