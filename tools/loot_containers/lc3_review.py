"""Контейнеры для лута, партия 1, отделка v03: файл просмотра — шесть предметов (без сумки), закрыто и открыто, ТЁМНАЯ
студия как у образцов Sketchfab (фон ~0,02, ключевой свет сверху-сбоку, контровые для кромок, HDRI только в отражениях),
вьюпорт сразу Rendered; материалы — обычный Principled с картами v03 (относительные пути, textures/finish_v03).

  blender --background <RING_Loot_Containers_uv_v01.blend> --factory-startup --python tools/loot_containers/lc3_review.py -- \
      <папка карт> <выход.blend> [shots <папка> [кадры через запятую]] [res=1600x1000] [samples=64]

Папка карт — <папка>/<набор>/<набор>_{baseColor,normal,occlusionRoughnessMetallic}.png. Кадры (Cycles, GPU без шумодава на
GPU — Painter держит видеопамять) — для самопроверки и листов сверки.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "asset_kit", "finish"))
import finish_review as R  # noqa: E402
import mlib as L  # noqa: E402
import render_cards as RC  # noqa: E402

PLACE = {"lc_safe": ("floor", 0.7, 1.3), "lc_cell": ("wall", 0.6, 1.0), "lc_gun": ("floor", 1.0, 1.9),
         "lc_file": ("floor", 0.7, 0.7), "lc_cash": ("floor", 0.6, 0.6), "lc_aid": ("wall", 0.6, 1.0)}
GLASS = ("окно",)
TITLES = {"lc_safe": "Сейф напольный", "lc_cell": "Сейф-ячейка", "lc_gun": "Оружейный шкаф", "lc_file": "Картотечный шкаф",
          "lc_cash": "Кассовое место", "lc_aid": "Аптечка настенная"}

# (имя, набор, состояние, смещение цели от корня, расстояние, азимут°, возвышение°, фокусное мм)
SHOTS = [
    ("gun_open", "lc_gun", "открыто", (0, 0, 0.9), 4.2, -32, 10, 50),
    ("gun_closed", "lc_gun", "закрыто", (0, 0, 0.9), 4.2, -32, 10, 50),
    ("gun_door", "lc_gun", "закрыто", (0.0, -0.24, 1.0), 1.1, -12, 3, 50),
    ("safe_door", "lc_safe", "закрыто", (0.0, -0.24, 0.42), 0.95, -14, 4, 50),
    ("gun_edge", "lc_gun", "открыто", (-0.34, -0.2, 1.62), 0.9, -25, 8, 50),
    ("gun_hinge", "lc_gun", "открыто", (-0.40, -0.2, 0.3), 1.0, -35, 14, 50),
    ("safe_open", "lc_safe", "открыто", (0.1, 0.0, 0.34), 2.4, -30, 12, 50),
    ("safe_closed", "lc_safe", "закрыто", (0, 0, 0.34), 2.0, -28, 14, 50),
    ("safe_dial", "lc_safe", "закрыто", (0.0, -0.22, 0.46), 0.5, -22, 10, 50),
    ("file_open", "lc_file", "открыто", (0, -0.1, 0.66), 3.2, -30, 12, 50),
    ("file_edge", "lc_file", "открыто", (0, -0.3, 0.9), 0.9, -22, 12, 50),
    ("cash_closed", "lc_cash", "закрыто", (0, 0, 0.18), 1.3, -35, 24, 50),
    ("cash_side", "lc_cash", "закрыто", (0, 0, 0.18), 1.5, -88, 4, 50),
    ("cash_keys", "lc_cash", "закрыто", (-0.05, -0.1, 0.2), 0.6, -15, 45, 50),
    ("aid_closed", "lc_aid", "закрыто", (0, -0.05, 0.0), 1.3, -20, 8, 50),
    ("aid_open", "lc_aid", "открыто", (0, -0.1, 0.0), 1.3, -25, 8, 50),
    ("cell_open", "lc_cell", "открыто", (0, -0.1, 0.0), 1.0, -25, 10, 50),
]


def world_dark():
    """Фон камеры почти чёрный; HDRI студии — только в отражениях и слабым заполнением."""
    w = bpy.data.worlds.new("Студия_тёмная")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(RC.STUDIO_HDR), check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.22
    flat = nt.nodes.new("ShaderNodeBackground")
    flat.inputs["Color"].default_value = (0.018, 0.018, 0.02, 1.0)
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


def studio(coll, span):
    """Пол тёмный, ключевой свет сверху-сбоку (мягкий, большой), два контровых софтбокса для кромок."""
    import bmesh
    bm = bmesh.new()
    L.bm_box(bm, (-3.0, -4.0, -0.02), (span + 3.0, 3.0, 0.0))
    L.finish_bm(bm, "студия_пол", coll, L.material("Студия_пол", (0.025, 0.025, 0.027), 0.55))
    lights = [("ключевой", (span * 0.35, -3.2, 3.6), 760, 5.0, (math.radians(52), 0, math.radians(-12))),
              ("ключевой_2", (span * 0.8, -3.2, 3.6), 600, 5.0, (math.radians(52), 0, math.radians(10))),
              ("контровой_лево", (-0.8, 1.9, 2.6), 650, 1.6, (math.radians(-118), 0, math.radians(-30))),
              ("контровой_право", (span + 0.8, 1.9, 2.6), 650, 1.6, (math.radians(-118), 0, math.radians(30))),
              ("контровой_центр", (span * 0.5, 2.2, 3.0), 400, 3.0, (math.radians(-130), 0, 0)),
              ("заполнение", (span * 0.5, -4.0, 1.2), 60, 4.0, (math.radians(88), 0, 0))]
    for name, loc, e, size, rot in lights:
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = e
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = rot
        coll.objects.link(lo)


def label(coll, text, at):
    cu = bpy.data.curves.new(f"подпись {text}", "FONT")
    cu.body = text
    cu.size = 0.05
    cu.align_x = "CENTER"
    t = bpy.data.objects.new(f"подпись {text}", cu)
    coll.objects.link(t)
    t.location = at
    t.data.materials.append(bpy.data.materials.get("Подпись") or L.material("Подпись", (0.6, 0.6, 0.58), 0.6))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    opts = {a.split("=")[0]: a.split("=")[1] for a in argv if "=" in a}
    shots = argv[3] if len(argv) > 3 and argv[2] == "shots" else None
    only = argv[4].split(",") if shots and len(argv) > 4 and "=" not in argv[4] else None
    for o in list(bpy.data.objects):
        if o.name.startswith("_src_"):
            bpy.data.objects.remove(o)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    for g in ("lc_bag", "lc_bag__closed"):   # сумку делает другой исполнитель
        if g in bpy.data.collections:
            bpy.data.collections[g].hide_viewport = True
            bpy.data.collections[g].hide_render = True
    x = 0.0
    spots = {}
    for game, (how, wc, wo) in PLACE.items():
        maps_dir = os.path.join(maps_root, game)
        have = os.path.exists(os.path.join(maps_dir, f"{game}_baseColor.png"))
        mats = {}
        for suffix, width, tag in (("__closed", wc, "закрыто"), ("", wo, "открыто")):
            coll = bpy.data.collections[game + suffix]
            coll.hide_viewport = False
            coll.hide_render = False
            cx = x + width / 2
            m = Matrix.Translation((cx, 1.4 if how == "wall" else 0.0, 1.3 if how == "wall" else 0.0))
            for ob in coll.objects:
                ob.hide_viewport = False
                ob.hide_render = False
                ob.matrix_world = m
                ob.data.materials.clear()
                if not have:
                    continue
                key = "glass" if any(k in ob.name for k in GLASS) else ""
                if key not in mats:
                    mats[key] = R.material(f"{game}{'_стекло' if key else ''}", maps_dir, glass=bool(key))
                ob.data.materials.append(mats[key])
                for p in ob.data.polygons:
                    p.use_smooth = True
                ob.data.set_sharp_from_angle(angle=math.radians(40))
            label(coll, f"{TITLES[game]} — {tag}", (cx, -0.9 if how == "floor" else 0.5, 0.002 if how == "floor" else 0.02))
            spots[(game, tag)] = m.translation.copy()
            x += width + 0.12
        x += 0.35
    st = L.collection("Студия")
    studio(st, x)
    if "Стена" not in bpy.data.objects:
        import bmesh
        bm = bmesh.new()
        L.bm_box(bm, (-3.0, 1.4, 0.0), (x + 3.0, 1.45, 3.2))
        L.finish_bm(bm, "Стена", st, L.material("Студия_стена", (0.004, 0.004, 0.005), 0.8))
    sc = bpy.context.scene
    bpy.context.scene.world = world_dark()
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(opts.get("samples", 64))
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        sc.cycles.device = "GPU"
    except Exception as e:   # noqa: BLE001
        print("GPU нет:", e)
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    if shots:
        res = opts.get("res", "1600x1000").split("x")
        sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
        render_shots(shots, spots, only)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


def render_shots(folder, spots, only) -> None:
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("проверка")
    co = bpy.data.objects.new("проверка", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    for name, game, state, off, dist, az, el, lens in SHOTS:
        if only and name not in only:
            continue
        base = spots[(game, state)]
        tgt = base + V(off)
        a, e = math.radians(az - 90), math.radians(el)
        co.location = tgt + V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
        co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
        cam.lens = lens
        sc.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, flush=True)


if __name__ == "__main__":
    main()
