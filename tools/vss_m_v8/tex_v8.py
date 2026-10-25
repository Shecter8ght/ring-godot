# ВСС-М v8: наложение материалов (materials_v8), отпечатки-декали, свойства слоёв, студия для осмотра.
# blender --background --factory-startup <geometry.blend> --python-exit-code 1 --python tools/vss_m_v8/tex_v8.py -- <out.blend>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import materials_v8 as MV  # noqa: E402

PRINTS = "01_Отпечатки_пальцев/"
PALMS = "02_Отпечатки_ладоней/"

# (родитель, точка мм, нормаль, поворот°, размер мм, маска, материалы)
DECALS = [
    ("Charging_handle", (474.5, -32.0, 9.6), (0, 0, 1), 55, 16, PRINTS + "Отпечаток_смазанный_вправо_01.png", ["Steel_black"]),
    ("Safety_lever", (400.5, -25.6, 0.5), (0, -1, 0), -15, 18, PRINTS + "Отпечаток_чёткий_01.png", ["Steel_black"]),
    ("Trigger", (381.5, 0.0, -29.0), (1, 0, 0), 90, 14, PRINTS + "Отпечаток_грязный_02.png", ["Steel_black"]),
    ("Magazine_catch", (406.0, 0.0, -58.0), (-1, 0, 0), 90, 14, PRINTS + "Отпечаток_смазанный_вниз_01.png", ["Steel_black"]),
    ("Receiver_lower", (428.0, -18.4, -3.0), (0, -1, 0), 10, 34, PRINTS + "Отпечаток_смазанный_по_диагонали_01.png", ["Steel_black"]),
    ("Receiver_lower", (330.0, -18.4, -6.0), (0, -1, 0), -30, 30, PRINTS + "Отпечаток_растёртый_01.png", ["Steel_black"]),
    ("Receiver_cover", (365.0, 19.2, 27.0), (0, 1, 0), 160, 40, PRINTS + "Отпечаток_смазанный_вправо_02.png", ["Steel_black"]),
    ("Receiver_lower", (335.0, 18.4, -8.0), (0, 1, 0), 60, 30, PRINTS + "Отпечаток_грязный_01.png", ["Steel_black"]),
    ("Trigger_guard", (378.0, 0.0, -50.9), (0, 0, -1), 0, 24, PRINTS + "Отпечаток_смазанный_вправо_03.png", ["Steel_black"]),
    ("Rail_sleeve", (612.0, -27.5, 10.0), (0, -1, 0), 75, 44, PALMS + "Ладонь_частичная_01.png", ["Alu_anodized"]),
    ("Rail_sleeve", (628.0, 27.5, 6.0), (0, 1, 0), -100, 36, PRINTS + "Отпечаток_смазанный_по_диагонали_02.png", ["Alu_anodized"]),
    ("Handguard", (522.0, -19.9, 6.0), (0, -1, 0), 95, 62, PALMS + "Ладонь_смазанная_вправо_01.png", ["Polymer_handguard"]),
    ("Handguard", (530.0, 20.1, 14.0), (0, 1, 0), -80, 46, PRINTS + "Отпечаток_грязный_03.png", ["Polymer_handguard"]),
    ("Handguard", (512.0, 0.0, 49.2), (0, 0, 1), 10, 32, PRINTS + "Отпечаток_растёртый_01.png", ["Polymer_handguard"]),
    ("Magazine_10", (455.0, -15.4, -48.0), (0, -1, 0), 100, 34, PRINTS + "Отпечаток_смазанный_вниз_01.png", ["Polymer_magazine"]),
    ("Magazine_10", (450.0, 15.4, -44.0), (0, 1, 0), -70, 30, PRINTS + "Отпечаток_грязный_02.png", ["Polymer_magazine"]),
    ("Magazine_20", (456.0, -15.4, -60.0), (0, -1, 0), 80, 34, PRINTS + "Отпечаток_смазанный_вправо_01.png", ["Polymer_magazine"]),
    ("Magazine_20", (452.0, 15.4, -95.0), (0, 1, 0), 120, 34, PRINTS + "Отпечаток_чёткий_01.png", ["Polymer_magazine"]),
    ("Wood_stock_v8", (330.0, -17.1, -72.0), (0, -1, 0), 100, 60, PALMS + "Ладонь_грязная_01.png", ["Wood_stock"]),
    ("Wood_stock_v8", (205.0, 17.1, -2.0), (0, 1, 0), 0, 70, PALMS + "Ладонь_растёртая_01.png", ["Wood_stock"]),
    ("Suppressor_body", (800.0, 0.0, 30.4), (0, 0, 1), 30, 34, PRINTS + "Отпечаток_смазанный_по_диагонали_01.png", ["Suppressor"]),
    ("Suppressor_body", (760.0, -20.4, 10.0), (0, -1, 0), 80, 30, PRINTS + "Отпечаток_грязный_01.png", ["Suppressor"]),
]

# множители слоёв по деталям: места частого контакта — сильнее износ; внутренние — меньше пыли, больше масла
TUNE = {
    "Charging_handle": {"wear": 2.4}, "Safety_lever": {"wear": 2.2}, "Trigger": {"wear": 1.8},
    "Magazine_catch": {"wear": 2.0}, "Trigger_guard": {"wear": 1.8}, "Cover_picatinny": {"wear": 1.7},
    "Rail_sleeve": {"wear": 1.5}, "Fire_selector": {"wear": 2.0}, "Cover_latch_button": {"wear": 2.0},
    "Bolt": {"wear": 0.8, "dust": 0.1, "grime": 1.6, "oil": 1.8}, "Bolt_carrier": {"wear": 0.9, "dust": 0.1, "oil": 1.6},
    "Bolt_extractor": {"dust": 0.1, "oil": 1.5}, "Gas_piston_rod": {"dust": 0.0, "grime": 1.8, "oil": 1.2},
    "Recoil_spring": {"dust": 0.0}, "Recoil_spring_guide": {"dust": 0.0}, "Receiver_trunnion": {"dust": 0.2, "grime": 1.5},
    "Receiver_inner_rails": {"dust": 0.1, "oil": 1.6}, "Ejector_blade": {"dust": 0.1},
    "Barrel": {"dust": 0.2, "grime": 1.8}, "Suppressor_baffles": {"dust": 0.0, "grime": 2.0},
    "Magazine_10": {"wear": 1.2}, "Magazine_20": {"wear": 1.0}, "Handguard": {"wear": 1.1},
    "Rubber_butt_pad": {"wear": 0.8},
}


def make_decals():
    out = {}
    coll = bpy.data.collections.get("Decals") or bpy.data.collections.new("Decals")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.data.collections["VSS_M_v8"].children.link(coll)
    for i, (parent, pos, nrm, rot, size, img, mats) in enumerate(DECALS):
        par = bpy.data.objects.get(parent)
        if par is None:
            print("NO DECAL PARENT", parent)
            continue
        e = bpy.data.objects.new(f"Print_{i:02d}_{parent}", None)
        e.empty_display_type = "CUBE"
        e.empty_display_size = 1.0
        coll.objects.link(e)
        n = Vector(nrm).normalized()
        q = Vector((0, 0, 1)).rotation_difference(n)
        m = q.to_matrix().to_4x4() @ Matrix.Rotation(math.radians(rot), 4, "Z")
        h = size * 0.0005
        local = Matrix.Translation(Vector(pos) * 0.001) @ m @ Matrix.Diagonal((h, h, 0.0025, 1.0))
        bpy.context.view_layer.update()
        # точка задана в координатах детали в исходном положении
        e.matrix_world = par.matrix_world @ local
        e.parent = par
        e.matrix_parent_inverse = par.matrix_world.inverted()
        e.matrix_world = par.matrix_world @ local
        im = MV.mask(img)
        for mname in mats:
            out.setdefault(mname, []).append((e, im, False))
    return out


def studio(bright=1.0, bg=(0.62, 0.62, 0.63), dark=False):
    """Студия осмотра. dark — тёмная съёмка, как на рендерах-образцах (Fab, Sketchfab): чёрный фон, большой софтбокс
    сверху спереди даёт блик по металлу и лаку, контровые полосы сзади обводят силуэт; окружение слабое."""
    if dark:
        bright, bg = 1.0, (0.008, 0.008, 0.009)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            if any(d.type == dev_type for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev_type
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = 128
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    w = bpy.data.worlds.new("V8_Studio")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load("E:/Games/RING-godot/_asset_src/vss_m_v8/hdri/photo_studio_loft_hall_2k.hdr", check_existing=True)
    bg_hdr = nt.nodes.new("ShaderNodeBackground"); bg_hdr.inputs["Strength"].default_value = (0.12 if dark else 0.35) * bright
    nt.links.new(env.outputs[0], bg_hdr.inputs[0])
    bg_c = nt.nodes.new("ShaderNodeBackground"); bg_c.inputs[0].default_value = (*bg, 1.0); bg_c.inputs[1].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_hdr.outputs[0], mix.inputs[1]); nt.links.new(bg_c.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    lc = bpy.data.collections.get("Studio") or bpy.data.collections.new("Studio")
    if lc.name not in sc.collection.children:
        sc.collection.children.link(lc)
    def area(name, loc, size, power, color=(1, 1, 1), tgt=(0.45, 0, 0)):
        ld = bpy.data.lights.new(name, "AREA"); ld.shape = "RECTANGLE"; ld.size = size[0]; ld.size_y = size[1]
        ld.energy = power * bright; ld.color = color
        lo = bpy.data.objects.new(name, ld); lc.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return lo
    if dark:
        # верхний софтбокс чуть за предметом: блики по верхним граням и кромкам; спереди слабая заливка —
        # чёрный пластик остаётся чёрным, металл и лак читаются бликами (как на образцах)
        sc.view_settings.exposure = -0.7          # 4 % блика на чёрном пластике не уходят в серый
        area("Key", (0.45, 0.2, 1.0), (1.6, 0.6), 130.0, (1.0, 0.97, 0.93))
        area("Rim_back", (0.45, 0.95, 0.3), (2.2, 0.22), 180.0, (0.92, 0.96, 1.0))
        # передняя подсветка — узкая наклонная полоса, а не большой софтбокс: большой зеркально ложился на боковины,
        # и любой глянец (цевьё, муфта) выглядел серым; полоса даёт блик полосой, остальное остаётся тёмным
        area("Front_strip", (0.8, -0.75, 0.35), (0.12, 1.6), 40.0, (1.0, 0.98, 0.95))
        area("Kicker", (1.25, -0.45, -0.15), (0.4, 0.4), 20.0, (1.0, 0.9, 0.8))
        return
    area("Key", (0.25, -0.9, 1.0), (1.2, 0.6), 120.0, (1.0, 0.97, 0.92))
    area("Fill", (0.6, 1.1, 0.5), (1.0, 1.0), 40.0, (0.92, 0.96, 1.0))
    area("Rim", (1.4, 0.3, 0.9), (0.3, 1.5), 80.0)
    area("Top_strip", (0.45, -0.2, 1.3), (1.6, 0.25), 50.0)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    prints = make_decals()
    M = MV.build_all(prints)
    MV.assign(M, TUNE)
    studio()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    main()
