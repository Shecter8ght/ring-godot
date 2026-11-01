# Цевьё по ролику Dolinskyi «Realistic Hard-Anodized Metal in Substance Painter» (эксперимент владельца 2026-11-01,
# docs/assets/handguard_dolinskyi_plan.md). Квадрорельсовое drop-in цевьё под M4 по типу FAB Defense NFR: длина 177,
# ширина 55, высота 60 мм (магазины); форма — по кадрам ролика 1:58, 7:54 и фото автора 3:00–3:35.
# Одна функция строит high-poly (фаски модификатором) и low-poly (те же формы без фасок, меньше сегментов).
# Надписи и номера планок — не в сетке: в ролике это маска текстуры (decal mask).
# Оси: +X вперёд (к дулу), +Z вверх, +Y — левая сторона стрелка. Начало — ось канала у заднего торца буртика.
#   blender --background --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/build.py
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ar15"))
import lib as L  # noqa: E402

L.ROUND_K = 1.0          # у AR-15 фаски утроены по слову владельца; здесь — ширина как задана

OUT_DIR = "E:/Models Blender/WEAPONS/Цевьё — Dolinskyi, анодирование 2026-11-01"
OUT_BLEND = os.path.join(OUT_DIR, "Цевьё_Dolinskyi_форма_v01.blend")

# размеры — dims.py (общие с масками)
sys.path.insert(0, HERE)
from dims import *  # noqa: E402,F401,F403


def rail_profile(depth):
    """Сечение планки (u — поперёк, h — от верха зуба вниз), основание — на глубине depth."""
    return [(-RAIL_TOP_HW, -depth), (RAIL_TOP_HW, -depth), (RAIL_TOP_HW, -2 * RAIL_V_D), (RAIL_V_HW, -RAIL_V_D),
            (RAIL_TOP_HW, 0.0), (-RAIL_TOP_HW, 0.0), (-RAIL_V_HW, -RAIL_V_D), (-RAIL_TOP_HW, -2 * RAIL_V_D)]


def to_yz(side, u, h):
    if side == "top":
        return (u, TOP_CREST + h)
    if side == "bot":
        return (u, -BOT_CREST - h)
    if side == "left":
        return (SIDE_CREST + h, u)
    return (-SIDE_CREST - h, u)


def rail(name, side, x0, x1, coll):
    crest = {"top": TOP_CREST, "bot": BOT_CREST}.get(side, SIDE_CREST)
    depth = crest - STEM_TO
    pts = [to_yz(side, u, h) for u, h in rail_profile(depth)]
    return L.prism_yz(name, pts, x0, x1, coll)


def slot_cutters(side, x0, x1, coll):
    out = []
    for i, xs in enumerate(slot_starts(x0, x1)):
        if side == "top":
            b = L.box(f"c_{side}_{i}", xs, xs + SLOT_W, -14, 14, TOP_CREST - SLOT_D, TOP_CREST + 2, coll)
        elif side == "bot":
            b = L.box(f"c_{side}_{i}", xs, xs + SLOT_W, -14, 14, -BOT_CREST - 2, -BOT_CREST + SLOT_D, coll)
        elif side == "left":
            b = L.box(f"c_{side}_{i}", xs, xs + SLOT_W, SIDE_CREST - SLOT_D, SIDE_CREST + 2, -14, 14, coll)
        else:
            b = L.box(f"c_{side}_{i}", xs, xs + SLOT_W, -SIDE_CREST - 2, -SIDE_CREST + SLOT_D, -14, 14, coll)
        out.append(b)
    return out


def stadium(length, width, seg):
    """Контур «стадиона» вдоль оси b (длина) — точки (a, b)."""
    r = width / 2
    c = length / 2 - r
    pts = []
    for k in range(seg + 1):
        t = math.pi * k / seg
        pts.append((r * math.cos(t), c + r * math.sin(t)))
    for k in range(seg + 1):
        t = math.pi + math.pi * k / seg
        pts.append((r * math.cos(t), -c + r * math.sin(t)))
    return pts


def window_cutter(name, xc, theta0, coll, seg):
    """Окно на диагонали трубы: контур на развёртке цилиндра, стенки радиальные (как фреза по нормали)."""
    import bmesh
    sgn = 1.0 if (theta0 % 180.0) < 90.0 else -1.0      # +s — к ближней планке сверху или снизу (45, 225: θ растёт)
    tilt = math.radians(WIN_TILT)
    pts = []
    for a, b in stadium(WIN_LEN, WIN_W, seg):
        # дальний от горизонтали конец (+b) уходит назад: поворот на tilt
        x = xc + a * math.cos(tilt) - b * math.sin(tilt)
        s = a * math.sin(tilt) + b * math.cos(tilt)
        pts.append((x, s))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for r in (R_IN - 3.0, R_OUT + 3.0):
        ring = []
        for x, s in pts:
            th = math.radians(theta0) + sgn * s / R_OUT
            ring.append(bm.verts.new(L.v(x, r * math.cos(th), r * math.sin(th))))
        rings.append(ring)
    n = len(pts)
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[1])))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((rings[0][i], rings[1][i], rings[1][j], rings[0][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def merge(objs, name):
    return L.join(objs, name) if len(objs) > 1 else objs[0]


def build(tag, coll, hp):
    seg_tube = 192 if hp else 64
    seg_win = 16 if hp else 6
    seg_hole = 48 if hp else 20
    mat = "Alu_anodized"
    body = L.lathe(f"{tag}_body", [(BODY_X[0], R_IN), (BODY_X[0], R_OUT), (BODY_X[1], R_OUT), (BODY_X[1], R_IN)],
                   coll, mat, seg=seg_tube, cz=0.0)
    lip = L.lathe(f"{tag}_lip", [(LIP_X[0], R_IN), (LIP_X[0], R_LIP), (LIP_X[1] + 0.5, R_LIP), (LIP_X[1] + 0.5, R_IN)],
                  coll, mat, seg=seg_tube, cz=0.0)
    L.boolean(body, lip, "UNION")
    for side, (x0, x1) in (("top", TOP_X), ("bot", BOT_X), ("left", SIDE_X), ("right", SIDE_X)):
        L.boolean(body, rail(f"{tag}_rail_{side}", side, x0, x1, coll), "UNION")
    for sgn in (1, -1):
        for x0, x1 in PADS:
            y0, y1 = (19.0, PAD_FACE) if sgn > 0 else (-PAD_FACE, -19.0)
            L.boolean(body, L.box(f"{tag}_pad", x0, x1, y0, y1, -PAD_HZ, PAD_HZ, coll), "UNION")
    # пазы планок — один резак на все
    cut = []
    for side, (x0, x1) in (("top", TOP_X), ("bot", BOT_X), ("left", SIDE_X), ("right", SIDE_X)):
        cut += slot_cutters(side, x0, x1, coll)
    L.boolean(body, merge(cut, f"{tag}_cut_slots"))
    # окна на четырёх диагоналях
    cut = []
    for theta0 in (45.0, 135.0, 225.0, 315.0):
        for i in range(WIN_N):
            cut.append(window_cutter(f"{tag}_win_{int(theta0)}_{i}", WIN_X0 + i * PITCH, theta0, coll, seg_win))
    L.boolean(body, merge(cut, f"{tag}_cut_windows"))
    # гнёзда QD — сквозные отверстия в площадках
    cut = []
    for x0, x1 in PADS:
        cut.append(L.cyl(f"{tag}_hole", -32.0, 32.0, HOLE_R, coll, seg=seg_hole, cy=(x0 + x1) / 2, cz=0.0, axis="Y"))
    L.boolean(body, merge(cut, f"{tag}_cut_holes"))
    # «замочная скважина» под газовую трубку и вырезы буртика против проворота
    cut = [L.cyl(f"{tag}_key", -1.0, 9.0, KEY_R, coll, seg=seg_hole, cy=0.0, cz=KEY_Z, axis="X")]
    cut.append(L.box(f"{tag}_notch_l", -1.0, LIP_X[1], 17.0, 22.0, -2.0, 2.0, coll))
    cut.append(L.box(f"{tag}_notch_r", -1.0, LIP_X[1], -22.0, -17.0, -2.0, 2.0, coll))
    cut.append(L.box(f"{tag}_notch_b", -1.0, LIP_X[1], -2.0, 2.0, -22.0, -17.0, coll))
    L.boolean(body, merge(cut, f"{tag}_cut_rear"))
    # спереди — расточка под колпак цевья
    L.boolean(body, L.cyl(f"{tag}_front_bore", BODY_X[1] - 5.0, BODY_X[1] + 1.0, R_IN + 1.1, coll,
                          seg=seg_tube, cy=0.0, cz=0.0, axis="X"))
    body.name = tag
    body.data.name = tag
    if hp:
        L.finish(body, w=0.4, seg=3, angle=30.0)
    else:
        L.clean(body)
        L.auto_sharp(body, 40)
    return body


def studio():
    """Студия для просмотра формы владельцем: светлая «глина» (как белая модель в кадре ролика 1:58), HDRI студии
    Blender в отражениях и свете, камера 3/4 сзади сверху со стороны надписей, Cycles, вьюпорт сразу Rendered."""
    sc = bpy.context.scene
    m = L.material("Alu_anodized")
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.62, 0.62, 0.62, 1.0)
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Metallic"].default_value = 0.0
    w = bpy.data.worlds.new("Студия формы")
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(os.path.dirname(bpy.app.binary_path), "5.2", "datafiles",
                                                  "studiolights", "world", "studio.exr"))
    env.image.pack()
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 1.2
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    sc.world = w
    cd = bpy.data.cameras.new("Камера формы")
    cam = bpy.data.objects.new("Камера формы", cd)
    sc.collection.objects.link(cam)
    tgt = Vector((0.090, 0.0, 0.002))
    cam.location = tgt + Vector((-0.45, -0.80, 0.42)).normalized() * 0.44
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.cycles.preview_samples = 32
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = False
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    for scr in bpy.data.screens:
        for ar in scr.areas:
            if ar.type == "VIEW_3D":
                for sp in ar.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    hp_coll = L.collection("High-poly")
    lp_coll = L.collection("Low-poly")
    hp = build("handguard_high", hp_coll, True)
    lp = build("handguard_low", lp_coll, False)
    lp_coll.hide_render = True
    for o in (hp, lp):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        mn = [min(c[i] for c in bb) / L.MM for i in range(3)]
        mx = [max(c[i] for c in bb) / L.MM for i in range(3)]
        print("BOX", o.name, [round(a, 2) for a in mn], [round(a, 2) for a in mx], "tris", L.tris(o),
              "verts", len(o.data.vertices))
    studio()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("SAVED", OUT_BLEND)


if __name__ == "__main__":
    main()
