"""Купе Ильи: игровая модель предмета car_wheel — то же колесо, что на машине (решение владельца: колесо одно на
четыре места и оно же — найденный предмет).

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/wheel_item.py -- export | imports

Берёт игровую сетку колеса машины LOD0 (tools/coupe_ilya/game_lp.py → _asset_src/coupe_ilya_game/lp/Coupe_Game_LP.blend,
файл только читается): шина, лицо диска, обод, гайки, знак на колпачке; тормозной диск и суппорт остаются на машине.
Карты — атлас колеса машины, уже запечённый с принятой отделки tex_v01 (assets/models/props/coupe_ilya/coupe_ilya_wheel_*):
вид у колеса на машине и у предмета один.
  export  → assets/items/models/car/car_wheel.glb (+ .json); просмотр — <библиотека>/game/Wheel_Ilya_Game_v01.blend
  imports — после `tools/godot.cmd --headless --import`: сжатие карт как у ПМ и кузова; затем импорт ещё раз
Предмет лежит плашмя лицом диска вверх (ось колеса — вертикаль): так его кладут на полку и так он падает на пол;
начало — по центру на нижней грани шины.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
LP_FILE = ROOT / "_asset_src/coupe_ilya_game/lp/Coupe_Game_LP.blend"
MAPS = ROOT / "assets/models/props/coupe_ilya"
OUT = ROOT / "assets/items/models/car"
VIEW = Path("E:/Models Blender/VEHICLES/Купе Ильи/game/Wheel_Ilya_Game_v01.blend")
PARTS = ("Tire_FL", "Rim_Face_FL", "Rim_Barrel_FL", "Lug_Nuts_FL", "Center_Badge_FL")
UV = "GameUV"
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "export"
log = lambda *a: print("WHEEL_ITEM", *a, flush=True)  # noqa: E731


def material() -> bpy.types.Material:
    """Материал на картах колеса машины: albedo, ORM (AO / шероховатость / металл), нормали OpenGL."""
    m = bpy.data.materials.new("GAME • car_wheel")
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = UV

    def tex(kind: str, space: str):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(MAPS / f"coupe_ilya_wheel_{kind}.png"), check_existing=True)
        t.image.colorspace_settings.name = space
        t.image.name = f"car_wheel_{kind}"
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t

    nt.links.new(tex("albedo", "sRGB").outputs["Color"], p.inputs["Base Color"])
    orm = tex("orm", "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], p.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = UV
    nt.links.new(tex("normal", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    g = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [s.name for s in g.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]:
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = g
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    return m


def export() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(LP_FILE))          # только чтение: файл машины не сохраняется
    keep = [bpy.data.objects[n] for n in PARTS]
    scene = bpy.context.scene
    mat = material()
    obs = []
    for o in keep:
        c = bpy.data.objects.new(o.name.replace("_FL", ""), o.data.copy())
        scene.collection.objects.link(c)
        c.data.materials.clear()
        c.data.materials.append(mat)
        obs.append(c)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = mesh.data.name = "Car_Wheel_Mesh"
    # ось колеса +X (наружу, лицо диска) → вверх; низ шины — на ноль
    mesh.data.transform(Matrix.Rotation(math.radians(-90.0), 4, "Y"))
    zmin = min(v.co.z for v in mesh.data.vertices)
    mesh.data.transform(Matrix.Translation((0.0, 0.0, -zmin)))
    mesh.data.update()
    root = bpy.data.objects.new("Car_Wheel", None)
    scene.collection.objects.link(root)
    mesh.parent = root
    mesh["source"] = ("игровое колесо машины LOD0 (tools/coupe_ilya/game_lp.py), карты — атлас колеса машины "
                      "(отделка tex_v01 принята 2026-10-18); tools/coupe_ilya/wheel_item.py")
    mesh.data.calc_loop_triangles()
    tris = len(mesh.data.loop_triangles)
    xs = [v.co.x for v in mesh.data.vertices]
    zs = [v.co.z for v in mesh.data.vertices]
    OUT.mkdir(parents=True, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (root, mesh))
    glb = OUT / "car_wheel.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_tangents=True, export_extras=True, export_animations=False,
                              export_cameras=False, export_lights=False, export_image_format="AUTO")
    manifest = {
        "item": "car_wheel", "source_lp": str(LP_FILE.relative_to(ROOT)).replace("\\", "/"), "parts": list(PARTS),
        "triangles": tris, "size_m": {"diameter": round(max(xs) - min(xs), 3), "width": round(max(zs) - min(zs), 3)},
        "maps": "атлас колеса машины 2048×2048: albedo (sRGB), normal (OpenGL), orm (R — AO, G — шероховатость, B — металл)",
        "axes": "лежит плашмя: ось колеса — вертикаль (Godot Y), лицо диска вверх; начало — центр нижней грани шины",
        "lod": "автоматические LOD движка при импорте (как у остальных предметов)",
    }
    (OUT / "car_wheel.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8",
                                        newline="\n")
    log("экспорт", glb, "треугольников", tris, "диаметр", manifest["size_m"], hashlib.sha256(glb.read_bytes()).hexdigest()[:16])
    for o in list(bpy.data.objects):                           # в файл просмотра — только предмет
        if o not in (root, mesh):
            bpy.data.objects.remove(o)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    VIEW.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(VIEW))
    log("просмотр", VIEW)


def imports() -> None:
    """Сжатие VRAM и mip-уровни; нормали — флаг карты нормалей; у ORM — сглаживание шероховатости (G) по нормали."""
    def setp(text: str, key: str, val: str) -> str:
        pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
        assert pat.search(text), key
        return pat.sub(f"{key}={val}", text)
    res = "res://assets/items/models/car/"
    for f in sorted(OUT.glob("car_wheel_*.png.import")):
        base = f.name[: -len(".import")]
        t = f.read_text(encoding="utf-8")
        t = setp(t, "compress/mode", "2")
        t = setp(t, "mipmaps/generate", "true")
        t = setp(t, "detect_3d/compress_to", "0")
        if base.endswith("_normal.png"):
            t = setp(t, "compress/normal_map", "1")
        elif base.endswith("_orm.png"):
            t = setp(t, "roughness/mode", "3")
            t = setp(t, "roughness/src_normal", f'"{res}{base.replace("_orm.png", "_normal.png")}"')
        f.write_text(t, encoding="utf-8", newline="\n")
        log("импорт", f.name)


if __name__ == "__main__":
    {"export": export, "imports": imports}[MODE]()
