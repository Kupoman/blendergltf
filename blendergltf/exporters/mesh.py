from distutils.version import StrictVersion as Version

import mathutils

from .base import BaseExporter
from .common import (
    Buffer,
    Reference,
    SimpleID,
)


OES_ELEMENT_INDEX_UINT = 'OES_element_index_uint'


class OffsetTracker:
    def __init__(self):
        self.value = 0

    def get(self):
        return self.value

    def add(self, value):
        self.value += value


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
        self.uvs = tuple(
            layer.data[loop_idx].uv[:]
            for layer in mesh.uv_layers
            if layer.data
        )
        self.colors = tuple(
            tuple(
                list(layer.data[loop_idx].color) + [1.0] * (4 - len(layer.data[loop_idx].color))
            )
            for layer in mesh.vertex_colors
            if layer.data
        )
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


def requires_int_indices(vert_list):
    return len(vert_list) > 65535


def get_vert_list(mesh, has_shape_keys):
    mesh.calc_normals_split()
    mesh.calc_tessface()

    # Remove duplicate verts with dictionary hashing (causes problems with shape keys)
    if has_shape_keys:
        vert_list = [Vertex(mesh, loop) for loop in mesh.loops]
    else:
        vert_list = list({Vertex(mesh, loop): 0 for loop in mesh.loops}.keys())

    return vert_list


def gather_primitives(state, mesh, vert_lists):
    # For each material, make an empty primitive set.
    # This dictionary maps material names to list of indices that form the
    # part of the mesh that the material should be applied to.
    mesh_materials = [ma for ma in mesh.materials if ma in state['input']['materials']]
    prims = {ma.name if ma else '': [] for ma in mesh_materials}
    if not prims:
        prims = {'': []}

    # Index data
    # Map loop indices to vertices
    vert_dict = {i: vertex for vertex in vert_lists[0] for i in vertex.loop_indices}

    for poly in mesh.polygons:
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
    return prims


def fill_data(acc, iterator):
    for i, data in enumerate(iterator):
        size = len(data)
        for j, element in enumerate(data):
            acc[(i * size + j)] = element


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

        vert_lists = [get_vert_list(blender_data, len(shape_keys) > 0)]
        vert_lists += [
            get_vert_list(key_mesh, True)
            for key_mesh in [key[1] for key in shape_keys]
        ]

        # Process mesh data and gather attributes
        buffer = Buffer(mesh_name)
        gltf_attrs = cls.export_attributes(state, buffer, mesh_name, None, vert_lists[0])

        # Process shape keys
        targets = [
            cls.export_attributes(
                state,
                Buffer(key_mesh.name),
                key_mesh.name,
                vert_lists[0],
                vert_lists[i + 1]
            )
            for i, key_mesh in enumerate([key[1] for key in shape_keys])
        ]

        if shape_keys:
            gltf_mesh['weights'] = [key[0] for key in shape_keys]

        prims = gather_primitives(state, blender_data, vert_lists)

        if requires_int_indices(vert_lists[0]):
            # Use the integer index extension
            if OES_ELEMENT_INDEX_UINT not in state['gl_extensions_used']:
                state['gl_extensions_used'].append(OES_ELEMENT_INDEX_UINT)
            itype = Buffer.UNSIGNED_INT
        else:
            itype = Buffer.UNSIGNED_SHORT

        gltf_mesh['primitives'] = [
            cls.export_primitive(state, buffer, mat, indices, itype, gltf_attrs, targets)
            for mat, indices in prims.items() if indices
        ]

        return gltf_mesh

    @classmethod
    def export_primitive(cls, state, buf, material, indices, index_type, attributes, targets):
        index_stride = 4 if index_type == Buffer.UNSIGNED_INT else 2

        # Pad index buffer if necessary to maintain a size that is a multiple of 4
        view_length = index_stride * len(indices)
        view_length = view_length + ((4 - view_length % 4) % 4)

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
    def export_attributes(cls, state, buf, mesh_name, base_vert_list, vert_list):
        gltf_attrs = {}
        is_skinned = mesh_name in state['skinned_meshes']

        color_size = 4 if state['settings']['meshes_vertex_color_alpha'] else 3
        num_uv_layers = len(vert_list[0].uvs)
        num_col_layers = len(vert_list[0].colors)
        vertex_size = (3 + 3 + num_uv_layers * 2 + num_col_layers * color_size) * 4
        if is_skinned:
            vertex_size += (4 + 4) * 4
        num_verts = len(vert_list)

        if state['settings']['meshes_interleave_vertex_data']:
            view = buf.add_view(vertex_size * num_verts, vertex_size, Buffer.ARRAY_BUFFER)
        else:
            view = None

        offset = OffsetTracker()

        def create_attr_accessor(name, component_type, component_count):
            component_size = 1 if component_type == Buffer.UNSIGNED_BYTE else 4
            if not view:
                stride = component_size * component_count
                buffer = Buffer(mesh_name + '_' + name)
                state['buffers'].append(buffer)
                state['input']['buffers'].append(SimpleID(buffer.name))
                _view = buffer.add_view(stride * num_verts, stride, Buffer.ARRAY_BUFFER)
                interleaved = False
            else:
                _view = view
                buffer = buf
                stride = vertex_size
                interleaved = True

            data_type = [Buffer.SCALAR, Buffer.VEC2, Buffer.VEC3, Buffer.VEC4][component_count - 1]
            _offset = offset.get()
            acc = buffer.add_accessor(_view, _offset, stride, component_type, num_verts, data_type)
            if interleaved:
                offset.add(component_size * component_count)
            return acc

        def add_attribute(name, num_components, component_type=Buffer.FLOAT):
            acc = create_attr_accessor(name, component_type, num_components)
            gltf_attrs[name] = Reference('accessors', acc.name, gltf_attrs, name)
            state['references'].append(gltf_attrs[name])
            return acc

        vdata = add_attribute('POSITION', 3)
        ndata = add_attribute('NORMAL', 3)
        if not base_vert_list:
            tdata = [
                add_attribute('TEXCOORD_' + str(i), 2)
                for i in range(num_uv_layers)
            ]
            cdata = [
                add_attribute('COLOR_' + str(i), color_size)
                for i in range(num_col_layers)
            ]

        # Copy vertex data
        if base_vert_list:
            fill_data(vdata, (
                [a - b for a, b in zip(v.co, b.co)]
                for v, b in zip(vert_list, base_vert_list)
            ))
            fill_data(ndata, (
                [a - b for a, b in zip(v.normal, b.normal)]
                for v, b in zip(vert_list, base_vert_list)
            ))
        else:
            fill_data(vdata, (v.co for v in vert_list))
            fill_data(ndata, (v.normal for v in vert_list))
            for i, accessor in enumerate(cdata):
                if state['settings']['meshes_vertex_color_alpha']:
                    fill_data(accessor, (v.colors[i] for v in vert_list))
                else:
                    fill_data(accessor, (v.colors[i][:3] for v in vert_list))
            for i, accessor in enumerate(tdata):
                if state['settings']['asset_profile'] == 'WEB':
                    fill_data(accessor, ((v.uvs[i][0], 1.0 - v.uvs[i][1]) for v in vert_list))
                else:
                    fill_data(accessor, (v.uvs[i] for v in vert_list))
            for i, vtx in enumerate(vert_list):
                vtx.index = i

        state['buffers'].append(buf)
        state['input']['buffers'].append(SimpleID(buf.name))

        if is_skinned:
            if state['version'] < Version('2.0'):
                joint_key = 'JOINT'
                weight_key = 'WEIGHT'
            else:
                joint_key = 'JOINTS_0'
                weight_key = 'WEIGHTS_0'

            jdata = add_attribute(joint_key, 4, Buffer.UNSIGNED_BYTE)
            fill_data(jdata, (v.joint_indexes for v in vert_list))
            wdata = add_attribute(weight_key, 4)
            fill_data(wdata, (v.weights for v in vert_list))

        return gltf_attrs
