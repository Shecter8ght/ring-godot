# «Осока»: ретопология — игровая сетка той же процедурной сборкой формы, что и принятая high-poly (build.py, части
# part_*.py), с подменами на время прогона (исходники формы и принятый файл не меняются; приём Мосина, game_retopo):
# - тела вращения — число сегментов по допуску прогиба TOL_ROUND (кратно 4), не больше исходного;
# - контуры призм (рама, литьё, короб, спуск…) после сглаживания обводки — упрощение Дугласа — Пекера с допуском
#   TOL_OUTLINE; скругление кромок — 2 сегмента (радиус от 1.6 мм) или одна фаска 45°; скругления углов контура —
#   число сегментов по допуску;
# - фаски-модификаторы (finish, finish_small, bevel_edges) снимаются: ребро — жёсткое, скругление придёт картой нормалей;
# - насечка рукояти, литые «ИСХОДНОЕ» / «НАКОЛ», штамп таблички — не строятся (рельеф — в карте нормалей с high-poly);
# - нарезка сеткой (grid_split) не нужна: нормали в конце — по площади граней, рёбра круче SHARP_DEG — жёсткие;
# - раструб: 64 сегмента (8 желобков по 8) и станции только там, где меняется профиль или глубина желобка; крышки
#   с выемками по ободу — 6 сегментов на выемку; стабилизаторы ракеты — 10 × 1 клеток; ремень — шаг 10 мм.
# Подвижные детали и риг — те же (part_rig: OSOKA_Controls, драйверы), имена объектов — как у high-poly.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/osoka/game_retopo.py -- <out.blend>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import build  # noqa: E402  (сначала сборка: она перезагружает lib — подмены ставятся после)
import lib  # noqa: E402
import stamps  # noqa: E402
import dims as D  # noqa: E402

MM = lib.MM
TOL_ROUND = 0.12      # мм: прогиб хорды на телах вращения
TOL_OUTLINE = 0.10    # мм: упрощение контуров призм
TOL_FILLET = 0.10     # мм: скругления углов контуров
SHARP_DEG = 60.0      # рёбра круче — жёсткие (правило Godot); 50 — скругления крышек из двух точек профиля (55°)
                      # выходили жёстким ребром (сверка v01)
ROUND2_R = 1.0        # мм: скругление кромки призм от этого радиуса — 2 сегмента, тоньше — фаска 45°
BEVEL_KEEP = 2.0      # мм: фаски-модификаторы шире — остаются (2 сегмента)
SLING_STEP = 6.0      # мм: шаг ремня (10 — на изгибе у петли 2.3 мм мимо, сверка v01)
STATS = {"lathe": 0, "prism": 0}


def seg_for(r, cap, tol=TOL_ROUND):
    """Сегменты окружности радиуса r (мм) при прогибе хорды tol; кратно 4, мин. 8 (от 1.5 мм — 12), не больше cap."""
    if r <= tol * 2:
        return min(cap, 8)
    n = math.pi / math.acos(max(-1.0, 1.0 - tol / r))
    n = int(math.ceil(n / 4.0) * 4)
    n = max(n, 12 if r >= 1.5 else 8)
    return min(cap, n)


# ---------- тела вращения ----------
_lathe = lib.lathe


def lathe_g(name, prof, coll, mat=None, seg=64, cy=0.0, cz=lib.BORE_Z, smooth=True, closed=True):
    rmax = max(abs(r) for _, r in prof)
    s = seg_for(rmax, seg)
    STATS["lathe"] += 1
    return _lathe(name, prof, coll, mat, s, cy, cz, smooth, closed)


# ---------- контуры ----------
def _dist_seg(p, a, b):
    ax, ay = a; bx, by = b; px_, py_ = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.hypot(px_ - ax, py_ - ay)
    t = max(0.0, min(1.0, ((px_ - ax) * dx + (py_ - ay) * dy) / L2))
    return math.hypot(px_ - ax - t * dx, py_ - ay - t * dy)


def _rdp(pts, tol):
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        dmax, imax = 0.0, -1
        for i in range(i0 + 1, i1):
            d = _dist_seg(pts[i], pts[i0], pts[i1])
            if d > dmax:
                dmax, imax = d, i
        if dmax > tol and imax > 0:
            keep[imax] = True
            stack += [(i0, imax), (imax, i1)]
    return [p for p, k in zip(pts, keep) if k]


def dp_closed(pts, tol):
    """Упрощение замкнутого контура: якоря — две самые далёкие точки, обе половины — Дугласом — Пекером."""
    n = len(pts)
    if n < 8:
        return list(pts)
    i_far = max(range(n), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    a = _rdp(pts[0:i_far + 1], tol)
    b = _rdp(pts[i_far:] + [pts[0]], tol)
    out = a[:-1] + b[:-1]
    return out if len(out) >= 4 else list(pts)


def fillet_g(points, radii, seg=6):
    """Как lib.fillet, но число сегментов — на каждом углу по допуску TOL_FILLET (не больше seg)."""
    n = len(points)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p0 = Vector(points[i - 1]); p1 = Vector(points[i]); p2 = Vector(points[(i + 1) % n])
        r = radii[i]
        if r <= 0:
            out.append((p1.x, p1.y)); continue
        a = (p0 - p1); b = (p2 - p1)
        la, lb = a.length, b.length
        if la < 1e-9 or lb < 1e-9:
            out.append((p1.x, p1.y)); continue
        a.normalize(); b.normalize()
        ang = a.angle(b)
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            out.append((p1.x, p1.y)); continue
        t = r / math.tan(ang / 2)
        t = min(t, la * 0.49, lb * 0.49)
        r_eff = t * math.tan(ang / 2)
        s = p1 + a * t; e = p1 + b * t
        bis = (a + b).normalized()
        c = p1 + bis * (r_eff / math.sin(ang / 2))
        v0 = s - c; v1 = e - c
        a0 = math.atan2(v0.y, v0.x); a1 = math.atan2(v1.y, v1.x)
        da = a1 - a0
        while da > math.pi: da -= 2 * math.pi
        while da < -math.pi: da += 2 * math.pi
        step = 2 * math.acos(max(-1.0, 1.0 - TOL_FILLET / max(r_eff, 1e-6))) if r_eff > TOL_FILLET else math.pi
        sg = max(1, min(seg, int(math.ceil(abs(da) / step))))
        for k in range(sg + 1):
            aa = a0 + da * k / sg
            out.append((c.x + math.cos(aa) * r_eff, c.y + math.sin(aa) * r_eff))
    return out


def rounded_prism_g(name, pts, y0, y1, r, coll, mat=None, seg=6, tri_caps=False, r_fn=None, smooth=(0.7, 3)):
    """lib.rounded_prism для игры: та же обводка (сглаживание), затем упрощение контура; кромка — 2 сегмента
    (радиус от ROUND2_R) или фаска 45°. Граница плоской боковины и скругления — жёсткое ребро: иначе нормали края
    тянулись по длинным треугольникам боковины тёмными клиньями (спуск, сверка v01)."""
    pts = lib.smooth_poly(pts, smooth[0], smooth[1])
    pts = dp_closed(pts, TOL_OUTLINE)
    rs = [r_fn(x, z) for x, z in pts] if r_fn is not None else [r] * len(pts)
    sg = 2 if max(rs) >= ROUND2_R else 1
    sg = min(sg, seg)
    rings = []
    angs = [math.pi / 2 * k / sg for k in range(sg + 1)]
    for t in reversed(angs):
        k = 1.0 - math.sin(t) if t < math.pi / 2 else 0.0
        rings.append(([y0 + ri * k for ri in rs], [ri * (1 - math.cos(t)) for ri in rs]))
    for t in angs:
        if t == 0 and r_fn is None and abs((y1 - r) - (y0 + r)) < 1e-6:
            continue
        k = 1.0 - math.sin(t) if t < math.pi / 2 else 0.0
        rings.append(([y1 - ri * k for ri in rs], [ri * (1 - math.cos(t)) for ri in rs]))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vr = []
    for ys, ds in rings:
        q = lib.offset_poly(pts, ds) if max(ds) > 1e-9 else pts
        vr.append([bm.verts.new(lib.v(x, y, z)) for (x, z), y in zip(q, ys)])
    n = len(pts)
    for r0, r1 in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    caps = [bm.faces.new(vr[0]), bm.faces.new(list(reversed(vr[-1])))]
    for f in caps:
        for e in f.edges:
            e.smooth = False
    if tri_caps:
        bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    STATS["prism"] += 1
    return lib._obj(name, me, coll, mat)


# ---------- фаски, нарезка, надписи ----------
def finish_g(o, w=0.5, seg=2, angle=30.0, apply=True, exclude=None, tri_first=False):
    """Широкие скругления (от BEVEL_KEEP мм — накладка трубы, 3.2 мм) остаются двумя сегментами: без них углы игровой
    торчат за принятую форму на 1.3…1.9 мм (сверка v01); узкие — ребром, скругление придёт картой нормалей."""
    o["_fin"] = 1
    lib.clean(o)
    ww = w * lib.ROUND_K
    if ww < BEVEL_KEEP:
        return o
    keep = o.data.copy()
    before = lib._bbox(o)
    lib.bevel(o, ww, 2, angle, exclude=exclude)
    lib.apply_all(o)
    after = lib._bbox(o)
    if before and after and ((after[0] - before[0]).length > 0.002 or (after[1] - before[1]).length > 0.002):
        print("GAME_BEVEL_FAIL", o.name)
        old = o.data
        o.data = keep
        bpy.data.meshes.remove(old)
    else:
        bpy.data.meshes.remove(keep)
    return o


def finish_small_g(o, w=0.5, seg=2, angle=30.0, exclude=None):
    o["_fin"] = 1
    lib.clean(o)
    return o


def bevel_edges_g(o, pick, w=4.0, seg=6, profile=0.5, clamp=False, where=None):
    return 0


GRID_KEEP = {"Trigger": 3.0}   # деталь → шаг нарезки, мм, перед вырезами


_grid_split = lib.grid_split


def grid_split_g(o, step=12.0, min_verts=12):
    """Нарезка сеткой не нужна, кроме деталей из GRID_KEEP: щека пера с вогнутой выемкой после выреза отверстий стала
    многоугольником с дырами и разбилась треугольником поперёк выемки — щека закрыла прилив (сверка v01). Разбивка
    торцов на треугольники до булевых тоже не годится: точное булево даёт задвоенные грани (вставки рукояти)."""
    if o.name in GRID_KEEP:
        r = _grid_split(o, step=GRID_KEEP[o.name], min_verts=min_verts)
        # нарезка делает новые рёбра гладкими — и куски границы боковины со скруглением тоже: нормали края гнулись,
        # по щеке пера шли светлые полосы. Граница боковины (грань ±Y) — снова жёсткая
        bm = bmesh.new(); bm.from_mesh(o.data); bm.normal_update()
        for e in bm.edges:
            if len(e.link_faces) == 2:
                f1, f2 = e.link_faces
                c1, c2 = abs(f1.normal.y) > 0.9998, abs(f2.normal.y) > 0.9998
                if c1 != c2:
                    e.smooth = False
        bm.to_mesh(o.data); bm.free()
        return r
    return None


def grid_split_local_g(o, center_mm, radius_mm, axes, step=1.2):
    return None


def stamp_g(*a, **k):
    return None


# ---------- игровые версии отдельных деталей ----------
def bell_g(coll):
    """Раструб с желобками (part_tube.bell): 64 сегмента, станции — концы конуса, начало и конец желобков."""
    import part_tube as T
    x0, x1, r0, r1 = D.BELL
    Ri = 43.0
    n = D.BELL_FLUTES
    xa, xb = x0 + 6.0, x1 - 10.0

    def rfun(x, a, r):
        if r < Ri + 0.5 or x < xa or x > xb:
            return r
        ph = (a * n / (2 * math.pi)) % 1.0
        d = min(abs(ph - 0.5) / 0.24, 1.0)
        prof_ = 0.5 * (1 + math.cos(math.pi * d)) if d < 1.0 else 0.0
        t = min((x - xa) / 5.0, (xb - x) / 5.0, 1.0)
        return r - 2.8 * prof_ * t

    # выход желобка — три станции на 5 мм (у принятой — шаг ~2 мм; одной гранью конец желобка не читался, сверка v01)
    xs = [x0, xa, xa + 1.7, xa + 3.3, xa + 5.0, xb - 5.0, xb - 3.3, xb - 1.7, xb, x1 - 3.0]
    prof = [(x, r0 + (r1 - r0) * (x - x0) / (x1 - x0)) for x in xs]
    prof += [(x1 - 1.8, r1 + 0.8), (x1 - 0.6, r1 + 0.5), (x1, r1 - 0.6), (x1, Ri + 0.8), (x1 - 0.8, Ri), (x0 + 2.0, Ri),
             (x0, Ri + 1.0)]
    # 12 сегментов на желобок (8 — желобки едва читались)
    return T.lathe_mod("Tube_bell", prof, rfun, coll, "Paint_olive", seg=12 * n)


def knurled_lid_g(name, d, h, coll, notches=10, depth=1.2):
    """Крышка с выемками по ободу (part_saddle.knurled_lid): 6 сегментов на выемку, кольца — только по краям выемок."""
    R = d / 2

    def rfun(x, a, r):
        if r < R - 0.01 or x > h - 1.0 or x < 0.6:
            return r
        ph = (a * notches / (2 * math.pi)) % 1.0
        dd = min(abs(ph - 0.5) / 0.14, 1.0)
        return r - depth * (0.5 * (1 + math.cos(math.pi * dd)) if dd < 1.0 else 0.0)

    prof = [(0.0, 0.0), (0.0, R - 0.8), (0.4, R), (0.4 + (h - 2.2) / 8, R), (h - 1.8, R),
            (h - 1.0, R - 0.4), (h - 0.3, R - 1.4), (h, R - 3.0), (h, 0.0)]
    o = _lathe(name, prof, coll, "Paint_olive_cast", seg=notches * 6)
    for vv in o.data.vertices:
        x = vv.co.x / MM
        r = math.hypot(vv.co.y, vv.co.z) / MM
        if r > 1e-3:
            a = math.atan2(vv.co.z, vv.co.y)
            r2 = rfun(x, a, r)
            if r2 != r:
                vv.co.y *= r2 / r
                vv.co.z *= r2 / r
    return o


def tail_fin_g(name, phi0_deg, coll):
    """Стабилизатор ракеты (part_missile.tail_fin): изогнутая пластина 10 × 1 клеток."""
    import part_missile as M
    r0, t = M.TAIL_R + 0.6, 1.4
    x0, x1 = M.FIN_CHORD
    n_a, n_x = 10, 1
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    grid = {}
    for side, rr in ((0, r0), (1, r0 + t)):
        for i in range(n_a + 1):
            a = math.radians(phi0_deg + M.FIN_SPAN_DEG * i / n_a)
            frac = i / n_a
            xa = x0 + 8.0 * frac
            xb = x1 - 26.0 * frac ** 1.5
            for j in range(n_x + 1):
                x = xa + (xb - xa) * j / n_x
                grid[(side, i, j)] = bm.verts.new(lib.v(x, rr * math.cos(a), rr * math.sin(a)))
    for side in (0, 1):
        for i in range(n_a):
            for j in range(n_x):
                q = (grid[(side, i, j)], grid[(side, i + 1, j)], grid[(side, i + 1, j + 1)], grid[(side, i, j + 1)])
                bm.faces.new(q if side else tuple(reversed(q)))
    for i in range(n_a):
        for j in (0, n_x):
            bm.faces.new((grid[(0, i, j)], grid[(0, i + 1, j)], grid[(1, i + 1, j)], grid[(1, i, j)]))
    for j in range(n_x):
        for i in (0, n_a):
            bm.faces.new((grid[(0, i, j)], grid[(0, i, j + 1)], grid[(1, i, j + 1)], grid[(1, i, j)]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = lib._obj(name, me, coll, "Fin_steel")
    a0 = math.radians(phi0_deg)
    lib.set_origin(o, (x0, (r0 + t / 2) * math.cos(a0), (r0 + t / 2) * math.sin(a0)))
    return o


def game_normals():
    """Вместо build.flat_normals: сварка, многоугольники — на треугольники (уши), всё гладкое, рёбра круче SHARP_DEG
    и край сетки — жёсткие (уже жёсткие — край боковин призм, буквы — остаются), нормали по площади граней."""
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002 * MM)
        bmesh.ops.dissolve_degenerate(bm, dist=0.002 * MM, edges=bm.edges)
        big = [f for f in bm.faces if len(f.verts) > 4]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        loose = [vv for vv in bm.verts if not vv.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.normal_update()
        for f in bm.faces:
            f.smooth = True
        lim = math.radians(SHARP_DEG)
        for e in bm.edges:
            e.smooth = e.smooth and len(e.link_faces) == 2 and e.calc_face_angle(0.0) <= lim
        bm.to_mesh(o.data); bm.free()
        o.modifiers.clear()
        lib.weighted(o)
        lib.apply_all(o)


def patch():
    lib.lathe = lathe_g
    lib.rounded_prism = rounded_prism_g
    lib.fillet = fillet_g
    lib.finish = finish_g
    lib.finish_small = finish_small_g
    lib.bevel_edges = bevel_edges_g
    lib.grid_split = grid_split_g
    lib.grid_split_local = grid_split_local_g
    stamps.stamp = stamp_g
    # части импортируются после подмен lib — их «from lib import …» берут игровые функции
    import part_tube, part_saddle, part_launcher, part_power, part_sling, part_missile, part_rig  # noqa: F401
    part_tube.bell = bell_g
    part_saddle.knurled_lid = knurled_lid_g
    _arc = part_saddle.arc_shell
    part_saddle.arc_shell = lambda name, x0, x1, r_in, r_out, a0, a1, coll, mat, seg=48: _arc(
        name, x0, x1, r_in, r_out, a0, a1, coll, mat, seg=max(4, int(math.ceil(abs(a1 - a0) / 6.0))))
    part_launcher.knurl_patch = lambda *a, **k: None
    _res = part_sling.resample
    part_sling.resample = lambda pts, step=4.0: _res(pts, max(step, SLING_STEP))
    part_missile.tail_fin = tail_fin_g
    build.flat_normals = game_normals


def report():
    groups = {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        c = o.users_collection[0].name if o.users_collection else "-"
        groups.setdefault(c, []).append((lib.tris(o), o.name))
    hand = 0
    for c, rows in sorted(groups.items()):
        n = sum(r[0] for r in rows)
        if c != "Missile":
            hand += n
        print("GAME_COLL", c, n)
    allrows = sorted((r for rows in groups.values() for r in rows), reverse=True)
    for n, name in allrows[:40]:
        print("GAME_OBJ", n, name)
    print("GAME_TRIS_HANDS", hand, "MISSILE", sum(r[0] for r in groups.get("Missile", [])))
    print("GAME_STATS", STATS)


patch()
build.main()
report()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--") + 1]), compress=True)
