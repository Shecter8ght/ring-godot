"""Опоры касс v01, отделка: файл просмотра — прилавок и бокс с картами Painter, касса партии 1 (карты v03) на socket_register
(дисплей покупателя довёрнут к покупателю), тёмная студия как у lc3_review.py (приёмы и свет — оттуда).

  blender --background <RING_Loot_Counters_uv_v01.blend> --factory-startup --python tools/loot_containers/counters_review.py -- \
      <папка карт> <выход.blend> [shots <папка> [кадры через запятую]] [res=1600x1000] [samples=64]

Папка карт — <папка>/<набор>/<набор>_{baseColor,normal,occlusionRoughnessMetallic}.png.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lc3_review as R3  # noqa: E402  (студия, тёмный мир; main() не запускается)

R = R3.R
L = R3.L
FIN = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Containers_finish_v03.blend"
CASH_MAPS = "E:/Games/RING-godot/_asset_src/loot_containers/maps_v03/lc_cash"
X = {"cn_counter": 0.0, "cn_checkout": 3.6}
SOCK = {"cn_counter": ((-0.25, 0.0, 0.9)), "cn_checkout": ((0.40, 0.30, 0.92))}
TITLES = {"cn_counter": "Прилавок торговый", "cn_checkout": "Кассовый бокс"}

# (имя, набор, цель от корня, расстояние, азимут (0 — камера с −Y, покупатель), подъём, фокус)
SHOTS = [
    ("counter_buyer34", "cn_counter", (0, 0, 0.45), 3.3, -35, 14, 40),
    ("counter_seller34", "cn_counter", (0, 0, 0.45), 3.3, 145, 16, 40),
    ("counter_edge", "cn_counter", (-0.70, -0.27, 0.86), 0.55, -40, 26, 50),
    ("counter_floor", "cn_counter", (-0.55, -0.2, 0.08), 0.65, -35, 10, 50),
    ("counter_top", "cn_counter", (-0.1, 0.0, 0.9), 1.5, 25, 48, 40),
    ("counter_drawer", "cn_counter", (0.0, 0.28, 0.65), 1.2, 150, 14, 45),
    ("counter_front", "cn_counter", (0, -0.27, 0.45), 1.6, -8, 6, 45),
    ("checkout_buyer34", "cn_checkout", (0.1, 0, 0.55), 5.0, -38, 18, 40),
    ("checkout_seller34", "cn_checkout", (0.1, 0, 0.55), 5.0, 140, 20, 40),
    ("checkout_panel", "cn_checkout", (0.3, -0.55, 0.35), 1.7, -12, 5, 45),
    ("checkout_belt", "cn_checkout", (-0.5, -0.25, 0.84), 1.5, -28, 24, 45),
    ("checkout_belt_graze", "cn_checkout", (0.0, -0.25, 0.84), 1.6, -80, 9, 45),
    ("checkout_accum", "cn_checkout", (0.8, -0.25, 0.9), 1.4, -35, 24, 45),
    ("checkout_floor", "cn_checkout", (0.7, -0.55, 0.08), 0.9, -25, 8, 50),
    ("checkout_cashier", "cn_checkout", (0.45, 0.35, 0.9), 1.6, 150, 22, 45),
    ("checkout_sign", "cn_checkout", (0.95, 0.48, 1.9), 1.1, 70, 8, 50),
]


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    opts = {a.split("=")[0]: a.split("=")[1] for a in argv if "=" in a}
    shots = argv[3] if len(argv) > 3 and argv[2] == "shots" else None
    only = argv[4].split(",") if shots and len(argv) > 4 and "=" not in argv[4] else None
    for o in list(bpy.data.objects):
        if o.name.startswith("_src_"):
            bpy.data.objects.remove(o)
    for cn in ("Опоры_касс_v01", "Для_масштаба", "Студия", "Камеры"):   # исходные коллекции формы — не нужны (форма — в «Развёртка_v01»)
        c = bpy.data.collections.get(cn)
        if c is not None:
            for ob in list(c.all_objects):
                bpy.data.objects.remove(ob)
    for c in list(bpy.data.collections):
        if c.name in ("Опоры_касс_v01", "Для_масштаба", "Прилавок торговый", "Кассовый бокс", "Камеры", "Студия", "Кассовое место"):
            bpy.data.collections.remove(c)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    spots = {}
    for game, cx in X.items():
        maps_dir = os.path.join(maps_root, game)
        coll = bpy.data.collections[game]
        coll.hide_viewport = False
        coll.hide_render = False
        mat = R.material(game, maps_dir)
        m = Matrix.Translation((cx, 0.0, 0.0))
        for ob in coll.objects:
            ob.hide_viewport = False
            ob.hide_render = False
            ob.matrix_world = m
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            for p in ob.data.polygons:
                p.use_smooth = True
            ob.data.set_sharp_from_angle(angle=math.radians(10))   # крупные плоскости с фасками: при 40° градиент нормалей даёт блики-«диагонали»
        R3.label(coll, TITLES[game], (cx, -1.0, 0.002))
        spots[game] = m.translation.copy()
    # касса партии 1 (закрытая, карты v03) на socket_register: поворот 180°, дисплей покупателя — к покупателю
    with bpy.data.libraries.load(FIN, link=False) as (df, dt):
        dt.collections = ["lc_cash__closed"]
    cc = dt.collections[0]
    cmat = R.material("lc_cash_v03", CASH_MAPS)
    emi = os.path.join(CASH_MAPS, "lc_cash_emissive.png")
    if os.path.exists(emi):
        nt = cmat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = R.load(emi, False)
        nt.links.new(tn.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 4.0
    kc = L.collection("Касса_для_масштаба")
    cx2, cy2 = -0.145, 0.155   # ось дисплея покупателя в осях кассы
    for game, cx in X.items():
        sx, sy, sz = SOCK[game]
        M = Matrix.Translation((cx + sx, sy, sz)) @ Matrix.Rotation(math.pi, 4, "Z")
        for ob in cc.objects:
            if ob.type != "MESH":
                continue
            o2 = ob.copy()
            o2.data = ob.data.copy()
            o2.name = f"{game}:{ob.name}"
            o2.data.materials.clear()
            o2.data.materials.append(cmat)
            if "дисплей_покупателя" in ob.name:
                o2.data.transform(Matrix.Translation((cx2, cy2, 0)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Translation((-cx2, -cy2, 0)))
            o2.matrix_world = M
            for p in o2.data.polygons:
                p.use_smooth = True
            kc.objects.link(o2)
    st = L.collection("Студия")
    R3.studio(st, X["cn_checkout"] + 1.5)
    sc = bpy.context.scene
    sc.world = R3.world_dark()
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
    # камеры остаются в файле
    kcam = L.collection("Камеры")
    cams = {}
    for name, game, off, dist, az, el, lens in SHOTS:
        cd = bpy.data.cameras.new("Кам_" + name)
        cd.lens = lens
        cd.clip_start = 0.02
        co = bpy.data.objects.new("Кам_" + name, cd)
        tgt = spots[game] + V(off)
        a, e = math.radians(az - 90), math.radians(el)
        co.location = tgt + V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
        co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
        kcam.objects.link(co)
        cams[name] = co
    if shots:
        res = opts.get("res", "1600x1000").split("x")
        sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
        os.makedirs(shots, exist_ok=True)
        for name, co in cams.items():
            if only and name not in only:
                continue
            sc.camera = co
            sc.render.filepath = os.path.join(shots, name + ".png")
            bpy.ops.render.render(write_still=True)
            print("SHOT", name, flush=True)
    sc.camera = cams["counter_buyer34"]
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
