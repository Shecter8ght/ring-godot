# «Частокол», этап 2 (износ): геометрические карты набора — в каждом пикселе развёртки «UVMap» (та же, что в проектах
# Painter) положение (мм, в осях пулемёта) и нормаль. По ним места износа считаются вне Blender (tools/pkp/wear_place.py):
# кривизна в 1/мм — кромкой считается скругление радиусом меньше миллиметра, а не всё, что круглое (генератор кривизны
# Painter меряет в пикселях развёртки и на этой форме закрывал оси, спуск и предохранитель целиком — проба 14.11).
#   blender -b <Частокол_развёртка_v02.blend> --factory-startup --python-exit-code 1 --python tools/pkp/wear_maps.py -- <папка> [набор …] [size=4096]
# Пишет <папка>/<набор>_maps.npz: pos (мм, float32 ×3), nrm (float16 ×3) — строки сверху вниз, как в картинке.
# Номер детали в пикселе — по треугольникам развёртки (_asset_src/pkp/tex/uv/<набор>_tris.npz), здесь не печётся.
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets as T  # noqa: E402


def _gpu():
    """Cycles на видеокарте (с --factory-startup устройства не включены — печь на процессоре вчетверо дольше)."""
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                pr.compute_device_type = kind
                pr.get_devices()
                devs = [d for d in pr.devices if d.type == kind]
                if devs:
                    for d in pr.devices:
                        d.use = d.type == kind
                    bpy.context.scene.cycles.device = "GPU"
                    return kind
            except Exception:      # noqa: BLE001
                continue
    except Exception:      # noqa: BLE001
        pass
    bpy.context.scene.cycles.device = "CPU"
    return "CPU"


def _unexclude(lc):
    lc.exclude = False
    lc.hide_viewport = False
    for c in lc.children:
        _unexclude(c)


def _material(kind, off, scale):
    """Свечение = положение (сдвиг и масштаб в 0…1: отрицательное свечение запекание обрезает) / нормаль."""
    mat = bpy.data.materials.new("wm_" + kind)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], out.inputs[0])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    a = nt.nodes.new("ShaderNodeVectorMath")
    a.operation = "MULTIPLY_ADD"
    nt.links.new(geo.outputs["Position" if kind == "pos" else "Normal"], a.inputs[0])
    a.inputs[1].default_value = scale
    a.inputs[2].default_value = off
    nt.links.new(a.outputs[0], em.inputs["Color"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    return mat, tex


def objects_of(name):
    """Сетки набора, по одной на сетку (копии ленты делят сетку и развёртку — достаточно одной)."""
    names = T.SETS[name][2]
    objs = [o for o in bpy.data.objects if o.type == "MESH" and T.set_of_object(o.name, o.data.name) == name]
    objs.sort(key=lambda o: (o.name not in names, o.name))
    seen, out = set(), []
    for o in objs:
        if o.data.name in seen:
            continue
        seen.add(o.data.name)
        out.append(o)
    return out


def bake_set(name, out_dir, size):
    objs = objects_of(name)
    S = bpy.context.scene
    S.render.engine = "CYCLES"
    S.cycles.samples = 1
    S.render.bake.margin = 4
    S.render.bake.margin_type = "EXTEND"
    S.cycles.filter_width = 0.01
    pts = []
    for o in objs:
        m = np.array(o.matrix_world)
        co = np.empty(len(o.data.vertices) * 3, np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        pts.append([co.min(0), co.max(0)])
    pts = np.array(pts)
    lo, hi = pts[:, 0].min(0) - 0.01, pts[:, 1].max(0) + 0.01
    sc = 1.0 / (hi - lo)
    old = {o.data.name: list(o.data.materials) for o in objs}
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.hide_render = False
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    bpy.context.view_layer.objects.active = objs[0]
    res = {}
    for kind, off, scale in (("pos", tuple(-lo * sc), tuple(sc)), ("nrm", (0.5,) * 3, (0.5,) * 3)):
        mat, tex = _material(kind, off, scale)
        img = bpy.data.images.new("wm_" + kind, size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        bpy.ops.object.bake(type="EMIT")
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        res[kind] = px.reshape(size, size, 4)[::-1, :, :3].copy()          # сверху вниз, как в файле картинки
        bpy.data.images.remove(img)
    for o in objs:
        o.data.materials.clear()
        for m in old[o.data.name]:
            o.data.materials.append(m)
    pos = ((res["pos"] / sc + lo) * 1000.0).astype(np.float32)
    nrm = res["nrm"] * 2.0 - 1.0
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}_maps.npz")
    np.savez_compressed(path, pos=pos, nrm=nrm.astype(np.float16))
    print("MAPS", name, size, "сеток", len(objs), "→", path, flush=True)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    size = 4096
    names = []
    for x in a[1:]:
        if x.startswith("size="):
            size = int(x[5:])
        else:
            names.append(x)
    names = names or list(T.SETS)
    _unexclude(bpy.context.view_layer.layer_collection)
    print("DEVICE", _gpu(), flush=True)
    for n in names:
        bake_set(n, out, size)


if __name__ == "__main__":
    main()
