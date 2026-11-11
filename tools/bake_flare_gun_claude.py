"""Запекание игровых карт ракетницы Claude из слоёв UCUPaint и сборка игровых GLB с текстурами.

Источник вида — FlareGun_Claude_v02_ucupaint_worn_v01.blend (нативные слои, всё процедурное). Развёртка — принятая
«UVMap»: одно поле 0–1 на материал. На каждый материал пишутся цвет, нормаль (в касательном пространстве, вместе
со скруглением мелких кромок и рельефом слоёв) и ORM (R — затенение, G — шероховатость, B — металл).
Геометрия не меняется: в GLB уходит принятая сетка, меняются только материалы.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/bake_flare_gun_claude.py -- bake | glb
  bake → _asset_src/flare_gun_claude/textures/game_v01/<материал>_{albedo,normal,orm}.png
  glb  → _asset_src/flare_gun_claude/FlareGun_Claude_v02_game_textured.blend,
         assets/models/weapons/flare_gun_claude/{flare_gun_claude,flare_red_claude,flare_green_claude}.glb
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
MASTER = SRC / "FlareGun_Claude_v02_ucupaint_worn_v01.blend"
APPROVED = SRC / "approved/FlareGun_Claude_v02_game_APPROVED.blend"
TEX = SRC / "textures/game_v01"
GAME = SRC / "FlareGun_Claude_v02_game_textured.blend"
OUT = ROOT / "assets/models/weapons/flare_gun_claude"
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "bake"
SIZES = {"FlareGun_Body_Metal": 2048, "FlareGun_Small_Steel": 1024, "FlareGun_Bright_Steel": 512, "FlareGun_Grip_Plastic": 1024,
         "Flare_Case_Brass": 512, "Flare_Hull_Red": 512, "Flare_Hull_Green": 512, "Flare_Wad": 256}
SAMPLES = 96


def gpu(scene) -> None:
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    return
            except TypeError:
                continue
    except Exception as exc:
        print("BAKE gpu off:", exc, flush=True)


def bake() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = bpy.context.scene
    gpu(scene)
    scene.cycles.samples = SAMPLES
    scene.render.bake.margin = 8
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.use_clear = True
    TEX.mkdir(parents=True, exist_ok=True)
    meshes = [o for o in scene.objects if o.type == "MESH"]
    for ob in meshes:
        ob.hide_render = False
        ob.hide_set(False)
        ob.data.uv_layers.active = ob.data.uv_layers["UVMap"]
    setup: dict = {}
    for name, size in SIZES.items():
        mat = bpy.data.materials[name]
        nt = mat.node_tree
        group = next(n for n in nt.nodes if n.type == "GROUP")     # группа UCUPaint (без включённого аддона свойства yp нет)
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        target = nt.nodes.new("ShaderNodeTexImage")
        emit = nt.nodes.new("ShaderNodeEmission")
        setup[name] = {"nt": nt, "group": group, "bsdf": bsdf, "out": out, "target": target, "emit": emit, "size": size}

    def run(kind: str, suffix: str, colorspace: str, source: str | None) -> dict:
        """Один проход по всем материалам сразу. source — выход группы UCUPaint, который печём как излучение;
        None — обычный проход Cycles (нормаль, затенение) с настоящим шейдером."""
        images = {}
        for name, s in setup.items():
            img = bpy.data.images.new(f"{name}_{suffix}", s["size"], s["size"], alpha=False)
            img.colorspace_settings.name = colorspace
            s["target"].image = img
            s["nt"].nodes.active = s["target"]
            for link in list(s["out"].inputs["Surface"].links):
                s["nt"].links.remove(link)
            if source is None:
                s["nt"].links.new(s["bsdf"].outputs[0], s["out"].inputs["Surface"])
            else:
                s["nt"].links.new(s["group"].outputs[source], s["emit"].inputs["Color"])
                s["nt"].links.new(s["emit"].outputs[0], s["out"].inputs["Surface"])
            images[name] = img
        bpy.ops.object.select_all(action="DESELECT")
        for ob in meshes:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if kind == "NORMAL":
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        else:
            bpy.ops.object.bake(type=kind)
        print("BAKE pass", suffix, flush=True)
        return images

    color = run("EMIT", "albedo", "sRGB", "Color")
    metal = run("EMIT", "metal", "Non-Color", "Metallic")
    rough = run("EMIT", "rough", "Non-Color", "Roughness")
    normal = run("NORMAL", "normal", "Non-Color", None)
    scene.cycles.samples = 48
    occl = run("AO", "ao", "Non-Color", None)
    manifest: dict = {}
    for name, s in setup.items():
        size = s["size"]

        def px(img) -> np.ndarray:
            a = np.empty(size * size * 4, np.float32)
            img.pixels.foreach_get(a)
            return a.reshape(size, size, 4)

        orm = np.ones((size, size, 4), np.float32)
        orm[..., 0] = np.clip(px(occl[name])[..., 0] * 0.6 + 0.4, 0.0, 1.0)      # затенение мягче: в игре его добавит и свет
        orm[..., 1] = px(rough[name])[..., 0]
        orm[..., 2] = px(metal[name])[..., 0]
        img = bpy.data.images.new(f"{name}_orm", size, size, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(orm.ravel())
        files = {}
        for suffix, image in (("albedo", color[name]), ("normal", normal[name]), ("orm", img)):
            path = TEX / f"{name}_{suffix}.png"
            image.filepath_raw = str(path)
            image.file_format = "PNG"
            image.save()
            files[suffix] = path.name
            if suffix != "normal":                                   # рабочая копия для игры
                image.filepath_raw = str(path.with_suffix(".jpg"))
                image.file_format = "JPEG"
                image.save()
        manifest[name] = {"size": size, "files": files}
    (TEX / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BAKE done", len(manifest), flush=True)


def game_material(mat) -> None:
    """Игровой материал: Principled с запечёнными картами (ORM разбирается на шероховатость и металл)."""
    name = mat.name
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    def tex(suffix: str, colorspace: str):
        node = nt.nodes.new("ShaderNodeTexImage")
        ext = "png" if suffix == "normal" else "jpg"          # цвет и ORM — JPEG (иначе GLB в 40 МБ), нормаль без потерь
        node.image = bpy.data.images.load(str(TEX / f"{name}_{suffix}.{ext}"), check_existing=True)
        node.image.colorspace_settings.name = colorspace
        return node

    nt.links.new(tex("albedo", "sRGB").outputs["Color"], bsdf.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex("orm", "Non-Color").outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex("normal", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])


def glb() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(APPROVED))
    scene = bpy.context.scene
    for name in SIZES:
        game_material(bpy.data.materials[name])
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(GAME))
    OUT.mkdir(parents=True, exist_ok=True)

    def export(root, name: str) -> None:
        keep = root.location.copy()
        root.location = Vector((0, 0, 0))
        bpy.ops.object.select_all(action="DESELECT")
        stack = [root]
        while stack:
            ob = stack.pop()
            ob.select_set(True)
            stack.extend(ob.children)
        bpy.ops.export_scene.gltf(filepath=str(OUT / name), export_format="GLB", use_selection=True, export_yup=True,
                                  export_apply=True, export_animations=False, export_tangents=True, export_image_format="AUTO")
        root.location = keep

    export(bpy.data.objects["FlareGun_Claude"], "flare_gun_claude.glb")
    export(bpy.data.objects["Flare_Red_Claude"], "flare_red_claude.glb")
    export(bpy.data.objects["Flare_Green_Claude"], "flare_green_claude.glb")
    print("BAKE glb done", [round((OUT / n).stat().st_size / 1e6, 2) for n in ("flare_gun_claude.glb", "flare_red_claude.glb", "flare_green_claude.glb")], flush=True)


if MODE == "glb":
    glb()
else:
    bake()
