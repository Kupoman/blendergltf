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
        images_embed_data = BoolProperty(name='Embed Image Data', default=False)

        def execute(self, context):
            scene = {
                'actions': bpy.data.actions,
                'camera': bpy.data.cameras,
                'lamps': bpy.data.lamps,
                'images': bpy.data.images,
                'materials': bpy.data.materials,
                'meshes': bpy.data.meshes,
                'objects': bpy.data.objects,
                'scenes': bpy.data.scenes,
                'textures': bpy.data.textures,
            }

            # Copy properties to settings
            settings = self.as_keywords(ignore=("filter_glob",))

            gltf = blendergltf.export_gltf(scene, settings)
            with open(self.filepath, 'w') as fout:
                json.dump(gltf, fout, indent=4, sort_keys=True, check_circular=False)
            return {'FINISHED'}


    def menu_func_export(self, context):
        self.layout.operator(ExportGLTF.bl_idname, text="glTF (.gltf)")


    def register():
        bpy.utils.register_module(__name__)

        bpy.types.INFO_MT_file_export.append(menu_func_export)


    def unregister():
        bpy.utils.unregister_module(__name__)

        bpy.types.INFO_MT_file_export.remove(menu_func_export)
