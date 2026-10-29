"""Транспорт «Проспекта», партия 2: ливреи и маски мест — запечь в развёртку кузова игровой сетки (для Painter).

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/livery.py -- \
        <taxi|police|ambulance|van|bus12_over> <игровой .blend (game_kit.py)> <папка Painter>

Ливрея — картинка цвета кузова (основа и рисунок: полосы, шашки, надписи), в Painter — источник цвета эмали
(sp/stack_car.py livery=…/livery_<семья>; поверх неё — всё старение «Краски v2»). Надписи — текст Blender шрифтом
DejaVu Sans Bold (лицензия Bitstream Vera, свободная; файл — _asset_src/fonts, иначе из matplotlib системного Python):
у встроенного Inter контуры «А» и «Д» перекрываются, и заливка «чётно-нечётно» вырезала перекладину. Полосы и шашки — сетки; всё это — наклейки, прижатые к кузову проекцией (Shrinkwrap вдоль
нормали стороны, 4 мм над листом), запечённые излучением «выбранное на активное» в развёртку каждого набора Body.
Не в Painter: рисунок идёт по борту через двери и щели, а развёртка у каждой панели своя — проекции Painter на
раздвинутых деталях дают швы (опыт ВСС-М: узор по форме — запекать в развёртку в Blender).
Маска мест (перевёрнутый автобус) — ч/б: борт, лёгший на асфальт, смятая кромка крыши и разбитый передний угол — те же
места, что у деформации build_bus.overturned; в Painter — маска ссадин (where=…/where_over).
Выход: <папка Painter>/livery/livery_<семья>_<набор>.png, where_<семья>_<набор>.png, _decals_<семья>.blend (наклейки
на кузове — посмотреть, что легло). Надписи — вымышленные фирмы (такси «ВЕРСТА», фургон «ДОМОВОЙ»), без гербов и
эмблем; «ПОЛИЦИЯ», «СКОРАЯ МЕДИЦИНСКАЯ ПОМОЩЬ», «03» — просто слова.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401
import vspecial  # noqa: E402
from game_kit import set_res  # noqa: E402

# цвета ливрей (sRGB)
BLACK, WHITE = (0.03, 0.03, 0.03), (0.90, 0.90, 0.88)
TAXI_YELLOW, POLICE_WHITE, POLICE_BLUE = (0.93, 0.74, 0.12), (0.88, 0.88, 0.86), (0.05, 0.20, 0.52)
AMB_WHITE, AMB_RED = (0.90, 0.90, 0.88), (0.78, 0.07, 0.05)
VAN_WHITE, VAN_BLUE = (0.84, 0.84, 0.80), (0.08, 0.18, 0.42)
_CAP: dict = {}                 # высота прописной «Н» у шрифта при кегле 1 (меряется по сетке: у разных шрифтов кегль разный)
FONTS = (Path(__file__).resolve().parents[2] / "_asset_src" / "fonts" / "DejaVuSans-Bold.ttf",
         Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf"))
PROJ, GAP = 0.6, 0.004          # наклейка: предел проекции, зазор над листом
# поворот рамки стороны: локальные x — направление чтения, y — вверх, z — наружу (нормаль листа)
ROT = {"L": ((0, 0, 1), (1, 0, 0), (0, 1, 0)), "R": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
       "F": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "B": ((-1, 0, 0), (0, 0, 1), (0, 1, 0))}


def lin(c):
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c)


def emission(rgb) -> bpy.types.Material:
    name = "LIV_" + ",".join(f"{c:.2f}" for c in rgb)
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
    """Рамка наклейки снаружи стороны машины (оси машины: X влево, Y назад, Z вверх). u — вдоль чтения (на левом борту
    u = Y, на правом u = −Y, на переде u = X, на корме u = −X), v — высота, out — где плоскость старта по нормали
    стороны (борт: |X|, перёд и корма: |Y|); проекция прижмёт к листу."""
    pos = {"L": (out, u, v), "R": (-out, -u, v), "F": (u, -out, v), "B": (-u, out, v)}[side]
    M = Matrix(ROT[side]).to_4x4()
    M.translation = pos
    return M


def grid(w: float, h: float, step: float = 0.02):
    """Прямоугольник w × h с центром в нуле, частая сетка (проекция повторяет изгиб борта)."""
    nx, ny = max(2, int(w / step) + 1), max(2, int(h / step) + 1)
    xs, ys = np.linspace(-w / 2, w / 2, nx), np.linspace(-h / 2, h / 2, ny)
    V = [(float(x), float(y), 0.0) for y in ys for x in xs]
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
    cu.resolution_u = 6
    ob = bpy.data.objects.new("txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return me


def text_mesh(text: str, cap: float) -> bpy.types.Mesh:
    """Надпись (DejaVu Sans Bold) высотой прописной cap, по центру; заливка — мелкие треугольники."""
    if "H" not in _CAP:
        ref = _glyphs("Н", 1.0)
        zs = [v.co.y for v in ref.vertices]
        _CAP["H"] = max(zs) - min(zs)
        bpy.data.meshes.remove(ref)
    me = _glyphs(text, cap / _CAP["H"])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    long = [e for e in bm.edges if e.calc_length() > 0.02]
    if long:
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return me


class Decals:
    """Наклейки одной семьи: сетки с излучением, прижатые к кузову проекцией по своей нормали (−z рамки)."""

    def __init__(self, target: bpy.types.Object, col: bpy.types.Collection, out: dict):
        self.target, self.col, self.out, self.objs = target, col, out, []

    def _place(self, me: bpy.types.Mesh, M: Matrix, rgb) -> None:
        me.materials.append(emission(rgb))
        ob = bpy.data.objects.new("decal", me)
        self.col.objects.link(ob)
        ob.matrix_world = M
        sw = ob.modifiers.new("press", "SHRINKWRAP")
        sw.target = self.target
        sw.wrap_method = "PROJECT"
        sw.use_project_z = True
        sw.use_negative_direction = True
        sw.use_positive_direction = False
        sw.project_limit = PROJ
        sw.offset = GAP
        self.objs.append(ob)

    def _frame(self, side, u, v, extra):
        M = frame(side, u, v, self.out[side])
        return extra @ M if extra is not None else M

    def rect(self, side, u, v, w, h, rgb, extra=None):
        V, F = grid(w, h)
        me = bpy.data.meshes.new("rect")
        me.from_pydata(V, [], F)
        self._place(me, self._frame(side, u, v, extra), rgb)

    def text(self, side, u, v, s, cap, rgb, extra=None):
        self._place(text_mesh(s, cap), self._frame(side, u, v, extra), rgb)

    def checks(self, side, u0, u1, v_top, cell, rows, rgb_a, rgb_b, extra=None):
        """Шашки: rows рядов квадратов cell от u0 до u1, верх — v_top; в шахматном порядке."""
        n = int((u1 - u0) / cell)
        for r in range(rows):
            for k in range(n):
                rgb = rgb_a if (k + r) % 2 == 0 else rgb_b
                self.rect(side, u0 + (k + 0.5) * cell, v_top - (r + 0.5) * cell, cell, cell, rgb, extra)


def points(col: bpy.types.Collection, *prefixes: str) -> np.ndarray:
    """Вершины деталей семьи по началу имени (без «семья:»), в осях машины."""
    return np.vstack([np.array([v.co[:] for v in o.data.vertices]) for o in col.objects
                      if o.type == "MESH" and o.name.split(":", 1)[-1].startswith(prefixes)])


def u_of(side: str, y: float) -> float:
    """Координата вдоль чтения по Y машины: на левом борту u = y, на правом u = −y."""
    return y if side == "L" else -y


# --- раскладки --------------------------------------------------------------------------------------------

def sedan_layout(col, kind: str, fam: str, src, dcol) -> tuple:
    F = points(col, "Door_F_Skin_L")
    Rr = points(col, "Door_R_Skin_L")
    f0, f1, r0, r1 = F.min(0), F.max(0), Rr.min(0), Rr.max(0)
    allp = points(col, "")
    d = Decals(src, dcol, {"L": f1[0] + 0.10, "R": f1[0] + 0.10, "F": -allp[:, 1].min() + 0.2,
                           "B": allp[:, 1].max() + 0.2})
    yF, yR = (f0[1] + f1[1]) / 2, (r0[1] + r1[1]) / 2
    zd0, zd1 = f0[2], f1[2]
    zm = (zd0 + zd1) / 2
    if kind == "taxi":
        for side in ("L", "R"):
            ua, ub = sorted((u_of(side, f0[1] + 0.06), u_of(side, r1[1] - 0.04)))
            d.checks(side, ua, ub, zd1 - 0.05, 0.065, 2, BLACK, WHITE)
            d.text(side, u_of(side, yF), zm - 0.06, "ТАКСИ", 0.10, BLACK)
            d.text(side, u_of(side, yR), zm - 0.02, "ВЕРСТА", 0.072, BLACK)
            d.text(side, u_of(side, yR), zm - 0.12, "222-22-22", 0.05, BLACK)
        # плафон: «ТАКСИ» и два ряда шашек на передней и задней гранях; у битого плафон опрокинут — рисунок с ним
        yc, z, _ = vspecial.roof_top(points(col, "Roof"))
        knock = None
        if fam == "wreck":
            p = (0.0, yc + 0.075, z + 0.022)
            knock = (Matrix.Translation((0.06, 0.04, 0.0)) @ Matrix.Translation(p) @
                     Matrix.Rotation(math.radians(28.0), 4, "Z") @ Matrix.Rotation(math.radians(-90.0), 4, "X") @
                     Matrix.Translation(tuple(-c for c in p)))
        sign = Decals(src, dcol, {"F": 0.20 - yc, "B": yc + 0.20})
        zs = z + 0.022 + 0.075                    # середина плафона по высоте
        # у опрокинутого задняя грань лежит на крыше: её наклейка ушла бы под лист и легла бы на изнанку крыши
        for side in (("F",) if knock is not None else ("F", "B")):
            sign.text(side, 0.0, zs + 0.028, "ТАКСИ", 0.042, BLACK, extra=knock)
            sign.checks(side, -0.24, 0.24, zs - 0.010, 0.024, 2, BLACK, (0.95, 0.93, 0.82), extra=knock)
        d.objs += sign.objs
        return d, TAXI_YELLOW
    # полиция: синяя полоса по низу дверей, «ПОЛИЦИЯ» над ней на передней двери (через щель между дверями «И»
    # разрезалась стойкой), бортовой номер на заднем крыле
    Q = points(col, "Bodyside_L")
    for side in ("L", "R"):
        # концы полосы — по краю дверей на высоте полосы: задняя дверь у колёсного проёма скруглена, и полоса до её
        # дальнего края ложилась за скругление «лесенкой» на кромку проёма
        zb0, zb1 = zd0 + 0.12, zd0 + 0.30
        # край двери — у нижней кромки полосы: выше скруглённая у проёма дверь тянется дальше назад
        low = (zb0 - 0.02, zb0 + 0.03)
        yb0 = float(F[(F[:, 2] > zb0) & (F[:, 2] < zb1)][:, 1].min()) + 0.03
        yb1 = float(Rr[(Rr[:, 2] > low[0]) & (Rr[:, 2] < low[1])][:, 1].max()) - 0.04
        ua, ub = sorted((u_of(side, yb0), u_of(side, yb1)))
        d.rect(side, (ua + ub) / 2, (zb0 + zb1) / 2, ub - ua, zb1 - zb0, POLICE_BLUE)
        d.text(side, u_of(side, yF), zd0 + 0.43, "ПОЛИЦИЯ", 0.10, POLICE_BLUE)
        d.text(side, u_of(side, (r1[1] + Q[:, 1].max()) / 2 - 0.05), zd1 - 0.14, "07-23", 0.075, POLICE_BLUE)
    return d, POLICE_WHITE


def van_layout(col, kind: str, src, dcol) -> tuple:
    S = points(col, "Side_L")
    allp = points(col, "")
    d = Decals(src, dcol, {"L": S[:, 0].max() + 0.10, "R": S[:, 0].max() + 0.10, "F": -allp[:, 1].min() + 0.2,
                           "B": allp[:, 1].max() + 0.2})
    if kind == "ambulance":
        for side in ("L", "R"):
            ua, ub = sorted((u_of(side, -1.62), u_of(side, 2.94)))
            d.rect(side, (ua + ub) / 2, 1.095, ub - ua, 0.15, AMB_RED)
            d.text(side, u_of(side, 1.35), 2.14, "СКОРАЯ МЕДИЦИНСКАЯ ПОМОЩЬ", 0.10, AMB_RED)
            d.text(side, u_of(side, 2.62), 1.55, "03", 0.20, AMB_RED)
        d.text("B", 0.0, 1.02, "03", 0.22, AMB_RED)
        d.text("F", 0.0, 2.36, "03", 0.16, AMB_RED)
        return d, AMB_WHITE
    for side in ("L", "R"):
        d.text(side, u_of(side, 1.35), 1.62, "ДОМОВОЙ", 0.24, VAN_BLUE)
        d.text(side, u_of(side, 1.35), 1.36, "ПЕРЕЕЗДЫ · ДОСТАВКА · ГРУЗЧИКИ", 0.085, VAN_BLUE)
    d.text("B", 0.0, 1.62, "ДОМОВОЙ", 0.13, VAN_BLUE)
    return d, VAN_WHITE


# --- запекание ------------------------------------------------------------------------------------------

def gpu() -> None:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            bpy.context.scene.cycles.device = "GPU"
            return
    bpy.context.scene.cycles.device = "CPU"


def joined_copy(objs, name: str) -> bpy.types.Object:
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


def bake_into(target: bpy.types.Object, sources: list, img: bpy.types.Image, selected: bool) -> None:
    """EMIT в картинку по развёртке цели: selected — с наклеек и кузова снаружи; иначе — из атрибута вершин «where»."""
    m = bpy.data.materials.new("_bake")
    m.use_nodes = True
    nt = m.node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    if not selected:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "where"
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(attr.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    target.data.materials.clear()
    target.data.materials.append(m)
    bpy.ops.object.select_all(action="DESELECT")
    for s in sources:
        s.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.bake(type="EMIT", use_selected_to_active=selected, cage_extrusion=0.012, max_ray_distance=0.03,
                        margin=8, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")


def where_weights(P: np.ndarray, spec: dict) -> np.ndarray:
    """Маска мест перевёрнутого: борт снизу (+X), смятая кромка крыши с той же стороны, разбитый передний левый угол."""
    def ss(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3 - 2 * t)
    hw, H = spec["width"] / 2, spec["height"]
    x, z = P[:, 0], P[:, 2]
    side = ss(hw - 0.30, hw - 0.07, x)
    edge = 1.0 - ss(0.0, 0.55, np.hypot(np.clip(hw - x, 0, None), np.clip(H - z, 0, None)))
    yf = float(P[:, 1].min())
    corner = 1.0 - ss(0.0, 1.1, np.linalg.norm(P - np.array([hw, yf + 0.35, 0.8]), axis=1))
    return np.clip(np.maximum.reduce([side, edge, corner * 0.9]), 0.0, 1.0)


def clean_crumbs(img: bpy.types.Image, target: bpy.types.Object, base) -> int:
    """Крошки развёртки (вырезанные треугольники загибов, vuv.py) лежат внахлёст — одна клетка на материал; наклейка,
    попавшая на одну крошку, красила все (синие крапины по кромкам у полиции). Где треугольники развёртки перекрываются
    (и на 2 пикселя вокруг — поле запекания), — основной цвет ливреи. Возвращает число перекрашенных пикселей."""
    w, h = img.size
    cnt = np.zeros((h, w), np.int16)
    me = target.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    for t in me.loop_triangles:
        P = np.array([uv[i].uv[:] for i in t.loops]) * (w, h)
        x0, y0 = np.floor(P.min(0)).astype(int)
        x1, y1 = np.ceil(P.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
        a, b, c = P
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(d) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
        cnt[y0:y1 + 1, x0:x1 + 1] += (l1 >= 0) & (l2 >= 0) & (1 - l1 - l2 >= 0)
    over = cnt >= 2
    for _ in range(2):                            # раздуть на 2 пикселя: поле запекания вокруг крошек
        over = over | np.roll(over, 1, 0) | np.roll(over, -1, 0) | np.roll(over, 1, 1) | np.roll(over, -1, 1)
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    px[over, :3] = base                           # у картинки sRGB пиксели хранятся в sRGB — цвет как есть
    img.pixels.foreach_set(px.ravel())
    return int(over.sum())


def save(img: bpy.types.Image, path: Path) -> None:
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    kind, game, sp_dir = argv[0], Path(argv[1]), Path(argv[2])
    out = sp_dir / "livery"
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(game))
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    gpu()
    scn.cycles.samples = 4
    from specs_bus import BOXES
    for col in [c for c in bpy.data.collections if c.name.startswith("LOD0_")]:
        fam = col.name[5:]
        body = [o for o in col.objects if o.type == "MESH" and o["tex_set"].startswith("Body")]
        sets = sorted({o["tex_set"] for o in body})
        if kind == "bus12_over":
            for ts in sets:
                tgt = joined_copy([o for o in body if o["tex_set"] == ts], f"_where_{ts}")
                P = np.array([v.co[:] for v in tgt.data.vertices])
                w = where_weights(P, BOXES[kind])
                a = tgt.data.color_attributes.new("where", "FLOAT_COLOR", "POINT")
                rgba = np.c_[w, w, w, np.ones_like(w)].astype(np.float32).ravel()
                a.data.foreach_set("color", rgba)
                res = set_res(kind, ts)
                img = bpy.data.images.new(f"where_{fam}_{ts}", res, res, alpha=False)
                img.colorspace_settings.name = "Non-Color"
                bake_into(tgt, [], img, selected=False)
                save(img, out / f"where_{fam}_{ts}.png")
                print(f"маска мест {fam}/{ts}: {res}², доля места {float(w.mean()):.2f}")
            continue
        dcol = bpy.data.collections.new("_decals")
        scn.collection.children.link(dcol)
        src = joined_copy(body, "_body")
        d, base = sedan_layout(col, kind, fam, src, dcol) if kind in ("taxi", "police") else van_layout(col, kind, src, dcol)
        src.data.materials.append(emission(base))
        dg = bpy.context.evaluated_depsgraph_get()
        for o in d.objs:                          # прижать: модификатор применить (материал наклейки остаётся)
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            o.modifiers.clear()
            o.data = me
        for ts in sets:
            tgt = joined_copy([o for o in body if o["tex_set"] == ts], f"_tgt_{ts}")
            res = set_res(kind, ts)
            img = bpy.data.images.new(f"livery_{fam}_{ts}", res, res, alpha=False)
            img.colorspace_settings.name = "sRGB"
            bake_into(tgt, [src] + d.objs, img, selected=True)
            n_crumbs = clean_crumbs(img, tgt, base)
            save(img, out / f"livery_{fam}_{ts}.png")
            print(f"ливрея {fam}/{ts}: {res}², наклеек {len(d.objs)}, основа {base}, крошек перекрашено {n_crumbs} пикс.")
            bpy.data.objects.remove(tgt)
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"_decals_{fam}.blend"), copy=True)
        for o in list(dcol.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(dcol)
        bpy.data.objects.remove(src)


main()
