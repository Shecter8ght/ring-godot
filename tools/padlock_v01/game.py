"""Навесной замок Padlock_01: игровая версия (принятая отделка v05).

  blender --background --factory-startup --python-exit-code 1 --python tools/padlock_v01/game.py -- [lp] [bake] [export]

Источник — E:/Models Blender/PROPS/Padlock_01/models/padlock_v05_textured.blend (24 детали high-poly, карты 4K textures/export_v05).
Исходные файлы не меняются; рабочий файл и карты — _asset_src/padlock_v01/game/.

  lp     — низкая сетка. Щёки: лицевая плоскость high-poly (грани, смотрящие наружу), схлопнутая и с упрощённым контуром,
           стенка по контуру до тыльной плоскости щеки; скважина и малое отверстие — колодцы с тёмным дном (дно и нижняя часть
           стенки красятся тёмным после запекания), отверстия под шляпками заклёпок закрыты. Обечайка — только наружная
           стенка. Дужка — круглый пруток заново по оси high-poly (12 граней по окружности, 20 шагов по дуге, шов развёртки —
           с внутренней стороны). Шляпки заклёпок и штифтов, видимый штифт скважины — схлопыванием; стержни и посадки (внутри)
           не нужны. Развёртка: щёки и дужка — свои (плоская проекция лица, стенки лентами, пруток одной лентой), остальное —
           Smart UV; укладка — укладчик проекта tools/asset_kit/uv.py в один атлас 1K.
  bake   — карты атласа с high-poly переносом карт v05 (цвет, шероховатость с лаком, металл, AO — излучением без света),
           нормаль — касательная с геометрией и картой нормалей high-poly (Cycles, процессор); дно колодцев — тёмное.
  export — assets/models/props/padlock_01/padlock_01.gltf (узлы Body, Shackle, Body_lod1, Shackle_lod1), карты WebP, padlock_01.json;
           файл для владельца E:/Models Blender/PROPS/Padlock_01/models/padlock_v05_game.blend (карты — textures/game_v05).

Затем: tools/godot.cmd --headless --import, python -X utf8 tools/padlock_v01/game_imports.py, --import ещё раз.
Общие части конвейера — tools/loot_containers/lc_game_lib.py (как у контейнеров лута).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector as V
from mathutils.bvhtree import BVHTree

sys.path.insert(0, "E:/Games/RING-godot/tools/loot_containers")
import lc_game_lib as G  # noqa: E402

SRC = "E:/Models Blender/PROPS/Padlock_01/models/padlock_v05_textured.blend"
MAPS_SRC = "E:/Models Blender/PROPS/Padlock_01/textures/export_v05"
WORK = G.ROOT + "/_asset_src/padlock_v01/game"
LIBDIR = "E:/Models Blender/PROPS/Padlock_01"
OUTDIR = G.ROOT + "/assets/models/props/padlock_01"
NAME = "Padlock"
SIZE = 1024
MARGIN = int(os.environ.get("PAD_MARGIN", "4"))
CONTOUR_MM = float(os.environ.get("PAD_CONTOUR", "0.08"))  # допуск упрощения внешнего контура щеки (силуэт), мм
CONTOUR_HOLE_MM = 0.2                                       # то же у скважины и малого отверстия
PACK = dict(score="top", order="area", precision=0.001)
PACK.update(json.loads(os.environ.get("PAD_PACK", "{}")))
ANGLE = float(os.environ.get("PAD_ANGLE", "80"))            # Smart UV для мелких деталей
BAND_LOD1_RATIO = 0.4  # обечайка LOD1 — схлопыванием
COAT_GAIN = 0.75     # доля, на которую лак (слой Coat исходника) приближается к своей шероховатости в итоговой карте
FRONT_MIN_NY = 0.6   # грань щеки — лицевая, если её нормаль смотрит наружу по Y сильнее этого (скругление кромки — в стенку)
LOD1_STEP = 4          # LOD1 щеки: каждая четвёртая вершина внешнего контура
STEINER_M = float(os.environ.get("PAD_STEINER", "0.013"))   # шаг внутренних точек лица щеки, м
WELL_DEPTH = 0.004   # глубина тёмного колодца скважины за тыльной плоскостью щеки, м
WALL_CHUNK = 0.04    # лента стенки режется на куски не длиннее, м (иначе не уложится в атлас)
CORNER_DEG = 50.0    # излом контура больше — жёсткое ребро и шов стенки
TUBE_SIDES, TUBE_ARC, TUBE_LEG = 12, 20, 1               # дужка LOD0: грани по окружности, шаги по дуге, шаги по ноге
TUBE1_SIDES, TUBE1_ARC, TUBE1_LEG = 6, 8, 1              # дужка LOD1
DARK_SRGB, DARK_AO, DARK_ROUGH = 0.02, 0.08, 0.85         # дно колодцев: почти чёрное, затенённое, матовое

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
stages = [a for a in argv if a in ("lp", "bake", "export")] or ["lp", "bake", "export"]
os.makedirs(WORK, exist_ok=True)

# треугольники на деталь (подстрока имени → цель); у щёк — цель лицевой плоскости до стенок
TARGETS = [("Body_perimeter", 105), ("Front_cheek", 135), ("Rear_cheek", 140),
           ("front_pressed", 14), ("rear_peened", 14), ("internal_pin", 14), ("Visible_key_guide_post", 24)]
DROP = ("_shaft", "_seat")      # стержни заклёпок и посадки штифтов спрятаны внутри щёк
SHACKLE = "Shackle_forged"
HEADS = ("front_pressed", "rear_peened", "internal_pin")


def target_of(name: str):
    if any(d in name for d in DROP):
        return None
    for k, t in TARGETS:
        if k in name:
            return t
    raise RuntimeError("нет цели для " + name)


def world_co(o) -> np.ndarray:
    return np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])


def _clean_shell(h, keep) -> "bpy.types.Mesh":
    """Копия высокой детали в мировых осях только из граней, которые прошли keep(грань): открытая оболочка без висящих
    рёбер, без развёрток и материалов исходника."""
    bm = bmesh.new()
    bm.from_mesh(h.data)
    bm.transform(h.matrix_world)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f)], context="FACES")
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    me = bpy.data.meshes.new("shell")
    bm.to_mesh(me)
    bm.free()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    me.materials.clear()
    return me


def _decimate_mesh(me, target: int):
    """Схлопывание рёбер открытой оболочки до target треугольников (границы держатся квадриками)."""
    n = G.tris(me)
    if n <= target:
        return me
    tmp = bpy.data.objects.new("tmp", me)
    bpy.context.scene.collection.objects.link(tmp)
    md = tmp.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = max(0.003, target / n)
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return out


def _simplify_contour(bm, outer_mm: float, hole_mm: float) -> None:
    """Вершины границы, лежащие на прямой между соседями, сливаются — стенка не раздувает число треугольников. Допуск —
    outer_mm у внешнего контура (силуэт) и hole_mm у отверстий. Соседние вершины за проход не берутся (ошибка не копится)."""
    loops = _boundary_loops(bm)
    big = max(loops, key=lambda lp: (max(v.co.x for v in lp) - min(v.co.x for v in lp)) * (max(v.co.z for v in lp) - min(v.co.z for v in lp)))
    on_outer = set(big)
    for _ in range(40):
        pick = set()
        for v in bm.verts:
            be = [e for e in v.link_edges if e.is_boundary]
            if len(be) != 2:
                continue
            na, nb = be[0].other_vert(v), be[1].other_vert(v)
            if v in pick or na in pick or nb in pick:
                continue
            ab = nb.co - na.co
            if ab.length < 1e-9:
                continue
            dist = ((v.co - na.co).cross(ab)).length / ab.length
            tol = (outer_mm if v in on_outer else hole_mm) * 0.001
            if dist < tol and 0.0 <= (v.co - na.co).dot(ab) <= ab.length_squared:
                pick.add(v)
        if not pick:
            break
        on_outer -= pick
        bmesh.ops.dissolve_verts(bm, verts=list(pick))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))


def _boundary_loops(bm) -> list:
    """Замкнутые петли граничных рёбер — упорядоченные списки вершин."""
    edges = [e for e in bm.edges if e.is_boundary]
    adj: dict = {}
    for e in edges:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    used: set = set()
    loops = []
    for e0 in edges:
        if e0 in used:
            continue
        used.add(e0)
        start, cur = e0.verts[0], e0.verts[1]
        loop = [start]
        while cur is not start:
            loop.append(cur)
            nxt = next((e for e in adj[cur] if e not in used), None)
            if nxt is None:
                break
            used.add(nxt)
            cur = nxt.other_vert(cur)
        loops.append(loop)
    return loops


def _inside(px: float, pz: float, poly) -> bool:
    res = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i - 1], poly[i]
        if (z1 > pz) != (z2 > pz) and px < x1 + (pz - z1) * (x2 - x1) / (z2 - z1):
            res = not res
    return res


def _seg_dist(px: float, pz: float, poly) -> float:
    best = 1e9
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i - 1], poly[i]
        dx, dz = x2 - x1, z2 - z1
        t = max(0.0, min(1.0, ((px - x1) * dx + (pz - z1) * dz) / max(dx * dx + dz * dz, 1e-18)))
        best = min(best, math.hypot(px - x1 - t * dx, pz - z1 - t * dz))
    return best


def cheek_meshes(h, front: bool, target: int, heads: list) -> tuple:
    """Щека: лицевая плоскость, стенка контура до тыльной плоскости, колодцы отверстий — LOD0 и LOD1 одной разметкой.
    Тыл и внутренности не строятся — у корпуса они закрыты обечайкой. heads — центры шляпок (x, z): отверстия под ними
    закрываются заподлицо. У граней — номер острова развёртки pad_isl и исходная развёртка Param: LOD1 получает свою
    GameUV переносом с LOD0 по островам (у острова после укладки — одно аффинное преобразование)."""
    d = -1.0 if front else 1.0
    ys = [(h.matrix_world @ v.co).y for v in h.data.vertices]
    y_front = min(ys) if front else max(ys)
    y_back = max(ys) if front else min(ys)
    y_floor = y_back - d * WELL_DEPTH
    me = _decimate_mesh(_clean_shell(h, lambda f: f.normal.y * d > FRONT_MIN_NY), target)
    src = bmesh.new()
    src.from_mesh(me)
    _simplify_contour(src, CONTOUR_MM, CONTOUR_HOLE_MM)
    contours = [[(v.co.x, v.co.z) for v in lp] for lp in _boundary_loops(src)]
    src.free()
    bpy.data.meshes.remove(me)

    def area_xz(pts) -> float:
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        return (max(xs) - min(xs)) * (max(zs) - min(zs))
    contours.sort(key=area_xz, reverse=True)          # первый — внешний контур
    holes, n_capped = [], 0
    for pts in contours[1:]:
        cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        if any(math.hypot(cx - hx, cz - hz) < 0.003 for hx, hz in heads):
            n_capped += 1                 # под шляпкой: не отверстие, закрыто лицом заподлицо
        else:
            holes.append(pts)
    polylines = [contours[0]] + holes
    # лицо — заново: плоская триангуляция контура с отверстиями, вершины на гладком куполе, подогнанном по лицу high-poly
    # (схлопнутая оболочка даёт складки и перевёрнутые треугольники — при косом солнце они читаются гранями); рельеф
    # (клеймо, раковины, кромки) — в карте нормалей
    mw, nw = h.matrix_world, h.matrix_world.to_3x3()
    pts3 = np.array([(mw @ p.center)[:] for p in h.data.polygons if (nw @ p.normal).normalized().y * d > FRONT_MIN_NY])
    X = np.c_[np.ones(len(pts3)), pts3[:, 0], pts3[:, 2], pts3[:, 0] ** 2, pts3[:, 0] * pts3[:, 2], pts3[:, 2] ** 2]
    coef, *_ = np.linalg.lstsq(X, pts3[:, 1], rcond=None)
    rms = float(np.sqrt(np.mean((X @ coef - pts3[:, 1]) ** 2)))

    def dome(x: float, z: float) -> float:
        return float(coef @ np.array([1.0, x, z, x * x, x * z, z * z]))

    def dome_n(x: float, z: float) -> tuple:
        fx = coef[1] + 2 * coef[3] * x + coef[4] * z
        fz = coef[2] + coef[4] * x + 2 * coef[5] * z
        return (V((-fx, 1.0, -fz)).normalized() * d)[:]
    # стенки — лентами: длина вдоль контура, куски не длиннее WALL_CHUNK и с разрывом на изломах; номер куска — остров
    walls = []
    isl_next = 10
    for pl in polylines:
        n = len(pl)
        s = [0.0]
        for i in range(n):
            (x1, z1), (x2, z2) = pl[i], pl[(i + 1) % n]
            s.append(s[-1] + math.hypot(x2 - x1, z2 - z1))
        corner = [False] * n
        for i in range(n):
            (ax, az), (bx, bz), (cx, cz) = pl[i - 1], pl[i], pl[(i + 1) % n]
            u1, u2 = V((bx - ax, bz - az)), V((cx - bx, cz - bz))
            if u1.length > 1e-9 and u2.length > 1e-9 and math.degrees(u1.angle(u2)) > CORNER_DEG:
                corner[i] = True
        start = [False] * n
        s0 = [0.0] * n
        chunk = [0] * n
        cs = 0.0
        for i in range(n):
            if i == 0 or corner[i] or s[i] - cs > WALL_CHUNK:
                cs = s[i]
                start[i] = True
                isl_next += 1
            s0[i] = cs
            chunk[i] = isl_next
        walls.append(dict(n=n, s=s, s0=s0, chunk=chunk, start=start, corner=corner))

    def build(lod: int):
        # LOD1: внешний контур — каждая LOD1_STEP-я вершина и все начала кусков ленты; отверстия — целиком (иначе лицо
        # заходит в отверстие, а там в атласе чужие острова); без внутренних точек; колодец без нижней части стенки
        keep_idx = []
        for k in range(len(polylines)):
            w = walls[k]
            if lod == 0 or k > 0:
                keep_idx.append(list(range(w["n"])))
            else:
                keep_idx.append([i for i in range(w["n"]) if i % LOD1_STEP == 0 or w["start"][i] or w["corner"][i]])
        sub = [[polylines[k][i] for i in keep_idx[k]] for k in range(len(polylines))]
        extra = []
        if lod == 0:
            xs = [p[0] for p in sub[0]]
            zs = [p[1] for p in sub[0]]
            gx = min(xs) + STEINER_M / 2
            while gx < max(xs):
                gz = min(zs) + STEINER_M / 2
                while gz < max(zs):
                    extra.append((gx, gz))
                    gz += STEINER_M
                gx += STEINER_M
            for hp in sub[1:]:
                cx, cz = sum(p[0] for p in hp) / len(hp), sum(p[1] for p in hp) / len(hp)
                rad = max(math.hypot(p[0] - cx, p[1] - cz) for p in hp) + 0.003
                extra += [(cx + rad * math.cos(2 * math.pi * k / 8), cz + rad * math.sin(2 * math.pi * k / 8)) for k in range(8)]
        keep = []
        for px, pz in extra:
            if not _inside(px, pz, sub[0]) or any(_inside(px, pz, hp) for hp in sub[1:]):
                continue
            if min(_seg_dist(px, pz, pl) for pl in sub) < 0.0035:
                continue
            if any(math.hypot(px - qx, pz - qz) < 0.004 for qx, qz in keep):
                continue
            keep.append((px, pz))
        from mathutils.geometry import delaunay_2d_cdt
        coords, edges = [], []
        for pl in sub:
            base = len(coords)
            coords += [V((x, z)) for x, z in pl]
            edges += [(base + i, base + (i + 1) % len(pl)) for i in range(len(pl))]
        coords += [V(p) for p in keep]
        out_co, _e, out_f, orig_v, _oe, _of = delaunay_2d_cdt(coords, edges, [], 0, 1e-7, True)
        bm = bmesh.new()
        verts = [bm.verts.new((c.x, dome(c.x, c.y), c.y)) for c in out_co]
        by_orig = {}
        for i, ov in enumerate(orig_v):
            for o in ov:
                by_orig[o] = verts[i]
        loops, base = [], 0
        for pl in sub:
            loops.append([by_orig[base + i] for i in range(len(pl))])
            base += len(pl)
        kind = bm.faces.layers.int.new("pad_kind")      # 0 лицо, 1 стенка (запекается), 2 тёмное (колодец)
        dark = bm.faces.layers.int.new("pad_dark")
        isl = bm.faces.layers.int.new("pad_isl")
        uvl = bm.loops.layers.uv.new("GameUV")
        prm = bm.loops.layers.uv.new("Param")
        front_faces = []
        for tri in out_f:
            c = out_co[tri[0]] + out_co[tri[1]] + out_co[tri[2]]
            cx, cz = c.x / 3, c.y / 3
            if not _inside(cx, cz, sub[0]) or any(_inside(cx, cz, hp) for hp in sub[1:]):
                continue
            try:
                f = bm.faces.new([verts[i] for i in tri])
            except ValueError:
                continue
            f[kind], f[isl] = 0, 1
            front_faces.append(f)
        on_loop = {v for lp in loops for v in lp}
        for v in [v for v in bm.verts if not v.link_faces and v not in on_loop]:
            bm.verts.remove(v)
        sharp = []
        wall_uv = {}
        for k, lp in enumerate(loops):
            w = walls[k]
            idx = keep_idx[k]
            n = len(lp)
            hole = k > 0
            rings = [lp, [bm.verts.new((v.co.x, y_back, v.co.z)) for v in lp]]
            kinds = [1]
            if hole and lod == 0:
                rings.append([bm.verts.new((v.co.x, y_floor, v.co.z)) for v in lp])
                kinds.append(2)
            for r in range(len(rings) - 1):
                ra, rb = rings[r], rings[r + 1]
                for a in range(n):
                    b = (a + 1) % n
                    ia = idx[a]
                    sb = w["s"][idx[b]] if b != 0 else w["s"][w["n"]]       # замыкание петли — полная длина
                    f = bm.faces.new((ra[a], ra[b], rb[b], rb[a]))
                    f[kind] = kinds[r]
                    f[dark] = 1 if kinds[r] == 2 else 0
                    f[isl] = w["chunk"][ia] + (5000 if kinds[r] == 2 else 0)     # тёмная часть ужимается укладчиком отдельно
                    u_a, u_b = w["s"][ia] - w["s0"][ia], sb - w["s0"][ia]
                    wall_uv[f] = {ra[a]: (u_a, abs(ra[a].co.y - y_front)), ra[b]: (u_b, abs(ra[b].co.y - y_front)),
                                  rb[b]: (u_b, abs(rb[b].co.y - y_front)), rb[a]: (u_a, abs(rb[a].co.y - y_front))}
            for a in range(n):
                sharp.append(bm.edges.get((lp[a], lp[(a + 1) % n])))
                if w["corner"][idx[a]] or w["start"][idx[a]]:
                    for r in range(len(rings) - 1):
                        sharp.append(bm.edges.get((rings[r][a], rings[r + 1][a])))
            if hole:
                ring_c = rings[-1]
                fl = bm.faces.new(ring_c)
                fl[kind], fl[dark], fl[isl] = 2, 1, 1000 + k
                for a in range(n):
                    sharp.append(bm.edges.get((ring_c[a], ring_c[(a + 1) % n])))
        bm.normal_update()
        # ориентация: лицо и дно — к смотрящему, стенки — наружу от материала (точка у грани по нормали не под лицом)
        tv, tp = [], []
        for f in front_faces:
            b0 = len(tv)
            tv += [v.co.copy() for v in f.verts]
            tp.append(list(range(b0, b0 + len(f.verts))))
        bvh = BVHTree.FromPolygons(tv, tp)
        for f in bm.faces:
            if f[kind] == 0 or abs(f.normal.y) > 0.5:
                if f.normal.y * d < 0:
                    f.normal_flip()
                continue
            p = f.calc_center_median() + f.normal * 0.0003
            if bvh.ray_cast(V((p.x, y_front + d * 0.01, p.z)), V((0.0, -d, 0.0)), 0.05)[0] is not None:
                f.normal_flip()
        bm.normal_update()
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        # развёртка: лицо и дно — плоская проекция (вид снаружи, не зеркально), стенки — лентами (длина × глубина)
        for f in bm.faces:
            for l in f.loops:
                uv = wall_uv[f][l.vert] if f in wall_uv else (-d * l.vert.co.x, l.vert.co.z)
                l[uvl].uv = uv
                l[prm].uv = uv
            f.smooth = True
        for e in sharp:
            if e is not None:
                e.smooth = False
        out = bpy.data.meshes.new("cheek%d" % lod)
        bm.to_mesh(out)
        bm.free()
        # нормали лица — точно по куполу (иначе длинные треугольники дают полосы в освещении); стенки и дно — обычные
        kinds_a = np.zeros(len(out.polygons), np.int32)
        out.attributes["pad_kind"].data.foreach_get("value", kinds_a)
        cn = []
        for p in out.polygons:
            for li in p.loop_indices:
                if kinds_a[p.index] == 0:
                    c = out.vertices[out.loops[li].vertex_index].co
                    cn.append(dome_n(c.x, c.z))
                else:
                    cn.append((0.0, 0.0, 0.0))
        out.normals_split_custom_set(cn)
        return out
    me0, me1 = build(0), build(1)
    print("ЩЕКА", h.name, "купол: отклонение high-poly %.3f мм (ср. кв.); вершин контура %s; колодцев %d, закрыто под шляпками %d;"
          " LOD0 %d, LOD1 %d" % (rms * 1000, [len(p) for p in polylines], len(holes), n_capped, G.tris(me0), G.tris(me1)), flush=True)
    return me0, me1


def band_mesh(h, cheeks, target: int):
    """Обечайка: только наружная стенка (точка в 2,2 мм наружу по нормали не под щекой — луч вдоль Y не упирается в щёки)."""
    verts, polys = [], []
    for c in cheeks:
        base = len(verts)
        verts += [(c.matrix_world @ v.co).copy() for v in c.data.vertices]
        polys += [[base + i for i in p.vertices] for p in c.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)

    def outer(f) -> bool:
        p = f.calc_center_median() + f.normal * 0.0022
        return bvh.ray_cast(V((p.x, -0.1, p.z)), V((0.0, 1.0, 0.0)), 0.2)[0] is None
    return _decimate_mesh(_clean_shell(h, outer), target)


def shackle_dims(hs) -> dict:
    """Ось прутка дужки по high-poly: ноги вертикальны (x = ±R), дуга — полуокружность радиуса R по оси."""
    co = world_co(hs)
    r = float(co[:, 1].max() - co[:, 1].min()) / 2
    x_out = float(co[:, 0].max() - co[:, 0].min()) / 2
    R = x_out - r
    z_top = float(co[:, 2].max())
    return dict(R=R, r=r, zb=float(co[:, 2].min()), zc=z_top - r - R, y=float((co[:, 1].max() + co[:, 1].min()) / 2))


def tube_mesh(dims: dict, sides: int, n_arc: int, n_leg: int, name: str):
    """Пруток дужки: кольца по оси (левая нога вверх, дуга, правая нога вниз), общие вершины по окружности (без шва в нормалях),
    шов развёртки — с внутренней стороны дужки. Слой TubeParam — (длина по оси, длина по окружности) для переноса развёртки на LOD1.
    Концы ног в корпусе не закрываются: их не видно и при поднятой дужке."""
    R, r, zb, zc, y0 = dims["R"], dims["r"], dims["zb"], dims["zc"], dims["y"]
    path = []
    for i in range(n_leg):
        path.append((V((-R, y0, zb + (zc - zb) * i / n_leg)), V((0, 0, 1))))
    for k in range(n_arc + 1):
        a = math.pi - math.pi * k / n_arc
        path.append((V((R * math.cos(a), y0, zc + R * math.sin(a))), V((math.sin(a), 0, -math.cos(a)))))
    for i in range(1, n_leg + 1):
        path.append((V((R, y0, zc - (zc - zb) * i / n_leg)), V((0, 0, -1))))
    s = [0.0]
    for i in range(1, len(path)):
        s.append(s[-1] + (path[i][0] - path[i - 1][0]).length)
    bm = bmesh.new()
    B = V((0, 1, 0))
    rings = []
    for C, T in path:
        N = B.cross(T).normalized()             # внутрь дужки
        rings.append([bm.verts.new(C + r * (math.cos(2 * math.pi * j / sides) * N + math.sin(2 * math.pi * j / sides) * B))
                      for j in range(sides)])
    uvl = bm.loops.layers.uv.new("GameUV")
    prm = bm.loops.layers.uv.new("TubeParam")
    for i in range(len(rings) - 1):
        for j in range(sides):
            jn = (j + 1) % sides
            f = bm.faces.new((rings[i][j], rings[i][jn], rings[i + 1][jn], rings[i + 1][j]))
            f.smooth = True
            uvs = [(s[i], r * 2 * math.pi * j / sides), (s[i], r * 2 * math.pi * (j + 1) / sides),
                   (s[i + 1], r * 2 * math.pi * (j + 1) / sides), (s[i + 1], r * 2 * math.pi * j / sides)]
            for l, uv in zip(f.loops, uvs):
                l[uvl].uv = uv
                l[prm].uv = uv
    bm.normal_update()
    # нормали наружу: точка грани дальше от оси, чем центр кольца
    bm.faces.ensure_lookup_table()
    f0 = bm.faces[0]
    c0 = path[0][0]
    if (f0.calc_center_median() - c0).dot(f0.normal) < 0:
        for f in bm.faces:
            f.normal_flip()
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def stage_lp() -> None:
    bpy.ops.wm.open_mainfile(filepath=SRC)
    highs = [o for o in bpy.data.collections["PADLOCK | geometry candidate"].objects if o.type == "MESH"]
    coll = bpy.data.collections.new("Игровая_низкая")
    bpy.context.scene.collection.children.link(coll)
    lows = []
    cheeks = [h for h in highs if "cheek" in h.name]
    heads = []
    for h in highs:
        if any(k in h.name for k in HEADS):
            c = world_co(h)
            heads.append((float(c[:, 0].mean()), float(c[:, 2].mean()), float(c[:, 1].mean())))
    hs = next(h for h in highs if SHACKLE in h.name)
    dims = shackle_dims(hs)
    print("ДУЖКА", {k: round(v * 1000, 2) for k, v in dims.items()}, "мм", flush=True)

    def add(me, part, src_name):
        me.name = "низк:" + src_name
        o = bpy.data.objects.new(me.name, me)
        coll.objects.link(o)
        o["part"] = part
        lows.append(o)
        print("ДЕТАЛЬ", src_name, "→", G.tris(me), flush=True)
        return o
    for h in highs:
        if SHACKLE in h.name:
            add(tube_mesh(dims, TUBE_SIDES, TUBE_ARC, TUBE_LEG, "tube"), "shackle", h.name)
            continue
        t = target_of(h.name)
        if t is None:
            continue
        if "cheek" in h.name:
            fr = "Front" in h.name
            me, me1 = cheek_meshes(h, fr, t, [(x, z) for x, z, y in heads if (y < 0) == fr])     # шляпки своей стороны
            me1.name = "низк1:" + h.name
            o1 = bpy.data.objects.new(me1.name, me1)
            coll.objects.link(o1)
            o1.hide_render = True
        elif "perimeter" in h.name:
            me = band_mesh(h, cheeks, t)
        else:
            me = G.low_mesh(h, t, solidify=False)
            me.transform(h.matrix_world)      # сетка высокой детали — в осях объекта; ставим в мир
        add(me, "body", h.name)
    # ось поворота дужки: ноги в модели равной длины — ось условно по левой ноге
    bodyz = max(max(v.co[2] for v in o.data.vertices) for o in lows if "cheek" in o.name)   # сетки уже в мировых осях
    info = dict(long_leg="left", legs_equal=True, pivot=[-dims["R"], dims["y"], bodyz], short_zmin=dims["zb"], body_top=float(bodyz),
                dims=dims)
    bpy.context.scene["pad_info"] = json.dumps(info)
    kit = G.kit
    own = [o for o in lows if "cheek" in o.name or o["part"] == "shackle"]       # своя развёртка
    rest = [o for o in lows if o not in own]
    kit.smart_unwrap(rest, uv="GameUV", angle=math.radians(ANGLE))
    for o in own:
        o.data.uv_layers.active = o.data.uv_layers["GameUV"]
    # классы видимости лучами в двух позах (дужка закрыта и поднята на ход): скрытое ужимается; пруток — весь видимый (одна лента)
    lift = Matrix.Translation((0, 0, info["body_top"] - info["short_zmin"]))
    cls = kit.visibility(lows, poses={"closed": {}, "lifted": {"shackle": lift}}, node_of=lambda o: o["part"])
    for i, o in enumerate(lows):
        if o["part"] == "shackle":
            cls[i][:] = kit.VISIBLE
        elif "cheek" in o.name:
            # у щёк острова заданы построением (лицо, куски стенок, дно колодцев): класс — по одному на остров, тёмное ужато
            dk = np.zeros(len(o.data.polygons), np.int32)
            o.data.attributes["pad_dark"].data.foreach_get("value", dk)
            cls[i][:] = np.where(dk > 0, kit.HIDDEN, kit.VISIBLE)
    rep = kit.layout(lows, SIZE, uv="GameUV", classes=cls, stack=False, margin=MARGIN, group_margin=max(2, MARGIN - 2),
                     **PACK, log=lambda *a: print("UVKIT", *a, flush=True))
    lo, hi = G.stretch_report(lows, "GameUV")
    print("РАЗВЁРТКА: заполнение %.1f %%, плотность %.3f пикс/мм, островов %d, искажение площади 5–95 %%: %.2f…%.2f" % (
        rep["fill"] * 100, rep["px_mm"], rep["islands"], lo, hi), flush=True)
    bpy.context.scene["pad_uv"] = json.dumps({"fill": rep["fill"], "px_mm": rep["px_mm"], "islands": rep["islands"]})
    G.finish_shading(rest)            # у щёк и прутка жёсткие рёбра заданы при построении
    for o in lows:
        o.data.uv_layers.active = o.data.uv_layers["GameUV"]
        o.data.uv_layers["GameUV"].active_render = True
    print("ИТОГО LOD0", sum(G.tris(o.data) for o in lows), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=WORK + "/work.blend", compress=True)


def hi_material(kind: str):
    m = bpy.data.materials.new("hi_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    def tex(fn, srgb):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(f"{MAPS_SRC}/Padlock_{fn}.png", check_existing=True)
        t.image.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
        t.interpolation = "Linear"
        return t

    if kind == "normal":
        bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex("normal", False).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
        nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
        return m
    em = nt.nodes.new("ShaderNodeEmission")
    if kind == "color":
        nt.links.new(tex("baseColor", True).outputs["Color"], em.inputs["Color"])
    else:
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex("occlusionRoughnessMetallic", False).outputs["Color"], sep.inputs["Color"])
        if kind == "rough":
            # итоговая шероховатость с лаком: лак, более гладкий, чем основа, тянет её к своей шероховатости пропорционально весу
            sc = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(tex("coat", False).outputs["Color"], sc.inputs["Color"])
            sub = nt.nodes.new("ShaderNodeMath")
            sub.operation = "SUBTRACT"
            nt.links.new(sep.outputs["Green"], sub.inputs[0])
            nt.links.new(sc.outputs["Green"], sub.inputs[1])
            mx = nt.nodes.new("ShaderNodeMath")
            mx.operation = "MAXIMUM"
            nt.links.new(sub.outputs[0], mx.inputs[0])
            mx.inputs[1].default_value = 0.0
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            nt.links.new(mx.outputs[0], mul.inputs[0])
            nt.links.new(sc.outputs["Red"], mul.inputs[1])
            mul2 = nt.nodes.new("ShaderNodeMath")
            mul2.operation = "MULTIPLY"
            nt.links.new(mul.outputs[0], mul2.inputs[0])
            mul2.inputs[1].default_value = COAT_GAIN
            res = nt.nodes.new("ShaderNodeMath")
            res.operation = "SUBTRACT"
            nt.links.new(sep.outputs["Green"], res.inputs[0])
            nt.links.new(mul2.outputs[0], res.inputs[1])
            nt.links.new(res.outputs[0], em.inputs["Color"])
        else:
            nt.links.new(sep.outputs[{"ao": "Red", "metal": "Blue"}[kind]], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def _copy(o):
    c = o.copy()
    c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.hide_render = c.hide_viewport = False
    c.parent = None
    c.matrix_world = o.matrix_world
    return c


def dark_mask(objs, size: int, grow: int = 2) -> np.ndarray:
    """Пиксели атласа под тёмными гранями (атрибут pad_dark), строки снизу вверх, как у пикселей Blender; с запасом grow."""
    mask = np.zeros((size, size), bool)
    for o in objs:
        me = o.data
        at = me.attributes.get("pad_dark")
        if at is None:
            continue
        dk = np.zeros(len(me.polygons), np.int32)
        at.data.foreach_get("value", dk)
        uvd = me.uv_layers["GameUV"].data
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            if not dk[lt.polygon_index]:
                continue
            p = np.array([uvd[li].uv[:] for li in lt.loops]) * size
            x0, y0 = np.floor(p.min(0)).astype(int)
            x1, y1 = np.ceil(p.max(0)).astype(int)
            xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, size)), np.arange(max(y0, 0), min(y1 + 1, size)))
            cx, cy = xs + 0.5, ys + 0.5
            (ax, ay), (bx, by), (qx, qy) = p
            den = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
            if abs(den) < 1e-12:
                continue
            w1 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / den
            w2 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / den
            inside = (w1 >= -0.02) & (w2 >= -0.02) & (1 - w1 - w2 >= -0.02)
            mask[ys[inside], xs[inside]] = True
    for _ in range(grow):
        g = mask.copy()
        g[1:] |= mask[:-1]
        g[:-1] |= mask[1:]
        g[:, 1:] |= mask[:, :-1]
        g[:, :-1] |= mask[:, 1:]
        mask = g
    return mask


def stage_bake() -> None:
    bpy.ops.wm.open_mainfile(filepath=WORK + "/work.blend")
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    highs = [o for o in bpy.data.collections["PADLOCK | geometry candidate"].objects if o.type == "MESH"]
    lows = [o for o in bpy.data.objects if o.name.startswith("низк:")]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in highs and o not in lows:
            o.hide_render = True
            o.hide_viewport = True
    for o in highs + lows:
        o.hide_render = False
        o.hide_viewport = False
    for lo in lows:
        lo.data.uv_layers["GameUV"].active_render = True
    mask = dark_mask(lows, SIZE)
    print("ТЁМНОЕ: пикселей", int(mask.sum()), flush=True)
    # одна высокая и одна низкая сетка на всё запекание: лучи строят дерево один раз, а не по разу на деталь (так в 10 раз быстрее)
    hi_all = G.join([_copy(h) for h in highs], "hi_all")
    for h in highs:
        h.hide_render = h.hide_viewport = True
    lo_all = G.join([_copy(o) for o in lows], "lo_all")
    for o in lows:
        o.hide_render = o.hide_viewport = True
    highs_b, lows_b = [hi_all], [lo_all]
    G.bake_target_material(lows_b)
    kinds = ["color", "rough", "metal", "ao", "normal"]
    mats = {k: hi_material(k) for k in kinds}
    orig = {h: [m for m in h.data.materials] for h in highs_b}

    def prep(kind):
        def f():
            for h in highs_b:
                h.data.materials.clear()
                h.data.materials.append(mats[kind])
        return f

    def restore():
        for h in highs_b:
            h.data.materials.clear()
            for m in orig[h]:
                h.data.materials.append(m)

    def run(kind, btype, samples, srgb, extra=None):
        return G.bake_image(kind, btype, SIZE, highs_b, lows_b, samples, prep(kind), restore, srgb=srgb, extra=extra,
                            extrusion=0.0012, max_dist=0.0025, margin=4)
    color = run("color", "EMIT", 16, True)
    rough = run("rough", "EMIT", 16, False)
    metal = run("metal", "EMIT", 16, False)
    ao = run("ao", "EMIT", 16, False)
    normal = run("normal", "NORMAL", 32, False, {"normal_space": "TANGENT"})
    # промахи лучей (концы ног дужки в корпусе — у high-poly они скруглены) дают нормаль «назад»: ровная
    bad = normal[..., 2] < 0.35
    normal[bad] = (0.5, 0.5, 1.0)
    print("НОРМАЛЬ: исправлено пикселей", int(bad.sum()), flush=True)
    # дно и глубина колодцев: тень внутри корпуса (лучи сюда с high-poly не доходят)
    color[mask] = DARK_SRGB
    ao[mask] = DARK_AO
    rough[mask] = DARK_ROUGH
    metal[mask] = 0.0
    normal[mask] = (0.5, 0.5, 1.0)
    G.write_maps(WORK + "/maps", NAME, SIZE, color, rough, metal, normal, ao)
    bpy.data.objects.remove(lo_all)
    bpy.data.objects.remove(hi_all)
    bpy.ops.wm.save_as_mainfile(filepath=WORK + "/work_baked.blend", compress=True)


def save_game_blend(root) -> None:
    """Файл игровой версии для владельца: только игровые узлы (корень, Body, Shackle, LOD1), карты рядом, пути относительные."""
    import shutil
    keep = {root} | set(root.children_recursive)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for o in root.children_recursive:
        if o.name.endswith("_lod1"):
            o.hide_viewport = True
            o.hide_render = True
    ldir = LIBDIR + "/textures/game_v05"
    os.makedirs(ldir, exist_ok=True)
    for f in os.listdir(WORK + "/maps"):
        shutil.copy(WORK + "/maps/" + f, ldir + "/" + f)
    for im in bpy.data.images:
        if im.filepath and "Padlock_" in os.path.basename(im.filepath):
            im.filepath = ldir + "/" + os.path.basename(im.filepath)
    for im in list(bpy.data.images):
        if "Padlock_" not in im.name:          # образцы исходника, кадры рендера — не нужны
            bpy.data.images.remove(im)
    for dg in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for b in list(dg):
            if b.users == 0:
                dg.remove(b)
    path = LIBDIR + "/models/padlock_v05_game.blend"
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(filepath=path, compress=True)
    if os.path.exists(path + "1"):
        os.remove(path + "1")               # резервная копия Blender рядом не нужна
    print("GAME BLEND", path, flush=True)


def tube_lod1(lod0, dims: dict, pivot: V):
    """LOD1 прутка тем же построителем; развёртка — та же лента атласа: перенос (длина, окружность) → GameUV, найденный по LOD0."""
    def loops_uv(me, name):
        a = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[name].data.foreach_get("uv", a)
        return a.reshape(-1, 2).astype(np.float64)
    p0, q0 = loops_uv(lod0.data, "TubeParam"), loops_uv(lod0.data, "GameUV")
    A = np.c_[p0, np.ones(len(p0))]
    M, *_ = np.linalg.lstsq(A, q0, rcond=None)
    err = float(np.abs(A @ M - q0).max())
    me = tube_mesh(dims, TUBE1_SIDES, TUBE1_ARC, TUBE1_LEG, "Shackle_lod1")
    p1 = loops_uv(me, "TubeParam")
    q1 = np.c_[p1, np.ones(len(p1))] @ M
    me.uv_layers["GameUV"].data.foreach_set("uv", q1.astype(np.float32).ravel())
    me.uv_layers.remove(me.uv_layers["TubeParam"])
    me.transform(Matrix.Translation(-pivot))
    print("ДУЖКА LOD1: перенос развёртки, наибольшая ошибка %.2e UV" % err, flush=True)
    return me, err


def uv_by_islands(me0, me1) -> float:
    """GameUV LOD1 щеки по LOD0: у каждого острова (pad_isl) — аффинное Param → GameUV, найденное по LOD0. Возврат —
    наибольшая ошибка подгонки (в долях атласа): у острова, разрезанного укладчиком, она была бы заметной."""
    def per_loop(me):
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers["GameUV"].data.foreach_get("uv", uv)
        pr = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers["Param"].data.foreach_get("uv", pr)
        isl = np.zeros(len(me.polygons), np.int32)
        me.attributes["pad_isl"].data.foreach_get("value", isl)
        lp_isl = np.zeros(len(me.loops), np.int32)
        for p in me.polygons:
            lp_isl[p.loop_start:p.loop_start + p.loop_total] = isl[p.index]
        return uv.reshape(-1, 2).astype(np.float64), pr.reshape(-1, 2).astype(np.float64), lp_isl
    q0, p0, i0 = per_loop(me0)
    q1, p1, i1 = per_loop(me1)
    worst = 0.0
    for k in np.unique(i1):
        m0 = i0 == k
        A = np.c_[p0[m0], np.ones(int(m0.sum()))]
        M, *_ = np.linalg.lstsq(A, q0[m0], rcond=None)
        worst = max(worst, float(np.abs(A @ M - q0[m0]).max()))
        m1 = i1 == k
        q1[m1] = np.c_[p1[m1], np.ones(int(m1.sum()))] @ M
    me1.uv_layers["GameUV"].data.foreach_set("uv", q1.astype(np.float32).ravel())
    return worst


def stage_export() -> None:
    bpy.ops.wm.open_mainfile(filepath=WORK + "/work_baked.blend")
    sc = bpy.context.scene
    info = json.loads(sc["pad_info"])
    uvrep = json.loads(sc["pad_uv"])
    G.OUT = OUTDIR
    G.TEX = OUTDIR + "/textures"
    os.makedirs(G.TEX, exist_ok=True)
    mat = G.game_material(NAME, WORK + "/maps")
    lows = [o for o in bpy.data.objects if o.name.startswith("низк:")]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in lows:
            o.hide_render = True
            o.hide_viewport = True

    def dup(o):
        c = o.copy()
        c.data = o.data.copy()
        c.data.materials.clear()
        c.data.materials.append(mat)
        c.hide_viewport = False
        c.hide_render = False
        sc.collection.objects.link(c)
        c.hide_set(False)
        return c

    root = bpy.data.objects.new("padlock_01", None)
    sc.collection.objects.link(root)
    body = G.join([dup(o) for o in lows if o["part"] == "body"], "Body")
    shackle = dup(next(o for o in lows if o["part"] == "shackle"))
    shackle.name = "Shackle"
    shackle.data.name = "Shackle"
    pivot = V(info["pivot"])
    shackle.data.transform(Matrix.Translation(-pivot))
    for ob, loc in ((body, V((0, 0, 0))), (shackle, pivot)):
        ob.parent = root
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = loc
    # LOD1: щёки — своей сеткой из lp (развёртка — переносом с LOD0 по островам), обечайка — схлопыванием, шляпки
    # заклёпок и штифт не нужны (на лице они в карте); пруток — заново по оси с той же лентой атласа
    parts1, isl_err = [], 0.0
    for o in lows:
        if "cheek" in o.name:
            o1 = bpy.data.objects["низк1:" + o.name[len("низк:"):]]
            c = dup(o1)
            isl_err = max(isl_err, uv_by_islands(o.data, c.data))
            parts1.append(c)
        elif "perimeter" in o.name:
            parts1.append(G.decimate_copy(dup(o), BAND_LOD1_RATIO, "band_lod1"))
    for c in parts1:
        c.data.materials.clear()
        c.data.materials.append(mat)
    lb = G.join(parts1, "Body_lod1")
    me1, uv_err = tube_lod1(shackle, info["dims"], pivot)
    ls = bpy.data.objects.new("Shackle_lod1", me1)
    sc.collection.objects.link(ls)
    me1.materials.append(mat)
    for lo, src in ((lb, body), (ls, shackle)):
        lo.parent = root
        lo.matrix_parent_inverse = Matrix.Identity(4)
        lo.matrix_basis = src.matrix_basis.copy()
    shackle.data.uv_layers.remove(shackle.data.uv_layers["TubeParam"])
    for ob in (body, shackle, lb, ls):
        for name in [a.name for a in ob.data.attributes if a.name in ("pad_kind", "pad_dark", "pad_isl", "uv_stack", "uv_group")]:
            ob.data.attributes.remove(ob.data.attributes[name])
        if "Param" in ob.data.uv_layers:
            ob.data.uv_layers.remove(ob.data.uv_layers["Param"])
    nodes = {o.name: G.tris(o.data) for o in (body, shackle, lb, ls)}
    t0, t1 = nodes["Body"] + nodes["Shackle"], nodes["Body_lod1"] + nodes["Shackle_lod1"]
    bpy.context.view_layer.update()
    G.export_gltf(root, "padlock_01")
    aabb = G.aabb_of([body, shackle])
    lift = round(info["body_top"] - info["short_zmin"], 4)
    data = {
        "file": "res://assets/models/props/padlock_01/padlock_01.gltf",
        "source": "E:/Models Blender/PROPS/Padlock_01/models/padlock_v05_textured.blend (отделка v05)",
        "triangles": t0, "triangles_lod1": t1, "nodes_triangles": nodes,
        "aabb": aabb,
        "nodes": ["Body", "Shackle", "Body_lod1", "Shackle_lod1"],
        "material": "Padlock",
        "atlas": {"size": SIZE, "maps": ["baseColor", "normal", "occlusionRoughnessMetallic"], "uv_fill": uvrep["fill"],
                  "px_per_mm": uvrep["px_mm"]},
        "axes": "Godot: Y вверх, лицо со скважиной к +Z, ширина по X; начало у основания корпуса; метры, масштаб 1",
        "shackle": {
            "node": "Shackle", "pivot_leg": info["long_leg"], "legs_equal": info["legs_equal"], "pivot": G.gd(pivot),
            "axis": [0.0, 1.0, 0.0], "closed_angle_deg": 0.0, "swing_open_deg": 180.0, "lift_max_m": lift,
            "note": "начало узла — на оси левой ноги в плоскости верха корпуса (узел Shackle_lod1 — так же); открыть: поднять по +Y "
                    "на lift_max_m (нога выходит из гнезда), затем повернуть вокруг оси Y; у модели обе ноги одной длины "
                    "(до z 59,8 мм от основания) — какая нога остаётся в корпусе, решается в игре; механизм не воспроизведён",
        },
    }
    with open(OUTDIR + "/padlock_01.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("MODEL LOD0", t0, "LOD1", t1, nodes, aabb, "перенос развёртки LOD1: пруток %.1e, щёки %.1e" % (uv_err, isl_err), flush=True)
    save_game_blend(root)


for st in stages:
    {"lp": stage_lp, "bake": stage_bake, "export": stage_export}[st]()
