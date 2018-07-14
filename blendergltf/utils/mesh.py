import mathutils.geometry


def _process_faces(mesh, faces):
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


def extract_indices(mesh):
    faces = mesh.polygons
    index_collections = []
    for i, _ in enumerate(mesh.materials):
        material_faces = [f for f in faces if f.material_index == i]
        collection = _process_faces(mesh, material_faces)
        index_collections.append(collection)
    return index_collections


def extract_positions(mesh):
    return (v.co for v in mesh.vertices)


def extract_normals(mesh):
    mesh.calc_normals()
    return (v.normal for v in mesh.vertices)


def extract_colors(mesh):
    colors = []
    for color_layer in mesh.vertex_colors:
        colors.append((c.color for c in color_layer.data))
    return colors


def extract_uvs(mesh):
    uvs = []
    for uv_layer in mesh.uv_layers:
        uvs.append((l.uv for l in uv_layer.data))
    return uvs


def extract_attributes(mesh):
    attributes = {
        'indices': extract_indices(mesh),
        'positions': extract_positions(mesh),
        'normals': extract_normals(mesh),
        'colors': extract_colors(mesh),
        'uvs': extract_uvs(mesh),
    }
    return attributes
