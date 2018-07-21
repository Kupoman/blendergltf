import math

import bpy
import mathutils

ALPHA_MODE_ITEMS = [
    ('OPAQUE', 'Opaque', 'The alpha value is ignored and the rendered output is fully opaque'),
    ('MASK', 'Mask', (
        'The rendered output is either fully opaque or fully transparent depending on the '
        'alpha value and the specified alpha cutoff value'
    )),
    ('BLEND', 'Blend', 'The alpha value is used to composite the source and destination areas'),
]


def get_base_color_factor(self):
    material = self.id_data
    diffuse = mathutils.Vector(material.diffuse_color)
    diffuse *= material.diffuse_intensity
    return [*diffuse, material.alpha]


def set_base_color_factor(self, value):
    material = self.id_data
    material.diffuse_color = value[:3]
    material.diffuse_intensity = 1.0

    alpha = value[3]
    material.alpha = alpha
    if alpha < 1.0:
        material.use_transparency = True
        material.transparency_method = 'Z_TRANSPARENCY'
    else:
        material.use_transparency = False


def get_emissive_factor(self):
    material = self.id_data
    return [min(material.emit, 2.0) * 0.5] * 3


def set_emissive_factor(self, value):
    material = self.id_data
    material.emit = mathutils.Color(value).v * 2.0


def get_alpha_mode(self):
    material = self.id_data

    alpha_mode = 'OPAQUE'

    if material.use_transparency:
        gs_alpha = material.game_settings.alpha_blend
        if gs_alpha == 'CLIP':
            alpha_mode = 'MASK'
        else:
            alpha_mode = 'BLEND'

    for i, mode in enumerate(ALPHA_MODE_ITEMS):
        if mode[0] == alpha_mode:
            alpha_mode = i
            break
    else:
        alpha_mode = 0

    return alpha_mode


def set_alpha_mode(self, value):
    material = self.id_data

    value = ALPHA_MODE_ITEMS[value][0]

    if value == 'OPAQUE':
        material.use_transparency = False
        material.game_settings.alpha_blend = 'OPAQUE'
    elif value == 'MASK':
        material.use_transparency = True
        material.game_settings.alpha_blend = 'CLIP'
    elif value == 'BLEND':
        material.use_transparency = True
        material.game_settings.alpha_blend = 'ALPHA'


def get_roughness_factor(self):
    material = self.id_data
    hardness = material.specular_hardness
    if 1.0 < self.hardness_float < 511.0 and not hardness < self.hardness_float < hardness + 1:
        self.hardness_float = material.specular_hardness
    roughness = pow(2.0 / (self.hardness_float + 2.0), 0.25)
    return max(min(roughness, 1.0), 0.0)


def set_roughness_factor(self, value):
    material = self.id_data
    if value <= 0:
        value = 0.00001

    roughness_texture = self.metal_roughness_texture
    if roughness_texture:
        slot = material.texture_slots[roughness_texture]
        slot.hardness_factor = value

    material.specular_intensity = 0.04 / (math.pi * pow(value, 4.0))
    material.specular_color = (1.0, 1.0, 1.0)

    self.hardness_float = (2.0 / pow(value, 4.0)) - 2.0
    material.specular_hardness = min(math.floor(self.hardness_float), 511)


def get_texture(self, search_func, index_prop):
    material = self.id_data
    slots = [
        t for t in material.texture_slots
        if t and t.texture and t.texture_coords == 'UV'
    ]

    slot = None
    for slot in slots[::-1]:
        if search_func(slot):
            break
    else:
        return ''

    if (
            bpy.context.space_data
            and bpy.context.space_data.type == 'PROPERTIES'
            and bpy.context.object
    ):
        uv_layers = bpy.context.object.data.uv_layers
        setattr(self, index_prop, uv_layers.find(slot.uv_layer) if slot.uv_layer else 0)

    return slot.texture.name


def _clear_slot_settings(slot):
    slot.use_map_diffuse = False
    slot.use_map_color_diffuse = False
    slot.use_map_alpha = False
    slot.use_map_translucency = False

    slot.use_map_ambient = False
    slot.use_map_emit = False
    slot.use_map_mirror = False
    slot.use_map_raymir = False

    slot.use_map_specular = False
    slot.use_map_color_spec = False
    slot.use_map_hardness = False

    slot.use_map_normal = False
    slot.use_map_warp = False
    slot.use_map_displacement = False

    slot.blend_type = 'MIX'


def set_texture(self, value, current_value, update_func):
    material = self.id_data
    current_index = material.texture_slots.find(current_value)
    slot_index = material.texture_slots.find(value)

    # Clear slot
    if not value:
        if current_index != -1:
            material.texture_slots.clear(current_index)
        return

    # Don't do anything if the correct texture is already set
    if value == current_value:
        return

    bl_texture = bpy.data.textures[value]
    # Texture is not already in a slot on this material
    if current_index == -1 and slot_index == -1:
        slot = material.texture_slots.add()
        slot.texture = bl_texture
        _clear_slot_settings(slot)
        update_func(slot)
        return

    # Adjust existing slot to meet texture criteria
    slot = material.texture_slots[slot_index]
    _clear_slot_settings(slot)
    update_func(slot)
    if slot_index < current_index:
        material.active_texture_index = slot_index
        for _ in range(current_index - slot_index):
            bpy.ops.texture.slot_move(type='DOWN')
            material.active_texture_index -= 1


def get_base_color_texture(self):
    return get_texture(self, lambda t: t.use_map_color_diffuse, 'base_color_text_index')


def set_base_color_texture(self, value):
    def update(slot):
        slot.use_map_color_diffuse = True
        slot.blend_type = 'MULTIPLY'
    set_texture(self, value, get_base_color_texture(self), update)


def get_metal_roughness_texture(self):
    return get_texture(self, lambda t: t.use_map_hardness, 'metal_rough_text_index')


def set_metal_roughness_texture(self, value):
    def update(slot):
        slot.use_map_hardness = True
        slot.hardness_factor = self.roughness_factor
    set_texture(self, value, get_metal_roughness_texture(self), update)


def get_normal_texture(self):
    return get_texture(self, lambda t: t.use_map_normal, 'normal_text_index')


def set_normal_texture(self, value):
    def update(slot):
        slot.use_map_normal = True
    set_texture(self, value, get_normal_texture(self), update)


def get_emissive_texture(self):
    return get_texture(self, lambda t: t.use_map_emit, 'emissive_text_index')


def set_emissive_texture(self, value):
    def update(slot):
        slot.use_map_emit = True
    set_texture(self, value, get_emissive_texture(self), update)


class PbrSettings(bpy.types.PropertyGroup):
    hardness_float = bpy.props.FloatProperty()
    base_color_text_index = 0
    metal_rough_text_index = 0
    normal_text_index = 0
    occlusion_text_index = 0
    emissive_text_index = 0

    base_color_factor = bpy.props.FloatVectorProperty(
        name='Base Color Factor',
        size=4,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        get=get_base_color_factor,
        set=set_base_color_factor,
    )
    base_color_texture = bpy.props.StringProperty(
        name='Texture',
        get=get_base_color_texture,
        set=set_base_color_texture,
    )

    alpha_mode = bpy.props.EnumProperty(
        items=ALPHA_MODE_ITEMS,
        name='Alpha Mode',
        default='OPAQUE',
        get=get_alpha_mode,
        set=set_alpha_mode,
    )

    alpha_cutoff = bpy.props.FloatProperty(
        name='Alpha Cutoff',
        min=0.0,
        max=1.0,
        default=0.5,
    )

    metallic_factor = bpy.props.FloatProperty(
        name='Metallic Factor',
        min=0.0,
        max=1.0,
    )
    roughness_factor = bpy.props.FloatProperty(
        name='Roughness Factor',
        min=0.0,
        max=1.0,
        get=get_roughness_factor,
        set=set_roughness_factor,
    )
    metal_roughness_texture = bpy.props.StringProperty(
        name='Texture',
        get=get_metal_roughness_texture,
        set=set_metal_roughness_texture,
    )

    normal_texture = bpy.props.StringProperty(
        name='Normal',
        get=get_normal_texture,
        set=set_normal_texture,
    )
    occlusion_texture = bpy.props.StringProperty(
        name='Occlusion',
    )

    emissive_factor = bpy.props.FloatVectorProperty(
        name='Emissive Factor',
        size=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        get=get_emissive_factor,
        set=set_emissive_factor,
    )
    emissive_texture = bpy.props.StringProperty(
        name='Texture',
        get=get_emissive_texture,
        set=set_emissive_texture,
    )


class PbrExportPanel(bpy.types.Panel):
    bl_idname = 'MATERIAL_PT_pbr_export'
    bl_label = 'PBR Export'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.material is not None and hasattr(context.material, 'pbr_export_settings')

    def draw(self, context):
        settings = context.material.pbr_export_settings
        self.layout.label('Base Color:')
        box = self.layout.box()
        box.prop(settings, 'base_color_factor', text='Factor')
        box.prop_search(settings, 'base_color_texture', bpy.data, 'textures')
        box.prop(settings, 'alpha_mode')
        box.prop(settings, 'alpha_cutoff')

        self.layout.label('Roughness:')
        box = self.layout.box()
        box.prop(settings, 'metallic_factor', text='Metallic')
        box.prop(settings, 'roughness_factor', text='Factor')
        box.prop_search(settings, 'metal_roughness_texture', bpy.data, 'textures')

        self.layout.label('Emissive:')
        box = self.layout.box()
        box.prop(settings, 'emissive_factor', text='Factor')
        box.prop_search(settings, 'emissive_texture', bpy.data, 'textures')

        self.layout.prop_search(settings, 'normal_texture', bpy.data, 'textures')
        self.layout.prop_search(settings, 'occlusion_texture', bpy.data, 'textures')

        self.layout.prop(context.material.game_settings, 'use_backface_culling')
