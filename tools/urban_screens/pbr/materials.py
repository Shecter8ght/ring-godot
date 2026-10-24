"""Нативные UCUPaint-материалы: основание, покрытие и причинный износ отдельно."""
from pathlib import Path
import importlib
import importlib.util

import addon_utils
import bpy
from mathutils import Vector

from plan import ROOT
from profiles import INDOOR

SKILL = Path('C:/Users/Schecter_8ght/.agents/skills/weapon-asset-texturing')
UV, PART, GRAIN = 'MetricUV', 'PartUV', 'GrainUV'
U = H = None
IMAGE_CACHE = {}

PAINT = {
 'black': (.075,.085,.08), 'grey': (.43,.445,.415), 'graphite': (.16,.175,.18),
 'olive': (.26,.29,.19), 'teal': (.105,.265,.26), 'green': (.075,.28,.215),
 'blue': (.12,.25,.40), 'ochre': (.54,.39,.17), 'red': (.47,.105,.065),
 'burgundy': (.37,.09,.10), 'cream': (.74,.715,.62), 'white': (.80,.80,.75),
 'yellow': (.69,.52,.14), 'silver': (.61,.64,.63), 'skyblue': (.39,.54,.60),
}
METAL = {
 'galvanized': ((.58,.61,.59), .43, 'metal_plate'),
 'stainless': ((.61,.64,.63), .26, 'metal_plate'),
 'aluminium': ((.69,.71,.69), .33, 'metal_plate'),
 'aluminium_dark': ((.20,.22,.21), .40, 'metal_plate'),
 'steel_dark': ((.28,.29,.27), .48, 'metal_plate'),
 'rail_steel': ((.49,.51,.50), .24, 'metal_plate'),
 'chrome': ((.72,.74,.73), .15, 'metal_plate'),
 'brass': ((.65,.49,.23), .31, 'metal_plate'),
 'bronze': ((.38,.27,.15), .40, 'metal_plate'),
}
PHOTO = {
 'concrete_cast': ('concrete_wall_007', (1.23,.278), (.55,.55,.505), .88, .22, .24),
 'concrete_fracture': ('rough_concrete', .8, (.52,.51,.46), .95, .65, .20),
 'stone_dark': ('granite_tile', (.39,.39), (.22,.235,.23), .50, .24, .23),
 'stone_polished': ('granite_tile', (.39,.39), (.085,.095,.092), .24, .10, .54),
 'granite_light': ('granite_tile', (.39,.39), (.66,.65,.60), .63, .32, .57),
 'marble_warm': ('marble_01', (.43,.255), (.73,.68,.57), .35, .13, .20),
 'wood_aged': ('wood_planks_grey', (.314,1.60), (.48,.435,.345), .85, .62, .24),
 'timber_warm': ('wood_planks_grey', (.314,1.60), (.50,.33,.17), .63, .45, .57),
 'plywood': ('plywood', 2.4, (.60,.48,.31), .82, .35, .30),
 'laminate_dark': ('natural_walnut_veneer', .70, (.20,.145,.085), .43, .18, .36),
 'laminate_white': ('natural_walnut_veneer', .70, (.72,.72,.66), .47, .08, .87),
 'soil': ('mud_forest', 1.2, (.15,.125,.075), .96, .30, .20),
 'roof_bitumen': ('tarred_gravel', 2.0, (.13,.14,.125), .91, .22, .42),
 'mineral_yellow': ('rough_concrete', 1.4, (.66,.50,.13), .78, .28, .80),
}
FABRIC = {
 'canvas_olive': ((.34,.36,.22), .91, .254, .67),
 'canvas_cyan': ((.20,.44,.44), .88, .254, .58),
 'woven_olive': ((.29,.32,.20), .88, .254, .57),
 'woven_teal': ((.115,.32,.33), .88, .254, .57),
 'cloth_dark': ((.13,.145,.14), .90, .254, .56),
 'tarp_olive': ((.36,.375,.255), .64, .254, .25),
 'tarp_green': ((.16,.28,.22), .67, .254, .25),
 'awning_burgundy': ((.43,.10,.12), .77, .254, .35),
 'awning_cream': ((.78,.74,.62), .82, .254, .35),
}
POLY = {
 'polymer_black': ((.075,.08,.072), .55), 'polymer_grey': ((.45,.46,.43), .45),
 'polymer_graphite': ((.145,.155,.16), .49), 'polymer_orange': ((.77,.255,.055), .48),
 'polymer_white': ((.79,.79,.73), .44), 'polymer_yellow': ((.70,.53,.13), .53),
 'rubber': ((.075,.073,.06), .78), 'tyre_rubber': ((.075,.073,.064), .82),
 'interior_dark': ((.055,.06,.055), .74),
}


def linear(rgb):
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb)


def native():
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    spec = importlib.util.spec_from_file_location('urban_ucup_helpers', SKILL / 'scripts/ucupaint_helpers.py')
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    U = H.load_ucupaint()
    print('URBAN_NATIVE', bpy.app.version_string, U.common.get_current_version_str(), flush=True)


def clear_cache():
    IMAGE_CACHE.clear()


def image(path, data=False):
    key = (path, data)
    if key not in IMAGE_CACHE:
        im = bpy.data.images.load(str(ROOT / 'textures' / path), check_existing=True)
        im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        IMAGE_CACHE[key] = im
    return IMAGE_CACHE[key]


def activate(ob, slot=0):
    for other in bpy.context.selected_objects:
        other.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.active_material_index = slot


def stack(mat, holder):
    index = list(holder.data.materials).index(mat)
    activate(holder, index)
    p = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=mat.name, color=True, metallic=True,
        roughness=True, normal=True, ao=False, switch_to_material_view=False, target_bsdf_name=p.name)
    group = next(n for n in mat.node_tree.nodes if n.type == 'GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    ch = next(c for c in tree.yp.channels if c.type == 'NORMAL')
    ch.main_uv = UV
    ch.enable_smooth_bump = False
    return tree, p


def scale(entity, values):
    if isinstance(values, (int, float)):
        values = (values, values, values)
    elif len(values) == 2:
        values = tuple(values) + (1,)
    entity.enable_uniform_scale = False
    H.sync_property(U, entity, 'scale', Vector(values))


def layer(tree, name, color=None, metal=None, rough=None, height=None, kind='COLOR', im=None,
          amount=1, tile=1, uv=UV, bump=.0001, normal=False, blend='MIX'):
    tree.yp.halt_update = True
    l = U.Layer.add_new_layer(tree, name, kind, -1, blend, 'OVERLAY',
        'NORMAL_MAP' if normal else 'BUMP_MAP', 'UV', uv, image=im,
        use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    for root, ch in zip(tree.yp.channels, l.channels):
        value = {'Color':color, 'Metallic':metal, 'Roughness':rough, 'Normal':height}[root.name]
        ch.enable = value is not None
        if value is None:
            continue
        if not isinstance(value, str):
            ch.override = True
            ch.override_type = 'DEFAULT'
            H.sync_property(U, ch, 'override_color' if root.type == 'RGB' else 'override_value', value)
        if root.type == 'NORMAL':
            H.sync_property(U, ch, 'bump_distance', bump)
            H.sync_property(U, ch, 'bump_midlevel', .5)
            if normal:
                H.sync_property(U, ch, 'normal_strength', 1.0)
    H.sync_property(U, l, 'intensity_value', amount)
    if kind == 'IMAGE':
        inv = tuple(1/x for x in tile) if isinstance(tile,(tuple,list)) else 1/tile
        scale(l, inv)
        U.common.get_layer_source(l).extension = 'REPEAT'
    return l


def imask(l, name, tile=.3, amount=1, uv=UV):
    m = U.Mask.add_new_mask(l, name, 'IMAGE', 'UV', uv, image=image('owner_'+name+'.png', True))
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.extension = 'REPEAT'
    scale(m, 1/tile)
    H.sync_property(U, m, 'intensity_value', amount)
    return m


def custom_mask(l, path, uv=UV):
    m = U.Mask.add_new_mask(l, 'Local surface mask', 'IMAGE', 'UV', uv, image=image(path, True))
    U.common.get_mask_tree(m).nodes[m.source].extension = 'EXTEND'
    return m


def attr(l, name):
    return U.Mask.add_new_mask(l, name, 'VCOL', 'Object', UV, vcol_name=name)


def noise(l, freq, lo=.28, hi=.74, stretch=None):
    m = U.Mask.add_new_mask(l, 'Irregular local breakup', 'NOISE', 'Object', UV)
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.inputs['Scale'].default_value = freq
    src.inputs['Detail'].default_value = 2.6
    src.inputs['Roughness'].default_value = .64
    if stretch:
        scale(m, stretch)
    H.local_noise_ramp(U, m, lo, hi)
    return m


def edges(l, radius=.003):
    mask = U.Mask.add_new_mask(l, 'Physical exposed edges', 'EDGE_DETECT', 'Object', UV,
        edge_detect_radius=radius, hemi_use_prev_normal=False)
    importlib.import_module(U.__name__+'.MaskModifier').add_new_mask_modifier(mask,'RAMP')
    ramp=U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp]
    ramp.color_ramp.elements[0].position=.003
    ramp.color_ramp.elements[1].position=.09
    ramp.color_ramp.elements[0].color=(0,0,0,1)
    ramp.color_ramp.elements[1].color=(1,1,1,1)
    return mask


def photo_normal(tree, scan, tile, amount, uv=UV, surface=False):
    path = scan + ('/surface_normal.png' if surface else '/normal.jpg')
    return layer(tree, '12 • CC0 photo micro-normal', height='source', kind='IMAGE', im=image(path, True),
        tile=tile, uv=uv, amount=amount, normal=True)


def micro(tree, freq=800, distance=.000025, stretch=None):
    l = layer(tree, '14 • Manufacturing microstructure', height='source', kind='NOISE', bump=distance)
    src = U.common.get_layer_source(l)
    src.inputs['Scale'].default_value = freq
    src.inputs['Detail'].default_value = 2.4
    src.inputs['Roughness'].default_value = .65
    if stretch:
        scale(l, stretch)
    return l


def dust_and_contact(tree, a, strength=.24, ground=True, touch=False, smooth=False):
    indoor = a['key'] in INDOOR
    l = layer(tree, '70 • Settled dry dust on upper ledges', linear((.48,.46,.40)), 0, .91,
        amount=strength * (.65 if indoor else 1))
    attr(l, 'FaceUp')
    imask(l, 'dust', .45, .85)
    if ground:
        l = layer(tree, '60 • Dirt at actual ground contacts', linear((.19,.18,.135)), 0, .93,
            amount=.40 * (.55 if indoor else 1))
        attr(l, 'GroundContact')
        imask(l, 'grime', .35, .7)
    if touch:
        l = layer(tree, '80 • Local hand contact and oily fingerprints', None, None, .21 if smooth else .34, amount=.52)
        attr(l, 'HandContact')
        imask(l, 'finger', .085)


def paint(tree, p, key, a):
    col = PAINT[key.removeprefix('paint_')]
    layer(tree, '01 • Painted steel, continuous dielectric coating', linear(col), 0, .48)
    layer(tree, '08 • Restrained photographed coating variation', 'source', kind='IMAGE',
        im=image('blue_metal_plate/albedo.jpg'), amount=.055, tile=1.5)
    micro(tree, 650, .000020)
    l = layer(tree, '25 • Slight chalking from outdoor exposure', linear(tuple(min(1,c*1.25+.025) for c in col)),
        0, .69, amount=.20 if a['key'] not in INDOOR else .07)
    imask(l, 'film', .65)
    # Contact-derived chips, not a uniform noise pattern across every plane.
    l = layer(tree, '40 • Small chips exposing steel at edges', linear((.37,.39,.37)), 1, .38, amount=.58)
    edges(l, .008)
    imask(l, 'grime', .14)
    if a['key'] not in INDOOR:
        l = layer(tree, '45 • Oxide at failed coating and weld contacts', linear((.30,.155,.07)), 0, .91,
            height='source', bump=.00015, kind='IMAGE', im=image('rusty_metal_02/albedo.jpg'), tile=.45, amount=.46)
        edges(l, .011)
        imask(l, 'film', .18)
    dust_and_contact(tree, a, .24, True, True)


def author(mat, holder, key, a):
    tree, p = stack(mat, holder)
    if key.startswith('paint_'):
        paint(tree, p, key, a)
    elif key in METAL:
        col, rough, scan = METAL[key]
        layer(tree, '01 • Alloy reflectance and surface finish', linear(col), 1, rough)
        layer(tree, '06 • Photographic metal surface variation', 'source', kind='IMAGE',
            im=image(scan+'/albedo.jpg'), amount=.075, tile=.6)
        micro(tree, 1200, .000008, (1,9,1) if key in ('stainless','aluminium','brass','bronze') else None)
        l = layer(tree, '20 • Dry tarnish in protected junctions', linear((.23,.235,.20)), 0, .73, amount=.19)
        imask(l, 'film', .28)
        dust_and_contact(tree, a, .18, True, True, True)
    elif key in PHOTO:
        scan, tile, col, rough, normal, tint = PHOTO[key]
        cropped = key in ('concrete_cast','stone_dark','stone_polished','granite_light','marble_warm','wood_aged','timber_warm')
        uv = GRAIN if key in ('wood_aged','timber_warm','plywood','laminate_dark','laminate_white') else UV
        path = scan + ('/surface_albedo.png' if cropped else '/albedo.jpg')
        layer(tree, '01 • CC0 photographic material base', 'source', 0, rough, kind='IMAGE', im=image(path), tile=tile, uv=uv)
        layer(tree, '05 • Reference-matched material colour', linear(col), amount=tint)
        photo_normal(tree, scan, tile, normal, uv, cropped)
        roughpath = scan + ('/surface_roughness.png' if cropped else '/roughness.png')
        layer(tree, '18 • Photographed roughness variation', rough='source', kind='IMAGE',
            im=image(roughpath, True), tile=tile, uv=uv, amount=.22)
        if key.startswith('concrete'):
            l = layer(tree, '30 • Nonuniform mineral weathering', linear((.33,.34,.28)), 0, .94, amount=.23)
            imask(l, 'grime', 1.2)
            micro(tree, 240, .00017)
        dust_and_contact(tree, a, .21 if key.startswith('stone') else .26, key not in ('roof_bitumen','soil'),
            key in ('wood_aged','timber_warm','laminate_dark','laminate_white','stone_polished'))
    elif key in ('wood_aged_end','timber_warm_end'):
        col = (.51,.46,.35) if key=='wood_aged_end' else (.52,.38,.23)
        layer(tree, '01 • Absorbent exposed timber end grain', linear(col),0,.94)
        micro(tree,350,.00022)
        l=layer(tree,'20 • Pore colour in cross-cut fibres',linear(tuple(c*.70 for c in col)),rough=.96,amount=.25)
        noise(l,220,.35,.68)
        dust_and_contact(tree,a,.20,True,False)
    elif key in FABRIC:
        col, rough, tile, normal = FABRIC[key]
        layer(tree, '01 • Woven/coated fabric reference colour', linear(col), 0, rough)
        l = layer(tree, '08 • CC0 photographed yarn tone', 'source', kind='IMAGE',
            im=image('denim_fabric_06/albedo.jpg'), tile=tile, amount=.08, uv=GRAIN)
        photo_normal(tree, 'denim_fabric_06', tile, normal, GRAIN)
        p.inputs['Sheen Weight'].default_value = .18 if not key.startswith('tarp') else .04
        l = layer(tree, '30 • Rubbing on exposed fabric folds', linear(tuple(min(1,c*1.14+.015) for c in col)),
            rough=.74, amount=.22)
        edges(l, .008)
        imask(l, 'film', .18)
        dust_and_contact(tree, a, .24, True, False)
    elif key == 'vinyl_black':
        layer(tree, '01 • Black flexible vinyl upholstery', linear((.10,.105,.095)), 0, .56)
        photo_normal(tree, 'brown_leather', .7, .28, GRAIN)
        dust_and_contact(tree, a, .14, False, True)
    elif key in POLY:
        col, rough = POLY[key]
        layer(tree, '01 • Moulded polymer or rubber, no metal substrate', linear(col), 0, rough)
        micro(tree, 850 if 'rubber' in key else 600, .000028 if 'rubber' in key else .000015)
        l = layer(tree, '25 • Scuffed polymer edges remain dielectric', linear(tuple(c*1.24+.012 for c in col)),
            0, rough+.06, amount=.24)
        edges(l, .002)
        imask(l, 'film', .10)
        dust_and_contact(tree, a, .23, True, key != 'interior_dark')
    elif key in ('rusted_steel','rust_weld','cast_iron','skip_floor'):
        col = (.115,.12,.105) if key == 'cast_iron' else (.26,.16,.075)
        layer(tree, '01 • Oxidized steel/cast iron substrate', linear(col), 0, .88)
        layer(tree, '10 • Photographic oxide darkens substrate, no white painted patches', 'source', 0, .91,
            kind='IMAGE', im=image('rusty_metal_02/albedo.jpg'), tile=.7, amount=.65, blend='MULTIPLY')
        photo_normal(tree, 'rusty_metal_02', .7, .44)
        l = layer(tree, '35 • Polished exposed steel on high contact edges', linear((.34,.35,.32)), 1, .4, amount=.42)
        edges(l,.003)
        imask(l, 'film',.13)
        dust_and_contact(tree,a,.31,True,False)
    elif key == 'car_blue':
        layer(tree, '01 • Dark blue automotive basecoat', linear((.065,.17,.29)), .30, .28)
        micro(tree, 1500, .000006)
        p.inputs['Coat Weight'].default_value = .65
        p.inputs['Coat Roughness'].default_value = .18
        group = next(n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree==tree)
        mat.node_tree.links.new(group.outputs['Roughness'], p.inputs['Coat Roughness'])
        l = layer(tree, '30 • Weathered clearcoat tone on exposed panels', linear((.18,.28,.34)), rough=.43, amount=.12)
        attr(l, 'FaceUp')
        imask(l, 'film', .75)
        l = layer(tree, '50 • Road spray low on doors and wheel arches', linear((.25,.24,.19)), 0, .87, amount=.64)
        attr(l, 'RoadFilm')
        imask(l, 'splash', .60, .8)
        dust_and_contact(tree,a,.23,True,True)
    elif key.startswith('glass_') or key.startswith('optic_') or key == 'pet_blue':
        col = {'glass_clear':(.94,.96,.94), 'glass_smoke':(.49,.57,.54), 'glass_green':(.52,.72,.65),
            'optic_red':(.58,.055,.022), 'optic_amber':(.84,.35,.045), 'optic_green':(.09,.62,.23),
            'pet_blue':(.57,.75,.90)}[key]
        layer(tree, '01 • Transparent dielectric with correct bulk tint', linear(col), 0, .055 if key != 'pet_blue' else .12)
        p.inputs['Transmission Weight'].default_value = .96 if not key.startswith('optic_') else .71
        p.inputs['IOR'].default_value = 1.46 if key.startswith('glass_') else 1.57
        l = layer(tree, '30 • Fine exterior surface dust and wiping film', None, None, .26, amount=.26)
        imask(l,'film', .65)
        l = layer(tree, '40 • Dust trapped at glass perimeter', linear((.43,.43,.37)), 0, .69, amount=.19)
        custom_mask(l, 'original_graphics/perimeter.png', PART)
        imask(l,'dust', .25)
    elif key.startswith('print_'):
        file=key.removeprefix('print_')
        layer(tree,'01 • Original fictional environmental print','source',0,.59,kind='IMAGE',
            im=image('original_graphics/'+file+'.png'),uv=PART)
        if file=='poster':
            group=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree==tree)
            mat.node_tree.links.new(group.outputs['Color'],p.inputs['Emission Color'])
            p.inputs['Emission Strength'].default_value=.18
        l=layer(tree,'30 • Dust and weather film on printed face',linear((.43,.405,.32)),0,.87,amount=.18)
        imask(l,'film',.3)
    elif key.startswith('screen_'):
        layer(tree, '01 • Dark display glass and polarizer', linear((.055,.075,.07)), 0, .14)
        if key != 'screen_off':
            file = 'atm' if key == 'screen_atm' else 'ticket' if key == 'screen_ticket' else 'monitor'
            layer(tree, '10 • Original fictional service display', 'source', kind='IMAGE',
                im=image('original_graphics/'+file+'.png'), uv=PART)
            p.inputs['Emission Strength'].default_value = .35
            group = next(n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree == tree)
            mat.node_tree.links.new(group.outputs['Color'],p.inputs['Emission Color'])
        l=layer(tree,'30 • Hand marks on display glass',None,None,.37,amount=.43)
        imask(l,'finger',.09)
    elif key.startswith('reflector_') or key == 'enamel_blue':
        color = {'white':(.85,.84,.75),'red':(.65,.075,.04),'yellow':(.79,.60,.12),
            'lime':(.69,.78,.18),'cyan':(.12,.55,.64),'blue':(.055,.21,.49)}
        col = color['blue'] if key=='enamel_blue' else color[key.removeprefix('reflector_')]
        layer(tree,'01 • Road enamel or dielectric reflective film',linear(col),0,.34)
        micro(tree,2100,.000004)
        dust_and_contact(tree,a,.16,True,False)
    elif key.startswith('lamp_'):
        col=(.80,.81,.73) if key=='lamp_opal' else (.1,.60,.19)
        layer(tree,'01 • Opal light diffuser',linear(col),0,.32)
        p.inputs['Emission Color'].default_value = (*linear(col),1)
        p.inputs['Emission Strength'].default_value = .35
        l=layer(tree,'30 • Dust on diffuser',None,None,.61,amount=.16)
        imask(l,'dust',.35)
    elif key in ('ink_black','ink_ivory'):
        layer(tree,'01 • Original printed/raised lettering',linear((.045,.05,.04) if key=='ink_black' else (.83,.82,.71)),0,.64)
    else:
        raise ValueError('Unknown production surface: '+key)
    H.reconnect(U, tree)
    mat['surface_recipe']=key
    mat['authoring']='Native UCUPaint 2.4.9; all channels editable; source geometry retained'
    return tree
