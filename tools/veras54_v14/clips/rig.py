"""ВЕРАС-54 (wpn_ar_01): риг для клипов рук на кистях v14 — по образцу tools/asten919/clips/rig.py.

Основа — риг v13 («Игровая версия/Риг v13/VERAS54_Rig_v13.blend»: руки FPS_ArmsRig с хватом владельца, игровая сетка
автомата на костях VERAS54_WeaponRig, свойства VERAS54 с драйверами деталей). Руки переводятся на кисти мастера v14 прямо
в файле (tools/fps_hands_fix.py — та же правка, которой сделан мастер FPS_Arms_v14) и сверяются с мастером.

Позы со старых рук (захват магазина, крюк на рукоятке затвора, проверка, рукоятки ВАРН V1 / V2, магазины 45 / 60)
пересчитываются под v14: у кисти и пальцев — тот же поворот от покоя (B' = C⁻¹·B·C, C = R_old⁻¹·R_new), сдвиги — в осях
новой кости и меньше, цель кисти сдвигается так, чтобы середина ладони осталась на месте. Хват владельца на v14
(пробный файл 11.11, кадр 1 — хват, кадр 5 — указательный выжал спуск) берётся как есть. Всё — в source_poses.json рядом
с выходом; по нему poses.py ставит позы.

Добавляется: кости mag.L и supp.L в левой кисти (место магазина и глушителя в руке), старый магазин быстрой перезарядки
(кость SpareMag) и гильза задержки (JamCase) — «выключены» масштабом 0,001; рукоятки ВАРН V1 / V2, магазины 45 / 60 и их
копии на SpareMag, глушитель на кости Suppressor_Control, фонарь ДОЗОР Ф-1 в креплении ДОЗОР-П на левой планке.
Варианты — коллекциями («Рукоятка ВАРН V1», «Магазин 45» …), видимость переключает панель.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/veras54_v14/clips/rig.py [-- <выход.blend>]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/veras54_v13/clips"))
import fps_hands_fix as hands_fix  # noqa: E402

LIB = Path("E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия")
SRC = LIB / "Риг v13/VERAS54_Rig_v13.blend"
V02 = LIB / "Клипы v02 (Claude)"                        # check_grip_pose.json, grip_varn_v1|v2_pose.json (позы владельца ВАРН)
GRIPS45 = LIB / "Хваты магазинов 45 и 60"
PILOT = ROOT / "_asset_src/veras54_v14_pilot/VERAS54_FPS_v14_Pilot.blend"
PILOT_ACTION = "VERAS54_V14_Хват_и_указательный"
MASTER = Path("E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend")
ATT_SRC = ROOT / "_asset_src/veras_attachments"
ATT_TEX = ROOT / "assets/models/attachments"
DOZOR = Path("E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж/models/DOZOR_Game_v01.blend")
OUT = ROOT / "_asset_src/veras54_v14/anim/VERAS54_Rig_v14.blend"
PALM_K, FINGER_K = 0.72, 0.74                          # кисти v14 против прежних (ладонь × 0,70 / 0,76, пальцы × 0,74)
HAND_PART = ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky", "hand")
# точки v13 в мире при прежнем хвате (tools/veras54_v13/clips/build_clips.py, rig_common.py) → в оси рига оружия
WORLD_V13 = dict(pivot=(-0.14, -0.463, 1.675),          # передний зацеп магазина — ось качка
                 grip=(-0.14, -0.323, 1.635))           # пистолетная рукоятка — ось наклонов автомата
LEFT_RAIL = Vector((0.393, 0.031, 0.029))               # левая боковая планка (data/weapons.json models.veras54.sockets.side_left)
log = lambda *a: print("VERAS_RIG", *a, flush=True)    # noqa: E731


def update():
    bpy.context.view_layer.update()


def M(m):
    return [[round(v, 7) for v in row] for row in m]


def basis_of(arms):
    return {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}


def apply(arms, pose):
    for n, m in pose.items():
        if n in arms.pose.bones:
            arms.pose.bones[n].matrix_basis = m
    update()


def action_pose(act, frame, bones):
    """Поза по кривым действия на кадре (без назначения действия): {кость: matrix_basis}."""
    cv = {}
    for layer in act.layers:
        for st in layer.strips:
            for bag in st.channelbags:
                for fc in bag.fcurves:
                    if fc.data_path.startswith('pose.bones["'):
                        cv[(fc.data_path.split('"')[1], fc.data_path.rsplit(".", 1)[1], fc.array_index)] = fc.evaluate(frame)
    out = {}
    for n in bones:
        if not any(k[0] == n for k in cv):
            continue
        loc = Vector([cv.get((n, "location", i), 0.0) for i in range(3)])
        if (n, "rotation_quaternion", 0) in cv:
            from mathutils import Quaternion
            rot = Quaternion([cv.get((n, "rotation_quaternion", i), 1.0 if i == 0 else 0.0) for i in range(4)]).normalized()
        else:
            from mathutils import Euler
            rot = Euler([cv.get((n, "rotation_euler", i), 0.0) for i in range(3)], "XYZ")
        sc = Vector([cv.get((n, "scale", i), 1.0) for i in range(3)])
        out[n] = Matrix.LocRotScale(loc, rot, sc)
    return out


def appended_arms_pose(path):
    """Поза рук из чужого файла (хваты магазинов 45 / 60): объект рук добавляется, поза снимается, всё добавленное — прочь."""
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = ["FPS_ArmsRig"]
    ob = dst.objects[0]
    pose = {pb.name: pb.matrix_basis.copy() for pb in ob.pose.bones}
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o, do_unlink=True)
    return pose


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else OUT
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    S = bpy.context.scene
    S.name = "ВЕРАС-54 — клипы рук"
    S.render.fps = 30
    arms = bpy.data.objects["FPS_ArmsRig"]
    mesh = bpy.data.objects["FPS_Arms"]
    wr = bpy.data.objects["VERAS54_WeaponRig"]
    root = bpy.data.objects["VERAS54"]
    magob = bpy.data.objects["Magazine"]
    for o in (arms, wr, root, magob):
        if o.animation_data:
            log("в файле у", o.name, "назначено действие", o.animation_data.action.name if o.animation_data.action else None, "— снято")
            o.animation_data.action = None
    for pb in list(arms.pose.bones) + list(wr.pose.bones):
        pb.rotation_mode = "XYZ"
    names = [pb.name for pb in arms.pose.bones]

    # ---------------------------------------------------------------- позы на прежних руках
    FILE = basis_of(arms)                                # левая — на магазине, правая — крюком на рукоятке затвора
    READY = action_pose(bpy.data.actions["VERAS54_Grip_Manual_v02"], 1, names)
    READY = {n: READY.get(n, Matrix.Identity(4)) for n in names}
    src = {"ready_old": READY, "file": FILE}
    chk = {n: Matrix(v) for n, v in json.loads((V02 / "check_grip_pose.json").read_text(encoding="utf-8")).items()}
    src["check"] = dict(READY, **chk)
    for gid in ("varn_v1", "varn_v2"):
        g = {n: Matrix(v) for n, v in json.loads((V02 / f"grip_{gid}_pose.json").read_text(encoding="utf-8")).items()}
        src[gid] = dict(READY, **g)
    for key, fn in (("mag45", "VERAS54_Grip_Mag45_v01.blend"), ("drum60", "VERAS54_Grip_Drum60_v01.blend")):
        src[key] = appended_arms_pose(GRIPS45 / fn)
    old_rest = {b.name: b.matrix_local.copy() for b in arms.data.bones}

    def anchors():
        out_ = {}
        for s in ("L", "R"):
            hand = arms.data.bones[f"hand.{s}"]
            knuckle = arms.data.bones[f"f_middle.01.{s}"].head_local
            out_[s] = hand.matrix_local.inverted() @ hand.head_local.lerp(knuckle, 0.6)
        return out_

    old_anchor = anchors()
    hand_state = {}
    for k, pose in src.items():
        apply(arms, pose)
        hand_state[k] = {s: (arms.pose.bones[f"ik_hand.{s}"].matrix.copy(), arms.pose.bones[f"hand.{s}"].matrix.to_3x3().copy())
                         for s in ("L", "R")}

    # точки v13 в оси рига оружия — при прежнем хвате
    apply(arms, READY)
    WRI = wr.matrix_world.inverted()
    points = {k: list(WRI @ Vector(v)) for k, v in WORLD_V13.items()}

    # ---------------------------------------------------------------- добавки на оружие (пока оно стоит в прежнем хвате)
    import rig_common as rc
    coll_main = bpy.data.collections.get("VERAS54 v13 • игровая сетка") or S.collection

    def coll(name):
        c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if c.name not in S.collection.children:
            S.collection.children.link(c)
        return c

    def move_to(o, c):
        for old in list(o.users_collection):
            old.objects.unlink(o)
        c.objects.link(o)

    # рукоятки ВАРН V1 / V2 на нижней планке
    for gid, label in (("varn_v1", "Рукоятка ВАРН V1"), ("varn_v2", "Рукоятка ВАРН V2")):
        ob = rc.add_grip(gid)
        ob.name = "Foregrip • " + gid
        ob["variant"] = "grip:" + gid
        move_to(ob, coll(label))
    # штатный магазин — своей коллекцией
    c30 = coll("Магазин 30 (штатный)")

    def under(ob, top):
        q = ob.parent
        while q is not None:
            if q == top:
                return True
            q = q.parent
        return False

    for o in list(bpy.data.objects):
        if o.type == "MESH" and (under(o, magob) or o.name == "Magazine_Follower"):
            o["variant"] = "mag:30"
            move_to(o, c30)
    # магазины 45 / 60 из файлов хватов: сетки под пустышкой Magazine (то же место крепления)
    for key, fn, label, prefix in (("45", "VERAS54_Grip_Mag45_v01.blend", "Магазин 45", "Магазин 45 • "),
                                   ("60", "VERAS54_Grip_Drum60_v01.blend", "Барабан 60", "Барабан 60 • ")):
        before = set(bpy.data.objects)
        with bpy.data.libraries.load(str(GRIPS45 / fn), link=False) as (s_, d_):
            d_.objects = [n for n in s_.objects if n.startswith(("Magazine_Body", "Magazine_Follower", "Magazine • ")) or n == "Magazine"]
        new = set(bpy.data.objects) - before
        src_mag = next(o for o in new if o.name.startswith("Magazine") and o.type == "EMPTY" and o.name.split(".")[0] == "Magazine")
        c = coll(label)
        kept = 0
        for o in new:
            if o.type != "MESH":
                continue
            local = src_mag.matrix_world.inverted() @ o.matrix_world
            o.name = prefix + o.name.split(".")[0].replace("Magazine • ", "").replace("Magazine_", "")
            o.parent = magob
            o.parent_type = "OBJECT"
            o.matrix_parent_inverse = Matrix.Identity(4)
            update()
            o.matrix_world = magob.matrix_world @ local
            o["variant"] = "mag:" + key
            o.animation_data_clear()
            move_to(o, c)
            kept += 1
        for o in list(new):
            if o.type != "MESH":
                bpy.data.objects.remove(o, do_unlink=True)
        log(label, "сеток", kept)
        c.hide_viewport = c.hide_render = True
    # гильза задержки (в окне выброса), старый магазин быстрой перезарядки
    case_pb = rc.add_jam_case(wr)
    case_ob = bpy.data.objects["JamCase • stuck case"]
    move_to(case_ob, coll("Гильза задержки"))
    bpy.context.view_layer.objects.active = wr
    bpy.ops.object.mode_set(mode="EDIT")
    srcb = wr.data.edit_bones["Magazine_Control"]
    eb = wr.data.edit_bones.new("SpareMag")
    eb.head, eb.tail, eb.roll = srcb.head.copy(), srcb.tail.copy(), srcb.roll
    eb.parent = wr.data.edit_bones["WeaponRoot"]
    eb.use_deform = False
    er = wr.data.edit_bones.new("SpareMag_Rounds")          # патроны старого магазина — отдельно (пустой магазин — масштаб 0)
    er.head, er.tail, er.roll = srcb.head.copy(), srcb.tail.copy(), srcb.roll
    er.parent, er.use_deform = eb, False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in wr.pose.bones:
        pb.rotation_mode = "XYZ"
    update()
    spare_coll = {"30": coll("Старый магазин 30"), "45": coll("Старый магазин 45"), "60": coll("Старый магазин 60")}
    for o in [o for o in bpy.data.objects if o.type == "MESH" and str(o.get("variant", "")).startswith("mag:")]:
        key = o["variant"][4:]
        n = o.name
        if ("loaded" in n or "case" in n or "projectile" in n) and n.rsplit(" ", 1)[-1] not in ("1", "2"):
            continue
        world = o.matrix_world.copy()
        cp = o.copy()
        cp.animation_data_clear()                       # без драйверов «Патронов в магазине»
        cp.name = "Старый " + key + " • " + n
        cp["variant"] = "mag:" + key
        spare_coll[key].objects.link(cp)
        cp.parent = wr
        cp.parent_type = "BONE"
        cp.parent_bone = "SpareMag_Rounds" if ("loaded" in n or "case" in n or "projectile" in n) else "SpareMag"
        update()
        cp.matrix_world = world
        cp.hide_viewport = cp.hide_render = False
    for k_, c in spare_coll.items():
        c.hide_viewport = c.hide_render = k_ != "30"
    # глушитель — на кости Suppressor_Control (в покое — под автоматом; в клипах его несёт левая и накручивает)
    with bpy.data.libraries.load(str(ATT_SRC / "supp_veras_low.blend"), link=False) as (s_, d_):
        d_.objects = ["Body"]
    sup = d_.objects[0]
    sup.name = "Глушитель • supp_veras"
    mat = bpy.data.materials.new("Глушитель • supp_veras")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for ch, sock in (("base_color", "Base Color"), ("roughness", "Roughness"), ("metallic", "Metallic"), ("normal", "Normal")):
        p = ATT_TEX / "supp_veras" / f"supp_veras_100_{ch}.png"
        if not p.exists():
            continue
        t = mat.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(p))
        t.image.colorspace_settings.name = "sRGB" if ch == "base_color" else "Non-Color"
        if ch == "normal":
            nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            mat.node_tree.links.new(t.outputs["Color"], nm.inputs["Color"])
            mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs[sock])
        else:
            mat.node_tree.links.new(t.outputs["Color"], bsdf.inputs[sock])
    sup.data.materials.clear()
    sup.data.materials.append(mat)
    move_to(sup, coll("Глушитель"))
    sup.parent = wr
    sup.parent_type = "BONE"
    sup.parent_bone = "SuppressorAttachment"
    update()
    sup.matrix_world = wr.matrix_world @ Matrix.Translation(wr.pose.bones["SuppressorAttachment"].head)
    # фонарь ДОЗОР Ф-1 в креплении ДОЗОР-П на левой планке (кнопка — хвостовая; её жмёт большой левой)
    lc = coll("Фонарь ДОЗОР (левая планка)")
    # игровой файл фонаря (DOZOR_Game_v01.blend): +Z — луч, +Y — от планки, X — поперёк → оси рига оружия
    R = Matrix(((0, 0, 1), (0, 1, 0), (-1, 0, 0))).to_4x4()
    want = ("DOZOR_F1", "DOZOR_P", "Bezel", "Clip", "Housing", "Lens", "ModeButton", "Optics", "PrimaryButton", "TailCap",
            "CapHinge", "ClampPadNegative", "ClampPadPositive", "LockScrew", "MountBody", "MovingJaw", "FlashlightSocket")
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(str(DOZOR), link=False) as (s_, d_):
        d_.objects = [n for n in s_.objects if n in want]
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        move_to(o, lc)
    P, F1 = bpy.data.objects["DOZOR_P"], bpy.data.objects["DOZOR_F1"]
    for o in (P, F1):
        o.parent = wr
        o.parent_type = "BONE"
        o.parent_bone = "WeaponRoot"
        o.matrix_parent_inverse = Matrix.Identity(4)
    update()
    P.matrix_world = wr.matrix_world @ Matrix.Translation(LEFT_RAIL) @ R
    update()
    F1.matrix_world = P.matrix_world @ Matrix.Translation(Vector((0.0, 0.024, 0.0)))
    log("фонарь: объектов", len(new))
    update()
    btn = bpy.data.objects.get("TailCap")
    if btn is not None:
        dg = bpy.context.evaluated_depsgraph_get()
        e = btn.evaluated_get(dg)
        pts = [e.matrix_world @ Vector(c) for c in e.bound_box]
        # кнопка — задний торец хвостовика: самая задняя по оси оружия точка, середина торца
        WR = wr.matrix_world
        loc = [WR.inverted() @ p for p in pts]
        xmin = min(p.x for p in loc)
        c = sum(loc, Vector()) / 8
        points["light_button"] = [xmin, c.y, c.z]
        log("кнопка фонаря (оси рига оружия), мм", [round(v * 1000, 1) for v in points["light_button"]])

    # ---------------------------------------------------------------- руки → кисти v14
    for o in (arms, wr):
        for pb in o.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    update()
    before, after = hands_fix.fix_objects(arms, mesh)
    log("кисть до / после, см", before.get("R"), after.get("R"))
    with bpy.data.libraries.load(str(MASTER), link=False) as (s_, d_):
        d_.objects = ["FPS_ArmsRig", "FPS_Arms"]
    mr, mm = d_.objects
    rest_d = max(abs(a - b) for bn in arms.data.bones for ra, rb in zip(bn.matrix_local, mr.data.bones[bn.name].matrix_local)
                 for a, b in zip(ra, rb))
    mesh_d = max((a.co - b.co).length for a, b in zip(mesh.data.vertices, mm.data.vertices))
    bpy.data.objects.remove(mm, do_unlink=True)
    bpy.data.objects.remove(mr, do_unlink=True)
    assert rest_d < 1e-5 and mesh_d < 1e-5, (rest_d, mesh_d)
    log("кисти совпадают с мастером v14: покой костей", f"{rest_d:.1e}", "сетка", f"{mesh_d:.1e}")
    new_anchor = anchors()

    def C(n):
        return old_rest[n].to_3x3().normalized().transposed() @ arms.data.bones[n].matrix_local.to_3x3().normalized()

    worst = max((math.degrees(C(n).to_quaternion().angle), n) for n in names if n.split(".")[0] in HAND_PART)
    log("покой v14 против прежних рук: наибольшая разница осей, °", round(worst[0], 1), worst[1])

    def convert(key):
        pose = src[key]
        new = {}
        for n in names:
            m = pose.get(n, Matrix.Identity(4))
            if n.split(".")[0] in HAND_PART:
                c = C(n)
                r = (c.transposed() @ m.to_3x3() @ c).to_4x4()
                t = c.transposed() @ m.translation
                r.translation = t * (PALM_K if n.startswith(("palm", "hand")) else FINGER_K)
                new[n] = r
            else:
                new[n] = m.copy()
        apply(arms, new)
        for s in ("L", "R"):
            ik_old, rot_old = hand_state[key][s]
            want = ik_old.copy()
            want.translation += rot_old @ (old_anchor[s] - new_anchor[s])
            pb = arms.pose.bones[f"ik_hand.{s}"]
            pb.matrix = want
            new[f"ik_hand.{s}"] = pb.matrix_basis.copy()
        return new

    poses = {k: convert(k) for k in src}
    # хват владельца на v14 (пробный файл): кадр 1 — хват, кадр 5 — указательный выжал спуск
    with bpy.data.libraries.load(str(PILOT), link=False) as (s_, d_):
        d_.actions = [PILOT_ACTION]
    pa = d_.actions[0]
    g1 = action_pose(pa, 1, names)
    g5 = action_pose(pa, 5, names)
    poses["grip"] = {n: g1.get(n, poses["ready_old"][n]) for n in names}
    poses["pressed"] = {n: g5.get(n, poses["grip"][n]) for n in names}
    bpy.data.actions.remove(pa)
    log("хват владельца v14: костей", len(g1), "; спуск выжат (кадр 5)", len(g5))

    # кости места магазина и глушителя в левой кисти
    bpy.context.view_layer.objects.active = arms
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arms)
    bpy.ops.object.mode_set(mode="EDIT")
    for bn in ("mag.L", "supp.L"):
        e = arms.data.edit_bones.new(bn)
        h = arms.data.edit_bones["hand.L"]
        e.head, e.tail, e.roll = h.head.copy(), h.head + (h.tail - h.head).normalized() * 0.03, h.roll
        e.parent, e.use_deform = h, False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arms.pose.bones:
        pb.rotation_mode = "XYZ"
    for bn, target in (("Magazine_Control", "mag.L"), ("Suppressor_Control", "supp.L"), ("SpareMag", "mag.L")):
        con = wr.pose.bones[bn].constraints.new("COPY_TRANSFORMS")
        con.name = "В левой кисти"
        con.target, con.subtarget, con.influence = arms, target, 0.0
    # в покое не видны: старый магазин, гильза задержки, глушитель (в клипах «включаются» масштабом)
    for bn in ("SpareMag", "JamCase", "Suppressor_Control"):
        wr.pose.bones[bn].scale = (0.001, 0.001, 0.001)
    # переводчик: четвёртое положение — «2» (очередь по 2) между АВ и ОД; в свойстве «Fire mode» это 3
    sel = next(d for d in wr.animation_data.drivers if d.data_path == 'pose.bones["Selector"].rotation_euler')
    ang = lambda v: f"(-0.0872665 if {v}<.5 else (0.0 if {v}<1.5 else (0.1370083 if {v}<2.5 else 0.0684169)))"  # noqa: E731
    sel.driver.expression = f"{ang('previous')}*(1-(min(max(blend,0),1)))+{ang('mode')}*(min(max(blend,0),1))"
    root["fire_modes"] = "Fire mode: 0 — предохранитель, 1 — АВ, 2 — ОД, 3 — «2» (очередь по 2)"
    apply(arms, poses["grip"])

    rec = dict(source=str(SRC), pilot=str(PILOT), points=points,
               poses={k: {n: M(m) for n, m in p.items()} for k, p in poses.items()},
               note="позы — matrix_basis на кистях v14; ready_old / file / check / varn_* / mag45 / drum60 — пересчёт со старых рук, "
                    "grip / pressed — хват владельца на v14")
    jp = out.parent / "source_poses.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8", newline="\n")
    root["axes"] = "оси VERAS54_WeaponRig: +X — к дулу, +Y — влево, +Z — вверх; м"
    S.frame_start, S.frame_end = 1, 1
    S.camera = bpy.data.objects.get("FPS • Camera")
    # карты не упаковываются (файл и так большой): берутся с диска — библиотека ВЕРАСа и assets игры
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    log("сохранено", out, "позы", sorted(poses), "точки", {k: [round(v * 1000, 1) for v in p] for k, p in points.items()})


if __name__ == "__main__":
    main()
