# «Осока»: надписи рельефом в сетке детали — табличка пускового механизма (штамп, вглубь) и литые слова у рычага
# (выпуклые). Взято из tools/smg03/part_stamps.py (ИЗЛОМ-45): буквы по одной, проверка объёма и открытых рёбер,
# повтор со сдвигом на сотые миллиметра. Шрифт — Arial Bold (встроенный Inter даёт сбой на кириллице).
# Реальные индексы не переносятся: вместо «9П521» — вымышленный «ПМ-52» (владелец 2026-11-05: название «Осока»).
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from lib import MM, boolean, renormal

FONT = "C:/Windows/Fonts/arialbd.ttf"


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
EMBLEMS = []                     # (центр мм, радиус мм, оси в плоскости знака) — part_receiver мелко нарезает там сетку


def stamp(target, text, size, center, normal, up, depth, coll, raised=False):
    """Текст гравировкой глубиной depth (raised — выпуклый на depth, литой): center — точка на поверхности (мм),
    normal — наружу, up — верх строки."""
    ZONES.append((tuple(center), size * max(1.0, len(text) * 0.42) + 1.0))
    cut = text_cutter(text, size, depth + 0.6, coll)
    # выдавливание шрифта симметричное (±(depth + 0.6)): гравировка — подъём 0.6, низ буквы на depth под поверхностью;
    # литая выпуклая — опускание на 0.6, верх буквы на depth над поверхностью
    place(cut, center, normal, up, -0.6 if raised else 0.6, target)
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
              (0.011, 0.013, "FLOAT", False), (0.023, -0.029, "EXACT", False), (-0.031, 0.027, "EXACT", True),
              (0.041, 0.037, "EXACT", False), (-0.047, -0.043, "FLOAT", False)]
    if raised:
        # литые выпуклые буквы — всегда вливаются телом в сетку детали (низ утоплен на 0.6 мм, верх на depth над
        # поверхностью): объединение точным булевым на большой боковине литья давало рваные буквы (v03, владелец)
        bm = bmesh.new(); bm.from_mesh(target.data)
        for ob in objs:
            bm.from_mesh(ob.data)
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.meshes.remove(me)
        bm.to_mesh(target.data); bm.free()
        bpy.data.objects.remove(cut, do_unlink=True)
        print("STAMP_RAISED_JOINED", text)
        return
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
            boolean(target, c2, op="UNION" if raised else "DIFFERENCE", solver=solver, hole_tolerant=tol)
            removed = abs(v0 - _volume(target.data))
            if (_lib._nonmanifold(target) <= nm0 and 0.2 * exp < removed < 1.6 * exp
                    and _shells(target.data) <= sh0):
                ok = True
                break
            print("STAMP_RETRY", text, k, round(removed * 1e9, 4), round(vol_l * 1e9, 4), "nm", nm0, _lib._nonmanifold(target))
        if not ok:
            # ни один сдвиг не помог — корпус возвращаем как был (испорченный результат дальше ломал все вырезы)
            old = target.data
            target.data = keep
            bpy.data.meshes.remove(old)
            if raised:
                # литая буква: вливаем её тело в сетку детали — низ утоплен на 0.6 мм в поверхность, верх на depth над
                # ней; висящей буквы и зазора нет, буква — часть детали и двигается с ней
                bm = bmesh.new(); bm.from_mesh(target.data)
                tmp = bpy.data.meshes.new("_tmp"); tmp.from_pydata([], [], []); tmp.update()
                bm.from_mesh(ob.data)
                bm.to_mesh(target.data); bm.free()
                bpy.data.meshes.remove(tmp)
                print("STAMP_JOINED", text)
            else:
                print("STAMP_FAIL", text)
                FAILED.append(text)
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


