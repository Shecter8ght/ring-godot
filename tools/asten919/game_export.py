"""АСТЕН-919: игровая сетка (game_lp.py) с картами (game_pack.py) → glTF игры под общий риг пистолета (WeaponRig).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/asten919/game_export.py
→ assets/models/weapons/asten919/:
  asten919.gltf — пистолет: корень ASTEN919; узлы деталей — пустышки без поворота в точке оси (Frame, Slide, Barrel,
    Trigger, SlideStop, SlideLock, MagCatch, Magazine → Rounds → Round_01…17, 1 — верхний), сетки — дочерние
    (<Имя>_Mesh; MuzzleDevice_Mesh — гайка резьбы ствола: обвес на резьбу её прячет; MosCover_Mesh — крышка выреза
    под коллиматор); метки Muzzle (срез резьбы ствола), SightFront, SightRear; ветка ASTEN919_LOD1 — то же, упрощённое
    (~4,5 тыс. треугольников, один патрон) для третьего лица;
  asten919_mag.gltf — магазин с патронами отдельно (значок и предмет на полу), оси как в оружии;
  asten919.json — отчёт: треугольники, метки, оси узлов — в осях игры.
Оси игры: +Z — к дулу, +Y — вверх, −X — правая сторона стрелка; начало — как у прежней модели игры (157,7 мм позади
среза штатного ствола, 65,2 мм ниже оси канала): хваты рук и точки обвесов оружия остаются на местах. Перевод из
осей исходника — поворот на −90° вокруг Z и сдвиг; экспорт Y-up.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src/asten919/game"
OUT = ROOT / "assets/models/weapons/asten919"
REC = json.loads((WORK / "lp/parts.json").read_text(encoding="utf-8"))
ORIGIN = Vector(REC["marks"]["Origin"])
MAP = Matrix.Rotation(math.radians(-90), 4, "Z") @ Matrix.Translation(-ORIGIN)
NODES = ["Frame", "Slide", "Barrel", "Trigger", "SlideStop", "SlideLock", "MagCatch", "Magazine"]
UNDER = {"SlideLock": "Frame"}        # риг игры этого узла не знает: он под Frame и уходит вместе с ним при смене LOD
LOD_TRIS = 4500
log = lambda *a: print("ASTEN_EXPORT", *a, flush=True)  # noqa: E731


def game_point(p) -> list:
    """Точка исходника (м) → оси игры: (y, z, x) от начала."""
    q = Vector(p) - ORIGIN
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def tris(o) -> int:
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def material(atlas: str):
    tag = f"asten919_{atlas}_100"
    m = bpy.data.materials.get(f"GAME • {atlas} • 100") or bpy.data.materials.new(f"ASTEN919_{atlas}")
    m.name = f"ASTEN919_{atlas}"
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "GameUV"

    def tex(kind, cs):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(OUT / f"{tag}_{kind}.png"), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t
    nt.links.new(tex("albedo", "sRGB").outputs["Color"], p.inputs["Base Color"])
    orm = tex("orm", "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], p.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "GameUV"
    nt.links.new(tex("normal", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    g = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [s.name for s in g.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]:
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = g
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    return m


def export_gltf(path: Path, objs) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), use_selection=True, export_yup=True, export_apply=True,
                              export_extras=False, export_animations=False, export_cameras=False, export_lights=False,
                              export_texcoords=True, export_normals=True, export_tangents=True,
                              export_format="GLTF_SEPARATE", export_texture_dir="", export_materials="EXPORT",
                              export_image_format="AUTO")


def empty(name, parent, world: Matrix):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = 0.004
    e.parent = parent
    e.matrix_parent_inverse = Matrix.Identity(4)
    e.matrix_basis = (parent.matrix_world.inverted() if parent else Matrix.Identity(4)) @ world
    bpy.context.view_layer.update()
    return e


def main():
    bpy.context.preferences.use_preferences_save = False
    bpy.ops.wm.open_mainfile(filepath=str(WORK / "lp/ASTEN919_Game_LP.blend"))
    S = bpy.context.scene
    for o in bpy.data.objects:                      # сетки — в коллекцию сцены
        if o.name not in S.collection.objects:
            S.collection.objects.link(o)
    for atlas in ("Slide", "Frame", "Magazine"):
        material(atlas)
    meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    root = empty("ASTEN919", None, Matrix.Identity(4))
    nodes = {}
    for n in NODES:
        nodes[n] = empty(n, nodes[UNDER[n]] if n in UNDER else root, Matrix.Translation((MAP @ Vector(REC["pivots"][n]))))
    for name, o in meshes.items():
        if name == "Round_Mesh":
            continue
        node = nodes[o["node"]]
        w = o.matrix_world.copy()
        o.parent = node
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.data.transform(node.matrix_world.inverted() @ MAP @ w)
        o.matrix_basis = Matrix.Identity(4)
    # патроны: одна сетка, 17 мест (1 — верхний)
    rounds = empty("Rounds", nodes["Magazine"], nodes["Magazine"].matrix_world.copy())
    rd = meshes["Round_Mesh"]
    S.collection.objects.unlink(rd) if rd.name in S.collection.objects else None
    for c in list(rd.users_collection):
        c.objects.unlink(rd)
    round_objs = []
    for i, m in enumerate(REC["rounds"], 1):
        r = bpy.data.objects.new(f"Round_{i:02d}", rd.data)
        S.collection.objects.link(r)
        r.parent = rounds
        r.matrix_parent_inverse = Matrix.Identity(4)
        r.matrix_basis = rounds.matrix_world.inverted() @ MAP @ Matrix(m)
        round_objs.append(r)
    bpy.data.objects.remove(rd, do_unlink=True)
    marks = REC["marks"]
    empty("Muzzle", root, Matrix.Translation(MAP @ Vector(marks["Muzzle"])))
    empty("SightFront", nodes["Slide"], Matrix.Translation(MAP @ Vector(marks["SightFront"])))
    empty("SightRear", nodes["Slide"], Matrix.Translation(MAP @ Vector(marks["SightRear"])))
    bpy.context.view_layer.update()

    main_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    main_total = sum(tris(o) for o in main_meshes)

    # магазин отдельно — до LOD (иначе в него попала бы ветка LOD1)
    mag_objs = [nodes["Magazine"], rounds] + round_objs + [o for o in main_meshes if o.parent == nodes["Magazine"]]
    keep = nodes["Magazine"].parent, nodes["Magazine"].matrix_basis.copy()
    nodes["Magazine"].parent = None
    nodes["Magazine"].matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    export_gltf(OUT / "asten919_mag.gltf", mag_objs)
    nodes["Magazine"].parent = keep[0]
    nodes["Magazine"].matrix_parent_inverse = Matrix.Identity(4)
    nodes["Magazine"].matrix_basis = keep[1]
    bpy.context.view_layer.update()

    # LOD1: копия иерархии с суффиксом _LOD1 под ASTEN919_LOD1, сетки упрощены пропорционально; патрон — один
    unique = {}
    for o in main_meshes:
        unique.setdefault(o.data.name, o)
    budget_src = sum(tris(o) for o in unique.values())
    lod_root = empty("ASTEN919_LOD1", root, Matrix.Identity(4))
    copies = {"ASTEN919": lod_root}
    for n in NODES:
        copies[n] = empty(n + "_LOD1", copies[UNDER[n]] if n in UNDER else lod_root, nodes[n].matrix_world.copy())
    copies["Rounds"] = empty("Rounds_LOD1", copies["Magazine"], rounds.matrix_world.copy())
    lod_total = 0
    for o in main_meshes:
        if o.name.startswith("Round_") and o.name != "Round_01":
            continue
        c = o.copy()
        c.data = o.data.copy()
        S.collection.objects.link(c)
        c.name = o.name + "_LOD1"
        c.parent = copies[o.parent.name]
        c.matrix_parent_inverse = Matrix.Identity(4)
        c.matrix_basis = o.matrix_basis.copy()
        budget = max(12, int(tris(o) * LOD_TRIS / budget_src))
        if tris(c) > budget:
            bpy.ops.object.select_all(action="DESELECT")
            c.select_set(True)
            bpy.context.view_layer.objects.active = c
            d = c.modifiers.new("lod", "DECIMATE")
            d.ratio = budget / tris(c)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
        lod_total += tris(c)
    bpy.context.view_layer.update()
    export_gltf(OUT / "asten919.gltf", [o for o in bpy.data.objects])
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / "lp/ASTEN919_export.blend"), compress=True)
    rep = dict(schema="asten919_game", source=REC["source"],
               triangles=dict(first_person=main_total, lod1=lod_total,
                              nodes={k: v["tris"] for k, v in REC["nodes"].items()}),
               axes="+Z дуло, +Y верх, −X правая сторона стрелка; начало — как у прежней модели игры",
               origin_source_m=[round(c, 5) for c in ORIGIN],
               markers_game_m={n: game_point(marks[n]) for n in ("Muzzle", "SightFront", "SightRear")},
               pivots_game_m={n: game_point(REC["pivots"][n]) for n in NODES},
               atlases={a: dict(size=v["size"], px_mm=v["report"]["px_mm_visible"], fill=v["report"]["fill"])
                        for a, v in REC["atlases"].items()},
               materials=[f"ASTEN919_{a}" for a in ("Slide", "Frame", "Magazine")])
    (OUT / "asten919.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    log("SAVED", OUT / "asten919.gltf", "tris", main_total, "lod1", lod_total, rep["markers_game_m"])


if __name__ == "__main__":
    main()
