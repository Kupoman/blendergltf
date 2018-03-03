class KhrMaterialsUnlit:
    ext_meta = {
        'name': 'KHR_materials_unlit',
        'url': (
            'https://github.com/KhronosGroup/glTF/pull/1163'
        ),
        'isDraft': True,
    }

    def export(self, state):
        state['extensions_used'].append('KHR_materials_unlit')

        # Export materials
        material_pairs = [
            (material, state['output']['materials'][state['refmap'][('materials', material.name)]])
            for material in state['input']['materials']
        ]
        for bl_mat, gl_mat in material_pairs:
            if bl_mat.use_shadeless:
                print('Found shadeless material')
            gl_mat['extensions'] = gl_mat.get('extensions', {})
            gl_mat['extensions']['KHR_materials_unlit'] = {}
