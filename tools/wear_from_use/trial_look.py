"""Следы использования из данных игры, шаг 4: пробный вид ВЕРАС-54 v13 на автоматических масках (копия, не исходник).

В копии (hp_texels.py) в стеки UCUPaint v04 кладутся слои «U• … (из клипов)» поверх принятых: маска места — картинка
wear_masks.py в развёртке WearUV, рисунок — прежние рисунки владельца (Маски_АЛЬФА, рабочие копии tex/masks) коробочной
проекцией и шум. Принятые слои, которые раньше ставили те же следы руками (декали отпечатков и ладоней, полировка
рукоятки и рамы по номеру детали, планки, крючок и защёлка), в копии выключены, но не удалены — их можно включить
и сравнить в одном файле. Числа слоёв — как у принятых слоёв v04 того же смысла (tex13_look.py, TEX13_LOOK=v04).

blender --background --factory-startup --python-exit-code 1 --python tools/wear_from_use/trial_look.py -- <копия.blend> <папка масок>
  (маски подключаются относительным путём; копия пересохраняется)
blender … trial_look.py -- <копия.blend> <папка масок> --view <вид,…> --out <папка> — снимки масок цветом без сохранения:
  красный — потёртость (руки, магазин, обвесы, ремень), зелёный — отпечатки пальцев, синий — ладони
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
ARGS = sys.argv[sys.argv.index("--") + 1:]
COPY, MASKS = ARGS[0], Path(ARGS[1]).resolve()
VIEW = ARGS[ARGS.index("--view") + 1] if "--view" in ARGS else ""
OUTDIR = Path(ARGS[ARGS.index("--out") + 1]).resolve() if "--out" in ARGS else MASKS / "views"
UV = "WearUV"
OBJS = json.loads((ROOT / "_asset_src/veras54_v13/use_wear/texels/objects.json").read_text(encoding="utf-8"))
SET_OF = {v["name"]: v["set"] for v in OBJS.values()}

bpy.context.preferences.use_preferences_save = False
addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
bpy.ops.wm.open_mainfile(filepath=COPY)
os.environ.setdefault("TEX13_LOOK", "v04")
spec = importlib.util.spec_from_file_location("tex13_look", ROOT / "_asset_src/veras54_v13/tex/tex13_look.py")
look = importlib.util.module_from_spec(spec)
spec.loader.exec_module(look)
U, MMOD = look.U, look.MMOD


def mask_img(s, ch):
    name = f"USE • {s} • {ch}"
    im = bpy.data.images.get(name)
    if im is None:
        im = bpy.data.images.load(str(MASKS / f"{s}_{ch}.png"), check_existing=False)
        im.name = name
    im.colorspace_settings.name = "Non-Color"
    return im


# ------------------------------------------------------------------ снимки масок (без сохранения)
if VIEW:
    sc = bpy.context.scene
    mats = {}
    for s in ("Steel", "Polymer", "Magazine"):
        m = bpy.data.materials.new(f"_use_view_{s}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = UV
        comb = nt.nodes.new("ShaderNodeCombineColor")

        def tex(ch):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = mask_img(s, ch)
            t.interpolation = "Linear"
            nt.links.new(uvn.outputs[0], t.inputs[0])
            return t.outputs[0]

        def mx(a, b):
            n = nt.nodes.new("ShaderNodeMath")
            n.operation = "MAXIMUM"
            nt.links.new(a, n.inputs[0])
            nt.links.new(b, n.inputs[1])
            return n.outputs[0]

        red = mx(mx(tex("hand_rub"), tex("mag_rub")), mx(tex("mount_wear"), tex("sling_wear")))
        base = nt.nodes.new("ShaderNodeMath")       # серый фон, чтобы видеть форму
        base.operation = "MULTIPLY_ADD"
        nt.links.new(red, base.inputs[0])
        base.inputs[1].default_value = 0.9
        base.inputs[2].default_value = 0.06
        nt.links.new(base.outputs[0], comb.inputs[0])
        g = nt.nodes.new("ShaderNodeMath")
        g.operation = "MULTIPLY_ADD"
        nt.links.new(tex("hand_prints"), g.inputs[0])
        g.inputs[1].default_value = 0.9
        g.inputs[2].default_value = 0.06
        nt.links.new(g.outputs[0], comb.inputs[1])
        b = nt.nodes.new("ShaderNodeMath")
        b.operation = "MULTIPLY_ADD"
        nt.links.new(tex("hand_palms"), b.inputs[0])
        b.inputs[1].default_value = 0.9
        b.inputs[2].default_value = 0.06
        nt.links.new(b.outputs[0], comb.inputs[2])
        nt.links.new(comb.outputs[0], em.inputs["Color"])
        mats[s] = m
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name in SET_OF:
            o.data.materials.clear()
            o.data.materials.append(mats[SET_OF[o.name]])
        else:
            o.hide_render = True
    for o in bpy.data.objects:
        if o.type in ("LIGHT", "CAMERA"):
            o.hide_render = True
    w = bpy.data.worlds.new("_flat")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
    sc.world = w
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.view_settings.view_transform = "Raw"         # уровни маски на снимке — как в PNG
    cam = bpy.data.objects.new("_cam", bpy.data.cameras.new("_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.002
    # направление от цели к камере, цель (мм), расстояние (м), фокусное (мм)
    VIEWS = {
        "full_l": ((0.0, 1.0, 0.12), (235, 0, -50), 1.75, 50), "full_r": ((0.0, -1.0, 0.12), (235, 0, -50), 1.75, 50),
        "full_b": ((0.0, -0.35, -1.0), (235, 0, -40), 1.75, 50), "full_t": ((0.0, -0.3, 1.0), (235, 0, 0), 1.75, 50),
        "grip_l": ((0.2, 0.97, 0.05), (32, 0, -88), 0.32, 60), "grip_r": ((0.2, -0.97, 0.05), (32, 0, -88), 0.32, 60),
        "grip_f": ((0.95, -0.3, -0.1), (40, 0, -88), 0.32, 60), "grip_b": ((-0.95, -0.3, -0.1), (30, 0, -88), 0.32, 60),
        "hg_l": ((0.0, 0.97, -0.2), (345, 0, 0), 0.45, 55), "hg_r": ((0.0, -0.97, -0.2), (345, 0, 0), 0.45, 55),
        "hg_b": ((0.2, -0.4, -0.9), (345, 0, -20), 0.45, 55), "recv_r": ((0.25, -0.95, 0.25), (140, 0, -10), 0.42, 55),
        "recv_l": ((-0.2, 0.95, 0.25), (140, 0, -10), 0.42, 55), "mag_r": ((0.2, -0.98, 0.05), (205, 0, -110), 0.4, 55),
        "mag_l": ((0.2, 0.98, 0.05), (205, 0, -110), 0.4, 55), "magwell": ((0.1, -0.5, -0.86), (190, 0, -40), 0.22, 60),
        "rail": ((0.1, -0.6, 0.8), (160, 0, 40), 0.25, 60), "handle": ((0.55, -0.75, 0.35), (215, -25, 12), 0.18, 60),
        "gas_l": ((0.1, 0.9, -0.3), (520, 0, -10), 0.28, 60), "stock_l": ((0.0, 0.97, 0.15), (-140, 0, -55), 0.42, 55),
        "stock_r": ((0.0, -0.97, 0.15), (-140, 0, -55), 0.42, 55), "rear_l": ((-0.3, 0.9, 0.2), (0, 0, -10), 0.22, 60),
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for v in VIEW.split(","):
        d, t, dist, lens = VIEWS[v]
        t = Vector(t) * 0.001
        cam.location = t + Vector(d).normalized() * dist
        cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        sc.render.filepath = str(OUTDIR / f"masks_{v}.png")
        bpy.ops.render.render(write_still=True)
        print("USE_VIEW", sc.render.filepath, flush=True)
    sys.exit(0)


# ------------------------------------------------------------------ слои в стеках
def uv_mask(layer, s, ch, first=True, ramp=(0.0, 1.0)):
    m = U.Mask.add_new_mask(layer, f"Место из данных • {ch}", "IMAGE", "UV", UV, image=mask_img(s, ch),
                            socket_input_name="Color", blend_type="MULTIPLY" if first else "LIGHTEN")
    if ramp != (0.0, 1.0):
        MMOD.add_new_mask_modifier(m, "RAMP")
        r = U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp]
        r.color_ramp.elements[0].position = ramp[0]
        r.color_ramp.elements[1].position = ramp[1]
    return m


def layer(t, name, values, amount, s, chans, ramp=(0.0, 1.0)):
    l = look.new_layer(t, name, values, amount)
    for i, ch in enumerate(chans):
        uv_mask(l, s, ch, first=(i == 0), ramp=ramp)
    return l


# что выключить в копии: слои v04, ставившие те же следы руками (по началу имени)
MANUAL = {
    "01 • Phosphate steel / black coating": ("05c", "05d", "09 •"),
    "02 • Machined steel": ("05c", "09 •"),
    "03 • Injection moulded polymer": ("06c", "06d", "09 •", "10 •"),
    "04 • Magazine polymer": ("09 •", "10 •"),
}
STEEL = {  # материал: (основа, шероховатость) — как в v04
    "01 • Phosphate steel / black coating": ((0.008, 0.008, 0.009), 0.86),
    "02 • Machined steel": ((0.010, 0.010, 0.011), 0.82),
    "09 • Interior / fasteners": ((0.011, 0.011, 0.012), 0.82),
}
POLY = {"03 • Injection moulded polymer": ((0.024, 0.025, 0.023), 0.74), "04 • Magazine polymer": ((0.018, 0.019, 0.018), 0.70)}
OIL = look.OIL

# материал → набор текстур копии (по деталям из parts.json); общий на разные наборы — нельзя (маска из другой картинки)
users = {}
for o in bpy.data.objects:
    if o.type == "MESH" and o.name in SET_OF:
        for slot in o.material_slots:
            if slot.material:
                users.setdefault(slot.material.name, set()).add(SET_OF[o.name])
print("MATERIAL_SETS", {k: sorted(v) for k, v in users.items()}, flush=True)


def drop_auto(t):
    """Повторный запуск: прежние слои «U• …» снять, чтобы не копились."""
    # remove_layer сбрасывает состояние панели UCUPaint — в фоне его нет, заготовки по числу каналов
    ui = bpy.context.window_manager.ypui.layer_ui
    while len(ui.channels) < len(t.yp.channels):
        ui.channels.add()
    removed = 0
    for i in reversed(range(len(t.yp.layers))):
        n = t.yp.layers[i].name
        if n[:1] == "U" and n[1:].split(" ", 1)[0].isdigit():
            U.Layer.remove_layer(t.yp, i)
            removed += 1
    if removed:
        t.yp.active_layer_index = 0
        U.input_outputs.check_all_channel_ios(t.yp, reconnect=True)
        U.node_connections.reconnect_yp_nodes(t)
        print("AUTO_REMOVED", removed, flush=True)


def disable_manual(mat_name, t):
    off = []
    for lay in t.yp.layers:
        if lay.name.startswith(MANUAL.get(mat_name, ())):
            lay.enable = False
            off.append(lay.name)
    print("MANUAL_OFF", mat_name, off, flush=True)


# металл почти чёрный и матовый (v04, владелец): заполировано и жир ладоней — только где трения много (порог Ramp выше),
# иначе касания ложатся мутным облаком на плоскости коробки
def steel(mat_name):
    s = next(iter(users[mat_name]))
    mat = bpy.data.materials[mat_name]
    look.activate(mat)
    t = look.native_tree(mat)
    drop_auto(t)
    disable_manual(mat_name, t)
    base, rough = STEEL[mat_name]
    sh = (0.33, 0.6, 0.21)
    l = layer(t, "U1 • Залощено руками (из клипов)", {"Color": (0.12, 0.12, 0.13), "Metallic": 1.0, "Roughness": 0.30}, 0.65, s, ["hand_rub"], (0.40, 0.95))
    look.noise_mask(l, "Неравномерная полировка", 18, 0.30, 0.80, sh)
    l = layer(t, "U2 • Кромки в касании: вытерто до стали (из клипов)", {"Color": (0.24, 0.24, 0.245), "Metallic": 1.0, "Roughness": 0.30}, 0.60, s, ["hand_rub"], (0.25, 0.85))
    look.edge_mask(l, 1.0, 0.10, 0.28, name="Кромки")
    look.noise_mask(l, "Где вытерто", 15, 0.25, 0.70, (sh[0] + 1.5, sh[1], sh[2]))
    l = layer(t, "U3 • Горловина шахты: магазин (из клипов)", {"Color": (0.28, 0.28, 0.28), "Metallic": 1.0, "Roughness": 0.32}, 0.75, s, ["mag_rub"], (0.05, 0.70))
    look.image_mask(l, "chips_scuffs_01", 26, "Рваный край — потёртости владельца", (sh[0] + 0.01, sh[1], sh[2]))
    l = layer(t, "U4 • Планки: обвесы ставят и снимают (из сокетов)", {"Color": (0.28, 0.28, 0.28), "Metallic": 1.0, "Roughness": 0.32}, 0.75, s, ["mount_wear"], (0.10, 0.80))
    look.image_mask(l, "chips_scuffs_01", 20, "Рваный край — потёртости владельца", (sh[0] + 0.03, sh[1], sh[2]))
    l = layer(t, "U5 • Антабки и ремень (из точек ремня)", {"Color": (0.24, 0.24, 0.245), "Metallic": 1.0, "Roughness": 0.30}, 0.70, s, ["sling_wear"], (0.10, 0.80))
    look.noise_mask(l, "Неравномерно", 6, 0.30, 0.70, (sh[0] + 4, sh[1], sh[2]))
    l = layer(t, "U6 • Жир ладоней (из клипов)", {"Color": tuple(c * 1.5 for c in base), "Roughness": 0.30, OIL: 0.5}, 0.5, s, ["hand_palms"], (0.35, 0.95))
    look.image_mask(l, "oil_spotty_04", 55, "Пятнистая масляная плёнка владельца", (sh[0] + 0.02, sh[1], sh[2]))
    l = layer(t, "U7 • Жировые отпечатки пальцев (из клипов)", {"Color": tuple(c * 2.0 for c in base), "Roughness": 0.16, OIL: 1.0}, 1.0, s, ["hand_prints"], (0.05, 0.60))
    look.image_mask(l, "fp_group_many", 60, "Отпечатки владельца (россыпь)", (sh[0], sh[1] + 0.02, sh[2]))
    l = layer(t, "U8 • Жировые отпечатки пальцев, второй рисунок", {"Color": tuple(c * 2.0 for c in base), "Roughness": 0.16, OIL: 1.0}, 0.8, s, ["hand_prints"], (0.15, 0.70))
    look.image_mask(l, "fp_group_scatter", 48, "Отпечатки владельца (вразброс)", (sh[0] + 0.013, sh[1], sh[2] + 0.007), rot_deg=(0, 0, 90))


def polymer(mat_name):
    s = next(iter(users[mat_name]))
    mat = bpy.data.materials[mat_name]
    look.activate(mat)
    t = look.native_tree(mat)
    drop_auto(t)
    disable_manual(mat_name, t)
    base, rough = POLY[mat_name]
    sh = (0.17, 0.3, 0.05)
    l = layer(t, "U1 • Залощено руками (из клипов)", {"Color": tuple(c * 1.35 for c in base), "Roughness": 0.34, OIL: 0.25}, 0.85, s, ["hand_rub"], (0.05, 0.75))
    look.noise_mask(l, "Неравномерная полировка", 30, 0.20, 0.75, sh)
    l = layer(t, "U2 • Вытерто до глянца: магазин в шахте, ремень (из клипов)", {"Color": tuple(c * 1.9 for c in base), "Roughness": rough - 0.24}, 0.70, s, ["mag_rub", "sling_wear"], (0.05, 0.70))
    look.noise_mask(l, "Разрыв", 4.0, 0.35, 0.60, (sh[0], sh[1] + 0.2, sh[2]))
    l = layer(t, "U3 • Жир ладоней (из клипов)", {"Color": tuple(c * 1.7 for c in base), "Roughness": 0.28, OIL: 0.6}, 0.9, s, ["hand_palms"], (0.05, 0.75))
    look.image_mask(l, "oil_spotty_04", 55, "Пятнистая масляная плёнка владельца", (sh[0] + 0.02, sh[1], sh[2]))
    l = layer(t, "U4 • Жировые отпечатки пальцев (из клипов)", {"Color": tuple(c * 2.4 for c in base), "Roughness": 0.20, OIL: 1.0}, 1.0, s, ["hand_prints"], (0.05, 0.60))
    look.image_mask(l, "fp_group_many", 70, "Отпечатки владельца (россыпь)", (sh[0], sh[1] + 0.02, sh[2]))
    l = layer(t, "U5 • Жировые отпечатки пальцев, второй рисунок", {"Color": tuple(c * 2.4 for c in base), "Roughness": 0.20, OIL: 1.0}, 0.8, s, ["hand_prints"], (0.15, 0.70))
    look.image_mask(l, "fp_group_scatter", 55, "Отпечатки владельца (вразброс)", (sh[0] + 0.011, sh[1], sh[2] + 0.009), rot_deg=(0, 0, 90))


for name in STEEL:
    if name in users:
        steel(name)
for name in POLY:
    if name in users:
        polymer(name)
for mat in bpy.data.materials:
    if mat.use_nodes and any(look.is_yp(n) for n in mat.node_tree.nodes):
        t = look.native_tree(mat)
        U.input_outputs.check_all_channel_ios(t.yp, reconnect=True)

# маски — рядом с копией, относительным путём
for im in bpy.data.images:
    if im.name.startswith("USE • "):
        im.filepath = bpy.path.relpath(im.filepath_raw, start=str(Path(COPY).parent))
root = bpy.data.objects["VERAS54"]
root["Use wear trial"] = ("v01 (2026-10-26): следы использования из данных игры (tools/wear_from_use): клипы рук v13, путь магазина, "
                          "сокеты обвесов, точки ремня → маски в развёртке WearUV (папка masks рядом); слои «U• …» в стеках, "
                          "прежние ручные слои тех же следов выключены (не удалены). Исходник v04 не менялся.")
bpy.ops.wm.save_mainfile(filepath=COPY)
print("TRIAL_SAVED", COPY, flush=True)
