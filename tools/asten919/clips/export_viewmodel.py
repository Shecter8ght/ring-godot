"""АСТЕН-919 (wpn_hg_02): клипы рук владельца → игра. Руки (мастер FPS-рук v14, кисти исправлены) и пистолет со всеми
клипами → assets/models/weapons/asten919/asten919_viewmodel.gltf; кадры фаз (свойство действия marks) и длины клипов —
в отчёт asten919_viewmodel.json рядом (из него данные игры: tools/asten919/clips/viewmodel_data.py).

Файл владельца (E:/Models Blender/WEAPONS/АСТЕН-919/АСТЕН-919_руки_клипы_v01.blend) — источник правды: он не
открывается и не сохраняется, работа идёт на копии _asset_src/asten919/anim/export_src.blend (копируется заново
каждый запуск). Клип — действие ASTEN919_<Клип> со слотами двух ригов (FPS_ArmsRig, ASTEN919_WeaponRig); поза
каждого кадра снимается целиком — с IK рук, ограничением «В левой кисти» (магазин держит кость mag.L) и масштабом
спрятанных деталей — и записывается ключами костей (ограничения затем снимаются). Кости, которых клип не трогает,
стоят как в позе покоя (действие ASTEN919_Poses, кадр 1 — хват обеими руками); старый магазин и гильзы в покое
сжаты в точку (масштаб 0,001), их «включают» сами клипы.

Клипы в игре (NLA-дорожки → анимации glTF): idle (покой), reload_tactical, reload_full (затвор на задержке, рычаг),
reload_full_rack (затвор закрыт, левая передёргивает), reload_fast, reload_fast_full, mag_check, inspect, jam_clear,
slide_rack, fire, finger_to_trigger; служебные: follower_by_rounds (подаватель на 0…30 патронов, кадр на счёт),
bolt_travel (затвор и ствол: закрыт / сзади, как в начале reload_full), slide_hold (рычаг задержки поднят).
Детали склеены по костям (Part_<кость>): Part_Magazine, Part_MagazineFollower, Part_SpareMag (старый магазин быстрой
перезарядки), Part_JamCase, Part_Case; заглушка резьбы — MuzzleDevice (её прячет глушитель), патроны — Round_01…17
(1 — верхний), у старого магазина — SpareRounds. Метки у кости WeaponRoot: Muzzle, SightRear, SightFront,
WeaponFrame (оси игры у рукояти: +Z к дулу, +Y вверх, +X влево).
Карты — прежние файлы: пистолет — asten919_<Атлас>_100_* рядом, руки — ../veras54/arm*.png.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/asten919/clips/export_viewmodel.py
  [-- <файл клипов.blend>]   (по умолчанию — файл владельца)
затем: tools/godot.cmd --headless --import; python -X utf8 tools/asten919/clips/viewmodel_data.py
"""
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[3]
OWNER = Path("E:/Models Blender/WEAPONS/АСТЕН-919/АСТЕН-919_руки_клипы_v01.blend")
WORK = ROOT / "_asset_src/asten919/anim/export_src.blend"
OUT = ROOT / "assets/models/weapons/asten919"
NAME = "asten919_viewmodel"
ARMS_TEX = ROOT / "assets/models/weapons/veras54"
ARMS, GUN, ROOT_EMPTY, CAM = "FPS_ArmsRig", "ASTEN919_WeaponRig", "ASTEN919", "FPS • Camera"
POSES = "ASTEN919_Poses"
# клип в игре ← действие владельца
CLIPS = {
    "reload_tactical": "ASTEN919_Reload_Tactical",
    "reload_full": "ASTEN919_Reload_Full",
    "reload_full_rack": "ASTEN919_Reload_Full_Rack",
    "reload_fast": "ASTEN919_Reload_Fast_Tactical",
    "reload_fast_full": "ASTEN919_Reload_Fast_Full",
    "mag_check": "ASTEN919_Mag_Check",
    "inspect": "ASTEN919_Inspect",
    "jam_clear": "ASTEN919_Jam_Clear",
    "slide_rack": "ASTEN919_Slide_Rack",
    "fire": "ASTEN919_Fire",
    "finger_to_trigger": "ASTEN919_Finger_To_Trigger",
}
HIDDEN = ("SpareMag_Control", "Case", "JamCase")      # в покое сжаты в точку
TABLE_ROUNDS = 31                                       # follower_by_rounds: записи 0…30 (ViewmodelClips)
report = {}


def log(*a):
    print("ASTEN919_VM", *a, flush=True)


def slot_of(act, ob):
    return next((s for s in act.slots if s.name_display == ob.name), None)


def bag_of(act, ob):
    slot = slot_of(act, ob)
    if slot is None:
        return None
    for layer in act.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag is not None:
                return bag
    return None


def last_key(act):
    frames = [kp.co[0] for layer in act.layers for strip in layer.strips for bag in strip.channelbags
              for fc in bag.fcurves for kp in fc.keyframe_points]
    return int(math.ceil(max(frames, default=1.0)))


def keyed_bones(act, ob):
    bag = bag_of(act, ob)
    return sorted({fc.data_path.split('"')[1] for fc in (bag.fcurves if bag else ()) if fc.data_path.startswith('pose.bones["')})


def assign(ob, act):
    ad = ob.animation_data or ob.animation_data_create()
    if ad.use_tweak_mode:
        ad.use_tweak_mode = False
    ad.use_nla = False
    ad.action = act
    if act is not None:
        slot = slot_of(act, ob)
        if slot is not None:
            ad.action_slot = slot
        ad.action_extrapolation = "HOLD"
        ad.action_blend_type = "REPLACE"
        ad.action_influence = 1.0


def set_base(rigs, base):
    for ob in rigs:
        for pb in ob.pose.bones:
            pb.matrix_basis = base[ob.name][pb.name].copy()


def sample(rigs, frames, skip=()):
    """Итоговая поза костей (IK, ограничения) в локальных осях — по кадрам."""
    sc = bpy.context.scene
    data = {ob.name: {} for ob in rigs}
    for f in frames:
        sc.frame_set(int(f))
        bpy.context.view_layer.update()
        for ob in rigs:
            for pb in ob.pose.bones:
                if pb.name in skip:
                    continue
                m = ob.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL")
                data[ob.name].setdefault(pb.name, []).append(m.copy())
    return data


def fcurves(act):
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


def bake_action(ob, name, count, mats):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ad = ob.animation_data or ob.animation_data_create()
    ad.use_nla = True
    ad.action = act
    for pb in ob.pose.bones:
        if pb.name not in mats:
            continue
        pb.rotation_mode = "QUATERNION"
        for i in range(count):
            loc, rot, scl = mats[pb.name][i].decompose()
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
            for path in ("location", "rotation_quaternion", "scale"):
                pb.keyframe_insert(path, frame=i + 1)
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    ad.action = None
    return act


def push_track(ob, track_name, act):
    ad = ob.animation_data or ob.animation_data_create()
    tr = ad.nla_tracks.new()
    tr.name = track_name
    tr.strips.new(track_name, 1, act)


def join(group, name):
    for o in group:
        if o.data.users > 1:
            o.data = o.data.copy()
    if len(group) > 1:
        with bpy.context.temp_override(active_object=group[0], selected_editable_objects=group, selected_objects=group):
            bpy.ops.object.join()
    group[0].name = name
    return group[0]


def reparent(ob, rig, bone):
    w = ob.matrix_world.copy()
    ob.parent = rig
    ob.parent_type = "BONE"
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = w


def open_marks(act_name):
    """Метки фаз: свойство действия; у клипа, открытого в окне при сохранении, — маркеры шкалы (их панель «АСТЕН»
    переносит в действие только при переходе к другому клипу)."""
    act = bpy.data.actions[act_name]
    arms = bpy.data.objects[ARMS]
    marks = json.loads(act.get("marks", "{}"))
    cur = arms.animation_data.action if arms.animation_data else None
    if cur is act and bpy.context.scene.timeline_markers:
        marks = {m.name: m.frame for m in bpy.context.scene.timeline_markers}
    return {k: int(v) for k, v in sorted(marks.items(), key=lambda kv: kv[1])}


def follower_table(wr):
    """Подаватель по числу патронов: стопка уходит вниз — подаватель стоит под нижним патроном (как у моделей магазинов
    в ViewmodelClips._mag_look): n патронов — сдвиг «последний → n-й»; 0 — ещё шаг вверх. Боковая «шахматка» не нужна."""
    fol = wr.pose.bones["MagazineFollower"]
    mag = wr.pose.bones["Magazine"]
    rounds = sorted((o for o in bpy.data.objects if o.name.startswith("Round_")), key=lambda o: o.name)
    full = fol.matrix.copy()                        # в осях рига (поза покоя)
    mag_inv = mag.matrix.inverted()
    R = [wr.matrix_world.inverted() @ o.matrix_world for o in rounds]
    last_inv = R[-1].inverted()
    lat = (mag_inv @ full).translation.x
    mats = []
    for n in range(TABLE_ROUNDS):
        k = min(n, len(R))
        t = R[max(k, 1) - 1] @ last_inv @ full
        if k == 0:
            t = R[0] @ R[1].inverted() @ t
        local = mag_inv @ t
        local.translation.x = lat
        t = mag.matrix @ local
        mats.append(wr.convert_space(pose_bone=fol, matrix=t, from_space="POSE", to_space="LOCAL"))
    return mats


def motion(data_arms, frames):
    """Насколько клип двигает пистолет (кость Weapon_CTRL) от первого кадра: см и градусы."""
    arms = bpy.data.objects[ARMS]
    pb = arms.pose.bones["Weapon_CTRL"]
    mats = data_arms["Weapon_CTRL"]
    rest = pb.bone.matrix_local
    first = rest @ mats[0]
    dmax, amax = 0.0, 0.0
    for m in mats:
        cur = rest @ m
        dmax = max(dmax, (cur.translation - first.translation).length)
        amax = max(amax, math.degrees(first.to_quaternion().rotation_difference(cur.to_quaternion()).angle))
    return round(dmax * 100, 1), round(amax, 1)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    src = Path(argv[0]) if argv else OWNER
    WORK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, WORK)
    bpy.ops.wm.open_mainfile(filepath=str(WORK))
    report["source"] = str(src)
    report["source_mtime"] = src.stat().st_mtime
    sc = bpy.context.scene
    fps = sc.render.fps
    arms, wr = bpy.data.objects[ARMS], bpy.data.objects[GUN]
    root, cam = bpy.data.objects[ROOT_EMPTY], bpy.data.objects[CAM]
    rigs = (arms, wr)
    marks = {clip: open_marks(act) for clip, act in CLIPS.items()}
    # ---- покой: кадр 1 поз
    poses = bpy.data.actions[POSES]
    for ob in rigs:
        assign(ob, poses)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    base = {ob.name: {pb.name: pb.matrix_basis.copy() for pb in ob.pose.bones} for ob in rigs}
    pose_keyed = set(keyed_bones(poses, wr))
    for b in HIDDEN:
        if b not in pose_keyed:
            base[GUN][b] = Matrix.Diagonal((0.001, 0.001, 0.001, 1.0))
    skip = ("MagazineFollower",)
    baked, lengths, weapon_keys, moves = {}, {}, {}, {}
    set_base(rigs, base)
    baked["idle"] = (2, sample(rigs, [1, 1], skip))
    for clip, act_name in CLIPS.items():
        act = bpy.data.actions[act_name]
        n = last_key(act)
        set_base(rigs, base)
        for ob in rigs:
            assign(ob, act)
        data = sample(rigs, range(1, n + 1), skip)
        baked[clip] = (n, data)
        lengths[clip] = n
        weapon_keys[clip] = keyed_bones(act, wr)
        moves[clip] = motion(data[ARMS], n)
        log("клип", clip, n, "кадров", round(n / fps, 2), "с, пистолет сдвиг/поворот", moves[clip])
    # ---- служебные таблицы (поза покоя рига пистолета, ограничения ещё на месте)
    for ob in rigs:
        assign(ob, None)
    set_base(rigs, base)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    fol_table = follower_table(wr)
    full = baked["reload_full"][1][GUN]            # кадр 1 reload_full: затвор на задержке
    jam = baked["jam_clear"][1][GUN]               # кадр 1 jam_clear: затвор недозакрыт на гильзе
    back = full["Slide"][0].translation.length
    report["jam_open"] = round(jam["Slide"][0].translation.length / back, 3) if back > 1e-6 else 0.3
    report["slide_travel_m"] = round(back, 4)
    rest = Matrix.Identity(4)
    bolt = {b: [rest, full[b][0]] for b in ("Slide", "Barrel")}
    hold = {"SlideStop": [rest, full["SlideStop"][0]]}
    # ---- ограничения прочь: дальше кости ведут только запечённые ключи
    for ob in rigs:
        for pb in ob.pose.bones:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
        ob.animation_data.action = None
        for tr in list(ob.animation_data.nla_tracks):
            ob.animation_data.nla_tracks.remove(tr)
    for clip, (n, data) in baked.items():
        push_track(arms, clip, bake_action(arms, f"VM_{clip}_arms", n, data[ARMS]))
        push_track(wr, clip, bake_action(wr, f"VM_{clip}_weapon", n, data[GUN]))
    push_track(wr, "follower_by_rounds", bake_action(wr, "VM_follower", TABLE_ROUNDS, {"MagazineFollower": fol_table}))
    push_track(wr, "bolt_travel", bake_action(wr, "VM_bolt", 2, bolt))
    push_track(wr, "slide_hold", bake_action(wr, "VM_slide_hold", 2, hold))
    # дальше — в позе покоя: экспорт считает детали и метки на костях от покоя кости, а дорожки NLA ставили бы
    # их по позе своего кадра (сетки пистолета уезжали от кости на ~9 см)
    for ob in rigs:
        ob.animation_data.use_nla = False
        ob.animation_data.action = None
        ob.data.pose_position = "POSE"
        for pb in ob.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    # ---- метки: у кости WeaponRoot (прицельные сидят на затворе — в покое те же места); WeaponFrame — оси игры
    for name in ("SightRear", "SightFront", "Muzzle"):
        reparent(bpy.data.objects[name], wr, "WeaponRoot")
    wf = bpy.data.objects["WeaponFrame"]
    reparent(wf, wr, "WeaponRoot")
    # исходник пистолета: +X дуло, +Y влево, +Z вверх; узел glTF: X Blender → X, Z → Y, −Y → Z. Нужно: X игры = влево,
    # Y = вверх, Z = к дулу — то есть локальные оси Blender: X = +Y исходника, Y = −X исходника, Z = +Z (поворот на 90°)
    rot = root.matrix_world.to_quaternion().to_matrix().to_4x4() @ Matrix.Rotation(math.radians(90.0), 4, "Z")
    wf.matrix_world = Matrix.Translation(wf.matrix_world.translation) @ rot
    # ---- руки: карты игры (общие с ВЕРАСом), не упакованные в исходник
    tex = {p.name.lower(): p for p in ARMS_TEX.glob("arm*.png")}
    for img in bpy.data.images:
        name = Path(img.filepath).name.lower() if img.filepath else img.name.lower()
        if name in tex:
            if img.packed_file:
                img.unpack(method="REMOVE")
            img.filepath = str(tex[name])
            img.reload()
    # ---- лишнее прочь: камеры кроме FPS, свет, скрытое
    for ob in list(bpy.data.objects):
        if ob.type == "MESH" and (ob.hide_render or ob.hide_get()):
            bpy.data.objects.remove(ob, do_unlink=True)
        elif ob.type in ("CAMERA", "LIGHT") and ob is not cam:
            bpy.data.objects.remove(ob, do_unlink=True)
    # ---- детали по костям
    muzzle = bpy.data.objects.get("MuzzleDevice_Mesh")
    if muzzle:
        muzzle.name = "MuzzleDevice"
    spare = [o for o in bpy.data.objects if o.name.startswith("SpareRound_")]
    if spare:
        join(spare, "SpareRounds")
    groups = {}
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        if ob.name.startswith(("Round_", "FPS_", "SpareRounds", "MuzzleDevice")):
            continue
        key = ob.parent_bone if ob.parent_type == "BONE" else (ob.parent.name if ob.parent else "")
        groups.setdefault(key, []).append(ob)
    for bone, group in groups.items():
        join(group, "Part_" + bone)
    report["parts"] = sorted("Part_" + b for b in groups)
    # ---- оси камеры: камера в начале, взгляд Blender +Y (= −Z glTF/Godot), верх +Z
    to_cam = Matrix.Rotation(math.radians(90), 4, "X") @ cam.matrix_world.inverted()
    report["camera_lens_mm"] = cam.data.lens
    report["camera_fov_deg"] = round(math.degrees(cam.data.angle), 2)
    arms.matrix_world = to_cam @ arms.matrix_world
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = {}
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        tris[ob.name] = len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    report["tris"] = sum(tris.values())
    report["tris_weapon"] = sum(v for k, v in tris.items() if not k.startswith("FPS_"))
    report["fps"] = fps
    report["clips"] = {clip: {"frames": lengths[clip], "seconds": round(lengths[clip] / fps, 3), "marks": marks[clip],
                              "action": CLIPS[clip], "weapon_bones": weapon_keys[clip],
                              "gun_move_cm_deg": moves[clip]} for clip in CLIPS}
    OUT.mkdir(parents=True, exist_ok=True)
    gpath = OUT / f"{NAME}.gltf"
    bpy.ops.export_scene.gltf(filepath=str(gpath), export_format="GLTF_SEPARATE", export_texture_dir="",
                              export_keep_originals=True, export_yup=True, export_materials="EXPORT",
                              export_cameras=False, export_lights=False, export_animations=True,
                              export_animation_mode="NLA_TRACKS", export_skins=True, export_all_influences=True,
                              export_def_bones=False, export_force_sampling=True, export_apply=False)
    # Godot переимпортирует .gltf по его сумме, а ключи клипов лежат в .bin: сумма .bin — в asset.extras
    doc = json.loads(gpath.read_text(encoding="utf-8"))
    doc.setdefault("asset", {}).setdefault("extras", {})["bin_md5"] = hashlib.md5((OUT / f"{NAME}.bin").read_bytes()).hexdigest()
    gpath.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    (OUT / f"{NAME}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    log("сохранено", gpath, report["tris"], {k: v["frames"] for k, v in report["clips"].items()})


if __name__ == "__main__":
    main()
