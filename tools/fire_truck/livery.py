"""Пожарная АЦ: ливрея — наклейки, прижатые к кузову, запечённые в развёртку наборов (для Painter).

Как у машин «Проспекта» (tools/prospekt_vehicles/livery.py): надписи — текст Blender шрифтом DejaVu Sans Bold
(свободный, `_asset_src/fonts`), полосы и знаки — сетки; наклейка прижата к детали проекцией (Shrinkwrap вдоль
нормали стороны, 3 мм над листом), излучение запекается «выбранное на активное» в развёртку детали. Надписи по образцу
московских АЦ-3,2-40 на КамАЗ-43253, но вымышленные: номер части «17», «ПСЧ-17», «ПОЖАРНАЯ ОХРАНА», «ТЕЛЕФОН 01, 112»;
эмблема двери экипажа — своя (круг с пламенем), настоящих эмблем МЧС и марок нет; номерные знаки — вымышленные.

На набор — три картинки 4K в `<WORK>/livery/`: `<набор>_color.png` (цвет наклеек), `<набор>_mask.png` (где наклейка),
`<набор>_tape.png` (где светоотражающая лента — у неё своя отделка). В Painter — слои плёнки поверх эмали.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/livery.py -- [набор,набор] [decals.blend]
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import spec as S  # noqa: E402
import tex_sets as T  # noqa: E402

# цвета (sRGB): красная плёнка надписей, белая плёнка полос, жёлтая светоотражающая лента, чёрная печать знаков
RED, WHITE, YELLOW, BLACK = (0.70, 0.06, 0.05), (0.92, 0.92, 0.90), (0.95, 0.72, 0.05), (0.03, 0.03, 0.03)
FONTS = (Path(HERE).parents[1] / "_asset_src" / "fonts" / "DejaVuSans-Bold.ttf",
         Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf"))
PROJ, GAP = 0.5, 0.003
# поворот рамки стороны: локальные x — направление чтения, y — вверх, z — наружу (нормаль листа)
ROT = {"L": ((0, 0, 1), (1, 0, 0), (0, 1, 0)), "R": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
       "F": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "B": ((-1, 0, 0), (0, 0, 1), (0, 1, 0))}
_CAP: dict = {}


def lin(c):
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c)


def emission(rgb, name=None) -> bpy.types.Material:
    name = name or "LIV_" + ",".join(f"{c:.2f}" for c in rgb)
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*lin(rgb), 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def frame(side: str, u: float, v: float, out: float) -> Matrix:
    """Рамка снаружи стороны (оси машины: X влево, Y назад, Z вверх): u — вдоль чтения (левый борт u = Y, правый
    u = −Y, перёд u = X, зад u = −X), v — высота, out — плоскость старта по нормали стороны (|X| или |Y|)."""
    pos = {"L": (out, u, v), "R": (-out, -u, v), "F": (u, -out, v), "B": (-u, out, v)}[side]
    M = Matrix(ROT[side]).to_4x4()
    M.translation = pos
    return M


def grid(w: float, h: float, step: float = 0.02, slant: float = 0.0):
    nx, ny = max(2, int(w / step) + 1), max(2, int(h / step) + 1)
    xs, ys = np.linspace(-w / 2, w / 2, nx), np.linspace(-h / 2, h / 2, ny)
    V = [(float(x + slant * y), float(y), 0.0) for y in ys for x in xs]
    F = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(ny - 1) for i in range(nx - 1)]
    return V, F


def _glyphs(text: str, size: float) -> bpy.types.Mesh:
    cu = bpy.data.curves.new("txt", "FONT")
    font = next((f for f in FONTS if f.exists()), None)
    if font is not None:
        cu.font = bpy.data.fonts.load(str(font), check_existing=True)
    cu.body = text
    cu.size = size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.resolution_u = 8
    ob = bpy.data.objects.new("txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return me


def text_mesh(text: str, cap: float) -> bpy.types.Mesh:
    """Надпись высотой прописной cap (мерим по «Н»), по центру; заливка — мелкие треугольники (проекция по изгибу)."""
    if "H" not in _CAP:
        ref = _glyphs("Н", 1.0)
        ys = [v.co.y for v in ref.vertices]
        _CAP["H"] = max(ys) - min(ys)
        bpy.data.meshes.remove(ref)
    me = _glyphs(text, cap / _CAP["H"])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for _ in range(2):
        long = [e for e in bm.edges if e.calc_length() > 0.015]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return me


def disc(d: float, n: int = 64, ring: float = 0.0):
    """Круг (или кольцо шириной ring) диаметром d — вершины и грани веером."""
    r, V, F = d / 2, [], []
    if ring <= 0:
        V.append((0.0, 0.0, 0.0))
        for k in range(n):
            a = 2 * math.pi * k / n
            V.append((r * math.cos(a), r * math.sin(a), 0.0))
        F = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    else:
        for k in range(n):
            a = 2 * math.pi * k / n
            V += [((r - ring) * math.cos(a), (r - ring) * math.sin(a), 0.0), (r * math.cos(a), r * math.sin(a), 0.0)]
        F = [(2 * k, 2 * k + 1, 2 * ((k + 1) % n) + 1, 2 * ((k + 1) % n)) for k in range(n)]
    return V, F


def flame(h: float):
    """Пламя эмблемы: три языка, контур — многоугольник (своя форма); одна грань, триангуляция — отсечением ушей
    (веер из точки внутри вогнутого контура вылезал лучами за край)."""
    pts = [(0.0, -0.50), (0.30, -0.42), (0.40, -0.18), (0.30, 0.10), (0.22, 0.02), (0.20, 0.22), (0.08, 0.50),
           (0.06, 0.18), (-0.02, 0.30), (-0.10, 0.08), (-0.18, 0.26), (-0.32, 0.04), (-0.40, -0.18), (-0.30, -0.42)]
    return [(x * h, y * h, 0.0) for x, y in pts], [tuple(range(len(pts)))]


class Decals:
    """Наклейки на детали target: сетки с излучением цвета, прижатые проекцией по −z рамки."""

    def __init__(self, col):
        self.col = col
        self.objs = []          # (объект, цель, это лента)

    def _place(self, me, M, rgb, target, tape=False, gap=GAP):
        if any(len(f.vertices) > 4 for f in me.polygons):
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="EAR_CLIP")
            bm.to_mesh(me)
            bm.free()
        me.materials.append(emission(rgb))
        ob = bpy.data.objects.new("decal", me)
        self.col.objects.link(ob)
        ob.matrix_world = M
        sw = ob.modifiers.new("press", "SHRINKWRAP")
        sw.target = bpy.data.objects[target]
        sw.wrap_method = "PROJECT"
        sw.use_project_z = True
        sw.use_negative_direction = True
        sw.use_positive_direction = False
        sw.project_limit = PROJ
        sw.offset = gap
        self.objs.append((ob, target, tape))

    def rect(self, target, side, out, u, v, w, h, rgb, tape=False, slant=0.0):
        V, F = grid(w, h, slant=slant)
        me = bpy.data.meshes.new("rect")
        me.from_pydata(V, [], F)
        self._place(me, frame(side, u, v, out), rgb, target, tape)

    def text(self, target, side, out, u, v, s, cap, rgb):
        self._place(text_mesh(s, cap), frame(side, u, v, out), rgb, target)

    def shape(self, target, side, out, u, v, VF, rgb, lift=0.0):
        """Знак слоями: lift — насколько слой дальше от листа (проекция кладёт всё на один зазор, поэтому слой
        поднимается зазором прижатия; запекание видит верхний — самый дальний)."""
        V, F = VF
        me = bpy.data.meshes.new("shape")
        me.from_pydata(V, [], F)
        self._place(me, frame(side, u, v, out), rgb, target, gap=GAP + lift)

    def chevrons(self, target, side, out, u0, u1, v, h, stripe, a, b):
        """Косые полосы предупреждения (как на бамперах спецмашин): чередуются a и b, наклон 45°."""
        n = int((u1 - u0) / stripe)
        for k in range(n):
            self.rect(target, side, out, u0 + (k + 0.5) * stripe, v, stripe, h, a if k % 2 == 0 else b, slant=1.0)


def layout(D: Decals) -> None:
    hw_cab, hw = S.CAB_W / 2, S.BODY_W / 2
    d = S.DOOR
    for side, tgt in (("L", "Cab_Door_L"), ("R", "Cab_Door_R")):
        yc = (d["y0"] + d["y1"]) / 2
        u = yc if side == "L" else -yc
        D.text(tgt, side, hw_cab + 0.25, u, 1.68, "17", 0.17, RED)
        D.rect(tgt, side, hw_cab + 0.25, u, 1.535, 0.74, 0.036, YELLOW, tape=True)
        D.text(tgt, side, hw_cab + 0.25, u, 1.44, "ПСЧ-17", 0.046, RED)
    # лицо кабины: две белые полосы над щелями решётки (панель решётки — своя деталь)
    for x in (-0.055, 0.055):
        D.rect("Cab_Grille_Panel", "F", -S.CAB_FRONT + 0.35, x, 1.64, 0.075, 0.36, WHITE)
    # верхняя полоса: лента у нижней кромки, надписи
    y0, y1 = S.BODY_FRONT + 0.02, S.BODY_BACK - S.REAR_COL - 0.02
    for side, tgt in (("L", "top_band_L"), ("R", "top_band_R")):
        f = (lambda y: y) if side == "L" else (lambda y: -y)
        D.rect(tgt, side, hw + 0.25, f((y0 + y1) / 2), S.BAND[0] + 0.035, y1 - y0, 0.03, YELLOW, tape=True)
        D.text(tgt, side, hw + 0.25, f(0.85), 2.945, "ПОЖАРНАЯ ОХРАНА", 0.085, RED)
        D.text(tgt, side, hw + 0.25, f(2.72), 2.945, "АЦ-3,2-40   ТЕЛЕФОН 01, 112", 0.07, RED)
    # лента по белым полосам под рольставнями и по задним стойкам
    for o in [o for o in bpy.data.objects if o.type == "MESH" and T.base_name(o.name) == "rub_strip"]:
        c = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / max(1, len(o.data.vertices))
        dims = o.dimensions
        side = "L" if c.x > 0 else "R"
        L = max(dims) - 0.04
        D.rect(o.name, side, hw + 0.25, c.y if side == "L" else -c.y, (S.RUB[0] + S.RUB[1]) / 2, L, 0.035, YELLOW, tape=True)
    for o in [o for o in bpy.data.objects if o.type == "MESH" and T.base_name(o.name) == "rear_column"]:
        c = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / max(1, len(o.data.vertices))
        side = "L" if c.x > 0 else "R"
        yb = S.BODY_BACK - 0.035
        D.rect(o.name, side, hw + 0.25, yb if side == "L" else -yb, 1.62, 0.04, 2.20, YELLOW, tape=True)
    # задняя рольставня: белые полосы и «АЦ 17»
    rs = S.REAR_SHUTTER
    for x in (-0.10, 0.10):
        D.rect("rear_shutter", "B", S.BODY_BACK + 0.25, -x, (rs["z0"] + rs["z1"]) / 2 + 0.05, 0.09, rs["z1"] - rs["z0"] - 0.25,
               WHITE)
    D.text("rear_shutter", "B", S.BODY_BACK + 0.25, -0.46, 2.33, "АЦ", 0.17, WHITE)
    D.text("rear_shutter", "B", S.BODY_BACK + 0.25, 0.46, 2.33, "17", 0.17, WHITE)
    D.text("rear_shutter", "B", S.BODY_BACK + 0.25, 0.46, 2.17, "ПСЧ", 0.05, WHITE)
    # подножка: косые красно-белые полосы по краям заднего борта
    st = S.REAR_STEP
    for u0 in (-st["w"] / 2 + 0.03, st["w"] / 2 - 0.53):
        D.chevrons("rear_step", "B", st["y1"] + 0.25, u0, u0 + 0.50, (st["z0"] + st["z1"]) / 2, 0.08, 0.05, RED, WHITE)
    # двери экипажа: своя эмблема — белое кольцо, красный круг, белое пламя
    for o in [o for o in bpy.data.objects if o.type == "MESH" and T.base_name(o.name) == "crew_door"]:
        if "Целая" not in [cl.name for cl in o.users_collection]:
            continue                       # створка «открыто» — та же сетка, наклейка ляжет и так
        c = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / max(1, len(o.data.vertices))
        side = "L" if c.x > 0 else "R"
        u = c.y if side == "L" else -c.y
        D.shape(o.name, side, hw + 0.25, u, 1.62, disc(0.21), WHITE)
        D.shape(o.name, side, hw + 0.25, u, 1.62, disc(0.185), RED, lift=0.001)
        D.shape(o.name, side, hw + 0.25, u, 1.615, flame(0.12), WHITE, lift=0.002)
        D.text(o.name, side, hw + 0.25, u, 1.465, "ПОЖАРНАЯ ОХРАНА", 0.028, WHITE)
    # номерные знаки (вымышленные)
    b = S.BUMPER
    D.text("plate_front", "F", -b["y0"] + 0.3, 0.0, 0.572, "А 017 ПО 77", 0.055, BLACK)
    # задний знак — квадратный, на левой стойке: две строки
    xl = S.BODY_W / 2 - S.REAR_COL / 2 + 0.005
    D.text("plate_rear", "B", S.BODY_BACK + 0.3, -xl, 1.222, "А 017", 0.052, BLACK)
    D.text("plate_rear", "B", S.BODY_BACK + 0.3, -xl, 1.150, "ПО 77", 0.042, BLACK)


def joined_copy(objs, name):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake(target, sources, img, first):
    m = bpy.data.materials.new("_bake")
    m.use_nodes = True
    node = m.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    m.node_tree.nodes.active = node
    target.data.materials.clear()
    target.data.materials.append(m)
    bpy.ops.object.select_all(action="DESELECT")
    for s in sources:
        s.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=0.010, max_ray_distance=0.025,
                        margin=6, margin_type="EXTEND", use_clear=first, target="IMAGE_TEXTURES")


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = a[0].split(",") if a and a[0] else None
    keep = a[1] if len(a) > 1 else None
    out = Path(T.WORK) / "livery"
    out.mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.device = "CPU"
    col = bpy.data.collections.new("Ливрея")
    sc.collection.children.link(col)
    D = Decals(col)
    layout(D)
    bpy.context.view_layer.update()
    # наклейки — в сетки (модификатор применён), по целям
    dg = bpy.context.evaluated_depsgraph_get()
    by_target = {}
    for ob, tgt, tape in D.objs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.materials.clear()
        me.materials.append(ob.data.materials[0])
        fixed = bpy.data.objects.new("decal_" + tgt, me)
        col.objects.link(fixed)
        fixed.matrix_world = ob.matrix_world
        by_target.setdefault(tgt, []).append((fixed, tape))
        bpy.data.objects.remove(ob)
    if keep:
        bpy.ops.wm.save_as_mainfile(filepath=keep, copy=True, compress=True)
        print("наклейки:", keep, flush=True)
    sets = {}
    for tgt in by_target:
        sets.setdefault(bpy.data.objects[tgt].get("ft_set"), []).append(tgt)
    white = emission((1, 1, 1), "LIV_mask")
    for st, tgts in sets.items():
        if only and st not in only:
            continue
        res = T.SETS[st][0]
        for kind in ("color", "mask", "tape"):
            img = bpy.data.images.new(f"{st}_{kind}", res, res, alpha=False)
            img.colorspace_settings.name = "sRGB" if kind == "color" else "Non-Color"
            for i, tgt in enumerate(tgts):
                decs = [d for d, tape in by_target[tgt] if kind != "tape" or tape]
                if not decs:
                    continue
                tmp = []
                if kind != "color":
                    for d in decs:
                        dd = d.copy()
                        dd.data = d.data.copy()
                        dd.data.materials.clear()
                        dd.data.materials.append(white)
                        col.objects.link(dd)
                        tmp.append(dd)
                src = tmp or decs
                target = bpy.data.objects[tgt]
                proxy = target.copy()
                proxy.data = target.data.copy()
                sc.collection.objects.link(proxy)
                bake(proxy, src, img, first=(i == 0))
                bpy.data.objects.remove(proxy)
                for dd in tmp:
                    bpy.data.objects.remove(dd)
            img.filepath_raw = str(out / f"{st}_{kind}.png")
            img.file_format = "PNG"
            img.save()
            print("LIVERY", st, kind, img.filepath_raw, flush=True)


if __name__ == "__main__":
    main()
