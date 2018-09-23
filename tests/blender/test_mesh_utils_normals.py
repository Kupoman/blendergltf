import unittest

import bpy

from blendergltf import utils

def extract_from_mesh(name):
    mesh = bpy.data.meshes[name]
    return utils.mesh.extract_attributes(mesh)

def count_normals(mesh_name):
    attrs = extract_from_mesh(mesh_name)
    return len(list(attrs.normals.iterator))


class TestMeshUtils(unittest.TestCase):
    def test_smooth_shading(self):
        self.assertEqual(count_normals('shade_smooth'), 4)

    def test_flat_shading(self):
        self.assertEqual(count_normals('shade_flat'), 6)

    def test_custom_normals(self):
        self.assertEqual(count_normals('auto_custom'), 4)

    def test_auto_smooth_angle(self):
        self.assertEqual(count_normals('auto_angle'), 6)

    def test_auto_smooth_sharp(self):
        self.assertEqual(count_normals('auto_sharp'), 6)


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
