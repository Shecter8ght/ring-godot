"""Следы использования из данных игры, шаг 2: копия high-poly с развёрткой для масок и «карта текселей».

Копия принятого текстурированного исходника получает развёртку WearUV (у части деталей v13 своей развёртки нет; исходная
UVMap не трогается) — по набору текстур на атлас игры (Steel, Polymer, Magazine из parts.json game_lp.py): Smart UV Project
и упаковка всех деталей набора в один квадрат. Копия сохраняется — в ней же потом стоит пробный вид (trial_look.py).

Затем, без сохранения, в WearUV запекаются (Cycles, излучение, float): положение точки в осях VERAS54 (м), нормаль и номер
детали. По ним wear_masks.py считает маски на каждом текселе — без растеризации и без развёртки руками.

blender --background --factory-startup --python-exit-code 1 --python tools/wear_from_use/hp_texels.py -- <принятый.blend> <копия.blend> <папка данных> [размер]
→ <папка>/texels_<набор>.npz (pos, nrm, obj — по текселям с данными), <папка>/objects.json (номер → деталь, кость, набор).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REC = json.loads((ROOT / "_asset_src/veras54_game_v13/lp/parts.json").read_text(encoding="utf-8"))
SRC, COPY, OUT = sys.argv[sys.argv.index("--") + 1:][:3]
SIZE = int(sys.argv[sys.argv.index("--") + 4]) if len(sys.argv) > sys.argv.index("--") + 4 else 2048
OUT = Path(OUT)
OUT.mkdir(parents=True, exist_ok=True)
UV = "WearUV"
OFFSET = 4.0           # излучение запекается со сдвигом: отрицательные координаты не теряются

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
root = bpy.data.objects["VERAS54"]

# деталь исходника → (набор текстур, кость рига) — как в игровой сетке
part_of = {}
for p, v in REC["parts"].items():
    for s in v["sources"]:
        part_of[s] = (v["atlas"], v["node"])
sets: dict[str, list] = {}
for name, (atlas, node) in part_of.items():
    o = bpy.data.objects.get(name)
    if o is None or o.type != "MESH":
        print("NO SOURCE", name)
        continue
    sets.setdefault(atlas, []).append(o)

# связанные копии сетки разделить: общая развёртка легла бы внахлёст
for objs in sets.values():
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()


def area_of(objs) -> float:
    a = 0.0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        a += sum(f.calc_area() for f in bm.faces)
        bm.free()
    return a


for atlas, objs in sorted(sets.items()):
    for o in objs:
        uvs = o.data.uv_layers
        if UV in uvs:
            uvs.remove(uvs[UV])
        uv = uvs.new(name=UV)
        uvs.active = uv            # Smart UV Project пишет в активную; UVMap остаётся основной для рендера
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.hide_viewport = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.reveal()
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.002, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, margin_method="FRACTION", margin=0.004, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        uvs = o.data.uv_layers
        # для рендера и стеков UCUPaint остаётся прежняя UVMap
        if "UVMap" in uvs:
            uvs.active = uvs["UVMap"]
            uvs["UVMap"].active_render = True
    a = area_of(objs)
    print(f"WEAR_UV {atlas}: {len(objs)} деталей, площадь {a * 1e4:.0f} см², ≈{SIZE / (a ** 0.5) * 0.001 * 0.8:.2f} пикс/мм при {SIZE}", flush=True)

bpy.ops.wm.save_as_mainfile(filepath=COPY, copy=False)
print("COPY_SAVED", COPY, flush=True)

# --- запекание карты текселей (не сохраняется) ---
sc.render.engine = "CYCLES"
sc.cycles.samples = 1
sc.cycles.use_denoising = False
# на процессоре (по умолчанию в --factory-startup) 161 деталь стали печётся ~25 мин
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != "CPU"
sc.cycles.device = "GPU"
sc.render.bake.use_clear = True
objects = {}
idx = 0
for atlas, objs in sorted(sets.items()):
    for o in objs:
        idx += 1
        o.pass_index = idx
        objects[idx] = {"name": o.name, "set": atlas, "bone": part_of[o.name][1]}
(OUT / "objects.json").write_text(json.dumps(objects, ensure_ascii=False, indent=1), encoding="utf-8")


def bake_pass(atlas, objs, what, margin):
    img = bpy.data.images.new(f"_tex_{atlas}_{what}", SIZE, SIZE, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0, 0, 0, 0)
    m = bpy.data.materials.new(f"_bake_{what}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    if what == "obj":
        info = nt.nodes.new("ShaderNodeObjectInfo")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(info.outputs["Object Index"], comb.inputs[0])
        nt.links.new(comb.outputs[0], em.inputs["Color"])
    else:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        add = nt.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        add.inputs[1].default_value = (OFFSET, OFFSET, OFFSET)
        nt.links.new(geo.outputs["Position" if what == "pos" else "Normal"], add.inputs[0])
        nt.links.new(add.outputs[0], em.inputs["Color"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
        o.data.uv_layers.active = o.data.uv_layers[UV]
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    sc.render.bake.margin = margin
    sc.render.bake.margin_type = "EXTEND"
    bpy.ops.object.bake(type="EMIT")
    px = np.zeros(SIZE * SIZE * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(SIZE, SIZE, 4)


for atlas, objs in sorted(sets.items()):
    pos = bake_pass(atlas, objs, "pos", 6)
    nrm = bake_pass(atlas, objs, "nrm", 6)
    oid = bake_pass(atlas, objs, "obj", 6)
    cov = bake_pass(atlas, objs, "obj", 0)
    has = pos[..., :3].sum(axis=2) > 1.0
    ys, xs = np.nonzero(has)
    p = pos[ys, xs, :3].astype(np.float64) - OFFSET
    # мир → оси VERAS54
    inv = np.array(root.matrix_world.inverted())
    p = p @ inv[:3, :3].T + inv[:3, 3]
    n = nrm[ys, xs, :3].astype(np.float64) - OFFSET
    n = n @ np.array(root.matrix_world.to_3x3().normalized())   # мир → оси VERAS54: Rᵀ·n (строкой — n·R)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    np.savez_compressed(OUT / f"texels_{atlas}.npz", ys=ys.astype(np.int16), xs=xs.astype(np.int16), pos=p.astype(np.float32),
                        nrm=n.astype(np.float32), obj=np.rint(oid[ys, xs, 0]).astype(np.int16),
                        inside=(cov[ys, xs, 0] > 0.5), size=np.array(SIZE))
    print(f"TEXELS {atlas}: {len(ys)} текселей с данными, из них в островах {(cov[ys, xs, 0] > 0.5).sum()}", flush=True)
