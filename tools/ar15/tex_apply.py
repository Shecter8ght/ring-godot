# AR-15 «ГРАНЬ-15», этап 1 текстур: карты из Substance Painter → файлы просмотра владельцу в Blender, по варианту
# основы на файл (AR-15_текстуры_этап1_<вариант>.blend рядом с геометрией), со студией прямо в файле (как у ВЕРАС-54:
# студийная HDRI отражениями и тёмный фон, неподвижные мягкие источники, камера, Cycles, вьюпорт в Rendered).
# Геометрия, развёртка, риг AR15_Controls — из AR15_uv_v01.blend без изменений; меняются только материалы:
# материал на набор текстур (AR15_<набор>), карты — внешние PNG по относительным путям из папки варианта.
#   apply <вариант> <папка карт> <out.blend> [папка нормалей] — файл варианта (нормали у вариантов общие)
#   shots <out.blend> <папка снимков> [samples]  — нейтральные снимки файла варианта (открыть файл и вызвать)
# blender --background <AR15_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/ar15/tex_apply.py -- apply A <папка> <out>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import tex_sets as T  # noqa: E402

HDRI = "E:/Games/RING-godot/_asset_src/pm_game/sources/studio_small_09_1k.hdr"   # Poly Haven, CC0
CENTER = Vector((-0.02, 0.0, -0.04))


def material(s, folder, normal_dir=None):
    m = bpy.data.materials.get(f"AR15_{s}") or bpy.data.materials.new(f"AR15_{s}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location = (600, 0)
    b.location = (300, 0)
    if not os.path.exists(os.path.join(folder, f"{s}_baseColor.png")):
        # набора нет в выгрузке (пробная выгрузка одного набора) — серая глина
        b.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
        b.inputs["Roughness"].default_value = 0.6
        return m

    def img(suffix, noncolor, y):
        t = nt.nodes.new("ShaderNodeTexImage")
        path = os.path.join(normal_dir if (suffix == "normal" and normal_dir) else folder, f"{s}_{suffix}.png")
        t.image = bpy.data.images.load(path, check_existing=True)
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
    """Студия для просмотра владельцем (как у ВЕРАС-54, tex13_author.studio): HDRI только в отражениях, тёмный фон,
    четыре неподвижных мягких источника вокруг винтовки, камера 3/4, Cycles, вьюпорт в Rendered."""
    S = bpy.context.scene
    coll = bpy.data.collections.get("Студия просмотра")
    if coll is None:
        coll = bpy.data.collections.new("Студия просмотра")
        S.collection.children.link(coll)
    w = bpy.data.worlds.new("AR-15 • Студия")
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
    bg_cam.label = "Фон за винтовкой"
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

    # винтовка вдвое длиннее ВЕРАС-54 — источники дальше и сильнее
    light("Студия • ключевой (справа спереди сверху)", (0.45, -0.75, 0.70), 1.9, 70, 1.1)
    light("Студия • заполняющий (слева)", (-0.30, 0.90, 0.20), 2.0, 18, 1.4)
    light("Студия • контровой (сзади сверху)", (-0.60, 0.30, 0.80), 1.8, 50, 0.7)
    light("Студия • полоса бликов (сверху)", (0.0, -0.35, 1.0), 1.5, 40, 1.8, 0.15)
    cd = bpy.data.cameras.new("Студия • камера")
    cd.lens = 50
    cd.clip_start = 0.005
    cam = bpy.data.objects.new("Студия • камера", cd)
    coll.objects.link(cam)
    cam.location = CENTER + Vector((0.40, -0.85, 0.30)).normalized() * 1.25
    cam.rotation_euler = (CENTER - cam.location).to_track_quat("-Z", "Y").to_euler()
    S.camera = cam
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 128
    S.cycles.preview_samples = 64
    S.cycles.use_denoising = True
    S.cycles.use_preview_denoising = True
    S.cycles.denoising_use_gpu = False      # Painter держит видеопамять — шумоподавление на процессоре
    # шумоподавление по цвету и нормалям: по одной картинке оно смывало мелкое зерно покрытия вместе с шумом рендера,
    # и металл во вьюпорте казался гладким (владелец 30.10 показал настройки вьюпорта в ролике Dolinskyi — резкость
    # текстуры важнее скорости)
    for pre in ("", "preview_"):
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


def apply(variant, folder, out, normal_dir=None):
    mats = {s: material(s, folder, normal_dir) for s in T.SETS}
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH" or "ar15_set" not in o:
            continue
        m = mats[o["ar15_set"]]
        slots = max(1, len(o.data.materials))
        o.data.materials.clear()
        for _ in range(slots):
            o.data.materials.append(m)
        n += 1
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    old_cam = bpy.data.objects.get("Cam_3q")
    if old_cam is not None:
        bpy.data.objects.remove(old_cam, do_unlink=True)
    studio()
    bpy.context.scene["ar15_variant"] = variant
    bpy.context.preferences.filepaths.save_version = 0      # без .blend1 рядом с выдачей (настройки не сохраняются)
    # пути к картам — относительно файла
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    print("APPLIED", variant, n, "объектов →", out)


VIEWS = {
    # имя: (направление от центра к камере, расстояние, фокусное, точка взгляда)
    "01_справа_3-4": ((0.40, -0.85, 0.30), 1.25, 50, CENTER),
    "02_слева_3-4": ((0.40, 0.85, 0.30), 1.25, 50, CENTER),
    "03_справа_сбоку": ((0.0, -1.0, 0.05), 1.55, 50, CENTER),
    "04_ресиверы_слева": ((0.15, 0.95, 0.25), 0.42, 50, Vector((-0.08, 0.0, -0.02))),
    "05_ресиверы_справа": ((0.15, -0.95, 0.25), 0.42, 50, Vector((-0.08, 0.0, -0.02))),
    "06_ствол_цевьё": ((0.35, -0.90, 0.35), 0.55, 50, Vector((0.15, 0.0, 0.0))),
    "07_рукоять": ((0.30, -0.95, 0.10), 0.30, 50, Vector((-0.158, 0.0, -0.10))),
    "08_рукоять_шов_крупно": ((0.85, -0.45, 0.10), 0.13, 50, Vector((-0.128, 0.0, -0.115))),
}


def shots(folder, samples=64, only=None):
    S = bpy.context.scene
    os.makedirs(folder, exist_ok=True)
    cam = S.camera
    S.cycles.samples = samples
    S.cycles.device = "GPU"
    S.cycles.denoising_use_gpu = False
    v = S.get("ar15_variant", "X")
    for name, (d, dist, lens, at) in VIEWS.items():
        if only and name not in only:
            continue
        cam.data.lens = lens
        cam.location = at + Vector(d).normalized() * dist
        cam.rotation_euler = (at - cam.location).to_track_quat("-Z", "Y").to_euler()
        S.render.filepath = os.path.join(folder, f"{v}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", S.render.filepath)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "apply":
        apply(a[1], a[2], a[3], a[4] if len(a) > 4 else None)
    elif a[0] == "shots":
        shots(a[1], int(a[2]) if len(a) > 2 else 64, a[3].split(",") if len(a) > 3 else None)
