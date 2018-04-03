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

    # Clear flags
    for data_list in bpy_data.values():
        for data in data_list:
            data.tag = False

    # Always mark actions as used
    for action in bpy_data['actions']:
        action.tag = True

    # Need a function to handle some recursion for dupli-groups
    def tag_object(obj):
        obj.tag = True

        if obj.dupli_group:
            for dupli_obj in obj.dupli_group.objects:
                tag_object(dupli_obj)

        for scene in obj.users_scene:
            scene.tag = True

        if obj.data:
            obj.data.tag = True

        materials = []
        if obj.data and hasattr(obj.data, 'materials'):
            materials = [material for material in obj.data.materials.values() if material]

        for material in materials:
            material.tag = True

            textures = [
                slot.texture for slot in material.texture_slots.values()
                if slot is not None
                and slot.use
                and isinstance(slot.texture, bpy.types.ImageTexture)
            ]
            for texture in textures:
                texture.tag = True

                if texture.image:
                    texture.image.tag = True

    # Now let's go through the objects and start tagging
    for obj in bpy_data['objects']:
        tag_object(obj)

    pruned_data = {
        key: [data for data in value if data.tag] for key, value in bpy_data.items()
    }

    return pruned_data
