"""Купе Ильи, радиатор с патрубками: игровая модель предмета car_radiator — сетка, запекание, карты, GLB.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/radiator_game.py -- lp | bake | pack | export | imports

Источник — принятые текстуры `models/items/Radiator_Ilya_v01_pbr.blend` (владелец 2026-10-18) на принятой форме v01.
Игровая сетка — тот же генератор radiator.py с меньшей плотностью (Q_PART, по деталям): те же формы, реже сегменты; сердцевина —
брусок, лапки обжима и надпись бирки — в картах. Два атласа 2K (~2,5 пкс/мм):
  core — передняя и задняя грани сердцевины (зигзаг ламелей различим);
  body — всё остальное.
Запекание — каждая игровая деталь только со своих high-poly (соседние в лучи не попадают); каналы — как у кузова
купе (game_bake.py): color — цвет со стеков UCUPaint, normal — касательное пространство OpenGL, mra — металл и
шероховатость, ao — AO самой игровой сетки. Ламели — листы без толщины вдоль луча: на время запекания им даётся
толщина 0,5 мм, а посередине сердцевины — тёмная подложка (каналы между ламелями тёмные, как вглубь).
  lp     → _asset_src/car_radiator_game/Radiator_Game_LP.blend, parts.json
  bake   → _asset_src/car_radiator_game/raw/<атлас>_<канал>.png
  pack   → _asset_src/car_radiator_game/game/car_radiator_<атлас>_{albedo,normal,orm}.png
  export → assets/items/models/car/car_radiator.glb (+ .json); просмотр — <библиотека>/game/Radiator_Ilya_Game_v01.blend
  imports — после `tools/godot.cmd --headless --import`: сжатие карт как у ПМ и кузова; затем импорт ещё раз
Оси: как в машине и у high-poly (+X — левый борт, −Y — перёд), начало — под нижними шипами по центру; экспорт glTF
переводит в оси Godot (Y вверх, перёд машины → +Z).
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

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import radiator as rad  # noqa: E402

LIB = Path("E:/Models Blender/VEHICLES/Купе Ильи")
HP_FILE = LIB / "models/items/Radiator_Ilya_v01_pbr.blend"
WORK = ROOT / "_asset_src/car_radiator_game"
LP_FILE = WORK / "Radiator_Game_LP.blend"
RAW = WORK / "raw"
GAME = WORK / "game"
OUT = ROOT / "assets/items/models/car"
VIEW = LIB / "game/Radiator_Ilya_Game_v01.blend"
# плотность по деталям: круглое, что видно вблизи (патрубки, горловины, хомуты), — гуще; плоское — реже
Q_PART = {"frame": 0.4, "tank": 0.5, "plug": 0.5, "hose": 0.75, "clamp": 0.45, "wire": 0.4, "tag": 0.5}
TAG_UV_SCALE = 2.0                      # бирка с надписью — вдвое плотнее остального в атласе
ATLAS = {"core": 2048, "body": 2048}
UV = "GameUV"
SAMPLES = {"color": 16, "mra": 16, "normal": 8, "ao": 64}
AO_DIST = 0.05
AO_STRENGTH = 0.6
MARGIN = 6
FIN_BAKE_T = 0.0005                     # толщина ламелей на время запекания
BACKFILL = (0.012, 0.012, 0.013)        # тёмная глубина каналов сердцевины
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "lp"
log = lambda *a: print("RAD_GAME", *a, flush=True)  # noqa: E731


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- игровая сетка

def core_box():
    """Сердцевина бруском: передняя и задняя грани несут запечённые трубки и ламели, остальные скрыты рамкой."""
    x0, x1 = -rad.CORE_X, rad.CORE_X
    y0, y1 = rad.Y_C - rad.CORE_D / 2, rad.Y_C + rad.CORE_D / 2
    z0, z1 = rad.CORE_Z0, rad.CORE_Z1
    V = np.array([(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    F = [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]
    return V, F


def lp_parts() -> list[tuple[str, str, np.ndarray, list, list[str]]]:
    """(игровая деталь, атлас, вершины, грани, её high-poly) — в осях машины."""
    def at(kind: str, fn, *args):
        rad.Q = Q_PART[kind]
        try:
            return fn(*args)
        finally:
            rad.Q = 1.0
    hoses = at("hose", rad.hoses_and_clamps)
    clamps = at("clamp", rad.hoses_and_clamps)
    return [
        ("Core", "core", *core_box(), ["Radiator_Core_Tubes", "Radiator_Core_Fins", "BAKE_Backfill"]),
        ("Frame", "body", *at("frame", rad.core_frame), ["Radiator_Core_Frame"]),
        ("Tank_L", "body", *at("tank", rad.tank, 1), ["Radiator_Tank_L"]),
        ("Tank_R", "body", *at("tank", rad.tank, -1), ["Radiator_Tank_R"]),
        ("Drain_Plug", "body", *at("plug", rad.drain_plug), ["Radiator_Drain_Plug"]),
        ("Hose_Upper", "body", *hoses["upper"][0], ["Hose_Upper"]),
        ("Hose_Upper_Clamps", "body", *clamps["upper"][1], ["Hose_Upper_Clamps"]),
        ("Hose_Lower", "body", *hoses["lower"][0], ["Hose_Lower"]),
        ("Hose_Lower_Clamps", "body", *clamps["lower"][1], ["Hose_Lower_Clamps"]),
        ("Tag_Wire", "body", *at("wire", rad.tag_wire), ["Tag_Wire"]),
        ("Tag_Card", "body", *at("tag", rad.tag_card), ["Tag_Card", "Tag_Text"]),
        ("Tag_Rings", "body", *at("tag", rad.tag_rings), ["Tag_Rings"]),
    ]


def game_material(atlas: str) -> bpy.types.Material:
    name = f"GAME • radiator_{atlas}"
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def mesh_object(name: str, V, F, mat) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V - rad.CAR_POS], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(40))
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def core_uv(ob) -> None:
    """Передняя грань — низ атласа, задняя — над ней; скрытые грани — крошечным пятном в углу."""
    me = ob.data
    uv = me.uv_layers.new(name=UV)
    w = 2 * rad.CORE_X
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = 0.01 + (co.x + rad.CORE_X) / w * 0.98
            v = 0.01 + (co.z - (rad.CORE_Z0 - rad.CAR_POS[2])) / w * 0.98
            if n.y < -0.9:
                uv.data[li].uv = (u, v)
            elif n.y > 0.9:
                uv.data[li].uv = (u, v + 0.5)
            else:
                uv.data[li].uv = (0.96 + 0.02 * u, 0.96 + 0.02 * v)


def body_uv(obs) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.data.uv_layers.new(name=UV)
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in obs:                                   # бирку — крупнее: надпись должна читаться вблизи
        if o.name == "Tag_Card":
            uv = o.data.uv_layers[UV].data
            a = np.empty(len(uv) * 2, np.float32)
            uv.foreach_get("uv", a)
            a = a.reshape(-1, 2)
            a = (a - a.mean(0)) * TAG_UV_SCALE + a.mean(0)
            uv.foreach_set("uv", a.ravel())
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="ADD", margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")


def density(obs, px: int) -> float:
    """Пикселей на миллиметр: корень отношения площади развёртки к площади поверхности."""
    a3 = auv = 0.0
    for o in obs:
        me = o.data
        uv = me.uv_layers[UV].data
        for p in me.polygons:
            a3 += p.area
            pts = [uv[i].uv for i in p.loop_indices]
            for k in range(1, len(pts) - 1):
                auv += abs((pts[k].x - pts[0].x) * (pts[k + 1].y - pts[0].y)
                           - (pts[k + 1].x - pts[0].x) * (pts[k].y - pts[0].y)) / 2
    return math.sqrt(auv / max(a3, 1e-12)) * px / 1000.0


def lp() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    WORK.mkdir(parents=True, exist_ok=True)
    parts = lp_parts()
    rec = {"source": str(HP_FILE), "source_sha256": sha(HP_FILE), "q": Q_PART, "atlas_size": ATLAS, "parts": {}}
    by_atlas: dict[str, list] = {"core": [], "body": []}
    for name, atlas, V, F, hp in parts:
        ob = mesh_object(name, V, F, game_material(atlas))
        by_atlas[atlas].append(ob)
        rec["parts"][name] = {"atlas": atlas, "hp": hp}
    # грани бруска — каждая со своими вершинами: без клетки Blender пускает лучи вдоль сглаженных нормалей
    # вершин, и у бруска они расходились бы веером от углов (ламели смазывались к краям)
    core = by_atlas["core"][0]
    bm = bmesh.new()
    bm.from_mesh(core.data)
    bmesh.ops.split_edges(bm, edges=bm.edges[:])
    bm.to_mesh(core.data)
    bm.free()
    core_uv(core)
    body_uv(by_atlas["body"])
    total = 0
    for o in bpy.data.objects:
        o.data.calc_loop_triangles()
        t = len(o.data.loop_triangles)
        rec["parts"][o.name]["tris"] = t
        total += t
        log(f"  {o.name}: треугольников {t}")
    rec["tris"] = total
    rec["px_per_mm"] = {"core_front": round(ATLAS["core"] * 0.98 / (2 * rad.CORE_X) / 1000, 2),
                        "body": round(density(by_atlas["body"], ATLAS["body"]), 2)}
    log("треугольников всего", total, "плотность", rec["px_per_mm"])
    (WORK / "parts.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(LP_FILE))
    log("сохранено", LP_FILE)


# ---------------------------------------------------------------- запекание

def _source(nt, name: str):
    p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if p is None:
        return None, 0.0
    inp = p.inputs[name]
    return (inp.links[0].from_socket, None) if inp.links else (None, inp.default_value)


def _feed(nt, sock_in, src) -> None:
    sock, value = src
    for link in list(sock_in.links):
        nt.links.remove(link)
    if sock is not None:
        nt.links.new(sock, sock_in)
    elif hasattr(value, "__len__"):
        sock_in.default_value = tuple(value)[:len(sock_in.default_value)]
    else:
        sock_in.default_value = (value, value, value, 1.0) if sock_in.type == "RGBA" else value


def _node(nt, kind: str, name: str):
    n = nt.nodes.get(name) or nt.nodes.new(kind)
    n.name = name
    return n


_saved: dict[str, object] = {}


def route(channel: str) -> None:
    """Канал → Emission у материалов high-poly (для EMIT); normal — обратно BSDF."""
    for m in bpy.data.materials:
        if m.name.startswith("GAME •") or m.node_tree is None:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None:
            continue
        if m.name not in _saved:
            link = out.inputs["Surface"].links[0] if out.inputs["Surface"].links else None
            _saved[m.name] = link.from_socket if link else None
        if channel == "normal":
            if _saved[m.name] is not None:
                nt.links.new(_saved[m.name], out.inputs["Surface"])
            continue
        emit = _node(nt, "ShaderNodeEmission", "BAKE_EMIT")
        emit.inputs["Strength"].default_value = 1.0
        if channel == "color":
            _feed(nt, emit.inputs["Color"], _source(nt, "Base Color"))
        else:
            comb = _node(nt, "ShaderNodeCombineColor", "BAKE_COMB")
            _feed(nt, comb.inputs["Red"], _source(nt, "Metallic"))
            _feed(nt, comb.inputs["Green"], _source(nt, "Roughness"))
            comb.inputs["Blue"].default_value = 1.0          # отметка «запечено» для полей
            nt.links.new(comb.outputs["Color"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])


def bake() -> None:
    bpy.context.preferences.use_preferences_save = False
    bpy.ops.wm.open_mainfile(filepath=str(HP_FILE))
    S = bpy.context.scene
    # ламели — толщина на время запекания (в исходник не сохраняется)
    sol = bpy.data.objects["Radiator_Core_Fins"].modifiers.new("BAKE_thickness", "SOLIDIFY")
    sol.thickness = FIN_BAKE_T
    sol.offset = 0.0
    # тёмная подложка посередине сердцевины
    z0, z1 = rad.CORE_Z0 - rad.CAR_POS[2], rad.CORE_Z1 - rad.CAR_POS[2]
    me = bpy.data.meshes.new("BAKE_Backfill")
    # две плоскости в 1 мм: лицом вперёд и лицом назад — луч с каждой стороны видит лицевую (иначе нормаль «внутрь»)
    me.from_pydata([(-rad.CORE_X, -0.0005, z0), (rad.CORE_X, -0.0005, z0), (rad.CORE_X, -0.0005, z1),
                    (-rad.CORE_X, -0.0005, z1), (-rad.CORE_X, 0.0005, z0), (rad.CORE_X, 0.0005, z0),
                    (rad.CORE_X, 0.0005, z1), (-rad.CORE_X, 0.0005, z1)], [], [(0, 1, 2, 3), (4, 7, 6, 5)])
    mat = bpy.data.materials.new("BAKE_backfill")
    mat.use_nodes = True
    bs = mat.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*BACKFILL, 1.0)
    bs.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    fill = bpy.data.objects.new("BAKE_Backfill", me)
    S.collection.objects.link(fill)
    HP = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    rec = json.loads((WORK / "parts.json").read_text(encoding="utf-8"))
    with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in rec["parts"]]
    lpc = bpy.data.collections.new("LP_BAKE")
    S.collection.children.link(lpc)
    LP = {}
    for o in dst.objects:
        lpc.objects.link(o)
        LP[o.name.rsplit(".", 1)[0] if o.name.rsplit(".", 1)[0] in rec["parts"] else o.name] = o
    for o in LP.values():
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
        o.visible_volume_scatter = o.visible_shadow = False
    bpy.context.view_layer.update()
    S.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type != "CPU"
    S.cycles.device = "GPU"
    S.cycles.use_denoising = False
    bk = S.render.bake
    bk.margin_type = "EXTEND"
    bk.normal_space = "TANGENT"
    bk.use_cage = False
    RAW.mkdir(parents=True, exist_ok=True)
    images: dict[tuple[str, str], list] = {}

    def target(o, atlas: str, channel: str):
        key = (atlas, channel)
        if key not in images:
            size = ATLAS[atlas]
            im = bpy.data.images.new(f"{atlas}_{channel}", size, size, alpha=True, float_buffer=(channel == "normal"))
            im.colorspace_settings.name = "sRGB" if channel == "color" else "Non-Color"
            im.generated_color = (0.5, 0.5, 1.0, 0.0) if channel == "normal" else (0, 0, 0, 0)
            images[key] = [im, False]
        for m in o.data.materials:
            m.use_nodes = True
            nt = m.node_tree
            node = _node(nt, "ShaderNodeTexImage", "BAKE_TARGET")
            node.image = images[key][0]
            uvn = _node(nt, "ShaderNodeUVMap", "BAKE_UV")
            uvn.uv_map = UV
            nt.links.new(uvn.outputs["UV"], node.inputs["Vector"])
            nt.nodes.active = node
        return images[key]

    for ch in ("color", "mra", "normal"):
        route(ch)
        S.cycles.samples = SAMPLES[ch]
        for name, info in rec["parts"].items():
            o = LP[name]
            bpy.ops.object.select_all(action="DESELECT")
            for h in info["hp"]:
                HP[h].hide_render = False
                HP[h].select_set(True)
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            t = target(o, info["atlas"], ch)
            core = info["atlas"] == "core"
            bpy.ops.object.bake(type="NORMAL" if ch == "normal" else "EMIT", use_clear=not t[1],
                                use_selected_to_active=True, cage_extrusion=0.001 if core else 0.004,
                                max_ray_distance=0.016 if core else 0.012, margin=MARGIN)
            t[1] = True
        log(ch, "готово")
    # AO игровой сетки: видны только игровые детали
    for o in HP.values():
        o.hide_render = True
    for o in LP.values():
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_shadow = True
    S.world = S.world or bpy.data.worlds.new("AO")
    S.world.light_settings.distance = AO_DIST
    S.cycles.samples = SAMPLES["ao"]
    for name, info in rec["parts"].items():
        o = LP[name]
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        t = target(o, info["atlas"], "ao")
        bpy.ops.object.bake(type="AO", use_clear=not t[1], use_selected_to_active=False, margin=MARGIN)
        t[1] = True
    log("ao", "готово")
    for (atlas, ch), (im, used) in images.items():
        if used:
            im.filepath_raw = str(RAW / f"{atlas}_{ch}.png")
            im.file_format = "PNG"
            im.save()
            log("сохранено", f"{atlas}_{ch}.png")


# ---------------------------------------------------------------- игровые карты

def _load(name: str) -> np.ndarray | None:
    path = RAW / f"{name}.png"
    if not path.exists():
        return None
    im = bpy.data.images.load(str(path))
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def _save(arr: np.ndarray, path: Path, srgb: bool) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    im = bpy.data.images.new(path.stem, w, h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    log("сохранено", path.name)


def _pushpull(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Пустые пиксели — из пирамиды средних по запечённому (дальние mip не тянут чёрный фон в швы)."""
    c = img * mask[..., None]
    wgt = mask.astype(np.float32)
    levels = []
    while c.shape[0] > 1:
        levels.append((c, wgt))
        h, w = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :w * 2].reshape(h, 2, w, 2, -1).sum(axis=(1, 3))
        wgt = wgt[:h * 2, :w * 2].reshape(h, 2, w, 2).sum(axis=(1, 3))
    fill = c / np.maximum(wgt, 1e-6)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c_l.shape[0], :c_l.shape[1]]
        fill = np.where((w_l > 1e-6)[..., None], c_l / np.maximum(w_l, 1e-6)[..., None], up)
    return np.where(mask[..., None], img, fill)


def pack() -> None:
    GAME.mkdir(parents=True, exist_ok=True)
    for atlas in ATLAS:
        color, mra = _load(f"{atlas}_color"), _load(f"{atlas}_mra")
        mask = mra[..., 2] > 0.02
        tag = f"car_radiator_{atlas}"
        _save(_pushpull(color[..., :3], mask), GAME / f"{tag}_albedo.png", True)
        v = _pushpull(_load(f"{atlas}_normal")[..., :3], mask) * 2 - 1
        v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
        _save(v * 0.5 + 0.5, GAME / f"{tag}_normal.png", False)
        rough = _pushpull(mra[..., 1:2], mask)[..., 0]
        metal = _pushpull(mra[..., 0:1], mask)[..., 0]
        ao_raw = _load(f"{atlas}_ao")
        ao = _pushpull(ao_raw[..., :1], mask)[..., 0] if ao_raw is not None else np.ones_like(rough)
        ao = 1.0 - (1.0 - ao) * AO_STRENGTH
        _save(np.dstack([ao, rough, metal]), GAME / f"{tag}_orm.png", False)
        log(atlas, "покрытие", round(float(mask.mean()), 3), "шероховатость", round(float(rough[mask].mean()), 3),
            "металл", round(float(metal[mask].mean()), 3), "AO", round(float(ao[mask].mean()), 3))


# ---------------------------------------------------------------- GLB

def atlas_material(atlas: str) -> None:
    m = game_material(atlas)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
            nt.nodes.remove(n)
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = UV

    def tex(kind: str, space: str):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(GAME / f"car_radiator_{atlas}_{kind}.png"), check_existing=True)
        t.image.colorspace_settings.name = space
        t.image.name = f"car_radiator_{atlas}_{kind}"
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t

    nt.links.new(tex("albedo", "sRGB").outputs["Color"], p.inputs["Base Color"])
    orm = tex("orm", "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], p.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = UV
    nt.links.new(tex("normal", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    g = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [s.name for s in g.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]:
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = g
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    # бирка и проволока тонкие: изнанку видно — без отсечения задних граней
    m.use_backface_culling = False


def export() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(LP_FILE))
    rec = json.loads((WORK / "parts.json").read_text(encoding="utf-8"))
    for a in ATLAS:
        atlas_material(a)
    obs = [o for o in bpy.data.objects if o.type == "MESH"]
    root = bpy.data.objects.new("Car_Radiator", None)
    bpy.context.scene.collection.objects.link(root)
    # одной сеткой (две поверхности — атласы): меньше вызовов отрисовки
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = mesh.data.name = "Car_Radiator_Mesh"
    mesh.parent = root
    mesh["source"] = "Radiator_Ilya_v01_pbr.blend (текстуры приняты 2026-10-18), форма v01; tools/coupe_ilya/radiator_game.py"
    mesh.data.calc_loop_triangles()
    tris = len(mesh.data.loop_triangles)
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    mesh.select_set(True)
    glb = OUT / "car_radiator.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_tangents=True, export_extras=True, export_animations=False,
                              export_cameras=False, export_lights=False, export_image_format="AUTO")
    manifest = {
        "item": "car_radiator", "source": rec["source"], "source_sha256": rec["source_sha256"],
        "triangles": tris, "parts": {k: v["tris"] for k, v in rec["parts"].items()},
        "atlases": {a: f"{s}×{s}: albedo (sRGB), normal (OpenGL), orm (R — AO, G — шероховатость, B — металл)"
                    for a, s in ATLAS.items()},
        "px_per_mm": rec["px_per_mm"],
        "axes": "Blender: +X — левый борт машины, −Y — перёд; в Godot перёд машины → +Z, Y вверх; "
                "начало — под нижними шипами по центру (в машине: (0, −2,02, 0,333) в осях Blender)",
        "lod": "автоматические LOD движка при импорте (как у остальных предметов)",
    }
    (OUT / "car_radiator.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8",
                                           newline="\n")
    log("экспорт", glb, "треугольников", tris, sha(glb)[:16])
    VIEW.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(VIEW))
    log("просмотр", VIEW)


def imports() -> None:
    """Настройки импорта карт после первого `tools/godot.cmd --headless --import` — как у ПМ, Мосина и кузова:
    сжатие VRAM и mip-уровни; нормали — флаг карты нормалей; у ORM — сглаживание шероховатости (G) по нормали."""
    import re

    def setp(text: str, key: str, val: str) -> str:
        pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
        assert pat.search(text), key
        return pat.sub(f"{key}={val}", text)
    res = "res://assets/items/models/car/"
    for f in sorted(OUT.glob("car_radiator_*.png.import")):
        base = f.name[: -len(".import")]
        t = f.read_text(encoding="utf-8")
        t = setp(t, "compress/mode", "2")
        t = setp(t, "mipmaps/generate", "true")
        t = setp(t, "detect_3d/compress_to", "0")
        if base.endswith("_normal.png"):
            t = setp(t, "compress/normal_map", "1")
        elif base.endswith("_orm.png"):
            t = setp(t, "roughness/mode", "3")
            t = setp(t, "roughness/src_normal", f'"{res}{base.replace("_orm.png", "_normal.png")}"')
        f.write_text(t, encoding="utf-8", newline="\n")
        log("импорт", f.name)


if __name__ == "__main__":
    {"lp": lp, "bake": bake, "pack": pack, "export": export, "imports": imports}[MODE]()
