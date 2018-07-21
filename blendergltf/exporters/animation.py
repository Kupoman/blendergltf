from distutils.version import StrictVersion as Version
import itertools

import bpy
import mathutils

from .base import BaseExporter
from .common import (
    AnimationPair,
    Buffer,
    Reference,
    SimpleID,
    get_bone_name,
)


def _decompose(matrix):
    loc, rot, scale = matrix.decompose()
    loc = loc.to_tuple()
    rot = (rot.x, rot.y, rot.z, rot.w)
    scale = scale.to_tuple()

    return loc, rot, scale


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


class AnimationExporter(BaseExporter):
    gltf_key = 'animations'
    blender_key = 'action_pairs'

    @classmethod
    def gather_actions(cls, state):
        armature_objects = [obj for obj in state['input']['objects'] if obj.type == 'ARMATURE']
        regular_objects = [obj for obj in state['input']['objects'] if obj.type != 'ARMATURE']

        actions = []

        def export_eligible(objects):
            for obj in objects:
                actions.extend([
                    AnimationPair(obj, action) for action in state['input']['actions']
                    if _can_object_use_action(obj, action)
                ])

        def export_active(objects):
            for obj in objects:
                if obj.animation_data and obj.animation_data.action:
                    actions.append(AnimationPair(obj, obj.animation_data.action))

        armature_setting = state['settings']['animations_armature_export']
        object_setting = state['settings']['animations_object_export']

        if armature_setting == 'ACTIVE':
            export_active(armature_objects)
        elif armature_setting == 'ELIGIBLE':
            export_eligible(armature_objects)
        else:
            print(
                'WARNING: Unrecognized setting for animations_armature_export:',
                '{}'.format(armature_setting)
            )

        if object_setting == 'ACTIVE':
            export_active(regular_objects)
        elif object_setting == 'ELIGIBLE':
            export_eligible(regular_objects)
        else:
            print(
                'WARNING: Unrecognized setting for animations_object_export:',
                '{}'.format(object_setting)
            )

        return actions

    @classmethod
    def gather_shape_key_actions(cls, state):
        shape_key_objects = [
            obj for obj in state['input']['objects']
            if obj.type == 'MESH' and obj.data.shape_keys
        ]
        shape_key_setting = state['settings']['animations_shape_key_export']

        shape_key_actions = []

        if shape_key_setting == 'ACTIVE':
            for obj in shape_key_objects:
                action = obj.data.shape_keys.animation_data.action
                shape_key_actions.append(AnimationPair(obj, action, True))
        elif shape_key_setting == 'ELIGIBLE':
            for obj in shape_key_objects:
                eligible_actions = []
                shape_keys = set([
                    block.name for block in obj.data.shape_keys.key_blocks
                    if block != block.relative_key
                ])
                for action in state['input']['actions']:
                    fcurve_keys = set([fcurve.data_path.split('"')[1] for fcurve in action.fcurves])
                    if fcurve_keys <= shape_keys:
                        eligible_actions.append(action)
                for action in eligible_actions:
                    shape_key_actions.append(AnimationPair(obj, action, True))
        else:
            print(
                'WARNING: Unrecognized setting for animations_shape_key_export:',
                '{}'.format(shape_key_setting)
            )

        return shape_key_actions

    @classmethod
    def gather(cls, state):
        actions = cls.gather_actions(state)
        actions.extend(cls.gather_shape_key_actions(state))
        return actions

    @classmethod
    def export_action(cls, state, blender_data):
        obj = blender_data.target
        action = blender_data.action
        action_name = blender_data.name

        if state['version'] < Version('2.0'):
            target_key = 'id'
        else:
            target_key = 'node'

        channels = {}
        decompose = state['decompose_fn']
        axis_mat = mathutils.Matrix.Identity(4)
        if state['settings']['nodes_global_matrix_apply']:
            axis_mat = state['settings']['nodes_global_matrix']

        sce = bpy.context.scene
        prev_frame = sce.frame_current
        prev_action = obj.animation_data.action

        frame_start, frame_end = [int(x) for x in action.frame_range]
        num_frames = frame_end - frame_start + 1
        obj.animation_data.action = action

        has_location = set()
        has_rotation = set()
        has_scale = set()

        # Check action groups to see what needs to be animated
        pose_bones = {}
        for group in action.groups:
            for channel in group.channels:
                data_path = channel.data_path
                if obj.pose and 'pose.bones' in data_path:
                    target_name = data_path.split('"')[1]
                    transform = data_path.split('.')[-1]
                    pose_bones[obj.pose.bones[target_name]] = None
                else:
                    target_name = obj.name
                    transform = data_path.lower()
                    if obj.name not in channels:
                        channels[obj.name] = []

                if 'location' in transform:
                    has_location.add(target_name)
                if 'rotation' in transform:
                    has_rotation.add(target_name)
                if 'scale' in transform:
                    has_scale.add(target_name)
        channels.update({pbone.name: [] for pbone in pose_bones})

        # Iterate frames and bake animations
        for frame in range(frame_start, frame_end + 1):
            sce.frame_set(frame)

            if obj.name in channels:
                # Decompose here so we don't store a reference to the matrix
                loc, rot, scale = decompose(obj.matrix_local)
                if obj.name not in has_location:
                    loc = None
                if obj.name not in has_rotation:
                    rot = None
                if obj.name not in has_scale:
                    scale = None
                channels[obj.name].append((loc, rot, scale))

            for pbone in pose_bones:
                if pbone.parent:
                    mat = pbone.parent.matrix.inverted() * pbone.matrix
                else:
                    mat = axis_mat * pbone.matrix

                loc, rot, scale = _decompose(mat)

                if pbone.name not in has_location:
                    loc = None
                if pbone.name not in has_rotation:
                    rot = None
                if pbone.name not in has_scale:
                    scale = None
                channels[pbone.name].append((loc, rot, scale))

        gltf_channels = []
        gltf_parameters = {}
        gltf_samplers = []

        tbuf = Buffer('{}_time'.format(action_name))
        tbv = tbuf.add_view(num_frames * 1 * 4, 1 * 4, None)
        tdata = tbuf.add_accessor(tbv, 0, 1 * 4, Buffer.FLOAT, num_frames, Buffer.SCALAR)
        time = 0
        for i in range(num_frames):
            tdata[i] = time
            time += state['animation_dt']
        state['buffers'].append(tbuf)
        state['input']['buffers'].append(SimpleID(tbuf.name))
        time_parameter_name = '{}_time_parameter'.format(action_name)
        ref = Reference('accessors', tdata.name, gltf_parameters, time_parameter_name)
        gltf_parameters[time_parameter_name] = ref
        state['references'].append(ref)

        input_list = '{}_{}_samplers'.format(action_name, obj.name)
        state['input'][input_list] = []

        sampler_keys = []
        for targetid, chan in channels.items():
            buf = Buffer('{}_{}'.format(targetid, action_name))
            ldata = rdata = sdata = None
            paths = []
            if targetid in has_location:
                lbv = buf.add_view(num_frames * 3 * 4, 3 * 4, None)
                ldata = buf.add_accessor(lbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)
                paths.append('translation')
            if targetid in has_rotation:
                rbv = buf.add_view(num_frames * 4 * 4, 4 * 4, None)
                rdata = buf.add_accessor(rbv, 0, 4 * 4, Buffer.FLOAT, num_frames, Buffer.VEC4)
                paths.append('rotation')
            if targetid in has_scale:
                sbv = buf.add_view(num_frames * 3 * 4, 3 * 4, None)
                sdata = buf.add_accessor(sbv, 0, 3 * 4, Buffer.FLOAT, num_frames, Buffer.VEC3)
                paths.append('scale')

            if not paths:
                continue

            for i in range(num_frames):
                loc, rot, scale = chan[i]
                if ldata:
                    for j in range(3):
                        ldata[(i * 3) + j] = loc[j]
                if sdata:
                    for j in range(3):
                        sdata[(i * 3) + j] = scale[j]
                if rdata:
                    for j in range(4):
                        rdata[(i * 4) + j] = rot[j]

            state['buffers'].append(buf)
            state['input']['buffers'].append(SimpleID(buf.name))

            is_bone = False
            if targetid != obj.name:
                is_bone = True
                targetid = get_bone_name(bpy.data.armatures[obj.data.name].bones[targetid])

            for path in paths:
                sampler_name = '{}_{}_{}_sampler'.format(action_name, targetid, path)
                sampler_keys.append(sampler_name)
                parameter_name = '{}_{}_{}_parameter'.format(action_name, targetid, path)

                gltf_channel = {
                    'sampler': sampler_name,
                    'target': {
                        target_key: targetid,
                        'path': path,
                    }
                }
                gltf_channels.append(gltf_channel)
                id_ref = Reference(
                    'objects' if is_bone else 'objects',
                    targetid,
                    gltf_channel['target'],
                    target_key
                )
                state['references'].append(id_ref)
                state['input'][input_list].append(SimpleID(sampler_name))
                sampler_ref = Reference(input_list, sampler_name, gltf_channel, 'sampler')
                state['references'].append(sampler_ref)

                gltf_sampler = {
                    'input': None,
                    'interpolation': 'LINEAR',
                    'output': None,
                }
                gltf_samplers.append(gltf_sampler)

                accessor_name = {
                    'translation': ldata.name if ldata else None,
                    'rotation': rdata.name if rdata else None,
                    'scale': sdata.name if sdata else None,
                }[path]

                if state['version'] < Version('2.0'):
                    gltf_sampler['input'] = time_parameter_name
                    gltf_sampler['output'] = parameter_name
                    accessor_ref = Reference(
                        'accessors',
                        accessor_name,
                        gltf_parameters,
                        parameter_name
                    )
                    gltf_parameters[parameter_name] = accessor_ref
                else:
                    time_ref = Reference(
                        'accessors',
                        tdata.name,
                        gltf_sampler,
                        'input'
                    )
                    gltf_sampler['input'] = time_ref
                    state['references'].append(time_ref)
                    accessor_ref = Reference(
                        'accessors',
                        accessor_name,
                        gltf_sampler,
                        'output'
                    )
                    gltf_sampler['output'] = accessor_ref

                state['references'].append(accessor_ref)

        gltf_action = {
            'name': blender_data.action.name,
            'channels': gltf_channels,
            'samplers': gltf_samplers,
        }

        if state['version'] < Version('2.0'):
            gltf_action['samplers'] = {
                '{}_{}'.format(input_list, i[0]): i[1]
                for i in zip(sampler_keys, gltf_action['samplers'])
            }
            gltf_action['parameters'] = gltf_parameters

        sce.frame_set(prev_frame)
        obj.animation_data.action = prev_action

        return gltf_action

    @classmethod
    def export_shape_key_action(cls, state, blender_data):
        obj = blender_data.target
        action = blender_data.action
        action_name = blender_data.name

        fcurves = action.fcurves
        frame_range = action.frame_range
        frame_count = int(frame_range[1]) - int(frame_range[0])
        for fcurve in fcurves:
            fcurve.convert_to_samples(*frame_range)
        samples = {
            fcurve.data_path.split('"')[1]: [point.co[1] for point in fcurve.sampled_points]
            for fcurve in fcurves
        }
        shape_keys = [
            block for block in obj.data.shape_keys.key_blocks
            if block != block.relative_key
        ]
        empty_data = [0.0] * frame_count

        weight_data = zip(*[samples.get(key.name, empty_data) for key in shape_keys])
        weight_data = itertools.chain.from_iterable(weight_data)
        dt_data = [state['animation_dt'] * i for i in range(frame_count)]

        anim_buffer = Buffer('{}_{}'.format(obj.name, action_name))
        state['buffers'].append(anim_buffer)
        state['input']['buffers'].append(SimpleID(anim_buffer.name))

        time_view = anim_buffer.add_view(frame_count * 1 * 4, 1 * 4, None)
        time_acc = anim_buffer.add_accessor(
            time_view,
            0,
            1 * 4,
            Buffer.FLOAT,
            frame_count,
            Buffer.SCALAR
        )
        for i, dt in enumerate(dt_data):
            time_acc[i] = dt

        key_count = len(shape_keys)
        weight_view = anim_buffer.add_view(frame_count * key_count * 4, 4, None)
        weight_acc = anim_buffer.add_accessor(
            weight_view,
            0,
            1 * 4,
            Buffer.FLOAT,
            frame_count * key_count,
            Buffer.SCALAR
        )
        for i, weight in enumerate(weight_data):
            weight_acc[i] = weight

        channel = {
            'sampler': 0,
            'target': {
                'path': 'weights',
            },
        }
        channel['target']['node'] = Reference('objects', obj.name, channel['target'], 'node')
        state['references'].append(channel['target']['node'])

        sampler = {
            'interpolation': 'LINEAR',
        }
        sampler['input'] = Reference('accessors', time_acc.name, sampler, 'input')
        state['references'].append(sampler['input'])
        sampler['output'] = Reference('accessors', weight_acc.name, sampler, 'output')
        state['references'].append(sampler['output'])

        gltf_action = {
            'name': blender_data.action.name,
            'channels': [channel],
            'samplers': [sampler],
        }

        return gltf_action

    @classmethod
    def export(cls, state, blender_data):
        if blender_data.is_shape_key:
            return cls.export_shape_key_action(state, blender_data)

        return cls.export_action(state, blender_data)
