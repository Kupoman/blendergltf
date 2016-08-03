import bpy
import mathutils
import gpu


import json
import collections
import base64
import struct


default_settings = {
    'materials_export_shader': False,
    'meshes_apply_modifiers': True,
    'images_embed_data': False,
    'global_matrix': mathutils.Matrix.Identity(4)
}


# Texture formats
GL_ALPHA = 6406
GL_RGB = 6407
GL_RGBA = 6408
GL_LUMINANCE = 6409
GL_LUMINANCE_ALPHA = 6410

# sRGB texture formats (not actually part of WebGL 1.0 or glTF 1.0)
GL_SRGB = 0x8C40
GL_SRGB_ALPHA = 0x8C42


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
            "min",
            "max",
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
            self.min = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.max = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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

            i = idx % self.type_size
            self.min[i] = value if value < self.min[i] else self.min[i]
            self.max[i] = value if value > self.max[i] else self.max[i]

            ptr = (i * self._ctype_size + idx // self.type_size * self.byte_stride) + self.byte_offset

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
            }

            if v['target'] is not None:
                gltf[k]['target'] = v['target']

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
                'min': v.min[:v.type_size],
                'max': v.max[:v.type_size],
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


def export_materials(settings, materials, shaders, programs, techniques):
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

        if settings['materials_export_shader'] == False:
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
                for i in range(poly.loop_total-2):
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

    return {me.name: export_mesh(me) for me in meshes}


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
        buf_view = buf.add_view(element_size * num_elements, None)
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


def export_nodes(objects, skinned_meshes, modded_meshes):
    def export_physics(obj):
        rb = obj.rigid_body
        physics =  {
            'collision_shape': rb.collision_shape.lower(),
            'mass': rb.mass,
            'dynamic': rb.type == 'ACTIVE' and rb.enabled,
            'dimensions': obj.dimensions[:],
        }

        if rb.collision_shape in ('CONVEX_HULL', 'MESH'):
            physics['mesh'] = obj.data.name

        return physics

    def export_node(obj):
        ob = {
            'name': obj.name,
            'children': [child.name for child in obj.children],
            'matrix': togl(obj.matrix_world),
        }

        if obj.type == 'MESH':
            mesh = modded_meshes.get(obj.name, obj.data)
            ob['meshes'] = [mesh.name]
            if obj.find_armature():
                ob['skeletons'] = ['{}_root'.format(obj.find_armature().data.name)]
                skinned_meshes[mesh.name] = obj
        elif obj.type == 'LAMP':
            ob['extras'] = {'light': obj.data.name}
        elif obj.type == 'CAMERA':
            ob['camera'] = obj.data.name
        elif obj.type == 'EMPTY' and obj.dupli_group is not None:
            # Expand dupli-groups
            ob['children'] += [i.name for i in obj.dupli_group.objects]

        if obj.rigid_body:
            ob['extensions'] = {
                'BLENDER_physics': export_physics(obj)
            }

        return ob

    gltf_nodes = {obj.name: export_node(obj) for obj in objects}

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
        gltf_nodes['{}_root'.format(arm.name)] = {
            'name': arm.name,
            'jointName': arm.name,
            'children': ['{}_{}'.format(arm.name, bone.name) for bone in arm.bones if bone.parent is None],
            'matrix': togl(obj.matrix_world),
        }

    return gltf_nodes


def export_scenes(scenes):
    def export_scene(scene):
        return {
            'nodes': [ob.name for ob in scene.objects if ob.parent is None],
            'extras': {
                'background_color': scene.world.horizon_color[:],
                'active_camera': scene.camera.name if scene.camera else '',
                'hidden_nodes': [ob.name for ob in scene.objects if not ob.is_visible(scene)],
                'frames_per_second': scene.render.fps,
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


def export_images(settings, images):
    def export_image(image):
        if settings['images_embed_data']:
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
        gltf_texture = {
            'sampler' : 'default',
            'source' : texture.image.name,
        }
        tformat = None
        channels = texture.image.channels
        use_srgb = texture.image.colorspace_settings.name == 'sRGB'

        if channels == 3:
            if use_srgb:
                tformat = GL_SRGB
            else:
                tformat = GL_RGB
        elif channels == 4:
            if use_srgb:
                tformat = GL_SRGB_ALPHA
            else:
                tformat = GL_RGBA

        if tformat is None:
            raise RuntimeError(
                "Could not find a texture format for image (name={}, num channels={})".format(texture.image.name, channels)
            )

        gltf_texture['format'] = gltf_texture['internalFormat'] = tformat

        return gltf_texture

    return {texture.name: export_texture(texture) for texture in textures
        if type(texture) == bpy.types.ImageTexture}


_path_map = {
    'location': 'translation',
    'rotation_quaternion': 'rotation',
    'scale': 'scale',
}


def _can_object_use_action(obj, action):
    for fcurve in action.fcurves:
        path = fcurve.data_path
        if not path.startswith('pose'):
            return obj.animation_data is not None

        if obj.type == 'ARMATURE':
            path = path.split('["')[-1]
            path = path.split('"]')[0]
            if path in [bone.name for bone in obj.data.bones]:
                return True

    return False


def export_actions(actions):
    def export_action(obj, action):
        params = []

        exported_paths = {}
        channels = {}

        sce = bpy.context.scene
        prev_frame = sce.frame_current
        prev_action = obj.animation_data.action

        frame_start, frame_end = [int(x) for x in action.frame_range]
        num_frames = frame_end - frame_start
        obj.animation_data.action = action

        channels[obj.name] = []

        if obj.type == 'ARMATURE':
            for pbone in obj.pose.bones:
                channels[pbone.name] = []

        for frame in range(frame_start, frame_end):
            sce.frame_set(frame)

            channels[obj.name].append(obj.matrix_local)

            if obj.type == 'ARMATURE':
                for pbone in obj.pose.bones:
                    if pbone.parent:
                        mat = pbone.parent.matrix.inverted() * pbone.matrix
                    else:
                        mat = pbone.matrix
                    channels[pbone.name].append(mat)

        gltf_channels = []

        for targetid, chan in channels.items():
            buf = Buffer('{}_{}'.format(targetid, action.name))
            lbv = buf.add_view(num_frames * 3 * 4, None)
            ldata = buf.add_accessor(lbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)
            rbv = buf.add_view(num_frames * 4 * 4, None)
            rdata = buf.add_accessor(rbv, 0, 4 * 4, Buffer.FLOAT, num_frames, Buffer.VEC4)
            sbv = buf.add_view(num_frames * 3 * 4, None)
            sdata = buf.add_accessor(sbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)

            for i in range(num_frames):
                mat = chan[i]
                loc, rot, scale = mat.decompose()
                for j in range(3):
                    ldata[(i * 3) + j] = loc[j]
                    sdata[(i * 3) + j] = scale[j]
                for j in range(4):
                    rdata[(i * 4) + j] = rot[j]

            g_buffers.append(buf)

            if targetid != obj.name:
                targetid = '{}_root_{}'.format(obj.data.name, targetid)

            gltf_channels += [
                {
                    'id': targetid,
                    'path': 'translation',
                    'data': ldata.name,
                },
                {
                    'id': targetid,
                    'path': 'rotation',
                    'data': rdata.name,
                },
                {
                    'id': targetid,
                    'path': 'scale',
                    'data': sdata.name,
                }
            ]

        gltf_action = {
            'channels': gltf_channels,
            'frames': num_frames,
        }

        obj.animation_data.action = prev_action
        sce.frame_set(prev_frame)

        return gltf_action

    gltf_actions = {}
    for obj in bpy.data.objects:
        act_prefix = '{}_root'.format(obj.data.name) if obj.type == 'ARMATURE' else obj.name
        gltf_actions.update({
            '{}|{}'.format(act_prefix, action.name): export_action(obj, action)
            for action in actions
            if _can_object_use_action(obj, action)
        })

    return gltf_actions


def export_gltf(scene_delta, settings={}):
    global g_buffers

    # Fill in any missing settings with defaults
    for key, value in default_settings.items():
        settings.setdefault(key, value)

    shaders = {}
    programs = {}
    techniques = {}
    mesh_list = []
    mod_meshes = {}
    skinned_meshes = {}
    object_list = list(scene_delta.get('objects', []))

    # Apply modifiers
    if settings['meshes_apply_modifiers']:
        scene = bpy.context.scene
        mod_obs = [ob for ob in object_list if ob.is_modified(scene, 'PREVIEW')]
        for mesh in scene_delta.get('meshes', []):
            mod_users = [ob for ob in mod_obs if ob.data == mesh]

            # Only convert meshes with modifiers, otherwise each non-modifier
            # user ends up with a copy of the mesh and we lose instancing
            mod_meshes.update({ob.name: ob.to_mesh(scene, True, 'PREVIEW') for ob in mod_users})

            # Add unmodified meshes directly to the mesh list
            if len(mod_users) < mesh.users:
                mesh_list.append(mesh)
        mesh_list.extend(mod_meshes.values())
    else:
        mesh_list = scene_delta.get('meshes', [])

    # Use this to store objects that we need to transform back from their
    # converted axis space. There is no need to copy meshes that don't have any
    # modifiers applied but that means we have to be careful in modifying them.
    user_objects = []

    global_matrix = settings.get('global_matrix', None)
    if global_matrix != None:
        # If a global matrix was provided apply it to all objects.
        for obj in object_list:
            if obj.type != 'MESH': continue

            # Find the mesh associated with this object
            if obj.name in mod_meshes:
                # Use the modified mesh copy (completely safe to modify).
                mesh = mod_meshes[obj.name]
            else:
                # We have to remember to undo the transformation because this is
                # a user mesh (not one we created).
                mesh = obj.data
                user_objects.append(obj)

            inv_world_mat = obj.matrix_world.inverted()

            # Transform the mesh from model space to blender world space, then
            # converted-axis world space and finally back to a converted-axis
            # model space, suitable for copying.
            mesh.transform(inv_world_mat * global_matrix * obj.matrix_world)

    gltf = {
        'asset': {'version': '1.0'},
        'cameras': export_cameras(scene_delta.get('cameras', [])),
        'extras': {
            'lights' : export_lights(scene_delta.get('lamps', [])),
            'actions': export_actions(scene_delta.get('actions', [])),
        },
        'images': export_images(settings, scene_delta.get('images', [])),
        'materials': export_materials(settings, scene_delta.get('materials', []),
            shaders, programs, techniques),
        'nodes': export_nodes(object_list, skinned_meshes, mod_meshes),
        # Make sure meshes come after nodes to detect which meshes are skinned
        'meshes': export_meshes(mesh_list, skinned_meshes),
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

    # Remove any temporary meshes from applying modifiers
    for mesh in mod_meshes.values():
        bpy.data.meshes.remove(mesh)

    # Reset the transformation on meshes that we didn't create
    if global_matrix != None:
        for obj in user_objects:
            inv_world_mat = obj.matrix_world.inverted()
            inv_global_matrix = global_matrix.inverted()
            mesh.transform(inv_world_mat * inv_global_matrix * obj.matrix_world)

    return gltf
