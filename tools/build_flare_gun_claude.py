"""Компактная ракетница (переломная, 12-й калибр) и два патрона — модель Claude, v02.

Основа формы — фото владельца «8» (_asset_src/flare_gun_claude/refs/09.webp: красная ракетница на ковре, строго
сбоку) и модель по его ссылке на Sketchfab (вид сверху, спереди, толщины). Контуры рамы, накладки, скобы, курка и
спуска сняты с фото программой tools/trace_flare_gun_claude.py (trace/profiles.json, миллиметры), здесь из них
строится объём. Масштаб — по наружному диаметру ствола 28 мм; патрон — 12-й калибр, как на фото «7».

Детали (каждая — отдельный объект со своей осью):
  Frame — рама: рукоять с окнами под накладки, коробка под стволом с вилкой шарнира, скоба, ушко под шнур,
          казённый щиток с отверстием бойка, паз курка, приливы осей, таблички под надписи;
  Barrel — ствол (начало — ось шарнира; +32° вокруг своей X — открыт): труба с расточкой под закраину,
          прицельная планка, таблички по бокам, седло и ушко шарнира; дети — метки Muzzle и Chamber;
  Hammer — курок со спицей и бойком (начало — ось; −43° вокруг своей X — взведён, как на фото);
  Trigger — спуск (начало — ось); BarrelLatch_L/R — пружинные защёлки ствола на щитке;
  GripPad_L/R — тонкие пластиковые накладки; GripScrews, Pins — винт накладки и оси.
  Flare_Red_Claude — осветительный патрон, Flare_Green_Claude — патрон вызова груза.

Рукоятка скруглена под руку (grip_radius: 6 мм на спинке, пятке и под пальцами, к коробке сходит к фаске 1.2 мм),
накладки идут по тому же скруглению.

Материалы раздельные (под UCUPaint): FlareGun_Body_Metal — рама и ствол (потом красная матовая краска с
потёртостями до металла), FlareGun_Small_Steel — курок, спуск, оси, FlareGun_Bright_Steel — боёк, защёлки, винт,
FlareGun_Grip_Plastic — накладки; у патронов — латунь, пластик гильзы (красный / зелёный), пыж.

Оси сцены как у ВЕРАСа: дуло по −Y, верх +Z, +X — левая сторона стрелка; начало — середина рукоятки.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_flare_gun_claude.py
  → _asset_src/flare_gun_claude/FlareGun_Claude_v02.blend (правится: фаски, наплывы и вырезы — модификаторы),
    …_v02_game.blend (модификаторы применены, развёртка), asset-audit.json,
    assets/models/weapons/flare_gun_claude/{flare_gun_claude,flare_red_claude,flare_green_claude}.glb
… -- render  → _asset_src/flare_gun_claude/Просмотр/*.png (из сохранённого игрового файла)
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
OUT = ROOT / "assets/models/weapons/flare_gun_claude"
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "build"
EDIT_FILE = SRC / "FlareGun_Claude_v02.blend"
GAME_FILE = SRC / "FlareGun_Claude_v02_game.blend"
PROF = json.loads((SRC / "trace/profiles.json").read_text(encoding="utf-8"))
MM = 0.001
U0, V0 = -62.0, -57.0                       # середина рукоятки в осях чертежа (u вперёд от казны, v вверх от оси ствола)
R_OUT, R_BORE, R_RIM = 14.0, 10.3, 11.45    # ствол: наружный радиус, канал (он же патронник), расточка под закраину
LEN = float(PROF["muzzle_u"])
HINGE = tuple(PROF["pin_hinge"])
HPIV = tuple(PROF["pin_hammer"])
TPIV = tuple(PROF["pin_trigger"])
T_MAIN, T_BOW, T_RING = 9.0, 4.2, 3.6       # половина толщины: рама, дуга скобы, ушко
SHIELD_U, SHIELD_HALF = -6.0, 14.6          # казённый щиток: задняя плоскость и половина ширины
BREECH = 0.3                                # зазор между щитком и казённым срезом ствола
OPEN_DEG = 32.0
EAR_R = 4.3                                 # ушко шарнира ствола: радиус вокруг оси
R_EDGE, R_GRIP = 1.2, 6.0                   # скругление кромок рамы: обычное и на рукоятке (под ладонь и пальцы)
PAD_PROUD, PAD_FLOOR = 0.8, 5.5             # накладка: выступает над рамой; дно окна под неё (от плоскости симметрии)
SEG = 64


def P(u: float, v: float, x: float = 0.0) -> Vector:
    """Точка чертежа (мм) → сцена (м): дуло по −Y."""
    return Vector((x * MM, -(u - U0) * MM, (v - V0) * MM))


# ---------------------------------------------------------------- контуры

def clean(poly: list, eps: float = 0.03) -> list:
    out: list = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > eps:
            out.append((float(p[0]), float(p[1])))
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def rot(p, c, deg: float) -> tuple:
    a = math.radians(deg)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * math.cos(a) - dy * math.sin(a), c[1] + dx * math.sin(a) + dy * math.cos(a))


def clip_half(poly: list, a: float, b: float, c: float) -> list:
    """Часть многоугольника, где a·u + b·v ≤ c."""
    out: list = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp, dq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return clean(out)


def hull(points: list) -> list:
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def grow(poly: list, c, k: float) -> list:
    return [(c[0] + (p[0] - c[0]) * k, c[1] + (p[1] - c[1]) * k) for p in poly]


def arc(cu: float, cv: float, r: float, a0: float, a1: float, n: int) -> list:
    return [(cu + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cv + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rrect(a0: float, b0: float, a1: float, b1: float, r: float, n: int = 6, r_top: float | None = None) -> list:
    """Прямоугольник со скруглёнными углами (r_top — свой радиус у верхних углов)."""
    rt = r if r_top is None else r_top
    return clean(arc(a1 - r, b0 + r, r, -90, 0, n) + arc(a1 - rt, b1 - rt, rt, 0, 90, n) + arc(a0 + rt, b1 - rt, rt, 90, 180, n) + arc(a0 + r, b0 + r, r, 180, 270, n))


def top_at(poly: list, u: float) -> float:
    """Верхняя точка многоугольника на вертикали u."""
    best = -1e9
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        if (p[0] - u) * (q[0] - u) <= 0 and abs(q[0] - p[0]) > 1e-9:
            best = max(best, p[1] + (q[1] - p[1]) * (u - p[0]) / (q[0] - p[0]))
    return best


# ---------------------------------------------------------------- сетки

def slab(bm: bmesh.types.BMesh, contour: list, x0: float, x1: float, holes: tuple = ()) -> None:
    """Пластина по контуру вида сбоку [(u, v)…] от x0 до x1 (мм), с отверстиями."""
    loops = [clean(contour)] + [clean(h) for h in holes]
    a = [[bm.verts.new(P(u, v, x0)) for u, v in lp] for lp in loops]
    b = [[bm.verts.new(P(u, v, x1)) for u, v in lp] for lp in loops]
    for rings in (a, b):
        if len(loops) == 1:
            bm.faces.new(rings[0])
        else:
            edges = [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for vs in rings for i in range(len(vs))]
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    for va, vb in zip(a, b):
        n = len(va)
        for i in range(n):
            bm.faces.new((va[i], va[(i + 1) % n], vb[(i + 1) % n], vb[i]))


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def grip_radius(u: float, v: float) -> float:
    """Радиус скругления кромки рамы в точке контура (мм): на рукоятке большой — чтобы не резала ладонь и пальцы,
    у хвоста под спицей курка умеренный (рядом паз), на коробке обычная фаска."""
    along = smoothstep((-20.0 - u) / 14.0)          # 0 у коробки (u ≥ −20), 1 на рукоятке (u ≤ −34)
    down = smoothstep((-10.0 - v) / 14.0)           # 0 на верхней линии хвоста, 1 ниже v = −24
    return R_EDGE + (R_GRIP - R_EDGE) * along * max(down, 0.3)


def round_corners(loop: list, r: float, deg: float = 38.0, n: int = 4) -> list:
    """Острые углы контура → маленькие дуги: после этого у каждой точки есть нормаль и радиус кривизны."""
    out: list = []
    m = len(loop)
    for i in range(m):
        p0, p1, p2 = Vector(loop[i - 1]), Vector(loop[i]), Vector(loop[(i + 1) % m])
        d0, d1 = p0 - p1, p2 - p1
        if d0.length < 1e-6 or d1.length < 1e-6 or math.pi - d0.angle(d1) < math.radians(deg):
            out.append((p1.x, p1.y))
            continue
        ang = d0.angle(d1)
        t = min(r / math.tan(ang / 2.0), 0.45 * d0.length, 0.45 * d1.length)
        rr = t * math.tan(ang / 2.0)
        a, b = p1 + d0.normalized() * t, p1 + d1.normalized() * t
        c = p1 + (d0.normalized() + d1.normalized()).normalized() * (rr / math.sin(ang / 2.0))
        a0 = math.atan2(a.y - c.y, a.x - c.x)
        sweep = math.atan2(b.y - c.y, b.x - c.x) - a0
        while sweep > math.pi:
            sweep -= math.tau
        while sweep < -math.pi:
            sweep += math.tau
        out += [(c.x + rr * math.cos(a0 + sweep * k / n), c.y + rr * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]
    return clean(out)


def rounded_slab(bm: bmesh.types.BMesh, contour: list, half: float, radius_fn=None, steps: int = 6) -> None:
    """Пластина по контуру (толщина ±half) со скруглёнными кромками: радиус в каждой точке — radius_fn(u, v).
    Радиус ужимается там, где сам контур круче (иначе кромка вывернется), и меняется вдоль контура плавно.
    Сетка строится кольцами с одним числом точек — замкнута по построению (модификатор «Фаска» на переменной
    ширине давал самопересечения, и булевы операции разваливались)."""
    loop = round_corners(clean(contour), R_EDGE)
    n = len(loop)
    if sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n)) < 0.0:
        loop.reverse()                                               # обход против часовой: нормаль наружу — вправо от хода
    normals, radii, miters, rhos = [], [], [], []
    for i in range(n):
        p0, p1, p2 = Vector(loop[i - 1]), Vector(loop[i]), Vector(loop[(i + 1) % n])
        t0, t1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        tan = t0 + t1
        tan = tan.normalized() if tan.length > 1e-9 else t1
        normals.append(Vector((tan.y, -tan.x)))
        turn = math.atan2(t0.x * t1.y - t0.y * t1.x, t0.dot(t1))    # > 0 — выпуклое место
        rho = (p2 - p0).length / (2.0 * math.sin(turn)) if turn > 1e-4 else 1e9
        target = radius_fn(p1.x, p1.y) if radius_fn else R_EDGE
        radii.append(target)
        rhos.append(rho)
        miters.append(min(1.15, 1.0 / max(0.5, math.cos(turn / 2.0))))
    limit = [0.8 * rhos[i] for i in range(n)]                         # строже местной кривизны нельзя: кромка вывернется
    radii = [max(0.25, min(radii[i], limit[i])) for i in range(n)]
    seg = [math.hypot(loop[(i + 1) % n][0] - loop[i][0], loop[(i + 1) % n][1] - loop[i][1]) for i in range(n)]
    for _ in range(3):                                               # радиус не меняется быстрее 0.3 мм на миллиметр контура
        for i in range(n):
            radii[i] = min(radii[i], radii[i - 1] + 0.3 * seg[i - 1])
        for i in range(n - 1, -1, -1):
            radii[i] = min(radii[i], radii[(i + 1) % n] + 0.3 * seg[i])
    for _ in range(12):                                              # и без изломов: усреднение с соседями, не выше предела
        radii = [min(radii[i], 0.25 * radii[i - 1] + 0.5 * radii[i] + 0.25 * radii[(i + 1) % n]) for i in range(n)]
    rings: dict = {}
    for side in (1.0, -1.0):
        for k in range(steps + 1):
            th = (math.pi / 2.0) * k / steps
            rings[(side, k)] = [bm.verts.new(P(loop[i][0] - normals[i].x * radii[i] * (1.0 - math.cos(th)) * miters[i],
                                                 loop[i][1] - normals[i].y * radii[i] * (1.0 - math.cos(th)) * miters[i],
                                                 side * (half - radii[i] * (1.0 - math.sin(th))))) for i in range(n)]
    for side in (1.0, -1.0):
        for k in range(steps):
            r0, r1 = rings[(side, k)], rings[(side, k + 1)]
            for i in range(n):
                bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
        bm.faces.new(rings[(side, steps)])
    a, b = rings[(1.0, 0)], rings[(-1.0, 0)]
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))


def slab3(bm: bmesh.types.BMesh, base: list, push: Vector) -> None:
    """Пластина: контур из точек сцены, вытянутый на push."""
    a = [bm.verts.new(p) for p in base]
    b = [bm.verts.new(p + push) for p in base]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(base)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))


def lathe(bm: bmesh.types.BMesh, profile: list, closed: bool = True, seg: int = SEG, caps: tuple = (False, False),
          mats: list | None = None, origin: tuple = (0.0, 0.0), direction: tuple = (1.0, 0.0), axis_x: float = 0.0) -> None:
    """Тело вращения: profile [(длина вдоль оси, радиус)…]; ось — из origin (u, v) по direction в плоскости чертежа."""
    d = Vector(direction).normalized()
    nrm = Vector((-d.y, d.x))
    rings = []
    for t, r in profile:
        cu, cv = origin[0] + d.x * t, origin[1] + d.y * t
        rings.append([bm.verts.new(P(cu + nrm.x * r * math.sin(math.tau * k / seg), cv + nrm.y * r * math.sin(math.tau * k / seg),
                                     axis_x + r * math.cos(math.tau * k / seg))) for k in range(seg)])
    count = len(rings) if closed else len(rings) - 1
    for i in range(count):
        r0, r1 = rings[i], rings[(i + 1) % len(rings)]
        for k in range(seg):
            f = bm.faces.new((r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]))
            if mats:
                f.material_index = mats[i]
    for flag, ring, idx in ((caps[0], rings[0], 0), (caps[1], rings[-1], -1)):
        if flag:
            f = bm.faces.new(ring)
            f.material_index = mats[idx] if mats else 0


def cyl_x(bm: bmesh.types.BMesh, u: float, v: float, r: float, x0: float, x1: float, seg: int = 28) -> None:
    """Цилиндр поперёк оружия (вдоль X)."""
    slab(bm, [(u + r * math.cos(math.tau * k / seg), v + r * math.sin(math.tau * k / seg)) for k in range(seg)], x0, x1)


def collection(name: str, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def make(name: str, bm: bmesh.types.BMesh, materials, parent=None, origin: Vector | None = None, col=None):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    for m in (materials if isinstance(materials, (list, tuple)) else [materials]):
        me.materials.append(m)
    for poly in me.polygons:
        poly.use_smooth = True
    if origin is not None:
        me.transform(Matrix.Translation(-origin))
        ob.location = origin
    if parent is not None:
        bpy.context.view_layer.update()
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob


def operand(name: str, bm: bmesh.types.BMesh, col, owner):
    """Вспомогательная деталь для наплыва или выреза: идёт за хозяином, в рендер не попадает."""
    ob = make(name, bm, list(owner.data.materials) or [M_BODY], parent=owner, col=col)   # срезы — материалом хозяина
    ob.hide_render = True
    ob.display_type = "WIRE"
    return ob


def bevel(ob, width_mm: float, segments: int = 3, angle: float = 40.0) -> None:
    mod = ob.modifiers.new("Фаска", "BEVEL")
    mod.width = width_mm * MM
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = False


def boolean(ob, name: str, operation: str, col=None, other=None) -> None:
    mod = ob.modifiers.new(name, "BOOLEAN")
    mod.operation = operation
    mod.solver = "EXACT"
    if col is not None:
        mod.operand_type = "COLLECTION"
        mod.collection = col
    else:
        mod.object = other


def smooth_group():
    """Свой «сгладить по углу»: рёбра круче 30° остаются острыми, остальное гладкое."""
    g = bpy.data.node_groups.get("Сгладить по углу")
    if g:
        return g
    g = bpy.data.node_groups.new("Сгладить по углу", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    g.is_modifier = True
    n_in, n_out = g.nodes.new("NodeGroupInput"), g.nodes.new("NodeGroupOutput")
    ang = g.nodes.new("GeometryNodeInputMeshEdgeAngle")
    cmp_node = g.nodes.new("FunctionNodeCompare")
    cmp_node.data_type = "FLOAT"
    cmp_node.operation = "LESS_EQUAL"
    cmp_node.inputs[1].default_value = math.radians(30.0)
    edge = g.nodes.new("GeometryNodeSetShadeSmooth")
    edge.domain = "EDGE"
    face = g.nodes.new("GeometryNodeSetShadeSmooth")
    face.domain = "FACE"
    g.links.new(n_in.outputs[0], edge.inputs["Geometry"])
    g.links.new(ang.outputs["Unsigned Angle"], cmp_node.inputs[0])
    g.links.new(cmp_node.outputs[0], edge.inputs["Shade Smooth"])
    g.links.new(edge.outputs[0], face.inputs["Geometry"])
    g.links.new(face.outputs[0], n_out.inputs[0])
    return g


def smooth(ob) -> None:
    mod = ob.modifiers.new("Сглаживание", "NODES")
    mod.node_group = smooth_group()


def material(name: str, color: tuple, metallic: float, roughness: float, grain: float = 0.0):
    """Материал-заглушка для проверки формы. Узел Bevel скругляет в рендере мелкие острые кромки (0.25 мм)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 6
    bev.inputs["Radius"].default_value = 0.00025
    if grain > 0.0:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3400.0
        noise.inputs["Detail"].default_value = 3.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = grain
        bump.inputs["Distance"].default_value = 0.00035
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bev.outputs["Normal"], bump.inputs["Normal"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    else:
        nt.links.new(bev.outputs["Normal"], b.inputs["Normal"])
    return m


# ================================================================ сборка

def build() -> None:
    global M_BODY
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    M_BODY = material("FlareGun_Body_Metal", (0.19, 0.195, 0.205), 1.0, 0.48)
    M_STEEL = material("FlareGun_Small_Steel", (0.045, 0.047, 0.052), 1.0, 0.42)
    M_BRIGHT = material("FlareGun_Bright_Steel", (0.62, 0.63, 0.64), 1.0, 0.3)
    M_GRIP = material("FlareGun_Grip_Plastic", (0.022, 0.022, 0.024), 0.0, 0.6, grain=0.5)
    M_BRASS = material("Flare_Case_Brass", (0.78, 0.60, 0.30), 1.0, 0.32)
    M_WAD = material("Flare_Wad", (0.82, 0.80, 0.72), 0.0, 0.8)
    M_RED = material("Flare_Hull_Red", (0.62, 0.035, 0.03), 0.0, 0.42)
    M_GREEN = material("Flare_Hull_Green", (0.035, 0.30, 0.09), 0.0, 0.42)

    gun = bpy.data.objects.new("FlareGun_Claude", None)
    scene.collection.objects.link(gun)
    gun.empty_display_size = 0.02
    col_ops = collection("Вспомогательные (наплывы и вырезы)")

    # ------------------------------------------------------------ рама
    bm = bmesh.new()
    rounded_slab(bm, PROF["frame_main"], T_MAIN, grip_radius)
    frame = make("Frame", bm, M_BODY, parent=gun)
    # оболочка рукоятки с накладками: та же рама, толще на выступ накладки — по ней обрезаются накладки
    bm = bmesh.new()
    rounded_slab(bm, PROF["frame_main"], T_MAIN + PAD_PROUD, grip_radius)
    envelope = operand("Grip_Envelope", bm, col_ops, frame)
    f_add, f_cut = collection("Frame_Add", col_ops), collection("Frame_Cut", col_ops)

    bm = bmesh.new()
    slab(bm, PROF["guard_bow"], -T_BOW, T_BOW)
    bevel(operand("Frame_GuardBow", bm, f_add, frame), 1.5, 4, 50.0)
    # ушко под шнур: тонкая перемычка с отверстием — карманы с обеих сторон и сквозное отверстие
    lc = PROF["lanyard_center"]
    pocket = [(lc[0] + 6.7 * math.cos(math.tau * k / 40), lc[1] + 6.7 * math.sin(math.tau * k / 40)) for k in range(40)]
    for sign, tag in ((1.0, "L"), (-1.0, "R")):
        bm = bmesh.new()
        slab(bm, pocket, sign * T_RING, sign * (T_MAIN + 3.0))
        operand("Frame_LanyardPocket_" + tag, bm, f_cut, frame)
    bm = bmesh.new()
    slab(bm, PROF["lanyard_hole"], -T_MAIN - 3.0, T_MAIN + 3.0)
    operand("Frame_LanyardHole", bm, f_cut, frame)
    # казённый щиток: шире ствола, закрывает закраину патрона
    bm = bmesh.new()
    front = rrect(-SHIELD_HALF, -12.8, SHIELD_HALF, 15.05, 3.0, 6, r_top=7.0)
    slab3(bm, [P(SHIELD_U, v, x) for x, v in front], P(0.1, 0.0) - P(SHIELD_U, 0.0))
    bevel(operand("Frame_BreechShield", bm, f_add, frame), 0.9, 3)
    # таблички под надписи и приливы осей — на обеих сторонах
    plates = [(PROF["plate_big"], 2.4), (PROF["plate_small"], 2.0)]
    for sign, tag in ((1.0, "L"), (-1.0, "R")):
        for i, ((a, b), r) in enumerate(plates):
            u0, u1, v0, v1 = min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])
            bm = bmesh.new()
            slab(bm, rrect(u0, v0, u1, v1, r), sign * (T_MAIN - 0.5), sign * (T_MAIN + 0.5))
            bevel(operand(f"Frame_Plate{i}_{tag}", bm, f_add, frame), 0.3, 2)
            bm = bmesh.new()
            slab(bm, rrect(u0 + 0.9, v0 + 0.9, u1 - 0.9, v1 - 0.9, max(r - 0.9, 0.6)), sign * (T_MAIN + 0.25), sign * (T_MAIN + 2.0))
            operand(f"Frame_PlateField{i}_{tag}", bm, f_cut, frame)
        for i, pin in enumerate((HPIV, TPIV)):
            bm = bmesh.new()
            cyl_x(bm, pin[0], pin[1], 3.7, sign * (T_MAIN - 0.5), sign * (T_MAIN + 0.35))
            bevel(operand(f"Frame_Boss{i}_{tag}", bm, f_add, frame), 0.25, 2)
        bm = bmesh.new()
        slab(bm, PROF["pad_recess"], sign * PAD_FLOOR, sign * (T_MAIN + 3.0))
        operand("Frame_PadRecess_" + tag, bm, f_cut, frame)
    for sign, tag in ((1.0, "L"), (-1.0, "R")):                     # скосы: толщина рамы сходит к толщине дуги скобы
        bm = bmesh.new()
        slab3(bm, [P(u, -73.0, sign * x) for u, x in ((-21.3, T_MAIN + 0.5), (-12.6, T_BOW), (-12.6, T_MAIN + 1.5), (-21.3, T_MAIN + 1.5))], P(0.0, -57.0) - P(0.0, -73.0))
        operand("Frame_GuardTaperRear_" + tag, bm, f_cut, frame)
        bm = bmesh.new()
        slab3(bm, [P(12.0, v, sign * x) for v, x in ((-40.45, T_MAIN + 0.5), (-46.2, T_BOW + 0.15), (-48.6, T_BOW + 0.15), (-48.6, T_MAIN + 1.5), (-40.45, T_MAIN + 1.5))], P(24.0, 0.0) - P(12.0, 0.0))
        operand("Frame_GuardTaperFront_" + tag, bm, f_cut, frame)
    for i, pin in enumerate((HPIV, TPIV, HINGE)):
        bm = bmesh.new()
        cyl_x(bm, pin[0], pin[1], 2.3, -T_MAIN - 4.0, T_MAIN + 4.0)
        operand(f"Frame_PinHole{i}", bm, f_cut, frame)

    # курок: на фото взведён; исходное положение — спущен (боёк в отверстии щитка)
    ham_c = clean(PROF["hammer_cocked"])
    tip_c = tuple(PROF["firing_tip_cocked"])
    reach = math.hypot(tip_c[0] - HPIV[0], tip_c[1] - HPIV[1])
    tip_r = (HPIV[0] + math.sqrt(reach ** 2 - HPIV[1] ** 2), 0.0)
    cock = math.degrees(math.atan2(tip_c[1] - HPIV[1], tip_c[0] - HPIV[0]) - math.atan2(tip_r[1] - HPIV[1], tip_r[0] - HPIV[0]))
    ham_r = [rot(p, HPIV, -cock) for p in ham_c]
    body_c = clip_half(ham_c, -1.0, 0.0, 41.5)                       # без спицы: она над рамой
    sweep = [rot(p, HPIV, -cock * k / 6.0) for k in range(7) for p in body_c]
    slot = clip_half(grow(hull(sweep), HPIV, 1.07), 1.0, 0.0, SHIELD_U + 1.7)
    bm = bmesh.new()
    slab(bm, slot, -3.5, 3.5)
    operand("Frame_HammerSlot", bm, f_cut, frame)
    bm = bmesh.new()
    lathe(bm, [(SHIELD_U - 1.5, 1.5), (0.6, 1.5)], closed=False, seg=20, caps=(True, True))
    operand("Frame_FiringPinHole", bm, f_cut, frame)

    trig = clean(PROF["trigger"])
    upper = [p for p in trig if p[1] > -45.0]
    bm = bmesh.new()
    slab(bm, grow(hull([rot(p, TPIV, -a) for a in (0.0, 7.0, 14.0) for p in upper]), TPIV, 1.1), -2.9, 2.9)
    operand("Frame_TriggerSlot", bm, f_cut, frame)

    # выборка в коробке под ствол и его седло в открытом положении (перелом вокруг передней оси)
    bm = bmesh.new()
    lathe(bm, [(HINGE[0] - 2.5, R_OUT + 0.3), (66.0, R_OUT + 0.3)], closed=False, caps=(True, True))
    slab(bm, [(HINGE[0] - 1.0, -14.4), (HINGE[0] + EAR_R + 0.4, -14.4), (HINGE[0] + EAR_R + 0.4, -9.0), (HINGE[0] - 1.0, -9.0)], -T_MAIN - 1.0, T_MAIN + 1.0)
    relief = operand("Frame_OpenRelief", bm, f_cut, frame)
    bm = bmesh.new()                                                 # чистый скос переднего верхнего угла коробки (на фото — маленький уступ)
    slab(bm, [(HINGE[0] + EAR_R + 0.25, -14.25), (57.0, -17.1), (57.0, -12.0), (HINGE[0] + EAR_R + 0.25, -12.0)], -T_MAIN - 1.0, T_MAIN + 1.0)
    operand("Frame_FrontChamfer", bm, f_cut, frame)
    turn = Matrix.Translation(P(*HINGE)) @ Matrix.Rotation(math.radians(OPEN_DEG), 4, "X") @ Matrix.Translation(-P(*HINGE))
    relief.data.transform(turn)

    boolean(frame, "Наплывы", "UNION", col=f_add)
    boolean(frame, "Вырезы", "DIFFERENCE", col=f_cut)
    smooth(frame)

    # ------------------------------------------------------------ ствол
    bm = bmesh.new()
    muzzle = [(LEN - 1.3 + 1.3 * math.sin(math.radians(a)), R_OUT - 1.3 + 1.3 * math.cos(math.radians(a))) for a in (0, 22.5, 45, 67.5, 90)]
    lathe(bm, [(BREECH + 1.6, R_BORE), (BREECH + 1.6, R_RIM), (BREECH, R_RIM), (BREECH, R_OUT - 0.5), (BREECH + 0.5, R_OUT)] + muzzle +
          [(LEN, R_BORE + 0.8), (LEN - 0.8, R_BORE)])
    barrel = make("Barrel", bm, M_BODY, parent=gun, origin=P(*HINGE))
    b_add, b_cut = collection("Barrel_Add", col_ops), collection("Barrel_Cut", col_ops)
    bm = bmesh.new()
    slab(bm, [(BREECH + 0.15, -14.05), (HINGE[0] + EAR_R, -14.05), (HINGE[0] + EAR_R, -10.9), (BREECH + 0.15, -10.9)], -T_MAIN + 0.1, T_MAIN - 0.1)
    bevel(operand("Barrel_Saddle", bm, b_add, barrel), 0.4, 2)
    ear = clean([(HINGE[0] - EAR_R, -10.6), (HINGE[0] + EAR_R, -10.6)] + arc(HINGE[0], HINGE[1], EAR_R, 0, -180, 16))
    for sign, tag in ((1.0, "L"), (-1.0, "R")):                     # ушки шарнира охватывают коробку снаружи
        bm = bmesh.new()
        slab(bm, ear, sign * (T_MAIN + 0.05), sign * (T_MAIN + 1.7))
        bevel(operand("Barrel_HingeEar_" + tag, bm, b_add, barrel), 0.45, 2)
    bm = bmesh.new()
    slab(bm, [(BREECH + 0.3, 13.3), (LEN - 4.5, 13.3), (LEN - 6.5, 14.95), (BREECH + 0.3, 14.95)], -2.5, 2.5)
    bevel(operand("Barrel_SightRib", bm, b_add, barrel), 0.3, 2)
    bm = bmesh.new()
    cyl_x(bm, HINGE[0], HINGE[1], 2.3, -T_MAIN - 4.0, T_MAIN + 4.0)
    operand("Barrel_HingeHole", bm, b_cut, barrel)
    # таблички на трубе: полоса чуть большего радиуса, обрезанная по скруглённому прямоугольнику
    (pa, pb) = PROF["barrel_plate"]
    pu0, pu1 = min(pa[0], pb[0]), max(pa[0], pb[0])
    a_lo, a_hi = math.asin(min(pa[1], pb[1]) / R_OUT), math.asin(max(pa[1], pb[1]) / R_OUT)
    a_mid, half_w = (a_lo + a_hi) / 2.0, R_OUT * math.sin((a_hi - a_lo) / 2.0)
    for sign, tag in ((1.0, "L"), (-1.0, "R")):
        d = Vector((sign * math.cos(a_mid), math.sin(a_mid)))        # (x, v) от оси наружу
        t = Vector((-sign * math.sin(a_mid), math.cos(a_mid)))
        for kind, inset, r0, r1, col in (("Plate", 0.0, R_OUT - 0.6, R_OUT + 0.45, b_add), ("PlateField", 0.8, R_OUT + 0.22, R_OUT + 2.0, b_cut)):
            bm = bmesh.new()
            lathe(bm, [(pu0 - 3.0, r0), (pu1 + 3.0, r0), (pu1 + 3.0, r1), (pu0 - 3.0, r1)])
            shell = operand(f"Barrel_{kind}_{tag}", bm, col, barrel)
            bm = bmesh.new()
            outline = rrect(pu0 + inset, -half_w + inset, pu1 - inset, half_w - inset, half_w - inset - 0.05, 8)
            slab3(bm, [P(u, w * t.y + 8.0 * d.y, w * t.x + 8.0 * d.x) for u, w in outline], Vector((d.x, 0.0, d.y)) * 14.0 * MM)
            cutter = operand(f"Barrel_{kind}Outline_{tag}", bm, col_ops, barrel)
            boolean(shell, "Обрезка", "INTERSECT", other=cutter)
    boolean(barrel, "Наплывы", "UNION", col=b_add)
    boolean(barrel, "Вырезы", "DIFFERENCE", col=b_cut)
    smooth(barrel)
    for name, u in (("Muzzle", LEN), ("Chamber", BREECH)):
        e = bpy.data.objects.new(name, None)
        scene.collection.objects.link(e)
        e.empty_display_size = 0.008
        e.parent = barrel
        e.location = P(u, 0.0) - barrel.location

    # ------------------------------------------------------------ курок и боёк
    bm = bmesh.new()
    slab(bm, ham_r, -3.0, 3.0)
    hammer = make("Hammer", bm, M_STEEL, parent=gun, origin=P(*HPIV))
    bevel(hammer, 0.7, 3)
    h_add, h_cut = collection("Hammer_Add", col_ops), collection("Hammer_Cut", col_ops)
    spur_c = clip_half(ham_c, 1.0, 0.0, -40.5)
    bm = bmesh.new()
    slab(bm, [rot(p, HPIV, -cock) for p in spur_c], -4.6, 4.6)
    bevel(operand("Hammer_Spur", bm, h_add, hammer), 0.9, 3)
    u_lo, u_hi = min(p[0] for p in spur_c) + 3.0, max(p[0] for p in spur_c) - 5.0
    k = 0
    u = u_lo
    while u <= u_hi:                                                 # насечка под большой палец
        top = top_at(spur_c, u)
        groove = [rot(q, HPIV, -cock) for q in ((u - 0.22, top - 0.38), (u + 0.22, top - 0.38), (u + 0.55, top + 0.5), (u - 0.55, top + 0.5))]
        bm = bmesh.new()
        slab(bm, groove, -6.0, 6.0)
        operand(f"Hammer_Groove{k}", bm, h_cut, hammer)
        u += 1.35
        k += 1
    boolean(hammer, "Спица", "UNION", col=h_add)
    boolean(hammer, "Насечка", "DIFFERENCE", col=h_cut)
    smooth(hammer)
    aim = Vector((tip_r[0] - HPIV[0], tip_r[1] - HPIV[1]))
    aim = Vector(rot((aim.x, aim.y), (0.0, 0.0), 90.0 - 15.0)) .normalized()   # боёк смотрит вперёд и чуть вниз
    pin_dir = (math.cos(math.radians(-13.0)), math.sin(math.radians(-13.0)))
    pin_base = (tip_r[0] - pin_dir[0] * 8.1, tip_r[1] - pin_dir[1] * 8.1)
    bm = bmesh.new()
    lathe(bm, [(-2.0, 1.55), (2.2, 1.55), (2.9, 1.2), (7.3, 0.5), (8.1, 0.32)], closed=False, seg=20, caps=(True, True), origin=pin_base, direction=pin_dir)
    make("FiringPin", bm, M_BRIGHT, parent=hammer)

    # ------------------------------------------------------------ спуск, оси, защёлки
    bm = bmesh.new()
    slab(bm, trig, -2.4, 2.4)
    trigger = make("Trigger", bm, M_STEEL, parent=gun, origin=P(*TPIV))
    bevel(trigger, 0.8, 3)
    smooth(trigger)

    bm = bmesh.new()
    for pin, half in ((HPIV, T_MAIN - 0.1), (TPIV, T_MAIN - 0.1), (HINGE, T_MAIN + 1.2)):
        cyl_x(bm, pin[0], pin[1], 2.12, -half, half, 24)
    pins = make("Pins", bm, M_STEEL, parent=gun)
    bevel(pins, 0.3, 2)
    smooth(pins)

    for sign, tag in ((1.0, "L"), (-1.0, "R")):
        ang = math.radians(10.0)
        d = Vector((sign * math.cos(ang), math.sin(ang)))            # (x, v) от оси наружу
        t = Vector((-sign * math.sin(ang), math.cos(ang)))
        top = SHIELD_HALF / math.cos(ang) + 0.12                     # над боковой гранью щитка
        low = R_OUT + 0.12                                           # на трубе ствола
        outer = [(SHIELD_U - 0.9, 12.2), (SHIELD_U - 0.9, top + 0.8), (0.7, top + 0.8), (1.6, low + 0.8), (4.6, low + 0.8), (5.5, low + 1.7)]
        inner = [(5.1, low + 1.0), (4.3, low), (1.9, low), (1.0, top), (SHIELD_U - 0.1, top), (SHIELD_U - 0.1, 12.2)]
        bm = bmesh.new()
        slab3(bm, [P(u, r * d.y - 2.5 * t.y, r * d.x - 2.5 * t.x) for u, r in outer + inner], Vector((t.x, 0.0, t.y)) * 5.0 * MM)
        latch = make("BarrelLatch_" + tag, bm, M_BRIGHT, parent=gun, origin=P(SHIELD_U - 0.5, top * d.y, top * d.x))
        bevel(latch, 0.2, 2)
        smooth(latch)

    # ------------------------------------------------------------ накладки и винт
    for sign, tag in ((1.0, "L"), (-1.0, "R")):
        bm = bmesh.new()
        slab(bm, PROF["pad"], sign * (PAD_FLOOR + 0.05), sign * (T_MAIN + PAD_PROUD + 1.5))
        pad = make("GripPad_" + tag, bm, M_GRIP, parent=gun)
        boolean(pad, "По скруглению рукоятки", "INTERSECT", other=envelope)
        bevel(pad, 0.45, 3, 30.0)
        smooth(pad)
    su, sv = PROF["pad_screw"]
    bm = bmesh.new()
    cyl_x(bm, su, sv, 3.0, -(T_MAIN + PAD_PROUD - 0.1), -(T_MAIN + PAD_PROUD + 1.2))
    cyl_x(bm, su, sv, 2.3, T_MAIN + PAD_PROUD - 0.1, T_MAIN + PAD_PROUD + 0.45)
    screws = make("GripScrews", bm, M_BRIGHT, parent=gun)
    bevel(screws, 0.55, 3)
    s_cut = collection("Screw_Cut", col_ops)
    for i, a in enumerate((35.0, 125.0)):                            # крестовой шлиц
        box = [rot(q, (su, sv), a) for q in ((su - 1.9, sv - 0.38), (su + 1.9, sv - 0.38), (su + 1.9, sv + 0.38), (su - 1.9, sv + 0.38))]
        bm = bmesh.new()
        slab(bm, box, -(T_MAIN + PAD_PROUD + 0.5), -(T_MAIN + PAD_PROUD + 2.2))
        operand(f"Screw_Slot{i}", bm, s_cut, screws)
    boolean(screws, "Шлиц", "DIFFERENCE", col=s_cut)
    smooth(screws)

    # ------------------------------------------------------------ патроны 12-го калибра
    def cartridge(name: str, hull_mat, at: Vector):
        """Сигнальный патрон одной деталью: латунное донце с закраиной и капсюлем, пластиковая гильза, закатка и пыж.
        Начало — центр донца, ось — к дулу (−Y)."""
        prof = [(0.12, 2.9, 0), (0.4, 3.0, 0), (0.4, 3.18, 0), (0.0, 3.3, 0), (0.0, 10.4, 0), (0.12, 10.95, 0), (0.4, 11.2, 0), (1.2, 11.2, 0),
                (1.5, 10.95, 0), (1.5, 10.2, 0), (2.0, 10.15, 0), (10.4, 10.15, 0), (10.7, 9.97, 0), (11.0, 10.15, 0), (12.0, 10.15, 0),
                (12.0, 10.08, 1), (56.6, 10.08, 1), (58.2, 9.85, 1), (59.3, 9.2, 1), (59.6, 8.5, 1), (59.2, 8.0, 1), (58.2, 7.95, 1), (57.6, 8.2, 2)]
        b2 = bmesh.new()
        lathe(b2, [(t, r) for t, r, _ in prof], closed=False, seg=36, caps=(True, True), mats=[m for _, _, m in prof])
        ob = make(name, b2, [M_BRASS, hull_mat, M_WAD])
        ob.data.transform(Matrix.Translation(-P(0.0, 0.0)))
        ob.location = at
        smooth(ob)
        return ob

    cartridge("Flare_Red_Claude", M_RED, Vector((0.10, 0.02, -0.03)))
    cartridge("Flare_Green_Claude", M_GREEN, Vector((0.14, 0.02, -0.03)))

    for col in (f_add, f_cut, b_add, b_cut, h_add, h_cut, s_cut, col_ops):
        col.hide_render = True
    for ob in col_ops.all_objects:
        ob.hide_set(True)

    gun["cock_deg"] = round(cock, 2)
    gun["open_deg"] = OPEN_DEG
    txt = bpy.data.texts.new("Как устроено")
    txt.from_string(__doc__ + f"\nВзвод курка: Hammer, поворот вокруг своей X на −{cock:.1f}°. Перелом: Barrel, +{OPEN_DEG:.0f}° вокруг своей X.\n"
                    "Спуск: Trigger, до +14° вокруг своей X. Наплывы и вырезы — скрытые объекты в коллекции «Вспомогательные».\n")
    SRC.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(EDIT_FILE))
    print("FLARE edit saved; cock", round(cock, 2), flush=True)

    # ------------------------------------------------------------ игровая копия: модификаторы, развёртка
    for ob in col_ops.all_objects:
        ob.hide_set(False)
    parts = [o for o in scene.objects if o.type == "MESH" and o.name not in col_ops.all_objects]
    for ob in parts:
        bpy.context.view_layer.objects.active = ob
        for mod in list(ob.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for ob in list(col_ops.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    pin_ob = bpy.data.objects["FiringPin"]
    pin_ob.select_set(True)
    hammer.select_set(True)
    bpy.context.view_layer.objects.active = hammer
    bpy.ops.object.join()
    parts = [o for o in scene.objects if o.type == "MESH"]
    for ob in parts:
        if len(ob.data.polygons) == 0:
            raise RuntimeError(f"после применения модификаторов деталь {ob.name} пуста")
    groups: dict = {}
    for ob in parts:
        key = ob.name if ob.name.startswith("Flare_") else ob.data.materials[0].name
        groups.setdefault(key, []).append(ob)
    for group in groups.values():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in group:
            ob.select_set(True)
            if not ob.data.uv_layers:
                ob.data.uv_layers.new(name="UVMap")
        bpy.context.view_layer.objects.active = group[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, area_weight=0.0, scale_to_bounds=False)
        bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")

    audit: dict = {"units": "m", "axes": "muzzle -Y, up +Z, +X shooter's left; origin = grip centre", "parts": {}}
    lo, hi = Vector((9, 9, 9)), Vector((-9, -9, -9))
    bpy.context.view_layer.update()
    for ob in parts:
        me = ob.data
        me.calc_loop_triangles()
        bm = bmesh.new()
        bm.from_mesh(me)
        open_edges = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        bm.free()
        uvs = [d.uv for d in me.uv_layers[0].data]
        audit["parts"][ob.name] = {"tris": len(me.loop_triangles), "materials": [m.name for m in me.materials], "open_or_shared_edges": open_edges,
                                   "uv_in_0_1": all(-1e-4 <= c <= 1.0001 for uv in uvs for c in uv)}
        if not ob.name.startswith("Flare_"):
            for v in me.vertices:
                w = ob.matrix_world @ v.co
                lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    audit["gun_size_mm_hammer_down"] = {"width_x": round((hi.x - lo.x) * 1000, 1), "length_y": round((hi.y - lo.y) * 1000, 1), "height_z": round((hi.z - lo.z) * 1000, 1)}
    audit["gun_tris"] = sum(p["tris"] for n, p in audit["parts"].items() if not n.startswith("Flare_"))
    audit["cartridge_tris"] = audit["parts"]["Flare_Red_Claude"]["tris"]
    audit["cartridge_mm"] = {"length": 59.6, "hull": 20.16, "rim": 22.4}
    audit["barrel_mm"] = {"outer": R_OUT * 2, "bore": R_BORE * 2, "length": round(LEN, 1)}
    audit["cock_deg"] = round(cock, 2)
    audit["open_deg"] = OPEN_DEG
    (SRC / "asset-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print("FLARE audit", audit["gun_size_mm_hammer_down"], "tris", audit["gun_tris"], "cartridge", audit["cartridge_tris"], flush=True)
    for n, p in audit["parts"].items():
        print("  ", n, p["tris"], "open", p["open_or_shared_edges"], "uv", p["uv_in_0_1"], flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(GAME_FILE))

    OUT.mkdir(parents=True, exist_ok=True)

    def export(root, name: str) -> None:
        keep = root.location.copy()
        root.location = Vector((0, 0, 0))
        bpy.ops.object.select_all(action="DESELECT")
        stack = [root]
        while stack:
            ob = stack.pop()
            ob.select_set(True)
            stack.extend(ob.children)
        bpy.ops.export_scene.gltf(filepath=str(OUT / name), export_format="GLB", use_selection=True, export_yup=True,
                                  export_apply=True, export_animations=False, export_tangents=True)
        root.location = keep

    export(gun, "flare_gun_claude.glb")
    export(bpy.data.objects["Flare_Red_Claude"], "flare_red_claude.glb")
    export(bpy.data.objects["Flare_Green_Claude"], "flare_green_claude.glb")
    print("FLARE build done", flush=True)


# ================================================================ превью

def render() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(GAME_FILE))
    scene = bpy.context.scene
    gun = bpy.data.objects["FlareGun_Claude"]
    barrel, hammer = bpy.data.objects["Barrel"], bpy.data.objects["Hammer"]
    red, green = bpy.data.objects["Flare_Red_Claude"], bpy.data.objects["Flare_Green_Claude"]
    cock = float(gun["cock_deg"])
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 72
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    break
            except TypeError:
                continue
    except Exception as exc:                                         # нет видеокарты — считаем процессором
        print("FLARE gpu off:", exc, flush=True)
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Просмотр")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.74, 0.75, 0.77, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    scene.world = world

    def area(name: str, loc: tuple, size: float, energy: float, target: Vector) -> None:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.size = size
        light.data.energy = energy
        light.location = loc
        z = (Vector(loc) - target).normalized()
        x = Vector((0, 0, 1)).cross(z).normalized()
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = Vector(loc)
        light.matrix_world = m
        scene.collection.objects.link(light)

    centre = Vector((0.0, -0.052, 0.012))
    area("Ключ", (0.5, -0.55, 0.75), 0.7, 20.0, centre)
    area("Ключ справа", (-0.6, -0.4, 0.6), 0.7, 16.0, centre)
    area("Контур", (0.1, 0.7, 0.5), 0.5, 12.0, centre)
    area("Снизу", (0.0, -0.2, -0.6), 0.8, 5.0, centre)
    cam = bpy.data.objects.new("Камера", bpy.data.cameras.new("Камера"))
    cam.data.clip_start = 0.01
    scene.collection.objects.link(cam)
    scene.camera = cam
    view = SRC / "Просмотр"
    view.mkdir(exist_ok=True)
    if not os.environ.get("FLARE_SHOTS"):
        for old in view.glob("*.png"):
            old.unlink()

    only = [k for k in os.environ.get("FLARE_SHOTS", "").split(",") if k]      # FLARE_SHOTS=01,04 — только эти кадры

    def shot(name: str, offset: tuple, target: Vector, ortho: float = 0.0, lens: float = 90.0) -> None:
        if only and not any(name.startswith(k) for k in only):
            return
        off = Vector(offset)
        cam.data.type = "ORTHO" if ortho > 0.0 else "PERSP"
        cam.data.ortho_scale = ortho
        cam.data.lens = lens
        z = off.normalized()
        up = Vector((0, 0, 1)) if abs(z.z) < 0.98 else Vector((1, 0, 0))
        x = up.cross(z).normalized()
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = target + off
        cam.matrix_world = m
        scene.render.filepath = str(view / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        print("FLARE shot", name, flush=True)

    for ob in (red, green):
        ob.hide_render = True

    # сверка с фото: тот же ракурс и масштаб, курок взведён
    s, w, h = float(PROF["scale_mm_per_px"]), 1024, 768
    hammer.rotation_euler = (math.radians(-cock), 0, 0)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.film_transparent = True
    shot("_overlay", (-0.6, 0, 0), P((w / 2 - float(PROF["breech_x_px"])) * s, (float(PROF["axis_y_px"]) - h / 2) * s), ortho=w * s * MM)
    scene.render.film_transparent = False
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    shot("01_sprava_kurok_vzveden", (-0.6, 0, 0), centre, ortho=0.25)
    hammer.rotation_euler = (0, 0, 0)
    shot("02_sprava", (-0.6, 0, 0), centre + Vector((0, 0, 0.006)), ortho=0.25)
    shot("03_sleva", (0.6, 0, 0), centre + Vector((0, 0, 0.006)), ortho=0.25)
    shot("04_tri_chetverti_speredi", (0.42, -0.5, 0.2), centre)
    shot("05_tri_chetverti_szadi", (-0.36, 0.5, 0.26), centre)
    shot("06_sverhu", (0.0, 0.0, 0.7), centre, ortho=0.25)
    shot("07_szadi", (0.0, 0.6, 0.0), centre + Vector((0, 0, 0.006)), ortho=0.22)
    shot("08_speredi", (0.0, -0.6, 0.0), centre + Vector((0, 0, 0.006)), ortho=0.22)
    shot("09_snizu_speredi", (-0.34, -0.48, -0.3), centre)
    shot("10_kazennik_krupno", (-0.2, 0.12, 0.13), P(-14.0, 2.0), lens=110.0)
    shot("11_rukoyat_krupno", (-0.3, 0.05, -0.02), P(-60.0, -58.0), lens=110.0)
    shot("11a_rukoyat_szadi", (-0.2, 0.34, -0.04), P(-70.0, -60.0), lens=110.0)
    shot("11b_rukoyat_snizu_speredi", (0.2, -0.26, -0.26), P(-58.0, -62.0), lens=110.0)
    # открыт, патрон в патроннике наполовину, второй рядом
    barrel.rotation_euler = (math.radians(OPEN_DEG), 0, 0)
    hammer.rotation_euler = (math.radians(-cock), 0, 0)
    bpy.context.view_layer.update()
    chamber = bpy.data.objects["Chamber"]
    red.hide_render = False
    green.hide_render = False
    red.matrix_world = barrel.matrix_world @ Matrix.Translation(chamber.location + Vector((0.0, 0.026, 0.0)))
    green.matrix_world = Matrix.Translation(Vector((-0.02, -0.118, -0.062))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    shot("12_otkryt_s_patronom", (-0.42, 0.42, 0.3), centre + Vector((0, 0.0, 0.01)))
    shot("13_otkryt_sprava", (-0.6, 0, 0), centre + Vector((0, 0, 0.012)), ortho=0.27)
    # патроны
    barrel.rotation_euler = (0, 0, 0)
    hammer.rotation_euler = (0, 0, 0)
    for ob in gun.children_recursive:
        ob.hide_render = True
    scene.view_settings.view_transform = "Standard"                  # цвет патронов и эскиз окраски — без приглушения
    scene.view_settings.exposure = -0.9
    red.matrix_world = Matrix.Translation(Vector((-0.016, 0.0, 0.0))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    green.matrix_world = Matrix.Translation(Vector((0.016, 0.0, 0.0))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    shot("14_patrony", (0.16, -0.36, 0.16), Vector((0, 0, 0.03)), lens=100.0)
    red.matrix_world = Matrix.Translation(Vector((-0.016, 0.0, 0.06))) @ Matrix.Rotation(math.radians(90), 4, "X")
    green.matrix_world = Matrix.Translation(Vector((0.016, 0.0, 0.06))) @ Matrix.Rotation(math.radians(90), 4, "X")
    shot("15_patrony_dontsa", (0.16, -0.36, 0.2), Vector((0, 0, 0.03)), lens=100.0)
    # цветовой эскиз (не текстура): красная матовая краска, как задумано на этап текстур
    for ob in gun.children_recursive:
        ob.hide_render = False
    red.hide_render = True
    green.hide_render = True
    body = bpy.data.materials["FlareGun_Body_Metal"].node_tree.nodes["Principled BSDF"]
    body.inputs["Base Color"].default_value = (0.5, 0.018, 0.014, 1.0)
    body.inputs["Metallic"].default_value = 0.0
    body.inputs["Roughness"].default_value = 0.66
    shot("16_eskiz_cveta_sprava", (-0.6, 0, 0), centre + Vector((0, 0, 0.006)), ortho=0.25)
    shot("17_eskiz_cveta_tri_chetverti", (0.42, -0.5, 0.2), centre)
    print("FLARE render done", flush=True)


if MODE == "render":
    render()
else:
    build()
