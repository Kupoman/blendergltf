import unittest

import bpy
import bmesh
from mathutils import (
    Vector,
    Color,
)

from blendergltf.blendergltf import utils


def add_vcolors(mesh):
    vertex_colors = mesh.vertex_colors.new()
    for item in  vertex_colors.data:
        item.color = (1.0, 0.0, 0.0)


def add_uv_layer(mesh):
    mesh.uv_layers.new()


def mesh_from_bmesh(bmesh_mesh, name='tmp_mesh'):
    mesh = bpy.data.meshes.new(name)
    bmesh_mesh.to_mesh(mesh)
    bmesh_mesh.free()
    return mesh


def create_tri():
    temp = bmesh.new()
    vert1 = temp.verts.new((-1.0, -1.0, 0.0))
    vert2 = temp.verts.new((1.0, 1.0, 0.0))
    vert3 = temp.verts.new((-1.0, 1.0, 0.0))
    temp.faces.new((vert1, vert2, vert3))
    return mesh_from_bmesh(temp)


def create_quad():
    temp = bmesh.new()
    vert1 = temp.verts.new((-1.0, -1.0, 0.0))
    vert2 = temp.verts.new((-1.0, 1.0, 0.0))
    vert3 = temp.verts.new((1.0, 1.0, 0.0))
    vert4 = temp.verts.new((1.0, -1.0, 0.0))
    temp.faces.new((vert1, vert2, vert3, vert4))
    return mesh_from_bmesh(temp)


def create_ngon():
    temp = bmesh.new()
    vert1 = temp.verts.new((-1.0, -1.0, 0.0))
    vert2 = temp.verts.new((-1.0, 1.0, 0.0))
    vert3 = temp.verts.new((1.0, 1.0, 0.0))
    vert4 = temp.verts.new((2.0, 0.0, 0.0))
    vert5 = temp.verts.new((1.0, -1.0, 0.0))
    temp.faces.new((vert1, vert2, vert3, vert4, vert5))
    return mesh_from_bmesh(temp)


def create_two_tris():
    temp = bmesh.new()
    vert1 = temp.verts.new((-1.0, -1.0, 0.0))
    vert2 = temp.verts.new((-1.0, 1.0, 0.0))
    vert3 = temp.verts.new((1.0, 1.0, 0.0))
    vert4 = temp.verts.new((1.0, -1.0, 0.0))
    temp.faces.new((vert1, vert2, vert3))
    temp.faces.new((vert3, vert4, vert1))
    return mesh_from_bmesh(temp)


class TestMeshUtils(unittest.TestCase):
    def test_extract_attributes_basic(self):
        mesh = create_tri()
        attrs = utils.mesh.extract_attributes(mesh)
        self.assertEqual(list(attrs['indices']), [[0, 1, 2]])
        self.assertEqual(list(attrs['positions'])[0], Vector([-1.0, -1.0, 0.0]))
        self.assertEqual(list(attrs['normals'])[0], Vector([0.0, 0.0, 1.0]))

    def test_extract_attributes_quad(self):
        mesh = create_quad()
        attrs = utils.mesh.extract_attributes(mesh)
        indices = list(attrs['indices'])
        self.assertEqual(len(indices), 2)

    def test_extract_attributes_ngon(self):
        mesh = create_ngon()
        attrs = utils.mesh.extract_attributes(mesh)
        indices = list(attrs['indices'])
        self.assertEqual(len(indices), 3)

    def test_vertex_colors(self):
        mesh = create_tri()
        add_vcolors(mesh)
        attrs = utils.mesh.extract_attributes(mesh)
        colors = list(attrs['colors'][0])
        self.assertEqual(colors[0], Color([1.0, 0.0, 0.0]))


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
