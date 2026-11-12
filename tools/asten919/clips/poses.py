"""АСТЕН-919 (wpn_hg_02): позы-заготовки рук для клипов — действие ASTEN919_Poses (хваты; их правит владелец).

На риге tools/asten919/clips/rig.py ставит черновые позы и пишет их ключами по кадрам действия ASTEN919_Poses (у каждого
кадра маркер). Клипы (build_clips.py) берут позы пальцев и места кистей ТОЛЬКО отсюда: поправил позу здесь — пересобрал
клипы — хват изменился во всех клипах, движение не тронуто.

  1  ХВАТ: обе руки на пистолете, указательный вдоль рамки            41  Л: магазин в кисти (магазин вышел на 55 мм)
  11 П: указательный на спуске                                        46  Л: ладонь досылает магазин
  16 П: спуск выжат                                                   51  Л: щепоть на затворе (передёргивание)
  21 П: большой на кнопке магазина                                    61  Л: кисть свободна (в пути, у подсумка)
  26 П: большой на рычаге задержки (затвор на задержке)
  31 П: большой вверх (осмотр)

Кость mag.L (дочерняя кисти hand.L) — место магазина в левой кисти: в клипах магазин «прилипает» к ней ограничением
Copy Transforms у кости Magazine_Control (влияние 0 / 1). Сдвинул mag.L на кадре 41 — магазин иначе лежит в кисти везде.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<ASTEN919_Rig_v01.blend>" --python-exit-code 1 --python tools/asten919/clips/poses.py -- <выход.blend>
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[sys.argv.index("--") + 1])
sys.argv = sys.argv[:sys.argv.index("--")]            # grip.py — модулем, без своих аргументов
sys.path.insert(0, str(HERE))
POSES = "ASTEN919_Poses"
MAG_DROP = 0.055                                      # магазин выпал в ладонь на столько (м) — за нижнюю часть берут
SLIDE_TRAVEL, TRIGGER_DEG, STOP_DEG, CATCH_IN = 0.043, 18.0, 6.0, 0.002
log = lambda *a: print("ASTEN_POSES", *a, flush=True)  # noqa: E731

# ---- кость места магазина в левой кисти (до подключения grip: правка арматуры сбрасывает ссылки на кости)
arms = bpy.data.objects["FPS_ArmsRig"]
bpy.context.view_layer.objects.active = arms
for o in bpy.context.view_layer.objects:
    o.select_set(o == arms)
bpy.ops.object.mode_set(mode="EDIT")
eb = arms.data.edit_bones.new("mag.L")
src = arms.data.edit_bones["hand.L"]
eb.head, eb.tail, eb.roll = src.head.copy(), src.head + (src.tail - src.head).normalized() * 0.03, src.roll
eb.parent, eb.use_deform = src, False
bpy.ops.object.mode_set(mode="OBJECT")

import grip as G  # noqa: E402
from sdf_grid import Grid  # noqa: E402

S, wr = G.S, G.wr
TW, TWI, AW, AWI = G.TW, G.TWI, G.AW, G.AWI
U = G.GRIP_UP.copy()                                  # ось магазина и рукояти вверх (исходник)
QUAT = ("Weapon_CTRL", "ik_hand.R", "ik_hand.L", "mag.L")
SIDE_BONES = {s: [b.name for b in arms.pose.bones if b.name.endswith("." + s)] for s in ("R", "L")}
FINGERS = {s: [n for n in SIDE_BONES[s] if n.split(".")[0] in ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky")
               and not n.endswith("_end")] for s in ("R", "L")}


def hand_axes(side):
    """Оси кисти в осях её кости (столбцы): e — вдоль (запястье → костяшка среднего), n — ладонная нормаль, c = n × e."""
    rest = arms.data.bones[f"hand.{side}"].matrix_local.to_3x3().transposed()
    n = np.array(rest @ G.PALM_N[side])
    e = np.array(rest @ (arms.data.bones[f"f_middle.01.{side}"].head_local - arms.data.bones[f"hand.{side}"].head_local).normalized())
    e = e - n * (e @ n)
    e /= np.linalg.norm(e)
    return np.stack([e, n, np.cross(n, e)], axis=1)


def place(side, e_src, n_src, anchor, target_mm):
    """Кисть: «вдоль» — по e_src, ладонь смотрит по n_src (исходник); anchor (имя кости — её голова, или точка в осях
    кисти (вдоль, к ладони, поперёк), мм) встаёт в target_mm (исходник). Плечо подаётся, если рука не дотягивается."""
    A = hand_axes(side)
    hwi = np.array(G.hand_world(side).inverted())
    N = np.array(n_src, float)
    N /= np.linalg.norm(N)
    D = np.array(e_src, float)
    D = D - N * (D @ N)
    D /= np.linalg.norm(D)
    R = np.stack([D, N, np.cross(N, D)], axis=1) @ A.T
    if isinstance(anchor, str):
        a = hwi[:3, :3] @ np.array(AW @ arms.pose.bones[anchor].head) + hwi[:3, 3]
    else:
        a = A @ (np.array(anchor, float) / 1000.0)
    m = Matrix(R.tolist()).to_4x4()
    m.translation = Vector(np.array(target_mm, float) / 1000.0 - R @ a)
    reach(side, TW @ m)


def reach(side, world):
    gap = G.set_hand(side, world)
    ua = arms.pose.bones[f"upper_arm.{side}"]
    n = 0
    while gap > 0.0008 and n < 8:
        d = arms.pose.bones[f"ik_hand.{side}"].head - arms.pose.bones[f"hand.{side}"].head
        ua.matrix = Matrix.Translation(d * 1.05) @ ua.matrix
        G.update()
        gap = G.set_hand(side, world)
        n += 1
    return gap


def flex(finger, side, degs):
    """Палец из покоя: сгибы суставов (градусы) вокруг своих осей сгиба."""
    for j, d in enumerate(degs, 1):
        n = f"{finger}.{j:02d}.{side}"
        arms.pose.bones[n].matrix_basis = Matrix.Rotation(math.radians(d), 4, G.flex_axis(n, side))
    G.update()


def thumb_aim(side, to_mm, bend=(16.0, -1.0, 1.0)):
    names = [f"thumb.{j:02d}.{side}" for j in (2, 3)]
    G.reset(names)
    G.aim(names[0], to_mm)
    G.aim(names[1], Vector(to_mm) + Vector(bend))


def cloud(side):
    return np.concatenate([G.SKIN.src_mm(n) for n in SIDE_BONES[side] if n in G.SKIN.local and not n.startswith(("upper_arm", "forearm"))])


def snapshot(names=None):
    return {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones if names is None or pb.name in names}


def restore(snap):
    for n, m in snap.items():
        arms.pose.bones[n].matrix_basis = m
    G.update()


def gun(slide=0.0, trigger=0.0, stop=0.0, catch=0.0, drop=0.0):
    """Подвижные детали пистолета (кости смотрят к дулу: X — вправо, Y — к дулу, Z — вверх)."""
    b = wr.pose.bones
    b["Slide"].location = (0.0, -slide, 0.0)
    b["Trigger"].rotation_euler = (-math.radians(trigger), 0.0, 0.0)
    b["SlideStop"].rotation_euler = (-math.radians(stop), 0.0, 0.0)
    b["MagCatch"].location = (catch, 0.0, 0.0)
    b["Magazine_Control"].location = (0.0, -U.x * drop, -U.z * drop)
    G.update()


def main():
    S.render.fps = 30
    for pb in list(arms.pose.bones) + list(wr.pose.bones):
        pb.rotation_mode = "QUATERNION" if pb.name in QUAT else "XYZ"
    con = wr.pose.bones["Magazine_Control"].constraints.new("COPY_TRANSFORMS")
    con.name = "В левой кисти"
    con.target, con.subtarget, con.influence = arms, "mag.L", 0.0
    act = bpy.data.actions.new(POSES)
    act.use_fake_user = True
    for ob in (arms, wr):
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = act
        ad.action_slot = act.slots.new(id_type="OBJECT", name=ob.name)
    for m in list(S.timeline_markers):
        S.timeline_markers.remove(m)

    def key(frame, label):
        for pb in arms.pose.bones:
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=frame)
        for pb in wr.pose.bones:
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_euler", frame=frame)
            pb.keyframe_insert("scale", frame=frame)
        con.keyframe_insert("influence", frame=frame)
        S.timeline_markers.new(label, frame=frame)

    # ================= правая (черновой хват из grip.py)
    G.right_hand()
    # ================= левая поддерживает: ладонь на левом боку рукояти, пальцы поверх пальцев правой
    G.reset(FINGERS["L"])
    G.EXTRA = cloud("R")
    e_r = TWI.to_3x3() @ (AW.to_3x3() @ (arms.pose.bones["hand.R"].matrix.to_3x3() @ Vector(hand_axes("R")[:, 0].tolist())))
    place("L", (e_r.x, 0.0, e_r.z - 0.10), (-0.22, -1.0, 0.0), "f_middle.01.L", (-3.0, 30.0, -76.0))
    for f in ("f_index", "f_middle", "f_ring", "f_pinky"):
        G.close_finger(f, "L")
    thumb_aim("L", (14.0, 25.0, -25.0))
    G.EXTRA = None
    mag_rest = (wr.matrix_world @ wr.pose.bones["Magazine_Control"].matrix).copy()
    arms.pose.bones["mag.L"].matrix = AWI @ mag_rest
    G.update()
    GRIP = snapshot()
    gun()
    key(1, "ХВАТ: обе руки, указательный вдоль рамки")
    log("хват: правая глубже всего, мм", round(G.SKIN.depth(FINGERS["R"]), 2), "левая (к пистолету)", round(G.SKIN.depth(FINGERS["L"]), 2),
        "IK остаток L, мм", round((arms.pose.bones["hand.L"].head - arms.pose.bones["ik_hand.L"].head).length * 1000, 2))

    # ================= правая: палец на спуске, спуск выжат
    G.index_trigger()
    key(11, "П: указательный на спуске")
    piv = Vector((0.0107, 0.0, -0.0206))
    pad = piv + Matrix.Rotation(math.radians(TRIGGER_DEG), 3, "Y") @ (G.TRIGGER_PAD - piv)
    keep = G.TRIGGER_PAD.copy()
    G.TRIGGER_PAD = pad
    G.index_trigger()
    G.TRIGGER_PAD = keep
    gun(trigger=TRIGGER_DEG)
    key(16, "П: спуск выжат")
    # ================= правая: большой на кнопке магазина / на рычаге задержки / вверх
    restore(GRIP)
    gun(catch=CATCH_IN)
    G.thumb_fit(Vector((-0.0175, 0.0150, -0.0447)), "на кнопке магазина")
    key(21, "П: большой на кнопке магазина")
    restore(GRIP)
    gun(slide=SLIDE_TRAVEL, stop=STOP_DEG)
    G.thumb_fit(Vector((-0.0195, 0.0146, -0.0125)), "на рычаге задержки")
    key(26, "П: большой на рычаге задержки (затвор на задержке)")
    restore(GRIP)
    gun()
    thumb_aim("R", (-52.0, 25.0, 14.0), bend=(4.0, -1.0, 16.0))
    key(31, "П: большой вверх (осмотр)")

    # ================= левая: магазин в кисти (касание — по магазину, он в покое; потом всё вместе вниз на MAG_DROP)
    restore(GRIP)
    G.SURFS[:] = [Grid.load("mag")]
    G.reset(FINGERS["L"])
    place("L", (U.z, 0.0, -U.x), (0.0, -1.0, 0.0), "f_middle.01.L", (-58.0, 24.0, -99.0))
    for f in ("f_index", "f_middle", "f_ring", "f_pinky"):
        G.close_finger(f, "L")
    thumb_aim("L", (-74.0, 4.0, -84.0), bend=(-6.0, -14.0, 2.0))
    arms.pose.bones["mag.L"].matrix = AWI @ mag_rest
    G.update()
    MAG_HOLD = arms.pose.bones["mag.L"].matrix_basis.copy()
    log("магазин в кисти: пальцы к магазину, мм", round(G.SKIN.depth(FINGERS["L"]), 2))
    G.SURFS[:] = [G.WHOLE]
    down = TW.to_3x3() @ (-U * MAG_DROP)
    reach("L", Matrix.Translation(down) @ G.hand_world("L"))
    gun(drop=MAG_DROP)
    LEFT_MAG = snapshot()
    con.influence = 1.0
    key(41, "Л: магазин в кисти (магазин вышел на 55 мм)")
    con.influence = 0.0
    # ================= левая: ладонь досылает магазин (пятка магазина на ладони, пальцы расслаблены)
    restore(GRIP)
    gun()
    G.reset(FINGERS["L"])
    for f, d in (("f_index", (8, 14, 8)), ("f_middle", (12, 18, 10)), ("f_ring", (16, 22, 12)), ("f_pinky", (20, 26, 14))):
        flex(f, "L", d)
    place("L", (0.80, -0.45, 0.39), tuple(U), (62.0, G.PALM_SKIN_N + 2.0, 6.0), (-62.5, 0.0, -128.5))
    arms.pose.bones["mag.L"].matrix_basis = MAG_HOLD
    key(46, "Л: ладонь досылает магазин")
    # ================= левая: щепоть на затворе — большой слева на насечках, указательный через верх на правый борт
    restore(GRIP)
    G.SURFS[:] = [Grid.load("slide")]
    G.reset(FINGERS["L"])
    place("L", (0.42, -0.88, 0.22), (0.10, -0.50, -0.86), "f_index.01.L", (-50.0, 12.0, 25.0))
    G.close_finger("f_index", "L")
    for f, d in (("f_middle", (50, 70, 40)), ("f_ring", (60, 80, 45)), ("f_pinky", (65, 85, 50))):
        flex(f, "L", d)
    thumb_aim("L", (-40.0, 21.5, 1.0), bend=(14.0, -2.0, -3.0))
    arms.pose.bones["mag.L"].matrix_basis = MAG_HOLD
    G.SURFS[:] = [G.WHOLE]
    key(51, "Л: щепоть на затворе (передёргивание)")
    # ================= левая: кисть свободна
    restore(GRIP)
    G.reset(FINGERS["L"])
    for f, d in (("f_index", (10, 18, 10)), ("f_middle", (14, 22, 12)), ("f_ring", (18, 26, 14)), ("f_pinky", (22, 30, 16))):
        flex(f, "L", d)
    arms.pose.bones["mag.L"].matrix_basis = MAG_HOLD
    key(61, "Л: кисть свободна (в пути, у подсумка)")
    # место магазина в кисти одно на все кадры — как на кадре 41
    for fc in [fc for layer in act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves]:
        if 'pose.bones["mag.L"]' in fc.data_path:
            S.frame_set(41)
            v = fc.evaluate(41)
            for kp in fc.keyframe_points:
                kp.co.y = v
                kp.handle_left.y = kp.handle_right.y = v
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    S.frame_start, S.frame_end = 1, 61
    S.frame_set(1)
    txt = bpy.data.texts.new("АСТЕН-919 — позы и клипы (читать)")
    txt.from_string(__doc__)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    log("сохранено", OUT)


main()
