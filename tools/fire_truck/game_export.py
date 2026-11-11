"""Пожарная АЦ в игру → assets/models/prospekt_vehicles/PV_fire_tanker[_lod1|_lod2].gltf и запись в индекс моделей карт.

Источник — упрощённые сетки game_lod.py («models/game/FireTanker_game_<уровень>_v01.blend»): развёртка у них та же, что
у high-poly, здесь она сдвигается в клетки атласов (game_atlas.LAYOUT), детали сливаются в одну сетку, материал — на
атлас: A (кузов и кабина снаружи), B (детали кузова, кабины, крыша, профили), C (шасси, колёса, отсек насоса, салон
кабины), D (салон экипажа, зеркала) и «стекло» (атлас D, прозрачность — в альфе цвета). Карты — WebP, как у машин
«Проспекта». Оси игры: Y вверх, лицо машины — +Z (в Blender перед машины — −Y). Индекс data/urban95_models.json:
запись PV_fire_tanker с габаритом, треугольниками и уровнями (lods: LOD0 до LOD_ENDS[0] м, LOD1 до [1], LOD2 дальше),
чужие записи не трогаются. Набор карты «Проспекта» — «m:PV_fire_tanker» в поле Item вещи (docs/level_editing.md).

blender --background --factory-startup --python-exit-code 1 --python tools/fire_truck/game_export.py -- [lod0 lod1 lod2]
затем: tools/godot.cmd --headless --import; python -X utf8 tools/prospekt_vehicles/game_imports.py; ещё раз --import
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import game_atlas as GA  # noqa: E402

SRC = Path("E:/Models Blender/VEHICLES/Пожарная_АЦ/models/game")
OUT = ROOT / "assets" / "models" / "prospekt_vehicles"
INDEX = ROOT / "data" / "urban95_models.json"
MID = "PV_fire_tanker"
TITLE = "Пожарная автоцистерна, брошенная"
LOD_ENDS = (40.0, 110.0, 520.0)
GLASS_SLOTS = {"glass_auto", "lens_blue", "lens_amber", "lens_red", "lens_clear"}


def occlusion_group():
    g = bpy.data.node_groups.get("glTF Material Output")
    if g:
        return g
    g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def image(name: str, data: bool):
    path = GA.OUT / f"{name}.png"
    im = bpy.data.images.load(str(path), check_existing=True)
    im.name = name
    im.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return im


def material(key: str):
    """Материал атласа: цвет, ORM (R — затенённость, G — шероховатость, B — металл), нормаль; у стекла — альфа."""
    atlas = "D" if key == "glass" else key
    name = f"{MID}_{key}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = image(f"{MID}_{atlas}_baseColor", False)
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = image(f"{MID}_{atlas}_occlusionRoughnessMetallic", True)
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = image(f"{MID}_{atlas}_normal", True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nt.links.new(nrm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = occlusion_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    if key == "glass":
        nt.links.new(col.outputs["Alpha"], bsdf.inputs["Alpha"])
        m.surface_render_method = "BLENDED"
        m.use_backface_culling = False
    return m


def material_key(o) -> str:
    st, slot = o.get("ft_set"), o.get("ft_slot", "")
    if st == "glass":
        return "glass" if slot in GLASS_SLOTS else "D"
    return GA.layout()[st][0]


def build(level: str):
    src = SRC / f"FireTanker_game_{level}_v01.blend"
    bpy.ops.wm.open_mainfile(filepath=str(src))
    lay = GA.layout()
    obs = [o for o in bpy.data.objects if o.type == "MESH" and o.get("ft_set") in lay]
    done = set()
    for o in obs:
        me = o.data
        if me in done:
            continue
        done.add(me)
        _, u0, v0, k = lay[o["ft_set"]]
        uv = me.uv_layers.get("UVMap") or me.uv_layers[0]
        for d in uv.data:
            d.uv = (u0 + d.uv[0] * k, v0 + d.uv[1] * k)
        for extra in [l for l in me.uv_layers if l != uv]:
            me.uv_layers.remove(extra)
        me.materials.clear()
        me.materials.append(material(material_key(o)))
    # одна сетка: копии без связей, преобразования внутрь, потом слияние
    copies = []
    for o in obs:
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.data.transform(o.matrix_world)
        c.matrix_world.identity()
        if o.matrix_world.determinant() < 0:
            c.data.flip_normals()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    name = MID if level == "lod0" else f"{MID}_{level}"
    ob.name = name
    ob.data.name = name
    bpy.ops.object.material_slot_remove_unused()
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    lo = (min(xs), min(zs), -max(ys))
    hi = (max(xs), max(zs), -min(ys))
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    path = OUT / f"{name}.gltf"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures",
                              use_selection=True, export_apply=True, export_yup=True, export_texcoords=True,
                              export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=90, export_cameras=False, export_lights=False,
                              export_animations=False)
    # прозрачность стекла — смешением: экспортёр по способу отрисовки Blender мог записать MASK / OPAQUE
    data = json.loads(path.read_text(encoding="utf-8"))
    for mat in data.get("materials", []):
        if mat.get("name") == f"{MID}_glass":
            mat["alphaMode"] = "BLEND"
            mat.pop("alphaCutoff", None)
            mat["doubleSided"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"EXPORT {name}: {tris} треуг., материалов {len(ob.material_slots)}, габарит "
          f"{[round(hi[i] - lo[i], 3) for i in range(3)]}", flush=True)
    return {"file": f"res://assets/models/prospekt_vehicles/{name}.gltf", "triangles": tris, "lo": lo, "hi": hi,
            "materials": len(ob.material_slots)}


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    levels = [x for x in a if x in ("lod0", "lod1", "lod2")] or ["lod0", "lod1", "lod2"]
    res = {lv: build(lv) for lv in levels}
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    entry = index["models"].get(MID, {})
    if "lod0" in res:
        r = res["lod0"]
        lo, hi = r["lo"], r["hi"]
        entry.update({"id": MID, "name": TITLE, "file": r["file"], "triangles": r["triangles"], "materials": r["materials"],
                      "aabb": {"center": [round((lo[i] + hi[i]) * 0.5, 4) for i in range(3)],
                               "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
                      "root_offset": [0, 0, 0], "cell": 24.0, "lod_fade": False})
    lods = {d["file"]: d for d in entry.get("lods", [])}
    files = [f"res://assets/models/prospekt_vehicles/{MID}{'' if lv == 'lod0' else '_' + lv}.gltf"
             for lv in ("lod0", "lod1", "lod2")]
    entry["lods"] = []
    for lv, f, end in zip(("lod0", "lod1", "lod2"), files, LOD_ENDS):
        tri = res[lv]["triangles"] if lv in res else lods.get(f, {}).get("triangles", 0)
        entry["lods"].append({"file": f, "end": end, "triangles": tri})
    index["models"][MID] = entry
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("INDEX", MID, entry["triangles"], [l["triangles"] for l in entry["lods"]], flush=True)


if __name__ == "__main__":
    main()
