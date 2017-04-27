#!/bin/env python
import bpy


def visible_only(bpy_data):
    """
    Filter out all the invisible objects
    """

    def visible(obj):
        return any(obj.is_visible(s) for s in bpy_data['scenes'])

    bpy_data['objects'] = [obj for obj in bpy_data['objects'] if visible(obj)]
    return bpy_data


def selected_only(bpy_data):
    """
    Filter out all the objects that are not selected
    """

    def selected_in_subtree(parent_obj):
        return parent_obj.select or any(selected_in_subtree(child) for child in parent_obj.children)

    bpy_data['objects'] = [obj for obj in bpy_data['objects'] if selected_in_subtree(obj)]
    return bpy_data


def used_only(bpy_data):
    """
    Filter out the data blocks not in use by the objects in the list
    """

    pruned_data = {
        'actions': bpy_data['actions'],
        'cameras': [],
        'lamps': [],
        'images': [],
        'materials': [],
        'meshes': [],
        'objects': [],
        'scenes': [],
        'textures': [],
    }

    # get list of objects
    for obj in bpy_data['objects']:

        # add object to list
        pruned_data['objects'].append(obj)

        # add scene to list
        for scene in obj.users_scene:
            if scene not in pruned_data['scenes']:
                pruned_data['scenes'].append(scene)

        # add cameras to list
        if isinstance(obj.data, bpy.types.Camera):
            pruned_data['cameras'].append(obj.data)

        # add lights to list
        elif isinstance(obj.data, bpy.types.Lamp):
            pruned_data['lamps'].append(obj.data)

        # add meshes to list
        elif isinstance(obj.data, bpy.types.Mesh):
            pruned_data['meshes'].append(obj.data)

            # add materials to list
            for mat in obj.data.materials.values():
                if not mat:
                    continue

                if mat not in pruned_data['materials']:
                    pruned_data['materials'].append(mat)

                    # add textures to list
                    textures = [
                        slot.texture for slot in mat.texture_slots.values()
                        if slot is not None
                        and slot.use
                        and isinstance(slot.texture, bpy.types.ImageTexture)
                    ]
                    for tex in textures:
                        if tex not in pruned_data['textures']:
                            pruned_data['textures'].append(tex)

                        # add images to list
                        if tex.image not in pruned_data['images']:
                            pruned_data['images'].append(tex.image)

    return pruned_data
