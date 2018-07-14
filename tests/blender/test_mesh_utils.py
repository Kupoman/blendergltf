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
        self.assertEqual(len(attrs.indices[0]), 1)
        self.assertEqual(list(attrs.indices[0].iterator), [[0, 2, 1]])
        self.assertEqual(list(attrs.positions.iterator)[0], Vector([-1.0, -1.0, 0.0]))
        self.assertEqual(list(attrs.normals.iterator)[0], Vector([0.0, 0.0, 1.0]))
        self.assertEqual(list(attrs.colors[0].iterator)[0], Color([1.0, 0.0, 0.0]))
        self.assertEqual(list(attrs.uvs[0].iterator)[1], Vector([1.0, 1.0]))

    def test_extract_attributes_quad(self):
        mesh = bpy.data.meshes['Quad']
        attrs = utils.mesh.extract_attributes(mesh)
        self.assertEqual(len(attrs.indices[0]), 2)
        self.assertEqual(len(attrs.positions), 4)
        self.assertEqual(len(attrs.normals), 4)
        self.assertEqual(len(attrs.colors[0]), 4)
        self.assertEqual(len(attrs.uvs[0]), 4)

    def test_extract_attributes_ngon(self):
        mesh = bpy.data.meshes['Ngon']
        attrs = utils.mesh.extract_attributes(mesh)
        self.assertEqual(len(attrs.indices[0]), 3)
        self.assertEqual(len(attrs.positions), 5)

    def test_material_splitting(self):
        mesh = bpy.data.meshes['TwoMaterials']
        attrs = utils.mesh.extract_attributes(mesh)
        all_indices = list(attrs.indices)
        self.assertEqual(len(all_indices), 2)
        self.assertEqual(len(list(all_indices[0].iterator)), 1)
        self.assertEqual(len(list(all_indices[1].iterator)), 1)


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
