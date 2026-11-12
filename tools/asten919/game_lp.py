"""АСТЕН-919: игровая сетка из принятой high-poly (отделка и износ v02) — узлы под общий риг пистолета игры.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/asten919/game_lp.py
High-poly — плотные сетки OpenVDB без петель, игровая сетка получается упрощением (Decimate Collapse по бюджету
детали). У деталей с мелким рельефом (рамка: пупырышки, шов, знак; затвор: гравировка) упрощается не сама high-poly,
а та же деталь, собранная тем же построителем без рельефа (ASTEN919_PLAIN=1 python -X utf8 tools/asten919/build.py
_asset_src/asten919/plain Frame Slide Front_Sight Serial_Plate --k 1.6): иначе бюджет уходит в обломки пупырышков и
букв. Рельеф целиком — в карте нормалей, запечённой с настоящей high-poly. Каждая подвижная
или съёмная деталь — свой узел (WeaponRig.PART_NAMES): Frame, Slide, Barrel, Trigger, SlideStop, MagCatch, Magazine
(с Rounds → Round_01…17, 1 — верхний), ещё SlideLock; дульная гайка резьбы — сетка MuzzleDevice (обвес на резьбу её
прячет), крышка выреза под коллиматор — своя сетка MosCover. Ствол игровой модели — вариант с резьбой: оружие в игре
принимает дульные устройства THREAD_9, и владелец в составе заказал ствол с резьбой.
Развёртка GameUV — общим модулем tools/asset_kit/uv.py (острова по изломам 60°, плотность по видимости и точкам
глаза, жёсткие рёбра на швах). Атласы: Slide (затвор, ствол, стальные органы управления, возвратная пружина), Frame
(рамка с вкладышами, спуск), Magazine (магазин, подаватель, патрон).
→ _asset_src/asten919/game/lp/ASTEN919_Game_LP.blend, parts.json (узлы, оси, метки, исходные детали, бюджеты)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
from asset_kit import uv as kit_uv  # noqa: E402
import dims as D  # noqa: E402

SRC = "E:/Models Blender/WEAPONS/АСТЕН-919/АСТЕН-919_износ_этап2_v02.blend"
OUT = ROOT / "_asset_src/asten919/game/lp"
PLAIN = ROOT / "_asset_src/asten919/plain"       # поля деталей без мелкого рельефа
MM = 0.001
ATLAS_SIZE = {"Slide": 4096, "Frame": 4096, "Magazine": 2048}
MATNAME = {a: f"GAME • {a} • 100" for a in ATLAS_SIZE}
ROUND_TRIS = 72
# игровая сетка: (имя сетки, узел, атлас, [(деталь high-poly, бюджет треугольников), …])
MESHES = [
    ("Frame_Mesh", "Frame", "Frame", [("Frame", 9000)]),
    ("FrameParts_Mesh", "Frame", "Frame", [("Locking_Block", 500), ("Trigger_Housing", 300), ("Ejector", 80),
                                           ("Serial_Plate", 60), ("Pin_Locking_Block", 60), ("Pin_Trigger", 60),
                                           ("Pin_Trigger_Housing", 60)]),
    ("RecoilSpring_Mesh", "Frame", "Slide", [("Guide_Rod", 260), ("Recoil_Spring_Outer", 1200)]),
    ("Slide_Mesh", "Slide", "Slide", [("Slide", 7200)]),
    ("SlideParts_Mesh", "Slide", "Slide", [("Slide_Cover_Plate", 420), ("Extractor", 180), ("MOS_Screw_L", 90),
                                           ("MOS_Screw_R", 90), ("Front_Sight", 300), ("Rear_Sight", 320)]),
    ("MosCover_Mesh", "Slide", "Slide", [("MOS_Cover_Plate", 260)]),
    ("Barrel_Mesh", "Barrel", "Slide", [("Barrel_Threaded", 1500)]),
    ("MuzzleDevice_Mesh", "Barrel", "Slide", [("Thread_Protector", 520)]),
    ("Trigger_Mesh", "Trigger", "Frame", [("Trigger", 620), ("Trigger_Safety", 160), ("Trigger_Safety_Pin", 24)]),
    ("SlideStop_Mesh", "SlideStop", "Slide", [("Slide_Stop", 520)]),
    ("SlideLock_Mesh", "SlideLock", "Slide", [("Slide_Lock", 360)]),
    ("MagCatch_Mesh", "MagCatch", "Slide", [("Mag_Catch", 460)]),
    ("Magazine_Mesh", "Magazine", "Magazine", [("Magazine_Body", 2200), ("Magazine_Floorplate", 420),
                                               ("Magazine_Insert", 120)]),
    ("Follower_Mesh", "Magazine", "Magazine", [("Magazine_Follower", 260)]),
]
log = lambda *a: print("ASTEN_LP", *a, flush=True)  # noqa: E731


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def plain_copy(hname, name, coll):
    """Деталь без мелкого рельефа из поля расстояний (как assemble.field_mesh, без своих нормалей) или None."""
    path = PLAIN / f"{hname}.npz"
    if not path.exists():
        return None
    import numpy as np
    import openvdb as vdb
    d = np.load(str(path))
    A = d["field"].astype(np.float32)
    h = float(d["h"])
    g = vdb.FloatGrid(background=4 * h)
    g.copyFromArray(A, tolerance=0.0)
    g.transform = vdb.createLinearTransform(voxelSize=h)
    g.gridClass = vdb.GridClass.LEVEL_SET
    pts, tr, qd = g.convertToPolygons(isovalue=0.0, adaptivity=0.25)
    pts = (pts + d["lo"][None, :]) * MM
    faces = [tuple(int(i) for i in f[::-1]) for f in tr] + [tuple(int(i) for i in f[::-1]) for f in qd]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts.tolist()], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def world_copy(o, name, coll):
    me = o.data.copy()
    me.transform(o.matrix_world)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def strip(me) -> None:
    """Без развёрток и своих нормалей исходника: сетка упрощается свободно, развёртка — заново."""
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in ("sharp_edge", "sharp_face", "custom_normal", "uv_group", "uv_stack"):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    me.materials.clear()


def simplify(o, budget: int) -> int:
    strip(o.data)
    select_only(o)
    for _ in range(8):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new("budget", "DECIMATE")
        d.ratio = max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    t = o.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=t.name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def deviation(lp, hp_objs) -> tuple:
    """Отклонение игровой сетки от исходника, мм: наибольшее и среднее по вершинам."""
    verts, polys = [], []
    for h in hp_objs:
        base = len(verts)
        m = h.matrix_world
        verts += [m @ v.co for v in h.data.vertices]
        polys += [[base + i for i in p.vertices] for p in h.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    ds = [bvh.find_nearest(v.co)[3] for v in lp.data.vertices]
    ds = [x for x in ds if x is not None]
    return (round(max(ds) * 1000, 2), round(sum(ds) / len(ds) * 1000, 3)) if ds else (0.0, 0.0)


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = name
    j.data.name = name
    return j


def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)

    def show(lc):                     # вариант ствола с резьбой выключен в слое вида — нужен
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            show(ch)
    show(bpy.context.view_layer.layer_collection)
    ctl = bpy.data.objects["ASTEN919_Controls"]
    for k in ("slide", "stop", "trigger", "trigger_safety", "mag_catch", "slide_lock", "mag_out"):
        ctl[k] = 0.0
    ctl.update_tag()
    bpy.context.view_layer.update()
    hp = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    coll = bpy.data.collections.new("GAME")
    bpy.context.scene.collection.children.link(coll)
    OUT.mkdir(parents=True, exist_ok=True)

    # метки и оси узлов в осях исходника, м (+X дуло, +Z верх, −Y — правая сторона стрелка)
    bt = hp["Barrel_Threaded"]
    muzzle_x = max((bt.matrix_world @ v.co).x for v in bt.data.vertices)
    std = hp["Barrel"]
    muzzle_std = max((std.matrix_world @ v.co).x for v in std.data.vertices)
    sight_z = (D.SLIDE_TOP + 4.3) * MM
    px, pz = D.PIN_TRIGGER
    marks = {"Muzzle": [muzzle_x, 0.0, 0.0], "SightFront": [D.FSIGHT_X * MM, 0.0, sight_z],
             "SightRear": [D.RSIGHT_X * MM, 0.0, sight_z],
             # начало осей игры — как у прежней модели игры: 157,7 мм позади среза штатного ствола, 65,2 мм ниже оси
             "Origin": [muzzle_std - 0.1577, 0.0, -0.0652]}
    pivots = {"Frame": [0.0, 0.0, 0.0], "Slide": [0.0, 0.0, 0.0], "Barrel": [0.0, 0.0, 0.0],
              "Trigger": [px * MM, 0.0, pz * MM], "SlideStop": [px * MM, 0.0, pz * MM],
              "SlideLock": [D.LOCK_C[0] * MM, 0.0, D.LOCK_C[1] * MM],
              "MagCatch": [D.CATCH_C[0] * MM, 0.0, D.CATCH_C[1] * MM],
              "Magazine": [D.MAG_REF[0] * MM, 0.0, D.MAG_REF[1] * MM]}
    rec = {"source": SRC, "axes_source": "+X дуло, +Z верх, −Y правая сторона стрелка; м", "marks": marks,
           "pivots": pivots, "nodes": {}, "atlases": {}, "rounds": []}

    game = []
    for name, node, atlas, sources in MESHES:
        pieces = []
        for hname, budget in sources:
            c = plain_copy(hname, f"_{hname}", coll) or world_copy(hp[hname], f"_{hname}", coll)
            n0 = tris(c.data)
            n = simplify(c, min(budget, n0))
            dv = deviation(c, [hp[hname]])
            log(f"{hname}: {n0} → {n} треугольников, отклонение наиб. {dv[0]} мм, среднее {dv[1]} мм")
            pieces.append(c)
        j = join(pieces, name)
        j.data.materials.clear()
        j.data.materials.append(bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas]))
        for p in j.data.polygons:
            p.material_index = 0
        j["atlas"], j["node"], j["hp"] = atlas, node, [s for s, _ in sources]
        game.append(j)
        rec["nodes"][name] = {"node": node, "atlas": atlas, "tris": tris(j.data), "hp": list(j["hp"])}

    # патрон: одна сетка на все 17 мест; места — по патронам исходника (Round_01 — верхний), в осях исходника
    r0 = hp["Round_01"]
    rd = bpy.data.objects.new("Round_Mesh", r0.data.copy())
    coll.objects.link(rd)
    simplify(rd, ROUND_TRIS)
    rd.data.materials.clear()
    rd.data.materials.append(bpy.data.materials.get(MATNAME["Magazine"]) or bpy.data.materials.new(MATNAME["Magazine"]))
    rd["atlas"], rd["node"], rd["hp"] = "Magazine", "Round", ["Round_01"]
    rd.matrix_world = r0.matrix_world.copy()
    rec["nodes"]["Round_Mesh"] = {"node": "Round", "atlas": "Magazine", "tris": tris(rd.data), "hp": ["Round_01"]}
    for i in range(1, 18):
        m = hp[f"Round_{i:02d}"].matrix_world
        rec["rounds"].append([list(row) for row in m])
    game.append(rd)
    bpy.context.view_layer.update()

    # позы для видимости: затвор отведён, магазин вынут
    a = math.radians(D.GRIP_DEG)
    out = Vector((-math.sin(a), 0.0, -math.cos(a))) * (D.MAG_OUT * MM)
    poses = {"rest": {}, "slide_back": {"Slide": Matrix.Translation((-D.SLIDE_TRAVEL * MM, 0, 0))},
             "mag_out": {"Magazine": Matrix.Translation(out), "Round": Matrix.Translation(out)}}
    sr = Vector(marks["SightRear"])
    # точки глаза (оси исходника): пистолет на вытянутых руках — от бедра (левее и выше) и в прицеливании
    eyes = [kit_uv.Eye((sr.x - 0.30, 0.07, sr.z + 0.07), name="hip"),
            kit_uv.Eye((sr.x - 0.34, 0.0, sr.z), k_max=kit_uv.ADS_K, name="ads")]
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o["atlas"] == atlas]
        kit_uv.smart_unwrap(objs)
        cls = kit_uv.visibility(objs, poses, lambda o: o["node"])
        rep = kit_uv.layout(objs, size, classes=cls, eyes=eyes if atlas != "Magazine" else [], log=log)
        kit_uv.harden_on_seams(objs)
        rep["report"] = kit_uv.report(objs, size, classes=cls)
        rep["verify"] = kit_uv.verify(objs, size, classes=cls)
        rec["atlases"][atlas] = {"size": size, "objects": [o.name for o in objs], **rep}
        log("атлас", atlas, size, rep["report"])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True
        rec["nodes"][o.name]["tris"] = tris(o.data)
    rec["tris_first_person"] = sum(v["tris"] for k, v in rec["nodes"].items() if k != "Round_Mesh") + 17 * rec["nodes"]["Round_Mesh"]["tris"]
    for o in list(bpy.data.objects):
        if o not in game:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / "ASTEN919_Game_LP.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / "parts.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding="utf-8",
                                    newline="\n")
    log("сохранено", path, "в руках", rec["tris_first_person"])


if __name__ == "__main__":
    main()
