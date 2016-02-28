import bpy
import mathutils
import gpu


import json
import collections
import base64
import struct


EXPORT_SHADERS = False
EMBED_IMAGES = False
class Vertex:
    __slots__ = (
        "co",
        "normal",
        "uvs",
        "loop_indices",
        "index",
        "weights",
        "joint_indexes",
        )
    def __init__(self, mesh, loop):
        vi = loop.vertex_index
        i = loop.index
        self.co = mesh.vertices[vi].co.freeze()
        self.normal = loop.normal.freeze()
        self.uvs = tuple(layer.data[i].uv.freeze() for layer in mesh.uv_layers)
        self.loop_indices = [i]

        # Take the four most influential groups
        groups = sorted(mesh.vertices[vi].groups, key=lambda group: group.weight, reverse=True)
        if len(groups) > 4:
            groups = groups[:4]

        self.weights = [group.weight for group in groups]
        self.joint_indexes = [group.group for group in groups]

        if len(self.weights) < 4:
            for i in range(len(self.weights), 4):
                self.weights.append(0.0)
                self.joint_indexes.append(0)

        self.index = 0

    def __hash__(self):
        return hash((self.co, self.normal, self.uvs))

    def __eq__(self, other):
        eq = (
            (self.co == other.co) and
            (self.normal == other.normal) and
            (self.uvs == other.uvs)
            )

        if eq:
            indices = self.loop_indices + other.loop_indices
            self.loop_indices = indices
            other.loop_indices = indices
        return eq

class Buffer:
    ARRAY_BUFFER = 34962
    ELEMENT_ARRAY_BUFFER = 34963

    BYTE = 5120
    UNSIGNED_BYTE = 5121
    SHORT = 5122
    UNSIGNED_SHORT = 5123
    FLOAT = 5126

    MAT4 = 'MAT4'
    VEC4 = 'VEC4'
    VEC3 = 'VEC3'
    VEC2 = 'VEC2'
    SCALAR = 'SCALAR'

    class Accessor:
        __slots__ = (
            "name",
            "buffer",
            "buffer_view",
            "byte_offset",
            "byte_stride",
            "component_type",
            "count",
            "type",
            "type_size",
            "_ctype",
            "_ctype_size",
            "_buffer_data",
            )
        def __init__(self,
                     name,
                     buffer,
                     buffer_view,
                     byte_offset,
                     byte_stride,
                     component_type,
                     count,
                     type):
            self.name = name
            self.buffer = buffer
            self.buffer_view = buffer_view
            self.byte_offset = byte_offset
            self.byte_stride = byte_stride
            self.component_type = component_type
            self.count = count
            self.type = type

            if self.type == Buffer.MAT4:
                self.type_size = 16
            elif self.type == Buffer.VEC4:
                self.type_size = 4
            elif self.type == Buffer.VEC3:
                self.type_size = 3
            elif self.type == Buffer.VEC2:
                self.type_size = 2
            else:
                self.type_size = 1

            if component_type == Buffer.BYTE:
                self._ctype = '<b'
            elif component_type == Buffer.UNSIGNED_BYTE:
                self._ctype = '<B'
            elif component_type == Buffer.SHORT:
                self._ctype = '<h'
            elif component_type == Buffer.UNSIGNED_SHORT:
                self._ctype = '<H'
            elif component_type == Buffer.FLOAT:
                self._ctype = '<f'
            else:
                raise ValueError("Bad component type")

            self._ctype_size = struct.calcsize(self._ctype)
            self._buffer_data = self.buffer._get_buffer_data(self.buffer_view)

        # Inlined for performance, leaving this here as reference
        # def _get_ptr(self, idx):
            # addr = ((idx % self.type_size) * self._ctype_size + idx // self.type_size * self.byte_stride) + self.byte_offset
            # return addr

        def __len__(self):
            return self.count

        def __getitem__(self, idx):
            if not isinstance(idx, int):
                raise TypeError("Expected an integer index")

            ptr = ((idx % self.type_size) * self._ctype_size + idx // self.type_size * self.byte_stride) + self.byte_offset

            return struct.unpack_from(self._ctype, self._buffer_data, ptr)[0]

        def __setitem__(self, idx, value):
            if not isinstance(idx, int):
                raise TypeError("Expected an integer index")

            ptr = ((idx % self.type_size) * self._ctype_size + idx // self.type_size * self.byte_stride) + self.byte_offset

            struct.pack_into(self._ctype, self._buffer_data, ptr, value)

    __slots__ = (
        "name",
        "type",
        "bytelength",
        "uri",
        "buffer_views",
        "accessors",
        )
    def __init__(self, name, uri=None):
        self.name = '{}_buffer'.format(name)
        self.type = 'arraybuffer'
        self.bytelength = 0
        self.uri = uri
        self.buffer_views = collections.OrderedDict()
        self.accessors = {}

    def export_buffer(self):
        data = bytearray()
        for bn, bv in self.buffer_views.items():
            data.extend(bv['data'])
            #print(bn)

            #if bv['target'] == Buffer.ARRAY_BUFFER:
            #    idx = bv['byteoffset']
            #    while idx < bv['byteoffset'] + bv['bytelength']:
            #    	print(struct.unpack_from('<ffffff', data, idx))
            #    	idx += 24
            #if bv['target'] == Buffer.ELEMENT_ARRAY_BUFFER:
            #    idx = bv['byteoffset']
            #    while idx < bv['byteoffset'] + bv['bytelength']:
            #    	print(struct.unpack_from('<HHH', data, idx))
            #    	idx += 6

        uri = 'data:text/plain;base64,' + base64.b64encode(data).decode('ascii')
        #fname = '{}.bin'.format(self.name)
        #with open(fname, 'wb') as f:
        #    for bv in self.buffer_views.values():
        #    	f.write(bv['data'])

        #uri = 'data:text/plain;base64,'
        #with open(fname, 'rb') as f:
        #    uri += str(base64.b64encode(f.read()), 'ascii')

        return {
            'byteLength': self.bytelength,
            'type': self.type,
            'uri': uri,
        }

    def add_view(self, bytelength, target):
        buffer_name = '{}_view_{}'.format(self.name, len(self.buffer_views))
        self.buffer_views[buffer_name] = {
                'data': bytearray(bytelength),
                'target': target,
                'bytelength': bytelength,
                'byteoffset': self.bytelength,
            }
        self.bytelength += bytelength
        return buffer_name

    def export_views(self):
        gltf = {}

        for k, v in self.buffer_views.items():
            gltf[k] = {
                'buffer': self.name,
                'byteLength': v['bytelength'],
                'byteOffset': v['byteoffset'],
                'target': v['target'],
            }

        return gltf

    def _get_buffer_data(self, buffer_view):
        return self.buffer_views[buffer_view]['data']

    def add_accessor(self,
                     buffer_view,
                     byte_offset,
                     byte_stride,
                     component_type,
                     count,
                     type):
        accessor_name = '{}_accessor_{}'.format(self.name, len(self.accessors))
        self.accessors[accessor_name] = self.Accessor(accessor_name, self, buffer_view, byte_offset, byte_stride, component_type, count, type)
        return self.accessors[accessor_name]

    def export_accessors(self):
        gltf = {}

        for k, v in self.accessors.items():
            gltf[k] = {
                'bufferView': v.buffer_view,
                'byteOffset': v.byte_offset,
                'byteStride': v.byte_stride,
                'componentType': v.component_type,
                'count': v.count,
                'type': v.type,
            }

        return gltf


g_buffers = []


def togl(matrix):
    return [i for col in matrix.col for i in col]


def export_cameras(cameras):
    def export_camera(camera):
        if camera.type == 'ORTHO':
            return {
                'orthographic': {
                    'xmag': camera.ortho_scale,
                    'ymag': camera.ortho_scale,
                    'zfar': camera.clip_end,
                    'znear': camera.clip_start,
                },
                'type': 'orthographic',
            }
        else:
            return {
                'perspective': {
                    'aspectRatio': camera.angle_x / camera.angle_y,
                    'yfov': camera.angle_y,
                    'zfar': camera.clip_end,
                    'znear': camera.clip_start,
                },
                'type': 'perspective',
            }

    return {camera.name: export_camera(camera) for camera in cameras}


def export_materials(materials, shaders, programs, techniques):
    def export_material(material):
        return {
                'values': {
                    'diffuse': list((material.diffuse_color * material.diffuse_intensity)[:]) + [material.alpha],
                    'specular': list((material.specular_color * material.specular_intensity)[:]) + [material.specular_alpha],
                    'emission': list((material.diffuse_color * material.emit)[:]) + [material.alpha],
                    'ambient': [material.ambient] * 4,
                    'shininess': material.specular_hardness,
                    'textures': [ts.texture.name for ts in material.texture_slots if ts and ts.texture.type == 'IMAGE'],
                    'uv_layers': [ts.uv_layer for ts in material.texture_slots if ts]
                }
            }
    exp_materials = {}
    for material in materials:
        exp_materials[material.name] = export_material(material)

        if not EXPORT_SHADERS:
            continue

        # Handle shaders
        shader_data = gpu.export_shader(bpy.context.scene, material)
        fs_bytes = shader_data['fragment'].encode()
        fs_uri = 'data:text/plain;base64,' + base64.b64encode(fs_bytes).decode('ascii')
        shaders[material.name+'FS'] = {'type': 35632, 'uri': fs_uri}
        vs_bytes = shader_data['vertex'].encode()
        vs_uri = 'data:text/plain;base64,' + base64.b64encode(vs_bytes).decode('ascii')
        shaders[material.name+'VS'] = {'type': 35633, 'uri': vs_uri}

        # Handle programs
        programs[material.name+'Program'] = {
            'attributes' : [],
            'fragmentShader' : material.name+'FS',
            'vertexShader' : material.name+'VS',
        }

        # Handle techniques
        techniques['material.name'+'Technique'] = {
            'program' : material.name+'Program',
            'attributes' : {a['varname'] : a['varname'] for a in shader_data['attributes']},
            'uniforms' : {u['varname'] : u['varname'] for u in shader_data['uniforms']},
        }

    return exp_materials


def export_meshes(meshes, skinned_meshes):
    def export_mesh(me):
        # glTF data
        gltf_mesh = {
                'name': me.name,
                'primitives': [],
            }

        is_skinned = me.name in skinned_meshes

        me.calc_normals_split()
        me.calc_tessface()

        num_loops = len(me.loops)
        num_uv_layers = len(me.uv_layers)
        vertex_size = (3 + 3 + num_uv_layers * 2) * 4

        buf = Buffer(me.name)
        skin_buf = Buffer('{}_skin'.format(me.name))

        # Vertex data

        vert_list = { Vertex(me, loop) : 0 for loop in me.loops}.keys()
        num_verts = len(vert_list)
        va = buf.add_view(vertex_size * num_verts, Buffer.ARRAY_BUFFER)
        vdata = buf.add_accessor(va, 0, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
        ndata = buf.add_accessor(va, 12, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC3)
        tdata = [buf.add_accessor(va, 24 + 8 * i, vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC2) for i in range(num_uv_layers)]

        skin_vertex_size = (4 + 4) * 4
        skin_va = skin_buf.add_view(skin_vertex_size * num_verts, Buffer.ARRAY_BUFFER)
        jdata = skin_buf.add_accessor(skin_va, 0, skin_vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC4)
        wdata = skin_buf.add_accessor(skin_va, 16, skin_vertex_size, Buffer.FLOAT, num_verts, Buffer.VEC4)

        for i, vtx in enumerate(vert_list):
            vtx.index = i
            co = vtx.co
            normal = vtx.normal

            for j in range(3):
                vdata[(i * 3) + j] = co[j]
                ndata[(i * 3) + j] = normal[j]

            for j, uv in enumerate(vtx.uvs):
                tdata[j][i * 2] = uv.x
                tdata[j][i * 2 + 1] = uv.y

        if is_skinned:
            for i, vtx in enumerate(vert_list):
                joints = vtx.joint_indexes
                weights = vtx.weights

                for j in range(4):
                    jdata[(i * 4) + j] = joints[j]
                    wdata[(i * 4) + j] = weights[j]

        prims = {ma.name if ma else '': [] for ma in me.materials}
        if not prims:
            prims = {'': []}

        # Index data
        vert_dict = {i : v for v in vert_list for i in v.loop_indices}
        for poly in me.polygons:
            first = poly.loop_start
            if len(me.materials) == 0:
                prim = prims['']
            else:
                mat = me.materials[poly.material_index]
                prim = prims[mat.name if mat else '']
            indices = [vert_dict[i].index for i in range(first, first+poly.loop_total)]

            if poly.loop_total == 3:
                prim += indices
            elif poly.loop_total > 3:
                for i in range(poly.loop_total-1):
                    prim += (indices[-1], indices[i], indices[i + 1])
            else:
                raise RuntimeError("Invalid polygon with {} vertexes.".format(poly.loop_total))

        for mat, prim in prims.items():
            ib = buf.add_view(2 * len(prim), Buffer.ELEMENT_ARRAY_BUFFER)
            idata = buf.add_accessor(ib, 0, 2, Buffer.UNSIGNED_SHORT, len(prim), Buffer.SCALAR)
            for i, v in enumerate(prim):
                idata[i] = v

            gltf_prim = {
                'attributes': {
                    'POSITION': vdata.name,
                    'NORMAL': ndata.name,
                },
                'indices': idata.name,
                'mode': 4,
                'material': mat,
            }
            for i, v in enumerate(tdata):
                gltf_prim['attributes']['TEXCOORD_' + me.uv_layers[i].name] = v.name

            if is_skinned:
                gltf_prim['attributes']['JOINT'] = jdata.name
                gltf_prim['attributes']['WEIGHT'] = wdata.name

            gltf_mesh['primitives'].append(gltf_prim)

        g_buffers.append(buf)
        if is_skinned:
            g_buffers.append(skin_buf)
        return gltf_mesh

    return {me.name: export_mesh(me) for me in meshes if me.users != 0}


def export_skins(skinned_meshes):
    def export_skin(obj):
        gltf_skin = {
            'bindShapeMatrix': togl(mathutils.Matrix.Identity(4)),
            'name': obj.name,
        }
        arm = obj.find_armature()
        gltf_skin['jointNames'] = ['{}_{}'.format(arm.name, group.name) for group in obj.vertex_groups]

        element_size = 16 * 4
        num_elements = len(obj.vertex_groups)
        buf = Buffer('IBM_{}_skin'.format(obj.name))
        buf_view = buf.add_view(element_size * num_elements, Buffer.ARRAY_BUFFER)
        idata = buf.add_accessor(buf_view, 0, element_size, Buffer.FLOAT, num_elements, Buffer.MAT4)

        for i in range(num_elements):
            mat = togl(mathutils.Matrix.Identity(4))
            for j in range(16):
                idata[(i * 16) + j] = mat[j]

        gltf_skin['inverseBindMatrices'] = idata.name
        g_buffers.append(buf)

        return gltf_skin

    return {'{}_skin'.format(mesh_name): export_skin(obj) for mesh_name, obj in skinned_meshes.items()}


def export_lights(lamps):
    def export_light(light):
        def calc_att():
            kl = 0
            kq = 0

            if light.falloff_type == 'INVERSE_LINEAR':
                kl = 1 / light.distance
            elif light.falloff_type == 'INVERSE_SQUARE':
                kq = 1 / light.distance
            elif light.falloff_type == 'LINEAR_QUADRATIC_WEIGHTED':
                kl = light.linear_attenuation * (1 / light.distance)
                kq = light.quadratic_attenuation * (1 / (light.distance * light.distance))

            return kl, kq

        if light.type == 'SUN':
            return {
                'directional': {
                    'color': (light.color * light.energy)[:],
                },
                'type': 'directional',
            }
        elif light.type == 'POINT':
            kl, kq = calc_att()
            return {
                'point': {
                    'color': (light.color * light.energy)[:],

                    # TODO: grab values from Blender lamps
                    'constantAttenuation': 1,
                    'linearAttenuation': kl,
                    'quadraticAttenuation': kq,
                },
                'type': 'point',
            }
        elif light.type == 'SPOT':
            kl, kq = calc_att()
            return {
                'spot': {
                    'color': (light.color * light.energy)[:],

                    # TODO: grab values from Blender lamps
                    'constantAttenuation': 1.0,
                    'fallOffAngle': 3.14159265,
                    'fallOffExponent': 0.0,
                    'linearAttenuation': kl,
                    'quadraticAttenuation': kq,
                },
                'type': 'spot',
            }
        else:
            print("Unsupported lamp type on {}: {}".format(light.name, light.type))
            return {'type': 'unsupported'}

    gltf = {lamp.name: export_light(lamp) for lamp in lamps}

    return gltf


def export_nodes(objects, skinned_meshes):
    def export_node(obj):
        ob = {
            'name': obj.name,
            'children': [child.name for child in obj.children],
            'matrix': togl(obj.matrix_world),
        }

        if obj.type == 'MESH':
            ob['meshes'] = [obj.data.name]
            if obj.find_armature():
                ob['skeletons'] = [obj.find_armature().name]
                skinned_meshes[obj.data.name] = obj
        elif obj.type == 'LAMP':
            ob['extras'] = {'light': obj.data.name}
        elif obj.type == 'CAMERA':
            ob['camera'] = obj.data.name
        elif obj.type == 'EMPTY' and obj.dupli_group is not None:
            # Expand dupli-groups
            ob['children'] += [i.name for i in obj.dupli_group.objects]

        return ob

    gltf_nodes = {obj.name: export_node(obj) for obj in objects if obj.type != 'ARMATURE'}

    def export_joint(arm_name, bone):
        gltf_joint = {
            'name': bone.name,
            'jointName': '{}_{}'.format(arm_name, bone.name),
            'children': ['{}_{}'.format(arm_name, child.name) for child in bone.children],
        }

        if bone.parent:
            gltf_joint['matrix'] = togl(bone.parent.matrix_local.inverted() * bone.matrix_local)
        else:
            gltf_joint['matrix'] = togl(bone.matrix_local)

        return gltf_joint

    for obj in [obj for obj in objects if obj.type == 'ARMATURE']:
        arm = obj.data
        gltf_nodes.update({"{}_{}".format(arm.name, bone.name): export_joint(arm.name, bone) for bone in arm.bones})
        gltf_nodes[arm.name] = {
            'name': arm.name,
            'jointName': arm.name,
            'children': ['{}_{}'.format(arm.name, bone.name) for bone in arm.bones if bone.parent is None],
            'matrix': togl(obj.matrix_world),
        }

    return gltf_nodes


def export_scenes(scenes):
    def export_scene(scene):
        return {
            'nodes': [ob.name for ob in scene.objects],
            'extras': {
                'background_color': scene.world.horizon_color[:],
                'active_camera': scene.camera.name if scene.camera else '',
                'hidden_nodes': [ob.name for ob in scene.objects if not ob.is_visible(scene)]
            }
        }

    return {scene.name: export_scene(scene) for scene in scenes}


def export_buffers():
    gltf = {
        'buffers': {},
        'bufferViews': {},
        'accessors': {},
    }

    for buf in g_buffers:
        gltf['buffers'][buf.name] = buf.export_buffer()
        gltf['bufferViews'].update(buf.export_views())
        gltf['accessors'].update(buf.export_accessors())

    return gltf


def export_images(images):
    def export_image(image):
        if EMBED_IMAGES:
            pixels = bytearray([int(p * 255) for p in image.pixels])
            uri = 'data:text/plain;base64,' + base64.b64encode(pixels).decode('ascii')
        else:
            uri = image.filepath.replace('//', '')

        return {
            'uri': uri,
        }
    return {image.name: export_image(image) for image in images}


def export_textures(textures):
    def export_texture(texture):
        return {
            'sampler' : 'default',
            'source' : texture.image.name,
        }
    return {texture.name: export_texture(texture) for texture in textures
        if type(texture) == bpy.types.ImageTexture}


def export_gltf(scene_delta):
    global g_buffers

    shaders = {}
    programs = {}
    techniques = {}
    skinned_meshes = {}

    gltf = {
        'asset': {'version': '1.0'},
        'cameras': export_cameras(scene_delta.get('cameras', [])),
        'extras': {'lights' : export_lights(scene_delta.get('lamps', []))},
        'images': export_images(scene_delta.get('images', [])),
        'materials': export_materials(scene_delta.get('materials', []),
            shaders, programs, techniques),
        'nodes': export_nodes(scene_delta.get('objects', []), skinned_meshes),
        # Make sure meshes come after nodes to detect which meshes are skinned
        'meshes': export_meshes(scene_delta.get('meshes', []), skinned_meshes),
        'skins': export_skins(skinned_meshes),
        'programs': programs,
        'samplers': {'default':{}},
        'scene': bpy.context.scene.name,
        'scenes': export_scenes(scene_delta.get('scenes', [])),
        'shaders': shaders,
        'techniques': techniques,
        'textures': export_textures(scene_delta.get('textures', [])),

        # TODO
        'animations': {},
    }

    # Retroactively add skins attribute to nodes
    for mesh_name, obj in skinned_meshes.items():
        gltf['nodes'][obj.name]['skin'] = '{}_skin'.format(mesh_name)

    gltf.update(export_buffers())
    g_buffers = []

    gltf = {key: value for key, value in gltf.items() if value}

    return gltf
