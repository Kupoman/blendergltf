from distutils.version import StrictVersion as Version

import mathutils

from .base import BaseExporter
from .common import (
    Buffer,
    Reference,
    SimpleID,
)


OES_ELEMENT_INDEX_UINT = 'OES_element_index_uint'


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


class MeshExporter(BaseExporter):
    gltf_key = 'meshes'
    blender_key = 'meshes'

    @classmethod
    def export(cls, state, blender_data):
        # glTF data
        mesh_name = blender_data.name
        blender_data = state['mod_meshes'].get(blender_data.name, blender_data)
        gltf_mesh = {
            'name': mesh_name,
            'primitives': [],
        }

        extras = BaseExporter.get_custom_properties(blender_data)
        if extras:
            gltf_mesh['extras'] = extras

        shape_keys = state['shape_keys'].get(mesh_name, [])

        # Process mesh data and gather attributes
        gltf_attrs, buf, vert_list = cls.export_attributes(state, blender_data, mesh_name, None)

        # Process shape keys
        targets = [
            cls.export_attributes(state, key_mesh, key_mesh.name, vert_list)[0]
            for key_mesh in [key[1] for key in shape_keys]
        ]

        if shape_keys:
            gltf_mesh['weights'] = [key[0] for key in shape_keys]

        # For each material, make an empty primitive set.
        # This dictionary maps material names to list of indices that form the
        # part of the mesh that the material should be applied to.
        mesh_materials = [ma for ma in blender_data.materials if ma in state['input']['materials']]
        prims = {ma.name if ma else '': [] for ma in mesh_materials}
        if not prims:
            prims = {'': []}

        # Index data
        # Map loop indices to vertices
        vert_dict = {i: vertex for vertex in vert_list for i in vertex.loop_indices}

        max_vert_index = 0
        for poly in blender_data.polygons:
            # Find the primitive that this polygon ought to belong to (by
            # material).
            if not mesh_materials:
                prim = prims['']
            else:
                try:
                    mat = mesh_materials[poly.material_index]
                except IndexError:
                    # Polygon has a bad material index, so skip it
                    continue
                prim = prims[mat.name if mat else '']

            # Find the (vertex) index associated with each loop in the polygon.
            indices = [vert_dict[i].index for i in poly.loop_indices]
            coords = [mathutils.Vector(vert_dict[i].co) for i in poly.loop_indices]

            # Used to determine whether a mesh must be split.
            max_vert_index = max(max_vert_index, max(indices))

            if len(indices) == 3:
                # No triangulation necessary
                prim += indices
            elif len(indices) > 3:
                # Triangulation necessary
                triangles = mathutils.geometry.tessellate_polygon((coords,))
                for triangle in triangles:
                    prim += [indices[i] for i in triangle[::-1]]
            else:
                # Bad polygon
                raise RuntimeError(
                    "Invalid polygon with {} vertices.".format(len(indices))
                )

        if max_vert_index > 65535:
            # Use the integer index extension
            if OES_ELEMENT_INDEX_UINT not in state['gl_extensions_used']:
                state['gl_extensions_used'].append(OES_ELEMENT_INDEX_UINT)
            itype = Buffer.UNSIGNED_INT
        else:
            itype = Buffer.UNSIGNED_SHORT

        gltf_mesh['primitives'] = [
            cls.export_primitive(state, buf, mat, indices, itype, gltf_attrs, targets)
            for mat, indices in prims.items() if indices
        ]

        return gltf_mesh

    @classmethod
    def export_primitive(cls, state, buf, material, indices, index_type, attributes, targets):
        index_stride = 4 if index_type == Buffer.UNSIGNED_INT else 2

        # Pad index buffer if necessary to maintain a size that is a multiple of 4
        view_length = index_stride * len(indices)
        view_length = view_length + (4 - view_length % 4)

        index_view = buf.add_view(view_length, 0, Buffer.ELEMENT_ARRAY_BUFFER)
        idata = buf.add_accessor(
            index_view,
            0,
            index_stride,
            index_type,
            len(indices),
            Buffer.SCALAR
        )

        for i, index in enumerate(indices):
            idata[i] = index

        gltf_prim = {
            'attributes': attributes,
            'mode': 4,
        }

        gltf_prim['indices'] = Reference('accessors', idata.name, gltf_prim, 'indices')
        state['references'].append(gltf_prim['indices'])

        if targets:
            gltf_prim['targets'] = targets

        # Add the material reference after checking that it is valid
        if material:
            gltf_prim['material'] = Reference('materials', material, gltf_prim, 'material')
            state['references'].append(gltf_prim['material'])

        return gltf_prim

    @classmethod
    def export_attributes(cls, state, mesh, mesh_name, base_vert_list):
        is_skinned = mesh_name in state['skinned_meshes']
        is_morph_base = len(state['shape_keys'].get(mesh_name, [])) != 0

        mesh.calc_normals_split()
        mesh.calc_tessface()

        # Remove duplicate verts with dictionary hashing (causes problems with shape keys)
        if is_morph_base or base_vert_list:
            vert_list = [Vertex(mesh, loop) for loop in mesh.loops]
        else:
            vert_list = {Vertex(mesh, loop): 0 for loop in mesh.loops}.keys()

        color_type = Buffer.VEC3
        color_size = 3
        if state['settings']['meshes_vertex_color_alpha']:
            color_type = Buffer.VEC4
            color_size = 4

        num_uv_layers = len(mesh.uv_layers)
        num_col_layers = len(mesh.vertex_colors)
        vertex_size = (3 + 3 + num_uv_layers * 2 + num_col_layers * color_size) * 4

        buf = Buffer(mesh_name)

        num_verts = len(vert_list)

        if state['settings']['meshes_interleave_vertex_data']:
            view = buf.add_view(vertex_size * num_verts, vertex_size, Buffer.ARRAY_BUFFER)
            vdata = buf.add_accessor(view, 0, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
            ndata = buf.add_accessor(view, 12, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
            if not base_vert_list:
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
                        color_type
                    )
                    for i in range(num_col_layers)
                ]
        else:
            prop_buffer = Buffer(mesh_name + '_POSITION')
            state['buffers'].append(prop_buffer)
            state['input']['buffers'].append(SimpleID(prop_buffer.name))
            prop_view = prop_buffer.add_view(12 * num_verts, 12, Buffer.ARRAY_BUFFER)
            vdata = prop_buffer.add_accessor(prop_view, 0, 12, Buffer.FLOAT, num_verts, Buffer.VEC3)

            prop_buffer = Buffer(mesh_name + '_NORMAL')
            state['buffers'].append(prop_buffer)
            state['input']['buffers'].append(SimpleID(prop_buffer.name))
            prop_view = prop_buffer.add_view(12 * num_verts, 12, Buffer.ARRAY_BUFFER)
            ndata = prop_buffer.add_accessor(prop_view, 0, 12, Buffer.FLOAT, num_verts, Buffer.VEC3)

            if not base_vert_list:
                tdata = []
                for uv_layer in range(num_uv_layers):
                    prop_buffer = Buffer('{}_TEXCOORD_{}'.format(mesh_name, uv_layer))
                    state['buffers'].append(prop_buffer)
                    state['input']['buffers'].append(SimpleID(prop_buffer.name))
                    prop_view = prop_buffer.add_view(8 * num_verts, 8, Buffer.ARRAY_BUFFER)
                    tdata.append(
                        prop_buffer.add_accessor(
                            prop_view,
                            0,
                            8,
                            Buffer.FLOAT,
                            num_verts,
                            Buffer.VEC2
                        )
                    )
                cdata = []
                for col_layer in range(num_col_layers):
                    prop_buffer = Buffer('{}_COLOR_{}'.format(mesh_name, col_layer))
                    state['buffers'].append(prop_buffer)
                    state['input']['buffers'].append(SimpleID(prop_buffer.name))
                    prop_view = prop_buffer.add_view(
                        4 * color_size * num_verts,
                        4 * color_size,
                        Buffer.ARRAY_BUFFER
                    )
                    cdata.append(
                        prop_buffer.add_accessor(
                            prop_view,
                            0,
                            color_size * 4,
                            Buffer.FLOAT,
                            num_verts,
                            color_type
                        )
                    )

        # Copy vertex data
        if base_vert_list:
            vert_iter = [(i, v[0], v[1]) for i, v in enumerate(zip(vert_list, base_vert_list))]
            for i, vtx, base_vtx in vert_iter:
                co = [a - b for a, b in zip(vtx.co, base_vtx.co)]
                normal = [a - b for a, b in zip(vtx.normal, base_vtx.normal)]
                for j in range(3):
                    vdata[(i * 3) + j] = co[j]
                    ndata[(i * 3) + j] = normal[j]

        else:
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
                    cdata[j][i * color_size] = col[0]
                    cdata[j][i * color_size + 1] = col[1]
                    cdata[j][i * color_size + 2] = col[2]

                    if state['settings']['meshes_vertex_color_alpha']:
                        cdata[j][i * color_size + 3] = 1.0

        # Handle attribute references
        gltf_attrs = {}
        gltf_attrs['POSITION'] = Reference('accessors', vdata.name, gltf_attrs, 'POSITION')
        state['references'].append(gltf_attrs['POSITION'])

        gltf_attrs['NORMAL'] = Reference('accessors', ndata.name, gltf_attrs, 'NORMAL')
        state['references'].append(gltf_attrs['NORMAL'])

        if not base_vert_list:
            for i, accessor in enumerate(tdata):
                attr_name = 'TEXCOORD_' + str(i)
                gltf_attrs[attr_name] = Reference('accessors', accessor.name, gltf_attrs, attr_name)
                state['references'].append(gltf_attrs[attr_name])
            for i, accessor in enumerate(cdata):
                attr_name = 'COLOR_' + str(i)
                gltf_attrs[attr_name] = Reference('accessors', accessor.name, gltf_attrs, attr_name)
                state['references'].append(gltf_attrs[attr_name])

        state['buffers'].append(buf)
        state['input']['buffers'].append(SimpleID(buf.name))

        if is_skinned:
            skin_buf = Buffer('{}_skin'.format(mesh_name))

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

            for i, vtx in enumerate(vert_list):
                joints = vtx.joint_indexes
                weights = vtx.weights

                for j in range(4):
                    jdata[(i * 4) + j] = joints[j]
                    wdata[(i * 4) + j] = weights[j]

            if state['version'] < Version('2.0'):
                joint_key = 'JOINT'
                weight_key = 'WEIGHT'
            else:
                joint_key = 'JOINTS_0'
                weight_key = 'WEIGHTS_0'

            gltf_attrs[joint_key] = Reference('accessors', jdata.name, gltf_attrs, joint_key)
            state['references'].append(gltf_attrs[joint_key])
            gltf_attrs[weight_key] = Reference('accessors', wdata.name, gltf_attrs, weight_key)
            state['references'].append(gltf_attrs[weight_key])

            state['buffers'].append(skin_buf)
            state['input']['buffers'].append(SimpleID(skin_buf.name))

        return gltf_attrs, buf, vert_list
