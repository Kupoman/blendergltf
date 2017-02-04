bl_info = {
    "name": "glTF format",
    "author": "Daniel Stokes",
    "version": (0, 1, 0),
    "blender": (2, 76, 0),
    "location": "File > Import-Export",
    "description": "Export glTF",
    "warning": "",
    "wiki_url": ""
                "",
    "support": 'TESTING',
    "category": "Import-Export"}


# Treat as module
if '.' in __name__:
    if 'loaded' in locals():
        import imp
        imp.reload(blendergltf)
        from .blendergltf import *
    else:
        loaded = True
        from .blendergltf import *

# Treat as addon
else:
    if "bpy" in locals():
        import importlib
        importlib.reload(blendergltf)


    import json
    import os

    import bpy
    from bpy.props import *
    from bpy_extras.io_utils import (
        ExportHelper,
        orientation_helper_factory,
        axis_conversion,
    )

    from . import blendergltf


    GLTFOrientationHelper = orientation_helper_factory(
        "GLTFOrientationHelper", axis_forward='Y', axis_up='Z'
    )


    profile_items = (
        ('WEB', 'Web', 'Export shaders for WebGL 1.0 use (shader version 100)'),
        ('DESKTOP', 'Desktop', 'Export shaders for OpenGL 3.0 use (shader version 130)')
    )

    image_storage_items = (
        ('EMBED', 'Embed', 'Embed image data into the glTF file'),
        ('REFERENCE', 'Reference', 'Use the same filepath that Blender uses for images'),
        ('COPY', 'Copy', 'Copy images to output directory and use a relative reference')
    )

    shader_storage_items = (
        ('EMBED', 'Embed', 'Embed shader data into the glTF file'),
        ('NONE', 'None', 'Use the KHR_material_common extension instead of a shader'),
        ('EXTERNAL', 'External', 'Save shaders to the output directory')
    )

    def get_pruned_blocks(bpy_data, selection_only, export_hidden):

        def selected_in_subtree(parent_obj):
            """Return True if object or any of its children
               is selected in the outline tree, False otherwise.

            """
            if parent_obj.select:
                return True
            if len(parent_obj.children) > 0:
                return any(selected_in_subtree(child) for child in parent_obj.children)
            else:
                return False

        pruned_data = {
            'actions': bpy_data.actions.values(),
            'cameras': [],
            'lamps': [],
            'images': [],
            'materials': [],
            'meshes': [],
            'objects': [],
            'scenes': [],
            'textures': []
        }

        # get list of objects
        for obj in bpy_data.objects.values():

            # filter out objects not to be exported
            selection_passed = not selection_only or selected_in_subtree(obj)
            hidden_passed = not obj.hide or export_hidden
            if selection_passed and hidden_passed:

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
                        if mat not in pruned_data['materials']:
                            pruned_data['materials'].append(mat)

                            # add textures to list
                            for tex in [slot.texture for slot in mat.texture_slots.values()
                                if slot != None and slot.use and isinstance(slot.texture, bpy.types.ImageTexture)]:
                                if tex not in pruned_data['textures']:
                                    pruned_data['textures'].append(tex)

                                # add images to list
                                if tex.image not in pruned_data['images']:
                                    pruned_data['images'].append(tex.image)


        return pruned_data


    class ExportGLTF(bpy.types.Operator, ExportHelper, GLTFOrientationHelper):
        """Save a Khronos glTF File"""

        bl_idname = "export_scene.gltf"
        bl_label = 'Export glTF'

        filename_ext = ".gltf"
        filter_glob = StringProperty(
                default="*.gltf",
                options={'HIDDEN'},
                )

        check_extension = True

        #blendergltf settings
        buffers_embed_data = BoolProperty(name='Embed Buffer Data', default=False)
        buffers_combine_data = BoolProperty(name='Combine Buffer Data', default=True)
        nodes_export_hidden = BoolProperty(name='Export Hidden Objects', default=False)
        nodes_selected_only = BoolProperty(name='Selection Only', default=False)
        shaders_data_storage = EnumProperty(items=shader_storage_items, name='Shader Storage', default='NONE')
        meshes_apply_modifiers = BoolProperty(name='Apply Modifiers', default=True)
        meshes_interleave_vertex_data = BoolProperty(name='Interleave Vertex Data', default=True)
        images_data_storage = EnumProperty(items=image_storage_items, name='Image Storage', default='COPY')
        asset_profile = EnumProperty(items=profile_items, name='Profile', default='WEB')
        ext_export_physics = BoolProperty(name='Export Physics Settings', default=False)
        ext_export_actions = BoolProperty(name='Export Actions', default=False)

        pretty_print = BoolProperty(
            name="Pretty-print / indent JSON",
            description="Export JSON with indentation and a newline",
            default=True
            )

        def execute(self, context):

            # Copy properties to settings
            settings = self.as_keywords(ignore=(
                "filter_glob",
                "axis_up",
                "axis_forward",
            ))

            # Set the output directory based on the supplied file path
            settings['gltf_output_dir'] = os.path.dirname(self.filepath)

            # Calculate a global transform matrix to apply to a root node
            settings['nodes_global_matrix'] = axis_conversion(
                to_forward=self.axis_forward,
                to_up=self.axis_up
            ).to_4x4()

            scene = get_pruned_blocks(bpy.data, settings['nodes_selected_only'], settings['nodes_export_hidden'])
            gltf = blendergltf.export_gltf(scene, settings)
            with open(self.filepath, 'w') as fout:
                # Figure out indentation
                if self.pretty_print:
                    indent = 4
                else:
                    indent = None

                # Dump the JSON
                json.dump(gltf, fout, indent=indent, sort_keys=True,
                          check_circular=False)

                if self.pretty_print:
                    # Write a newline to the end of the file
                    fout.write('\n')
            return {'FINISHED'}


    def menu_func_export(self, context):
        self.layout.operator(ExportGLTF.bl_idname, text="glTF (.gltf)")


    def register():
        bpy.utils.register_module(__name__)

        bpy.types.INFO_MT_file_export.append(menu_func_export)


    def unregister():
        bpy.utils.unregister_module(__name__)

        bpy.types.INFO_MT_file_export.remove(menu_func_export)
