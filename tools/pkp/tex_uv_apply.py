# «Частокол»: развёртка наборов (tex_uv.py → <WORK>/uv/<набор>.npz) в принятую форму — файл с развёрткой
# (tex_sets.UV_BLEND). Геометрия, нормали, родители, приводы рига и PKP_Controls не меняются: только слой UV «UVMap» и
# свойство объекта pkp_set (набор текстур). Видимость коллекций — как в исходнике (коробка 200, кронштейны выключены).
# blender -b "<Частокол_геометрия_v03.blend>" --factory-startup --python-exit-code 1 --python tools/pkp/tex_uv_apply.py -- [out.blend]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
import tex_sets as T  # noqa: E402

UV = "UVMap"


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = a[0] if a else T.UV_BLEND
    uvs = {}
    for s in T.SETS:
        p = f"{T.WORK}/uv/{s}.npz"
        if not os.path.exists(p):
            raise RuntimeError("нет развёртки набора " + s)
        z = np.load(p)
        for k in z.files:
            if k.startswith("uv__"):
                uvs[k[4:]] = (s, z[k])
    done = set()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        s = T.set_of_object(o.name, o.data.name)
        if s is None:
            raise RuntimeError("деталь без набора: " + o.name)
        o["pkp_set"] = s
        me = o.data
        if me.name in done:
            continue
        if me.name not in uvs:
            raise RuntimeError("нет развёртки сетки " + me.name)
        s2, uv = uvs[me.name]
        if len(uv) != len(me.loops):
            raise RuntimeError(f"{me.name}: петель {len(me.loops)}, в развёртке {len(uv)}")
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name=UV)
        me.uv_layers[UV].uv.foreach_set("vector", uv.astype(np.float32).ravel())
        me.update()
        done.add(me.name)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out, len(done), "сеток")


if __name__ == "__main__":
    main()
