"""R06 approved geometry -> editable native UCUPaint finish, without mesh edits.

Blender 5.2.2 / UCUPaint 2.4.9. preview: transient close view before packaging.
build: save a separate candidate; render: reopen that saved candidate.
"""
from pathlib import Path
import hashlib
import importlib
import importlib.util
import json
import math
import os
import sys
import time

import addon_utils
import bpy
import numpy as np
from mathutils import Vector

PROJECT = Path(__file__).resolve().parents[3]
ASSET = PROJECT / '_asset_src/urban_realrefs_v02/assets/R06_building'
ROOT = ASSET / 'pbr_v01'
TEX = ROOT / 'textures'
SOURCE = ASSET / 'model/R06_building_geometry_v02.blend'
MASTER = ROOT / 'model/R06_building_pbr_v01.blend'
SKILL = Path('C:/Users/Schecter_8ght/.agents/skills/weapon-asset-texturing')
UV, WALL, PART = 'MetricUV', 'WeatherUV', 'PartUV'
U = H = None
STACKS = {}
MATS = {}
SHIFT = None


def native():
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    spec = importlib.util.spec_from_file_location('r06_ucup_helpers', SKILL / 'scripts/ucupaint_helpers.py')
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    U = H.load_ucupaint()
    print('R06_NATIVE', bpy.app.version_string, U.common.get_current_version_str(), flush=True)


def active(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.active_material_index = 0


def srgb(rgb):
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb)


def img(relative, data=False):
    path = TEX / relative
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
    return im


def classify(ob):
    n = ob.name
    role = ob.get('finish_role', '')
    if n.startswith('FACADE |'):
        return 'plaster_front'
    if n.startswith('INTERIOR |'):
        return 'plaster_inside'
    if role == 'plaster':
        return 'plaster_rear' if 'rear masonry' in n else 'plaster_side'
    if role == 'brick':
        return 'brick'
    if role == 'mortar':
        return 'mortar'
    if role == 'glass':
        return 'glass'
    if role == 'rubber':
        return 'seal'
    if role == 'plastic':
        return 'pvc'
    if role == 'wood':
        return 'door'
    if role == 'diffuser':
        return 'diffuser'
    if n.startswith('SIGN | original title') or n.startswith('DETAIL | fictional address'):
        return 'lettering'
    if n.startswith('SIGN | faculty board') or n.startswith('DETAIL | address tablet'):
        return 'sign'
    if role == 'roof':
        return 'roof'
    if 'canopy' in n:
        return 'canopy'
    if 'conduit' in n:
        return 'conduit'
    if 'sill' in n:
        return 'sill'
    if n.startswith('ROOF |'):
        return 'flashing'
    if 'pull' in n or 'fixing' in n:
        return 'steel'
    if role == 'metal':
        return 'fixture'
    if n.startswith('PLINTH |'):
        return 'plinth'
    if role == 'concrete':
        return 'concrete'
    return 'mortar'


def assign_and_uv():
    """Only material slots, UVs and CORNER color attributes; all shape data intact."""
    global SHIFT
    bpy.context.view_layer.update()
    SHIFT = bpy.data.objects['FACADE | continuous rippled plaster'].matrix_world.translation.copy()
    for ob in bpy.data.collections['MODEL | editable components'].objects:
        if ob.type not in ('MESH', 'FONT', 'CURVE'):
            continue
        key = classify(ob)
        if key not in MATS:
            mat = bpy.data.materials.new('R06_' + key)
            mat.use_nodes = True
            mat['surface'] = key
            mat['authoring'] = 'Native UCUPaint 2.4.9; geometry approved by owner 2026-10-24'
            MATS[key] = mat
        ob.data.materials.clear()
        ob.data.materials.append(MATS[key])
        for face in ob.data.polygons if ob.type == 'MESH' else []:
            face.material_index = 0
        if ob.type != 'MESH':
            continue
        me = ob.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        mw = np.array(ob.matrix_world, np.float64)
        p = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3] - np.array(SHIFT)
        ix = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get('vertex_index', ix)
        lp = p[ix]
        normal = np.empty(len(me.polygons) * 3, np.float32)
        me.polygons.foreach_get('normal', normal)
        total = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_total', total)
        ns = np.repeat(normal.reshape(-1, 3) @ np.linalg.inv(mw[:3, :3]), total, axis=0)
        # World-projected metres per UV, independent of object scale/origin.
        axis = np.abs(ns).argmax(axis=1)
        metric = np.stack((lp[:, 0], lp[:, 2]), axis=1)
        metric[axis == 0] = lp[axis == 0][:, (1, 2)]
        metric[axis == 2] = lp[axis == 2][:, (0, 1)]
        weather = np.stack(((lp[:, 0] + 17.4) / 34.8, lp[:, 2] / 6.65), axis=1)
        if 'side' in key:
            weather[:, 0] = (lp[:, 1] + 5.25) / 10.5
        part = metric.copy()
        a, b = part.min(axis=0), part.max(axis=0)
        part = (part - a) / np.maximum(b - a, .0001)
        for name, values in ((UV, metric), (WALL, weather), (PART, part)):
            uv = me.uv_layers.get(name) or me.uv_layers.new(name=name)
            uv.data.foreach_set('uv', values.astype(np.float32).ravel())
        me.uv_layers.active = me.uv_layers[UV]
        me.uv_layers[UV].active_render = True
        up = np.clip(ns[:, 2], 0, 1)
        # Real height and real face orientation; no fake vertex edge mask on cubes.
        attrs = {'FaceUp': up, 'AtGround': np.clip((.65 - lp[:, 2]) / .55, 0, 1)}
        if key == 'canopy':
            # Causal paint breakdown at the actual folded lip and distorted corner.
            center = -7.8 if lp[:, 0].mean() < 0 else 7.8
            side_edge = np.maximum(0, 1.28 - np.abs(lp[:, 0] - center))
            front_edge = np.abs(lp[:, 1] - (-5.25 - 1.12))
            edge = np.exp(-np.minimum(side_edge, front_edge) / .025)
            fold = np.exp(-((lp[:, 0] - center - .66) / .17) ** 2) * np.exp(-front_edge / .20)
            attrs['CanopyWear'] = np.clip(np.maximum(edge, fold * .85), 0, 1)
        for name, values in attrs.items():
            attr = me.color_attributes.get(name) or me.color_attributes.new(name=name, type='FLOAT_COLOR', domain='CORNER')
            rgba = np.ones((len(ix), 4), np.float32)
            rgba[:, :3] = values[:, None]
            attr.data.foreach_set('color', rgba.ravel())
        if key == 'brick':
            # Per-brick fired-clay variation is stable by object identity.
            seed = int(hashlib.sha256(ob.name.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            col = np.array(srgb((.54, .33, .20))) * rng.uniform(.77, 1.22)
            col *= np.array((rng.uniform(.93, 1.08), rng.uniform(.93, 1.05), 1))
            attr = me.color_attributes.get('FiredClay') or me.color_attributes.new(name='FiredClay', type='FLOAT_COLOR', domain='CORNER')
            rgba = np.ones((len(ix), 4), np.float32)
            rgba[:, :3] = col
            attr.data.foreach_set('color', rgba.ravel())
        me.update()
    print('R06_UV_READY', len(MATS), 'materials', flush=True)


def stack(key):
    mat = MATS[key]
    ob = next(o for o in bpy.data.collections['MODEL | editable components'].objects
        if o.type == 'MESH' and mat in list(o.data.materials))
    active(ob)
    p = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    p.inputs['Roughness'].default_value = .6
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='R06 • ' + key, color=True, metallic=True,
        roughness=True, normal=True, ao=False, switch_to_material_view=False, target_bsdf_name=p.name)
    group = next(n for n in mat.node_tree.nodes if n.type == 'GROUP' and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    normal = next(c for c in tree.yp.channels if c.type == 'NORMAL')
    normal.main_uv = UV
    normal.enable_smooth_bump = False
    STACKS[key] = tree
    return tree, p


def scale_entity(entity, s):
    if isinstance(s, (int, float)):
        s = (s, s, s)
    entity.enable_uniform_scale = False
    H.sync_property(U, entity, 'scale', Vector(s))


def lay(tree, name, color=None, metal=None, rough=None, height=None, source='COLOR',
        image=None, uv=UV, tile=1, amount=1, distance=.0001, normal_type='BUMP_MAP', vcol=None):
    tree.yp.halt_update = True
    result = U.Layer.add_new_layer(tree, name, source, -1, 'MIX', 'OVERLAY', normal_type,
        'UV', uv, image=image, vcol=vcol, use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    for root, ch in zip(tree.yp.channels, result.channels):
        value = {'Color': color, 'Metallic': metal, 'Roughness': rough, 'Normal': height}[root.name]
        ch.enable = value is not None
        if value is None:
            continue
        if not isinstance(value, str):
            ch.override = True
            ch.override_type = 'DEFAULT'
            H.sync_property(U, ch, 'override_color' if root.type == 'RGB' else 'override_value', value)
        if root.type == 'NORMAL':
            H.sync_property(U, ch, 'bump_distance', distance)
            H.sync_property(U, ch, 'bump_midlevel', .5)
            if normal_type == 'NORMAL_MAP':
                H.sync_property(U, ch, 'normal_strength', 1.0)
    H.sync_property(U, result, 'intensity_value', amount)
    if source == 'IMAGE':
        U.common.get_layer_source(result).extension = 'REPEAT'
        scale_entity(result, 1 / tile)
    return result


def image_mask(layer, im, label, tile=1, uv=UV, intensity=1):
    m = U.Mask.add_new_mask(layer, label, 'IMAGE', 'UV', uv, image=im)
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.extension = 'REPEAT' if uv != WALL else 'EXTEND'
    scale_entity(m, 1 / tile)
    H.sync_property(U, m, 'intensity_value', intensity)
    return m


def attr_mask(layer, attr, label=None):
    return U.Mask.add_new_mask(layer, label or attr, 'VCOL', 'Object', UV, vcol_name=attr)


def nmask(layer, label, scale, lo=.25, hi=.75, stretch=None):
    m = U.Mask.add_new_mask(layer, label, 'NOISE', 'Object', UV)
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.inputs['Scale'].default_value = scale
    src.inputs['Detail'].default_value = 2.6
    src.inputs['Roughness'].default_value = .66
    if stretch:
        scale_entity(m, stretch)
    H.local_noise_ramp(U, m, lo, hi)
    return m


def photo_normal(tree, key, tile, amount=.35, single=False):
    return lay(tree, '12 • Photographic surface normal (CC0)', height='source', source='IMAGE',
        image=img(key + ('/single_normal.png' if single else '/normal.jpg'), True),
        tile=tile, amount=amount, normal_type='NORMAL_MAP')


def film(tree, amount=.16, tile=.7, top=False):
    l = lay(tree, '70 • Dry deposited dust in sheltered places', srgb((.48, .465, .43)), 0, .88, amount=amount)
    image_mask(l, img('owner_dust.png', True), 'Owner mask • sparse dust', tile)
    if top:
        attr_mask(l, 'FaceUp', 'Upward faces collect dust')
    return l


def plaster(key, elevation):
    tree, p = stack(key)
    lay(tree, '01 • Lime-painted plaster, CC0 photo base', 'source', 0, .83,
        source='IMAGE', image=img('painted_plaster_wall/albedo.jpg'), tile=2)
    lay(tree, '05 • Off-white lime paint matched to owner photos', srgb((.85, .845, .80)), amount=.38)
    photo_normal(tree, 'painted_plaster_wall', 2, .58)
    l = lay(tree, '16 • Old trowel ridges and local swollen coating', height='source',
        source='NOISE', uv=UV, distance=.018, amount=.80)
    source = U.common.get_layer_source(l)
    source.inputs['Scale'].default_value = 1.0
    source.inputs['Detail'].default_value = 1.3
    source.inputs['Roughness'].default_value = .45
    scale_entity(l, (1.3, 6.5, 1.0))
    image_mask(l, img(f'weather/{elevation}_swelling.png', True), 'Between-floor band seen in photo 2', uv=WALL)
    lay(tree, '18 • Roughness variation from plaster scan', rough='source', source='IMAGE',
        image=img('painted_plaster_wall/roughness.png', True), tile=2, amount=.38)
    # Sparse broad variation preserves the photo grain without universal noise grime.
    l = lay(tree, '20 • Uneven old repainting, warm pale grey', srgb((.72, .705, .65)), rough=.88, amount=.22)
    image_mask(l, img(f'weather/{elevation}_lime.png', True), 'Unique elevation repairs', uv=WALL)
    l = lay(tree, '30 • Dust washed from actual window sills', srgb((.38, .36, .30)), 0, .92, amount=.48)
    image_mask(l, img(f'weather/{elevation}_runoff.png', True), 'Sill positions and gravity • unique atlas', uv=WALL)
    l = lay(tree, '35 • Rain accumulation beneath eaves', srgb((.30, .29, .245)), 0, .92, amount=.55)
    image_mask(l, img(f'weather/{elevation}_eaves.png', True), 'Roof edge, no face-wide dirt', uv=WALL)
    l = lay(tree, '40 • Capillary dampness above plinth', srgb((.29, .31, .255)), 0, .94, amount=.43)
    image_mask(l, img(f'weather/{elevation}_damp.png', True), 'Ground contact band', uv=WALL)
    l = lay(tree, '45 • Hairline stress cracks in old plaster', srgb((.35, .335, .29)), 0, .9, height=.25, distance=.00045, amount=.5)
    image_mask(l, img(f'weather/{elevation}_hairline.png', True), 'Sparse opening stress, not a crack grid', uv=WALL)
    l = lay(tree, '48 • Fine coating age within damaged band', srgb((.59, .58, .535)), rough=.9, height=.38, distance=.00012, amount=.18)
    image_mask(l, img('owner_hairline.png', True), 'Owner weak-aging mask • 60 cm', tile=.60)
    image_mask(l, img(f'weather/{elevation}_lime.png', True), 'Confine to patches, do not cover whole wall', uv=WALL)
    H.reconnect(U, tree)


def plain_photo(key, color, scan='painted_plaster_wall', tile=1, rough=.8, normal=.18):
    tree, p = stack(key)
    lay(tree, '01 • Material substrate', srgb(color), 0, rough)
    l = lay(tree, '10 • Photo grain and discolouration (CC0)', 'source', rough=None,
        source='IMAGE', image=img(scan + '/albedo.jpg'), tile=tile, amount=.12)
    photo_normal(tree, scan, tile, normal)
    return tree, p


def materials():
    for key, elevation in (('plaster_front', 'front'), ('plaster_rear', 'rear'), ('plaster_side', 'side')):
        plaster(key, elevation)
    tree, p = plain_photo('plaster_inside', (.72, .71, .65), tile=2, normal=.12)
    H.reconnect(U, tree)
    tree, p = plain_photo('mortar', (.52, .50, .435), 'rough_concrete', .8, .94, .35)
    H.reconnect(U, tree)
    tree, p = stack('brick')
    ob = bpy.context.object
    lay(tree, '01 • Individually fired terracotta bricks', 'source', 0, .91,
        source='VCOL', vcol=ob.data.color_attributes['FiredClay'])
    lay(tree, '06 • Clay pores from one CC0 brick face', 'source', source='IMAGE',
        image=img('red_bricks_04/single_albedo.png'), tile=.246, amount=.23)
    photo_normal(tree, 'red_bricks_04', .246, .45, single=True)
    film(tree, .14, .36, True)
    H.reconnect(U, tree)
    # PVC is paint-white dielectric, with restrained ageing around up-facing rails.
    tree, p = stack('pvc')
    lay(tree, '01 • Aged white PVC extrusion', srgb((.83, .83, .79)), 0, .32)
    l = lay(tree, '20 • Light weather film, no flaking metal', srgb((.52, .51, .46)), 0, .61, amount=.19)
    image_mask(l, img('owner_film.png', True), 'Owner film, 45 cm', .45)
    film(tree, .21, .40, True)
    H.reconnect(U, tree)
    tree, p = stack('seal')
    lay(tree, '01 • EPDM glazing seal', srgb((.065, .062, .055)), 0, .73)
    film(tree, .08, .3, True)
    H.reconnect(U, tree)
    tree, p = stack('glass')
    lay(tree, '01 • Clear window glass, 6 mm accepted geometry', (.94, .96, .95), 0, .045)
    p.inputs['Transmission Weight'].default_value = .97
    p.inputs['IOR'].default_value = 1.46
    l = lay(tree, '20 • Sparse outside dust visible in reflection', srgb((.78, .78, .72)), rough=.24, amount=.19)
    image_mask(l, img('owner_film.png', True), 'Owner dry film • 1.2 m', 1.2)
    H.reconnect(U, tree)
    tree, p = plain_photo('door', (.24, .065, .045), 'wood_planks_grey', .8, .46, .12)
    # Keep original dark red painted timber; only slight chalking and local dirt.
    l = lay(tree, '20 • Chalked red paint, irregular sun exposure', srgb((.34, .13, .095)), rough=.67, amount=.25)
    image_mask(l, img('owner_film.png', True), 'Owner patch film, timber scale', .40)
    l = lay(tree, '30 • Ground splash and dirt on lower leaves', srgb((.16, .13, .10)), 0, .9, amount=.40)
    attr_mask(l, 'AtGround')
    nmask(l, 'Break ground splash irregularly', 24, .26, .65)
    H.reconnect(U, tree)
    for key, base, rough, metal in (
        ('canopy', (.56, .49, .27), .61, 0),
        ('sill', (.62, .62, .56), .48, 0),
        ('flashing', (.30, .31, .285), .54, .65),
        ('conduit', (.76, .765, .69), .61, 0),
        ('steel', (.59, .60, .58), .28, 1),
        ('fixture', (.39, .40, .355), .53, 0),
    ):
        tree, p = stack(key)
        lay(tree, '01 • Physical substrate and finish', srgb(base), metal, rough)
        if key in ('canopy', 'sill', 'flashing'):
            l = lay(tree, '10 • Local weathered sheet grain (CC0)', 'source', source='IMAGE',
                image=img('rusty_metal_sheet/albedo.jpg'), tile=.8, amount=.10 if key != 'canopy' else .16)
            photo_normal(tree, 'rusty_metal_sheet', .8, .13)
        if key == 'canopy':
            l = lay(tree, '20 • Dull ochre paint, patched fading', srgb((.65, .57, .34)), 0, .72, amount=.36)
            image_mask(l, img('owner_film.png', True), 'Broken paint tone, 35 cm', .35)
            # Local shape-derived edges, then irregular image breakup.
            l = lay(tree, '35 • Rust at bent steel edges and seams', srgb((.28, .15, .07)), 0, .91, height=.63, distance=.00028, amount=.63)
            attr_mask(l, 'CanopyWear', 'Actual lip and bent-corner stress')
            m = image_mask(l, img('owner_film.png', True), 'Break rust into local patches', .18, intensity=.65)
            l = lay(tree, '40 • Dark runoff at failed paint folds', srgb((.24, .235, .17)), 0, .86, amount=.5)
            attr_mask(l, 'CanopyWear')
            image_mask(l, img('owner_film.png', True), 'Soft stain around exposed areas', .35, intensity=.65)
        film(tree, .20 if key != 'steel' else .09, .55, True)
        H.reconnect(U, tree)
    tree, p = plain_photo('concrete', (.46, .45, .40), 'rough_concrete', 1.2, .88, .25)
    film(tree, .15, .6, True)
    H.reconnect(U, tree)
    tree, p = plain_photo('plinth', (.38, .38, .32), 'rough_concrete', .8, .93, .36)
    l = lay(tree, '30 • Wet-ground mineral staining', srgb((.23, .25, .18)), 0, .95, amount=.40)
    attr_mask(l, 'AtGround')
    image_mask(l, img('owner_film.png', True), 'Broken green-grey damp film', .45)
    H.reconnect(U, tree)
    tree, p = stack('roof')
    lay(tree, '01 • Old bituminous flat roofing', srgb((.16, .17, .155)), 0, .91)
    photo_normal(tree, 'rough_concrete', .4, .18)
    film(tree, .21, 2, True)
    H.reconnect(U, tree)
    tree, p = stack('sign')
    lay(tree, '01 • Faded blue-green enamel sign', srgb((.11, .23, .235)), 0, .48)
    film(tree, .17, .5)
    H.reconnect(U, tree)
    # Text is FONT; create stack on a temporary active existing mesh of another
    # material, restore assignment immediately. No temporary scene objects.
    key = 'lettering'
    mat = MATS[key]
    holder = next(o for o in bpy.data.collections['MODEL | editable components'].objects if o.type == 'MESH')
    keep = holder.data.materials[0]
    holder.data.materials[0] = mat
    tree, p = stack(key)
    lay(tree, '01 • Ivory printed lettering, fictional text', srgb((.81, .80, .69)), 0, .56)
    H.reconnect(U, tree)
    holder.data.materials[0] = keep
    tree, p = stack('diffuser')
    lay(tree, '01 • Warm opal lamp diffuser', srgb((.87, .85, .73)), 0, .28)
    p.inputs['Emission Color'].default_value = (1, .82, .54, 1)
    p.inputs['Emission Strength'].default_value = .0
    H.reconnect(U, tree)
    print('R06_MATERIALS_READY', len(STACKS), flush=True)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = int(os.environ.get('R06_SAMPLES', '32'))
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 9
    sc.cycles.transmission_bounces = 8
    sc.cycles.transparent_max_bounces = 8
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = 0
    # Physical sky rather than huge flat studio brightness; existing studio object
    # set is preserved. Camera/light poses are diagnostics, not model transforms.
    for ob in bpy.data.collections['STUDIO | neutral lights, no export'].objects:
        if ob.type == 'LIGHT':
            ob.data.energy = 0
    world = sc.world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = .75
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = img('kloofendal_overcast_puresky.hdr', True)
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type == 'OPTIX'
        if any(d.use for d in prefs.devices):
            sc.cycles.device = 'GPU'
        print('R06_DEVICES', [(d.name, d.type, d.use) for d in prefs.devices], flush=True)
    except Exception as exc:
        print('R06_CPU_FALLBACK', str(exc), flush=True)
    return sc


def render_views(names=None):
    global SHIFT
    sc = setup_render()
    bpy.context.view_layer.update()
    SHIFT = bpy.data.objects['FACADE | continuous rippled plaster'].matrix_world.translation.copy()
    folder = ROOT / 'previews'
    folder.mkdir(parents=True, exist_ok=True)
    cam = sc.camera
    views = {
        'damage_day': ((10.65, -5.28, 5.08), (1, -8, .85), 5.0, (1400, 1150)),
        'entry_day': ((-7.8, -5.28, 3.12), (2, -8, .75), 5.5, (1400, 1400)),
        'plaster_day': ((9.45, -5.28, 3.55), (.45, -8, .50), 3.8, (1400, 1100)),
        'front34_day': ((0, 0, 3.32), (12, -49, 10), 40.5, (2100, 820)),
        'front_day': ((0, -5.28, 3.3), (0, -49, .01), 37.6, (2100, 700)),
        'rear34_day': ((0, 0, 3.3), (-18, 46, 12), 41, (1800, 1050)),
        'canopy_day': ((-7.8, -6.05, 2.95), (1.7, -4, 1.3), 3.5, (1400, 1000)),
        'plaster_night': ((9.45, -5.28, 3.55), (.45, -8, .50), 3.8, (1400, 1100)),
        'front34_night': ((0, -5.28, 3.32), (8, -49, 4.4), 39.3, (2100, 700)),
    }
    records = []
    only = set(names or views)
    for name, (target, offset, width, size) in views.items():
        if name not in only:
            continue
        target = Vector(target) + SHIFT
        cam.location = target + Vector(offset)
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = width
        key = bpy.data.objects['Large soft key']
        # A broad raking daylight source exposes the accepted plaster undulations.
        key.location = target + Vector((-4.2, -3.0, 2.8)) if width < 10 else Vector((-24, -18, 17))
        key.rotation_euler = (target - key.location).to_track_quat('-Z', 'Y').to_euler()
        key.data.energy = 270 if width < 10 else 6500
        key.data.size = 1.8 if width < 10 else 5.0
        night = name.endswith('_night')
        bg = next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs['Strength'].default_value = .022 if night else .75
        for light in ('Soft fill', 'Rim softbox'):
            bpy.data.objects[light].data.energy = 0
        diffuser = bpy.data.materials.get('R06_diffuser')
        dp = next(n for n in diffuser.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        dp.inputs['Emission Strength'].default_value = 8 if night else 0
        if night:
            key.data.energy = 0
            for lightname, x in (('Soft fill', -7.8), ('Rim softbox', 7.8)):
                lamp = bpy.data.objects[lightname]
                lamp.location = Vector((x, -5.75, 6.06)) + SHIFT
                look = Vector((x, -5.26, 3.7)) + SHIFT
                lamp.rotation_euler = (look - lamp.location).to_track_quat('-Z', 'Y').to_euler()
                lamp.data.energy = 135
                lamp.data.size = .24
                lamp.data.color = (1.0, .91, .73)
            sc.view_settings.exposure = 1.0
        else:
            sc.view_settings.exposure = 0
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.resolution_percentage = 100
        sc.render.filepath = str(folder / (name + '.png'))
        bpy.ops.render.render(write_still=True)
        records.append(dict(view=name, file=sc.render.filepath, source_blend=bpy.data.filepath,
            samples=sc.cycles.samples, note='Cycles; physical overcast sky; same accepted geometry'))
        print('R06_VIEW_READY', name, flush=True)
    (ROOT / 'checks').mkdir(exist_ok=True)
    (ROOT / 'checks/render_views.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


def apply():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    native()
    assign_and_uv()
    materials()
    # No source mesh, modifiers, hierarchy, local pose or shape key is changed.
    for ob in bpy.data.collections['MODEL | editable components'].objects:
        if ob.type == 'EMPTY' and ob.name.startswith('R06 |'):
            ob['geometry_approved'] = True
            ob['geometry_approval'] = 'Owner 2026-10-24: Форма подходит — переходи к текстурам'
            ob['production_uv'] = True
            ob['production_textures'] = True
            ob['texture_approved'] = False
    sc = setup_render()
    sc['stage'] = 'Approved geometry; native UCUPaint texture candidate for owner review'
    sc['geometry_source_sha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    sc['texture_version'] = 'R06_pbr_v01'
    return sc


def save():
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    # External copies alongside packed bytes. References stay a reference, never
    # become albedo. Their untouched originals already exist in the v02 library.
    dep = ROOT / 'dependencies'
    dep.mkdir(exist_ok=True)
    images = []
    for im in bpy.data.images:
        if im.source in {'FILE', 'GENERATED'} and im.name not in {'Render Result', 'Viewer Node'}:
            original = im.filepath
            try:
                im.pack()
            except RuntimeError:
                pass
            if not im.packed_file:
                raise RuntimeError('Unpacked dependency: ' + im.name)
            raw = bytes(im.packed_file.data)
            digest = hashlib.sha256(raw).hexdigest()
            suffix = Path(original).suffix.lower() or '.png'
            base = Path(original).stem
            name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in base)[:64]
            file = dep / (name + '_' + digest[:10] + suffix)
            if not file.exists():
                file.write_bytes(raw)
            im.filepath = '//../dependencies/' + file.name
            images.append(dict(datablock=im.name, file=file.relative_to(ROOT).as_posix(),
                sha256=digest, bytes=len(raw), size=list(im.size), colorspace=im.colorspace_settings.name,
                source_path=original, packed=True))
    (ROOT / 'checks').mkdir(exist_ok=True)
    (ROOT / 'checks/image_manifest.json').write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding='utf-8')
    # Useful initial view in the saved material candidate.
    cam = bpy.context.scene.camera
    target = Vector((0, 0, 3.32)) + SHIFT
    cam.location = target + Vector((12, -49, 10))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 40.5
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.region_3d.view_distance = 40
                area.spaces.active.region_3d.view_location = target
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER), compress=True, relative_remap=False)
    print('R06_PBR_SAVED', MASTER, flush=True)


def inspect():
    data = []
    for mat in bpy.data.materials:
        if not mat.name.startswith('R06_'):
            continue
        groups = [n for n in mat.node_tree.nodes if n.type == 'GROUP' and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node]
        for group in groups:
            tree = group.node_tree
            layers = []
            for l in tree.yp.layers:
                channels = []
                for root, ch in zip(tree.yp.channels, l.channels):
                    channels.append(dict(name=root.name, enable=ch.enable, override=ch.override,
                        native_value=str(U.common.get_entity_prop_value(ch, 'override_color' if root.type == 'RGB' else 'override_value')),
                        normal_map_type=ch.normal_map_type,
                        bump_distance=float(U.common.get_entity_prop_value(ch, 'bump_distance')) if root.type == 'NORMAL' else None))
                layers.append(dict(name=l.name, type=l.type, enabled=l.enable, uv=l.uv_name,
                    masks=[dict(name=m.name, type=m.type, uv=m.uv_name) for m in l.masks], channels=channels))
            data.append(dict(material=mat.name, native_version=tree.yp.version,
                output_links=[(link.from_socket.name, link.to_node.name, link.to_socket.name)
                    for link in mat.node_tree.links if link.from_node == group], layers=layers))
    (ROOT / 'checks').mkdir(exist_ok=True)
    (ROOT / 'checks/native_stacks.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('R06_NATIVE_INSPECTED', len(data), flush=True)


def main():
    global ROOT, TEX, MASTER
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['preview']
    mode = args[0]
    names = args[1:] or None
    if mode == 'preview':
        apply()
        inspect()
        render_views(names or ['damage_day'])
    elif mode == 'build':
        apply()
        inspect()
        save()
    elif mode == 'render':
        bpy.ops.wm.open_mainfile(filepath=str(MASTER))
        native()
        render_views(names)
    elif mode == 'render-delivery':
        ROOT = Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references/assets/R06_building/pbr_v01')
        TEX = ROOT / 'textures'
        MASTER = ROOT / 'model/R06_building_pbr_v01.blend'
        bpy.ops.wm.open_mainfile(filepath=str(MASTER))
        native()
        render_views(names)
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    main()
