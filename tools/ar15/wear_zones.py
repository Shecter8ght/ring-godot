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
#   blender -b <AR15_uv_v03.blend> --python tools/ar15/wear_zones.py -- <папка вывода> [размер 2048] [размер углов 4096]
# Пишет grip_zone_<palm|fingers|thumb|base|ribs>.png и grip_zone_<rib_dirt|rib_dust>.png (ч/б, 16 бит) в папку вывода;
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
ZONES = ("palm", "fingers", "thumb", "base", "ribs")
AO_DIST = 1.2                                     # радиус AO углов, мм: стык рёбрышка (высота 0,45) с телом
AREA_MM = (1.2, 2.0)                              # область углов — до 2 мм от рёбрышек (плавно с 1,2)
DIRT_MM, DUST_MM = 0.3, 0.75                      # ширина полос грязи и пыли от края рёбрышка (шаг рёбрышек 2,6 мм:
                                                  # пыль по 1,2 мм заливала выемку между ними целиком)


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


def ribs_area(o, p):
    """Рёбрышки (куски сетки 4…40 мм — бугорки насечки ~1 мм, тело ~110 мм) и область углов вокруг них."""
    from mathutils import kdtree
    lab = components(o.data)
    u, inv = np.unique(lab, return_inverse=True)
    mn = np.full((len(u), 3), 1e9); mx = np.full((len(u), 3), -1e9)
    np.minimum.at(mn, inv, p); np.maximum.at(mx, inv, p)
    ext = (mx - mn).max(1)
    rib = ((ext > 4.0) & (ext < 40.0))[inv]
    print("RIBS кусков:", int(((ext > 4.0) & (ext < 40.0)).sum()), "вершин:", int(rib.sum()))
    kd = kdtree.KDTree(int(rib.sum()))
    for i, q in enumerate(p[rib]):
        kd.insert(Vector(q), i)
    kd.balance()
    near = [kd.find(Vector(q)) for q in p]
    d = np.array([f[2] for f in near])
    area = 1.0 - sstep(AREA_MM[0], AREA_MM[1], d)
    # над рёбрышком или под ним: пыль оседает в верхнем углу (рукоять стоит рукоятью вниз)
    zr = p[rib][:, 2]
    above = sstep(-0.15, 0.15, p[:, 2] - np.array([zr[f[1]] for f in near]))
    return rib.astype(np.float64), area, above


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
    ribs, area, above = ribs_area(o, p)
    return {"palm": palm, "fingers": fingers, "thumb": thumb, "base": base, "ribs": ribs, "rib_area": area,
            "rib_above": above}


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
    for key, kind in (("area", "EMIT"), ("ribs", "EMIT"), ("above", "EMIT"), ("ao", "AO")):
        if kind == "EMIT":
            data = np.zeros((len(me.vertices), 4), dtype=np.float32)
            data[:, 0] = data[:, 1] = data[:, 2] = w["rib_" + key if key != "ribs" else "ribs"]
            data[:, 3] = 1.0
            attr.data.foreach_set("color", data.ravel())
        img = bpy.data.images.new(f"grip_corner_{key}", size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        nt.nodes.active = tex
        if kind == "AO":
            S.world.light_settings.distance = AO_DIST * MM
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
    for k, a in (("rib_dirt", dirt), ("rib_dust", dust)):
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
