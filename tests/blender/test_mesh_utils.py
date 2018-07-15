import unittest

import bpy
from mathutils import (
    Vector,
    Color,
)

from blendergltf.blendergltf import utils

def extract_from_mesh(name):
    mesh = bpy.data.meshes[name]
    return utils.mesh.extract_attributes(mesh)


class TestMeshUtils(unittest.TestCase):
    def test_extract_attributes_basic(self):
        attrs = extract_from_mesh('Triangle')
        self.assertEqual(len(attrs.triangle_sets[0]), 1)
        self.assertEqual(list(attrs.triangle_sets[0].iterator), [[0, 2, 1]])
        self.assertEqual(list(attrs.positions.iterator)[0], Vector([-1.0, -1.0, 0.0]))
        self.assertEqual(list(attrs.normals.iterator)[0], Vector([0.0, 0.0, 1.0]))
        self.assertEqual(list(attrs.color_layers[0].iterator)[0], Color([1.0, 0.0, 0.0]))
        self.assertEqual(list(attrs.uv_layers[0].iterator)[1], Vector([1.0, 1.0]))

    def test_extract_vertex_groups(self):
        attrs = extract_from_mesh('Triangle')
        groups = list(attrs.group.iterator)[0]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].weight, 1.0)
        self.assertEqual(groups[0].group, 0)

    def test_extract_attributes_quad(self):
        attrs = extract_from_mesh('Quad')
        self.assertEqual(len(attrs.triangle_sets[0]), 2)
        self.assertEqual(len(attrs.polygon_sets[0]), 1)
        self.assertEqual(len(attrs.positions), 4)
        self.assertEqual(len(attrs.normals), 4)
        self.assertEqual(len(attrs.color_layers[0]), 4)
        self.assertEqual(len(attrs.uv_layers[0]), 4)

    def test_extract_attributes_ngon(self):
        attrs = extract_from_mesh('Ngon')
        self.assertEqual(len(attrs.triangle_sets[0]), 3)
        self.assertEqual(len(attrs.polygon_sets[0]), 1)
        self.assertEqual(len(attrs.positions), 5)

    def test_material_splitting(self):
        attrs = extract_from_mesh('TwoMaterials')
        self.assertEqual(len(attrs.triangle_sets), 2)
        self.assertEqual(len(attrs.triangle_sets[0]), 1)
        self.assertEqual(len(attrs.triangle_sets[1]), 1)
        self.assertEqual(len(attrs.polygon_sets), 2)
        self.assertEqual(len(attrs.polygon_sets[0]), 1)
        self.assertEqual(len(attrs.polygon_sets[1]), 1)


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
