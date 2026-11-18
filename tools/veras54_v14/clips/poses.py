"""ВЕРАС-54 (wpn_ar_01): позы-заготовки рук для клипов — действие VERAS54_Poses (хваты; их правит владелец).

На риге rig.py ставит черновые позы и пишет их ключами по кадрам (у каждого кадра маркер). Клипы (build_clips.py) берут
позы пальцев и места кистей только отсюда; поправленную позу в клипы переносит кнопка панели «ВЕРАС».

   1  ХВАТ — хват владельца на кистях v14 (пробный файл 11.11): всё, и где автомат в кадре
   6  П: указательный вдоль корпуса (с спуска)          46  Л: пальцы раскрываются к магазину
  11  П: спуск выжат (поза владельца, кадр 5 пробы)      51  Л: кисть свободна (в пути)
  16  П: большой на переводчике сверху (АВ → 2 → ОД)     56  Л: магазин у глаз — хват ниже, прорези видно
  21  П: большой под переводчиком (ОД → АВ)              61  Л: большой на кнопке фонаря (фонарь на левой планке)
  26  П: кисть раскрыта (в пути к затвору)               66  Л: держит глушитель (он на дуле)
  31  П: пальцы перед рукояткой затвора                  71 / 76  Л: на рукоятке ВАРН V1 / V2
  36  П: крюк на рукоятке затвора                        81 / 86  Л: на магазине 45 / на барабане 60
  41  Л: на магазине
Положение автомата на кадрах 36, 41, 56, 66 — где он стоит в этих фазах (передёргивание, смена магазина, проверка,
глушитель): клипы берут его отсюда. Пока это умолчания из клипов v13 — правит владелец.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<VERAS54_Rig_v14.blend>" --python-exit-code 1 --python tools/veras54_v14/clips/poses.py -- <выход.blend>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[sys.argv.index("--") + 1])
sys.path.insert(0, str(HERE))
import clip_tools as CT  # noqa: E402
from vcommon import Gun, finger_to, lerp_m  # noqa: E402

SRC = json.loads((Path(bpy.data.filepath).parent / "source_poses.json").read_text(encoding="utf-8"))
log = lambda *a: print("VERAS_POSES", *a, flush=True)  # noqa: E731
S = bpy.context.scene
arms = bpy.data.objects["FPS_ArmsRig"]
glove = bpy.data.objects["FPS_Arms"]
wr = bpy.data.objects["VERAS54_WeaponRig"]
root = bpy.data.objects["VERAS54"]
QUAT = ("Weapon_CTRL", "ik_hand.R", "ik_hand.L", "mag.L", "supp.L")
NAMES = [pb.name for pb in arms.pose.bones]
P = {k: {n: Matrix(v) for n, v in p.items()} for k, p in SRC["poses"].items()}
FING = lambda n: n.split(".")[0] in CT.FINGER  # noqa: E731
R_FING = [n for n in NAMES if FING(n) and n.endswith(".R")]
L_FING = [n for n in NAMES if FING(n) and n.endswith(".L")]
R_INDEX = [n for n in NAMES if n.startswith("f_index") and n.endswith(".R")]
R_THUMB = [n for n in NAMES if n.startswith("thumb") and n.endswith(".R")]
L_SIDE = [n for n in NAMES if n.endswith(".L") and n not in ("mag.L", "supp.L")]
R_SIDE = [n for n in NAMES if n.endswith(".R")]
I4 = Matrix.Identity(4)
# положения автомата по умолчанию — из клипов v13 (крен, тангаж, рыскание, x, y, z)
GUN_DEFAULT = dict(mag=(-34, -9, 6, 0.06, 0.05, 0.07),        # смена магазина: шахтой к левой руке
                   hook=(24, -4, -3, 0.0, 0.03, 0.05),         # передёргивание: правым боком (рукоятка затвора) к глазам
                   check=(-16, -2, 2, 0.01, 0.02, -0.02),      # проверка магазина: автомат пониже, магазин у глаз
                   supp=(0, 15, 50, 0.10, 0.12, -0.03))        # глушитель: дуло к середине кадра и чуть вниз, ближе


def update():
    bpy.context.view_layer.update()


def pose_from(base, over=None, names=None):
    """Поза: base, поверх — кости over (все или из списка names)."""
    out = {n: base.get(n, I4).copy() for n in NAMES}
    if over is not None:
        for n in (names if names is not None else over):
            if n in over:
                out[n] = over[n].copy()
    return out


def apply(pose):
    for n, m in pose.items():
        arms.pose.bones[n].matrix_basis = m
    update()


def snapshot():
    return {n: arms.pose.bones[n].matrix_basis.copy() for n in NAMES}


def shoulders_from(pose, src):
    """Плечи и локти — как в хвате владельца (src), остальное — из позы."""
    for n in ("upper_arm.L", "upper_arm.R", "pole.L", "pole.R", "FPS_Root"):
        if n in src:
            pose[n] = src[n].copy()
    return pose


def reach(pose, side, limit=0.25):
    """Рука не дотягивается до цели — плечо подаётся к кисти (не дальше limit, м). Поза дополняется плечом."""
    apply(pose)
    ua = arms.pose.bones[f"upper_arm.{side}"]
    moved = Vector()
    for _ in range(10):
        d = arms.pose.bones[f"ik_hand.{side}"].head - arms.pose.bones[f"hand.{side}"].head
        if d.length < 0.0008 or moved.length > limit:
            break
        ua.matrix = Matrix.Translation(d * 1.05) @ ua.matrix
        moved += d * 1.05
        update()
    pose[f"upper_arm.{side}"] = ua.matrix_basis.copy()
    gap = (arms.pose.bones[f"ik_hand.{side}"].head - arms.pose.bones[f"hand.{side}"].head).length * 1000
    return pose, moved.length * 1000, gap


def aim_gun(G, point_local, ahead, right, up, axis_cam, up_cam=(0.0, 0.0, 1.0)):
    """Сдвиг автомата в мире (для Gun.basis base=…), при котором точка автомата point_local (оси рига оружия) встаёт
    перед глазами (ahead м по взгляду, right / up — вбок и вверх), ствол смотрит по axis_cam (вправо, вперёд, вверх в
    осях камеры), верх автомата — по up_cam."""
    cam = bpy.data.objects["FPS • Camera"].matrix_world
    eye = cam.translation.copy()
    fwd = -(cam.to_3x3() @ Vector((0, 0, 1))).normalized()
    upv = (cam.to_3x3() @ Vector((0, 1, 0))).normalized()
    rt = fwd.cross(upv).normalized()

    def in_cam(v):
        return (rt * v[0] + fwd * v[1] + upv * v[2]).normalized()

    def frame(a, u):
        u = (u - a * a.dot(u)).normalized()
        return Matrix((a, u, a.cross(u))).transposed()

    WR = G.WR_REST
    p0 = WR @ Vector(point_local)
    a0 = (WR.to_3x3() @ Vector((1, 0, 0))).normalized()
    u0 = (WR.to_3x3() @ Vector((0, 0, 1))).normalized()
    R = frame(in_cam(axis_cam), in_cam(up_cam)) @ frame(a0, u0).transposed()
    target = eye + fwd * ahead + rt * right + upv * up
    return Matrix.Translation(target - R @ p0) @ R.to_4x4()


def gun_parts(supp_on=False, hide_muzzle=False):
    b = wr.pose.bones
    for pb in b:
        pb.matrix_basis = I4.copy()
    for n in ("SpareMag", "JamCase"):
        b[n].scale = (0.001,) * 3
    sc = b["Suppressor_Control"]
    if supp_on:                                      # глушитель на дуле: кость хранения → к срезу ствола
        rest = wr.data.bones["Suppressor_Control"].matrix_local
        tgt = Matrix.Translation(wr.data.bones["Socket_Muzzle"].head_local - rest.translation) @ rest
        sc.matrix = tgt
    else:
        sc.scale = (0.001,) * 3
    if hide_muzzle:
        b["MuzzleAttachment"].scale = (0.001,) * 3
    update()


def main():
    S.render.fps = 30
    for pb in list(arms.pose.bones):
        pb.rotation_mode = "QUATERNION" if pb.name in QUAT else "XYZ"
    for pb in wr.pose.bones:
        pb.rotation_mode = "XYZ"
    grip = pose_from(P["grip"])
    gun_parts()
    apply(grip)
    G = Gun(arms, grip["Weapon_CTRL"], SRC["points"]["grip"], wr)
    poses = {"grip": grip}
    # ---- правая: указательный вдоль корпуса, спуск выжат
    frame = pose_from(grip)
    for n in R_INDEX:
        frame[n] = lerp_m(grip[n], I4, 0.7)
    poses["frame"] = frame
    poses["pressed"] = pose_from(grip, P["pressed"], R_INDEX)
    # ---- правая: крюк на рукоятке затвора (со старых рук, пересчёт), пальцы перед ним, кисть раскрыта
    hook = shoulders_from(pose_from(grip, P["file"], R_SIDE), grip)
    hook["Weapon_CTRL"] = G.basis(GUN_DEFAULT["hook"])
    hook, mv, gap = reach(hook, "R")
    log(f"поза hook: правое плечо подано к кисти на {mv:.0f} мм, остаток {gap:.1f} мм")
    poses["hook"] = hook
    hp = pose_from(hook)                              # пальцы перед рукояткой — автомат и кисть как в «крюке»
    for n in R_FING:
        hp[n] = lerp_m(hook[n], I4, 0.35)
    poses["hook_pre"] = hp
    ro = pose_from(grip)
    for n in R_FING:
        ro[n] = lerp_m(grip[n], I4, 0.6)
    poses["r_open"] = ro
    # ---- правая: большой на переводчике (кисть у правой стенки коробки, пальцы приоткрыты; подушечка — на полочку)
    to_veras = root.matrix_world.inverted()

    def shelf(mode_from, down):
        root["Fire mode"] = float(mode_from)
        root["Selector from mode"] = float(mode_from)
        root["Selector blend"] = 1.0
        root.update_tag()
        update()
        dg = bpy.context.evaluated_depsgraph_get()
        ob = bpy.data.objects["Selector_Steel"].evaluated_get(dg)
        me = ob.to_mesh()
        pts = [ob.matrix_world @ v.co for v in me.vertices]
        ob.to_mesh_clear()
        sh = [p for p in pts if 0.134 <= (to_veras @ p).x <= 0.152]
        c = to_veras @ (sum(sh, Vector()) / len(sh))
        zs = [(to_veras @ p).z for p in sh]
        c.z = (max(zs) + 0.007) if down else (min(zs) - 0.007)
        c.y -= 0.006
        return root.matrix_world @ c

    for name, mode, down in (("sel_down", 1, True), ("sel_up", 2, False)):
        apply(grip)
        p = pose_from(grip)
        ikR = arms.pose.bones["ik_hand.R"]
        A = arms.matrix_world.inverted() @ root.matrix_world
        m = ikR.matrix.copy()
        m.translation += A.to_3x3() @ Vector((0.075, -0.022, 0.035 if down else 0.025))
        ikR.matrix = m
        p["ik_hand.R"] = ikR.matrix_basis.copy()
        for n in R_FING:
            if not n.startswith("thumb"):
                p[n] = lerp_m(grip[n], I4, 0.15)
        apply(p)
        miss = finger_to(arms, glove, "R", "thumb", shelf(mode, down))
        p.update({n: arms.pose.bones[n].matrix_basis.copy() for n in R_THUMB})
        poses[name] = p
        log(f"поза {name}: подушечка большого на полочке переводчика, промах {miss:.1f} мм")
    root["Fire mode"], root["Selector from mode"], root["Selector blend"] = 1.0, 1.0, 1.0
    # ---- левая: на магазине, пальцы раскрываются, свободна, проверка
    mag = shoulders_from(pose_from(grip, P["file"], L_SIDE), grip)
    mag["Weapon_CTRL"] = G.basis(GUN_DEFAULT["mag"])
    poses["mag"] = mag
    pre = pose_from(mag)
    for n in L_FING:
        pre[n] = lerp_m(mag[n], I4, 0.25)
    poses["pre"] = pre
    free = pose_from(grip)
    for n in L_FING:
        free[n] = lerp_m(lerp_m(grip[n], mag[n], 0.5), I4, 0.55)
    poses["free"] = free
    chk = shoulders_from(pose_from(grip, P["check"], L_SIDE), grip)
    chk["Weapon_CTRL"] = G.basis(GUN_DEFAULT["check"])
    poses["check"] = chk
    # ---- левая: большой на кнопке фонаря (хвостовик фонаря на левой планке), кисть на цевье как в хвате
    apply(grip)
    btn = wr.matrix_world @ (Vector(SRC["points"]["light_button"]) - Vector((0.006, 0.0, 0.0)))
    miss = finger_to(arms, glove, "L", "thumb", btn)
    light = pose_from(grip)
    ikL = arms.pose.bones["ik_hand.L"]
    for _ in range(3):                                # кисть немного к кнопке, если большой не достаёт
        if miss < 4.0:
            break
        pad = finger_pad = None
        from vcommon import pad_world
        pad = pad_world(arms, glove, "thumb.03.L")
        m = ikL.matrix.copy()
        m.translation += arms.matrix_world.inverted().to_3x3() @ ((btn - pad) * 0.8)
        ikL.matrix = m
        update()
        miss = finger_to(arms, glove, "L", "thumb", btn)
    light["ik_hand.L"] = ikL.matrix_basis.copy()
    light.update({n: arms.pose.bones[n].matrix_basis.copy() for n in NAMES if n.startswith("thumb") and n.endswith(".L")})
    poses["light"] = light
    log(f"поза light: большой левой на кнопке фонаря, промах {miss:.1f} мм")
    # ---- левая: рукоятки ВАРН, магазины 45 / 60 (со старых рук, пересчёт)
    for k in ("varn_v1", "varn_v2", "mag45", "drum60"):
        poses[k] = shoulders_from(pose_from(grip, P[k], L_SIDE), grip)
    # ---- левая: держит глушитель — хват рукоятки ВАРН V1 перенесён на глушитель (ось рукоятки → ось глушителя,
    # ладонь сзади рукоятки → ладонь слева глушителя), пальцы раскрыты под его толщину
    gun_parts(supp_on=True, hide_muzzle=True)
    supp = pose_from(poses["varn_v1"])
    apply(supp)
    fg = bpy.data.objects["Foregrip • varn_v1"]
    ik = arms.pose.bones["ik_hand.L"]
    H = arms.matrix_world @ ik.matrix
    rel = fg.matrix_world.inverted() @ H
    Q = Matrix(((0, 0, -1), (-1, 0, 0), (0, 1, 0))).to_4x4()       # столбцы: оси рукоятки → оси глушителя
    sock = wr.data.bones["Socket_Muzzle"].head_local
    Sw = wr.matrix_world @ Matrix.Translation(sock + Vector((0.045, 0.0075, 0.0))) @ Q
    want_ik = Sw @ rel
    ik.matrix = arms.matrix_world.inverted() @ want_ik
    supp["ik_hand.L"] = ik.matrix_basis.copy()
    for n in L_FING:
        supp[n] = lerp_m(poses["varn_v1"][n], I4, 0.25)
    # автомат: дуло с глушителем перед глазами чуть левее середины, ствол влево-вперёд и вниз
    sock_l = wr.data.bones["Socket_Muzzle"].head_local
    supp["Weapon_CTRL"] = G.basis((0, 0, 0, 0, 0, 0), aim_gun(G, sock_l + Vector((0.09, 0, 0)), 0.42, -0.06, -0.11,
                                                          (-0.75, 0.55, -0.30)))
    supp, mv, gap = reach(supp, "L", limit=0.15)
    log(f"поза supp: левое плечо подано к кисти на {mv:.0f} мм, остаток {gap:.1f} мм")
    poses["supp"] = supp
    gun_parts()

    # ---------------------------------------------------------------- ключи
    con_m = wr.pose.bones["Magazine_Control"].constraints["В левой кисти"]
    con_s = wr.pose.bones["Suppressor_Control"].constraints["В левой кисти"]
    act = bpy.data.actions.new(CT.POSES)
    act.use_fake_user = True
    for ob in (arms, wr):
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = act
        ad.action_slot = act.slots.new(id_type="OBJECT", name=ob.name)
    for m in list(S.timeline_markers):
        S.timeline_markers.remove(m)
    for name, f in CT.POSE_FRAMES.items():
        gun_parts(supp_on=name == "supp", hide_muzzle=name == "supp")
        for n in NAMES:
            arms.pose.bones[n].matrix_basis = poses[name][n]
        for pb in arms.pose.bones:
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert(CT.rot_prop(pb), frame=f)
        for pb in wr.pose.bones:
            for prop in ("location", "rotation_euler", "scale"):
                pb.keyframe_insert(prop, frame=f)
        for c in (con_m, con_s):
            c.influence = 0.0
            c.keyframe_insert("influence", frame=f)
        S.timeline_markers.new(f"ПОЗА {CT.POSE_RU[name]}", frame=f)
    for layer in act.layers:
        for st in layer.strips:
            for bag in st.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"     # кадр позы держится до следующей позы — без смешения
    S.frame_start, S.frame_end = 1, max(CT.POSE_FRAMES.values())
    # место магазина и глушителя в кисти — с кадров поз
    CT.tidy_poses(bpy.context, arms, wr, act, log)
    # дотягиваются ли руки до целей на кадрах поз
    for name, f in CT.POSE_FRAMES.items():
        S.frame_set(f)
        gap = {s: (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000 for s in ("L", "R")}
        if max(gap.values()) > 1.0:
            log(f"поза {name} (кадр {f}): рука не дотягивается, мм: L {gap['L']:.0f}, R {gap['R']:.0f}")
    S.frame_set(1)
    root["clip_points"] = json.dumps(SRC["points"])        # точки автомата для сборщика клипов (оси рига оружия, м)
    txt = bpy.data.texts.get("ВЕРАС-54 — позы и клипы (читать)") or bpy.data.texts.new("ВЕРАС-54 — позы и клипы (читать)")
    txt.from_string(__doc__)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    log("сохранено", OUT)


main()
