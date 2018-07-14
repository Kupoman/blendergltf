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
        self.iterator = (v.co for v in mesh.vertices)


class NormalsData:
    def __init__(self, mesh):
        mesh.calc_normals()
        self.iterator = (v.normal for v in mesh.vertices)


class ColorsData:
    def __init__(self, colors):
        self.layer = colors
        self.iterator = (c.color for c in colors.data)


class UvsData:
    def __init__(self, uv_layer):
        self.layer = uv_layer
        self.iterator = (l.uv for l in uv_layer.data)


class IndicesData:
    def __init__(self, mesh, material_index):
        self.material = mesh.materials[material_index]
        self.iterator = self._create_iter(mesh, material_index)

    def _create_iter(self, mesh, material_index):
        faces = [f for f in mesh.polygons if f.material_index == material_index]
        for face in faces:
            vertices = face.vertices
            if len(vertices) < 3:
                continue
            elif len(vertices) > 3:
                coords = [mesh.vertices[i].co for i in vertices]
                triangles = mathutils.geometry.tessellate_polygon((coords,))
                for triangle in triangles:
                    yield [vertices[i] for i in triangle]
            else:
                yield list(vertices)


def extract_attributes(mesh):
    return AttributeData(mesh)
