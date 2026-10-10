"""ВЕРАС-54: экспорт из Blender в игру — вьюмодель (руки + оружие + клипы) и мировая модель.

Источник — рабочие файлы клипов владельца (E:/Models Blender/…/Перезарядка v01 (Claude)): полная
перезарядка (база сцены) + действия тактической перезарядки и проверки магазина из своих файлов.

  viewmodel — руки FPS_ArmsRig и оружие VERAS54_WeaponRig в осях камеры от первого лица (камера в
              начале, взгляд по −Z Godot). Клипы (NLA-дорожки → анимации glTF): idle, reload_tactical,
              reload_full, mag_check; служебные: follower_by_rounds (подаватель, кадр n = n патронов),
              bolt_travel (затвор: кадр 0 закрыт, 1 — отведён; суффикс _cycle Godot счёл бы пометкой цикла). IK, копирование поворота и драйверы рига
              (затвор, защёлка) запечены в ключи костей. Детали склеены по узлам (меньше вызовов отрисовки),
              патроны — узлы Round_NN (1 — верхний), их показывает игра по счёту. Метки: SightRear,
              SightFront, Muzzle, WeaponFrame (оси игры у пистолетной рукоятки — сюда встают обвесы).
  world     — только оружие, без рига: одна сетка на материал, упрощена, начало — пистолетная рукоятка,
              оси игры (+Z к дулу, +Y вверх, −X — правая сторона стрелка), метки как выше; магазин и
              складной приклад — отдельные узлы Magazine, Stock (игра прячет / меняет их обвесом).
  detail    — та же мировая без упрощения, текстуры 2048: veras54_detail.glb для конструктора оружия
              (вблизи); пишется и вместе с world.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/export_veras54.py -- [viewmodel] [world] [detail] [grips]
  grips — добавить во вьюмодель наборы клипов под рукоятки ВАРН V1 / V2 (после правки поз владельцем)
→ assets/models/weapons/veras54/veras54_viewmodel.glb, veras54.glb, veras54.json (проверки)
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = Path("E:/Models Blender/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Перезарядка v01 (Claude)")
OUT = ROOT / "assets/models/weapons/veras54"
BASE = SRC / "VERAS54_Reload_Full_v05.blend"
# v02: те же клипы с левой на рукоятке под цевьём (ВАРН V1 / V2) и устранение задержки (гильза в окне)
SRC2 = SRC.parent / "Клипы v02 (Claude)"
# Позы кистей на рукоятках владелец правит сам (2026-10-10: «в игру пока не вноси»): наборы под
# рукоятки запекаются только с аргументом grips; без него в игре левая держит цевьё позади рукоятки.
GRIPS = ("varn_v1", "varn_v2") if "grips" in sys.argv else ()
# клип в игре: (суффикс действий build_clips.py, последний кадр, файл с действиями; None — база сцены)
CLIPS = {"reload_tactical": ("Tactical", 79, SRC / "VERAS54_Reload_Tactical_v04.blend"),
         "mag_check": ("Check", 104, SRC / "VERAS54_Mag_Check_v02.blend"),
         "reload_full": ("Full", 114, None),
         "jam_clear": ("Jam", 46, SRC2 / "VERAS54_Jam_Clear_v01.blend")}
for _g in GRIPS:
    for _clip, _tag, _last, _file in (("reload_tactical", "Tactical", 79, "Reload_Tactical"), ("mag_check", "Check", 104, "Mag_Check"),
                                      ("reload_full", "Full", 114, "Reload_Full"), ("jam_clear", "Jam", 46, "Jam_Clear")):
        CLIPS[f"{_clip}_{_g}"] = (f"{_tag}_{_g}", _last, SRC2 / f"VERAS54_{_file}_{_g}_v01.blend")
# стойка — первый кадр тактической: без рукоятки и с каждой из них
IDLES = {"idle": "Tactical", **{f"idle_{g}": f"Tactical_{g}" for g in GRIPS}}
GRIP = Vector((-0.14, -0.323, 1.635))        # пистолетная рукоятка — начало осей игры
MARKS = {"SightRear": Vector((-0.14, -0.30, 1.755)), "SightFront": Vector((-0.14, -0.768, 1.755)),
         "Muzzle": Vector((-0.14, -0.955, 1.70))}
TEX_VIEW = 2048
TEX_WORLD = 1024
WORLD_TRIS = 30000

report: dict = {}


def finish_materials(path: Path) -> None:
    """Отделка оружия в готовом GLB; карты рук и клипы не изменяются.

    Системный Python проекта содержит Pillow/numpy (как остальные инструменты
    ассетов); Python Blender для этой операции не используется.
    """
    subprocess.run(["python", str(ROOT / "tools/veras54_game_materials.py"), str(path)], check=True)


GLOSS_MASK_PX = 1024


def _under_any(ob, prefix: str) -> bool:
    p = ob.parent
    while p is not None:
        if p.name.startswith(prefix):
            return True
        p = p.parent
    return False


def _uv_raster(obs: list, n: int):
    """Треугольники GameUV объектов → булева карта n×n (строка 0 — низ картинки)."""
    import numpy as np
    m = np.zeros((n, n), dtype=bool)
    for ob in obs:
        me = ob.data
        uv = me.uv_layers["GameUV"].data
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            p = np.array([uv[l].uv[:] for l in t.loops]) * n
            x0, y0 = np.maximum(np.floor(p.min(0)).astype(int) - 1, 0)
            x1, y1 = np.minimum(np.ceil(p.max(0)).astype(int) + 1, n - 1)
            d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
            if x1 < x0 or y1 < y0 or abs(d) < 1e-9:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0]) + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / d
            b = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0]) + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / d
            e = -0.6 / max(1.0, abs(d) ** 0.5)      # край пикселя тоже считается накрытым
            m[y0:y1 + 1, x0:x1 + 1] |= (a >= e) & (b >= e) & (1 - a - b >= e)
    return m


def write_gloss_mask() -> None:
    """Где на развёртке металла остаётся блеск: затворная рама и трубка приклада (решение владельца,
    2026-10-10 — остальной автомат матовый). Читает tools/veras54_game_materials.py."""
    import numpy as np
    metal = [o for o in objs("MESH") if o.data.materials and o.data.materials[0]
             and "WeaponMetal" in o.data.materials[0].name and "GameUV" in o.data.uv_layers]
    gloss = [o for o in metal if _under_any(o, "BoltCarrier") or o.name.startswith("Stock • sliding extension tube")]
    if len(gloss) < 2:
        raise RuntimeError("не найдены затворная рама и трубка приклада")
    n = GLOSS_MASK_PX
    g = _uv_raster(gloss, n)
    rest = _uv_raster([o for o in metal if o not in gloss], n)
    # поля островов (отступ текстуры) — тоже блеск, но не на чужих островах
    grown = g.copy()
    for _ in range(3):
        grown[1:, :] |= grown[:-1, :]
        grown[:-1, :] |= grown[1:, :]
        grown[:, 1:] |= grown[:, :-1]
        grown[:, :-1] |= grown[:, 1:]
    g |= grown & ~rest
    img = bpy.data.images.new("gloss_mask", n, n, alpha=False)
    px = np.zeros((n, n, 4), dtype=np.float32)
    px[..., :3] = g[..., None]
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    tmp = ROOT / "tools/veras54_gloss.mask.png"
    img.filepath_raw = str(tmp)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    # расширение не .png: Godot не должен импортировать служебную карту как текстуру
    tmp.replace(ROOT / "tools/veras54_gloss.mask")
    print("VERAS gloss mask", int(g.sum()), "px", flush=True)


def objs(kind=None):
    return [o for o in bpy.data.objects if kind is None or o.type == kind]


def remove(ob) -> None:
    bpy.data.objects.remove(ob, do_unlink=True)


def drop_extras() -> None:
    """Глушитель (отдельный ассет), камеры, свет, скрытые и текстовые объекты — не в игру."""
    sup = {o for c in bpy.data.collections if "Suppressor" in c.name for o in c.all_objects}
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


def scale_images(px: int) -> None:
    for img in bpy.data.images:
        if img.size[0] > px:
            img.scale(px, px * img.size[1] // max(img.size[0], 1))


def mesh_list(names_pred):
    return [o for o in objs("MESH") if names_pred(o)]


def join(group: list, name: str):
    """Склеить сетки (модификаторы уже применены), имя — name; возвращает объект."""
    if not group:
        return None
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


def join_by_parent(skip_prefix=("Round_", "FPS_")) -> int:
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
    write_gloss_mask()
    # гильза задержки: кость JamCase у WeaponRoot и сетка на ней (стоит в окне; клип jam_clear её выбрасывает)
    sys.path.insert(0, str(SRC2))
    import rig_common
    sc.frame_set(1)
    bpy.context.view_layer.update()
    rig_common.add_jam_case(wr)
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
    # служебные: подаватель по счёту патронов и затвор (отвод для выстрела)
    for ob in (arms, wr, root, magob):
        assign(ob, None)
    follower = []
    for n in range(31):
        magob["Rounds remaining"] = n
        magob.update_tag()
        bpy.context.view_layer.update()
        pb = wr.pose.bones["MagazineFollower"]
        follower.append(wr.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL").copy())
    magob["Rounds remaining"] = 30
    bolt = []
    for v in (0.0, 1.0):
        root["Bolt pull"] = v
        root.update_tag()
        bpy.context.view_layer.update()
        pb = wr.pose.bones["Bolt"]
        bolt.append(wr.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL").copy())
    root["Bolt pull"] = 0.0
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
    push_track(wr, "bolt_travel", bake_action(wr, "VM_bolt", [0, 1], {"Bolt": bolt}))
    for arm in (arms, wr):
        arm.data.pose_position = "POSE"
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(1)
    # метки и рама обвесов — у кости WeaponRoot (в боевой позе, Weapon_CTRL в покое)
    for name, p in MARKS.items():
        add_mark(name, p, wr, "WeaponRoot")
    add_mark("WeaponFrame", GRIP, wr, "WeaponRoot")
    drop_extras()
    apply_mods()
    report["rounds"] = rounds_join()
    report["parts_viewmodel"] = join_by_parent()
    scale_images(TEX_VIEW)
    # оси камеры: камера в начале, взгляд Blender +Y (= −Z glTF/Godot), верх +Z
    to_cam = Matrix.Rotation(math.radians(90), 4, "X") @ cam.matrix_world.inverted()
    arms.matrix_world = to_cam @ arms.matrix_world
    remove(cam)
    report["tris_viewmodel"] = tri_count()
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "veras54_viewmodel.glb"), export_format="GLB", export_yup=True,
                              export_animations=True, export_animation_mode="NLA_TRACKS", export_skins=True,
                              # у основания большого пальца на вершину до 8 костей: с четырьмя перчатка там ломалась
                              export_all_influences=True,
                              export_def_bones=False, export_force_sampling=True, export_materials="EXPORT",
                              export_image_format="AUTO", export_apply=False, export_cameras=False, export_lights=False)
    finish_materials(OUT / "veras54_viewmodel.glb")
    print("VERAS viewmodel saved", flush=True)


def tri_count() -> int:
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in objs("MESH"):
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        t += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return t


# ---------------------------------------------------------------- мировая модель

def _under(ob, prefix: str) -> bool:
    """Объект в иерархии узла, имя которого начинается с prefix (до снятия связей с ригом)."""
    p = ob.parent
    while p is not None:
        if p.name.startswith(prefix):
            return True
        p = p.parent
    return False


def world(detail: bool = False) -> None:
    """Мировая модель. detail — подробная (без упрощения, текстуры 2048) для конструктора оружия,
    где ствол разглядывают вблизи; обычная — упрощённая для вида со стороны."""
    bpy.ops.wm.open_mainfile(filepath=str(SRC / "VERAS54_Reload_Tactical_v04.blend"))
    sc = bpy.context.scene
    write_gloss_mask()
    for ob in objs():
        if ob.animation_data:
            ob.animation_data.action = None
    arms = bpy.data.objects["FPS_ArmsRig"]
    for pb in arms.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    for ob in list(objs()):
        if ob.name.startswith("FPS_Arms"):
            remove(ob)
    drop_extras()
    strip_drivers()
    # складной приклад — отдельной деталью: обвес «приклад» прячет штатный (meta part = stock)
    stock_names = {ob.name for ob in objs("MESH") if _under(ob, "StockFold")}
    # мировые матрицы зафиксировать, связи с ригом снять (статичная модель в боевой позе)
    keep = {}
    for ob in objs("MESH"):
        keep[ob.name] = ob.matrix_world.copy()
    for ob in objs("MESH"):
        for m in [m for m in ob.modifiers if m.type == "ARMATURE"]:
            ob.modifiers.remove(m)
        ob.parent = None
        ob.matrix_world = keep[ob.name]
    for ob in list(objs()):
        if ob.type != "MESH":
            remove(ob)
    apply_mods()
    meshes = objs("MESH")
    # дульное устройство — отдельной деталью (обвес «на резьбу» его прячет: meta part = muzzle_device)
    brake = [o for o in meshes if o.name.startswith(("Muzzle brake", "Brake"))]
    # магазин с патронами — отдельной деталью: игра прячет его (магазин вынут) или меняет на другой
    # (meta part = mag); защёлка ("Magazine catch") остаётся на корпусе
    mag = [o for o in meshes if o.name.startswith(("Magazine_", "Magazine •"))]
    stock = [o for o in meshes if o.name in stock_names]
    rest = [o for o in meshes if o not in brake and o not in mag and o not in stock]
    body = join(rest, "Body")
    md = join(brake, "MuzzleDevice")
    mg = join(mag, "Magazine")
    st = join(stock, "Stock")
    # начало — пистолетная рукоятка; оси игры совпадают с осями glTF после экспорта Y-up
    for ob in (body, md, mg, st):
        if ob is None:
            continue
        ob.matrix_world = Matrix.Translation(-GRIP) @ ob.matrix_world
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    t0 = tri_count()
    ratio = 1.0 if detail else min(1.0, WORLD_TRIS / max(t0, 1))
    if ratio < 1.0:
        # корпус, магазин и приклад — с одним коэффициентом: бюджет мировой модели общий
        for ob in (body, mg, st):
            if ob is None:
                continue
            dec = ob.modifiers.new("dec", "DECIMATE")
            dec.ratio = ratio
            dec.use_collapse_triangulate = True
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
                bpy.ops.object.modifier_apply(modifier="dec")
    for name, p in MARKS.items():
        add_mark(name, p - GRIP, None)
    scale_images(TEX_VIEW if detail else TEX_WORLD)
    name = "veras54_detail.glb" if detail else "veras54.glb"
    if detail:
        report["tris_detail"] = tri_count()
    else:
        report["tris_world_before"] = t0
        report["tris_world"] = tri_count()
    bb = [v.co for v in body.data.vertices]
    report["world_size_m"] = [round(max(c[i] for c in bb) - min(c[i] for c in bb), 3) for i in range(3)]
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / name), export_format="GLB", export_yup=True,
                              export_animations=False, export_materials="EXPORT", export_image_format="AUTO",
                              export_apply=True, export_cameras=False, export_lights=False)
    finish_materials(OUT / name)
    print("VERAS world saved", name, flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["viewmodel", "world"]
    if "viewmodel" in args:
        viewmodel()
    if "world" in args:
        world()
    if "detail" in args or "world" in args:
        world(detail=True)
    path = OUT / "veras54.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old.update(report)
    path.write_text(json.dumps(old, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("VERAS report", report, flush=True)
