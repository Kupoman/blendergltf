from distutils.version import StrictVersion as Version

import mathutils

from .base import BaseExporter
from .common import (
    Buffer,
    Reference,
    SimpleID,
    get_bone_name,
)


def togl(matrix):
    return [i for col in matrix.col for i in col]


class SkinExporter(BaseExporter):
    gltf_key = 'skins'
    blender_key = 'skins'

    @classmethod
    def export(cls, state, blender_data):
        if state['version'] < Version('2.0'):
            joints_key = 'jointNames'
        else:
            joints_key = 'joints'

        arm = blender_data.find_armature()

        axis_mat = mathutils.Matrix.Identity(4)
        if state['settings']['nodes_global_matrix_apply']:
            axis_mat = state['settings']['nodes_global_matrix']

        bind_shape_mat = (
            axis_mat
            * arm.matrix_world.inverted()
            * blender_data.matrix_world
            * axis_mat.inverted()
        )

        bone_groups = [
            group for group in blender_data.vertex_groups if group.name in arm.data.bones
        ]

        gltf_skin = {
            'name': blender_data.name,
        }
        gltf_skin[joints_key] = [
            Reference('objects', get_bone_name(arm.data.bones[group.name]), None, None)
            for group in bone_groups
        ]
        for i, ref in enumerate(gltf_skin[joints_key]):
            ref.source = gltf_skin[joints_key]
            ref.prop = i
            state['references'].append(ref)

        if state['version'] < Version('2.0'):
            gltf_skin['bindShapeMatrix'] = togl(mathutils.Matrix.Identity(4))
        else:
            bone_names = [get_bone_name(b) for b in arm.data.bones if b.parent is None]
            if len(bone_names) > 1:
                print('Warning: Armature {} has no root node'.format(arm.data.name))
            gltf_skin['skeleton'] = Reference('objects', bone_names[0], gltf_skin, 'skeleton')
            state['references'].append(gltf_skin['skeleton'])

        element_size = 16 * 4
        num_elements = len(bone_groups)
        buf = Buffer('IBM_{}_skin'.format(blender_data.name))
        buf_view = buf.add_view(element_size * num_elements, element_size, None)
        idata = buf.add_accessor(buf_view, 0, element_size, Buffer.FLOAT, num_elements, Buffer.MAT4)

        for i, group in enumerate(bone_groups):
            bone = arm.data.bones[group.name]
            mat = togl((axis_mat * bone.matrix_local).inverted() * bind_shape_mat)
            for j in range(16):
                idata[(i * 16) + j] = mat[j]

        gltf_skin['inverseBindMatrices'] = Reference(
            'accessors',
            idata.name,
            gltf_skin,
            'inverseBindMatrices'
        )
        state['references'].append(gltf_skin['inverseBindMatrices'])
        state['buffers'].append(buf)
        state['input']['buffers'].append(SimpleID(buf.name))

        return gltf_skin
