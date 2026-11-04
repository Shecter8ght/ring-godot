# ПП по мотивам KRISS Vector: габариты оценённой сетки в мире против заводских (KRISS Vector Gen II SDP/SMG, листы
# производителя; TFB/Wikipedia — длина со сложенным прикладом), в положениях приклада.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/smg03/measure.py
import bpy
from mathutils import Vector

REF = {
    "длина, приклад сложен (SBR 5.5″: 16.25″, TFB)": 412.8,
    "длина, приклад разложен (SMG: 24.3″, Wikipedia; +8.3″ к сложенному)": 617.0,
    "длина без приклада: колпачок … торец коробки (SDP 16.7″ с затыльной пластиной)": 425.4,
    "высота без магазина и прицелов, до верха планки (SDP 6.8″)": 172.7,
    "ширина наибольшая (SDP 2.6″ / SMG 2.8″)": 66.0,
}


def bounds(names=None, skip=()):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get():
            continue
        if names and not any(o.name.startswith(n) for n in names):
            continue
        if any(o.name.startswith(s) for s in skip):
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        for v in me.vertices:
            w = oe.matrix_world @ v.co
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        oe.to_mesh_clear()
    return lo * 1000, hi * 1000


def state(**kw):
    c = bpy.data.objects["SMG03_Controls"]
    for k in ("stock_fold", "front_sight", "rear_sight", "mag30"):
        c[k] = {"front_sight": 1.0, "rear_sight": 1.0}.get(k, 0.0)
    for k, v in kw.items():
        c[k] = v
    c.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def main():
    rows = []
    state(stock_fold=1.0)
    lo, hi = bounds()
    rows.append(("длина, приклад сложен (SBR 5.5″: 16.25″, TFB)", hi.x - lo.x))
    state()
    lo, hi = bounds()
    rows.append(("длина, приклад разложен (SMG: 24.3″, Wikipedia; +8.3″ к сложенному)", hi.x - lo.x))
    lo, hi = bounds(skip=("Stock", "Magazine"))
    rows.append(("длина без приклада: колпачок … торец коробки (SDP 16.7″ с затыльной пластиной)", hi.x - lo.x))
    state(front_sight=0.0, rear_sight=0.0)
    lo, hi = bounds(skip=("Stock", "Magazine", "Front_sight", "Rear_sight"))
    rows.append(("высота без магазина и прицелов, до верха планки (SDP 6.8″)", hi.z - lo.z))
    lo, hi = bounds(skip=("Stock",))
    rows.append(("ширина наибольшая (SDP 2.6″ / SMG 2.8″)", hi.y - lo.y))
    lo2, hi2 = bounds(names=("Receiver",))
    for name, val in rows:
        ref = REF[name]
        print(f"DIM {name}: {val:.1f} мм, образец {ref:.1f} мм, {100 * (val - ref) / ref:+.1f} %")
    print(f"DIM коробка: длина {hi2.x - lo2.x:.1f}, ширина {hi2.y - lo2.y:.1f} (цевьё KRISS MK1 внутри 43.7), высота {hi2.z - lo2.z:.1f}")
    for nm in ("Magazine13_body", "Receiver", "Receiver", "Stock_body", "Stock_buttplate"):
        a, b = bounds(names=(nm,))
        print(f"DIM {nm}: X {a.x:.1f}…{b.x:.1f}, ширина {b.y - a.y:.1f}, Z {a.z:.1f}…{b.z:.1f}")


main()
