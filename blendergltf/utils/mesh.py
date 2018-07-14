import mathutils.geometry


def extract_indices(mesh):
    faces = mesh.polygons

    for face in faces:
        vertices = face.vertices
        print(face.material_index)
        if len(vertices) < 3:
            continue
        elif len(vertices) > 3:
            coords = [mesh.vertices[i].co for i in vertices]
            triangles = mathutils.geometry.tessellate_polygon((coords,))
            for triangle in triangles:
                yield [vertices[i] for i in triangle]
        else:
            yield list(vertices)


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
