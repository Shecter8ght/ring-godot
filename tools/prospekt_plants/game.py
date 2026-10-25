"""Растения «Проспекта» — игровая версия (bpy), из принятой формы v01 и PBR v01:

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_plants/game.py -- [birch linden poplar lilac hedge] [atlas] [meshes]

  atlas  — модули веточек из PBR-файла (материалы UCUPaint) рендерятся сверху и сбоку в атлас вида 2048²:
           цвет с альфой и нормаль (в осях карточки); у плоских веточек (липа, кизильник) — только вид сверху.
           → _asset_src/prospekt_plants/textures/<вид>_atlas_{albedo,normal}.png, <вид>_atlas.json
  meshes — экземпляры тем же генератором (те же ветви и точки модулей): ствол и ветви упрощены, веточки — карточки атласа
           (у объёмных — две крестом); LOD0 (полные), LOD1 (ветви толще 3 см, половина карточек крупнее), дальний — две
           скрещённые плоскости с видом дерева (рендер LOD0) → <ключ>_lod0.glb, _lod1.glb, _far.glb и дальний атлас вида.
           Цвет вершин (для шейдеров spruce_foliage / коры): r — затенение в кроне, g — гибкость, b — фаза ветра;
           считается по точке, поэтому ветка и её карточки качаются вместе. Нормали карточек — между плоскостью и
           направлением «наружу из кроны». Отчёт — _asset_src/prospekt_plants/game.json (для индекса и материалов).
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_forms as BF  # noqa: E402
import build_pbr as BP  # noqa: E402
import plib  # noqa: E402
import species as S  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "assets/models/plants"
TEX = ROOT / "_asset_src/prospekt_plants/textures"      # PNG атласов; в игру — WebP (godot_assets.py)
WORK = ROOT / "_asset_src/prospekt_plants"
ATLAS_PX = 2048
FAR_W, FAR_H = 512, 1024

# какие модули — крестом (два вида: сверху и сбоку); остальные — одна плоская карточка
CROSS = {
    "birch": {"01", "02", "03", "04", "05"},
    "linden": {"04"},
    "poplar": {"01", "02", "03", "04"},
    "lilac": {"01", "02", "03", "04"},
    "hedge": {"03", "05"},
}
# упрощение ветвей: LOD0 и LOD1
LOD0 = dict(min_r=0.007, side_div=1.6, seg=0.4)
# у липы и тополя ветвей много — тоньше 1 см веточки дают карточки, в сетке не нужны
LOD0_KIND = {"linden": dict(min_r=0.0105, side_div=2.0, seg=0.55), "poplar": dict(min_r=0.0105, side_div=2.0, seg=0.55)}
# карточки чуть крупнее модуля: плоская картинка вместо объёмной веточки, без этого крона просвечивает
CARD_GROW = {"birch": 1.05, "linden": 1.18, "poplar": 1.08, "lilac": 1.08, "hedge": 1.08}
LOD1 = dict(min_r=0.03, side_div=2.6, seg=0.9, no_roots=True)
# гибкость (ветер) по виду: деревья качаются, кусты — едва
FLEX = {"birch": 1.0, "linden": 0.75, "poplar": 0.8, "lilac": 0.45, "hedge": 0.25}
# дальность смены LOD, м (по клетке пачки)
RANGES = {"tree": (40.0, 140.0, 700.0), "bush": (30.0, 90.0, 320.0)}
MAT = {"birch": "Birch", "linden": "Linden", "poplar": "Poplar", "lilac": "Lilac", "hedge": "Hedge"}


def load_px(path: Path) -> np.ndarray:
    """PNG → массив (h, w, 4) сверху вниз, значения как в файле (без цветовых преобразований)."""
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1].copy()


def save_px(path: Path, arr: np.ndarray) -> None:
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.dstack([arr, np.ones((h, w), np.float32)])
    img = bpy.data.images.new("save_tmp", w, h, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1], np.float32).ravel())
    path.parent.mkdir(parents=True, exist_ok=True)
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def box(a: np.ndarray, r: int) -> np.ndarray:
    """Сумма в окне (2r+1)² через накопленные суммы."""
    c = np.cumsum(np.cumsum(np.pad(a, ((r + 1, r), (r + 1, r)) + ((0, 0),) * (a.ndim - 2)), 0), 1)
    return c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]


def bleed(rgb: np.ndarray, inside: np.ndarray) -> np.ndarray:
    """Цвет за краем листьев — средний цвет соседних листьев (окна растут), чтобы на мипах не было каймы."""
    out = rgb.copy()
    done = inside.copy()
    m = inside.astype(np.float32)
    for r in (2, 4, 8, 16, 32, 64):
        wsum = box(m, r)
        csum = box(rgb * m[..., None], r)
        fill = (~done) & (wsum > 0)
        out[fill] = csum[fill] / wsum[fill][:, None]
        done |= fill
    return out


def render_still() -> None:
    """Рендер кадра; видеокарта занята другими процессами (нет памяти) — повтор на процессоре."""
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError as e:
        if "memory" not in str(e).lower():
            raise
        bpy.context.scene.cycles.device = "CPU"
        print("PLANTS видеокарта без памяти — рендер на процессоре", flush=True)
        bpy.ops.render.render(write_still=True)


def mod_key(name: str) -> str:
    return name.split("_")[0]


def sh(a: float, b: float, x: float) -> float:
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ================================================================== атлас

def module_bounds(ob) -> tuple:
    vs = [v.co for v in ob.data.vertices]
    xs, ys, zs = [v.x for v in vs], [v.y for v in vs], [v.z for v in vs]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def pass_material(mat, mode: str) -> None:
    """Выход материала: albedo — цвет UCUPaint как свечение (альфа — вырез листа), normal — нормаль UCUPaint
    в осях камеры (как в атласах зоны 1: x вправо, y вверх, z к камере), с переворотом у изнанки."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    # группа UCUPaint (аддон для рендера не нужен: узнаём по выходам)
    group = next(n for n in nt.nodes if n.type == "GROUP" and "Color" in n.outputs and "Normal" in n.outputs)
    alpha_tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.label.startswith("Вырез")), None)
    for n in [n for n in nt.nodes if n.get("pass_node")]:
        nt.nodes.remove(n)

    def node(t: str):
        n = nt.nodes.new(t)
        n["pass_node"] = True
        return n

    em = node("ShaderNodeEmission")
    if mode == "albedo":
        nt.links.new(group.outputs["Color"], em.inputs["Color"])
    else:
        geo = node("ShaderNodeNewGeometry")
        flip = node("ShaderNodeMath")
        flip.operation = "MULTIPLY_ADD"
        flip.inputs[1].default_value = -2.0
        flip.inputs[2].default_value = 1.0
        nt.links.new(geo.outputs["Backfacing"], flip.inputs[0])
        sc = node("ShaderNodeVectorMath")
        sc.operation = "SCALE"
        nt.links.new(group.outputs["Normal"], sc.inputs[0])
        nt.links.new(flip.outputs[0], sc.inputs["Scale"])
        vt = node("ShaderNodeVectorTransform")
        vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
        nt.links.new(sc.outputs[0], vt.inputs[0])
        sp = node("ShaderNodeSeparateXYZ")
        nt.links.new(vt.outputs[0], sp.inputs[0])
        neg = node("ShaderNodeMath")
        neg.operation = "MULTIPLY"
        neg.inputs[1].default_value = -1.0
        nt.links.new(sp.outputs[2], neg.inputs[0])
        cb = node("ShaderNodeCombineXYZ")
        nt.links.new(sp.outputs[0], cb.inputs[0])
        nt.links.new(sp.outputs[1], cb.inputs[1])
        nt.links.new(neg.outputs[0], cb.inputs[2])
        ma = node("ShaderNodeVectorMath")
        ma.operation = "MULTIPLY_ADD"
        ma.inputs[1].default_value = (0.5, 0.5, 0.5)
        ma.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(cb.outputs[0], ma.inputs[0])
        nt.links.new(ma.outputs[0], em.inputs["Color"])
    if alpha_tex is not None:
        tr = node("ShaderNodeBsdfTransparent")
        mix = node("ShaderNodeMixShader")
        nt.links.new(alpha_tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])


def shelf_pack(cells: list, s: float, size: int, pad: int = 12):
    """Полки по высоте, каждая ячейка — на первую полку, где хватит места (длинные пряди не съедают полку целиком);
    отступ 12 пикс. — норма проекта для карт с мипами (иначе на дальних мипах альфа соседей подтекает).
    Возвращает (x, y) левого верхнего угла ячеек или None, если не влезло."""
    order = sorted(range(len(cells)), key=lambda i: -cells[i]["h"])
    shelves = []                     # [y, высота, занято по x]
    pos = [None] * len(cells)
    for i in order:
        w = int(math.ceil(cells[i]["w"] * s)) + pad
        h = int(math.ceil(cells[i]["h"] * s)) + pad
        if w > size:
            return None
        for sh_ in shelves:
            if sh_[1] >= h and sh_[2] + w <= size:
                pos[i] = (sh_[2], sh_[0])
                sh_[2] += w
                break
        else:
            y = shelves[-1][0] + shelves[-1][1] if shelves else 0
            if y + h > size:
                return None
            shelves.append([y, h, w])
            pos[i] = (0, y)
    return pos


def render_atlas(kind: str) -> None:
    idx = BF.ORDER.index(kind) + 1
    bpy.ops.wm.open_mainfile(filepath=str(BF.LIB / "models" / f"{idx:02d}_{S.LABEL[kind]}_PBR_{BP.VERSION}.blend"))
    sc = bpy.context.scene
    coll = bpy.data.collections[f"{S.LABEL[kind]}_модули_веточек"]
    mods = sorted(coll.objects, key=lambda o: o.name)
    cells = []
    for ob in mods:
        ob.location = (0, 0, 0)
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = (1, 0, 0, 0)
        x0, x1, y0, y1, z0, z1 = module_bounds(ob)
        m = 0.01
        cells.append(dict(module=ob.name, view="Z", rect=(x0 - m, x1 + m, y0 - m, y1 + m), w=x1 - x0 + 2 * m, h=y1 - y0 + 2 * m))
        if mod_key(ob.name) in CROSS[kind]:
            cells.append(dict(module=ob.name, view="Y", rect=(x0 - m, x1 + m, z0 - m, z1 + m), w=x1 - x0 + 2 * m, h=z1 - z0 + 2 * m))
    lo, hi = 50.0, 4000.0
    for _ in range(30):
        mid = (lo + hi) * 0.5
        if shelf_pack(cells, mid, ATLAS_PX):
            lo = mid
        else:
            hi = mid
    s = lo
    pos = shelf_pack(cells, s, ATLAS_PX)
    print("PLANTS атлас %s: %d ячеек, %.0f пикс/м" % (kind, len(cells), s), flush=True)
    for o in sc.objects:
        o.hide_render = True
    cam = bpy.data.objects.new("atlas_cam", bpy.data.cameras.new("atlas_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.clip_start, cam.data.clip_end = 0.01, 20
    sc.render.engine = "CYCLES"
    plib.gpu()
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 128
    sc.render.film_transparent = True
    sc.render.filter_size = 1.0
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    mats = {m for ob in mods for m in ob.data.materials if m}
    render_dir = WORK / "atlas" / kind
    render_dir.mkdir(parents=True, exist_ok=True)
    for ci, c in enumerate(cells):
        ob = bpy.data.objects[c["module"]]
        for o in mods:
            o.hide_render = o is not ob
        x0, x1, a0, a1 = c["rect"]
        sc.render.resolution_x = max(8, int(round(c["w"] * s)))
        sc.render.resolution_y = max(8, int(round(c["h"] * s)))
        cam.data.ortho_scale = max(c["w"], c["h"])
        if c["view"] == "Z":
            cam.location = ((x0 + x1) * 0.5, (a0 + a1) * 0.5, 5.0)
            cam.rotation_euler = (0, 0, 0)
        else:
            cam.location = ((x0 + x1) * 0.5, -5.0, (a0 + a1) * 0.5)
            cam.rotation_euler = (math.pi / 2, 0, 0)
        for mode in ("albedo", "normal"):
            for mt in mats:
                pass_material(mt, mode)
            sc.view_settings.view_transform = "Standard" if mode == "albedo" else "Raw"
            sc.cycles.samples = 24 if mode == "albedo" else 12
            sc.render.filepath = str(render_dir / f"{ci:02d}_{mode}.png")
            render_still()
    # склейка
    alb = np.zeros((ATLAS_PX, ATLAS_PX, 4), np.float32)
    nrm = np.zeros((ATLAS_PX, ATLAS_PX, 3), np.float32)
    nrm[...] = (0.5, 0.5, 1.0)
    meta = {"px_per_m": s, "cells": {}}
    for ci, c in enumerate(cells):
        a = load_px(render_dir / f"{ci:02d}_albedo.png")
        n = load_px(render_dir / f"{ci:02d}_normal.png")
        h, w = a.shape[:2]
        px, py = pos[ci]
        alb[py:py + h, px:px + w] = a
        nrm[py:py + h, px:px + w] = np.where(n[..., 3:4] > 0.02, n[..., :3], (0.5, 0.5, 1.0))
        x0, x1, a0, a1 = c["rect"]
        # UV Blender (v вверх): верх ячейки в картинке — py
        uv = [px / ATLAS_PX, 1.0 - (py + h) / ATLAS_PX, (px + w) / ATLAS_PX, 1.0 - py / ATLAS_PX]
        meta["cells"].setdefault(c["module"], {})[c["view"]] = dict(uv=[round(v, 6) for v in uv], rect=[round(v, 5) for v in c["rect"]])
    # цвет за краем листьев — от ближайшего листа (без тёмной каймы на мипах)
    inside = alb[..., 3] > 0.5
    rgb = bleed(alb[..., :3], inside)
    TEX.mkdir(parents=True, exist_ok=True)
    save_px(TEX / f"{kind}_atlas_albedo.png", np.clip(np.dstack([rgb, alb[..., 3]]), 0, 1))
    save_px(TEX / f"{kind}_atlas_normal.png", np.clip(nrm, 0, 1))
    (TEX / f"{kind}_atlas.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


# ================================================================== игровые сетки

def crown_axis(env, z: float) -> Vector:
    if hasattr(env, "center"):
        return env.center(z)
    return Vector((0, 0, 0))


def make_colors(kind: str, env, H: float, rmax: float):
    """Цвет вершины по точке: затенение (глубина в кроне), гибкость (от оси и высоты), фаза (сторона дерева)."""
    flex_k = FLEX[kind]

    def col(p: Vector) -> tuple:
        fr = env.frac(p)
        ao = 1.0 if fr >= 9 else 0.42 + 0.58 * sh(0.1, 0.95, fr)
        c = crown_axis(env, p.z)
        d = math.hypot(p.x - c.x, p.y - c.y)
        if kind == "hedge":
            g = flex_k * min(1.0, max(0.0, p.z / max(H, 0.5)))
        else:
            g = flex_k * min(1.0, (d / max(rmax, 0.3)) ** 1.25 * 0.9 + 0.1 * max(0.0, p.z) / max(H, 1.0))
        b = (math.atan2(p.y, p.x) / (2 * math.pi) + 0.5 + 0.13 * p.z / max(H, 1.0)) % 1.0
        return (ao, g, b, 1.0)
    return col


def out_dir(kind: str, env, p: Vector, zc: float) -> Vector:
    if kind == "hedge":
        return env.normal(p)
    c = crown_axis(env, p.z)
    v = Vector((p.x - c.x, p.y - c.y, (p.z - zc) * 0.6))
    return v.normalized() if v.length > 1e-4 else Vector((0, 0, 1))


def cards(kind: str, tw: plib.Twigs, atlas: dict, names: list, env, col, keep_every: int = 1, grow: float = 1.0,
          only_top: bool = False) -> tuple:
    """Карточки атласа на точках модулей: вершины, грани, UV, нормали, цвета (по каждой вершине)."""
    V, F, UVs, N, C = [], [], [], [], []
    zc = 0.5 * (getattr(env, "z0", 0.0) + getattr(env, "z1", getattr(env, "H", 1.0)))
    for i, (p, q, s, tid) in enumerate(zip(tw.pts, tw.rots, tw.scales, tw.ids)):
        if keep_every > 1 and (i * 7 + tid) % keep_every:
            continue
        info = atlas["cells"][names[tid]]
        views = ["Z"] if only_top or "Y" not in info else ["Z", "Y"]
        rot = q.to_matrix()
        out = out_dir(kind, env, p, zc)
        for view in views:
            cell = info[view]
            u0, v0, u1, v1 = cell["uv"]
            x0, x1, a0, a1 = cell["rect"]
            if view == "Z":
                loc = [Vector((x0, a0, 0)), Vector((x1, a0, 0)), Vector((x1, a1, 0)), Vector((x0, a1, 0))]
                fn = rot @ Vector((0, 0, 1))
            else:
                loc = [Vector((x0, 0, a0)), Vector((x1, 0, a0)), Vector((x1, 0, a1)), Vector((x0, 0, a1))]
                fn = rot @ Vector((0, -1, 0))
            k = s * grow
            pts = [p + rot @ (c * k) for c in loc]
            if fn.dot(out) < 0:
                fn = -fn
            nn = (fn * 0.45 + out * 0.55).normalized()
            b = len(V)
            V.extend(pts)
            F.append([b, b + 1, b + 2, b + 3])
            UVs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
            N.extend([nn] * 4)
            C.extend([col(v) for v in pts])
    return V, F, UVs, N, C


def build_cards_object(name: str, data: tuple, mat) -> bpy.types.Object:
    V, F, UVs, N, C = data
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], F)
    uvl = me.uv_layers.new(name="UVMap")
    for poly, puv in zip(me.polygons, UVs):
        for k in range(poly.loop_total):
            uvl.data[poly.loop_start + k].uv = puv[k]
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i, c in enumerate(C):
        ca.data[i].color = c
    me.materials.append(mat)
    me.validate()
    me.update()
    me.normals_split_custom_set([tuple(N[l.vertex_index]) for l in me.loops])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def game_materials(kind: str, key: str) -> dict:
    """Имена слотов = имена материалов Godot (assets/models/plants/materials/<имя>.tres)."""
    m = MAT[kind]
    names = {"bark": f"Plant{m}Bark", "branch": f"Plant{m}Branch", "leaves": f"Plant{m}Leaves", "far": f"Plant{m}Far"}
    if kind in ("birch", "poplar"):
        names["bark"] = f"Plant{m}Bark_{key.split('_')[1]}"      # своя высота тёмного низа / старой коры
    if kind in ("lilac", "hedge"):
        names["branch"] = names["bark"]
    return {k: (bpy.data.materials.get(v) or bpy.data.materials.new(v)) for k, v in names.items()}


def export(ob, path: Path) -> int:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    me = ob.data
    if me.color_attributes.get("Col"):
        me.color_attributes.active_color = me.color_attributes["Col"]
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
    path.parent.mkdir(parents=True, exist_ok=True)
    kw = dict(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
              export_normals=True, export_tangents=True, export_materials="EXPORT", export_animations=False,
              export_vertex_color="ACTIVE")
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        kw.pop("export_vertex_color")
        bpy.ops.export_scene.gltf(**kw, export_colors=True)
    return sum(len(p.vertices) - 2 for p in me.polygons)


def join(obs: list, name: str):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def wood_object(kind: str, pl, lod: dict, col, mats: dict) -> tuple:
    plib.LOD = dict(lod, col=col)
    m, tw, env = S.BUILDERS[kind](pl)
    plib.LOD = None
    slot = {"bark": mats["bark"], "branch": mats["branch"], "twig": mats["branch"], "seed": mats["branch"]}
    ob = m.build(pl.key + "_wood", slot) if m.parts else None
    return ob, tw, env


def far_render(kind: str, ob, H: float, half_w: float, atlas_img, out_prefix: Path) -> dict:
    """Два вида (спереди −Y и сбоку +X) орто: цвет с альфой и нормаль камеры → дальний силуэт."""
    sc = bpy.context.scene
    for o in sc.objects:
        o.hide_render = o is not ob
    cam = bpy.data.objects.get("far_cam") or bpy.data.objects.new("far_cam", bpy.data.cameras.new("far_cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    size = max(H * 1.03 + 0.3, half_w * 4.0)
    cam.data.ortho_scale = size
    cam.data.clip_start, cam.data.clip_end = 0.1, 200
    sc.render.resolution_x, sc.render.resolution_y = FAR_W, FAR_H
    sc.render.engine = "CYCLES"
    plib.gpu()
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 256
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    for mode in ("albedo", "normal"):
        far_materials(ob, mode, atlas_img, kind)
        sc.view_settings.view_transform = "Standard" if mode == "albedo" else "Raw"
        for vi, yaw in enumerate((0.0, 90.0)):
            a = math.radians(yaw)
            cam.location = (-math.sin(a) * 60, -math.cos(a) * 60, size * 0.5 - 0.3)
            cam.rotation_euler = (math.pi / 2, 0, -a)
            sc.render.filepath = str(out_prefix) + f"_{mode}_{vi}.png"
            render_still()
    return dict(size=round(size, 3), base=0.3)


def far_materials(ob, mode: str, atlas_img, kind: str) -> None:
    bark_img = BP.image(BP.BARK_TEX[kind]["albedo"], True)
    for slot in ob.material_slots:
        mt = slot.material
        mt.use_nodes = True
        nt = mt.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        t = nt.nodes.new("ShaderNodeTexImage")
        leaves = mt.name.endswith("Leaves")
        t.image = atlas_img if leaves else bark_img
        nt.links.new(uv.outputs[0], t.inputs[0])
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attr.outputs["Color"], sep.inputs[0])
        em = nt.nodes.new("ShaderNodeEmission")
        if mode == "albedo":
            pw = nt.nodes.new("ShaderNodeMath")
            pw.operation = "POWER"
            pw.inputs[1].default_value = 0.6
            nt.links.new(sep.outputs[0], pw.inputs[0])
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs[0].default_value = 1.0
            nt.links.new(t.outputs["Color"], mul.inputs[6])
            nt.links.new(pw.outputs[0], mul.inputs[7])
            nt.links.new(mul.outputs[2], em.inputs["Color"])
        else:
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            vt = nt.nodes.new("ShaderNodeVectorTransform")
            vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
            nt.links.new(geo.outputs["Normal"], vt.inputs[0])
            sp = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(vt.outputs[0], sp.inputs[0])
            neg = nt.nodes.new("ShaderNodeMath")
            neg.operation = "MULTIPLY"
            neg.inputs[1].default_value = -1.0
            nt.links.new(sp.outputs[2], neg.inputs[0])
            cb = nt.nodes.new("ShaderNodeCombineXYZ")
            nt.links.new(sp.outputs[0], cb.inputs[0])
            nt.links.new(sp.outputs[1], cb.inputs[1])
            nt.links.new(neg.outputs[0], cb.inputs[2])
            ma = nt.nodes.new("ShaderNodeVectorMath")
            ma.operation = "MULTIPLY_ADD"
            ma.inputs[1].default_value = (0.5, 0.5, 0.5)
            ma.inputs[2].default_value = (0.5, 0.5, 0.5)
            nt.links.new(cb.outputs[0], ma.inputs[0])
            nt.links.new(ma.outputs[0], em.inputs["Color"])
        if leaves:
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(t.outputs["Alpha"], mix.inputs[0])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], out.inputs["Surface"])


def far_mesh(key: str, info: dict, uv_rects: list, mat) -> bpy.types.Object:
    s, b = info["size"], info["base"]
    V, F, UVs, N, C = [], [], [], [], []
    for vi, yaw in enumerate((0.0, 90.0)):
        a = math.radians(yaw)
        right = Vector((math.cos(a), -math.sin(a), 0))
        out = Vector((-math.sin(a), -math.cos(a), 0))
        u0, v0, u1, v1 = uv_rects[vi]
        base = len(V)
        V.extend([right * (-s / 4) + Vector((0, 0, -b)), right * (s / 4) + Vector((0, 0, -b)),
                  right * (s / 4) + Vector((0, 0, s - b)), right * (-s / 4) + Vector((0, 0, s - b))])
        F.append([base, base + 1, base + 2, base + 3])
        UVs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        N.extend([out] * 4)
        C.extend([(1.0, 0.0, 0.5, 1.0)] * 4)
    return build_cards_object(key + "_far", (V, F, UVs, N, C), mat)


def build_meshes(kind: str) -> dict:
    atlas = json.loads((TEX / f"{kind}_atlas.json").read_text(encoding="utf-8"))
    names = [n for n, _ in S.MODULES[kind]()]
    plants = [p for p in S.PLANTS if p.kind == kind]
    report = {}
    far_imgs = []
    tile = BP.BARK_TEX[kind]["tile"]
    for pl in plants:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        plib.BARK.update(tile_u=tile[0], tile_v=tile[1])
        mats = game_materials(kind, pl.key)
        atlas_img = bpy.data.images.load(str(TEX / f"{kind}_atlas_albedo.png"), check_existing=True)
        # огибающая и цвета — с первого прохода (тот же seed — та же крона)
        _, tw0, env0 = S.BUILDERS[kind](pl)
        P = pl.params
        H = pl.height if kind != "hedge" else P["Hh"]
        rmax = P.get("rmax", P.get("W", 1.0) * 0.5)
        col = make_colors(kind, env0, H, rmax)
        res = {}
        for lod_name, lod in (("lod0", LOD0_KIND.get(kind, LOD0)), ("lod1", LOD1)):
            wood, tw, env = wood_object(kind, pl, lod, col, mats)
            if lod_name == "lod0":
                data = cards(kind, tw, atlas, names, env, col, grow=CARD_GROW[kind])
            else:
                # половина карточек, крупнее: при трети берёзы вдоль проспекта издали выходили жидкими
                data = cards(kind, tw, atlas, names, env, col, keep_every=2, grow=1.38 * CARD_GROW[kind], only_top=True)
            leaves = build_cards_object(pl.key + "_leaves", data, mats["leaves"])
            ob = join([o for o in (wood, leaves) if o is not None], f"{pl.key}_{lod_name}")
            tris = export(ob, OUT / f"{pl.key}_{lod_name}.glb")
            vs = [v.co for v in ob.data.vertices]
            lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            res[lod_name] = dict(triangles=tris, lo=list(lo), hi=list(hi))
            if lod_name == "lod0":
                lod0_ob, half_w, top = ob, max(abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y)), hi.z
            print("PLANTS %s %s: %d треуг." % (pl.key, lod_name, tris), flush=True)
        # дальний вид — после выгрузки обоих LOD (рендер меняет материалы, в .glb они должны остаться пустыми)
        res["far"] = far_render(kind, lod0_ob, top, half_w, atlas_img, WORK / "far" / pl.key)
        report[pl.key] = res
        far_imgs.append(pl.key)
    # дальний атлас вида: полосы 512 × 1024 (по два вида на экземпляр)
    cols = ATLAS_PX // FAR_W
    rows_needed = math.ceil(len(far_imgs) * 2 / cols)
    far_h = FAR_H * rows_needed
    alb = np.zeros((far_h, ATLAS_PX, 4), np.float32)
    nrm = np.zeros((far_h, ATLAS_PX, 3), np.float32)
    nrm[...] = (0.5, 0.5, 1.0)
    for i, key in enumerate(far_imgs):
        rects = []
        for vi in range(2):
            k = i * 2 + vi
            px, py = (k % cols) * FAR_W, (k // cols) * FAR_H
            alb[py:py + FAR_H, px:px + FAR_W] = load_px(Path(str(WORK / "far" / key) + f"_albedo_{vi}.png"))
            n = load_px(Path(str(WORK / "far" / key) + f"_normal_{vi}.png"))
            nrm[py:py + FAR_H, px:px + FAR_W] = np.where(n[..., 3:4] > 0.02, n[..., :3], (0.5, 0.5, 1.0))
            rects.append([px / ATLAS_PX, 1.0 - (py + FAR_H) / far_h, (px + FAR_W) / ATLAS_PX, 1.0 - py / far_h])
        report[key]["far"]["uv"] = rects
    inside = alb[..., 3] > 0.5
    alb[..., :3] = bleed(alb[..., :3], inside)
    save_px(TEX / f"{kind}_far_albedo.png", np.clip(alb, 0, 1))
    save_px(TEX / f"{kind}_far_normal.png", np.clip(nrm, 0, 1))
    for key in far_imgs:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mt = bpy.data.materials.new(f"Plant{MAT[kind]}Far")
        ob = far_mesh(key, report[key]["far"], report[key]["far"]["uv"], mt)
        report[key]["far"]["triangles"] = export(ob, OUT / f"{key}_far.glb")
    return report


def preview(kind: str) -> None:
    """Проверка выгрузки: .glb всех LOD рядом (атлас, кора, дальний атлас) — previews/<вид>_game_v01.png."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    imgs = {"leaves": TEX / f"{kind}_atlas_albedo.png", "far": TEX / f"{kind}_far_albedo.png"}
    x = 0.0
    top = 1.0
    for pl in [p for p in S.PLANTS if p.kind == kind]:
        for li, lod in enumerate(("lod0", "lod1", "far")):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=str(OUT / f"{pl.key}_{lod}.glb"))
            new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
            for o in new:
                o.location.x += x
                top = max(top, max((o.matrix_world @ v.co).z for v in o.data.vertices))
                for slot in o.material_slots:
                    mt = slot.material
                    nt = mt.node_tree
                    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
                    t = nt.nodes.new("ShaderNodeTexImage")
                    base = mt.name.split(".")[0]
                    key = "leaves" if base.endswith("Leaves") else "far" if base.endswith("Far") else None
                    t.image = BP.image(imgs[key] if key else BP.BARK_TEX[kind]["albedo"], True)
                    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
                    if key:
                        nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            x += max(4.0, pl.params.get("rmax", 1.5) * 2.4)
    plib.studio(plib.new_collection("студия"), size=max(80.0, x + 40))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    dist = max(top * 2.6, x * 1.5) + 3
    cam.location = (x * 0.5 - 1.5, -dist, top * 0.5)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.engine = "CYCLES"
    plib.gpu()
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1800, 900
    sc.render.filepath = str(BF.LIB / "previews" / f"{kind}_game_v01.png")
    render_still()


def compare(kind: str) -> None:
    """Исходник и игра при одном свете: PBR-файл вида как есть и тот же кадр, где вместо деревьев — LOD0 из .glb
    (атлас, кора, затенение по цвету вершин, как в шейдере игры) → previews/<вид>_pbr_vs_game_v01.png (слева PBR)."""
    idx = BF.ORDER.index(kind) + 1
    bpy.ops.wm.open_mainfile(filepath=str(BF.LIB / "models" / f"{idx:02d}_{S.LABEL[kind]}_PBR_{BP.VERSION}.blend"))
    sc = bpy.context.scene
    plants = [p for p in S.PLANTS if p.kind == kind]
    empties = [bpy.data.objects[p.key] for p in plants]
    atlas = BP.image(TEX / f"{kind}_atlas_albedo.png", True)
    atlas_n = BP.image(TEX / f"{kind}_atlas_normal.png", False)
    bark = BP.image(BP.BARK_TEX[kind]["albedo"], True)
    bark_n = BP.image(BP.BARK_TEX[kind]["normal"], False)
    games = []
    for pl, emp in zip(plants, empties):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(OUT / f"{pl.key}_lod0.glb"))
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.type != "MESH":
                continue
            o.location += emp.location
            games.append(o)
            for slot in o.material_slots:
                mt = slot.material
                nt = mt.node_tree
                bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
                leaves = mt.name.split(".")[0].endswith("Leaves")
                uvn = nt.nodes.new("ShaderNodeUVMap")
                uvn.uv_map = "UVMap"
                t = nt.nodes.new("ShaderNodeTexImage")
                t.image = atlas if leaves else bark
                tn = nt.nodes.new("ShaderNodeTexImage")
                tn.image = atlas_n if leaves else bark_n
                for n in (t, tn):
                    nt.links.new(uvn.outputs[0], n.inputs[0])
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.uv_map = "UVMap"
                nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
                attr = nt.nodes.new("ShaderNodeAttribute")
                attr.attribute_name = "Col"
                sep = nt.nodes.new("ShaderNodeSeparateColor")
                nt.links.new(attr.outputs["Color"], sep.inputs[0])
                ao = nt.nodes.new("ShaderNodeMapRange")          # как в spruce_foliage: mix(1, ao, 0.6)
                ao.inputs["To Min"].default_value = 0.4
                nt.links.new(sep.outputs[0], ao.inputs["Value"])
                mul = nt.nodes.new("ShaderNodeMix")
                mul.data_type = "RGBA"
                mul.blend_type = "MULTIPLY"
                mul.inputs[0].default_value = 1.0
                nt.links.new(t.outputs["Color"], mul.inputs[6])
                nt.links.new(ao.outputs[0], mul.inputs[7])
                nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
                if leaves:
                    nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
                    bsdf.inputs["Roughness"].default_value = 0.9
    H = max(p.height for p in plants) + 0.5
    xs = [e.location.x for e in empties]
    cx = (min(xs) + max(xs)) * 0.5
    row = max(xs) - min(xs) + 8.0
    dist = max(H * 2.6, row * 1.55) + 3
    cam = BF.camera("кадр_сравнения", Vector((cx, -dist, H * 0.5)), Vector((cx, 0, H * 0.5)), 50)
    work = WORK / "compare"
    pbr_objs = [c for e in empties for c in e.children]
    for o in games:
        o.hide_render = True
    BF.render(cam, work / f"{kind}_pbr.png", (1400, 900), 48)
    for o in pbr_objs:
        o.hide_render = True
    for o in games:
        o.hide_render = False
    BF.render(cam, work / f"{kind}_game.png", (1400, 900), 48)
    a = load_px(work / f"{kind}_pbr.png")
    b = load_px(work / f"{kind}_game.png")
    save_px(BF.LIB / "previews" / f"{kind}_pbr_vs_game_v01.png", np.concatenate([a, b], axis=1))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kinds = [k for k in BF.ORDER if k in argv] or BF.ORDER
    do_atlas = "atlas" in argv or "meshes" not in argv
    do_meshes = "meshes" in argv or "atlas" not in argv
    if "preview" in argv:
        for kind in kinds:
            preview(kind)
        return
    if "compare" in argv:
        for kind in kinds:
            compare(kind)
        return
    rep_path = WORK / "game.json"
    report = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
    for kind in kinds:
        if do_atlas:
            render_atlas(kind)
        if do_meshes:
            report[kind] = build_meshes(kind)
            rep_path.parent.mkdir(parents=True, exist_ok=True)
            rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
