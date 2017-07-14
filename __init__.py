import importlib
import json
import os

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    PointerProperty,
    StringProperty
)
from bpy_extras.io_utils import (
    ExportHelper,
    orientation_helper_factory,
    axis_conversion,
)

from .blendergltf import export_gltf
from .filters import visible_only, selected_only, used_only
from . import extension_exporters


bl_info = {
    "name": "glTF format",
    "author": "Daniel Stokes and GitHub contributors",
    "version": (1, 0, 0),
    "blender": (2, 76, 0),
    "location": "File > Import-Export",
    "description": "Export glTF",
    "warning": "",
    "wiki_url": "https://github.com/Kupoman/blendergltf/blob/master/README.md"
                "",
    "tracker_url": "https://github.com/Kupoman/blendergltf/issues",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}


if "bpy" in locals():
    importlib.reload(locals()['blendergltf'])
    importlib.reload(locals()['filters'])
    importlib.reload(locals()['extension_exporters'])


GLTFOrientationHelper = orientation_helper_factory(
    "GLTFOrientationHelper", axis_forward='Y', axis_up='Z'
)


PROFILE_ITEMS = (
    ('WEB', 'Web', 'Export shaders for WebGL 1.0 use (shader version 100)'),
    ('DESKTOP', 'Desktop', 'Export shaders for OpenGL 3.0 use (shader version 130)')
)
IMAGE_STORAGE_ITEMS = (
    ('EMBED', 'Embed', 'Embed image data into the glTF file'),
    ('REFERENCE', 'Reference', 'Use the same filepath that Blender uses for images'),
    ('COPY', 'Copy', 'Copy images to output directory and use a relative reference')
)
SHADER_STORAGE_ITEMS = (
    ('EMBED', 'Embed', 'Embed shader data into the glTF file'),
    ('NONE', 'None', 'Use the KHR_material_common extension instead of a shader'),
    ('EXTERNAL', 'External', 'Save shaders to the output directory')
)


class ExtPropertyGroup(bpy.types.PropertyGroup):
    name = StringProperty(name='Extension Name')
    enable = BoolProperty(
        name='Enable',
        description='Enable this extension',
        default=False
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

    ext_exporters = [exporter() for exporter in extension_exporters.__all__]
    extension_props = CollectionProperty(
        name='Extensions',
        type=ExtPropertyGroup,
        description='Select extensions to enable'
    )
    ext_prop_to_exporter_map = {}
    for ext_exporter in ext_exporters:
        meta = ext_exporter.ext_meta
        name = 'settings_' + meta['name']
        prop_group = type(name, (bpy.types.PropertyGroup,), meta.get('settings', {}))
        bpy.utils.register_class(prop_group)
        value = PointerProperty(type=prop_group)
        locals()[name] = value

    # blendergltf settings
    nodes_export_hidden = BoolProperty(
        name='Export Hidden Objects',
        description='Export nodes that are not set to visible',
        default=False
    )
    nodes_selected_only = BoolProperty(
        name='Selection Only',
        description='Only export nodes that are currently selected',
        default=False
    )
    meshes_apply_modifiers = BoolProperty(
        name='Apply Modifiers',
        description='Apply all modifiers to the output mesh data',
        default=True
    )
    meshes_interleave_vertex_data = BoolProperty(
        name='Interleave Vertex Data',
        description=(
            'Store data for each vertex contiguously'
            'instead of each vertex property (e.g. position) contiguously'
        ),
        default=True
    )
    shaders_data_storage = EnumProperty(
        items=SHADER_STORAGE_ITEMS,
        name='Storage',
        default='NONE'
    )
    images_data_storage = EnumProperty(
        items=IMAGE_STORAGE_ITEMS,
        name='Storage',
        default='COPY'
    )
    images_allow_srgb = BoolProperty(
        name='sRGB Texture Support',
        description='Use sRGB texture formats for sRGB textures',
        default=False
    )
    buffers_embed_data = BoolProperty(
        name='Embed Buffer Data',
        description='Embed buffer data into the glTF file',
        default=False
    )
    buffers_combine_data = BoolProperty(
        name='Combine Buffer Data',
        description='Combine all buffers into a single buffer',
        default=True
    )
    ext_export_physics = BoolProperty(
        name='Export Physics Settings',
        description='Enable support for the BLENDER_physics extension',
        default=False
    )
    asset_profile = EnumProperty(
        items=PROFILE_ITEMS,
        name='Profile',
        default='WEB'
    )
    pretty_print = BoolProperty(
        name='Pretty-print / indent JSON',
        description='Export JSON with indentation and a newline',
        default=True
    )
    blocks_prune_unused = BoolProperty(
        name='Prune Unused Resources',
        description='Do not export any data-blocks that have no users or references',
        default=True
    )

    def invoke(self, context, event):
        self.ext_prop_to_exporter_map = {ext.ext_meta['name']: ext for ext in self.ext_exporters}

        for exporter in self.ext_exporters:
            exporter.ext_meta['enable'] = False
        for prop in self.extension_props:
            exporter = self.ext_prop_to_exporter_map[prop.name]
            exporter.ext_meta['enable'] = prop.enable

        self.extension_props.clear()
        for exporter in self.ext_exporters:
            prop = self.extension_props.add()
            prop.name = exporter.ext_meta['name']
            prop.enable = exporter.ext_meta['enable']

        return super().invoke(context, event)

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
        for i in range(len(self.extension_props)):
            prop = self.extension_props[i]

            col.prop(prop, 'enable', text=prop.name)
            extension_exporter = self.ext_prop_to_exporter_map[prop.name]
            if prop.enable:
                settings = getattr(self, 'settings_' + prop.name, None)
                if settings:
                    if hasattr(extension_exporter, 'draw_settings'):
                        extension_exporter.draw_settings(col, settings, context)
                    else:
                        setting_props = [
                            name for name in dir(settings)
                            if not name.startswith('_')
                            and name not in ('bl_rna', 'name', 'rna_type')
                        ]
                        for setting_prop in setting_props:
                            col.prop(settings, setting_prop)
                    if i < len(self.extension_props) - 1:
                        col.separator()
                        col.separator()

        col = layout.box().column()
        col.label('Output:', icon='SCRIPTWIN')
        col.prop(self, 'asset_profile')
        col.prop(self, 'pretty_print')
        col.prop(self, 'blocks_prune_unused')

    def execute(self, _):
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

        # filter data according to settings
        data = {
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

        if not settings['nodes_export_hidden']:
            data = visible_only(data)

        if settings['nodes_selected_only']:
            data = selected_only(data)

        if settings['blocks_prune_unused']:
            data = used_only(data)

        for ext_exporter in self.ext_exporters:
            ext_exporter.settings = getattr(
                self,
                'settings_' + ext_exporter.ext_meta['name'],
                None
            )

        settings['extension_exporters'] = [
            self.ext_prop_to_exporter_map[prop.name]
            for prop in self.extension_props if prop.enable
        ]

        gltf = export_gltf(data, settings)
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


def menu_func_export(self, _):
    self.layout.operator(ExportGLTF.bl_idname, text="glTF (.gltf)")


def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_export.remove(menu_func_export)
