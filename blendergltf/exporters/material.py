from distutils.version import StrictVersion as Version

from .base import BaseExporter
from .common import (
    Reference,
)


class MaterialExporter(BaseExporter):
    gltf_key = 'materials'
    blender_key = 'materials'

    @classmethod
    def export(cls, state, blender_data):
        gltf = {
            'name': blender_data.name,
        }

        if state['version'] < Version('2.0'):
            return gltf

        if hasattr(blender_data, 'pbr_export_settings'):
            gltf['doubleSided'] = not blender_data.game_settings.use_backface_culling
            pbr_settings = blender_data.pbr_export_settings
            pbr = {
                'baseColorFactor': pbr_settings.base_color_factor[:],
                'metallicFactor': pbr_settings.metallic_factor,
                'roughnessFactor': pbr_settings.roughness_factor,
            }

            gltf['alphaMode'] = pbr_settings.alpha_mode
            if gltf['alphaMode'] == 'MASK':
                gltf['alphaCutoff'] = pbr_settings.alpha_cutoff

            input_textures = [texture.name for texture in state['input']['textures']]
            base_color_text = pbr_settings.base_color_texture
            if base_color_text and base_color_text in input_textures:
                pbr['baseColorTexture'] = {
                    'texCoord': pbr_settings.base_color_text_index,
                }
                pbr['baseColorTexture']['index'] = Reference(
                    'textures',
                    pbr_settings.base_color_texture,
                    pbr['baseColorTexture'],
                    'index'
                )
                state['references'].append(pbr['baseColorTexture']['index'])

            metal_rough_text = pbr_settings.metal_roughness_texture
            if metal_rough_text and metal_rough_text in input_textures:
                pbr['metallicRoughnessTexture'] = {
                    'texCoord': pbr_settings.metal_rough_text_index,
                }
                pbr['metallicRoughnessTexture']['index'] = Reference(
                    'textures',
                    pbr_settings.metal_roughness_texture,
                    pbr['metallicRoughnessTexture'],
                    'index'
                )
                state['references'].append(pbr['metallicRoughnessTexture']['index'])

            gltf['pbrMetallicRoughness'] = pbr

            gltf['emissiveFactor'] = pbr_settings.emissive_factor[:]

            emissive_text = pbr_settings.emissive_texture
            if emissive_text and emissive_text in input_textures:
                gltf['emissiveTexture'] = {
                    'texCoord': pbr_settings.emissive_text_index,
                }
                gltf['emissiveTexture']['index'] = Reference(
                    'textures',
                    pbr_settings.emissive_texture,
                    gltf['emissiveTexture'],
                    'index'
                )
                state['references'].append(gltf['emissiveTexture']['index'])

            normal_text = pbr_settings.normal_texture
            if normal_text and normal_text in input_textures:
                gltf['normalTexture'] = {
                    'texCoord': pbr_settings.normal_text_index,
                }
                gltf['normalTexture']['index'] = Reference(
                    'textures',
                    pbr_settings.normal_texture,
                    gltf['normalTexture'],
                    'index'
                )
                state['references'].append(gltf['normalTexture']['index'])

            occlusion_text = pbr_settings.occlusion_texture
            if occlusion_text and occlusion_text in input_textures:
                gltf['occlusionTexture'] = {
                    'texCoord': pbr_settings.occlusion_text_index,
                }
                gltf['occlusionTexture']['index'] = Reference(
                    'textures',
                    pbr_settings.occlusion_texture,
                    gltf['occlusionTexture'],
                    'index'
                )
                state['references'].append(gltf['occlusionTexture']['index'])

        return gltf
