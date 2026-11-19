# ВЕРАС-54 v14: развёртка наборов (tex_uv.py → <WORK>/uv/<набор>.npz) в принятую форму — файл развёртки
# (tex_sets.UV_BLEND, новая папка «Карты v14»). Геометрия, нормали, родители, приводы рига и VERAS54_Controls не
# меняются: у каждой сетки — один слой UV «UVMap», материал-заглушка заменён материалом набора (= набор текстур
# Painter; цвет в окне — по набору), у объекта свойства v14_set (набор), v14_slot (черновой слот отделки),
# v14_stub (прежний материал-заглушка формы). Экземпляры патронов (tex_sets.INSTANCES) получают развёртку детали-
# источника — топология сверяется по петлям.
# blender -b "<ВЕРАС-54_геометрия_v14_04.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_uv_apply.py -- [out.blend]
import colorsys
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
import tex_sets as T  # noqa: E402

UV = "UVMap"


def set_material(s, i, n):
    m = bpy.data.materials.get(s) or bpy.data.materials.new(s)
    r, g, b = colorsys.hsv_to_rgb(i / n, 0.45, 0.8)
    m.diffuse_color = (r, g, b, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.5
    m["v14_set"] = s
    return m


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(a[0] if a else T.UV_BLEND)
    uvs, lvs = {}, {}
    for s in T.SETS:
        p = f"{T.WORK}/uv/{s}.npz"
        if not os.path.exists(p):
            raise RuntimeError("нет развёртки набора " + s)
        z = np.load(p)
        for k in z.files:
            if k.startswith("uv__"):
                uvs[k[4:]] = (s, z[k])
            elif k.startswith("lv__"):
                lvs[k[4:]] = z[k]
    mats = {s: set_material(s, i, len(T.SETS)) for i, s in enumerate(T.SETS)}
    done = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        s = T.set_of(o.name)
        if s is None:
            raise RuntimeError("деталь без набора: " + o.name)
        src = T.INSTANCES.get(o.name, o.name)
        if src not in uvs:
            raise RuntimeError("нет развёртки детали " + src)
        s2, uv = uvs[src]
        me = o.data
        if me.users > 1:
            raise RuntimeError("общая сетка у " + o.name)
        if len(uv) != len(me.loops):
            raise RuntimeError(f"{o.name}: петель {len(me.loops)}, в развёртке {len(uv)}")
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        if not np.array_equal(lv, lvs[src]):
            raise RuntimeError(f"{o.name}: топология не совпадает с {src}")
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name=UV)
        me.uv_layers[UV].uv.foreach_set("vector", uv.astype(np.float32).ravel())
        stub = [sl.material.name if sl.material else "" for sl in o.material_slots]
        o["v14_set"] = s
        o["v14_slot"] = T.slot_of(o.name) or ""
        o["v14_stub"] = ",".join(stub)
        if src != o.name:
            o["v14_uv_from"] = src
        me.materials.clear()
        me.materials.append(mats[s])
        me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32))
        me.update()
        done += 1
    # заглушки формы больше никому не нужны — в файле остаются только материалы наборов
    for m in list(bpy.data.materials):
        if m.users == 0 and m.name not in mats:
            bpy.data.materials.remove(m)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
    print("SAVED", out, done, "сеток")


if __name__ == "__main__":
    main()
