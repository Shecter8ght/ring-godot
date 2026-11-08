"""Пожарная АЦ: файл просмотра отделки — развёрнутая форма с картами наборов из Painter, студия прямо в файле.

Материал детали — `FT_<набор>__<вид>`: карты набора (glTF из Painter: baseColor, occlusionRoughnessMetallic, normal)
в Principled; вид — по отделке слота (`render` карточки каталога): у автоэмали лак (coat), у стёкол и линз —
пропускание и IOR, остальное — как есть. Небо — HDRI переменной облачности (Poly Haven, CC0, assets/sky), площадка
асфальта под машиной, камера спереди слева, вьюпорт сразу Rendered — смотреть самому в Blender.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/tex_view.py -- <папка карт>[;<запасная папка>] <выход.blend> [worn]

worn — этап 2 (износ): лак эмали остаётся только там, где поверхность ещё гладкая (на выгоревшем, пыльном и в налёте
его нет), стекло пропускает меньше там, где грязное (матовее). Карты набора берутся из первой папки, где они есть.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(HERE).parents[1]
sys.path.insert(0, HERE)
import bpy  # noqa: E402

import tex_sets as T  # noqa: E402

SKY = ROOT / "assets/sky/kloofendal_48d_partly_cloudy_puresky.hdr"
CATALOG = ROOT / "tools/asset_kit/finish/finishes.json"


def image(path: Path, data: bool):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return im


def finishes():
    cat = {f["code"]: f for f in json.loads(CATALOG.read_text(encoding="utf-8"))["finishes"]}
    spec = json.loads((Path(T.MODEL_DIR) / "finish-spec.json").read_text(encoding="utf-8"))
    return {s["id"]: cat.get(s["finish"], {}) for s in spec["slots"]}


WORN = False


def _ramp(nt, src, a, b, top):
    """top при src ≤ a, 0 при src ≥ b (Map Range с ограничением)."""
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = a
    mr.inputs["From Max"].default_value = b
    mr.inputs["To Min"].default_value = top
    mr.inputs["To Max"].default_value = 0.0
    nt.links.new(src, mr.inputs["Value"])
    return mr.outputs["Result"]


def material(st: str, kind: str, f: dict, maps: Path):
    name = f"FT_{st}__{kind}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = image(maps / f"FT_{st}_baseColor.png", False)
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = image(maps / f"FT_{st}_occlusionRoughnessMetallic.png", True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = image(maps / f"FT_{st}_normal.png", True)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    for i, n in enumerate((col, orm, nrm)):
        n.location = (-800, 300 - 300 * i)
    sep.location, nmap.location = (-450, 0), (-450, -300)
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nt.links.new(nrm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    r = f.get("render") or {}
    if "coat" in r:
        w, rough, ior = r["coat"]
        bsdf.inputs["Coat Weight"].default_value = w
        if WORN:
            nt.links.new(_ramp(nt, sep.outputs["Green"], 0.22, 0.45, w), bsdf.inputs["Coat Weight"])
        bsdf.inputs["Coat Roughness"].default_value = rough
        bsdf.inputs["Coat IOR"].default_value = ior
    if "transmission" in r:
        bsdf.inputs["Transmission Weight"].default_value = r["transmission"]
        if WORN:
            nt.links.new(_ramp(nt, sep.outputs["Green"], 0.1, 0.75, r["transmission"]), bsdf.inputs["Transmission Weight"])
        bsdf.inputs["IOR"].default_value = r.get("ior", 1.5)
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
    return m


def studio(scene):
    w = bpy.data.worlds.new("Небо — переменная облачность")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(SKY), check_existing=True)
    mp = nt.nodes.new("ShaderNodeMapping")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value[2] = math.radians(140)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    scene.world = w
    # площадка асфальта
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0, 0, -0.007))
    g = bpy.context.object
    g.name = "Площадка"
    gm = bpy.data.materials.new("Асфальт (просмотр)")
    gm.use_nodes = True
    b = gm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.045, 0.045, 0.047, 1)
    b.inputs["Roughness"].default_value = 0.85
    g.data.materials.append(gm)
    # камера спереди слева, на высоте глаз
    cam = bpy.data.cameras.new("Камера")
    cam.lens = 35
    co = bpy.data.objects.new("Камера", cam)
    scene.collection.objects.link(co)
    from mathutils import Vector
    co.location = (5.6, -8.4, 1.75)
    co.rotation_euler = (Vector((0.0, -1.6, 1.45)) - co.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = co
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"


def main():
    global WORN
    a = sys.argv[sys.argv.index("--") + 1:]
    dirs, out = [Path(x) for x in a[0].split(";")], a[1]
    WORN = "worn" in a[2:]
    fin = finishes()
    missing = set()
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        st, slot = o.get("ft_set"), o.get("ft_slot")
        if not st:
            continue
        maps = next((d for d in dirs if (d / f"FT_{st}_baseColor.png").exists()), None)
        if maps is None:
            missing.add(st)
            continue
        f = fin.get(slot, {})
        r = f.get("render") or {}
        kind = "coat" if "coat" in r else ("glass" if "transmission" in r else "plain")
        m = material(st, kind, f, maps)
        o.material_slots[0].link = "OBJECT"
        o.material_slots[0].material = m
    studio(bpy.context.scene)
    # по умолчанию — «Целая» (рольставни и двери закрыты); «Отсеки открыты» включается галочкой в Outliner
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.collection.name == "Отсеки открыты":
            lc.exclude = True
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.clip_end = 500.0
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print("VIEW", out, "без карт:", sorted(missing))


if __name__ == "__main__":
    main()
