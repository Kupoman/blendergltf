from distutils.version import StrictVersion as Version
import functools
import itertools
import json
import struct

import bpy
import mathutils

from .exporters import (
    Buffer,
    Reference,
    SimpleID,
    get_bone_name,

    AnimationExporter,
    CameraExporter,
    ImageExporter,
    MaterialExporter,
    MeshExporter,
    NodeExporter,
    SceneExporter,
    SkinExporter,
    TextureExporter,
)


__all__ = ['export_gltf']


DEFAULT_SETTINGS = {
    'gltf_output_dir': '',
    'gltf_name': 'gltf',
    'gltf_export_binary': False,
    'buffers_embed_data': True,
    'buffers_combine_data': False,
    'nodes_export_hidden': False,
    'nodes_global_matrix': mathutils.Matrix.Identity(4),
    'nodes_global_matrix_apply': True,
    'nodes_selected_only': False,
    'blocks_prune_unused': True,
    'meshes_apply_modifiers': True,
    'meshes_interleave_vertex_data': True,
    'meshes_vertex_color_alpha': True,
    'images_data_storage': 'COPY',
    'asset_version': '2.0',
    'asset_copyright': '',
    'asset_profile': 'WEB',
    'images_allow_srgb': False,
    'extension_exporters': [],
    'animations_object_export': 'ACTIVE',
    'animations_armature_export': 'ELIGIBLE',
    'animations_shape_key_export': 'ELIGIBLE',
    'hacks_streaming': False,
}


PROFILE_MAP = {
    'WEB': {'api': 'WebGL', 'version': '1.0'},
    'DESKTOP': {'api': 'OpenGL', 'version': '3.0'}
}


def togl(matrix):
    return [i for col in matrix.col for i in col]


def _decompose(matrix):
    loc, rot, scale = matrix.decompose()
    loc = loc.to_tuple()
    rot = (rot.x, rot.y, rot.z, rot.w)
    scale = scale.to_tuple()

    return loc, rot, scale


def export_joint(state, bone):
    axis_mat = mathutils.Matrix.Identity(4)
    if state['settings']['nodes_global_matrix_apply']:
        axis_mat = state['settings']['nodes_global_matrix']

    matrix = axis_mat * bone.matrix_local
    if bone.parent:
        matrix = bone.parent.matrix_local.inverted() * bone.matrix_local

    bone_name = get_bone_name(bone)

    gltf_joint = {
        'name': bone.name,
    }
    if state['version'] < Version('2.0'):
        gltf_joint['jointName'] = Reference(
            'objects',
            bone_name,
            gltf_joint,
            'jointName'
        )
        state['references'].append(gltf_joint['jointName'])
    if bone.children:
        gltf_joint['children'] = [
            Reference('objects', get_bone_name(child), None, None) for child in bone.children
        ]
    if bone_name in state['bone_children']:
        bone_children = [
            Reference('objects', obj_name, None, None)
            for obj_name in state['bone_children'][bone_name]
        ]
        gltf_joint['children'] = gltf_joint.get('children', []) + bone_children
    for i, ref in enumerate(gltf_joint.get('children', [])):
        ref.source = gltf_joint['children']
        ref.prop = i
        state['references'].append(ref)

    (
        gltf_joint['translation'],
        gltf_joint['rotation'],
        gltf_joint['scale']
    ) = _decompose(matrix)

    return gltf_joint


def export_buffers(state):
    if state['settings']['buffers_combine_data']:
        buffers = [functools.reduce(
            lambda x, y: x.combine(y, state),
            state['buffers'],
            Buffer('empty')
        )]
        state['buffers'] = buffers
        state['input']['buffers'] = [SimpleID(buffers[0].name)]
    else:
        buffers = state['buffers']

    gltf = {}
    gltf['buffers'] = [buf.export_buffer(state) for buf in buffers]
    gltf['bufferViews'] = list(itertools.chain(*[buf.export_views(state) for buf in buffers]))
    gltf['accessors'] = list(itertools.chain(*[buf.export_accessors(state) for buf in buffers]))

    return gltf


def insert_root_nodes(state, root_matrix):
    for i, scene in enumerate(state['output']['scenes']):
        # Generate a new root node for each scene
        root_node = {
            'children': scene['nodes'],
            'matrix': root_matrix,
            'name': '{}_root'.format(scene['name']),
        }
        state['output']['nodes'].append(root_node)
        ref_name = '__scene_root_{}_'.format(i)
        state['input']['objects'].append(SimpleID(ref_name))

        # Replace scene node lists to just point to the new root nodes
        scene['nodes'] = []
        scene['nodes'].append(Reference('objects', ref_name, scene['nodes'], 0))
        state['references'].append(scene['nodes'][0])


def build_string_refmap(input_data):
    in_out_map = {
        'objects': 'nodes',
        'bones': 'nodes',
        'lamps': 'lights'
    }
    refmap = {}
    for key, value in input_data.items():
        refmap.update({
            (key, data.name): '{}_{}'.format(in_out_map.get(key, key), data.name)
            for data in value
        })
    return refmap


def build_int_refmap(input_data):
    refmap = {}
    for key, value in input_data.items():
        refmap.update({(key, data.name): i for i, data in enumerate(value)})
    return refmap


def initialize_state(settings=None):
    # Fill in any missing settings with defaults
    if not settings:
        settings = {}
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)

    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y
    # Initialize export state
    state = {
        'version': Version(settings['asset_version']),
        'settings': settings,
        'animation_dt': 1.0 / bpy.context.scene.render.fps,
        'mod_meshes_obj': {},
        'aspect_ratio': res_x / res_y,
        'mod_meshes': {},
        'shape_keys': {},
        'dupli_nodes': [],
        'bone_children': {},
        'skinned_meshes': set(),
        'extensions_used': [],
        'gl_extensions_used': [],
        'buffers': [],
        'samplers': [],
        'input': {
            'buffers': [],
            'accessors': [],
            'bufferViews': [],
            'objects': [],
            'bones': [],
            'anim_samplers': [],
            'samplers': [],
            'scenes': [],
            'skins': [],
            'materials': [],
            'dupli_ids': [],
        },
        'output': {
            'extensions': [],
        },
        'references': [],
        'files': {},
        'decompose_fn': _decompose,
        'decompose_mesh_fn': _decompose,
    }

    return state


def export_gltf(scene_delta, settings=None):
    state = initialize_state(settings)
    state['input'].update({key: list(value) for key, value in scene_delta.items()})

    # Filter out empty meshes
    if 'meshes' in state['input']:
        state['input']['meshes'] = [mesh for mesh in state['input']['meshes'] if mesh.loops]
        if 'objects' in state['input']:
            state['input']['objects'] = [
                obj for obj in state['input']['objects']
                if obj.type != 'MESH' or obj.data in state['input']['meshes']
            ]

    # Make sure any temporary meshes do not have animation data baked in
    default_scene = bpy.context.scene
    if not state['settings']['hacks_streaming']:
        saved_pose_positions = [armature.pose_position for armature in bpy.data.armatures]
        for armature in bpy.data.armatures:
            armature.pose_position = 'REST'
        if saved_pose_positions:
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE':
                    obj.update_tag()
        default_scene.frame_set(default_scene.frame_current)

    mesh_list = []
    mod_obs = [
        ob for ob in state['input']['objects']
        if [mod for mod in ob.modifiers if mod.type != 'ARMATURE']
    ]
    for mesh in state['input'].get('meshes', []):
        if mesh.shape_keys and mesh.shape_keys.use_relative:
            relative_key = mesh.shape_keys.key_blocks[0].relative_key
            keys = [key for key in mesh.shape_keys.key_blocks if key != relative_key]

            # Gather weight values
            weights = [key.value for key in keys]

            # Clear weight values
            for key in keys:
                key.value = 0.0
            mesh_users = [obj for obj in state['input']['objects'] if obj.data == mesh]

            # Mute modifiers if necessary
            muted_modifiers = []
            original_modifier_states = []
            if not state['settings']['meshes_apply_modifiers']:
                muted_modifiers = itertools.chain.from_iterable(
                    [obj.modifiers for obj in mesh_users]
                )
                original_modifier_states = [mod.show_viewport for mod in muted_modifiers]
                for modifier in muted_modifiers:
                    modifier.show_viewport = False

            for user in mesh_users:
                base_mesh = user.to_mesh(default_scene, True, 'PREVIEW')
                mesh_name = base_mesh.name
                state['mod_meshes_obj'][user.name] = base_mesh

                if mesh_name not in state['shape_keys']:
                    key_meshes = []
                    for key, weight in zip(keys, weights):
                        key.value = key.slider_max
                        key_meshes.append((
                            weight,
                            user.to_mesh(default_scene, True, 'PREVIEW')
                        ))
                        key.value = 0.0
                    state['shape_keys'][mesh_name] = key_meshes

            # Reset weight values
            for key, weight in zip(keys, weights):
                key.value = weight

            # Unmute modifiers
            for modifier, state in zip(muted_modifiers, original_modifier_states):
                modifier.show_viewport = state
        elif state['settings']['meshes_apply_modifiers']:
            mod_users = [ob for ob in mod_obs if ob.data == mesh]

            # Only convert meshes with modifiers, otherwise each non-modifier
            # user ends up with a copy of the mesh and we lose instancing
            state['mod_meshes_obj'].update(
                {ob.name: ob.to_mesh(default_scene, True, 'PREVIEW') for ob in mod_users}
            )

            # Add unmodified meshes directly to the mesh list
            if len(mod_users) < mesh.users:
                mesh_list.append(mesh)
        else:
            mesh_list.append(mesh)

    mesh_list.extend(state['mod_meshes_obj'].values())
    state['input']['meshes'] = mesh_list

    apply_global_matrix = (
        state['settings']['nodes_global_matrix'] != mathutils.Matrix.Identity(4)
        and state['settings']['nodes_global_matrix_apply']
    )
    if apply_global_matrix:
        global_mat = state['settings']['nodes_global_matrix']
        global_scale_mat = mathutils.Matrix([[abs(j) for j in i] for i in global_mat])

        def decompose_apply(matrix):
            loc, rot, scale = matrix.decompose()

            loc.rotate(global_mat)
            loc = loc.to_tuple()

            rot.rotate(global_mat)
            rot = (rot.x, rot.y, rot.z, rot.w)

            scale.rotate(global_scale_mat)
            scale = scale.to_tuple()

            return loc, rot, scale

        def decompose_mesh_apply(matrix):
            loc, rot, scale = matrix.decompose()

            loc.rotate(global_mat)
            loc = loc.to_tuple()

            rot = mathutils.Vector(list(rot.to_euler()))
            rot.rotate(global_mat)
            rot = mathutils.Euler(rot, 'XYZ').to_quaternion()
            rot = (rot.x, rot.y, rot.z, rot.w)

            scale.rotate(global_scale_mat)
            scale = scale.to_tuple()

            return loc, rot, scale
        state['decompose_fn'] = decompose_apply
        state['decompose_mesh_fn'] = decompose_mesh_apply

        transformed_meshes = [mesh.copy() for mesh in mesh_list]
        for mesh in transformed_meshes:
            mesh.transform(global_mat, shape_keys=False)
        state['mod_meshes'].update(
            {mesh.name: xformed_mesh for xformed_mesh, mesh in zip(transformed_meshes, mesh_list)}
        )
        for shape_key_list in state['shape_keys'].values():
            for shape_key in shape_key_list:
                shape_key[1].transform(global_mat, shape_keys=False)

    # Restore armature pose positions
    for i, armature in enumerate(bpy.data.armatures):
        armature.pose_position = saved_pose_positions[i]

    state['input']['action_pairs'] = AnimationExporter.gather(state)

    exporters = [
        CameraExporter,
        ImageExporter,
        NodeExporter,
        MaterialExporter,
        # Make sure meshes come after nodes to detect which meshes are skinned
        MeshExporter,
        SceneExporter,
        SkinExporter,
        TextureExporter,
        AnimationExporter,
    ]
    state['output'] = {
        exporter.gltf_key: [
            exporter.export(state, data)
            if exporter.check(state, data)
            else exporter.default(state, data)
            for data in state['input'].get(exporter.blender_key, [])
        ] for exporter in exporters
    }

    # Export top level data
    gltf = {
        'asset': {
            'version': state['settings']['asset_version'],
            'generator': 'blendergltf v1.2.0',
            'copyright': state['settings']['asset_copyright'],
        }
    }
    if state['version'] < Version('2.0'):
        gltf['asset']['profile'] = PROFILE_MAP[state['settings']['asset_profile']]

    # Export samplers
    state['output']['samplers'] = state['samplers']

    # Export animations
    state['output']['nodes'].extend([
        export_joint(state, sid.data) for sid in state['input']['bones']
    ])

    # Move bones to nodes for updating references
    state['input']['objects'].extend(state['input']['bones'])
    state['input']['bones'] = []

    # Export dupli-groups
    state['output']['nodes'].extend(state['dupli_nodes'])
    state['input']['objects'].extend(state['input']['dupli_ids'])
    state['input']['dupli_ids'] = []

    # Export default scene
    default_scene = None
    for scene in state['input']['scenes']:
        if scene == bpy.context.scene:
            default_scene = scene
    if default_scene:
        scene_ref = Reference('scenes', bpy.context.scene.name, gltf, 'scene')
        scene_ref.value = 0
        state['references'].append(scene_ref)

    # Export extensions
    state['refmap'] = build_int_refmap(state['input'])
    for ext_exporter in state['settings']['extension_exporters']:
        ext_exporter.export(state)

    # Insert root nodes if axis conversion is needed
    root_node_needed = (
        state['settings']['nodes_global_matrix'] != mathutils.Matrix.Identity(4)
        and not state['settings']['nodes_global_matrix_apply']
    )
    if root_node_needed:
        insert_root_nodes(state, togl(state['settings']['nodes_global_matrix']))

    if state['buffers']:
        state['output'].update(export_buffers(state))
    state['output'] = {key: value for key, value in state['output'].items() if value != []}
    if state['extensions_used']:
        gltf.update({'extensionsUsed': state['extensions_used']})
    if state['version'] < Version('2.0'):
        gltf.update({'glExtensionsUsed': state['gl_extensions_used']})

    # Convert lists to dictionaries
    if state['version'] < Version('2.0'):
        extensions = state['output'].get('extensions', [])
        state['output'] = {
            key: {
                '{}_{}'.format(key, data['name']): data for data in value
            } for key, value in state['output'].items()
            if key != 'extensions'
        }
        if extensions:
            state['output']['extensions'] = extensions
    gltf.update(state['output'])

    # Gather refmap inputs
    reference_inputs = state['input']
    if state['settings']['hacks_streaming']:
        reference_inputs.update({
            'actions': list(bpy.data.actions),
            'cameras': list(bpy.data.cameras),
            'lamps': list(bpy.data.lamps),
            'images': list(bpy.data.images),
            'materials': list(bpy.data.materials),
            'meshes': list(bpy.data.meshes),
            'objects': list(bpy.data.objects),
            'scenes': list(bpy.data.scenes),
            'textures': list(bpy.data.textures),
        })

    # Resolve references
    if state['version'] < Version('2.0'):
        refmap = build_string_refmap(reference_inputs)
        ref_default = 'INVALID'
    else:
        refmap = build_int_refmap(reference_inputs)
        ref_default = -1
    for ref in state['references']:
        ref.source[ref.prop] = refmap.get((ref.blender_type, ref.blender_name), ref_default)
        if ref.source[ref.prop] == ref_default:
            print(
                'Warning: {} contains an invalid reference to {}'
                .format(ref.source, (ref.blender_type, ref.blender_name))
            )

    # Remove any temporary meshes
    temp_mesh_collections = (
        state['mod_meshes'].values(),
        state['mod_meshes_obj'].values(),
        [
            shape_key_pair[1] for shape_key_pair
            in itertools.chain.from_iterable(state['shape_keys'].values())
        ]
    )
    for mesh in itertools.chain(*temp_mesh_collections):
        bpy.data.meshes.remove(mesh)

    # Transform gltf data to binary
    if state['settings']['gltf_export_binary']:
        json_data = json.dumps(gltf, sort_keys=True, check_circular=False).encode()
        json_length = len(json_data)
        json_pad = (' ' * (4 - json_length % 4)).encode()
        json_pad = json_pad if len(json_pad) != 4 else b''
        json_length += len(json_pad)
        json_format = '<II{}s{}s'.format(len(json_data), len(json_pad))
        chunks = [struct.pack(json_format, json_length, 0x4e4f534a, json_data, json_pad)]

        if settings['buffers_embed_data']:
            buffers = [data for path, data in state['files'].items() if path.endswith('.bin')]

            # Get padded lengths
            lengths = [len(buffer) for buffer in buffers]
            lengths = [
                length + ((4 - length % 4) if length % 4 != 0 else 0)
                for length in lengths
            ]

            chunks.extend([
                struct.pack('<II{}s'.format(length), length, 0x004E4942, buffer)
                for buffer, length in zip(buffers, lengths)
            ])

            state['files'] = {
                path: data for path, data in state['files'].items()
                if not path.endswith('.bin')
            }

        version = 2
        size = 12
        for chunk in chunks:
            size += len(chunk)
        header = struct.pack('<4sII', b'glTF', version, size)

        gltf = bytes(0).join([header, *chunks])

    # Write secondary files
    for path, data in state['files'].items():
        with open(path, 'wb') as fout:
            fout.write(data)

    return gltf
