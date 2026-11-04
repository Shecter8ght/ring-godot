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
NAME = "ИЗЛОМ-45"               # кандидат названия — до решения владельца (asset-state.md)
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


def stamp(target, text, size, center, normal, up, depth, coll):
    """Текст гравировкой глубиной depth: center — точка на поверхности (мм), normal — наружу, up — верх строки."""
    ZONES.append((tuple(center), size * max(1.0, len(text) * 0.42) + 1.0))
    cut = text_cutter(text, size, depth + 0.6, coll)
    place(cut, center, normal, up, 0.6, target)
    # сетка шрифта не сварена (крышки и стенки букв — отдельными кусками) и буквы перекрываются: сварить, разобрать на
    # буквы (острова), объединить их в один замкнутый резец и вычесть обычным булевым (самопересечения корпуса не трогаем —
    # режим use_self на корпусе ломал сетку у рукояти, проверка v02)
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
    acc = objs[0]
    for ob in objs[1:]:
        boolean(acc, ob, op="UNION")
    # вычитание — до мелкой фаски корпуса (part_receiver.build): по готовой фаске EXACT рвал сетку у рукояти
    boolean(target, acc)
    bpy.data.objects.remove(cut, do_unlink=True)


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
    up = target
    mw = up
    L, R = (0, 1, 0), (0, -1, 0)
    Z = (0, 0, 1)
    # название — слева на переднем блоке (где у прототипа была марка, X 65…95, Z 36…40) и справа над планкой бокового
    stamp(up, NAME, 4.2, (79.0, HALF_W, 38.0), L, Z, 0.3, C)
    stamp(up, NAME, 4.2, (76.0, -HALF_W, 33.0), R, Z, 0.3, C)
    # калибр и номер — справа на задней части коробки над рукоятью
    stamp(up, CALIBER, 2.4, (-190.0, -HALF_W, 37.0), R, Z, 0.25, C)
    stamp(up, SERIAL, 2.4, (-190.0, -HALF_W, 31.5), R, Z, 0.25, C)
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
