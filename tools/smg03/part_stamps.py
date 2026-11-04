# ПП по мотивам KRISS Vector: надписи и знаки выштамповкой в сетке детали (требование владельца 7). Реальные бренды и
# знаки не переносятся: вместо «KRISS» — название ствола (кандидат до решения владельца — NAME), вместо литого «V» в
# треугольнике — свой знак: кольцо с ломаной линией («излом» — ход затвора Super V вниз под углом).
# Шрифт — Arial Bold, как у клейм ВСС-М и AR-15 (встроенный Inter даёт сбой на кириллице).
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from lib import MM, HALF_W, boolean, renormal
from part_controls import SELECTOR_PIVOT, SAFETY_PIVOT

FONT = "C:/Windows/Fonts/arialbd.ttf"
NAME = "ИЗЛОМ-45"               # название принято владельцем 2026-11-04
CALIBER = "КАЛ .45"
SERIAL = "№ 45-0412"            # вымышленный номер


def text_cutter(text, size_mm, depth_mm, coll):
    cu = bpy.data.curves.new("_stamp", "FONT")
    cu.body = text
    f = bpy.data.fonts.get("StampFont")
    if f is None:
        try:
            f = bpy.data.fonts.load(FONT)
            f.name = "StampFont"
        except Exception:
            f = None
    if f is not None:
        cu.font = f
    cu.size = size_mm * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = depth_mm * MM
    cu.resolution_u = 5
    o = bpy.data.objects.new("_stamp", cu)
    coll.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    ob = bpy.data.objects.new("_stampm", me)
    coll.objects.link(ob)
    return ob


def place(cut, center, normal, up, lift, target):
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(center) * MM + n * (lift * MM)
    cut.data.transform(target.matrix_world.inverted() @ m)


ZONES = []                       # (центр мм, радиус мм) — места гравировок: мелкая фаска корпуса их не трогает
FAILED = []                      # надписи, где буква не вырезалась (part_receiver пересобирает корпус и повторяет)


def stamp(target, text, size, center, normal, up, depth, coll):
    """Текст гравировкой глубиной depth: center — точка на поверхности (мм), normal — наружу, up — верх строки."""
    ZONES.append((tuple(center), size * max(1.0, len(text) * 0.42) + 1.0))
    cut = text_cutter(text, size, depth + 0.6, coll)
    place(cut, center, normal, up, 0.6, target)
    # сетка шрифта не сварена (крышки и стенки букв — отдельными кусками): сварить и разобрать на буквы (острова);
    # каждую вычесть обычным булевым (самопересечения корпуса не трогаем — режим use_self ломал сетку у рукояти, v02)
    bm = bmesh.new(); bm.from_mesh(cut.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    islands = []
    left = set(bm.faces)
    while left:
        f0 = left.pop(); grp = {f0}; stack = [f0]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in left:
                        left.discard(g); grp.add(g); stack.append(g)
        islands.append(grp)
    objs = []
    for grp in islands:
        vmap = {}; verts = []; faces = []
        for f in grp:
            idx = []
            for vv in f.verts:
                if vv not in vmap:
                    vmap[vv] = len(verts); verts.append(vv.co.copy())
                idx.append(vmap[vv])
            faces.append(idx)
        me = bpy.data.meshes.new("_ch"); me.from_pydata(verts, [], faces); me.update()
        ob = bpy.data.objects.new("_ch", me); coll.objects.link(ob)
        objs.append(ob)
    bm.free()
    # буквы — по одной: точное вычитание всем резцом сразу на большом корпусе иногда пропускало часть букв («ИЗЛО»
    # не вырезались, 04.11) и оставляло ребро на четыре грани. После каждой буквы — проверка: объём корпуса уменьшился
    # (буква вошла в поверхность) и открытых рёбер не прибавилось; иначе откат и повтор со сдвигом на сотые миллиметра
    import lib as _lib
    along = _along(normal, up)
    upv = Vector(up)
    # попытки: точное булево со сдвигами, точное «с допуском к дырам», быстрое (у точного на большом корпусе бывают
    # сбои от запуска к запуску — буква не вырезается, по краю рёбра на 3–4 грани)
    shifts = [(0.0, 0.0, "EXACT", False), (0.013, 0.007, "EXACT", False), (-0.017, 0.011, "EXACT", False),
              (0.0, 0.0, "EXACT", True), (0.009, -0.019, "EXACT", True), (0.0, 0.0, "FLOAT", False),
              (0.011, 0.013, "FLOAT", False)]
    for ob in objs:
        vol_l = abs(_volume(ob.data))
        keep = target.data.copy()
        v0 = _volume(target.data)
        nm0 = _lib._nonmanifold(target)
        sh0 = _shells(target.data)
        exp = vol_l * depth / (depth + 0.6)          # часть буквы ниже плоской поверхности
        ok = False
        for k, (da, du, solver, tol) in enumerate(shifts):
            if k:
                old = target.data
                target.data = keep.copy()
                bpy.data.meshes.remove(old)
            c2 = ob.copy(); c2.data = ob.data.copy(); coll.objects.link(c2)
            c2.data.transform(Matrix.Translation((along * da + upv * du) * MM))
            boolean(target, c2, solver=solver, hole_tolerant=tol)
            removed = v0 - _volume(target.data)
            if (_lib._nonmanifold(target) <= nm0 and 0.2 * exp < removed < 1.6 * exp
                    and _shells(target.data) <= sh0):
                ok = True
                break
            print("STAMP_RETRY", text, k, round(removed * 1e9, 4), round(vol_l * 1e9, 4), "nm", nm0, _lib._nonmanifold(target))
        if not ok:
            # ни один сдвиг не помог — букву пропускаем, корпус возвращаем как был (испорченный результат дальше ломал
            # все вырезы)
            print("STAMP_FAIL", text)
            FAILED.append(text)
            old = target.data
            target.data = keep
            bpy.data.meshes.remove(old)
        else:
            bpy.data.meshes.remove(keep)
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
    bpy.data.objects.remove(cut, do_unlink=True)


def _shells(me):
    """Число отдельных оболочек (внутренняя лишняя оболочка от сбойного вычитания не меняет числа открытых рёбер)."""
    n = len(me.vertices)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    return len({find(i) for i in range(n)})


def _volume(me):
    """Объём по треугольникам (у корпуса крышки — большие вогнутые многоугольники, веером объём считается неверно)."""
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    vol = bm.calc_volume(signed=True)
    bm.free()
    return vol


def _along(normal, up):
    """Направление вдоль строки (поперёк нормали и верха)."""
    n = Vector(normal); u = Vector(up)
    return u.cross(n).normalized()


def emblem_cutter(r_out, depth, coll):
    """Свой знак в плоскости XY (z — наружу): кольцо и ломаная из трёх отрезков внутри."""
    me = bpy.data.meshes.new("_emb")
    bm = bmesh.new()
    seg = 64
    # кольцо: внешний и внутренний контуры — две трубки сеткой «стенки»
    for (ra, rb) in ((r_out, r_out - 1.4),):
        ring_a = [bm.verts.new(Vector((ra * math.cos(2 * math.pi * k / seg) * MM, ra * math.sin(2 * math.pi * k / seg) * MM, z * MM)))
                  for z in (-depth, 1.0) for k in range(seg)]
        ring_b = [bm.verts.new(Vector((rb * math.cos(2 * math.pi * k / seg) * MM, rb * math.sin(2 * math.pi * k / seg) * MM, z * MM)))
                  for z in (-depth, 1.0) for k in range(seg)]
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((ring_a[k], ring_a[j], ring_a[seg + j], ring_a[seg + k]))
            bm.faces.new((ring_b[seg + k], ring_b[seg + j], ring_b[j], ring_b[k]))
            bm.faces.new((ring_b[k], ring_b[j], ring_a[j], ring_a[k]))
            bm.faces.new((ring_a[seg + k], ring_a[seg + j], ring_b[seg + j], ring_b[seg + k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ring = bpy.data.objects.new("_emb", me)
    coll.objects.link(ring)
    # ломаная — один замкнутый контур (полоса шириной 1.6 вдоль трёх отрезков, углы — на биссектрисах), отдельной
    # оболочкой в том же резце: три перекрывающиеся «пилюли» давали дыры на стыках (проверка v01/v02)
    import math as _m
    pts = [(-r_out * 0.62, -r_out * 0.18), (-r_out * 0.2, r_out * 0.36), (r_out * 0.2, -r_out * 0.36), (r_out * 0.62, r_out * 0.18)]
    hw = 0.8
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a_ = pts[max(i - 1, 0)]; b_ = pts[min(i + 1, len(pts) - 1)]
        if 0 < i < len(pts) - 1:
            d1 = Vector((x - a_[0], y - a_[1], 0)).normalized(); d2 = Vector((b_[0] - x, b_[1] - y, 0)).normalized()
            n1 = Vector((-d1.y, d1.x, 0)); n2 = Vector((-d2.y, d2.x, 0))
            m = (n1 + n2).normalized()
            k = hw / max(0.3, m.dot(n1))
        else:
            d = Vector((b_[0] - a_[0], b_[1] - a_[1], 0)).normalized()
            m = Vector((-d.y, d.x, 0)); k = hw
        left.append((x + m.x * k, y + m.y * k)); right.append((x - m.x * k, y - m.y * k))
    outline = left + list(reversed(right))
    me2 = bpy.data.meshes.new("_zz")
    bm = bmesh.new()
    lo = [bm.verts.new(Vector((x * MM, y * MM, -depth * MM))) for x, y in outline]
    hi = [bm.verts.new(Vector((x * MM, y * MM, 1.0 * MM))) for x, y in outline]
    bm.faces.new(list(reversed(lo))); bm.faces.new(hi)
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.from_mesh(ring.data)
    bm.to_mesh(me2); bm.free()
    old = ring.data
    ring.data = me2
    bpy.data.meshes.remove(old)
    return ring


def build(ctx):
    """Гравировки режутся из part_receiver.build (apply) до мелкой фаски корпуса; здесь ничего не делается."""
    return {}


def apply(target, C):
    import lib
    if not getattr(lib, "MARKINGS_GEOMETRY", False):
        return []
    ZONES.clear()
    FAILED.clear()
    up = target
    mw = up
    L, R = (0, 1, 0), (0, -1, 0)
    Z = (0, 0, 1)
    # название — слева на переднем блоке (где у прототипа была марка, X 65…95, Z 36…40) и справа над планкой бокового
    stamp(up, NAME, 4.2, (79.0, HALF_W, 38.0), L, Z, 0.3, C)
    stamp(up, NAME, 4.2, (76.0, -HALF_W, 33.0), R, Z, 0.3, C)
    # калибр и номер — справа на задней части коробки над рукоятью
    # X −224: под флажком предохранителя (X −197…−180) надпись закрывалась (сверка v04b Н6)
    stamp(up, CALIBER, 2.4, (-224.0, -HALF_W, 37.0), R, Z, 0.25, C)
    stamp(up, SERIAL, 2.4, (-224.0, -HALF_W, 31.5), R, Z, 0.25, C)
    # предохранитель: «П» (предохранение) и «О» (огонь) у хвоста флажка с обеих сторон
    sx, sz = SAFETY_PIVOT
    for nrm, s in ((L, 1), (R, -1)):
        stamp(up, "П", 2.6, (sx - 7.5, s * HALF_W, sz - 9.5), nrm, Z, 0.25, C)
        stamp(up, "О", 2.6, (sx - 15.5, s * HALF_W, sz + 6.0), nrm, Z, 0.25, C)
    # переводчик огня: «ОД», «2», «АВ» по дуге хода флажка (вперёд-вниз), с обеих сторон
    fx, fz = SELECTOR_PIVOT
    for nrm, s in ((L, 1), (R, -1)):
        for txt, a in (("ОД", -8.0), ("2", -38.0), ("АВ", -68.0)):
            r = 17.5
            px = fx + r * math.cos(math.radians(a))
            pz = fz + r * math.sin(math.radians(a))
            tgt = up if pz > lib.SEAM_Z + 2.0 else mw
            stamp(tgt, txt, 2.3, (px, s * HALF_W, pz), nrm, Z, 0.25, C)
    # знак на переднем торце (крышка) — как на боку
    e = emblem_cutter(8.0, 0.45, C)
    place(e, (lib.FRONT_FACE_X, 0.0, 33.0), (1, 0, 0), Z, 0.0, up)
    boolean(up, e)
    ZONES.append(((lib.FRONT_FACE_X, 0.0, 33.0), 9.5))
    # знак на боках корпуса шахты — на месте литого «V» прототипа (X −80, Z −32)
    for nrm, s in ((L, 1), (R, -1)):
        e = emblem_cutter(10.5, 0.45, C)
        place(e, (-80.0, s * HALF_W, -32.0), nrm, Z, 0.0, mw)
        boolean(mw, e)
        ZONES.append(((-80.0, s * HALF_W, -32.0), 12.0))
    return list(ZONES)
