# AR-15 «ГРАНЬ-15»: длинная нижняя планка 1913 вместо короткой — без пересборки геометрии и без перезапекания текстур
# (владелец 30.10: «планка снизу цевья очень коротенькая и далеко… отдельную модель длинной планки, которая будет
# вместо этой цепляться; не хочется тратить время на переделывание модели и перепекание текстур»).
# Длинная планка собирается из кусков штатной короткой (Bottom_rail, 244…272 мм) вместе с их развёрткой: левый конец
# с отверстием под винт, N одинаковых звеньев «полпаза — зуб — полпаза» по 10 мм и правый конец с отверстием. Звенья
# режутся по серединам пазов (дно паза — одно и то же сечение), поэтому стыкуются без щелей, а текстура — та же, что у
# короткой планки. Винты и Т-гайки — копии штатных, переставлены в пазы M-LOK цевья (центры x = 100 + 40·k).
# Короткая планка остаётся в файле в своей коллекции (выключена), длинная — в своей: переключение галочкой в Outliner.
#   blender -b <AR-15_…blend> --python tools/ar15/long_rail.py -- <out.blend> [задний_паз 100] [передний_паз 220]
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001
SHORT = "Bottom_rail"
X0, X1 = 244.0, 272.0          # штатная короткая планка по X, мм
SLOTS = (253.0, 263.0)         # её поперечные пазы (середины)
HOLES = (248.0, 268.0)         # отверстия под винты (зубья у концов)
STEP = 10.0                    # шаг пазов 1913
COLL_SHORT = "Нижняя планка — короткая (штатная)"
COLL_LONG = "Нижняя планка — длинная"


def piece(src, x_keep0, x_keep1, dx, name):
    """Кусок меша src между плоскостями x_keep0…x_keep1 (мм, None — без среза), сдвинутый на dx вдоль X."""
    bm = bmesh.new()
    bm.from_mesh(src.data)
    inv = src.matrix_world.inverted()
    for xc, keep_neg in ((x_keep1, True), (x_keep0, False)):
        if xc is None:
            continue
        co = inv @ Vector((xc * MM, 0.0, 0.0))
        no = (inv.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=keep_neg, clear_inner=not keep_neg)
    bmesh.ops.translate(bm, vec=inv.to_3x3() @ Vector((dx * MM, 0.0, 0.0)), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in src.data.materials:
        me.materials.append(m)
    return me


def build(rear_slot=100.0, front_slot=220.0):
    src = bpy.data.objects[SHORT]
    n = int(round((front_slot - rear_slot - (HOLES[1] - HOLES[0]) + (SLOTS[1] - SLOTS[0])) / STEP))
    # левый конец: отверстие HOLES[0] → rear_slot
    d_a = rear_slot - HOLES[0]
    parts = [piece(src, None, SLOTS[0], d_a, "lr_a")]
    for k in range(n):                  # звено k встаёт сразу за концом предыдущего куска
        parts.append(piece(src, SLOTS[0], SLOTS[1], d_a + STEP * k, f"lr_m{k}"))
    d_b = d_a + STEP * n - (SLOTS[1] - SLOTS[0])
    parts.append(piece(src, SLOTS[1], None, d_b, "lr_b"))
    assert abs((HOLES[1] + d_b) - front_slot) < 1e-6, (HOLES[1] + d_b, front_slot)
    # в один меш и сварить стыки по серединам пазов
    bm = bmesh.new()
    for me in parts:
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002 * MM)
    me = bpy.data.meshes.new("Bottom_rail_long")
    bm.to_mesh(me)
    bm.free()
    for m in src.data.materials:
        me.materials.append(m)
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new("Bottom_rail_long", me)
    ob.parent = src.parent
    ob.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    ob.matrix_basis = src.matrix_basis.copy()
    for k, v in src.items():
        ob[k] = v
    objs = [ob]
    # винты и Т-гайки: штатные копии в новые пазы
    for i, d in ((0, d_a), (1, d_b)):
        for kind in ("screw", "tnut"):
            s = bpy.data.objects[f"{SHORT}_{kind}{i}"]
            c = s.copy()
            c.data = s.data.copy()
            c.name = f"Bottom_rail_long_{kind}{i}"
            c.data.transform(Matrix.Translation(s.matrix_world.inverted().to_3x3() @ Vector((d * MM, 0.0, 0.0))))
            objs.append(c)
    return objs, n, (X0 + d_a, X1 + d_b)


def collection(name, parent):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def find_layer(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = find_layer(ch, name)
        if r:
            return r
    return None


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    rear, front = (float(a[1]), float(a[2])) if len(a) > 2 else (100.0, 220.0)
    src = bpy.data.objects[SHORT]
    home = src.users_collection[0]
    short = [src] + [bpy.data.objects[f"{SHORT}_{k}{i}"] for k in ("screw", "tnut") for i in (0, 1)]
    cs = collection(COLL_SHORT, home)
    cl = collection(COLL_LONG, home)
    for o in short:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        cs.objects.link(o)
    objs, n, span = build(rear, front)
    for o in objs:
        cl.objects.link(o)
    lc = find_layer(bpy.context.view_layer.layer_collection, COLL_SHORT)
    lc.exclude = True                   # штатная короткая выключена; включить — галочка в Outliner
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print("LONG_RAIL", n, "звеньев", f"x {span[0]:.1f}…{span[1]:.1f} мм", "винты", rear, front, "→", out)


if __name__ == "__main__":
    main()
