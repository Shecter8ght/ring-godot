"""ВЕРАС-54: экспорт из Blender в игру — вьюмодель (руки + оружие + клипы), мировая и подробная модели.

v13 (2026-10-19): форма и текстуры v13 v02 (приняты владельцем), игровая сетка ~33 тыс. треугольников + 30 патронов
(tools/veras54_v13: game_lp.py → game_bake.py → game_pack.py → game_rig.py → clips/build_clips.py → этот экспорт).
Модели — .gltf с картами отдельными PNG рядом: вьюмодель, мировая и подробная делят один набор карт
(veras54_<Атлас>_100_{albedo,normal,orm}.png); маски жировой плёнки _coat кладёт game_pack.py.

  viewmodel — руки FPS_ArmsRig и оружие VERAS54_WeaponRig в осях камеры от первого лица (камера в начале, взгляд по −Z
              Godot). Клипы (NLA-дорожки → анимации glTF): idle, reload_tactical, reload_full, mag_check, jam_clear,
              reload_fast, reload_fast_full; служебные: follower_by_rounds (подаватель, кадр n = n патронов), bolt_travel
              (кадр 0 — затвор закрыт, 1 — отведён на 100,6 мм; кости Bolt и RecoilSpring), selector_by_mode (рычаг переводчика:
              кадр на положение — АВ, «2», ОД, как fire_modes ствола); переводчик большим пальцем — fire_mode_<откуда>_<куда>
              (clips/fire_mode_clip.py). IK и драйверы рига запечены в
              ключи костей. Детали склеены по узлам, патроны — узлы Round_NN (1 — верхний). Метки: SightRear (плечики
              U-прорези целика), SightFront (вершина мушки) — обе на 57 мм над осью канала, Muzzle, WeaponFrame (оси игры у
              пистолетной рукоятки — сюда встают обвесы).
  world     — только оружие, без рига, упрощено до WORLD_TRIS: начало — пистолетная рукоятка, оси игры (+Z к дулу, +Y вверх,
              −X — правая сторона стрелка), метки как выше; магазин, приклад и дульное устройство — отдельные узлы Magazine,
              Stock, MuzzleDevice (игра прячет / меняет их обвесом).
  detail    — та же мировая без упрощения (игровая сетка в руках): veras54_detail.gltf для конструктора; пишется и с world.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/export_veras54.py -- [viewmodel] [world] [detail] [grips]
  grips — добавить во вьюмодель наборы клипов под рукоятки ВАРН V1 / V2 (позы кистей владельца); grips=varn_v2 — только названные
→ assets/models/weapons/veras54/veras54_viewmodel.gltf, veras54.gltf, veras54_detail.gltf (+ .bin, карты), veras54.json (проверки)
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/veras54_v13"))
sys.path.insert(0, str(ROOT / "tools/veras54_v13/clips"))
import game_mats  # noqa: E402

LIB = Path("E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия")
SRC = LIB / "Клипы v13"
OUT = ROOT / "assets/models/weapons/veras54"
WORK = ROOT / "_asset_src/veras54_game_v13"
REC = json.loads((WORK / "lp/parts.json").read_text(encoding="utf-8"))
BASE = SRC / "VERAS54_Reload_Full_v13.blend"
# Позы кистей на рукоятках владелец правил сам (2026-10-10); наборы под рукоятки — только с аргументом grips.
GRIPS: tuple = ()
for _arg in sys.argv:
    if _arg == "grips":
        GRIPS = ("varn_v1", "varn_v2")
    elif _arg.startswith("grips="):
        GRIPS = tuple(g for g in _arg.split("=", 1)[1].split(",") if g in ("varn_v1", "varn_v2"))
# клип в игре: (суффикс действий build_clips.py, последний кадр, файл с действиями; None — база сцены)
CLIPS = {"reload_tactical": ("Tactical", 79, SRC / "VERAS54_Reload_Tactical_v13.blend"),
         "mag_check": ("Check", 104, SRC / "VERAS54_Mag_Check_v13.blend"),
         "reload_full": ("Full", 114, None),
         "jam_clear": ("Jam", 46, SRC / "VERAS54_Jam_Clear_v13.blend"),
         # быстрая перезарядка (двойное R): новым магазином выбивают старый; _full — с досылкой затвором
         "reload_fast": ("Fast", 58, SRC / "VERAS54_Reload_Fast_v13.blend"),
         "reload_fast_full": ("Fastfull", 92, SRC / "VERAS54_Reload_FastFull_v13.blend")}
for _g in GRIPS:
    for _clip, _tag, _last, _file in (("reload_tactical", "Tactical", 79, "Reload_Tactical"), ("mag_check", "Check", 104, "Mag_Check"),
                                      ("reload_full", "Full", 114, "Reload_Full"), ("jam_clear", "Jam", 46, "Jam_Clear"),
                                      ("reload_fast", "Fast", 58, "Reload_Fast"), ("reload_fast_full", "Fastfull", 92, "Reload_FastFull")):
        CLIPS[f"{_clip}_{_g}"] = (f"{_tag}_{_g}", _last, SRC / f"VERAS54_{_file}_{_g}_v13.blend")
# переводчик огня большим пальцем правой руки (tools/veras54_v13/clips/fire_mode_clip.py): АВ→2, 2→ОД, ОД→АВ, 18 кадров;
# рычаг в игре ставит сама игра по режиму (служебный клип selector_by_mode)
for _a, _b in (("auto", "burst"), ("burst", "semi"), ("semi", "auto")):
    CLIPS[f"fire_mode_{_a}_{_b}"] = (f"Firemode_{_a}_{_b}", 18, SRC / f"VERAS54_FireMode_{_a}_{_b}_v13.blend")
    for _g in GRIPS:
        CLIPS[f"fire_mode_{_a}_{_b}_{_g}"] = (f"Firemode_{_a}_{_b}_{_g}", 18, SRC / f"VERAS54_FireMode_{_a}_{_b}_{_g}_v13.blend")
# стойка — первый кадр тактической: без рукоятки и с каждой из них
IDLES = {"idle": "Tactical", **{f"idle_{g}": f"Tactical_{g}" for g in GRIPS}}
# магазины 45 и барабан 60 (tools/veras54_mags/mags_vm.py): свои наборы клипов «<клип>[_<рукоятка>]_<mag45|drum60>»,
# если их файлы есть в «Клипы v13»; модели магазинов игра ставит сама на метки MagAsset / SpareMagAsset
sys.path.insert(0, str(ROOT / "tools/veras54_mags"))
import mags_vm  # noqa: E402
CLIPS.update(mags_vm.clips(SRC, GRIPS))
# Сцена клипов: оси VERAS54 (дуло +X, влево +Y) → мир (оружие смотрит по −Y), ось канала на высоте 1,7 м.
ROOT_REST = Matrix.Translation((-0.14, -0.25, 1.7)) @ Matrix.Rotation(math.radians(-90), 4, "Z")
GRIP_LOCAL = Vector((0.073, 0.0, -0.065))      # пистолетная рукоятка — начало осей игры (оси VERAS54)
GRIP = ROOT_REST @ GRIP_LOCAL
MARKS_LOCAL = {"SightRear": Vector(REC["markers_m"]["SightRear"]), "SightFront": Vector(REC["markers_m"]["SightFront"]),
               "Muzzle": Vector(REC["markers_m"]["MuzzleBrakeEnd"])}
MARKS = {k: ROOT_REST @ v for k, v in MARKS_LOCAL.items()}
WORLD_TRIS = 9000
TEX_ARMS = 2048
# в мировой и подробной модели — только верхние патроны (остальные закрыты корпусом магазина)
WORLD_ROUNDS = (1, 2)

report: dict = {}


def objs(kind=None):
    return [o for o in bpy.data.objects if kind is None or o.type == kind]


def remove(ob) -> None:
    bpy.data.objects.remove(ob, do_unlink=True)


def drop_extras() -> None:
    """Глушитель (отдельный ассет), камеры, свет, скрытые и текстовые объекты — не в игру."""
    sup = {o for c in bpy.data.collections if "Suppressor" in c.name for o in c.all_objects if o is not None}
    for ob in list(bpy.data.objects):
        if ob.name not in bpy.data.objects:
            continue
        if ob in sup or ob.type in ("CAMERA", "LIGHT", "FONT", "CURVE") and ob.name != "FPS • Camera":
            remove(ob)
        elif ob.type == "MESH" and (ob.hide_render or ob.hide_get()) and "loaded" not in ob.name:
            remove(ob)


def strip_drivers() -> None:
    for ob in objs():
        ad = ob.animation_data
        if ad:
            for d in list(ad.drivers):
                ad.drivers.remove(d)
        if ob.type == "MESH":
            ob.hide_viewport = ob.hide_render = False


def join(group: list, name: str):
    """Склеить сетки (модификаторы уже применены), имя — name; возвращает объект."""
    if not group:
        return None
    for o in group:
        if o.data.users > 1:
            o.data = o.data.copy()
    if len(group) == 1:
        group[0].name = name
        return group[0]
    with bpy.context.temp_override(active_object=group[0], selected_editable_objects=group, selected_objects=group):
        bpy.ops.object.join()
    group[0].name = name
    return group[0]


def apply_mods() -> None:
    for ob in objs("MESH"):
        if any(m.type != "ARMATURE" for m in ob.modifiers):
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
                for m in [m for m in ob.modifiers if m.type != "ARMATURE"]:
                    bpy.ops.object.modifier_apply(modifier=m.name)


def rounds_join() -> int:
    """Патрон = гильза + пуля одного номера → узел Round_NN."""
    n = 0
    for i in range(1, 31):
        parts = [o for o in objs("MESH") if o.name in (f"Magazine • loaded case {i}", f"Magazine • loaded projectile {i}")]
        if parts:
            join(parts, f"Round_{i:02d}")
            n += 1
    return n


def join_by_parent(skip_prefix=("Round_", "FPS_", "SpareRounds")) -> int:
    """Детали с одним родителем (кость/пустышка) — одной сеткой: меньше вызовов отрисовки."""
    groups: dict = {}
    for ob in objs("MESH"):
        if ob.name.startswith(skip_prefix):
            continue
        key = (ob.parent.name if ob.parent else "", ob.parent_bone if ob.parent_type == "BONE" else "", ob.parent_type)
        groups.setdefault(key, []).append(ob)
    for (pname, pbone, _), group in groups.items():
        join(group, "Part_" + (pbone or pname).replace(" • ", "_").replace(" ", "_")[:40])
    return len(groups)


def add_mark(name: str, world: Vector, parent, bone: str = "") -> None:
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = 0.01
    e.matrix_world = Matrix.Translation(world)
    if parent is not None:
        mw = e.matrix_world.copy()
        e.parent = parent
        if bone:
            e.parent_type = "BONE"
            e.parent_bone = bone
        e.matrix_world = mw


def export_gltf(path: Path, **kw) -> None:
    """glTF с картами отдельными файлами рядом (общими для всех моделей ВЕРАСа)."""
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="", export_yup=True,
                              export_materials="EXPORT", export_image_format="AUTO", export_cameras=False,
                              export_lights=False, **kw)


# ---------------------------------------------------------------- вьюмодель

def fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def append_actions() -> None:
    for suffix, _, path in CLIPS.values():
        if path is None:
            continue
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.actions = [a for a in src.actions if a.startswith(f"VERAS54_{suffix}_") and a.endswith("_v01")
                           and a.split("_v01")[0].rsplit("_", 1)[0] == f"VERAS54_{suffix}"]


def assign(ob, act) -> None:
    ad = ob.animation_data or ob.animation_data_create()
    ad.action = act
    if act is not None and act.slots:
        ad.action_slot = act.slots[0]


def sample(arms, wr, frames: list, skip=()) -> dict:
    """Итоговая поза костей (с IK, ограничениями и драйверами) в локальных осях — по кадрам."""
    sc = bpy.context.scene
    data = {arms.name: {}, wr.name: {}}
    # кость без ключей в этом клипе — в покое, а не там, где её оставил прошлый клип (гильза задержки)
    for arm in (arms, wr):
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    for f in frames:
        sc.frame_set(int(f), subframe=f - int(f))
        bpy.context.view_layer.update()
        for arm in (arms, wr):
            for pb in arm.pose.bones:
                if pb.name in skip:
                    continue
                m = arm.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL")
                data[arm.name].setdefault(pb.name, []).append(m.copy())
    return data


def bake_action(arm, name: str, frames: list, mats: dict) -> bpy.types.Action:
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    assign(arm, act)
    for pb in arm.pose.bones:
        if pb.name not in mats:
            continue
        pb.rotation_mode = "QUATERNION"
        for i, f in enumerate(frames):
            loc, rot, scl = mats[pb.name][i].decompose()
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
            for path in ("location", "rotation_quaternion", "scale"):
                pb.keyframe_insert(path, frame=i + 1)
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    assign(arm, None)
    return act


def push_track(arm, track_name: str, act) -> None:
    ad = arm.animation_data or arm.animation_data_create()
    tr = ad.nla_tracks.new()
    tr.name = track_name
    tr.strips.new(track_name, 1, act)


def local_of(wr, name: str):
    pb = wr.pose.bones[name]
    return wr.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL").copy()


def viewmodel() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    append_actions()
    sc = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    wr = bpy.data.objects["VERAS54_WeaponRig"]
    root = bpy.data.objects["VERAS54"]
    magob = bpy.data.objects["Magazine"]
    cam = bpy.data.objects["FPS • Camera"]
    acts = {a.name: a for a in bpy.data.actions}
    report["materials_viewmodel"] = game_mats.build_all()
    # карты рук — 2048, как в прежней вьюмодели (карты оружия — своего размера из game_pack.py)
    for img in bpy.data.images:
        if not img.name.startswith("veras54_") and img.size[0] > TEX_ARMS:
            img.scale(TEX_ARMS, TEX_ARMS * img.size[1] // max(img.size[0], 1))
    # гильза задержки: кость JamCase у WeaponRoot и сетка на ней (стоит в окне; клип jam_clear её выбрасывает)
    import rig_common
    sc.frame_set(1)
    bpy.context.view_layer.update()
    rig_common.add_jam_case(wr)
    # старый магазин быстрой перезарядки: кость SpareMag и копия магазина на ней (вне клипа скрыт игрой)
    rig_common.add_spare_mag(wr)
    # метки моделей магазинов 45 / 60 (оси модели магазина) на костях Magazine и SpareMag
    report["mag_marks"] = mags_vm.add_marks(wr, magob)
    report["mag_sets"] = sorted(k for k in CLIPS if k.endswith(mags_vm.MAG_SETS))
    # подаватель в клипах не запекается — его ставит игра по счёту патронов (клип follower_by_rounds)
    skip = ("MagazineFollower",)
    baked = {}
    for clip, (suffix, last, _) in CLIPS.items():
        for kind in ("Arms", "Weapon"):
            if f"VERAS54_{suffix}_{kind}_v01" not in acts:
                raise RuntimeError(f"нет действия VERAS54_{suffix}_{kind}_v01 для клипа {clip}")
        for ob, kind in ((arms, "Arms"), (wr, "Weapon"), (root, "Controls"), (magob, "Rounds")):
            assign(ob, acts.get(f"VERAS54_{suffix}_{kind}_v01"))
        frames = list(range(1, last + 1))
        baked[clip] = (frames, sample(arms, wr, frames, skip))
        print("VERAS clip", clip, len(frames), flush=True)
    # стойка — первый кадр тактической (боевой хват владельца), два кадра для зацикливания
    for idle, suffix in IDLES.items():
        for ob, kind in ((arms, "Arms"), (wr, "Weapon"), (root, "Controls"), (magob, "Rounds")):
            assign(ob, acts.get(f"VERAS54_{suffix}_{kind}_v01"))
        baked[idle] = ([1, 2], sample(arms, wr, [1, 1], skip))
    # служебные: подаватель по счёту патронов и затвор (отвод для выстрела; с ним пружина)
    for ob in (arms, wr, root, magob):
        assign(ob, None)
    for pb in wr.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    follower = []
    for n in range(31):
        magob["Rounds remaining"] = n
        magob.update_tag()
        bpy.context.view_layer.update()
        follower.append(local_of(wr, "MagazineFollower"))
    magob["Rounds remaining"] = 30
    bolt, spring = [], []
    for v in (0.0, 1.0):
        root["Bolt pull"] = v
        root.update_tag()
        bpy.context.view_layer.update()
        bolt.append(local_of(wr, "Bolt"))
        spring.append(local_of(wr, "RecoilSpring"))
    root["Bolt pull"] = 0.0
    report["bolt_travel_m"] = round((bolt[1].translation - bolt[0].translation).length, 4)
    # переводчик: положения рычага по порядку fire_modes ствола (data/weapons.json) — АВ, «2», ОД. Драйвер рига знает только
    # АВ и ОД, «2» — между ними по меткам (3,92° из 7,85°, _asset_src/veras54_v13/tex/gen_selector_track.py)
    sel = []
    for mode in (1, 2):
        for k, v in (("Fire mode", mode), ("Selector from mode", mode), ("Selector blend", 1.0)):
            root[k] = v
        root.update_tag()
        bpy.context.view_layer.update()
        sel.append(local_of(wr, "Selector"))
    for k, v in (("Fire mode", 1), ("Selector from mode", 1), ("Selector blend", 1.0)):
        root[k] = v
    root.update_tag()
    bpy.context.view_layer.update()
    l0, r0, s0 = sel[0].decompose()
    l1, r1, s1 = sel[1].decompose()
    k_burst = 3.92 / 7.85
    sel.insert(1, Matrix.LocRotScale(l0.lerp(l1, k_burst), r0.slerp(r1, k_burst), s0))
    report["selector_auto_single_deg"] = round(math.degrees(r0.rotation_difference(r1).angle), 2)
    # снять ограничения и драйверы — дальше кости ведут только запечённые ключи
    for arm in (arms, wr):
        for pb in arm.pose.bones:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
    strip_drivers()
    for ob in (root, magob):
        if ob.animation_data:
            ob.animation_data.action = None
    for clip, (frames, data) in baked.items():
        push_track(arms, clip, bake_action(arms, f"VM_{clip}_arms", frames, data[arms.name]))
        push_track(wr, clip, bake_action(wr, f"VM_{clip}_weapon", frames, data[wr.name]))
    push_track(wr, "follower_by_rounds", bake_action(wr, "VM_follower", list(range(31)), {"MagazineFollower": follower}))
    push_track(wr, "bolt_travel", bake_action(wr, "VM_bolt", [0, 1], {"Bolt": bolt, "RecoilSpring": spring}))
    push_track(wr, "selector_by_mode", bake_action(wr, "VM_selector", [0, 1, 2], {"Selector": sel}))
    for arm in (arms, wr):
        arm.data.pose_position = "POSE"
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    # метки и рама обвесов — у кости WeaponRoot (руки в покое: VERAS54 стоит в ROOT_REST)
    for name, p in MARKS.items():
        add_mark(name, p, wr, "WeaponRoot")
    add_mark("WeaponFrame", GRIP, wr, "WeaponRoot")
    drop_extras()
    apply_mods()
    report["rounds"] = rounds_join()
    # патроны запасного магазина — отдельным узлом: у пустого старого магазина игра их не показывает
    join([o for o in objs("MESH") if o.name.startswith("SpareMag • round")], "SpareRounds")
    report["parts_viewmodel"] = join_by_parent()
    # оси камеры: камера в начале, взгляд Blender +Y (= −Z glTF/Godot), верх +Z
    to_cam = Matrix.Rotation(math.radians(90), 4, "X") @ cam.matrix_world.inverted()
    arms.matrix_world = to_cam @ arms.matrix_world
    remove(cam)
    report["tris_viewmodel"] = tri_count()
    report["tris_viewmodel_weapon"] = tri_count(lambda o: not o.name.startswith("FPS_"))
    export_gltf(OUT / "veras54_viewmodel.gltf", export_animations=True, export_animation_mode="NLA_TRACKS",
                export_skins=True,
                # у основания большого пальца на вершину до 8 костей: с четырьмя перчатка там ломалась
                export_all_influences=True, export_def_bones=False, export_force_sampling=True, export_apply=False)
    print("VERAS viewmodel saved", flush=True)


def tri_count(pred=None) -> int:
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in objs("MESH"):
        if pred is not None and not pred(ob):
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        t += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return t


# ---------------------------------------------------------------- мировая модель

def world(detail: bool = False) -> None:
    """Мировая модель из игровой сетки (оси VERAS54). detail — без упрощения (конструктор, вблизи)."""
    bpy.ops.wm.open_mainfile(filepath=str(WORK / "lp/VERAS54_Game_LP.blend"))
    game_mats.build_all()
    for ob in list(objs("MESH")):
        if ob.name.startswith("Magazine • loaded") and int(ob.name.rsplit(" ", 1)[1]) not in WORLD_ROUNDS:
            remove(ob)
    meshes = objs("MESH")
    brake = [o for o in meshes if o.name.startswith("MuzzleDevice")]
    mag = [o for o in meshes if o.name.startswith(("Magazine_", "Magazine •"))]
    stock = [o for o in meshes if o.name.startswith("StockFold")]
    rest = [o for o in meshes if o not in brake and o not in mag and o not in stock]
    # начало — пистолетная рукоятка; оси игры совпадают с осями glTF после экспорта Y-up
    to_game = Matrix.Rotation(math.radians(-90), 4, "Z") @ Matrix.Translation(-GRIP_LOCAL)
    for ob in meshes:
        ob.matrix_world = to_game @ ob.matrix_world
    nodes = {"Body": join(rest, "Body"), "MuzzleDevice": join(brake, "MuzzleDevice"), "Magazine": join(mag, "Magazine"),
             "Stock": join(stock, "Stock")}
    for ob in nodes.values():
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    t0 = tri_count()
    ratio = 1.0 if detail else min(1.0, WORLD_TRIS / max(t0, 1))
    if ratio < 1.0:
        for ob in nodes.values():
            dec = ob.modifiers.new("dec", "DECIMATE")
            dec.ratio = ratio
            dec.use_collapse_triangulate = True
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
                bpy.ops.object.modifier_apply(modifier="dec")
    for name, p in MARKS_LOCAL.items():
        add_mark(name, to_game @ p, None)
    name = "veras54_detail.gltf" if detail else "veras54.gltf"
    if detail:
        report["tris_detail"] = tri_count()
    else:
        report["tris_world_before"] = t0
        report["tris_world"] = tri_count()
    bb = [v.co for v in nodes["Body"].data.vertices]
    report["world_size_m"] = [round(max(c[i] for c in bb) - min(c[i] for c in bb), 3) for i in range(3)]
    export_gltf(OUT / name, export_animations=False, export_apply=True)
    print("VERAS world saved", name, flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["viewmodel", "world"]
    # VERAS_CLAY=1 — пробный экспорт без карт (проверка клипов и меток в игре до конца запекания)
    if not game_mats.ready() and os.environ.get("VERAS_CLAY") != "1":
        raise SystemExit("нет игровых карт — сначала tools/veras54_v13/game_pack.py")
    if "viewmodel" in args:
        viewmodel()
    if "world" in args:
        world()
    if "detail" in args or "world" in args:
        world(detail=True)
    path = OUT / "veras54.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old.update(report)
    old.update(source=REC["source"], source_sha256=REC["source_sha256"], version="v13 (2026-10-19)",
               markers_local_m={k: [round(c, 4) for c in v] for k, v in MARKS_LOCAL.items()},
               lp_triangles=REC["triangles"])
    path.write_text(json.dumps(old, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("VERAS report", report, flush=True)
