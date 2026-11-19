# ВЕРАС-54 v14, текстуры этап 1: карты из Substance Painter → файл просмотра в Blender со студией прямо в файле (по
# образцу tools/pkp/tex_review.py: HDRI только в отражениях, тёмный фон, неподвижные мягкие источники, камера, Cycles,
# вьюпорт в Rendered). Геометрия, развёртка, риг (VERAS54_Controls и приводы) — из файла развёртки без изменений;
# меняются только материалы: материал на набор текстур, карты — внешние PNG по относительным путям.
#   apply <папка карт> <out.blend>                       — файл просмотра
#   shots <папка снимков> [samples] [вид,вид]            — кадры Cycles (на файле просмотра): общие, 3/4 и ракурсы снимков
#                                                          образца S01…S05 (камеры образца в наших осях)
#   sheets <папка снимков> <папка образца>               — без Blender (python): листы «образец | наш» по S01…S05
# blender -b "<ВЕРАС-54_развёртка_v14_01.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_review.py -- apply <папка> <out>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tex_sets as T  # noqa: E402

HDRI = "E:/Games/RING-godot/_asset_src/pm_game/sources/studio_small_09_1k.hdr"   # Poly Haven, CC0
# камеры образца (Sketchfab «Kalashnikov AK-12»): глаз → цель в осях образца (м), перевод в наши мм: x·1000 + 252,1,
# z·1000 − 279,5; кадр образца 800 × 600, поле зрения по горизонтали REF_FOV
REF = {
    "S01_front_right": ((0.45, -0.55, 0.42), (0.22, 0.0, 0.28)),
    "S02_rear_right": ((-0.55, -0.7, 0.3), (-0.25, 0.0, 0.2)),
    "S03_receiver_right": ((-0.02, -0.32, 0.33), (-0.06, 0.0, 0.27)),
    "S04_magazine": ((0.05, -0.3, 0.12), (-0.02, 0.0, 0.13)),
    "S05_handguard_left": ((0.05, 0.34, 0.36), (0.12, 0.0, 0.28)),
}
REF_FOV = 45.0
LIGHT_K = float(os.environ.get("VERAS_LIGHT_K", "0.18"))     # сила источников студии
HDRI_K = float(os.environ.get("VERAS_HDRI_K", "0.6"))       # сила отражений HDRI
REF_RES = (1200, 900)


def ref_point(p):
    return (p[0] * 1000.0 + 252.1) * 0.001, p[1], (p[2] * 1000.0 - 279.5) * 0.001


def material(s, folder):
    import bpy
    m = bpy.data.materials.get(f"ВЕРАС-54 • {s}") or bpy.data.materials.new(f"ВЕРАС-54 • {s}")
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


def center():
    import bpy
    from mathutils import Vector
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.visible_get():
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
    return (lo + hi) / 2, hi - lo


def studio():
    """HDRI только в отражениях, тёмно-серый фон (как у образца), четыре неподвижных мягких источника, камера 3/4."""
    import bpy
    from mathutils import Vector
    S = bpy.context.scene
    C, size = center()
    coll = bpy.data.collections.get("Студия просмотра")
    if coll is None:
        coll = bpy.data.collections.new("Студия просмотра")
        S.collection.children.link(coll)
    w = bpy.data.worlds.new("ВЕРАС-54 • Студия")
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
    bg_env.inputs["Strength"].default_value = HDRI_K
    nt.links.new(env.outputs["Color"], bg_env.inputs["Color"])
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.label = "Фон за автоматом (тёмно-серый, как у образца)"
    bg_cam.inputs["Color"].default_value = (0.008, 0.008, 0.009, 1)
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
        o.location = C + Vector(direction).normalized() * dist
        o.rotation_euler = (C - o.location).to_track_quat("-Z", "Y").to_euler()
        return o

    # сила — LIGHT_K от студии «Частокола»: там белёсая серая сталь, здесь чёрная краска; при полной силе чёрное
    # выходило серой глиной (проба 19.11) — свет как у образца: тёмный корпус с бликами по кромкам
    k = LIGHT_K
    light("Студия • ключевой (справа спереди сверху)", (0.45, -0.75, 0.70), 1.8, 260 * k, 1.1)
    light("Студия • заполняющий (слева)", (-0.30, 0.90, 0.20), 1.9, 110 * k, 1.3)
    light("Студия • контровой (сзади сверху)", (-0.60, 0.30, 0.80), 1.7, 190 * k, 0.8)
    light("Студия • полоса бликов (сверху)", (0.0, -0.35, 1.0), 1.5, 150 * k, 1.7, 0.16)
    cd = bpy.data.cameras.new("Студия • камера")
    cd.lens = 50
    cd.clip_start = 0.01
    cam = bpy.data.objects.new("Студия • камера", cd)
    coll.objects.link(cam)
    cam.location = C + Vector((0.35, -0.85, 0.35)).normalized() * 1.9
    cam.rotation_euler = (C - cam.location).to_track_quat("-Z", "Y").to_euler()
    S.camera = cam
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 128
    S.cycles.preview_samples = 64
    S.cycles.use_denoising = True
    S.cycles.use_preview_denoising = True
    S.cycles.denoising_use_gpu = False      # Painter держит видеопамять — шумоподавление на процессоре
    for pre in ("", "preview_"):
        setattr(S.cycles, pre + "denoising_input_passes", "RGB_ALBEDO_NORMAL")
        setattr(S.cycles, pre + "denoising_prefilter", "ACCURATE")
    S.render.resolution_x, S.render.resolution_y = 1920, 1080
    S.render.film_transparent = False
    S.view_settings.view_transform = "AgX"
    S.view_settings.look = "AgX - Base Contrast"
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.clip_start = 0.005


def apply(folder, out):
    import bpy
    folder = os.path.abspath(folder)
    out = os.path.abspath(out)
    mats = {s: material(s, folder) for s in T.SETS}
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH" or "v14_set" not in o:
            continue
        m = mats[o["v14_set"]]
        o.data.materials.clear()
        o.data.materials.append(m)
        n += 1
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    studio()
    bpy.context.preferences.filepaths.save_version = 0      # без .blend1 рядом с выдачей
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    print("APPLIED", n, "сеток →", out)


# имя: (направление от точки взгляда к камере, расстояние, фокусное, точка взгляда, позы); точка — вектор (м) или
# имя детали (середина габарита), None — середина автомата
VIEWS = {
    "01_справа": ((0.0, -1.0, 0.08), 1.55, 50, None, {}),
    "02_слева": ((0.0, 1.0, 0.08), 1.55, 50, None, {}),
    "03_спереди_3-4": ((0.55, -0.75, 0.35), 1.6, 50, None, {}),
    "04_сзади_3-4": ((-0.55, -0.75, 0.35), 1.6, 50, None, {}),
    "05_клейма_слева": ((0.0, 1.0, 0.05), 0.16, 50, (0.195, 0.0, -0.006), {}),
    "06_переводчик_АВ_2_ОД": ((0.0, -1.0, 0.05), 0.16, 50, (0.160, 0.0, -0.012), {}),
    "07_рама_отведена": ((0.25, -1.0, 0.35), 0.42, 50, "Bolt_Carrier", {"carrier": 1.0, "selector": 0.6}),
    "08_целик": ((-0.7, -0.45, 0.55), 0.20, 50, "Rear_Sight_Leaf", {}),
    "09_магазин_цифры": ((0.1, -1.0, 0.0), 0.30, 50, "Magazine_Body", {}),
    "11_оттенки_крышки": ((0.0, -0.55, 1.0), 0.42, 50, "Dust_Cover", {}),
    "12_оттенки_цевья_слева": ((0.1, 1.0, 0.35), 0.40, 50, "Handguard_Upper", {}),
    "10_донца_гильз": ((-0.6, -0.3, -0.75), 0.11, 50, "Chambered_Case", {"carrier": 1.0, "selector": 0.6}),
}


def _pose(p):
    import bpy
    ctl = bpy.data.objects.get(T.CONTROLS)
    if ctl is None:
        return
    for k, v in p.items():
        if k in ctl:
            ctl[k] = float(v)
    ctl.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.view_layer.update()


def _gpu():
    import addon_utils
    import bpy
    addon_utils.enable("cycles")
    cp = bpy.context.preferences.addons["cycles"].preferences
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


def shots(folder, samples=64, only=None):
    import bpy
    from mathutils import Vector
    _gpu()
    S = bpy.context.scene
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    cam = S.camera
    S.cycles.samples = samples
    ctl = bpy.data.objects.get(T.CONTROLS)
    keep = {k: float(ctl[k]) for k in ctl.keys() if isinstance(ctl[k], (int, float))} if ctl else {}
    C, _size = center()

    def want(name):
        return not only or name in only or name.split("_")[0] in only

    S.render.resolution_x, S.render.resolution_y = 1920, 1080
    cam.data.sensor_fit = "AUTO"
    for name, (d, dist, lens, at, pose) in VIEWS.items():
        if not want(name):
            continue
        _pose({**keep, **pose})
        if at is None:
            at = C
        elif isinstance(at, str):
            o = bpy.data.objects[at]
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            at = sum(bb, Vector()) / 8.0
        else:
            at = Vector(at)
        cam.data.lens = lens
        cam.location = at + Vector(d).normalized() * dist
        cam.rotation_euler = (at - cam.location).to_track_quat("-Z", "Y").to_euler()
        S.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, flush=True)
    _pose(keep)
    # ракурсы образца: тот же глаз, та же цель, кадр 4:3, поле зрения по горизонтали REF_FOV
    S.render.resolution_x, S.render.resolution_y = REF_RES
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(REF_FOV)
    for name, (eye, tgt) in REF.items():
        if not want(name):
            continue
        cam.location = Vector(ref_point(eye))
        cam.rotation_euler = (Vector(ref_point(tgt)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        S.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, flush=True)
    cam.data.sensor_fit = "AUTO"


def sheets(folder, refs):
    """Листы «образец | наш» по ракурсам S01…S05 (PIL, без Blender) → <folder>/sheet_<ракурс>.jpg."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    for name in REF:
        a, b = os.path.join(refs, name + ".jpg"), os.path.join(folder, name + ".png")
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        ia = Image.open(a).convert("RGB")
        ib = Image.open(b).convert("RGB").resize(ia.size, Image.LANCZOS)
        sh = Image.new("RGB", (ia.width * 2 + 8, ia.height + 28), (30, 30, 30))
        sh.paste(ia, (0, 28))
        sh.paste(ib, (ia.width + 8, 28))
        dr = ImageDraw.Draw(sh)
        dr.text((8, 6), f"образец {name} (изношен)", fill=(230, 230, 230), font=font)
        dr.text((ia.width + 16, 6), "ВЕРАС-54 v14 — заводская отделка v01 (этап 1, новый)", fill=(230, 230, 230), font=font)
        p = os.path.join(folder, f"sheet_{name}.jpg")
        sh.save(p, quality=92)
        print("SHEET", p)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if a[0] == "apply":
        apply(a[1], a[2])
    elif a[0] == "shots":
        shots(a[1], int(a[2]) if len(a) > 2 else 64, a[3].split(",") if len(a) > 3 else None)
    elif a[0] == "sheets":
        sheets(a[1], a[2])
