# AR-15 «ГРАНЬ-15», этап 2 (износ): маски МЕСТ хвата рукояти, запечённые в развёртку набора текстур (UVMap — та же,
# что в проекте Painter). Клипов рук от первого лица у AR-15 ещё нет (tools/wear_from_use нечем кормить), поэтому места —
# по форме рукояти и правому хвату: ладонь — спинка и правый бок (кроме переда), пальцы — передние выемки и кончики на
# переднем крае левого бока, большой палец — левый бок вверху, низ — торец. Рисунок следа (отпечаток, развод, пыль) —
# фото-маски CC0 в Painter (sp_ar15_wear.py); здесь только «где».
# Рёбрышки в выемках под пальцы (владелец 30.10): сами рёбрышки заглажены пальцами — глянец; в углах их стыка с телом —
# грязь и пыль. Рёбрышки — отдельные куски сетки (part_grip.ribs). Угол на теле — полоса по развёртке от края места,
# закрытого рёбрышком (там AO с радиусом 1,2 мм — полная тень): до 0,3 мм — грязь, до 0,75 мм — пыль (рёбрышко
# 0,45 мм почти не даёт тени AO, и угол по одному AO выходил в пару пикселей); на самом рёбрышке — низ боков по AO.
# Пыль гуще в верхнем углу (над рёбрышком), грязь — в обоих.
# Пупырышки на боковых площадках (владелец 30.10): так же — вершины заглажены, в углах у основания грязь, пыли нет;
# справа (ладонь) — вся площадка, слева — только место большого пальца: он обхватывает левый бок наискосок (основание
# сзади вверху, подушечка вперёд и вниз на уровне среднего пальца) — пятно ~30 × 18 мм в верхней части площадки.
#   blender -b <AR15_uv_v03.blend> --python tools/ar15/wear_zones.py -- <папка вывода> [размер 2048] [размер углов 4096]
# Пишет grip_zone_<palm|fingers|thumb|base|ribs|stip_gloss|panels>.png и grip_zone_<rib_dirt|rib_dust|stip_dirt>.png
# (ч/б, 16 бит) в папку вывода;
# 8-битные копии и объединения зон для Painter — tools/ar15/wear_masks.py.
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

from lib import GRIP_TOP_Z, GRIP_SCREW_X  # noqa: F401  (ось рукояти — те же числа, что в part_grip)

MM = 0.001
ANGLE = math.radians(18.0)                       # part_grip.ANGLE
TOP = Vector((-147.0, 0.0, GRIP_TOP_Z))           # part_grip.TOP (TOP_CX, GRIP_TOP_Z)
DOWN = Vector((-math.sin(ANGLE), 0.0, -math.cos(ANGLE)))
FWD = Vector((math.cos(ANGLE), 0.0, -math.sin(ANGLE)))
ZONES = ("palm", "fingers", "thumb", "base", "ribs", "stip_gloss", "panels")
AO_DIST = 1.2                                     # радиус AO углов, мм: стык рёбрышка (высота 0,45) с телом
AREA_MM = (1.2, 2.0)                              # область углов — до 2 мм от рёбрышек (плавно с 1,2)
DIRT_MM, DUST_MM = 0.3, 0.75                      # ширина полос грязи и пыли от края рёбрышка (шаг рёбрышек 2,6 мм:
                                                  # пыль по 1,2 мм заливала выемку между ними целиком)
STIP_AREA_MM = (0.9, 1.4)                         # дно площадки между пупырышками (шаг 1,7 мм)
STIP_DIRT_MM = 0.22                               # полоса грязи у основания пупырышка
AO_STIP = 0.3                                     # свой радиус AO у пупырышков (низ их боков), мм
STIP_FOOT = 0.443 / 0.55                          # сечение пупырышка на уровне дна к его низу: усечённая пирамида, низ
                                                  # 1,1 мм на 0,25 мм в дне, верх 0,56 мм на 0,38 над дном (part_grip.stipple)
THUMB_PANEL = (54.0, 0.55, 30.0, 15.0, 9.0)       # пятно большого пальца на левой площадке: s центра (мм вниз от верха
                                                  # рукояти), доля ширины площадки вперёд, наклон (° вперёд-вниз), полуоси


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def window(x, a0, a1, b0, b1):
    """1 между a1 и b0, плавно к нулю до a0 и после b1."""
    return sstep(a0, a1, x) * (1.0 - sstep(b0, b1, x))


def components(me):
    """Номер куска сетки у каждой вершины (связность по рёбрам; распространение меньшего номера со сжатием путей)."""
    n = len(me.vertices)
    e = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    lab = np.arange(n)
    while True:
        old = lab.copy()
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        np.minimum.at(lab, e[:, 0], m)
        np.minimum.at(lab, e[:, 1], m)
        lab = lab[lab[lab]]
        if (lab == old).all():
            return lab


def _near(p, sel):
    """Ближайшая вершина из sel для каждой вершины: (расстояние, номер среди sel)."""
    from mathutils import kdtree
    kd = kdtree.KDTree(int(sel.sum()))
    for i, q in enumerate(p[sel]):
        kd.insert(Vector(q), i)
    kd.balance()
    near = [kd.find(Vector(q)) for q in p]
    return np.array([f[2] for f in near]), np.array([f[1] for f in near])


def parts(o, p):
    """Куски сетки: рёбрышки (4…40 мм), пупырышки насечки (< 4 мм), тело (~110 мм); области углов вокруг них."""
    lab = components(o.data)
    u, inv = np.unique(lab, return_inverse=True)
    mn = np.full((len(u), 3), 1e9); mx = np.full((len(u), 3), -1e9)
    np.minimum.at(mn, inv, p); np.maximum.at(mx, inv, p)
    ext = (mx - mn).max(1)
    rib = ((ext > 4.0) & (ext < 40.0))[inv]
    stip = (ext < 4.0)[inv]
    print("RIBS кусков:", int(((ext > 4.0) & (ext < 40.0)).sum()), "вершин:", int(rib.sum()),
          "| пупырышков:", int((ext < 4.0).sum()))
    d, k = _near(p, rib)
    area = 1.0 - sstep(AREA_MM[0], AREA_MM[1], d)
    # над рёбрышком или под ним: пыль оседает в верхнем углу (рукоять стоит рукоятью вниз)
    above = sstep(-0.15, 0.15, p[:, 2] - p[rib][:, 2][k])
    ds, _ = _near(p, stip)
    stip_area = (1.0 - sstep(STIP_AREA_MM[0], STIP_AREA_MM[1], ds)) * (1.0 - rib)
    return {"ribs": rib.astype(np.float64), "rib_area": area, "rib_above": above, "stip": stip.astype(np.float64),
            "stip_area": stip_area}


def weights(o):
    me = o.data
    mw = o.matrix_world
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    nor = np.empty(n * 3); me.vertices.foreach_get("normal", nor)
    nor = nor.reshape(n, 3)
    M = np.array(mw)
    p = (co @ M[:3, :3].T + M[:3, 3]) / MM
    nw = nor @ np.linalg.inv(M[:3, :3])
    nw /= np.linalg.norm(nw, axis=1, keepdims=True) + 1e-12
    d = p - np.array(TOP)
    s = d @ np.array(DOWN)                      # вниз по рукояти от площадки, мм
    u = d @ np.array(FWD)                       # вперёд поперёк оси, мм
    nb, nf, ny, nd = nw @ -np.array(FWD), nw @ np.array(FWD), nw[:, 1], nw @ np.array(DOWN)
    # доля по глубине сечения: 0 — спинка, 1 — перёд (по ближайшим к этой высоте точкам)
    bins = np.floor(s / 2.0).astype(int)
    umin, umax = {}, {}
    for b, uu in zip(bins, u):
        umin[b] = min(umin.get(b, 1e9), uu)
        umax[b] = max(umax.get(b, -1e9), uu)
    t = np.array([(uu - umin[b]) / max(umax[b] - umin[b], 1.0) for b, uu in zip(bins, u)])
    palm = np.maximum(sstep(0.25, 0.6, nb), 0.85 * sstep(0.4, 0.8, -ny) * (1.0 - sstep(0.55, 0.85, t)))
    palm *= window(s, 4.0, 12.0, 92.0, 102.0)
    front = sstep(0.3, 0.7, nf) * window(s, 30.0, 38.0, 98.0, 104.0)
    tips = 0.8 * sstep(0.4, 0.8, ny) * sstep(0.55, 0.85, t) * window(s, 34.0, 42.0, 96.0, 102.0)
    fingers = np.maximum(front, tips)
    thumb = sstep(0.4, 0.8, ny) * window(s, -2.0, 4.0, 22.0, 32.0) * window(t, 0.1, 0.3, 0.75, 0.9)
    # торец и его кромка; вниз смотрит ещё низ выступа под скобой (s ≈ 35) — он не «низ»
    base = np.maximum(sstep(0.5, 0.85, nd) * sstep(80.0, 92.0, s), 0.6 * sstep(97.0, 102.0, s))
    w = {"palm": palm, "fingers": fingers, "thumb": thumb, "base": base}
    w.update(parts(o, p))
    # пупырышки: справа (ладонь) — вся площадка, слева — пятно большого пальца
    st = w["stip"] > 0.5
    left = st & (p[:, 1] > 0)
    s0, f0, ang, a, b = THUMB_PANEL
    uc = u[left].min() + f0 * (u[left].max() - u[left].min())
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    du, dv = u - uc, s - s0
    r = np.sqrt(((du * ca + dv * sa) / a) ** 2 + ((-du * sa + dv * ca) / b) ** 2)
    w["stip_w"] = np.where(p[:, 1] < 0, 1.0, 1.0 - sstep(0.75, 1.1, r))
    w["stip_gloss"] = w["stip"] * w["stip_w"]
    w["panels"] = np.maximum(w["stip"], w["stip_area"])
    print("THUMB на левой площадке: пупырышков вершин с весом > 0,5:", int((left & (w["stip_w"] > 0.5)).sum()),
          "из", int(left.sum()))
    return w


def _setup(o):
    S = bpy.context.scene
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.render.bake.margin = 16
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    o.hide_set(False); o.hide_render = False
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    return S


def _save16(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_depth = "16"
    img.save_render(path)


def _pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def texel_mm(me, vals, size):
    """Пикселей на мм у граней с vals > 0,5 (площадь развёртки к площади поверхности)."""
    uv = me.uv_layers["UVMap"].data
    a3 = a2 = 0.0
    for p in me.polygons:
        if max(vals[i] for i in p.vertices) < 0.5:
            continue
        a3 += p.area / (MM * MM)
        q = [uv[li].uv for li in p.loop_indices]
        for k in range(1, len(q) - 1):
            a2 += abs((q[k].x - q[0].x) * (q[k + 1].y - q[0].y) - (q[k + 1].x - q[0].x) * (q[k].y - q[0].y)) / 2.0
    return math.sqrt(a2 * size * size / max(a3, 1e-9))


def _dist(src, steps):
    """Расстояние в пикселях от src (bool) до steps: наращивание крестом и квадратом по очереди (восьмиугольник)."""
    d = np.full(src.shape, np.inf, dtype=np.float32)
    d[src] = 0.0
    f = src.copy()
    for i in range(1, steps + 1):
        g = f.copy()
        g[1:, :] |= f[:-1, :]; g[:-1, :] |= f[1:, :]; g[:, 1:] |= f[:, :-1]; g[:, :-1] |= f[:, 1:]
        if i % 2 == 0:
            g[1:, 1:] |= f[:-1, :-1]; g[:-1, :-1] |= f[1:, 1:]; g[1:, :-1] |= f[:-1, 1:]; g[:-1, 1:] |= f[1:, :-1]
        d[g & ~f] = float(i)
        f = g
    return d


def stip_footprints(o, w, size):
    """Места дна площадки под пупырышками — по геометрии, а не по AO: при радиусе 1,2 мм затенено всё дно между ними
    (шаг 1,7 мм — дно выходило грязным целиком), при 0,3 мм лучи из середины основания не достают до боков. Сечение
    каждого пупырышка на уровне дна переносится на ближайшие грани дна и закрашивается в их развёртке."""
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
    me = o.data
    me.calc_loop_triangles()
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    body = (w["stip"] < 0.5) & (w["ribs"] < 0.5)
    tris = [t for t in me.loop_triangles if body[t.vertices[0]] and body[t.vertices[1]] and body[t.vertices[2]]]
    verts = [Vector(q) for q in co]
    bvh = BVHTree.FromPolygons(verts, [tuple(t.vertices) for t in tris])
    uvl = me.uv_layers["UVMap"].data
    lab = components(me)
    mask = np.zeros((size, size), dtype=bool)
    skipped = 0
    for c in np.unique(lab[w["stip"] > 0.5]):
        idx = np.nonzero(lab == c)[0]
        ay = np.abs(co[idx, 1])
        low = idx[np.argsort(ay)[:4]]                 # низ пупырышка — ближе к оси рукояти (глубже в дне)
        cb = co[low].mean(0)
        pts = []
        for q in co[low]:
            loc, _n, ti, _d = bvh.find_nearest(Vector(cb + (q - cb) * STIP_FOOT))
            t = tris[ti]
            uvs = [Vector((*uvl[li].uv, 0.0)) for li in t.loops]
            uv = barycentric_transform(loc, verts[t.vertices[0]], verts[t.vertices[1]], verts[t.vertices[2]], *uvs)
            pts.append((uv.x * size, uv.y * size))
        pts = np.array(pts)
        c0 = pts.mean(0)
        pts = pts[np.argsort(np.arctan2(pts[:, 1] - c0[1], pts[:, 0] - c0[0]))]   # обход по кругу
        x0, y0 = np.floor(pts.min(0)).astype(int)
        x1, y1 = np.ceil(pts.max(0)).astype(int)
        if x1 - x0 > 60 or y1 - y0 > 60 or x0 < 0 or y0 < 0 or x1 >= size or y1 >= size:
            skipped += 1                              # углы разошлись по разным островам (шов) — пропуск
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        inside = np.ones(gx.shape, dtype=bool)
        sgn = []
        for k in range(4):
            a, b = pts[k], pts[(k + 1) % 4]
            sgn.append((b[0] - a[0]) * (gy - a[1]) - (b[1] - a[1]) * (gx - a[0]))
        inside = np.all([q >= 0 for q in sgn], axis=0) | np.all([q <= 0 for q in sgn], axis=0)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside
    print("STIP основания: пупырышков", len(np.unique(lab[w["stip"] > 0.5])), "пропущено на швах", skipped,
          "пикселей", int(mask.sum()))
    return mask


def bake_corners(o, w, out_dir, size):
    """Углы у рёбрышек: на теле — полосы грязи и пыли от края закрытого рёбрышком места (по AO), на рёбрышке — низ
    боков по AO; всё в пределах области рёбрышек. AO — только по самой рукояти: остальные детали скрыты от рендера,
    иначе ресивер затенял бы верх."""
    me = o.data
    hidden = [ob for ob in bpy.data.objects if ob != o and not ob.hide_render]
    for ob in hidden:
        ob.hide_render = True
    attr = me.color_attributes.get("wz") or me.color_attributes.new("wz", "FLOAT_COLOR", "POINT")
    mat = bpy.data.materials.new("wz_corner")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "wz"
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    old = list(me.materials)
    me.materials.clear(); me.materials.append(mat)
    S = _setup(o)
    if S.world is None:
        S.world = bpy.data.worlds.new("wz_world")
    res = {}
    src = {"area": "rib_area", "ribs": "ribs", "above": "rib_above", "stip": "stip", "stip_area": "stip_area",
           "stip_w": "stip_w"}
    for key, kind in [(k, "EMIT") for k in src] + [("ao", "AO"), ("ao_s", "AO")]:
        if kind == "EMIT":
            data = np.zeros((len(me.vertices), 4), dtype=np.float32)
            data[:, 0] = data[:, 1] = data[:, 2] = w[src[key]]
            data[:, 3] = 1.0
            attr.data.foreach_set("color", data.ravel())
        img = bpy.data.images.new(f"grip_corner_{key}", size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        nt.nodes.active = tex
        if kind == "AO":
            S.world.light_settings.distance = (AO_DIST if key == "ao" else AO_STIP) * MM
            S.cycles.samples = 128
        else:
            S.cycles.samples = 1
        bpy.ops.object.bake(type=kind)
        res[key] = _pixels(img)[..., 0].copy()
    me.materials.clear()
    for m in old:
        me.materials.append(m)
    for ob in hidden:
        ob.hide_render = False
    occl = 1.0 - res["ao"]
    area = np.clip(res["area"], 0.0, 1.0)
    rib = res["ribs"] > 0.5
    px = texel_mm(me, w["rib_area"], size)
    under = (~rib) & (area > 0.5) & (occl > 0.85)          # тело под рёбрышком — закрыто целиком
    d = _dist(under, int(math.ceil(DUST_MM * px)) + 2) / px   # мм от края
    body = (~rib) * area
    dirt = np.where(rib, area * sstep(0.30, 0.65, occl), body * (1.0 - sstep(0.6 * DIRT_MM, DIRT_MM, d)))
    dust = body * sstep(0.5 * DIRT_MM, DIRT_MM, d) * (1.0 - sstep(0.4 * DUST_MM, DUST_MM, d))
    dust *= 0.45 + 0.55 * np.clip(res["above"], 0.0, 1.0)     # в верхнем углу пыли больше
    print("CORNERS пикс/мм:", round(px, 1), "под рёбрышками пикселей:", int(under.sum()))
    # пупырышки: только грязь у основания (пыли нет — владелец), на самом пупырышке — низ боков по AO; вес стороны
    isl = res["stip"] > 0.5
    sa = np.clip(res["stip_area"], 0.0, 1.0)
    sw = np.clip(res["stip_w"], 0.0, 1.0)
    pxs = texel_mm(me, w["stip_area"], size)
    occs = 1.0 - res["ao_s"]
    under_s = stip_footprints(o, w, size) & (~isl) & (~rib)
    ds = _dist(under_s, int(math.ceil(STIP_DIRT_MM * pxs)) + 2) / pxs
    stip_dirt = sw * np.where(isl, sstep(0.45, 0.8, occs), sa * (1.0 - sstep(0.6 * STIP_DIRT_MM, STIP_DIRT_MM, ds)))
    floor = (~isl) & (~rib) & (sa > 0.5)
    print("STIP дно: закрыто пупырышками %.2f, в грязи %.2f" % (under_s[floor].mean(), (stip_dirt[floor] > 0.5).mean()))
    print("STIP пикс/мм:", round(pxs, 1), "под пупырышками пикселей:", int(under_s.sum()))
    for k, a in (("rib_dirt", dirt), ("rib_dust", dust), ("stip_dirt", stip_dirt)):
        img = bpy.data.images.new(f"grip_zone_{k}", size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        buf = np.zeros((size, size, 4), dtype=np.float32)
        buf[..., 0] = buf[..., 1] = buf[..., 2] = a
        buf[..., 3] = 1.0
        img.pixels.foreach_set(buf.ravel())
        _save16(img, os.path.join(out_dir, f"grip_zone_{k}.png"))
        print("ZONE", k, "пикселей > 0,5:", int((a > 0.5).sum()))


def bake(o, w, out_dir, size):
    me = o.data
    attr = me.color_attributes.get("wz") or me.color_attributes.new("wz", "FLOAT_COLOR", "POINT")
    mat = bpy.data.materials.new("wz_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "wz"
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    old = list(me.materials)
    me.materials.clear(); me.materials.append(mat)
    S = bpy.context.scene
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 1
    S.render.bake.margin = 16
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    o.hide_set(False); o.hide_render = False
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    me.uv_layers.active = me.uv_layers["UVMap"]
    os.makedirs(out_dir, exist_ok=True)
    keys = list(ZONES)
    for k in keys:
        vals = w[k]
        data = np.zeros((len(me.vertices), 4), dtype=np.float32)
        data[:, 0] = data[:, 1] = data[:, 2] = vals
        data[:, 3] = 1.0
        attr.data.foreach_set("color", data.ravel())
        img = bpy.data.images.new(f"grip_zone_{k}", size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        nt.nodes.active = tex
        bpy.ops.object.bake(type="EMIT")
        img.filepath_raw = os.path.join(out_dir, f"grip_zone_{k}.png")
        img.file_format = "PNG"
        S.render.image_settings.color_depth = "16"
        img.save_render(img.filepath_raw)
        print("ZONE", k, "доля >0.5:", round(float((vals > 0.5).mean()), 3), "→", img.filepath_raw)
    me.materials.clear()
    for m in old:
        me.materials.append(m)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out_dir = a[0]
    size = int(a[1]) if len(a) > 1 else 2048
    corner = int(a[2]) if len(a) > 2 else 4096
    o = bpy.data.objects["Pistol_grip"]
    w = weights(o)
    bake(o, w, out_dir, size)
    bake_corners(o, w, out_dir, corner)


if __name__ == "__main__":
    main()
