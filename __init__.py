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
            orientation_helper_factory,
            axis_conversion
            )

    from . import blendergltf

    GLTFOrientationHelper = orientation_helper_factory(
        "GLTFOrientationHelper", axis_forward='-Z', axis_up='Y'
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
        materials_export_shader = BoolProperty(name='Export Shaders', default=False)
        images_embed_data = BoolProperty(name='Embed Image Data', default=False)

        apply_modifiers = BoolProperty(
            name="Apply modifiers",
            description="Apply modifiers",
            default=True,
            )

        export_textures = BoolProperty(
            name="Export images / textures",
            description="Export textures and texture coordinates",
            default=True)

        pretty_print = BoolProperty(
            name="Pretty-print / indent JSON",
            description="Export JSON with indentation and a newline",
            default=True
            )

        def execute(self, context):
            scene = {
                'actions': bpy.data.actions,
                'camera': bpy.data.cameras,
                'lamps': bpy.data.lamps,
                'images': bpy.data.images,
                'materials': bpy.data.materials,
                'scenes': bpy.data.scenes,
                'textures': bpy.data.textures,
            }

            scene['objects'] = []
            scene['meshes'] = []

            # Mapping from object to mesh
            scene['obj_meshes'] = {}

            # Copy properties to settings
            settings = self.as_keywords(ignore=("filter_glob",))

            axis_matrix = axis_conversion(to_forward=self.axis_forward,
                                          to_up=self.axis_up).to_4x4()

            for obj in bpy.data.objects:
                if obj.type != 'MESH': continue

                # Apply the modifiers
                new_mesh = obj.to_mesh(
                    context.scene, settings['apply_modifiers'], 'PREVIEW'
                )

                inv_world_mat = obj.matrix_world.copy()
                inv_world_mat.invert()

                # Transform the mesh (think: object coordinates) from mesh
                # space to world space, then converted-axis space and then back
                # to model space.
                new_mesh.transform(inv_world_mat * axis_matrix * obj.matrix_world)

                scene['meshes'].append(new_mesh)

                # Map objects to the proper meshes (with modifiers applied).
                scene['obj_meshes'][obj] = new_mesh
                scene['objects'].append(obj)

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

            # Clean up meshes
            for mesh in scene['meshes']:
                bpy.data.meshes.remove(mesh)

            return {'FINISHED'}


    def menu_func_export(self, context):
        self.layout.operator(ExportGLTF.bl_idname, text="glTF (.gltf)")


    def register():
        bpy.utils.register_module(__name__)

        bpy.types.INFO_MT_file_export.append(menu_func_export)


    def unregister():
        bpy.utils.unregister_module(__name__)

        bpy.types.INFO_MT_file_export.remove(menu_func_export)
