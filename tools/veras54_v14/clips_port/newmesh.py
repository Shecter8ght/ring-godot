"""ВЕРАС-54, разведка: новая игровая сетка v14 в файл клипов (в память, тождественно в оси рига оружия) — как в measure.py."""
import bpy
from mathutils import Matrix

NEW_PARENT = {"Receiver": "WeaponRoot", "Bolt_Carrier": "Bolt", "Selector_Lever": "Selector", "Trigger": "Trigger",
              "Mag_Catch": "MagazineLatch", "Magazine": "Magazine", "Stock_Knuckle": "StockFold",
              "MuzzleDevice": "MuzzleAttachment", "Cover_Button": "CoverButton"}


def place(lp, wr, scene, coll_name="NEW v14 (разведка)", rounds=False):
    """Добавить объекты LOD0 из lp, подвижные узлы — на кости старого рига. Риг оружия должен стоять в покое.
    → {имя в файле сетки: объект}."""
    with bpy.data.libraries.load(lp, link=False) as (src, dst):
        names = [n for n in src.objects if not n.endswith("_LOD1") and (rounds or not n.startswith(("Round_", "Chamber_")))]
        dst.objects = list(names)
    coll = bpy.data.collections.new(coll_name)
    scene.collection.children.link(coll)
    new = {}
    for n, o in zip(names, dst.objects):
        if o is not None:
            coll.objects.link(o)
            new[n] = o
    for o in new.values():
        o.animation_data_clear()
        o.delta_location = (0, 0, 0)
        o.delta_rotation_euler = (0, 0, 0)
        o.delta_scale = (1, 1, 1)
    name_of = {o: n for n, o in new.items()}
    local = {}
    for o in new.values():
        m = Matrix.Identity(4)
        q = o
        while q is not None:
            m = q.matrix_basis @ m if q.parent is None else (q.matrix_parent_inverse @ q.matrix_basis) @ m
            q = q.parent
        local[name_of[o]] = m
    W = wr.matrix_world.copy()
    for name, bone in NEW_PARENT.items():
        if name not in new:
            continue
        o = new[name]
        if o.parent is not None and o.parent.name not in new and name != "Receiver":
            pass
        o.parent = wr
        o.parent_type = "BONE"
        o.parent_bone = bone
        o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for name in NEW_PARENT:
        if name in new:
            new[name].matrix_world = W @ local[name]
    bpy.context.view_layer.update()
    return new
