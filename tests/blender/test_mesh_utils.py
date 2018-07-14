import unittest

import bpy
from mathutils import (
    Vector,
    Color,
)

from blendergltf.blendergltf import utils


class TestMeshUtils(unittest.TestCase):
    def test_extract_attributes_basic(self):
        mesh = bpy.data.meshes['Triangle']
        attrs = utils.mesh.extract_attributes(mesh)
        self.assertEqual(list(attrs['indices']), [[0, 2, 1]])
        self.assertEqual(list(attrs['positions'])[0], Vector([-1.0, -1.0, 0.0]))
        self.assertEqual(list(attrs['normals'])[0], Vector([0.0, 0.0, 1.0]))

    def test_extract_attributes_quad(self):
        mesh = bpy.data.meshes['Quad']
        attrs = utils.mesh.extract_attributes(mesh)
        indices = list(attrs['indices'])
        self.assertEqual(len(indices), 2)

    def test_extract_attributes_ngon(self):
        mesh = bpy.data.meshes['Ngon']
        attrs = utils.mesh.extract_attributes(mesh)
        indices = list(attrs['indices'])
        self.assertEqual(len(indices), 3)

    def test_vertex_colors(self):
        mesh = bpy.data.meshes['Triangle']
        attrs = utils.mesh.extract_attributes(mesh)
        colors = list(attrs['colors'][0])
        self.assertEqual(colors[0], Color([1.0, 0.0, 0.0]))


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
