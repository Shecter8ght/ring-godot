"""Купе Ильи: игровая модель в GLB — узлы состояний, три LOD, материалы на запечённых картах.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/game_export.py

Из _asset_src/coupe_ilya_game/lp/Coupe_Game_LP.blend (game_lp.py) и карт maps/game (game_pack.py) →
  assets/models/props/coupe_ilya/coupe_ilya.glb  — корень Coupe_Ilya (Blender −Y перёд → в Godot перёд по +Z,
      начало — центр машины на земле), узлы:
        Body               — неподвижное (кузов, стёкла, салон, отсек без аккумулятора, тормоза всех колёс);
        Hood               — капот с внутренней панелью, начало на петле: открыт — поворот −0,87 рад вокруг X;
        Wheel_FL/FR/RL/RR  — колёса (одна сетка на четыре); Wheel_FL — состояние «колесо стоит»;
        WheelOff_FL        — кирпичи и поворотный кулак (колесо снято);
        Battery_Installed  — аккумулятор, клеммы на нём, экраны горят;
        Battery_Missing    — висящие клеммы, тёмные экраны;
      в каждом узле — сетки <узел>_LOD0/1/2 (дальности включает сцена, см. src/world/ilya_car.gd);
  assets/models/props/coupe_ilya/coupe_ilya.json — состав, треугольники, источники;
  E:/Models Blender/VEHICLES/Купе Ильи/game/Coupe_Ilya_Game_v01.blend — файл просмотра (карты встроены).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src/coupe_ilya_game"
REC = json.loads((WORK / "lp/parts.json").read_text(encoding="utf-8"))
MAPS = WORK / "maps/game"
OUT = ROOT / "assets/models/props/coupe_ilya"
OUT.mkdir(parents=True, exist_ok=True)
VIEW = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\game\Coupe_Ilya_Game_v01.blend")
VIEW.parent.mkdir(parents=True, exist_ok=True)
HOOD_OPEN_RAD = -0.87
DOUBLE_SIDED = {"body", "glass", "bay", "interior"}      # одинарные листы панелей: изнутри и из отсека видны
log = lambda *a: print("COUPE_EXPORT", *a, flush=True)

bpy.ops.wm.open_mainfile(filepath=str(WORK / "lp/Coupe_Game_LP.blend"))
bpy.context.preferences.use_preferences_save = False
O = bpy.data.objects


# --- материалы ---------------------------------------------------------------------------------------
def atlas_material(atlas: str) -> None:
    m = bpy.data.materials[f"GAME • {atlas}"]
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "GameUV"

    def tex(kind: str, cs: str):
        t = nt.nodes.new("ShaderNodeTexImage")
        # имя картинки в GLB — имя файла; Godot извлечёт её рядом с моделью как coupe_ilya_<атлас>_<канал>.png
        t.image = bpy.data.images.load(str(MAPS / f"{atlas}_{kind}.png"), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t

    alb = tex("albedo", "sRGB")
    nt.links.new(alb.outputs["Color"], p.inputs["Base Color"])
    if atlas == "glass":
        nt.links.new(alb.outputs["Alpha"], p.inputs["Alpha"])
        m.surface_render_method = "BLENDED"
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
    m.use_backface_culling = atlas not in DOUBLE_SIDED


for a in REC["atlas_size"]:
    atlas_material(a)
for m in bpy.data.materials:
    if m.name.startswith("GAME • const"):
        m.use_backface_culling = False

# --- узлы ----------------------------------------------------------------------------------------------
STATE_NODE = {"State_Wheel_FL_Off": "WheelOff_FL", "State_Battery_Installed": "Battery_Installed",
              "State_Battery_Missing": "Battery_Missing"}


def node_of(name: str) -> str:
    info = REC["objects"][name]
    parent, coll = info["parent"], info["collection"]
    if parent == "Hood_Hinge":
        return "Hood"
    if parent.startswith("Wheel_"):
        return "Body" if name.startswith(("Brake_Disc", "Caliper")) else parent
    return STATE_NODE.get(coll, "Body")


root = bpy.data.objects.new("Coupe_Ilya", None)
bpy.context.scene.collection.objects.link(root)
nodes: dict[str, bpy.types.Object] = {}
for n in ("Body", "Hood", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR", "WheelOff_FL", "Battery_Installed",
          "Battery_Missing"):
    e = bpy.data.objects.new(n, None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = root
    src = {"Hood": "Hood_Hinge"}.get(n, n if n.startswith("Wheel_") else None)
    if src and src in O:
        e.matrix_world = O[src].matrix_world.copy()
    nodes[n] = e
bpy.context.view_layer.update()


def merged(objs, node_obj, name: str) -> bpy.types.Mesh:
    """Сетки деталей одной сеткой в координатах узла (материалы — поверхностями)."""
    import bmesh
    bm = bmesh.new()
    inv = node_obj.matrix_world.inverted()
    mats: list[bpy.types.Material] = []
    for o in objs:
        me = o.data.copy()
        me.transform(inv @ o.matrix_world)
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for p in me.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in mats:
        out.materials.append(m)
    return out


tris_report: dict[str, list[int]] = {}
for lod in range(3):
    suffix = "" if lod == 0 else f"_LOD{lod}"
    groups: dict[str, list] = {}
    for name in REC["objects"]:
        o = O.get(name + suffix)
        if o is None:
            continue
        groups.setdefault(node_of(name), []).append(o)
    wheel_mesh = None
    for n, objs in groups.items():
        if n.startswith("Wheel_") and n != "Wheel_FL":
            continue                                    # колёса — одна сетка с переднего левого
        me = merged(objs, nodes[n], f"{n if not n.startswith('Wheel_') else 'Wheel'}_LOD{lod}")
        if n == "Wheel_FL":
            wheel_mesh = me
            targets = [k for k in ("Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR")]
        else:
            targets = [n]
        for t in targets:
            mo = bpy.data.objects.new(f"{t}_LOD{lod}", me)
            bpy.context.scene.collection.objects.link(mo)
            mo.parent = nodes[t]
        me.calc_loop_triangles()
        tris_report.setdefault(n if not n.startswith("Wheel_") else "Wheel(×4)", []).append(len(me.loop_triangles))
log("треугольники по узлам", tris_report)

# только игровое дерево
keep = {root.name} | {o.name for o in root.children_recursive}
for o in list(O):
    if o.name not in keep:
        O.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
# имена Hood, Wheel_FL, Hood_LOD1… были заняты деталями исходника — новые узлы получили «.001»; теперь они свободны
for o in [root] + list(root.children_recursive):
    clean = re.sub(r"\.\d{3}$", "", o.name)
    if clean != o.name:
        o.name = clean
        assert o.name == clean, clean
bpy.context.view_layer.update()
lod_tris = {}
for lod in range(3):
    t = 0
    for o in root.children_recursive:
        if o.type == "MESH" and o.name.endswith(f"_LOD{lod}"):
            o.data.calc_loop_triangles()
            t += len(o.data.loop_triangles)
    lod_tris[f"LOD{lod}"] = t
log("LOD", lod_tris)


def export(path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in [root] + list(root.children_recursive):
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_tangents=True, export_extras=True, export_animations=False,
                              export_cameras=False, export_lights=False, export_image_format="AUTO")
    log("экспорт", path)


export(OUT / "coupe_ilya.glb")
size = root.children_recursive
manifest = {
    "source": REC["source"], "source_sha256": REC["source_sha256"],
    "budget_owner": "ближняя ~150 тыс., дальше 50 и 12 тыс.; карты 4K кузов, 2K остальное (владелец 2026-10-18)",
    "triangles": lod_tris, "nodes_triangles": tris_report,
    "atlases": {a: s for a, s in REC["atlas_size"].items()},
    "axes": "Blender −Y перёд → Godot +Z; +X — левый борт машины (порог с приметой); начало — центр на земле",
    "hood": {"node": "Hood", "axis": "X", "open_rad": HOOD_OPEN_RAD},
    "states": {"wheel_fitted": ["Wheel_FL"], "wheel_removed": ["WheelOff_FL"],
               "battery_installed": ["Battery_Installed"], "battery_missing": ["Battery_Missing"]},
    "materials": {"GAME • body": "атлас кузова 4K", "GAME • glass": "стёкла, прозрачность в альфе цвета",
                  "GAME • wheel": "колесо, кирпичи, кулак", "GAME • bay": "моторный отсек, аккумулятор",
                  "GAME • interior": "салон", "GAME • const • …": "светящиеся и зеркальные мелочи без карт"},
}
(OUT / "coupe_ilya.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
# файл просмотра в библиотеке: карты встроены
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(VIEW))
log("просмотр", VIEW, hashlib.sha256((OUT / "coupe_ilya.glb").read_bytes()).hexdigest()[:16])
