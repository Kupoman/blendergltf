bl_info = {
    "name": "glTF format",
    "author": "Daniel Stokes",
    "version": (0, 9, 0),
    "blender": (2, 76, 0),
    "location": "File > Import-Export",
    "description": "Export glTF",
    "warning": "",
    "wiki_url": ""
                "",
    "support": 'TESTING',
    "category": "Import-Export"}


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

from .blendergltf import *


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
    shaders_data_storage = EnumProperty(items=shader_storage_items, name='Storage', default='NONE')
    meshes_apply_modifiers = BoolProperty(name='Apply Modifiers', default=True)
    meshes_interleave_vertex_data = BoolProperty(name='Interleave Vertex Data', default=True)
    images_data_storage = EnumProperty(items=image_storage_items, name='Storage', default='COPY')
    images_allow_srgb = BoolProperty(name='sRGB Texture Support', default=False)
    asset_profile = EnumProperty(items=profile_items, name='Profile', default='WEB')
    ext_export_physics = BoolProperty(name='Export Physics Settings', default=False)

    pretty_print = BoolProperty(
        name="Pretty-print / indent JSON",
        description="Export JSON with indentation and a newline",
        default=True
        )

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col = layout.box().column()
        col.label('Axis Conversion:', icon='MANIPUL')
        col.prop(self, 'axis_up')
        col.prop(self, 'axis_forward')

        col = layout.box().column()
        col.label('Nodes:', icon='OBJECT_DATA')
        col.prop(self, 'nodes_export_hidden')
        col.prop(self, 'nodes_selected_only')

        col = layout.box().column()
        col.label('Meshes:', icon='MESH_DATA')
        col.prop(self, 'meshes_apply_modifiers')
        col.prop(self, 'meshes_interleave_vertex_data')

        col = layout.box().column()
        col.label('Shaders:', icon='MATERIAL_DATA')
        col.prop(self, 'shaders_data_storage')

        col = layout.box().column()
        col.label('Images:', icon='IMAGE_DATA')
        col.prop(self, 'images_data_storage')
        col.prop(self, 'images_allow_srgb')

        col = layout.box().column()
        col.label('Buffers:', icon='SORTALPHA')
        col.prop(self, 'buffers_embed_data')
        col.prop(self, 'buffers_combine_data')

        col = layout.box().column()
        col.label('Extensions:', icon='PLUGIN')
        col.prop(self, 'ext_export_physics')

        col = layout.box().column()
        col.label('Output:', icon='SCRIPTWIN')
        col.prop(self, 'asset_profile')
        col.prop(self, 'pretty_print')

    def execute(self, context):
        scene = {
            'actions': list(bpy.data.actions),
            'cameras': list(bpy.data.cameras),
            'lamps': list(bpy.data.lamps),
            'images': list(bpy.data.images),
            'materials': list(bpy.data.materials),
            'meshes': list(bpy.data.meshes),
            'objects': list(bpy.data.objects),
            'scenes': list(bpy.data.scenes),
            'textures': list(bpy.data.textures),
        }

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
