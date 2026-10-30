# Каталог отделок: карточки и файл каталога в Blender по картам, выгруженным стеком Painter (sp_finish.card).
#   blender --background --factory-startup --python-exit-code 1 --python tools/asset_kit/finish/render_cards.py --
#       --catalog "<папка каталога>" [--codes A,B] [--cards] [--blend] [--samples 128] [--size 1500x1000]
# --cards — два кадра на отделку: студия как в интернет-магазине (светло-серый фон, софтбоксы) и улица днём (небо
# с солнцем — там виден настоящий блеск); выбор владельца 2026-10-30. --blend — Каталог_отделок.blend: все образцы
# рядом с подписями-кодами, сцены «Студия» и «Улица». Материал — Principled по картам glTF (baseColor sRGB,
# ORM: G — шероховатость, B — металличность, нормали OpenGL) и особые свойства из каталога (render: лак, стекло,
# тонкая плёнка, бархат), которые картами не передаются.
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
CATALOG_JSON = ROOT / "tools/asset_kit/finish/finishes.json"
SAMPLE = ROOT / "_asset_src/finish_catalog/sample/finish_sample.blend"
STUDIO_HDR = Path(bpy.utils.resource_path("LOCAL")) / "datafiles/studiolights/world/studio.exr"
SKY_HDR = ROOT / "assets/sky/kloppenheim_03_puresky.hdr"      # ясный полдень, солнце 59° (Poly Haven, CC0)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"catalog": None, "codes": None, "cards": False, "blend": False, "samples": 128, "size": (1500, 1000)}
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--catalog":
            out["catalog"] = Path(a[i + 1]).resolve()
            i += 1
        elif k == "--codes":
            out["codes"] = a[i + 1].split(",")
            i += 1
        elif k == "--samples":
            out["samples"] = int(a[i + 1])
            i += 1
        elif k == "--size":
            w, h = a[i + 1].split("x")
            out["size"] = (int(w), int(h))
            i += 1
        elif k in ("--cards", "--blend"):
            out[k[2:]] = True
        i += 1
    return out


def load_sample():
    with bpy.data.libraries.load(str(SAMPLE), link=False) as (src, dst):
        dst.objects = ["FinishSample"]
    ob = dst.objects[0]
    return ob


def image(path, data):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return im


def material(f, maps: Path, rel_to: Path = None):
    """Principled по картам карточки + особые свойства каталога (render)."""
    m = bpy.data.materials.new(f["code"])
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    out = nt.nodes["Material Output"]
    stem = "FinishSample"
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = image(maps / f"{stem}_baseColor.png", False)
    col.location = (-700, 300)
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = image(maps / f"{stem}_occlusionRoughnessMetallic.png", True)
    orm.location = (-700, 0)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-400, 0)
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = image(maps / f"{stem}_normal.png", True)
    nrm.location = (-700, -300)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-400, -300)
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
        bsdf.inputs["Coat Roughness"].default_value = rough
        bsdf.inputs["Coat IOR"].default_value = ior
    if "transmission" in r:
        bsdf.inputs["Transmission Weight"].default_value = r["transmission"]
    if "ior" in r:
        bsdf.inputs["IOR"].default_value = r["ior"]
    if "thin_film" in r:
        bsdf.inputs["Thin Film Thickness"].default_value = r["thin_film"][0]
        bsdf.inputs["Thin Film IOR"].default_value = r["thin_film"][1]
    if "sheen" in r:
        bsdf.inputs["Sheen Weight"].default_value = r["sheen"][0]
        bsdf.inputs["Sheen Roughness"].default_value = r["sheen"][1]
    for im in (col.image, orm.image, nrm.image):
        if rel_to is not None:
            im.filepath = bpy.path.relpath(bpy.path.abspath(im.filepath), start=str(rel_to))
    return m


def world_studio(name="Студия", strength=0.35):
    """Студия магазина: свет и отражения — студийная HDRI Blender, камера видит ровный светло-серый фон."""
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(STUDIO_HDR), check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    flat = nt.nodes.new("ShaderNodeBackground")
    flat.inputs["Color"].default_value = (0.62, 0.62, 0.63, 1.0)
    flat.inputs["Strength"].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(flat.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def world_sky(name="Улица"):
    """Улица днём: небо Poly Haven с солнцем в панораме (ясный полдень), земля — плоскость в сцене."""
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(95.0))    # солнце сзади-слева от камеры
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(SKY_HDR), check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def softbox(name, loc, rot, size, energy, coll):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = energy
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def frame(scene, cam, ob, direction, margin):
    """Камера по направлению direction так, чтобы габарит образца вошёл в кадр с запасом margin."""
    scene.render.resolution_x, scene.render.resolution_y = scene.render.resolution_x, scene.render.resolution_y
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    center = sum(pts, Vector()) / 8
    d = direction.normalized()
    cam.location = center + d * 1.0
    look_at(cam, center)
    bpy.context.view_layer.update()
    loc, _scale = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), [c for p in pts for c in p])
    cam.location = center + (Vector(loc) - center) * margin


def ground(name, size, z, color, coll):
    me = bpy.data.meshes.new(name)
    s = size / 2
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = 0.8
    me.materials.append(m)
    coll.objects.link(ob)
    return ob


def setup_render(scene, samples, size):
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for t in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = t
                prefs.get_devices()
                for d in prefs.devices:
                    d.use = d.type != "CPU"
                scene.cycles.device = "GPU"
                break
            except Exception:
                continue
    except Exception:
        pass
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"   # по одной картинке шумодав смывает фактуру (AR-15)
    scene.cycles.denoising_prefilter = "ACCURATE"
    scene.cycles.denoising_use_gpu = False                     # Painter держит видеопамять — шумодав на GPU падал
    scene.cycles.preview_samples = 64
    scene.cycles.use_preview_denoising = True
    scene.cycles.preview_denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 92


def cards(cfg, finishes):
    cat = cfg["catalog"]
    outdir = cat / "Карточки"
    outdir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    setup_render(scene, cfg["samples"], cfg["size"])
    coll = scene.collection
    ob = load_sample()
    coll.objects.link(ob)
    # образец 170 × 36 мм: камера 3/4 спереди-слева-сверху — видны паз, карман, ось, винт, гайка, ствол
    cam_d = bpy.data.cameras.new("Камера")
    cam_d.lens = 85
    cam = bpy.data.objects.new("Камера", cam_d)
    coll.objects.link(cam)
    scene.camera = cam
    frame(scene, cam, ob, Vector((0.32, -0.80, 0.50)), 1.10)
    studio = world_studio()
    sky = world_sky()
    lights = bpy.data.collections.new("Софтбоксы")
    coll.children.link(lights)
    softbox("Ключевой", (-0.25, -0.30, 0.35), (0, 0, 0), (0.35, 0.25), 4.0, lights)
    softbox("Заполняющий", (0.35, -0.25, 0.12), (0, 0, 0), (0.30, 0.30), 1.2, lights)
    softbox("Контровой", (0.05, 0.35, 0.30), (0, 0, 0), (0.40, 0.12), 2.5, lights)
    for lo in lights.objects:
        look_at(lo, (0, 0, 0))
    gnd = ground("Земля", 40.0, -0.0125, (0.22, 0.21, 0.20), coll)
    for f in finishes:
        maps = cat / "Карты" / f["code"]
        if not (maps / "FinishSample_baseColor.png").exists():
            print("NO MAPS", f["code"])
            continue
        ob.data.materials.clear()
        ob.data.materials.append(material(f, maps))
        for kind, w, show_lights, show_ground in (("studio", studio, True, False), ("outdoor", sky, False, True)):
            scene.world = w
            lights.hide_render = not show_lights
            gnd.hide_render = not show_ground
            scene.render.filepath = str(outdir / f"{f['code']}_{kind}.jpg")
            bpy.ops.render.render(write_still=True)
        print("CARD", f["code"], flush=True)


def blend(cfg, finishes):
    """Каталог_отделок.blend: группы рядами, в ряду образцы с подписями; сцены «Студия» и «Улица» видят одну
    коллекцию образцов. Карты — относительными путями из папки каталога."""
    cat = cfg["catalog"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = {g["id"]: g for g in json.loads(CATALOG_JSON.read_text(encoding="utf-8"))["groups"]}
    s1 = bpy.context.scene
    s1.name = "Студия"
    setup_render(s1, cfg["samples"], cfg["size"])
    samples = bpy.data.collections.new("Образцы")
    s1.collection.children.link(samples)
    proto = load_sample()
    text_m = bpy.data.materials.new("Подпись")
    text_m.use_nodes = True
    text_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
    text_m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    step_x, step_y = 0.24, 0.20
    rows = []
    for f in finishes:
        if not rows or rows[-1][0] != f["group"]:
            rows.append((f["group"], []))
        rows[-1][1].append(f)
    bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
    for r, (gid, items) in enumerate(rows):
        y = -r * step_y
        gc = bpy.data.collections.new(groups[gid]["title"])
        samples.children.link(gc)
        t = bpy.data.curves.new(f"Группа {gid}", "FONT")
        t.body = groups[gid]["title"]
        t.size = 0.016
        t.align_x = "RIGHT"
        to = bpy.data.objects.new(f"Группа {gid}", t)
        to.location = (-0.13, y - 0.005, -0.012)
        to.data.materials.append(text_m)
        gc.objects.link(to)
        for i, f in enumerate(items):
            maps = cat / "Карты" / f["code"]
            if not (maps / "FinishSample_baseColor.png").exists():
                continue
            ob = proto.copy()
            ob.data = proto.data.copy()
            ob.name = f["code"]
            ob.data.materials.clear()
            ob.data.materials.append(material(f, maps, rel_to=cat))
            ob.location = (i * step_x, y, 0.0)
            gc.objects.link(ob)
            lab = bpy.data.curves.new("Подпись " + f["code"], "FONT")
            lab.body = f"{f['code']}\n{f['title']}"
            lab.size = 0.0085
            lab.align_x = "CENTER"
            lo = bpy.data.objects.new("Подпись " + f["code"], lab)
            lo.location = (i * step_x - 0.02, y - 0.050, -0.012)
            lo.data.materials.append(text_m)
            gc.objects.link(lo)
    gnd = ground("Стол", 30.0, -0.0125, (0.55, 0.55, 0.56), s1.collection)
    s1.world = world_studio(strength=1.0)        # в файле софтбоксов нет — свет только от студийной HDRI
    s2 = bpy.data.scenes.new("Улица")
    setup_render(s2, cfg["samples"], cfg["size"])
    s2.collection.children.link(samples)
    s2.collection.objects.link(gnd)
    s2.world = world_sky()
    s2.unit_settings.length_unit = "MILLIMETERS"
    for img in bpy.data.images:
        if img.filepath and not img.filepath.startswith("//"):
            try:
                img.filepath = bpy.path.relpath(img.filepath, start=str(cat))
            except ValueError:
                pass
    # окно: вид сверху-спереди на первые ряды, сразу «Material Preview» со светом и миром сцены (быстрее Cycles на
    # 57 образцах; «Rendered» — Cycles, как карточки); мелкие образцы — ближняя граница отсечения 1 мм
    from mathutils import Euler
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            sp = area.spaces[0]
            sp.shading.type = "MATERIAL"
            sp.shading.use_scene_world = True
            sp.shading.use_scene_lights = True
            sp.clip_start = 0.001
            sp.clip_end = 100.0
            r3d = sp.region_3d
            r3d.view_perspective = "PERSP"
            r3d.view_location = (0.55, -0.35, 0.0)
            r3d.view_distance = 1.1
            r3d.view_rotation = Euler((1.0, 0.0, 0.0)).to_quaternion()
    path = cat / "Каталог_отделок.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True)
    print("BLEND", path, flush=True)


def main():
    cfg = args()
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    finishes = [f for f in data["finishes"] if not cfg["codes"] or f["code"] in cfg["codes"]]
    if cfg["cards"]:
        cards(cfg, finishes)
    if cfg["blend"]:
        blend(cfg, finishes)


main()
