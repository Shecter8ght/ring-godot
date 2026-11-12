# АСТЕН-919, текстуры этап 1: карты из Substance Painter → файл просмотра владельцу в Blender, со студией прямо в
# файле (по образцу tools/ar15/tex_apply.py: HDRI только в отражениях, тёмный фон, неподвижные мягкие источники, камера,
# Cycles, вьюпорт в Rendered). Геометрия, развёртка и ASTEN919_Controls — из файла развёртки без изменений; меняются
# только материалы: материал на набор текстур, карты — внешние PNG по относительным путям.
#   apply <папка карт> <out.blend>                 — файл просмотра
#   shots <папка снимков> [samples] [вид,вид]      — снимки для самопроверки (на файле просмотра)
# blender --background <АСТЕН-919_развёртка_v01.blend> --factory-startup --python-exit-code 1 --python tools/asten919/tex_review.py -- apply <папка> <out>
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import tex_sets as T  # noqa: E402

HDRI = "E:/Games/RING-godot/_asset_src/pm_game/sources/studio_small_09_1k.hdr"   # Poly Haven, CC0
CENTER = Vector((0.02, 0.0, -0.045))


def material(s, folder):
    m = bpy.data.materials.get(f"АСТЕН-919 • {s}") or bpy.data.materials.new(f"АСТЕН-919 • {s}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location = (600, 0)
    b.location = (300, 0)
    if not os.path.exists(os.path.join(folder, f"{s}_baseColor.png")):
        b.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)     # набора нет в выгрузке — серая глина
        b.inputs["Roughness"].default_value = 0.6
        return m

    def img(suffix, noncolor, y):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(folder, f"{s}_{suffix}.png"), check_existing=True)
        t.image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        t.interpolation = "Cubic"
        t.location = (-500, y)
        return t
    bc = img("baseColor", False, 300)
    orm = img("occlusionRoughnessMetallic", True, 0)
    nm = img("normal", True, -300)
    nt.links.new(bc.outputs[0], b.inputs["Base Color"])
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    sp.location = (-150, 0)
    nt.links.new(orm.outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], b.inputs["Metallic"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-150, -300)
    nt.links.new(nm.outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], b.inputs["Normal"])
    return m


def studio():
    """Студия для просмотра владельцем: HDRI только в отражениях, тёмный фон, четыре неподвижных мягких источника
    вокруг пистолета, камера 3/4, Cycles, вьюпорт в Rendered."""
    S = bpy.context.scene
    coll = bpy.data.collections.get("Студия просмотра")
    if coll is None:
        coll = bpy.data.collections.new("Студия просмотра")
        S.collection.children.link(coll)
    w = bpy.data.worlds.new("АСТЕН-919 • Студия")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    env.image.pack()
    mp = nt.nodes.new("ShaderNodeMapping")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    mp.inputs["Rotation"].default_value = (0, 0, 2.2)
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    bg_env = nt.nodes.new("ShaderNodeBackground")
    bg_env.label = "Отражения студии (сила)"
    bg_env.inputs["Strength"].default_value = 0.6
    nt.links.new(env.outputs["Color"], bg_env.inputs["Color"])
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.label = "Фон за пистолетом"
    bg_cam.inputs["Color"].default_value = (0.012, 0.012, 0.012, 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_env.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    S.world = w

    def light(name, direction, dist, energy, size, size_y=None):
        d = bpy.data.lights.new(name, "AREA")
        d.energy = energy
        d.shape = "RECTANGLE" if size_y else "DISK"
        d.size = size
        if size_y:
            d.size_y = size_y
        o = bpy.data.objects.new(name, d)
        coll.objects.link(o)
        o.location = CENTER + Vector(direction).normalized() * dist
        o.rotation_euler = (CENTER - o.location).to_track_quat("-Z", "Y").to_euler()
        return o

    # пистолет втрое короче винтовки — источники ближе и слабее (освещённость та же)
    light("Студия • ключевой (справа спереди сверху)", (0.45, -0.75, 0.70), 0.75, 11, 0.45)
    light("Студия • заполняющий (слева)", (-0.30, 0.90, 0.20), 0.8, 3.0, 0.55)
    light("Студия • контровой (сзади сверху)", (-0.60, 0.30, 0.80), 0.7, 8, 0.28)
    light("Студия • полоса бликов (сверху)", (0.0, -0.35, 1.0), 0.6, 6.5, 0.7, 0.06)
    cd = bpy.data.cameras.new("Студия • камера")
    cd.lens = 70
    cd.clip_start = 0.005
    cam = bpy.data.objects.new("Студия • камера", cd)
    coll.objects.link(cam)
    cam.location = CENTER + Vector((0.40, -0.85, 0.30)).normalized() * 0.62
    cam.rotation_euler = (CENTER - cam.location).to_track_quat("-Z", "Y").to_euler()
    S.camera = cam
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 128
    S.cycles.preview_samples = 64
    S.cycles.use_denoising = True
    S.cycles.use_preview_denoising = True
    S.cycles.denoising_use_gpu = False      # Painter держит видеопамять — шумоподавление на процессоре
    for pre in ("", "preview_"):            # шумоподавление по цвету и нормалям: не смывает мелкое зерно покрытия
        setattr(S.cycles, pre + "denoising_input_passes", "RGB_ALBEDO_NORMAL")
        setattr(S.cycles, pre + "denoising_prefilter", "ACCURATE")
    S.render.resolution_x, S.render.resolution_y = 1920, 1080
    S.render.film_transparent = False
    S.view_settings.view_transform = "AgX"
    S.view_settings.look = "AgX - Punchy"
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.clip_start = 0.002


def apply(folder, out):
    mats = {s: material(s, folder) for s in T.SETS}
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH" or "asten_set" not in o:
            continue
        m = mats[o["asten_set"]]
        if o.data.users > 1 and o.data.name == T.SHARED and o.data.materials and o.data.materials[0] == m:
            continue                                # общая сетка патрона уже переведена
        slots = max(1, len(o.data.materials))
        o.data.materials.clear()
        for _ in range(slots):
            o.data.materials.append(m)
        n += 1
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    for o in list(bpy.data.objects):                # камеры проверочных видов формы
        if o.type == "CAMERA":
            bpy.data.objects.remove(o, do_unlink=True)
    studio()
    bpy.context.preferences.filepaths.save_version = 0      # без .blend1 рядом с выдачей
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    print("APPLIED", n, "объектов →", out)


VIEWS = {
    # имя: (направление от центра к камере, расстояние, фокусное, точка взгляда)
    "01_справа_3-4": ((0.40, -0.85, 0.30), 0.62, 70, CENTER),
    "02_слева_3-4": ((0.40, 0.85, 0.30), 0.62, 70, CENTER),
    "03_слева_сбоку": ((0.0, 1.0, 0.03), 0.70, 70, CENTER),
    "04_затвор_слева_крупно": ((0.10, 0.95, 0.30), 0.26, 70, Vector((0.0, 0.0, 0.0))),
    "05_рукоять_справа": ((0.25, -0.95, 0.05), 0.28, 70, Vector((-0.045, 0.0, -0.075))),
    "06_органы_слева": ((0.05, 1.0, 0.10), 0.17, 70, Vector((-0.012, 0.0, -0.022))),
    "07_сзади_прицел": ((-1.0, 0.12, 0.18), 0.30, 70, Vector((-0.07, 0.0, 0.0))),
    "08_дуло": ((1.0, -0.35, 0.15), 0.26, 70, Vector((0.11, 0.0, -0.005))),
}


def shots(folder, samples=64, only=None):
    S = bpy.context.scene
    os.makedirs(folder, exist_ok=True)
    cam = S.camera
    S.cycles.samples = samples
    for name, (d, dist, lens, at) in VIEWS.items():
        if only and name.split("_")[0] not in only and name not in only:
            continue
        cam.data.lens = lens
        cam.location = at + Vector(d).normalized() * dist
        cam.rotation_euler = (at - cam.location).to_track_quat("-Z", "Y").to_euler()
        S.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "apply":
        apply(a[1], a[2])
    elif a[0] == "shots":
        import addon_utils
        prefs = bpy.context.preferences
        addon_utils.enable("cycles")
        cp = prefs.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):          # при --factory-startup устройства Cycles выключены
            try:
                cp.compute_device_type = kind
                cp.get_devices()
                for dv in cp.devices:
                    dv.use = dv.type != "CPU"
                break
            except Exception:      # noqa: BLE001
                continue
        bpy.context.scene.cycles.device = "GPU"
        shots(a[1], int(a[2]) if len(a) > 2 else 64, a[3].split(",") if len(a) > 3 else None)
