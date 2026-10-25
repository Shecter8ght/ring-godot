# ВСС-М v8: выбитые клейма (вымышленный номер, совпадающий на коробке, раме и крышке, как у серийного оружия),
# цифры дистанций на листе прицела. Глубина 0.12–0.15 мм, булево вычитание текста.
import math
import bpy
from mathutils import Matrix, Vector
from lib import MM, boolean

FONT = "C:/Windows/Fonts/arialbd.ttf"
NAME_FONT = "C:/Windows/Fonts/ARIALNB.TTF"      # узкий жирный без перекрытых контуров (у Bahnschrift буквы теряются)
SERIAL = "РН-0731"
SUB = "731-1"
# игровое название винтовки и подпись автора — выштамповка на правой стороне крышки
GAME_NAME = "ШОРОХ-9"
AUTHOR = "by Shecter8ght"


def _font(path=FONT):
    key = "StampFont" if path == FONT else "StampFont_" + path.rsplit("/", 1)[-1]
    f = bpy.data.fonts.get(key)
    if f is None:
        try:
            f = bpy.data.fonts.load(path)
            f.name = key
        except Exception:
            f = None
    return f


def text_cutter(text, size_mm, depth_mm, coll, font=FONT):
    cu = bpy.data.curves.new("_stamp", "FONT")
    cu.body = text
    f = _font(font)
    if f:
        cu.font = f
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
    """Текст лежит в плоскости, перпендикулярной normal (наружу), вверх — up; центр — на поверхности (мм)."""
    cut = text_cutter(text, size, depth + 0.6, coll)
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    # текст выдавлен в обе стороны от z=0 на (depth+0.6): сдвигаем так, чтобы в металл ушло ровно depth
    m.translation = Vector(center) * MM + n * (0.6 * MM)
    cut.data.transform(m)
    boolean(target, cut)


def _place(ob, center, normal, up, lift):
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(center) * MM + n * (lift * MM)
    ob.data.transform(m)


def nameplate(target, coll, center, normal=(0, -1, 0), up=(0, 0, 1)):
    """Выштамповка: углублённое на 0.6 мм поле со скруглёнными углами, в нём выпуклые название (0.5 мм над дном)
    и под ним мелкая подпись автора (0.4 мм). center — середина поля на поверхности детали (мм)."""
    name = text_cutter(GAME_NAME, 8.4, 0.35, coll, NAME_FONT)
    bb = [Vector(c) for c in name.bound_box]
    w = (max(v.x for v in bb) - min(v.x for v in bb)) / MM
    half_w, z0, z1 = w / 2 + 4.0, -8.2, 8.2
    cx, cy, cz = center
    n = Vector(normal).normalized()
    from lib import fillet, prism_xz
    panel = prism_xz("_plate", fillet([(cx - half_w, cz + z0), (cx + half_w, cz + z0), (cx + half_w, cz + z1), (cx - half_w, cz + z1)],
                                      2.4, 4), cy + n.y * 10.0, cy - n.y * 0.6, coll)
    boolean(target, panel)
    floor = (cx, cy - n.y * 0.6, cz)
    _place(name, (floor[0], floor[1], cz + 2.6), normal, up, 0.15)
    boolean(target, name, op="UNION")
    author = text_cutter(AUTHOR, 2.9, 0.3, coll, NAME_FONT)
    _place(author, (floor[0], floor[1], cz - 5.0), normal, up, 0.1)
    boolean(target, author, op="UNION")
    return w


def build(ctx):
    C = ctx["coll"]["Receiver"]
    P = ctx["parts"]
    lower = P["receiver"]["lower"]
    cover = P["receiver"]["cover"]
    plate = P["bolt"]["plate"]
    leaf = P["front"]["leaf"]
    # номер на правой стороне шахты (как «ИЕ-0440» на фото ВСС-М)
    stamp(lower, SERIAL, 3.6, (446.0, -18.0, -8.6), (0, -1, 0), (0, 0, 1), 0.15, C)
    # год и номер слева
    stamp(lower, "2019", 2.6, (446.0, 18.0, -8.6), (0, 1, 0), (0, 0, 1), 0.12, C)
    # номер узлов: крышка сзади справа, пылезащитная плита рамы
    stamp(cover, SUB, 2.4, (306.0, -19.5, 21.0), (0, -1, 0), (0, 0, 1), 0.12, C)
    stamp(plate, SUB, 2.2, (424.0, -14.45, 8.4), (0, -1, 0), (0, 0, 1), 0.12, C)
    # цифры дистанций на листе прицела (сотни метров), верхняя грань листа
    for i, x in enumerate((591.0, 601.0, 611.0, 621.0)):
        stamp(leaf, str(i + 1), 1.9, (x, 0.0, 38.1), (0, 0, 1), (-1, 0, 0), 0.1, C)
