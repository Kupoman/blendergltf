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

    import bpy
    from bpy.props import *
    from bpy_extras.io_utils import (
            ExportHelper,
            )

    from . import blendergltf


    class ExportGLTF(bpy.types.Operator, ExportHelper):
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
        materials_export_shader = BoolProperty(name='Export Shaders', default=False)
        meshes_apply_modifiers = BoolProperty(name='Apply Modifiers', default=True)
        images_embed_data = BoolProperty(name='Embed Image Data', default=False)

        pretty_print = BoolProperty(
            name="Pretty-print / indent JSON",
            description="Export JSON with indentation and a newline",
            default=True
            )

        def execute(self, context):
            scene = {
                'actions': list(bpy.data.actions),
                'camera': list(bpy.data.cameras),
                'lamps': list(bpy.data.lamps),
                'images': list(bpy.data.images),
                'materials': list(bpy.data.materials),
                'meshes': list(bpy.data.meshes),
                'objects': list(bpy.data.objects),
                'scenes': list(bpy.data.scenes),
                'textures': list(bpy.data.textures),
            }

            # Copy properties to settings
            settings = self.as_keywords(ignore=("filter_glob",))

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
