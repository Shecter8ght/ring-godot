# АСТЕН-919, этап 2 (износ): геометрические карты набора текстур — в каждом пикселе развёртки (UVMap, та же, что в
# проекте Painter) положение в осях модели (мм), нормаль и номер детали (по образцу tools/ar15/wear_maps.py). По ним
# места следов считаются попиксельно numpy вне Blender (tools/asten919/wear_marks.py).
#   blender -b <АСТЕН-919_развёртка_v02.blend> --factory-startup --python-exit-code 1 --python tools/asten919/wear_maps.py -- <набор|all> <папка> [размер]
# Пишет <набор>_maps.npz: pos (мм, float32 ×3), nrm (float16 ×3), ids (uint8, 0 — пусто) — строки сверху вниз, как в
# картинке; ids_names — имена деталей по номеру, ids_mats — их материал геометрии (asten_mat).
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets  # noqa: E402


def _material(kind, off, scale):
    """Свечение = положение (сдвиг и масштаб в 0…1: отрицательное свечение запекание обрезает) / нормаль / номер."""
    mat = bpy.data.materials.new("wm_" + kind)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], out.inputs[0])
    if kind == "id":
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        m = nt.nodes.new("ShaderNodeMath"); m.operation = "DIVIDE"; m.inputs[1].default_value = 255.0
        nt.links.new(oi.outputs["Object Index"], m.inputs[0])
        nt.links.new(m.outputs[0], em.inputs["Color"])
    else:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        a = nt.nodes.new("ShaderNodeVectorMath"); a.operation = "MULTIPLY_ADD"
        nt.links.new(geo.outputs["Position" if kind == "pos" else "Normal"], a.inputs[0])
        a.inputs[1].default_value = scale
        a.inputs[2].default_value = off
        nt.links.new(a.outputs[0], em.inputs["Color"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    return mat, tex


def _gpu():
    import addon_utils
    addon_utils.enable("cycles")
    cp = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):          # при --factory-startup устройства Cycles выключены
        try:
            cp.compute_device_type = kind
            cp.get_devices()
            for dv in cp.devices:
                dv.use = dv.type != "CPU"
            return
        except Exception:      # noqa: BLE001
            continue


def _show_all():
    """Все коллекции в слое вида (вариант ствола с резьбой выключен): запекание требует объект в слое. Не сохраняется."""
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            walk(ch)
    walk(bpy.context.view_layer.layer_collection)


def main():
    _gpu()
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "all":
        for n in tex_sets.SETS:
            bake_set(n, a[1], None)
        return
    bake_set(a[0], a[1], int(a[2]) if len(a) > 2 else None)


def bake_set(name, out_dir, size):
    size = size or tex_sets.SETS[name][0]
    objs = [o for o in bpy.data.objects if o.type == "MESH" and tex_sets.set_of(o.name) == name]
    _show_all()
    S = bpy.context.scene
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 1
    S.render.bake.margin = 8
    # без размытия: фильтр пикселя и поля «по соседним граням» смешивали номер детали на краях островов, и округление
    # давало промежуточные номера — чужие детали по краям (проба 30.10)
    S.render.bake.margin_type = "EXTEND"
    S.cycles.filter_width = 0.01
    lo = np.min([np.min([o.matrix_world @ v.co for v in o.data.vertices], 0) for o in objs], 0) - 0.01
    hi = np.max([np.max([o.matrix_world @ v.co for v in o.data.vertices], 0) for o in objs], 0) + 0.01
    sc = 1.0 / (hi - lo)
    old = {o.name: list(o.data.materials) for o in objs}
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for i, o in enumerate(objs):
        o.pass_index = i + 1
        o.hide_set(False); o.hide_render = False
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    bpy.context.view_layer.objects.active = objs[0]
    res = {}
    for kind, off, scale in (("pos", tuple(-lo * sc), tuple(sc)), ("nrm", (0.5,) * 3, (0.5,) * 3), ("id", None, None)):
        mat, tex = _material(kind, off or (0, 0, 0), scale or (1, 1, 1))
        img = bpy.data.images.new("wm_" + kind, size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        bpy.ops.object.bake(type="EMIT")
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        res[kind] = px.reshape(size, size, 4)[::-1, :, :3]          # сверху вниз, как в файле картинки
    for o in objs:
        o.data.materials.clear()
        for m in old[o.name]:
            o.data.materials.append(m)
    ids = np.rint(res["id"][..., 0] * 255.0).astype(np.uint8)
    pos = ((res["pos"] / sc + lo) * 1000.0).astype(np.float32)
    nrm = res["nrm"] * 2.0 - 1.0
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}_maps.npz")
    np.savez_compressed(path, pos=pos, nrm=nrm.astype(np.float16), ids=ids,
                        ids_names=np.array([""] + [o.name for o in objs]),
                        ids_mats=np.array([""] + [str(o.get("asten_mat", "")) for o in objs]))
    print("MAPS", name, size, "деталей", len(objs), "пикселей с деталью", int((ids > 0).sum()), "→", path)


if __name__ == "__main__":
    main()
