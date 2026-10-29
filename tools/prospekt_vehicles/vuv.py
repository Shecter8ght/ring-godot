"""Транспорт «Проспекта»: игровая развёртка набора текстур (вызывает game_kit.py внутри Blender).

Нормы — навык godot-asset-preparation (mesh-bake): швы по жёстким рёбрам, плотность по видимости, заполнение атласа от
80 %, отступ 12 пикс на 4K (0,003 атласа). Прежняя «умная проекция» давала на кузове 24–42 %: сотни тонких островов
(завёрнутые кромки панелей, изнанки, уплотнители) с отступом у каждого. Здесь:
1. Открытая оболочка (панель с кромкой и изнанкой) разворачивается одним островом без швов; замкнутое тело (бруски,
   трубки, кожухи) — со швами по рёбрам круче 60°. Развёртка по углам (ANGLE_BASED), выравнивание плотности.
2. Треугольники, растянутые больше чем в STRETCH раз против своего острова (загибы кромок — «лучи»), вырезаются;
   острова длиннее MAX_LEN режутся поперёк (крыша и борта автобуса иначе задают масштаб всему атласу); острова с пустотами (кольцо боковины вокруг дверных проёмов: площадь меньше HULL от выпуклой оболочки) режутся
   поперёк длинной оси через CUT м. Развёртка заново.
3. Плотность по видимости (только у кузова): мелкие тёмные детали (резина, молдинги, сетки) — мельче по LOWMAT, грани,
   которые снаружи не видно (луч по нормали упирается в машину), — × 0,45.
4. Крошки (вырезанные треугольники, мельче TINY общей площади) складываются внахлёст — одна клетка на материал: они
   невидимы, а отступ у каждой съедал бы атлас.
5. Упаковка — uvpack.py (растр, точная форма крупных островов, четыре поворота) в системном Python.
6. Детали с печатью (UNIQUE: плафон такси, партия 2) — проекцией по граням с плотностью набора: скруглённая замкнутая
   коробка без рёбер круче 60° иначе разворачивалась одним островом, почти вся уходила в «крошки» внахлёст — рисунок
   и запечённая затенённость на них ложились мешаниной (плафон вышел тёмным).
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, geometry
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
STRETCH = 3.0          # растяжение треугольника против медианы острова — вырезать
HULL = 0.65            # площадь острова / площадь выпуклой оболочки ниже — резать поперёк
CUT = 0.6              # м — шаг разреза таких островов
HULL_POLAR = 0.85      # у колеса режутся и кольца (у кольца площадь — около 0,75 оболочки)
SECTOR = 45.0          # град — сектор разреза колец колеса
MAX_LEN = 3.5          # м — остров длиннее режется поперёк: крыша и борта автобуса (12 м) иначе задают масштаб атласу
TINY = 2e-5            # доля общей площади — крошка, внахлёст
UNIQUE = ("sign_plastic",)   # материалы с печатью по детали — острова свои, без крошек
MARGIN = 0.003         # отступ между островами, доля атласа (12 пикс на 4K)
UV_FILL_MIN = 0.80     # норма заполнения (навык godot-asset-preparation)
LOWMAT = {"rubber": 0.30, "trim_black": 0.45, "mesh_black": 0.35, "chrome": 0.5, "lamp_inner": 0.5,
          "lamp_red_inner": 0.5, "steel_dark": 0.5, "liner": 0.5, "lamp_amber": 0.6}
HIDDEN_K = 0.45        # грани, невидимые снаружи


def _select(objs) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]


def _unwrap(objs) -> None:
    _select(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")


def _islands(bm) -> list:
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        if len(e.link_faces) == 2 and not e.seam:
            parent[find(e.link_faces[0].index)] = find(e.link_faces[1].index)
    out: dict = {}
    for f in bm.faces:
        out.setdefault(find(f.index), []).append(f)
    return list(out.values())


def _uva(f, uv) -> float:
    p = [lp[uv].uv for lp in f.loops]
    return abs(sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y for i in range(len(p)))) / 2


def _seams_by_shell(o) -> None:
    """Открытые оболочки — без швов, замкнутые тела — по рёбрам круче 60°."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    comp: dict = {}
    cid = 0
    for f in bm.faces:
        if f.index in comp:
            continue
        stack = [f]
        comp[f.index] = cid
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in comp:
                        comp[h.index] = cid
                        stack.append(h)
        cid += 1
    open_c = {comp[e.link_faces[0].index] for e in bm.edges if len(e.link_faces) == 1}
    for e in bm.edges:
        lf = e.link_faces
        e.seam = len(lf) == 2 and comp[lf[0].index] not in open_c and e.calc_face_angle(0.0) > math.radians(60.0)
    bm.to_mesh(o.data)
    bm.free()


def _cut_bad(o, polar: bool = False) -> tuple[int, int]:
    """Растянутые треугольники — швы вокруг; острова с пустотами — разрез поперёк длинной оси, а у колеса (polar) —
    по углу вокруг оси X секторами SECTOR: кольца боковин и «звёзды» колпаков — дугами."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uv = bm.loops.layers.uv.active
    nf = ni = 0
    for faces in _islands(bm):
        rs = [math.sqrt(_uva(f, uv) / f.calc_area()) if f.calc_area() > 1e-10 else 0.0 for f in faces]
        med = statistics.median(rs) if rs else 0.0
        if med <= 0.0:
            continue
        for f, r in zip(faces, rs):
            if r > med * STRETCH or r < med / STRETCH:
                for e in f.edges:
                    e.seam = True
                nf += 1
        cs = [o.matrix_world @ f.calc_center_median() for f in faces]
        lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
        hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
        ax = max(range(3), key=lambda k: hi[k] - lo[k])
        if not polar and hi[ax] - lo[ax] > MAX_LEN:
            # плиты не длиннее MAX_LEN; остров с пустотами ниже ещё и режется мельче (CUT) — одно другому не мешает
            n_cut = math.ceil((hi[ax] - lo[ax]) / MAX_LEN)
            step = (hi[ax] - lo[ax]) / n_cut + 1e-6
            key = {f.index: math.floor((c[ax] - lo[ax]) / step) for f, c in zip(faces, cs)}
            for f in faces:
                for e in f.edges:
                    lf = e.link_faces
                    if len(lf) == 2 and lf[0].index in key and lf[1].index in key and key[lf[0].index] != key[lf[1].index]:
                        e.seam = True
            ni += 1
        pts = [lp[uv].uv.copy() for f in faces for lp in f.loops]
        area = sum(_uva(f, uv) for f in faces)
        if len(pts) < 4 or area <= 0.0:
            continue
        hull = geometry.convex_hull_2d(pts)
        ha = abs(sum(pts[hull[i]].x * pts[hull[(i + 1) % len(hull)]].y - pts[hull[(i + 1) % len(hull)]].x * pts[hull[i]].y
                     for i in range(len(hull)))) / 2
        if ha <= 0.0 or area / ha >= (HULL_POLAR if polar else HULL):
            continue
        if polar:
            key = {f.index: math.floor((math.atan2(f.calc_center_median().z, f.calc_center_median().y) + math.pi)
                                       / math.radians(SECTOR)) for f in faces}
            for f in faces:
                for e in f.edges:
                    lf = e.link_faces
                    if len(lf) == 2 and lf[0].index in key and lf[1].index in key and key[lf[0].index] != key[lf[1].index]:
                        e.seam = True
            ni += 1
            continue
        key = {f.index: math.floor((c[ax] - lo[ax]) / CUT) for f, c in zip(faces, cs)}
        for f in faces:
            for e in f.edges:
                lf = e.link_faces
                if len(lf) == 2 and lf[0].index in key and lf[1].index in key and key[lf[0].index] != key[lf[1].index]:
                    e.seam = True
        ni += 1
    bm.to_mesh(o.data)
    bm.free()
    return nf, ni


def _visibility_density(objs, family_objs) -> None:
    """Плотность по видимости у кузова: мелкие тёмные детали и невидимое снаружи — мельче."""
    verts, polys = [], []
    for o in family_objs:
        if o.type != "MESH" or o.get("group") == "wheel":
            continue
        b = len(verts)
        verts += [o.matrix_world @ v.co for v in o.data.vertices]
        polys += [[b + i for i in p.vertices] for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uv = bm.loops.layers.uv.active
        km = LOWMAT.get(o["mat"], 1.0)
        rot = o.matrix_world.to_3x3()
        for faces in _islands(bm):
            vis = tot = 0.0
            for f in faces:
                c = o.matrix_world @ f.calc_center_median()
                n = (rot @ f.normal).normalized()
                a = f.calc_area()
                tot += a
                if bvh.ray_cast(c + n * 0.004, n, 4.0)[0] is None:
                    vis += a
            k = km if not (tot > 0.0 and vis / tot < 0.3) else min(km, HIDDEN_K)
            if k >= 0.999:
                continue
            ctr = Vector((0.0, 0.0))
            cnt = 0
            for f in faces:
                for lp in f.loops:
                    ctr += lp[uv].uv
                    cnt += 1
            ctr /= max(cnt, 1)
            for f in faces:
                for lp in f.loops:
                    lp[uv].uv = ctr + (lp[uv].uv - ctr) * k
        bm.to_mesh(o.data)
        bm.free()


def _pack(objs, grid: int, work: Path, tag: str) -> float:
    """Острова → uvpack.py (крошки — внахлёст по материалу) → обратно. Возвращает заполнение атласа."""
    raw = []
    for oi, o in enumerate(objs):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uv = bm.loops.layers.uv.active
        for faces in _islands(bm):
            tris = [[[lp[uv].uv.x, lp[uv].uv.y] for lp in f.loops] for f in faces]
            raw.append((oi, [f.index for f in faces], tris, sum(_uva(f, uv) for f in faces), o["mat"]))
        bm.free()
    total = sum(r[3] for r in raw)
    side = math.sqrt(total * TINY)
    islands, refs, tiny = [], [], {}
    moves: dict = {}
    for oi, fl, tris, a, mat in raw:
        if a >= total * TINY:
            islands.append({"tris": tris})
            refs.append([(oi, fl)])
            continue
        us = [p[0] for t in tris for p in t]
        vs = [p[1] for t in tris for p in t]
        k = side / max(max(us) - min(us), max(vs) - min(vs), 1e-9)
        g = tiny.setdefault(mat, {"tris": [], "refs": []})
        g["tris"] += [[[(p[0] - min(us)) * k, (p[1] - min(vs)) * k] for p in t] for t in tris]
        g["refs"].append((oi, fl))
        moves.setdefault(oi, []).append((fl, min(us), min(vs), k))
    for g in tiny.values():
        islands.append({"tris": g["tris"]})
        refs.append(g["refs"])
    for oi, items in moves.items():               # крошки — в общую клетку своего материала (до упаковки)
        bm = bmesh.new()
        bm.from_mesh(objs[oi].data)
        uv = bm.loops.layers.uv.active
        bm.faces.ensure_lookup_table()
        for fl, u0, v0, k in items:
            for fi in fl:
                for lp in bm.faces[fi].loops:
                    lp[uv].uv = ((lp[uv].uv.x - u0) * k, (lp[uv].uv.y - v0) * k)
        bm.to_mesh(objs[oi].data)
        bm.free()
    work.mkdir(parents=True, exist_ok=True)
    src, dst = work / f"{tag}.islands.json", work / f"{tag}.pack.json"
    src.write_text(json.dumps({"islands": islands}), encoding="utf-8")
    r = subprocess.run(["python", "-X", "utf8", str(HERE / "uvpack.py"), str(src), str(dst), str(grid), str(MARGIN)],
                       capture_output=True, text=True, encoding="utf-8")
    print(" ", tag, r.stdout.strip(), r.stderr.strip()[-400:])
    res = json.loads(dst.read_text(encoding="utf-8"))
    s = res["scale"]
    by_obj: dict = {}
    for rr, (k, x, y) in zip(refs, res["place"]):
        for oi, fl in rr:
            by_obj.setdefault(oi, []).append((fl, k, x, y))
    for oi, items in by_obj.items():
        bm = bmesh.new()
        bm.from_mesh(objs[oi].data)
        uv = bm.loops.layers.uv.active
        bm.faces.ensure_lookup_table()
        for fl, k, x, y in items:
            for fi in fl:
                for lp in bm.faces[fi].loops:
                    u, v = lp[uv].uv
                    for _ in range(k % 4):
                        u, v = -v, u
                    lp[uv].uv = (u * s + x, v * s + y)
        bm.to_mesh(objs[oi].data)
        bm.free()
    return float(res["fill"])


def _unique(objs) -> None:
    """Детали с печатью — проекцией по граням (острова по направлению граней), масштаб — по плотности остального набора."""
    uniq = [o for o in objs if o["mat"] in UNIQUE]
    rest = [o for o in objs if o["mat"] not in UNIQUE]
    if not uniq or not rest:
        return

    def density(group) -> float:
        uv_a = a3 = 0.0
        for o in group:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            uv = bm.loops.layers.uv.active
            for f in bm.faces:
                uv_a += _uva(f, uv)
                a3 += f.calc_area()
            bm.free()
        return uv_a / max(a3, 1e-9)
    d_rest = density(rest)
    _select(uniq)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50.0), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    k = math.sqrt(d_rest / max(density(uniq), 1e-12))
    for o in uniq:
        for d in o.data.uv_layers.active.data:
            d.uv = d.uv * k


def unwrap_set(ts: str, objs, family_objs, res_px: int, work: Path, tag: str) -> dict:
    """Развёртка набора ts (объекты objs одной семьи) под карту res_px; family_objs — вся семья (лучи видимости)."""
    for o in objs:
        _seams_by_shell(o)
    _unwrap(objs)
    nf = ni = 0
    for o in objs:
        a, b = _cut_bad(o, polar=(ts == "Wheel"))
        nf += a
        ni += b
    _unwrap(objs)
    _unique(objs)
    if ts.startswith("Body"):
        _visibility_density(objs, family_objs)
    fill = _pack(objs, max(256, res_px // 2), work, tag)
    # плотность: пикселей на сантиметр по видимому кузову (краска) или по всему набору
    uv_a = a3 = 0.0
    for o in objs:
        if ts.startswith("Body") and o["mat"] not in ("paint", "bumper"):
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uv = bm.loops.layers.uv.active
        for f in bm.faces:
            uv_a += _uva(f, uv)
            a3 += f.calc_area()
        bm.free()
    dens = math.sqrt(uv_a * res_px * res_px / a3) / 100.0 if a3 > 0 else 0.0
    warn = "  UV_FILL_LOW" if fill < UV_FILL_MIN else ""
    print(f"UV {tag}: заполнение {fill * 100:.0f} %, {dens:.1f} пикс/см ({res_px}), вырезано треугольников {nf}, "
          f"разрезано островов {ni}{warn}")
    return {"fill": round(fill, 3), "px_cm": round(dens, 2), "res": res_px}
