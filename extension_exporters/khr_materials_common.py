import importlib

from ..blendergltf import Reference

from . import _lights_common

if '__IMPORTED__' in locals():
    importlib.reload(locals()['_lights_common'])
else:
    __IMPORTED__ = True


class KhrMaterialsCommon:
    ext_meta = {
        'name': 'KHR_materials_common',
        'url': (
            'https://github.com/KhronosGroup/glTF/tree/master/extensions/'
            'Khronos/KHR_materials_common'
        ),
        'isDraft': True,
    }

    def export_material(self, state, material):
        all_textures = [
            slot for slot in material.texture_slots
            if slot and slot.texture.type == 'IMAGE'
        ]
        diffuse_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_diffuse
        ]
        emission_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures
            if (
                (material.use_shadeless and t.use_map_color_diffuse)
                or (not material.use_shadeless and t.use_map_emit)
            )
        ]
        specular_textures = [
            Reference('textures', t.texture.name, None, None)
            for t in all_textures if t.use_map_color_spec
        ]

        diffuse_color = list((material.diffuse_color * material.diffuse_intensity)[:])
        diffuse_color += [material.alpha]
        emission_color = list((material.diffuse_color * material.emit)[:])
        emission_color += [material.alpha]
        specular_color = list((material.specular_color * material.specular_intensity)[:])
        specular_color += [material.specular_alpha]

        technique = 'PHONG'
        if material.use_shadeless:
            technique = 'CONSTANT'
            emission_color = diffuse_color
        elif material.specular_intensity == 0.0:
            technique = 'LAMBERT'
        elif material.specular_shader == 'BLINN':
            technique = 'BLINN'

        gltf = {
            'technique': technique,
            'values': {
                'ambient': ([material.ambient]*3) + [1.0],
                'diffuse': diffuse_textures[-1] if diffuse_textures else diffuse_color,
                'doubleSided': not material.game_settings.use_backface_culling,
                'emission': emission_textures[-1] if emission_textures else emission_color,
                'specular': specular_textures[-1] if specular_textures else specular_color,
                'shininess': material.specular_hardness,
                'transparency': material.alpha,
                'transparent': material.use_transparency,
            }
        }

        for prop in ('diffuse', 'emission', 'specular'):
            if hasattr(gltf['values'][prop], 'blender_type'):
                ref = gltf['values'][prop]
                ref.source = gltf['values']
                ref.prop = prop
                state['references'].append(ref)

        return gltf

    def export(self, state):
        state['extensions_used'].append('KHR_materials_common')

        # Export materials
        material_pairs = [
            (material, state['output']['materials'][state['refmap'][('materials', material.name)]])
            for material in state['input']['materials']
        ]
        for bl_mat, gl_mat in material_pairs:
            gl_mat['extensions'] = gl_mat.get('extensions', {})
            gl_mat['extensions']['KHR_materials_common'] = self.export_material(state, bl_mat)

        _lights_common.export_lights(state, 'KHR_materials_common')
