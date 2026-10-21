"""NPC: швы, отстрочка и карманы — карты рельефа и масок по развёрткам лекал.

Развёртка вещи — координаты лекала в метрах (UV_Pattern). Края островов развёртки — это швы и
подгибки кроя. Вдоль них рисуем углубление шва и строчку нитками на 4 и 9 мм внутрь (у брюк —
4 и 10), пунктиром стежков 3,2 мм; у трикотажа — только шов. Карманы и клапаны задаются точками
на теле (3D) и переносятся на развёртку ближайшей точкой поверхности.
Выход — PNG в _asset_src/npc_kit/tex_gen: <вещь>_height (высота, 16 бит) и <вещь>_mask
(R — нитка, G — грязь в шве) и узлы в материалах (рельеф поверх фото, цвет нитки и грязи).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/details.py [-- render]
(читает и пересохраняет _asset_src/npc_kit/npc_scav_<версия>.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import mathutils.geometry as mg
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

GEN = kc.WORK / "tex_gen"
PX_PER_M = 1600.0          # 0,6 мм на пиксель
STITCH, GAP = 0.0032, 0.0018


# ---------- края развёртки ----------

def uv_half_edges(obj: bpy.types.Object):
    """Стороны граней на краю острова развёртки: (uv1, uv2, центр грани в uv, материал)."""
    me = obj.data
    uv = me.uv_layers["UV_Pattern"].data
    edge_uv: dict[tuple[int, int], list[tuple]] = {}
    for poly in me.polygons:
        mat = me.materials[poly.material_index].name if me.materials else ""
        loops = list(poly.loop_indices)
        cu = sum((Vector(uv[li].uv) for li in loops), Vector((0, 0))) / len(loops)
        for k, li in enumerate(loops):
            lj = loops[(k + 1) % len(loops)]
            a, b = me.loops[li].vertex_index, me.loops[lj].vertex_index
            ua, ub = Vector(uv[li].uv), Vector(uv[lj].uv)
            if a > b:
                a, b, ua, ub = b, a, ub, ua
            edge_uv.setdefault((a, b), []).append((ua, ub, cu, mat))
    out = []
    for sides in edge_uv.values():
        if len(sides) == 1:
            out.append(sides[0])
        elif (sides[0][0] - sides[1][0]).length > 1e-5 or (sides[0][1] - sides[1][1]).length > 1e-5:
            out.extend(sides[:2])
    return out


def chains(half_edges) -> list[tuple[list[Vector], list[Vector], str]]:
    """Сшить отрезки в цепочки: точки и направление «внутрь острова» в каждой точке."""
    def key(v: Vector) -> tuple:
        return (round(v.x, 5), round(v.y, 5))
    adj: dict[tuple, list[int]] = {}
    for i, (a, b, c, m) in enumerate(half_edges):
        adj.setdefault(key(a), []).append(i)
        adj.setdefault(key(b), []).append(i)
    used = [False] * len(half_edges)
    result = []
    for i in range(len(half_edges)):
        if used[i]:
            continue
        used[i] = True
        a, b, c, m = half_edges[i]
        pts, cents = [a, b], [c, c]
        for forward in (True, False):
            while True:
                end = pts[-1] if forward else pts[0]
                nxt = next((j for j in adj.get(key(end), []) if not used[j] and half_edges[j][3] == m), None)
                if nxt is None:
                    break
                used[nxt] = True
                a2, b2, c2, _ = half_edges[nxt]
                other = b2 if key(a2) == key(end) else a2
                if forward:
                    pts.append(other)
                    cents.append(c2)
                else:
                    pts.insert(0, other)
                    cents.insert(0, c2)
        inward = [((c - p).normalized() if (c - p).length > 1e-9 else Vector((0, 0))) for p, c in zip(pts, cents)]
        result.append((pts, inward, m))
    return result


def resample_polyline(pts: list[Vector], step: float) -> tuple[np.ndarray, np.ndarray]:
    """Точки ломаной через step и их расстояние от начала (для пунктира)."""
    a = np.array([(p.x, p.y) for p in pts], np.float64)
    if len(a) < 2:
        return a.astype(np.float32), np.zeros(len(a))
    seg = np.diff(a, axis=0)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    if cum[-1] <= 0:
        return a[:1].astype(np.float32), np.zeros(1)
    t = np.arange(0.0, cum[-1], step)
    return np.stack([np.interp(t, cum, a[:, 0]), np.interp(t, cum, a[:, 1])], 1).astype(np.float32), t


# ---------- холст ----------

class Canvas:
    """Холст в метрах развёртки: слои numpy, кисть наносится во множество точек разом."""

    def __init__(self, umin: Vector, umax: Vector, px: float):
        self.o = umin - Vector((0.01, 0.01))
        size = (umax - umin) + Vector((0.02, 0.02))
        self.px = px
        self.w = int(size.x * px) + 1
        self.h = int(size.y * px) + 1
        self.raised = np.zeros((self.h, self.w), np.float32)
        self.groove = np.zeros((self.h, self.w), np.float32)
        self.thread = np.zeros((self.h, self.w), np.float32)
        self.grime = np.zeros((self.h, self.w), np.float32)

    def stamp(self, arr: np.ndarray, pts_m: np.ndarray, radius_m: float, value: float) -> None:
        if len(pts_m) == 0:
            return
        pp = (pts_m - np.array([self.o.x, self.o.y], np.float32)) * self.px
        r = max(radius_m * self.px, 0.7)
        ri = int(math.ceil(r))
        bx = np.floor(pp[:, 0]).astype(np.int64)
        by = np.floor(pp[:, 1]).astype(np.int64)
        for dy in range(-ri, ri + 1):
            for dx in range(-ri, ri + 1):
                d = math.hypot(dx, dy) / (r + 0.5)
                if d >= 1.0:
                    continue
                xs, ys = bx + dx, by + dy
                ok = (xs >= 0) & (ys >= 0) & (xs < self.w) & (ys < self.h)
                np.maximum.at(arr, (ys[ok], xs[ok]), np.float32((1.0 - d) ** 0.6 * value))

    def save(self, name: str) -> tuple[Path, Path]:
        """В PNG через картинки Blender (в его Python нет PIL): высота 16 бит, маска RGB."""
        GEN.mkdir(parents=True, exist_ok=True)
        h = np.clip((self.raised - self.groove) * 0.5 + 0.5, 0, 1)
        hp, mp = GEN / f"{name}_height.png", GEN / f"{name}_mask.png"
        settings = bpy.context.scene.render.image_settings
        settings.file_format = "PNG"
        settings.color_depth = "16"
        settings.color_mode = "RGB"
        for path, rgb in ((hp, (h, h, h)), (mp, (self.thread, self.grime, np.zeros_like(h)))):
            img = bpy.data.images.new(path.stem, self.w, self.h, alpha=True, float_buffer=True)
            px = np.ones((self.h, self.w, 4), np.float32)
            for c in range(3):
                px[..., c] = np.clip(rgb[c], 0, 1)
            img.pixels.foreach_set(px.ravel())
            img.save_render(str(path))
            bpy.data.images.remove(img)
        return hp, mp


def seam_details(cv: Canvas, pts: list[Vector], inward: list[Vector], rows: list[float], groove: bool) -> None:
    """Вдоль цепочки: углубление шва (с грязью) и строчки на расстояниях rows внутрь."""
    if groove:
        g, _ = resample_polyline(pts, 0.4 / cv.px)
        cv.stamp(cv.groove, g, 0.0012, 0.55)
        cv.stamp(cv.grime, g, 0.0016, 0.8)
    for off in rows:
        q = [p + d * off for p, d in zip(pts, inward)]
        dots, t = resample_polyline(q, 0.35 / cv.px)
        dots = dots[(t % (STITCH + GAP)) < STITCH]
        cv.stamp(cv.raised, dots, 0.00065, 0.75)
        cv.stamp(cv.thread, dots, 0.00055, 1.0)
        cv.stamp(cv.grime, dots, 0.0012, 0.35)


# ---------- точки на теле → развёртка ----------

def uv_at(obj: bpy.types.Object, bvh: BVHTree, p: Vector) -> Vector | None:
    loc, nrm, fi, dist = bvh.find_nearest(p)
    if loc is None:
        return None
    me = obj.data
    poly = me.polygons[fi]
    uv = me.uv_layers["UV_Pattern"].data
    vs = [me.vertices[i].co for i in poly.vertices]
    us = [Vector((*uv[li].uv, 0.0)) for li in poly.loop_indices]
    best = None
    for k in range(1, len(vs) - 1):
        w = mg.barycentric_transform(loc, vs[0], vs[k], vs[k + 1], us[0], us[k], us[k + 1])
        best = Vector((w.x, w.y))
        if mg.intersect_point_tri(loc, vs[0], vs[k], vs[k + 1]) is not None:
            return best
    return best


def path_uv(obj, bvh, pts3d: list[Vector], steps: int = 40) -> list[Vector]:
    out = []
    for i in range(len(pts3d) - 1):
        for t in np.linspace(0, 1, steps, endpoint=False):
            u = uv_at(obj, bvh, pts3d[i].lerp(pts3d[i + 1], float(t)))
            if u is not None:
                out.append(u)
    u = uv_at(obj, bvh, pts3d[-1])
    if u is not None:
        out.append(u)
    return out


def draw_uv_path(cv: Canvas, uvs: list[Vector], depth: float, width: float, thread_rows: list[float]) -> None:
    """Линия кармана/клапана: углубление и строчки по сторонам; скачок между островами — разрыв."""
    parts, cur = [], []
    for u in uvs:
        if cur and (u - cur[-1]).length > 0.02:
            parts.append(cur)
            cur = []
        cur.append(u)
    if cur:
        parts.append(cur)
    for part in parts:
        if len(part) < 2:
            continue
        g, _ = resample_polyline(part, 0.4 / cv.px)
        cv.stamp(cv.groove, g, width, depth)
        cv.stamp(cv.grime, g, width * 1.4, 0.7)
        ins = []
        for i in range(len(part)):
            tv = part[min(i + 1, len(part) - 1)] - part[max(i - 1, 0)]
            ins.append(Vector((-tv.y, tv.x)).normalized() if tv.length > 1e-9 else Vector((0, 0)))
        for off in thread_rows:
            sgn = 1 if off > 0 else -1
            seam_details(cv, part, [n * sgn for n in ins], [abs(off)], False)


def build_canvas(obj: bpy.types.Object) -> Canvas:
    us = np.array([tuple(l.uv) for l in obj.data.uv_layers["UV_Pattern"].data], np.float32)
    return Canvas(Vector(us.min(axis=0)), Vector(us.max(axis=0)), PX_PER_M)


# ---------- материалы ----------

def hook_material(mat: bpy.types.Material, height_img: Path, mask_img: Path, cv: Canvas,
                  thread_color: tuple, strength: float = 0.9) -> None:
    """Рельеф швов поверх уже подключённой нормали; нитка и грязь в шве — поверх цвета."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UV_Pattern"
    uvn.location = (-1500, -1200)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-1300, -1200)
    sx, sy = cv.px / cv.w, cv.px / cv.h
    mp.inputs["Location"].default_value = (-cv.o.x * sx, -cv.o.y * sy, 0)
    mp.inputs["Scale"].default_value = (sx, sy, 1)
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
    imgs = []
    for path, y in ((height_img, -1200), (mask_img, -1500)):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.location = (-1100, y)
        n.image = bpy.data.images.load(str(path), check_existing=True)
        n.image.colorspace_settings.name = "Non-Color"
        n.interpolation = "Cubic"
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
        imgs.append(n)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (300, -900)
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.0012
    nt.links.new(imgs[0].outputs["Color"], bump.inputs["Height"])
    if bsdf.inputs["Normal"].links:
        nt.links.new(bsdf.inputs["Normal"].links[0].from_socket, bump.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-800, -1500)
    nt.links.new(imgs[1].outputs["Color"], sep.inputs["Color"])
    grime = nt.nodes.new("ShaderNodeMix")
    grime.data_type = "RGBA"
    grime.blend_type = "MULTIPLY"
    grime.location = (350, 200)
    nt.links.new(sep.outputs["Green"], grime.inputs[0])
    if bsdf.inputs["Base Color"].links:
        nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, grime.inputs[6])
    else:
        grime.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
    grime.inputs[7].default_value = (0.45, 0.42, 0.40, 1)
    thread = nt.nodes.new("ShaderNodeMix")
    thread.data_type = "RGBA"
    thread.location = (500, 200)
    nt.links.new(sep.outputs["Red"], thread.inputs[0])
    nt.links.new(grime.outputs[2], thread.inputs[6])
    thread.inputs[7].default_value = (*thread_color, 1)
    nt.links.new(thread.outputs[2], bsdf.inputs["Base Color"])


# ---------- вещи ----------

def jacket_details(obj: bpy.types.Object) -> Canvas:
    cv = build_canvas(obj)
    for pts, inward, mat in chains(uv_half_edges(obj)):
        seam_details(cv, pts, inward, [0.004, 0.009] if mat == "Jacket_Leather" else [], True)
    # Дерево — по самой сетке, без модификаторов: у вещи толщина (Solidify), и номера граней
    # вычисленной сетки не совпали бы с развёрткой.
    me = obj.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
    # Прорезные косые карманы спереди: линия кармана и две губки по 6 мм.
    # Прорез — прямой по лекалу (как его режут), поэтому прямая в развёртке между концами, а не
    # проекция 3D-линии на складки (та шла зигзагом).
    for sgn in (1, -1):
        ua = uv_at(obj, bvh, Vector((0.105 * sgn, -0.20, 0.985)))
        ub = uv_at(obj, bvh, Vector((0.150 * sgn, -0.17, 1.125)))
        if ua is None or ub is None or (ub - ua).length > 0.3:
            continue
        d = (ub - ua).normalized()
        n2 = Vector((-d.y, d.x))
        line = [ua.lerp(ub, t / 40) for t in range(41)]
        draw_uv_path(cv, line, 0.6, 0.0012, [0.004, -0.004])
        for off in (0.006, -0.006):
            draw_uv_path(cv, [u + n2 * off for u in line], 0.3, 0.0008, [])
    return cv


def pants_details(obj: bpy.types.Object) -> Canvas:
    cv = build_canvas(obj)
    for pts, inward, mat in chains(uv_half_edges(obj)):
        seam_details(cv, pts, inward, [0.004, 0.010], True)
    # Карманы-карго — объёмными деталями (pockets.py), здесь только швы кроя.
    return cv


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"npc_scav_{kc.VERSION}.blend"))
    for name, fn, mats in (("jacket", jacket_details, [("Jacket_Leather", (0.045, 0.030, 0.020), 1.0),
                                                         ("Jacket_Rib", (0.03, 0.03, 0.03), 0.6)]),
                           ("pants", pants_details, [("Pants_Fabric", (0.16, 0.15, 0.10), 0.9)])):
        obj = bpy.data.objects["Jacket" if name == "jacket" else "Pants"]
        cv = fn(obj)
        hp, mp = cv.save(name)
        for mname, thread, strength in mats:
            hook_material(bpy.data.materials[mname], hp, mp, cv, thread, strength)
        kc.log("DETAILS", name, cv.w, "x", cv.h)
    kc.save(kc.WORK / f"npc_scav_{kc.VERSION}.blend")
    if "render" in args:
        cams = {
            "det_chest": kc.camera("Cam_DetChest", (0.35, -0.75, 1.22), (0.05, -0.08, 1.12), 70),
            "det_back": kc.camera("Cam_DetBack", (0.3, 0.85, 1.30), (0.0, 0.05, 1.25), 70),
            "det_legs": kc.camera("Cam_DetLegs", (0.85, -0.55, 0.62), (0.15, -0.0, 0.55), 70),
            "det_sleeve": kc.camera("Cam_DetSleeve", (0.75, -0.6, 1.25), (0.38, -0.03, 1.22), 70),
        }
        for k, cam in cams.items():
            kc.render(cam, kc.WORK / "previews" / f"scav_{kc.VERSION}_{k}.png", (900, 800), 96)


if __name__ == "__main__":
    main()
