# AR-15: технические надписи гравировкой (булево вычитание текста, глубина 0.12–0.15 мм) — положения переводчика
# с обеих сторон, калибр и вымышленный номер на панели шахты слева. Название модели и знак марки — после решения
# владельца (место — верх той же панели и панель справа). Шрифт — встроенный в Blender (свободная лицензия).
import bpy
from mathutils import Matrix, Vector
from lib import MM, SELECTOR, LOWER_HALF_W, boolean
from part_lower import FCG_HALF_W

SERIAL = "SN 24-0731"          # вымышленный номер
CALIBER = "CAL 5.56 NATO"


def text_cutter(text, size_mm, depth_mm, coll):
    cu = bpy.data.curves.new("_stamp", "FONT")
    cu.body = text
    cu.size = size_mm * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = depth_mm * MM
    cu.resolution_u = 4
    o = bpy.data.objects.new("_stamp", cu)
    coll.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    ob = bpy.data.objects.new("_stampm", me)
    coll.objects.link(ob)
    return ob


def stamp(target, text, size, center, normal, up, depth, coll):
    """Текст в плоскости, перпендикулярной normal (наружу), вверх — up; center — точка на поверхности (мм)."""
    cut = text_cutter(text, size, depth + 0.6, coll)
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(center) * MM + n * (0.6 * MM)
    # переводим в локальные координаты детали (у детали может быть родитель)
    cut.data.transform(target.matrix_world.inverted() @ m)
    boolean(target, cut)


def build(ctx):
    C = ctx["coll"]["Lower"]
    lower = bpy.data.objects["Lower_receiver"]
    sx, sz = SELECTOR
    # положения переводчика (флажок: вперёд — предохранитель, вверх — одиночный, назад — автоматический)
    for side in (1, -1):
        y = FCG_HALF_W * side
        n = (0, side, 0)
        stamp(lower, "SAFE", 2.3, (sx + 18.0, y, sz), n, (0, 0, 1), 0.14, C)
        stamp(lower, "SEMI", 2.1, (sx, y, sz + 9.0), n, (0, 0, 1), 0.14, C)
        stamp(lower, "AUTO", 2.3, (sx - 18.0, y, sz), n, (0, 0, 1), 0.14, C)
    # калибр и номер — на панели шахты слева (панель утоплена на 0.8 мм); верх панели — под название
    panel_y = LOWER_HALF_W - 0.8
    stamp(lower, CALIBER, 2.5, (-18.8, panel_y, -40.0), (0, 1, 0), (0, 0, 1), 0.15, C)
    stamp(lower, SERIAL, 2.5, (-18.8, panel_y, -45.2), (0, 1, 0), (0, 0, 1), 0.15, C)
    from lib import renormal
    renormal(lower)
    return {}
