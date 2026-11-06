"""ИЗЛОМ-45 (wpn_smg_03): риг для клипов рук — мастер FPS-рук v14 (кисти исправлены, tools/fps_hands_master.py) и игровая
сетка ИЗЛОМа на костях своего рига; стартовый хват — боевой хват владельца с ВЕРАСа (VERAS54_Grip_Manual_v02), перенесённый
на ИЗЛОМ: правая — на пистолетную рукоятку, левая — под передний блок (у ВЕРАСа — под цевьё); владелец правит хват сам
(действие IZLOM45_Ready_v01), клипы строятся от него (как у ВЕРАСа: «хват ставит агент, владелец правит»).

  FPS_ArmsRig (мастер): Weapon_CTRL — ручка оружия (наклоны в клипах), ik_hand.R / ik_hand.L — дочерние ей цели кистей.
  SMG03 (пустышка на кости Weapon_CTRL): оси исходника ИЗЛОМа (X — к дулу, Y — влево, Z — вверх; как VERAS54).
  SMG03_WeaponRig (риг оружия): WeaponRoot, Bolt, ChargingSlider → ChargingHandle, BoltCatch, MagReleaseL / R, Selector
    (флажки с обеих сторон), Safety, Trigger, RearSight, FrontSight, Stock, Magazine_Control → Magazine →
    MagazineFollower; сетки игры (SMG03_Game_LP.blend) — на своих костях; магазин на 30 — скрыт (свой набор клипов потом).
  Рукоятка пистолетного хвата ИЗЛОМа стоит там же, где у ВЕРАСа (GRIP), — правая кисть владельца встаёт без переделки;
  дальше от глаз в игре — смещением сцены (viewmodel.hip_offset).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/clips/rig.py [-- <выход.blend>]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
MASTER = Path('E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend')
LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP.blend'
TEX = ROOT / 'assets/models/weapons/smg03'
READY_JSON = ROOT / '_asset_src/smg03/anim/veras_ready.json'
OUT = Path('E:/Models Blender/WEAPONS/Vector — модель/Анимации/ИЗЛОМ45_Rig_v01.blend')
READY_ACTION = 'VERAS54_Grip_Manual_v02'

GRIP_SRC = Vector((-0.2122, 0.0, -0.035))      # середина пистолетной рукоятки ИЗЛОМа (game_export.GRIP)
GRIP_VERAS = Vector((-0.14, -0.323, 1.635))    # рукоятка ВЕРАСа в мире рига (build_clips.GRIP)
# куда ложится левая ладонь на ИЗЛОМе: под передним блоком, у начала нижней планки (исходник, м)
LEFT_SRC_X = 0.03
MAG_A = math.radians(21.2)
MAG_MOUNT = Vector((-0.03546, 0.0, -0.0116))   # гнездо магазина (game_export.MAG_MOUNT)
# кисти: правка ладони (fps_hands_fix.PALM_LEN) — середина ладони остаётся на месте, запястье подаётся вперёд
PALM_LEN = 0.70
FINGER = 0.74
KNUCKLE_W = 0.76
KNUCKLE_T = 0.84
JAM_CASE_POS = (-0.022, -0.027, 0.007)        # окно выброса справа над патронником (исходник, м)
# кости рига оружия: имя → (голова, направление, родитель, сетки)
BONES = {
    'WeaponRoot': (GRIP_SRC, (1, 0, 0), None, ['Receiver_Upper', 'Receiver_Lower', 'Receiver_Steel', 'Receiver_Stock']),
    'Bolt': ((0.0, 0.0, 0.0), (1, 0, 0), 'WeaponRoot', ['Bolt_Steel']),
    'ChargingSlider': ((0.0, 0.0, 0.0), (1, 0, 0), 'WeaponRoot', ['ChargingSlider_Steel']),
    'ChargingHandle': ((0.0095, 0.02365, 0.023), (0, 0, 1), 'ChargingSlider', ['ChargingHandle_Steel']),
    'BoltCatch': ((-0.02275, 0.02425, 0.01), (0, 0, 1), 'WeaponRoot', ['BoltCatch_Steel']),
    'MagReleaseL': ((-0.01283, 0.0, -0.032406), (0, 1, 0), 'WeaponRoot', ['MagReleaseL_Steel']),
    'MagReleaseR': ((-0.013373, 0.0, -0.033805), (0, -1, 0), 'WeaponRoot', ['MagReleaseR_Steel']),
    'Selector': ((-0.072, 0.0, 0.0385), (0, 1, 0), 'WeaponRoot', ['SelectorL_Steel', 'SelectorR_Steel']),
    'Safety': ((-0.1835, 0.0, 0.039), (0, 1, 0), 'WeaponRoot', ['SafetyL_Steel', 'SafetyR_Steel']),
    'Trigger': ((-0.15, 0.0, 0.022), (0, 1, 0), 'WeaponRoot', ['Trigger_Steel']),
    'RearSight': ((-0.2245, 0.0, 0.0615), (0, 1, 0), 'WeaponRoot', ['RearSightLeaf_Steel']),
    'FrontSight': ((0.1005, 0.0, 0.0615), (0, 1, 0), 'WeaponRoot', ['FrontSightLeaf_Steel']),
    'Stock': ((-0.271, -0.0216, 0.03), (0, 0, 1), 'WeaponRoot', ['Stock_Stock', 'StockLatch_Stock']),
    'Magazine_Control': (tuple(MAG_MOUNT), (math.sin(MAG_A), 0, math.cos(MAG_A)), 'WeaponRoot', []),
    'Magazine': (tuple(MAG_MOUNT), (math.sin(MAG_A), 0, math.cos(MAG_A)), 'Magazine_Control', ['Mag13', 'Mag30', 'Round_01']),
    'MagazineFollower': (tuple(MAG_MOUNT), (math.sin(MAG_A), 0, math.cos(MAG_A)), 'Magazine', ['Mag13_follower']),
    # гильза задержки («гильза в окне»): стоит в окне выброса справа, клип jam её выбрасывает; вне задержки игра прячет
    'JamCase': (JAM_CASE_POS, (0, -1, 0), 'WeaponRoot', ['JamCase']),
}
# детали магазина на 13 (атрибут hp_part игровой сетки, порядок — Mag13['hp']): корпус и донышко остаются, подаватель
# и патрон — свои узлы (игра показывает патрон по счёту, подаватель — по таблице)
MAG13_SPLIT = {'Mag13_follower': {2}, 'Round_01': {3, 4}}
MAP_KIND = {'albedo': ('sRGB', 'Base Color'), 'orm': ('Non-Color', None), 'normal': ('Non-Color', None)}


def log(*a):
    print('SMG03_RIG', *a, flush=True)


def material(atlas):
    m = bpy.data.materials.new(f'ИЗЛОМ-45 • {atlas}')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind, cs):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(TEX / f'smg03_{atlas}_100_{kind}.png'), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    nt.links.new(tex('albedo', 'sRGB').outputs['Color'], b.inputs['Base Color'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tex('orm', 'Non-Color').outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.uv_map = 'GameUV'
    nt.links.new(tex('normal', 'Non-Color').outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m


def split_mag(mag, coll):
    """Части сетки магазина по hp_part: подаватель, патрон, гильза задержки (копия гильзы, повёрнута «свечкой»
    в окно выброса — дно в окне, дульце вправо-вверх)."""
    import bmesh
    out = {}

    def part(name, keep):
        o = mag.copy()
        o.data = mag.data.copy()
        o.name = name
        o.data.name = name
        coll.objects.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        lay = bm.faces.layers.int.get('hp_part')
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lay] not in keep], context='FACES')
        bm.to_mesh(o.data)
        bm.free()
        return o
    for name, keep in MAG13_SPLIT.items():
        out[name] = part(name, keep)
    case = part('JamCase', {3})
    pts = [v.co.copy() for v in case.data.vertices]
    c = sum(pts, Vector()) / max(len(pts), 1)
    q = Vector((1, 0, 0)).rotation_difference(Vector((0.15, -0.75, 0.64)).normalized())
    case.data.transform(Matrix.Translation(Vector(JAM_CASE_POS)) @ q.to_matrix().to_4x4() @ Matrix.Translation(-c))
    out['JamCase'] = case
    bm = bmesh.new()
    bm.from_mesh(mag.data)
    lay = bm.faces.layers.int.get('hp_part')
    drop = set().union(*MAG13_SPLIT.values())
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lay] in drop], context='FACES')
    bm.to_mesh(mag.data)
    bm.free()
    log('магазин на 13 разделён:', {k: len(v.data.polygons) for k, v in out.items()}, 'корпус', len(mag.data.polygons))
    return out


def pose_from_action(arms, name):
    """Кадр 1 действия → matrix_basis всех костей (как build_clips.READY), действие снимается."""
    ad = arms.animation_data or arms.animation_data_create()
    act = bpy.data.actions[name]
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    pose = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
    ad.action = None
    for pb in arms.pose.bones:
        pb.matrix_basis = pose[pb.name]
    bpy.context.view_layer.update()
    return pose


def main():
    out = Path(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv else OUT
    rd = json.loads(READY_JSON.read_text(encoding='utf-8'))
    M = lambda k: Matrix(rd[k])
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    S = bpy.context.scene
    S.render.fps = 30
    arms = bpy.data.objects['FPS_ArmsRig']
    for pb in arms.pose.bones:
        pb.rotation_mode = 'XYZ'
    pose_from_action(arms, READY_ACTION)
    wc = arms.pose.bones['Weapon_CTRL']
    # ---- оружие: сетки игры
    with bpy.data.libraries.load(str(LP)) as (src, dst):
        dst.objects = list(src.objects)
    coll = bpy.data.collections.new('ИЗЛОМ-45 — игровая сетка')
    S.collection.children.link(coll)
    mats = {}
    meshes = {}
    for o in dst.objects:
        if o is None or o.type != 'MESH' or 'atlas' not in o:
            continue
        coll.objects.link(o)
        at = o['atlas']
        if at not in mats:
            mats[at] = material(at)
        o.data.materials.clear()
        o.data.materials.append(mats[at])
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
        meshes[o.name] = o
    log('сетки', sorted(meshes))
    # магазин на 13: подаватель и патрон — отдельно; гильза задержки — копия гильзы патрона
    if 'Mag13' in meshes:
        meshes.update(split_mag(meshes['Mag13'], coll))
    # ---- пустышка оружия на Weapon_CTRL: оси исходника; рукоятка — на месте рукоятки ВЕРАСа
    T = Matrix.Translation(GRIP_VERAS) @ Matrix.Rotation(math.radians(-90.0), 4, 'Z') @ Matrix.Translation(-GRIP_SRC)
    root = bpy.data.objects.new('SMG03', None)
    root.empty_display_type = 'ARROWS'
    root.empty_display_size = 0.05
    coll.objects.link(root)
    root.parent = arms
    root.parent_type = 'BONE'
    root.parent_bone = 'Weapon_CTRL'
    bpy.context.view_layer.update()
    root.matrix_world = T
    bpy.context.view_layer.update()
    # ---- риг оружия
    data = bpy.data.armatures.new('SMG03_WeaponRig')
    wr = bpy.data.objects.new('SMG03_WeaponRig', data)
    coll.objects.link(wr)
    wr.parent = root
    wr.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = wr
    wr.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, d, parent, _) in BONES.items():
        eb = data.edit_bones.new(name)
        eb.head = Vector(head)
        eb.tail = Vector(head) + Vector(d).normalized() * 0.03
        up = Vector((0, 0, 1)) if abs(Vector(d).normalized().z) < 0.9 else Vector((-1, 0, 0))
        eb.align_roll(up)
        eb.use_deform = False
        if parent:
            eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in wr.pose.bones:
        pb.rotation_mode = 'XYZ'
    bpy.context.view_layer.update()
    for name, (_, _, _, parts) in BONES.items():
        for part in parts:
            o = meshes.get(part)
            if o is None:
                log('нет сетки', part)
                continue
            mw = T @ o.matrix_world         # сетки игры — в осях исходника, начало в нуле
            o.parent = wr
            o.parent_type = 'BONE'
            o.parent_bone = name
            bpy.context.view_layer.update()
            o.matrix_world = mw
    if 'Mag30' in meshes:
        meshes['Mag30'].hide_viewport = meshes['Mag30'].hide_render = True
    bpy.context.view_layer.update()
    # ---- стартовый хват: кисти владельца (ВЕРАС) — к ИЗЛОМу; короче ладонь — запястье подаётся к середине ладони
    to_arm = arms.matrix_world.inverted()

    def shrink(wrist, knuckle):
        f = (knuckle - wrist)
        return wrist + f * 0.55 * (1.0 - PALM_LEN)

    # правая: рукоятка ВЕРАСа (GRIP) в осях кисти владельца → та же точка рукоятки ИЗЛОМа (стоит там же) в осях новой
    # кисти: по длине — ладонь × PALM_LEN, дальше пальцы × FINGER; поперёк и по толщине — как ладонь
    w_r = M('hand.R')
    k_r = M('f_middle.01.R').translation
    L_old = (k_r - w_r.translation).length
    rot = w_r.to_3x3()
    rel = rot.transposed() @ (GRIP_VERAS - w_r.translation)
    along = min(rel.y, L_old) * PALM_LEN + max(0.0, rel.y - L_old) * FINGER
    rel_new = Vector((rel.x * KNUCKLE_W, along, rel.z * KNUCKLE_T))
    new_r = w_r.copy()
    new_r.translation = GRIP_VERAS - rot @ rel_new
    log('правая: рукоятка в осях кисти', [round(v, 3) for v in rel], '→', [round(v, 3) for v in rel_new])
    # левая: точка касания под цевьём ВЕРАСа → под передним блоком ИЗЛОМа (низ блока у начала нижней планки)
    blk = [T @ v.co for n in ('Receiver_Upper', 'Receiver_Lower', 'Receiver_Steel') if n in meshes
           for v in meshes[n].data.vertices
           if abs(v.co.x - LEFT_SRC_X) < 0.008 and abs(v.co.y) < 0.012]
    contact_i = min(blk, key=lambda p: p.z) if blk else T @ Vector((LEFT_SRC_X, 0.0, -0.045))
    contact_v = Vector(rd['nearest_weapon']['L'][1])
    w_l = M('hand.L')
    k_l = M('f_middle.01.L').translation
    new_l = w_l.copy()
    new_l.translation = shrink(w_l.translation, k_l) + (contact_i - contact_v)
    # середина новой ладони — над точкой касания по длине оружия (оружие смотрит в −Y мира)
    palm_c = new_l.translation + (k_l - w_l.translation) * 0.55 * PALM_LEN
    new_l.translation.y += contact_i.y - palm_c.y
    log('правая: запястье', [round(v, 3) for v in new_r.translation], 'левая: касание', [round(v, 3) for v in contact_i],
        'запястье', [round(v, 3) for v in new_l.translation])
    for side, m in (('R', new_r), ('L', new_l)):
        ik = arms.pose.bones[f'ik_hand.{side}']
        ik.matrix = to_arm @ m
    bpy.context.view_layer.update()
    # правая: середина обхвата (средние фаланги четырёх пальцев и середина ладони) — на ось рукоятки ИЗЛОМа (GRIP);
    # по высоте рукоятки кисть не сдвигается
    def grasp_center():
        pts = [arms.matrix_world @ arms.pose.bones[f'{f}.02.R'].head for f in ('f_index', 'f_middle', 'f_ring', 'f_pinky')]
        w = arms.matrix_world @ arms.pose.bones['hand.R'].head
        k = arms.matrix_world @ arms.pose.bones['f_middle.01.R'].head
        pts.append(w + (k - w) * 0.6)
        return sum(pts, Vector()) / len(pts)
    grip_axis = (T.to_3x3() @ Vector((0.27, 0.0, -0.96))).normalized()     # рукоятка Vector наклонена назад ~16°
    for _ in range(3):
        d = GRIP_VERAS - grasp_center()
        d -= grip_axis * d.dot(grip_axis)
        ik = arms.pose.bones['ik_hand.R']
        ik.matrix = Matrix.Translation(to_arm.to_3x3() @ d) @ ik.matrix
        bpy.context.view_layer.update()
    log('правая: обхват от оси рукоятки, мм', round((GRIP_VERAS - grasp_center() -
                                                    grip_axis * (GRIP_VERAS - grasp_center()).dot(grip_axis)).length * 1000, 1))
    # не дотягивается — плечо вперёд к цели (как у Мосина: shoulder_to)
    for side in ('L', 'R'):
        for _ in range(6):
            hand = arms.pose.bones[f'hand.{side}']
            ik = arms.pose.bones[f'ik_hand.{side}']
            gap = (ik.head - hand.head)
            if gap.length < 0.002:
                break
            ua = arms.pose.bones[f'upper_arm.{side}']
            ua.matrix = Matrix.Translation(gap * 1.05) @ ua.matrix
            bpy.context.view_layer.update()
        hand = arms.pose.bones[f'hand.{side}']
        log(f'кисть {side}: до цели, мм', round((arms.pose.bones[f"ik_hand.{side}"].head - hand.head).length * 1000, 1))
    # ---- действие хвата ИЗЛОМа (его правит владелец): ключи всех костей на кадре 1
    act = bpy.data.actions.new('IZLOM45_Ready_v01')
    act.use_fake_user = True
    ad = arms.animation_data or arms.animation_data_create()
    ad.action = act
    for pb in arms.pose.bones:
        pb.keyframe_insert('location', frame=1)
        pb.keyframe_insert('rotation_euler', frame=1)
        pb.keyframe_insert('scale', frame=1)
    S.frame_start, S.frame_end = 1, 1
    S.camera = bpy.data.objects.get('FPS • Camera')
    txt = bpy.data.texts.new('ИЗЛОМ-45 — риг и хват')
    txt.from_string(__doc__ + '\nХват правит владелец: Pose Mode, кадр 1, действие IZLOM45_Ready_v01 (ключи — I). Цели кистей — '
                    'ik_hand.R / ik_hand.L (дочерние Weapon_CTRL), пальцы — повороты костей пальцев.\n')
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    log('сохранено', out)


if __name__ == '__main__':
    main()
