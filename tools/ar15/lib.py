# AR-15 «Fab-сборка»: общие помощники построения (взяты из ВСС-М v8) и размеры. Все размеры в мм, в Blender — метры.
# Оси: +X к дулу, +Z вверх, −Y — правая сторона стрелка (окно выброса). Начало — зеркало затвора в положении
# «заперто» на оси канала. Положения осей и деталей ресиверов сняты с фото PEO Soldier (M4, правая сторона,
# выровнено, 4.55 пикс/мм по шагу планки), см. asset-state.md; формы ресиверов — «фрезерованные» в манере листинга Fab.
import math
import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001
BORE_Z = 0.0
# надписи и знаки — на этапе текстур (карта высоты/нормалей + заливка): в геометрию не режутся (владелец, 2026-10-29).
# True — вернуть гравировку/литьё в сетку (булевы; у шрифтов бывают незамкнутые контуры — проверять топологию)
MARKINGS_GEOMETRY = False

# ---------- ресиверы (фото PEO, сдвиг +20 мм: зеркало затвора 20 мм позади заднего торца гайки ствола) ----------
UPPER_FRONT = 20.0        # передний торец корпуса верхнего ресивера (дальше — гайка цевья)
UPPER_REAR = -176.0       # задний торец верхнего ресивера
RAIL_TOP = 31.0           # верх зубьев планки над осью канала
SPLIT_Z = -17.0           # плоскость разъёма верхнего и нижнего ресиверов (у оси сборки)
REAR_TOP_Z = -8.6         # за шахтой боковины нижнего поднимаются до этой высоты (фото PEO)
STEP_X = -90.0            # где линия разъёма поднимается (скругление STEP_R)
STEP_R = 6.0
UPPER_HALF_W = 15.0       # полуширина корпуса верхнего ресивера (≈1.18″ по типовым)
RAIL_HALF_W = 10.6        # полуширина планки MIL-STD-1913 (21.2 мм)
LOWER_HALF_W = 15.5       # полуширина нижнего ресивера у шахты магазина
LOWER_REAR = -182.0       # задний торец башни буферной трубки
PIVOT_PIN = (17.8, -15.2)       # ось сборки (x, z)
TAKEDOWN_PIN = (-150.3, -15.6)  # ось разборки
AUTOSEAR_PIN = (-129.0, -12.5)
SELECTOR = (-129.9, -26.2)
TRIGGER_PIN = (-99.1, -31.0)
HAMMER_PIN = (-78.7, -23.5)
MAG_BUTTON = (-62.4, -26.2)
PORT_X = (-74.2, 10.4)    # окно выброса (крышка) по X
PORT_Z = (1.3, 17.8)
GUARD_X = (-113.6, -60.9) # проём спусковой скобы 52.7 × 21.3 (фото PEO, увеличенный кадр; у прежней модели Opus 50 × 21.6)
GUARD_Z = (-71.4, -50.1)  # верх проёма — низ ресивера над спуском
MAGWELL_FRONT = 10.8      # передняя грань шахты над раструбом (раструб внизу выходит до 15.1)
GRIP_TOP_FRONT = (-156.9, -41.5)
BUFFER_R = 29.16 / 2      # буферная трубка mil-spec
BUFFER_Z = 0.0            # ось трубки = ось канала (рама соосна каналу)
GAS_Z = 16.5              # ось газовой трубки и ключа рамы над осью канала (оценка)
CARRIER_TRAVEL = 91.0     # ход рамы до упора буфера (≈3.6″, оценка)
BOLT_UNLOCK = 9.5         # ход рамы, за который затвор поворачивается (кулачковый паз), оценка
BOLT_FREE = 3.0           # свободный ход рамы до начала поворота
BOLT_ROT = 22.5           # поворот затвора при отпирании, град
# досылатель (справа сзади): ось от торца ресивера вперёд-внутрь-вниз к насечкам рамы (фото PEO: кнопка x −172, z 17.8)
FA_S = (-168.13, -16.33, 12.77)    # задний торец корпуса; кнопка почти заподлицо с торцом ресивера (фото PEO)
FA_D = (1.0, 0.1711, -0.0976)     # вперёд, внутрь и вниз к насечкам рамы (50° от верха к правому боку)
FA_R = 8.6               # корпус Ø17.2 у кнопки, к переду сходит «каплей» в бок ресивера
FA_LEN = 53.0            # канал толкателя по оси от заднего торца корпуса
FA_TRAVEL = 4.5

# ---------- ствол и перед (листинг Fab: короткий ствол, длинное M-LOK) ----------
BARREL_LEN = 292.1        # 11.5″ от зеркала затвора
THREAD_X = (278.0, BARREL_LEN)   # резьба 1/2-28 под дульное устройство, Ø12.7; заплечик в 278
BARREL_R_FRONT = 7.95     # Ø0.625″ перед газовым блоком
GAS_BLOCK_X = (184.0, 210.0)
HG_X = (20.8, 286.0)      # цевьё M-LOK (≈10.4″): сзади упирается в торец ресивера
HG_HALF_W = 20.5          # полуширина цевья по боковым граням
HG_BOTTOM = -21.0         # низ цевья
MLOK_PITCH = 40.0         # пазы M-LOK 7 × 32 мм, шаг 40
BRAKE_X = (THREAD_X[0], 340.0)   # дульный тормоз с муфтой под быстросъёмный глушитель
SUPPRESSOR_R = 20.0       # глушитель Ø40
SUPPRESSOR_LEN = 172.0
# ---------- прицелы на планке ----------
REAR_SIGHT_X = -150.0     # центр основания складного целика на планке ресивера
FRONT_SIGHT_X = 268.0     # центр основания складной мушки на планке цевья
# ---------- магазин, приклад, рукоять ----------
MAG_TOP_Z = -5.8          # верх губок магазина: затвор (упоры r7.4) проходит над губками, цепляя закраину верхнего патрона
MAG_X = (-54.4, 7.6)      # магазин в горловине: задняя и передняя стенки (шахта внутри 62.5 × 23.4; замер 15 ресиверов 2.409″ × 0.905″)
MAG_HALF_W = 11.5         # полуширина магазина в горловине
MAG_CATCH_SLOT = (-42.0, -26.0)  # окно защёлки на левой стенке магазина (x, z)
TUBE_X = (-358.0, -176.0)        # буферная трубка (резьба в башне до −176)
STOCK_TRAVEL = 84.0              # ход приклада: 6 положений (5 шагов по 16.8 мм)
GRIP_TOP_Z = -42.0               # площадка рукояти под нижним ресивером (выше низа над спуском — фото PEO)
GRIP_TOP_X = (-184.0, -119.0)    # спереди рукоять упирается в заднее ухо скобы


def v(x, y, z):
    return Vector((x * MM, y * MM, z * MM))


# ---------- коллекции и материалы ----------

def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


_MAT_COLORS = {
    "Alu_anodized": ((0.030, 0.030, 0.032), 0.45, 0.6),     # ресиверы, цевьё, рукоятка заряжания
    "Steel_black": ((0.035, 0.036, 0.038), 0.55, 0.85),      # ствол, оси, мелкие стальные детали
    "Steel_nitride": ((0.045, 0.045, 0.048), 0.40, 0.9),     # затворная группа
    "Steel_bare": ((0.30, 0.30, 0.31), 0.35, 1.0),           # трущиеся места, ударник
    "Polymer": ((0.035, 0.034, 0.033), 0.65, 0.0),           # приклад, рукоять, магазин
    "Rubber": ((0.02, 0.02, 0.02), 0.85, 0.0),
    "Spring_steel": ((0.12, 0.12, 0.13), 0.4, 1.0),
    "Brass": ((0.62, 0.42, 0.16), 0.3, 1.0),
    "Bullet_jacket": ((0.55, 0.30, 0.18), 0.3, 1.0),
    "Glass": ((0.8, 0.85, 0.9), 0.05, 0.0),
}


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        col, rough, metal = _MAT_COLORS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0))
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*col, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*col, 1.0)
    return m


# ---------- 2D-профили ----------

def fillet(points, radii, seg=6):
    """Скругляет углы замкнутого многоугольника. radii — число или список на каждый угол (0 — острый)."""
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
        for k in range(seg + 1):
            aa = a0 + da * k / seg
            out.append((c.x + math.cos(aa) * r_eff, c.y + math.sin(aa) * r_eff))
    return out


def arc_pts(cx, cy, r, a0, a1, seg):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg))) for k in range(seg + 1)]


# ---------- сетки ----------

def _obj(name, me, coll, mat):
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for mm in mat:
                o.data.materials.append(material(mm) if isinstance(mm, str) else mm)
        else:
            o.data.materials.append(material(mat) if isinstance(mat, str) else mat)
    return o


def prism_xz(name, pts, y0, y1, coll, mat=None, smooth=False):
    """Профиль в плоскости XZ (мм), выдавленный по Y от y0 до y1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x, y0, z)) for x, z in pts]
    b = [bm.verts.new(v(x, y1, z)) for x, z in pts]
    n = len(pts)
    bm.faces.new(list(reversed(a)) if y1 > y0 else a)
    bm.faces.new(b if y1 > y0 else list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def prism_xy(name, pts, z0, z1, coll, mat=None):
    """Профиль в плоскости XY (вид сверху), выдавленный по Z."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x, y, z0)) for x, y in pts]
    b = [bm.verts.new(v(x, y, z1)) for x, y in pts]
    n = len(pts)
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def prism_yz(name, pts, x0, x1, coll, mat=None):
    """Профиль в плоскости YZ (поперечное сечение), выдавленный по X."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x0, y, z)) for y, z in pts]
    b = [bm.verts.new(v(x1, y, z)) for y, z in pts]
    n = len(pts)
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def loft_yz(name, sections, coll, mat=None, cap=True, smooth=True):
    """Лофт по X: sections = [(x, [(y,z)...]), ...] — одинаковое число точек в каждом сечении."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, pts in sections:
        rings.append([bm.verts.new(v(x, y, z)) for y, z in pts])
    n = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def lathe(name, prof, coll, mat=None, seg=64, cy=0.0, cz=BORE_Z, smooth=True, closed=True):
    """Тело вращения вокруг оси, параллельной X, через (cy, cz). prof = [(x, r), ...] по контуру.
    closed=True — контур замкнут (последняя точка соединяется с первой)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, r in prof:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new(v(x, cy + r * math.cos(a), cz + r * math.sin(a))))
        rings.append(ring)
    m = len(rings)
    pairs = list(zip(range(m - 1), range(1, m)))
    if closed:
        pairs.append((m - 1, 0))
    for i0, i1 in pairs:
        r0, r1 = rings[i0], rings[i1]
        for k in range(seg):
            j = (k + 1) % seg
            q = (r0[k], r0[j], r1[j], r1[k])
            if len(set(q)) == 4:
                try:
                    bm.faces.new(q)
                except ValueError:
                    pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def cyl(name, x0, x1, r, coll, mat=None, seg=32, cy=0.0, cz=BORE_Z, axis="X", ch=0.0):
    """Цилиндр с фасками ch на торцах. axis — X, Y или Z; для Y/Z x0..x1 — координаты по этой оси, (cy,cz) — центр в двух других."""
    prof = [(x0, 0.0), (x0, r - ch), (x0 + ch, r), (x1 - ch, r), (x1, r - ch), (x1, 0.0)] if ch > 0 else [(x0, 0.0), (x0, r), (x1, r), (x1, 0.0)]
    o = lathe(name, prof, coll, mat, seg, 0.0, 0.0, smooth=True, closed=True)
    if axis == "X":
        o.location = v(0, cy, cz)
    elif axis == "Y":
        o.rotation_euler = (0, 0, math.pi / 2)
        o.location = v(cy, 0, cz)
    elif axis == "Z":
        o.rotation_euler = (0, -math.pi / 2, 0)
        o.location = v(cy, cz, 0)
    apply_transform(o)
    auto_sharp(o, 35)
    return o


def box(name, x0, x1, y0, y1, z0, z1, coll, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vv in bm.verts:
        vv.co.x = (x0 if vv.co.x < 0 else x1) * MM
        vv.co.y = (y0 if vv.co.y < 0 else y1) * MM
        vv.co.z = (z0 if vv.co.z < 0 else z1) * MM
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def apply_transform(o):
    mw = o.matrix_world.copy() if o.parent is None else o.matrix_basis.copy()
    o.data.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)


def auto_sharp(o, deg=35):
    """Плавное затенение с острыми рёбрами по углу (без модификатора)."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0) < math.radians(deg)
        else:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me); bm.free()


# ---------- булевы и фаски ----------

def boolean(target, cutter, op="DIFFERENCE", remove=True, solver="EXACT", self_x=False):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = solver
    if solver == "EXACT" and self_x:
        m.use_self = True
    apply_all(target)
    _drop_empty_slots(target)
    clean(target, 0.002)
    if remove:
        me = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def _drop_empty_slots(o):
    """Грани выреза приходят с пустым слотом материала (у резака его нет) — отдаём их материалу детали."""
    me = o.data
    mats = list(me.materials)
    if not any(m is None for m in mats):
        return
    keep = [i for i, m in enumerate(mats) if m is not None]
    if not keep:
        return
    remap = {old: new for new, old in enumerate(keep)}
    idx = [remap.get(p.material_index, 0) for p in me.polygons]
    new = [mats[i] for i in keep]
    me.materials.clear()
    for m in new:
        me.materials.append(m)
    for p, i in zip(me.polygons, idx):
        p.material_index = i


def apply_all(o):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
    old = o.data
    o.modifiers.clear()
    o.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _bevel_weights(o, angle, exclude):
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    sel = []
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0) < math.radians(angle):
            continue
        if any(exclude(f.calc_center_median() * (1.0 / MM), f.normal) for f in e.link_faces):
            continue
        sel.append(e.index)
    bm.free()
    attr = me.attributes.get("bevel_weight_edge") or me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for i in range(len(me.edges)):
        attr.data[i].value = 0.0
    for i in sel:
        attr.data[i].value = 1.0


def bevel(o, w=0.5, seg=2, angle=30.0, harden=True, profile=0.6, clamp=True, miter="MITER_ARC", exclude=None):
    """Фаска по углу. w — мм. Не применяет: применить через apply_all или finish()."""
    m = o.modifiers.new("bevel", "BEVEL")
    m.width = w * MM
    m.segments = seg
    if exclude is None:
        m.limit_method = "ANGLE"
    else:
        _bevel_weights(o, angle, exclude)
        m.limit_method = "WEIGHT"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.harden_normals = harden
    m.use_clamp_overlap = clamp
    m.miter_outer = miter
    for p in o.data.polygons:
        p.use_smooth = True
    return m


def bevel_edges(o, pick, w=4.0, seg=6, profile=0.5, clamp=False, where=None):
    """Скругление выбранных рёбер радиусом ~w мм: pick(n1, n2) по нормалям двух граней ребра,
    where(середина ребра в мм) — дополнительный отбор по месту; применяется сразу."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.normal_update()
    sel = set()
    for e in bm.edges:
        if len(e.link_faces) == 2:
            n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
            if not (pick(n1, n2) or pick(n2, n1)):
                continue
            if where is not None and not where((e.verts[0].co + e.verts[1].co) * (0.5 / MM)):
                continue
            sel.add(e.index)
    bm.free()
    attr = me.attributes.get("bevel_weight_edge") or me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for i in range(len(me.edges)):
        attr.data[i].value = 1.0 if i in sel else 0.0
    m = o.modifiers.new("bevel_w", "BEVEL")
    m.limit_method = "WEIGHT"
    m.width = w * MM
    m.segments = seg
    m.profile = profile
    m.use_clamp_overlap = clamp          # ограничение по соседним коротким рёбрам скруглений сводило ширину почти к нулю
    m.miter_outer = "MITER_ARC"
    m.harden_normals = False
    apply_all(o)
    a = o.data.attributes.get("bevel_weight_edge")
    if a is not None:
        o.data.attributes.remove(a)
    return len(sel)


def renormal(o):
    """Нормали заново по площадям граней — после булевых по уже готовой (с фаской) сетке: клейма, выштамповка.
    Рёбра круче 40° (буквы, стенки углублений) — жёсткие, полосы фасок остаются гладкими."""
    auto_sharp(o, 40)
    weighted(o)
    apply_all(o)


def weighted(o):
    m = o.modifiers.new("wn", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    m.weight = 50
    return m


def clean(o, dist=0.002):
    """Сварка совпавших вершин и растворение вырожденной геометрии после булевых (dist — мм)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist * MM)
    bmesh.ops.dissolve_degenerate(bm, dist=dist * MM, edges=bm.edges)
    bm.to_mesh(o.data); bm.free()


def _drop_loose(o):
    """Фаска иногда оставляет вершины без граней (в начале координат) — убираем, чтобы не ломать габарит."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.to_mesh(o.data)
    bm.free()


def _bbox(o):
    xs = [v.co for v in o.data.vertices]
    if not xs:
        return None
    return (Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs))),
            Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs))))


def _spots(o, lo, hi):
    """Где фаска разнесла сетку: вершины на месте у граней с улетевшими вершинами (мм, |y| > 15)."""
    bmd = bmesh.new(); bmd.from_mesh(o.data)
    spots = set()
    for vv in bmd.verts:
        if any(c < l - 0.002 or c > h + 0.002 for c, l, h in zip(vv.co, lo, hi)):
            for f in vv.link_faces:
                for q in f.verts:
                    if all(l - 1e-5 <= c <= h + 1e-5 for c, l, h in zip(q.co, lo, hi)):
                        spots.add(tuple(round(c / MM) for c in q.co))
    bmd.free()
    return sorted(spots)[:16]


def finish(o, w=0.5, seg=2, angle=30.0, apply=True, exclude=None):
    """Общая фаска по углу; если на вырожденных рёбрах фаска разносит сетку — повтор с меньшей шириной,
    в крайнем случае сетка без фаски с жёсткими рёбрами по углу."""
    o["_fin"] = 1
    clean(o)
    before = _bbox(o)
    keep = o.data.copy()
    if not apply:
        bevel(o, w, seg, angle, exclude=exclude)
        weighted(o)
        bpy.data.meshes.remove(keep)
        return o
    for k, (ww, tri, mit) in enumerate(((w, False, "MITER_ARC"), (w, False, "MITER_SHARP"), (w, True, "MITER_SHARP"),
                                        (w * 0.6, True, "MITER_SHARP"), (w * 0.35, True, "MITER_SHARP"))):
        if k:
            old = o.data
            o.data = keep.copy()
            bpy.data.meshes.remove(old)
        if tri:
            # большие многоугольники боковин после булевых фаска разносит — режем их на треугольники
            bm = bmesh.new(); bm.from_mesh(o.data)
            big = [f for f in bm.faces if len(f.verts) > 12]
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(o.data); bm.free()
            bevel(o, ww, seg, angle, miter=mit, exclude=exclude)
            apply_all(o)
            # после фаски плоские треугольники снова сливаем в многоугольники — иначе тонкие клинья портят затенение
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.05), verts=bm.verts, edges=bm.edges,
                                     delimit={"NORMAL"})
            bm.to_mesh(o.data); bm.free()
            for p in o.data.polygons:
                p.use_smooth = True
        else:
            bevel(o, ww, seg, angle, miter=mit, exclude=exclude)
        weighted(o)
        apply_all(o)
        _drop_loose(o)
        after = _bbox(o)
        if not (before and after and ((after[0] - before[0]).length > 0.002 or (after[1] - before[1]).length > 0.002)):
            if k:
                print("BEVEL_RETRY", o.name, round(ww, 2), "треугольники" if tri else "")
            bpy.data.meshes.remove(keep)
            return o
        print("BEVEL_FAIL", o.name, round(ww, 2), "места:", _spots(o, *before))
    old = o.data
    o.data = keep
    bpy.data.meshes.remove(old)
    for p in o.data.polygons:
        p.use_smooth = True
    auto_sharp(o, angle)
    print("BEVEL_FALLBACK", o.name)
    return o


def join(objs, name):
    base = objs[0]
    for o in objs[1:]:
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    base.data.transform(base.matrix_world); base.matrix_world = Matrix.Identity(4)
    bm = bmesh.new()
    mats = []
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material not in mats:
                mats.append(s.material)
    for o in objs:
        tmp = bmesh.new(); tmp.from_mesh(o.data)
        remap = {}
        for i, s in enumerate(o.material_slots):
            remap[i] = mats.index(s.material) if s.material in mats else 0
        for f in tmp.faces:
            f.material_index = remap.get(f.material_index, 0)
        me_tmp = bpy.data.meshes.new("tmp"); tmp.to_mesh(me_tmp); tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    coll = base.users_collection[0]
    for o in objs:
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in mats:
        me.materials.append(m)
    return o


# ---------- иерархия ----------

def empty(name, loc_mm, coll, parent=None, size=0.01, kind="PLAIN_AXES"):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    coll.objects.link(e)
    e.location = v(*loc_mm)
    bpy.context.view_layer.update()
    if parent is not None:
        set_parent(e, parent)
    return e


def set_parent(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def set_origin(o, loc_mm):
    """Переносит начало координат объекта в точку (мм, мир) без смещения геометрии."""
    p = v(*loc_mm)
    mw = o.matrix_world.copy()
    local = mw.inverted() @ p
    o.data.transform(Matrix.Translation(-local))
    o.matrix_world = mw @ Matrix.Translation(local)


def tris(o):
    me = o.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)
