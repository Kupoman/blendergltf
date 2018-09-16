import importlib
from distutils.version import StrictVersion as Version
import json
import os
import time

import bpy
try:
    import bpy_extras
    IS_IN_BLENDER = True
except ModuleNotFoundError:
    IS_IN_BLENDER = False

from . import blendergltf
from . import exporters
from . import filters
from . import pbr_utils
from . import extension_exporters as extensions

bl_info = {
    "name": "glTF format",
    "author": "Daniel Stokes and GitHub contributors",
    # When updating version, also update the generator string in blendergltf.py
    "version": (1, 2, 0),
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


__all__ = [
    blendergltf,
    exporters,
    extensions,
    filters,
    pbr_utils,
]


if "__IMPORTED__" in locals():
    importlib.reload(locals()['blendergltf'])
    importlib.reload(locals()['filters'])
    importlib.reload(locals()['extensions'])
    importlib.reload(locals()['pbr_utils'])

if IS_IN_BLENDER:
    GLTFOrientationHelper = bpy_extras.io_utils.orientation_helper_factory(
        "GLTFOrientationHelper", axis_forward='Z', axis_up='Y'
    )

    VERSION_ITEMS = (
        ('1.0', '1.0', ''),
        ('2.0', '2.0', ''),
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
    ANIM_EXPORT_ITEMS = (
        ('ACTIVE', 'Active Only', 'Export the active action per object'),
        ('ELIGIBLE', 'All Eligible', 'Export all actions that can be used by an object'),
    )

    class ExtPropertyGroup(bpy.types.PropertyGroup):
        name = bpy.props.StringProperty(name='Extension Name')
        enable = bpy.props.BoolProperty(
            name='Enable',
            description='Enable this extension',
            default=False
        )

    class ExportGLTF(bpy.types.Operator, bpy_extras.io_utils.ExportHelper, GLTFOrientationHelper):
        """Save a Khronos glTF File"""
        bl_idname = 'export_scene.gltf'
        bl_label = 'Export glTF'
        bl_options = {'PRESET'}

        filename_ext = ''
        filter_glob = bpy.props.StringProperty(
            default='*.gltf;*.glb',
            options={'HIDDEN'},
        )

        # Override filepath to simplify linting
        filepath = bpy.props.StringProperty(
            name='File Path',
            description='Filepath used for exporting the file',
            maxlen=1024,
            subtype='FILE_PATH'
        )

        check_extension = True

        ext_exporters = sorted(
            [exporter() for exporter in extensions.__all__],
            key=lambda ext: ext.ext_meta['name']
        )
        extension_props = bpy.props.CollectionProperty(
            name='Extensions',
            type=ExtPropertyGroup,
            description='Select extensions to enable'
        )
        ext_prop_to_exporter_map = {}
        for ext_exporter in ext_exporters:
            meta = ext_exporter.ext_meta
            if 'settings' in meta:
                name = 'settings_' + meta['name']
                prop_group = type(name, (bpy.types.PropertyGroup,), meta['settings'])
                bpy.utils.register_class(prop_group)
                value = bpy.props.PointerProperty(type=prop_group)
                locals()[name] = value

        # Dummy property to get icon with tooltip
        draft_prop = bpy.props.BoolProperty(
            name='',
            description='This extension is currently in a draft phase',
        )

        # blendergltf settings
        nodes_export_hidden = bpy.props.BoolProperty(
            name='Export Hidden Objects',
            description='Export nodes that are not set to visible',
            default=False
        )
        nodes_selected_only = bpy.props.BoolProperty(
            name='Selection Only',
            description='Only export nodes that are currently selected',
            default=False
        )
        materials_disable = bpy.props.BoolProperty(
            name='Disable Material Export',
            description='Export minimum default materials. Useful when using material extensions',
            default=False
        )
        meshes_apply_modifiers = bpy.props.BoolProperty(
            name='Apply Modifiers',
            description='Apply all modifiers to the output mesh data',
            default=True
        )
        meshes_vertex_color_alpha = bpy.props.BoolProperty(
            name='Export Vertex Color Alpha',
            description=(
                'Export vertex colors with 4 channels'
                ' (the value of the fourth channel is always 1.0)'
            ),
            default=False
        )
        meshes_interleave_vertex_data = bpy.props.BoolProperty(
            name='Interleave Vertex Data',
            description=(
                'Store data for each vertex contiguously'
                ' instead of each vertex property (e.g. position) contiguously'
            ),
            default=False
        )
        animations_object_export = bpy.props.EnumProperty(
            items=ANIM_EXPORT_ITEMS,
            name='Objects',
            default='ACTIVE'
        )
        animations_armature_export = bpy.props.EnumProperty(
            items=ANIM_EXPORT_ITEMS,
            name='Armatures',
            default='ELIGIBLE'
        )
        animations_shape_key_export = bpy.props.EnumProperty(
            items=ANIM_EXPORT_ITEMS,
            name='Shape Keys',
            default='ELIGIBLE'
        )
        images_data_storage = bpy.props.EnumProperty(
            items=IMAGE_STORAGE_ITEMS,
            name='Storage',
            default='COPY'
        )
        images_allow_srgb = bpy.props.BoolProperty(
            name='sRGB Texture Support',
            description='Use sRGB texture formats for sRGB textures',
            default=False
        )
        buffers_embed_data = bpy.props.BoolProperty(
            name='Embed Buffer Data',
            description='Embed buffer data into the glTF file',
            default=False
        )
        buffers_combine_data = bpy.props.BoolProperty(
            name='Combine Buffer Data',
            description='Combine all buffers into a single buffer',
            default=True
        )
        asset_copyright = bpy.props.StringProperty(
            name='Copyright',
            description='Copyright string to include in output file'
        )
        asset_version = bpy.props.EnumProperty(
            items=VERSION_ITEMS,
            name='Version',
            default='2.0'
        )
        asset_profile = bpy.props.EnumProperty(
            items=PROFILE_ITEMS,
            name='Profile',
            default='WEB'
        )
        gltf_export_binary = bpy.props.BoolProperty(
            name='Export as binary',
            description='Export to the binary glTF file format (.glb)',
            default=False
        )
        pretty_print = bpy.props.BoolProperty(
            name='Pretty-print / indent JSON',
            description='Export JSON with indentation and a newline',
            default=True
        )
        blocks_prune_unused = bpy.props.BoolProperty(
            name='Prune Unused Resources',
            description='Do not export any data-blocks that have no users or references',
            default=True
        )
        enable_actions = bpy.props.BoolProperty(
            name='Actions',
            description='Enable the export of actions',
            default=True
        )
        enable_cameras = bpy.props.BoolProperty(
            name='Cameras',
            description='Enable the export of cameras',
            default=True
        )
        enable_lamps = bpy.props.BoolProperty(
            name='Lamps',
            description='Enable the export of lamps',
            default=True
        )
        enable_materials = bpy.props.BoolProperty(
            name='Materials',
            description='Enable the export of materials',
            default=True
        )
        enable_meshes = bpy.props.BoolProperty(
            name='Meshes',
            description='Enable the export of meshes',
            default=True
        )
        enable_textures = bpy.props.BoolProperty(
            name='Textures',
            description='Enable the export of textures',
            default=True
        )

        def update_extensions(self):
            self.ext_prop_to_exporter_map = {
                ext.ext_meta['name']: ext for ext in self.ext_exporters
            }

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

                if exporter.ext_meta['name'] == 'KHR_technique_webgl':
                    prop.enable = Version(self.asset_version) < Version('2.0')

        def invoke(self, context, event):
            self.update_extensions()
            return super().invoke(context, event)

        def check(self, context):
            redraw = False

            if self.gltf_export_binary and self.filepath.endswith('.gltf'):
                self.filepath = self.filepath[:-4] + 'glb'
                redraw = True
            elif not self.gltf_export_binary and self.filepath.endswith('.glb'):
                self.filepath = self.filepath[:-3] + 'gltf'
                redraw = True

            if (
                    self.gltf_export_binary
                    and self.buffers_embed_data
                    and not self.buffers_combine_data
            ):
                self.buffers_combine_data = True
                redraw = True

            self.filename_ext = '.glb' if self.gltf_export_binary else '.gltf'
            redraw = redraw or super().check(context)

            return redraw

        def draw(self, context):
            self.update_extensions()
            layout = self.layout

            col = layout.box().column(align=True)
            col.label('Enable:')
            row = col.row(align=True)
            row.prop(self, 'enable_actions', toggle=True)
            row.prop(self, 'enable_cameras', toggle=True)
            row.prop(self, 'enable_lamps', toggle=True)
            row = col.row(align=True)
            row.prop(self, 'enable_materials', toggle=True)
            row.prop(self, 'enable_meshes', toggle=True)
            row.prop(self, 'enable_textures', toggle=True)

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
            col.prop(self, 'meshes_vertex_color_alpha')

            col = layout.box().column()
            col.label('Materials:', icon='MATERIAL_DATA')
            col.prop(self, 'materials_disable')
            if Version(self.asset_version) < Version('2.0'):
                material_settings = getattr(self, 'settings_KHR_technique_webgl')
                col.prop(material_settings, 'embed_shaders')

            col = layout.box().column()
            col.label('Animations:', icon='ACTION')
            col.prop(self, 'animations_armature_export')
            col.prop(self, 'animations_object_export')
            col.prop(self, 'animations_shape_key_export')

            col = layout.box().column()
            col.label('Images:', icon='IMAGE_DATA')
            col.prop(self, 'images_data_storage')
            if Version(self.asset_version) < Version('2.0'):
                col.prop(self, 'images_allow_srgb')

            col = layout.box().column()
            col.label('Buffers:', icon='SORTALPHA')
            col.prop(self, 'buffers_embed_data')

            col = col.column()
            col.enabled = not self.gltf_export_binary or not self.buffers_embed_data
            prop = col.prop(self, 'buffers_combine_data')

            col = layout.box().column()
            col.label('Extensions:', icon='PLUGIN')
            extension_filter = set()

            # Disable KHR_technique_webgl for all glTF versions
            extension_filter.add('KHR_technique_webgl')
            for i in range(len(self.extension_props)):
                prop = self.extension_props[i]
                extension_exporter = self.ext_prop_to_exporter_map[prop.name]

                if extension_exporter.ext_meta['name'] in extension_filter:
                    continue

                row = col.row()
                row.prop(prop, 'enable', text=prop.name)
                if extension_exporter.ext_meta.get('isDraft', False):
                    row.prop(self, 'draft_prop', icon='ERROR', emboss=False)
                info_op = row.operator('wm.url_open', icon='INFO', emboss=False)
                info_op.url = extension_exporter.ext_meta.get('url', '')

                if prop.enable:
                    settings = getattr(self, 'settings_' + prop.name, None)
                    if settings:
                        box = col.box()
                        if hasattr(extension_exporter, 'draw_settings'):
                            extension_exporter.draw_settings(box, settings, context)
                        else:
                            setting_props = [
                                name for name in dir(settings)
                                if not name.startswith('_')
                                and name not in ('bl_rna', 'name', 'rna_type')
                            ]
                            for setting_prop in setting_props:
                                box.prop(settings, setting_prop)
                        if i < len(self.extension_props) - 1:
                            col.separator()
                            col.separator()

            col = layout.box().column()
            col.label('Output:', icon='SCRIPTWIN')
            col.prop(self, 'asset_copyright')
            col.prop(self, 'asset_version')
            col.prop(self, 'gltf_export_binary')
            if Version(self.asset_version) < Version('2.0'):
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

            # Set the output name
            settings['gltf_name'] = os.path.splitext(os.path.basename(self.filepath))[0]

            # Calculate a global transform matrix to apply to a root node
            settings['nodes_global_matrix'] = bpy_extras.io_utils.axis_conversion(
                to_forward=self.axis_forward,
                to_up=self.axis_up
            ).to_4x4()

            # filter data according to settings
            data = {
                'actions': list(bpy.data.actions) if self.enable_actions else [],
                'cameras': list(bpy.data.cameras) if self.enable_cameras else [],
                'lamps': list(bpy.data.lamps) if self.enable_lamps else [],
                'images': list(bpy.data.images) if self.enable_textures else [],
                'materials': list(bpy.data.materials) if self.enable_materials else [],
                'meshes': list(bpy.data.meshes) if self.enable_meshes else [],
                'objects': list(bpy.data.objects),
                'scenes': list(bpy.data.scenes),
                'textures': list(bpy.data.textures) if self.enable_textures else [],
            }

            # Remove objects that point to disabled data
            if not self.enable_cameras:
                data['objects'] = [
                    obj for obj in data['objects']
                    if not isinstance(obj.data, bpy.types.Camera)
                ]
            if not self.enable_lamps:
                data['objects'] = [
                    obj for obj in data['objects']
                    if not isinstance(obj.data, bpy.types.Lamp)
                ]
            if not self.enable_meshes:
                data['objects'] = [
                    obj for obj in data['objects']
                    if not isinstance(obj.data, bpy.types.Mesh)
                ]

            if not settings['nodes_export_hidden']:
                data = filters.visible_only(data)

            if settings['nodes_selected_only']:
                data = filters.selected_only(data)

            if settings['blocks_prune_unused']:
                data = filters.used_only(data)

            for ext_exporter in self.ext_exporters:
                ext_exporter.settings = getattr(
                    self,
                    'settings_' + ext_exporter.ext_meta['name'],
                    None
                )

            def is_builtin_mat_ext(prop_name):
                if Version(self.asset_version) < Version('2.0'):
                    return prop_name == 'KHR_technique_webgl'
                return False

            settings['extension_exporters'] = [
                self.ext_prop_to_exporter_map[prop.name]
                for prop in self.extension_props
                if prop.enable and not (self.materials_disable and is_builtin_mat_ext(prop.name))
            ]

            start_time = time.perf_counter()
            gltf = blendergltf.export_gltf(data, settings)
            end_time = time.perf_counter()
            print('Export took {:.4} seconds'.format(end_time - start_time))

            if self.gltf_export_binary:
                with open(self.filepath, 'wb') as fout:
                    fout.write(gltf)
            else:
                with open(self.filepath, 'w') as fout:
                    # Figure out indentation
                    indent = 4 if self.pretty_print else None

                    # Dump the JSON
                    json.dump(gltf, fout, indent=indent, sort_keys=True, check_circular=False)

                    if self.pretty_print:
                        # Write a newline to the end of the file
                        fout.write('\n')
            return {'FINISHED'}

    def menu_func_export(self, _):
        self.layout.operator(ExportGLTF.bl_idname, text="glTF (.gltf)")

    def register():
        bpy.utils.register_class(ExtPropertyGroup)
        bpy.utils.register_class(ExportGLTF)
        bpy.utils.register_class(pbr_utils.PbrExportPanel)
        bpy.utils.register_class(pbr_utils.PbrSettings)

        bpy.types.Material.pbr_export_settings = bpy.props.PointerProperty(
            type=pbr_utils.PbrSettings
        )

        bpy.types.INFO_MT_file_export.append(menu_func_export)

    def unregister():
        bpy.types.INFO_MT_file_export.remove(menu_func_export)

        del bpy.types.Material.pbr_export_settings

        bpy.utils.unregister_class(pbr_utils.PbrSettings)
        bpy.utils.unregister_class(pbr_utils.PbrExportPanel)
        bpy.utils.unregister_class(ExportGLTF)
        bpy.utils.unregister_class(ExtPropertyGroup)


__IMPORTED__ = True
