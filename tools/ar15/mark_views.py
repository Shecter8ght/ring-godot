# AR-15 «ГРАНЬ-15», этап 2 (износ): виды для разметки владельцем (сервис tools/ar15/mark_server.py) — в каждом виде
# два кадра одной камерой: обычный рендер студии файла просмотра и «карта точек» (в каждом пикселе — мировая точка, мм,
# и номер набора текстур), по которой метка с картинки переносится в развёртку (tools/ar15/mark_apply.py).
#   blender -b <файл просмотра износа.blend> --python tools/ar15/mark_views.py -- <папка разметки> [вид,вид…] [сэмплы 96]
# Пишет <папка>/views/<вид>.png (рендер), <вид>_pts.npz (pos — мм float32 ×3, set — номер набора uint8, 0 — фон;
# порядок наборов — tex_sets.SETS) и <папка>/views.json (подписи, камера, мм на пиксель в центре кадра).
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets  # noqa: E402

W, H = 1920, 1200
LENS = 50.0
# вид: (подпись, центр м, направление на камеру, расстояние м)
VIEWS = {
    "01_left": ("Слева целиком", (-0.02, 0.0, -0.06), (0.0, 1.0, 0.05), 1.12),
    "02_right": ("Справа целиком", (-0.02, 0.0, -0.06), (0.0, -1.0, 0.05), 1.12),
    "03_top": ("Сверху целиком", (-0.02, 0.0, 0.0), (0.0, 0.15, 1.0), 1.12),
    "04_bottom": ("Снизу целиком", (-0.02, 0.0, -0.06), (0.0, 0.15, -1.0), 1.12),
    "05_receivers_l": ("Ресиверы слева", (-0.08, 0.0, -0.02), (0.03, 1.0, 0.1), 0.42),
    "06_receivers_r": ("Ресиверы справа", (-0.08, 0.0, -0.02), (0.03, -1.0, 0.1), 0.42),
    "07_port": ("Окно выброса", (-0.03, -0.02, 0.01), (0.15, -1.0, 0.45), 0.22),
    "08_handguard_l": ("Цевьё слева", (0.15, 0.0, 0.0), (0.0, 1.0, 0.1), 0.42),
    "09_handguard_r": ("Цевьё справа", (0.15, 0.0, 0.0), (0.0, -1.0, 0.1), 0.42),
    "10_handguard_b": ("Цевьё снизу", (0.15, 0.0, -0.02), (0.05, 0.25, -1.0), 0.42),
    "11_stock_l": ("Приклад слева", (-0.29, 0.0, -0.03), (0.0, 1.0, 0.05), 0.38),
    "12_stock_r": ("Приклад справа", (-0.29, 0.0, -0.03), (0.0, -1.0, 0.05), 0.38),
    "13_grip_mag_l": ("Рукоять и магазин слева", (-0.08, 0.0, -0.11), (0.05, 1.0, -0.05), 0.42),
    "14_grip_mag_r": ("Рукоять и магазин справа", (-0.08, 0.0, -0.11), (0.05, -1.0, -0.05), 0.42),
    "15_muzzle": ("Ствол и дульник", (0.31, 0.0, 0.0), (0.25, 1.0, 0.3), 0.22),
    "16_sights": ("Прицелы и верх", (0.05, 0.0, 0.05), (-0.3, 0.6, 1.0), 0.5),
}


def _points_material(lo, sc):
    """Свечение = положение (в 0…1 по габариту сцены) / номер набора — для «карты точек»."""
    mats = {}
    for kind in ("pos", "set"):
        m = bpy.data.materials.new("mv_" + kind)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs[0])
        if kind == "pos":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            a = nt.nodes.new("ShaderNodeVectorMath"); a.operation = "MULTIPLY_ADD"
            a.inputs[1].default_value = tuple(sc)
            a.inputs[2].default_value = tuple(-lo * sc)
            nt.links.new(geo.outputs["Position"], a.inputs[0])
            nt.links.new(a.outputs[0], em.inputs["Color"])
        else:
            oi = nt.nodes.new("ShaderNodeObjectInfo")
            d = nt.nodes.new("ShaderNodeMath"); d.operation = "DIVIDE"; d.inputs[1].default_value = 255.0
            nt.links.new(oi.outputs["Object Index"], d.inputs[0])
            nt.links.new(d.outputs[0], em.inputs["Color"])
        mats[kind] = m
    return mats


def _read_exr(path):
    img = bpy.data.images.load(path, check_existing=False)
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(H, W, 4)[::-1]                                 # сверху вниз, как в картинке; альфа — деталь


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    names = a[1].split(",") if len(a) > 1 and a[1] else list(VIEWS)
    samples = int(a[2]) if len(a) > 2 else 96
    os.makedirs(os.path.join(out, "views"), exist_ok=True)
    S = bpy.context.scene
    cam = S.camera
    cam.data.lens = LENS
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.dof.use_dof = False
    S.render.resolution_x, S.render.resolution_y, S.render.resolution_percentage = W, H, 100
    S.render.use_motion_blur = False
    sets = list(tex_sets.SETS)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    for o in meshes:
        s = tex_sets.set_of(o.name)
        o.pass_index = sets.index(s) + 1 if s else 0
    lo = np.min([np.min([o.matrix_world @ Vector(c) for c in o.bound_box], 0) for o in meshes], 0) - 0.01
    hi = np.max([np.max([o.matrix_world @ Vector(c) for c in o.bound_box], 0) for o in meshes], 0) + 0.01
    sc = 1.0 / (hi - lo)
    mats = _points_material(lo, sc)
    vl = S.view_layers[0]
    meta_path = os.path.join(out, "views.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {"views": {}}
    meta["sets"] = sets
    meta["size"] = [W, H]
    look = (S.view_settings.view_transform, S.view_settings.look, S.view_settings.exposure, S.view_settings.gamma)
    for name in names:
        title, c, d, dist = VIEWS[name]
        c = Vector(c)
        cam.location = c + Vector(d).normalized() * dist
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        # 1) обычный рендер
        vl.material_override = None
        S.view_settings.view_transform, S.view_settings.look, S.view_settings.exposure, S.view_settings.gamma = look
        S.cycles.samples = samples
        S.cycles.use_denoising = True
        S.cycles.filter_width = 1.5
        S.render.image_settings.file_format = "PNG"
        S.render.image_settings.color_depth = "8"
        S.render.filepath = os.path.join(out, "views", f"{name}.png")
        bpy.ops.render.render(write_still=True)
        # 2) карта точек: без сглаживания и шумодава, данные как есть
        S.view_settings.view_transform, S.view_settings.look = "Standard", "None"
        S.view_settings.exposure, S.view_settings.gamma = 0.0, 1.0
        S.cycles.samples = 1
        S.cycles.use_denoising = False
        S.cycles.filter_width = 0.01
        S.render.image_settings.file_format = "OPEN_EXR"
        S.render.image_settings.color_depth = "32"
        S.render.image_settings.color_mode = "RGBA"
        S.render.film_transparent = True        # фон — прозрачный: иначе студийное окружение читалось номером набора
        res = {}
        for kind in ("pos", "set"):
            vl.material_override = mats[kind]
            tmp = os.path.join(out, "views", f"_{name}_{kind}.exr")
            S.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            res[kind] = _read_exr(tmp)
            os.remove(tmp)
        vl.material_override = None
        S.render.film_transparent = False
        S.render.image_settings.color_mode = "RGB"
        solid = (res["pos"][..., 3] > 0.99) & (res["set"][..., 3] > 0.99)
        sid = np.where(solid, np.rint(res["set"][..., 0] * 255.0), 0).astype(np.uint8)
        pos = ((res["pos"][..., :3] / sc + lo) * 1000.0).astype(np.float32)
        pos[sid == 0] = 0.0
        np.savez_compressed(os.path.join(out, "views", f"{name}_pts.npz"), pos=pos, set=sid)
        mmpp = dist * 1000.0 * (36.0 / LENS) / W
        meta["views"][name] = {"title": title, "cam": [v * 1000.0 for v in cam.location], "mm_per_px": mmpp}
        print("VIEW", name, title, "пикселей детали:", int((sid > 0).sum()), "мм/пикс %.3f" % mmpp)
    S.view_settings.view_transform, S.view_settings.look, S.view_settings.exposure, S.view_settings.gamma = look
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
