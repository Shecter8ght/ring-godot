# AR-15: технические надписи гравировкой (булево вычитание текста, глубина 0.12–0.15 мм) — положения переводчика
# с обеих сторон; название «ГРАНЬ-15» (владелец, 2026-10-29), калибр и вымышленный номер на панели шахты слева; название
# крупно на ровном поле верхнего ресивера слева. Шрифт — Arial Bold, как у клейм ВСС-М; смещение контура (утолщение)
# не применять — буквы с ним перекрываются, и булево вычитание ломает деталь.
import bpy
from mathutils import Matrix, Vector
from lib import MM, SELECTOR, LOWER_HALF_W, boolean
from part_lower import FCG_HALF_W

FONT = "C:/Windows/Fonts/arialbd.ttf"   # жирный без перекрытых контуров (как клейма ВСС-М); встроенный Inter даёт сбой на кириллице
NAME = "ГРАНЬ-15"
SERIAL = "SN 24-0731"          # вымышленный номер
CALIBER = "CAL 5.56 NATO"


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
    import lib
    if not getattr(lib, "MARKINGS_GEOMETRY", False):
        print("STAMPS_SKIPPED надписи — на этапе текстур (lib.MARKINGS_GEOMETRY)")
        return {}
    C = ctx["coll"]["Lower"]
    lower = bpy.data.objects["Lower_receiver"]
    sx, sz = SELECTOR
    # положения переводчика (флажок: вперёд — предохранитель, вверх — одиночный, назад — автоматический)
    for side in (1, -1):
        y = FCG_HALF_W * side
        n = (0, side, 0)
        stamp(lower, "SAFE", 2.3, (sx + 18.0, y, sz), n, (0, 0, 1), 0.25, C)
        stamp(lower, "SEMI", 2.1, (sx, y, sz + 9.0), n, (0, 0, 1), 0.25, C)
        stamp(lower, "AUTO", 2.3, (sx - 18.0, y, sz), n, (0, 0, 1), 0.25, C)
    # калибр и номер — на панели шахты слева (панель утоплена на 0.8 мм); верх панели — под название
    panel_y = LOWER_HALF_W - 0.8
    px = -22.3
    stamp(lower, NAME, 4.6, (px, panel_y, -30.5), (0, 1, 0), (0, 0, 1), 0.3, C)
    stamp(lower, CALIBER, 2.4, (px, panel_y, -38.0), (0, 1, 0), (0, 0, 1), 0.25, C)
    stamp(lower, SERIAL, 2.4, (px, panel_y, -43.0), (0, 1, 0), (0, 0, 1), 0.25, C)
    from lib import renormal
    renormal(lower)
    # верхний ресивер: название на ровном поле слева (над затворной задержкой, перед карманами)
    upper = bpy.data.objects["Upper_receiver"]
    from part_upper import STEP
    from lib import UPPER_HALF_W
    stamp(upper, NAME, 6.0, (-52.0, UPPER_HALF_W - STEP, 9.6), (0, 1, 0), (0, 0, 1), 0.3, bpy.data.collections["Upper"])
    renormal(upper)
    # цевьё: знак на левой задней грани (между стяжками и первым пазом M-LOK)
    hg = bpy.data.objects.get("Handguard")
    if hg is not None:
        from lib import HG_HALF_W
        stamp(hg, "ГРАНЬ", 5.0, (46.0, HG_HALF_W, 0.5), (0, 1, 0), (0, 0, 1), 0.3, bpy.data.collections["Handguard"])
        renormal(hg)
    return {}
