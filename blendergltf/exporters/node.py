from distutils.version import StrictVersion as Version

from .base import BaseExporter

from .common import (
    Reference,
    SimpleID,
    get_bone_name,
)


class NodeExporter(BaseExporter):
    gltf_key = 'nodes'
    blender_key = 'objects'

    @classmethod
    def export(cls, state, blender_data):
        node = {
            'name': blender_data.name,
        }

        obj_children = [
            child for child in blender_data.children
            if child in state['input']['objects'] and not child.parent_bone
        ]
        if obj_children:
            node['children'] = []
        for i, child in enumerate(obj_children):
            node['children'].append(Reference('objects', child.name, node['children'], i))
            state['references'].append(node['children'][-1])

        extras = cls.get_custom_properties(blender_data)
        extras.update({
            prop.name: prop.value for prop in blender_data.game.properties.values()
        })
        if extras:
            node['extras'] = extras

        decompose = state['decompose_fn']

        if blender_data.parent and blender_data.parent_bone:
            parent_bone = blender_data.parent.data.bones[blender_data.parent_bone]
            bone_name = get_bone_name(parent_bone)
            if bone_name not in state['bone_children']:
                state['bone_children'][bone_name] = []
            state['bone_children'][bone_name].append(blender_data.name)

        if blender_data.type == 'MESH':
            decompose = state['decompose_mesh_fn']
            mesh = state['mod_meshes_obj'].get(blender_data.name, blender_data.data)
            mesh_name = mesh.name
            mesh = state['mod_meshes'].get(mesh.name, mesh)
            if state['version'] < Version('2.0'):
                node['meshes'] = []
                node['meshes'].append(Reference('meshes', mesh_name, node['meshes'], 0))
                state['references'].append(node['meshes'][0])
            else:
                node['mesh'] = Reference('meshes', mesh_name, node, 'mesh')
                state['references'].append(node['mesh'])
            armature = blender_data.find_armature()
            if armature:
                state['input']['skins'].append(blender_data)
                state['skinned_meshes'].add(mesh_name)
                node['skin'] = Reference('skins', blender_data.name, node, 'skin')
                state['references'].append(node['skin'])
                if state['version'] < Version('2.0'):
                    bone_names = [
                        get_bone_name(b) for b in armature.data.bones if b.parent is None
                    ]
                    node['skeletons'] = []
                    node['skeletons'].extend([
                        Reference('objects', bone, node['skeletons'], i)
                        for i, bone in enumerate(bone_names)
                    ])
                    for ref in node['skeletons']:
                        state['references'].append(ref)
        elif blender_data.type == 'CAMERA':
            node['camera'] = Reference('cameras', blender_data.data.name, node, 'camera')
            state['references'].append(node['camera'])
        elif blender_data.type == 'EMPTY' and blender_data.dupli_group is not None:
            node['children'] = node.get('children', [])
            node['children'].append(cls.export_dupli_group(state, blender_data.dupli_group))
            node['children'][-1].source = node['children']
            node['children'][-1].prop = len(node['children']) - 1
        elif blender_data.type == 'ARMATURE':
            decompose = state['decompose_mesh_fn']
            for i, bone in enumerate(blender_data.data.bones):
                state['input']['bones'].append(SimpleID(get_bone_name(bone), bone))
            if 'children' not in node:
                node['children'] = []
            offset = len(node['children'])
            root_bones = [bone for bone in blender_data.data.bones if bone.parent is None]
            root_refs = [
                Reference('objects', get_bone_name(b), node['children'], i + offset)
                for i, b in enumerate(root_bones)
            ]

            for bone in root_refs:
                state['references'].append(bone)
            node['children'].extend(root_refs)

        (
            node['translation'],
            node['rotation'],
            node['scale']
        ) = decompose(blender_data.matrix_local)

        return node

    @classmethod
    def export_dupli_group(cls, state, dupli_group):
        group_sid = SimpleID(
            'dupli_group_{}.{}'.format(dupli_group.name, len(state['dupli_nodes']))
        )
        state['input']['dupli_ids'].append(group_sid)

        group_node = {
            'name': group_sid.name,
        }
        state['dupli_nodes'].append(group_node)

        dupli_nodes = [group_node]
        children = []

        for dupli_obj in dupli_group.objects:
            obj_node = cls.export(state, dupli_obj)
            state['dupli_nodes'].append(obj_node)

            obj_sid = SimpleID(
                'dupli_node_{}.{}'.format(dupli_obj.name, len(state['dupli_nodes']))
            )
            state['input']['dupli_ids'].append(obj_sid)

            obj_node['name'] = obj_sid.name
            if dupli_obj.dupli_group is None and 'children' in obj_node:
                del obj_node['children']

            obj_ref = Reference('objects', obj_sid.name, children, len(children))
            children.append(obj_ref)
            state['references'].append(obj_ref)

            dupli_nodes.append(obj_node)

        group_node['children'] = children

        group_ref = Reference('objects', group_sid.name, None, None)
        state['references'].append(group_ref)
        return group_ref
