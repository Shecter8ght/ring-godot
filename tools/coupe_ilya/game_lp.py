"""Купе Ильи: игровая сетка — LOD0 ~150 тыс. треугольников, LOD1 ~50 тыс., LOD2 ~12 тыс. — и развёртки атласов.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/game_lp.py -- <отделка.blend>

Источник — принятая отделка (textured/Coupe_Ilya_tex_v01.blend на форме v05, владелец 2026-10-18). Каждая сетка
high-poly упрощается схлопыванием рёбер по бюджету своей группы; общие сетки (колесо на четыре места, как
в исходнике) упрощаются и развёртываются один раз — одна развёртка на все четыре колеса.
Бюджет и карты (владелец 2026-10-18): ближняя ~150 тыс., дальше 50 и 12 тыс.; атлас кузова 4K, остальные 2K —
стёкла (прозрачные), колесо, моторный отсек, салон. Мелкие светящиеся и зеркальные детали — постоянные материалы
без карт. Плотность текселей одна на атлас; скрытое (подкрылки, днище, задники решёток) — мелкими островами.
Жёсткие рёбра — только по швам развёртки и при изломе больше HARD_DEG: остальное сглаживает запечённая нормаль.
→ _asset_src/coupe_ilya_game/lp/Coupe_Game_LP.blend и parts.json (для game_bake.py и game_export.py).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(sys.argv[sys.argv.index("--") + 1])
WORK = ROOT / "_asset_src/coupe_ilya_game/lp"
WORK.mkdir(parents=True, exist_ok=True)

ATLAS_SIZE = {"body": 4096, "glass": 2048, "wheel": 2048, "bay": 2048, "interior": 2048}
UV_MARGIN_PX = {"body": 8, "glass": 6, "wheel": 6, "bay": 6, "interior": 6}
GLASS = {"glass", "lamp_glass", "lamp_red"}
CONST = {"lamp_drl", "lamp_red_led", "lens", "mirror", "screen_on", "screen_off"}
GROUP_ATLAS = {"body": "body", "glass": "glass", "wheel": "wheel", "wheel_state": "wheel", "bay": "bay",
               "interior": "interior", "const": None}
# уникальные треугольники групп: LOD0, LOD1, LOD2 (колесо — одно на четыре места)
BUDGET = {"body": (72000, 24000, 7000), "glass": (6000, 2400, 700), "wheel_state": (1200, 400, 100),
          "bay": (12000, 3000, 600), "interior": (18000, 5000, 800), "const": (5000, 1200, 300)}
WHEEL = {"Wheel_Rim_Face": (5200, 1300, 260), "Wheel_Tire": (2200, 600, 160), "Wheel_Rim_Barrel": (900, 300, 80),
         "Wheel_Brake_Disc": (900, 250, 60), "Wheel_Caliper": (450, 120, 30), "Wheel_Lug_Nuts": (300, 80, 0),
         "Wheel_Center_Badge": (31, 31, 0)}
# вес детали в своей группе: скрытое и пересечённые сверх меры протяжки — меньше
WEIGHT = {"Under_Tray": 0.35, "Grille_Back": 0.35, "Intake_Back_": 0.35, "Lower_Back": 0.35,
          "Plate_Recess_Floor": 0.35, "Lightbar_Reflector": 0.5, "Belt_Molding_": 0.45, "Sill_Trim_": 0.5,
          "Grille_Slats": 0.8, "Intake_Fins_": 0.7, "Headliner": 0.15, "Headlamp_DRL_": 0.4, "Taillamp_LED_": 0.4}
# доля места в атласе (плотность текселей относительно атласа): скрытое и тёмное — меньше; колёсная ниша,
# кирпичи и кулак — точка фото по заданию, им полная доля
UV_SCALE = {"Liner_": 0.6, "Under_Tray": 0.2, "Grille_Back": 0.3, "Intake_Back_": 0.3, "Lower_Back": 0.3,
            "Plate_Recess_Floor": 0.4, "Lightbar_Reflector": 0.4, "Taillamp_Reflector_": 0.6, "Floor": 0.5,
            "Headliner": 0.6, "Bay_Aprons": 0.8}
# в LOD2 (с 40 м) мелочь не нужна
DROP_LOD2 = ("Badge", "Lug_Nuts", "Dash_Vents", "Steering_Badge", "Engine_Badge", "Battery_Label", "Battery_Posts",
             "Cable_Clamps", "Radiator_Hose_Clamps", "Fuse_Box", "Brake_Reservoir", "Plate_Recess_Floor",
             "Sill_Trim_Fragment", "Headlamp_Lenses", "Headlamp_Reflector", "Screens_")
HARD_DEG = 40.0
# открытые листы (панели, стёкла, рассеиватели, подкрылки, обивки): шов по излому больше SHEET_SEAM_DEG и развёртка
# с сохранением углов — лист одним островом и полосы загнутых кромок. «Умная» развёртка дробила кромки на сотни
# островов, и поля вокруг каждого съедали атлас (занято было 23 %, так — около 60 %).
# (передний бампер и диффузор с вырезами лист искажал в 4–5,5 раза по площади — они развёртываются «по углу»)
SHEETS = ("Hood", "Fender_", "Door_L", "Door_R", "Bodyside_", "Roof", "Trunk_Lid", "Bumper_R", "Skirt_", "Cowl", "Glass_", "Headlamp_L", "Headlamp_R", "Taillamp_L", "Taillamp_R", "Lightbar", "Liner_", "Under_Tray",
          "Plate_Recess_Floor", "Headliner")
SHEET_SEAM_DEG = 50.0
log = lambda *a: print("COUPE_LP", *a, flush=True)


def pick(table: dict, name: str, default: float) -> float:
    for k, v in table.items():
        if name.startswith(k):
            return v
    return default


def tris_of(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


bpy.ops.wm.open_mainfile(filepath=str(SRC))
bpy.context.preferences.use_preferences_save = False
src_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
dg = bpy.context.evaluated_depsgraph_get()
HP = [o for o in bpy.data.objects if o.type in ("MESH", "FONT")]


def group_of(o) -> str:
    coll = o.users_collection[0].name if o.users_collection else ""
    mat = o.data.materials[0].name if o.type == "MESH" and o.data.materials and o.data.materials[0] else ""
    if o.parent is not None and o.parent.name.startswith("Wheel_"):
        return "wheel"
    if mat in CONST:
        return "const"
    if coll == "State_Wheel_FL_Off":
        return "wheel_state"
    if coll == "EngineBay" or coll.startswith("State_Battery") or o.name == "Hood_Inner":
        return "bay"
    if coll == "Interior":
        return "interior"
    if mat in GLASS:
        return "glass"
    return "body"


# --- 1. Уникальные сетки и их представители ---------------------------------------------------------
meshes: dict[str, dict] = {}            # ключ → описание
obj_key: dict[str, str] = {}
for o in HP:
    key = o.data.name if o.type == "MESH" else o.name
    obj_key[o.name] = key
    if key not in meshes:
        # колесо — по переднему левому (оно и снимается по заданию)
        meshes[key] = {"rep_hp": o.name, "group": group_of(o)}
    elif o.name.endswith("_FL"):
        meshes[key]["rep_hp"] = o.name
hp_mesh: dict[str, bpy.types.Mesh] = {}
for key, rec in meshes.items():
    o = bpy.data.objects[rec["rep_hp"]]
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    me.name = "HPEVAL•" + key
    hp_mesh[key] = me
    rec["hp_tris"] = tris_of(me)
    mats = [m.name for m in (o.data.materials if o.type == "MESH" else o.data.materials) if m]
    rec["material"] = mats[0] if mats else "plate_text"


# --- 2. Цели по группам -----------------------------------------------------------------------------
def solve(items: list[tuple[int, float, int]], budget: int) -> float:
    lo, hi = 0.0, 20.0
    for _ in range(60):
        r = (lo + hi) / 2
        s = sum(min(o, max(f, o * r * w)) for o, w, f in items)
        lo, hi = (r, hi) if s <= budget else (lo, r)
    return lo


def targets(lod: int, base: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for g, budget in BUDGET.items():
        keys = [k for k, r in meshes.items() if r["group"] == g]
        items = [(base[k], pick(WEIGHT, meshes[k]["rep_hp"], 1.0), min(base[k], 150 if lod == 0 else 60)) for k in keys]
        r = solve(items, budget[lod])
        for k, (o, w, f) in zip(keys, items):
            out[k] = int(min(o, max(f, o * r * w)))
    for k, rec in meshes.items():
        if rec["group"] == "wheel":
            out[k] = min(base[k], WHEEL[k][lod]) if k in WHEEL else base[k]
    if lod == 2:
        for k, rec in meshes.items():
            if rec["rep_hp"].startswith(DROP_LOD2) or out.get(k, 1) == 0:
                out[k] = 0
    return out


def decimated(src: bpy.types.Mesh, target: int, name: str) -> bpy.types.Mesh:
    tmp = bpy.data.objects.new("_tmp", src)
    bpy.context.scene.collection.objects.link(tmp)
    n = tris_of(src)
    if target < n:
        m = tmp.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(target / n, 1e-4)
        m.use_collapse_triangulate = True
    tmp.modifiers.new("tri", "TRIANGULATE")
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    me.name = name
    bpy.data.objects.remove(tmp)
    return me


hp_tris = {k: r["hp_tris"] for k, r in meshes.items()}
T0 = targets(0, hp_tris)
lp_mesh: dict[str, bpy.types.Mesh] = {}
for key, rec in meshes.items():
    lp_mesh[key] = decimated(hp_mesh[key], T0[key], "LP0•" + key)
    rec["tris"] = [tris_of(lp_mesh[key])]
log("LOD0 уникальных", sum(r["tris"][0] for r in meshes.values()))

# --- 3. Материалы игры: один на атлас, постоянные — по образцу high-poly ----------------------------
game_mat: dict[str, bpy.types.Material] = {}


def mat_for(key: str) -> bpy.types.Material:
    rec = meshes[key]
    atlas = GROUP_ATLAS[rec["group"]]
    name = f"GAME • {atlas}" if atlas else f"GAME • const • {rec['material']}"
    if name in game_mat:
        return game_mat[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    if atlas is None:
        src = bpy.data.materials.get(rec["material"])
        p = m.node_tree.nodes["Principled BSDF"]
        sp = src.node_tree.nodes.get("Principled BSDF") if src and src.node_tree else None
        if sp is not None:
            for inp in ("Base Color", "Metallic", "Roughness", "Emission Color", "Emission Strength", "Alpha"):
                if not sp.inputs[inp].is_linked:
                    p.inputs[inp].default_value = sp.inputs[inp].default_value
    game_mat[name] = m
    return m


def clean(me: bpy.types.Mesh, mat: bpy.types.Material) -> None:
    """Только геометрия и своя развёртка: атрибуты масок high-poly и его развёртки игре не нужны."""
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.attributes if a.name.startswith("m_") or a.domain == "POINT" and a.data_type == "FLOAT_COLOR"]:
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    me.materials.clear()
    me.materials.append(mat)
    me.uv_layers.new(name="GameUV")


for key, me in lp_mesh.items():
    clean(me, mat_for(key))

# --- 4. Игровые объекты: та же иерархия (петля капота, места колёс), общие сетки — общие ------------
lp_coll = bpy.data.collections.new("GAME_LOD0")
bpy.context.scene.collection.children.link(lp_coll)
lp_obj: dict[str, bpy.types.Object] = {}
for o in HP:
    key = obj_key[o.name]
    lo = bpy.data.objects.new("LP•" + o.name, lp_mesh[key])
    lo.parent = o.parent
    lo.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    lo.matrix_basis = o.matrix_basis.copy()
    lp_coll.objects.link(lo)
    lp_obj[o.name] = lo
bpy.context.view_layer.update()


# --- 5. Развёртки атласов --------------------------------------------------------------------------
def select_only(objs) -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


for o in bpy.data.objects:
    if not o.name.startswith("LP•") and o.type in ("MESH", "FONT"):
        o.hide_set(True)
def stretch(o) -> float:
    """Растяжение развёртки листа: отношение площадей UV/3D по треугольникам, p95 / p5 (1 — без искажений)."""
    me = o.data
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    uv = np.empty(len(me.uv_layers["GameUV"].data) * 2)
    me.uv_layers["GameUV"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    lt = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("loops", lt)
    vt = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", vt)
    t = uv[lt.reshape(-1, 3)]
    p = co[vt.reshape(-1, 3)]
    a2 = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
    a3 = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    r = a2[a3 > 1e-9] / a3[a3 > 1e-9]
    return float(np.percentile(r, 95) / max(np.percentile(r, 5), 1e-12)) if len(r) else 1.0


for atlas in ATLAS_SIZE:
    keys = [k for k, r in meshes.items() if GROUP_ATLAS[r["group"]] == atlas]
    reps = [lp_obj[meshes[k]["rep_hp"]] for k in keys]
    sheets = [o for o in reps if o.name[3:].startswith(SHEETS) and not o.name[3:].startswith("Door_Handle")]
    rest = [o for o in reps if o not in sheets]
    lim = math.radians(SHEET_SEAM_DEG)
    for o in sheets:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        for e in bm.edges:
            e.seam = len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim
        bm.to_mesh(o.data)
        bm.free()
    for objs, smart in ((sheets, False), (rest, True)):
        if not objs:
            continue
        select_only(objs)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        if smart:
            bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                                     correct_aspect=True, scale_to_bounds=False)
        else:
            bpy.ops.uv.unwrap(method="ANGLE_BASED", fill_holes=False, correct_aspect=True, margin=0.0)
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only(reps)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    for k, o in zip(keys, reps):
        s_uv = pick(UV_SCALE, meshes[k]["rep_hp"], 1.0)
        if s_uv != 1.0:
            uv = o.data.uv_layers["GameUV"].data
            a = np.empty(len(uv) * 2)
            uv.foreach_get("uv", a)
            uv.foreach_set("uv", a * s_uv)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="AXIS_ALIGNED", scale=True, margin_method="FRACTION",
                            margin=UV_MARGIN_PX[atlas] / ATLAS_SIZE[atlas], shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    worst = sorted(((round(stretch(o), 2), o.name[3:]) for o in sheets), reverse=True)[:4]
    used = 0.0
    for o in reps:
        me = o.data
        me.calc_loop_triangles()
        uv = np.empty(len(me.uv_layers["GameUV"].data) * 2)
        me.uv_layers["GameUV"].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        lt = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("loops", lt)
        t = uv[lt.reshape(-1, 3)]
        used += float(np.sum(0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                                          - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))))
    log("развёртка", atlas, len(reps), "сеток, листов", len(sheets), "занято", round(used, 3),
        "— сильнее всего растянуты", worst)
# постоянные материалы — развёртка не нужна, но слой оставляем (экспорт один на всё)


def harden(me: bpy.types.Mesh) -> int:
    """Жёсткое ребро там, где шов развёртки и излом больше HARD_DEG; грани гладкие."""
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.get("GameUV")
    n = 0
    lim = math.radians(HARD_DEG)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = True
        if len(e.link_faces) != 2:
            continue
        if e.calc_face_angle(0.0) < lim:
            continue
        if uvl is None:
            e.smooth = False
            n += 1
            continue
        f0, f1 = e.link_faces
        def uv_at(f, v):
            for lp in f.loops:
                if lp.vert == v:
                    return lp[uvl].uv.copy()
        seam = any((uv_at(f0, v) - uv_at(f1, v)).length > 1e-6 for v in e.verts)
        if seam:
            e.smooth = False
            n += 1
    bm.to_mesh(me)
    bm.free()
    return n


for key, me in lp_mesh.items():
    harden(me)


# --- 6. Лучи запекания: насколько high-poly выходит наружу и уходит внутрь игровой ------------------
def cage(key: str) -> dict[str, float]:
    hp = hp_mesh[key]
    lp = lp_mesh[key]
    lp.calc_loop_triangles()
    co = np.empty(len(lp.vertices) * 3)
    lp.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tri = np.empty(len(lp.loop_triangles) * 3, dtype=np.int64)
    lp.loop_triangles.foreach_get("vertices", tri)
    bvh = BVHTree.FromPolygons([tuple(v) for v in co], tri.reshape(-1, 3).tolist())
    hco = np.empty(len(hp.vertices) * 3)
    hp.vertices.foreach_get("co", hco)
    hco = hco.reshape(-1, 3)
    if len(hco) > 30000:
        hco = hco[np.random.default_rng(7).choice(len(hco), 30000, replace=False)]
    d = []
    for p in hco:
        loc, nrm, _, dist = bvh.find_nearest(p)
        if loc is None:
            continue
        d.append(float(np.dot(np.asarray(p) - np.asarray(loc), np.asarray(nrm))))
    d = np.asarray(d) if d else np.zeros(1)
    out_ = float(np.percentile(np.maximum(d, 0), 99.5))
    in_ = float(np.percentile(np.maximum(-d, 0), 99.5))
    ext = max(0.0015, out_ * 1.3 + 0.0005)
    return {"extrusion_m": round(ext, 5), "max_ray_m": round(ext + max(0.003, in_ * 1.3 + 0.001), 5),
            "dev_out_mm": round(out_ * 1000, 2), "dev_in_mm": round(in_ * 1000, 2)}


for key, rec in meshes.items():
    if GROUP_ATLAS[rec["group"]]:
        rec["cage"] = cage(key)

# --- 7. LOD1 и LOD2: из игровой сетки, развёртка сохраняется -----------------------------------------
for lod in (1, 2):
    T = targets(lod, {k: r["tris"][0] for k, r in meshes.items()})
    coll = bpy.data.collections.new(f"GAME_LOD{lod}")
    bpy.context.scene.collection.children.link(coll)
    lmesh = {}
    for key, rec in meshes.items():
        if T[key] <= 0:
            rec["tris"].append(0)
            continue
        me = decimated(lp_mesh[key], T[key], f"LP{lod}•" + key)
        harden(me)
        lmesh[key] = me
        rec["tris"].append(tris_of(me))
    for o in HP:
        key = obj_key[o.name]
        if key not in lmesh:
            continue
        lo = bpy.data.objects.new(f"LP•{o.name}_LOD{lod}", lmesh[key])
        lo.parent = o.parent
        lo.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        lo.matrix_basis = o.matrix_basis.copy()
        coll.objects.link(lo)


# --- 8. Итог: только игровое, имена — как у исходника ------------------------------------------------
def instances(lod: int) -> int:
    return sum(meshes[obj_key[o.name]]["tris"][lod] for o in HP)


totals = {f"LOD{i}": instances(i) for i in range(3)}
log("итого с повторами колёс", totals)
# состояния и узлы — по коллекциям и родителям исходника (коллекции high-poly уходят вместе с ним)
objects = {o.name: {"mesh": obj_key[o.name], "collection": o.users_collection[0].name if o.users_collection else "",
                    "parent": o.parent.name if o.parent else ""} for o in HP}
for o in HP:
    bpy.data.objects.remove(o, do_unlink=True)
for me in list(hp_mesh.values()):
    bpy.data.meshes.remove(me)
for o in list(bpy.data.objects):
    if o.name.startswith("LP•"):
        o.name = o.name[3:]
        o.hide_set(False)
for c in list(bpy.data.collections):
    if not c.name.startswith("GAME_") and c.name not in ("Body", "Wheels") and not c.all_objects:
        bpy.data.collections.remove(c)
for m in list(bpy.data.materials):
    if not m.name.startswith("GAME •") and m.users == 0:
        bpy.data.materials.remove(m)
try:
    bpy.ops.outliner.orphans_purge(do_recursive=True)
except RuntimeError:
    pass

record = {
    "source": str(SRC), "source_sha256": src_sha, "atlas_size": ATLAS_SIZE, "uv_margin_px": UV_MARGIN_PX,
    "budget": BUDGET, "wheel": WHEEL, "totals": totals, "meshes": meshes, "objects": objects,
}
(WORK / "parts.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(WORK / "Coupe_Game_LP.blend"))
log("сохранено", WORK / "Coupe_Game_LP.blend")
