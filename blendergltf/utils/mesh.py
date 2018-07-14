import mathutils.geometry


class AttributeData:
    def __init__(self, mesh):
        self.positions = PositionsData(mesh)
        self.normals = NormalsData(mesh)
        self.colors = [ColorsData(c) for c in mesh.vertex_colors]
        self.uvs = [UvsData(l) for l in mesh.uv_layers]
        self.indices = [IndicesData(mesh, i) for i, _ in enumerate(mesh.materials)]


class PositionsData:
    def __init__(self, mesh):
        self.mesh = mesh
        self.iterator = (v.co for v in self.mesh.vertices)

    def __len__(self):
        return len(self.mesh.vertices)


class NormalsData:
    def __init__(self, mesh):
        mesh.calc_normals()
        self.mesh = mesh
        self.iterator = (v.normal for v in self.mesh.vertices)

    def __len__(self):
        return len(self.mesh.vertices)


class ColorsData:
    def __init__(self, colors):
        self.layer = colors
        self.iterator = (c.color for c in self.layer.data)

    def __len__(self):
        return len(self.layer.data)


class UvsData:
    def __init__(self, uv_layer):
        self.layer = uv_layer
        self.iterator = (l.uv for l in self.layer.data)

    def __len__(self):
        return len(self.layer.data)


class IndicesData:
    def __init__(self, mesh, material_index):
        self.mesh = mesh
        self._faces = [f for f in mesh.polygons if f.material_index == material_index]
        self._len = self._count_polys()
        self.material = mesh.materials[material_index]
        self.iterator = self._create_iter()

    def __len__(self):
        return self._len

    def _count_polys(self):
        return sum([max(len(f.vertices) - 2, 1) for f in self._faces])

    def _create_iter(self):
        for face in self._faces:
            vertices = face.vertices
            if len(vertices) < 3:
                continue
            elif len(vertices) > 3:
                coords = [self.mesh.vertices[i].co for i in vertices]
                triangles = mathutils.geometry.tessellate_polygon((coords,))
                for triangle in triangles:
                    yield [vertices[i] for i in triangle]
            else:
                yield list(vertices)


def extract_attributes(mesh):
    return AttributeData(mesh)
