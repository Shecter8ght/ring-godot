"""Купе Ильи: запекание игровых карт с принятой отделки (стеки UCUPaint) на игровую сетку game_lp.py.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/game_bake.py -- [--channels color,normal,mra,ao] [--atlases body,glass,…] [--samples N]

Каждая деталь запекается только со своего high-poly (соседняя деталь не попадает в лучи); лучи — по замеру
game_lp.py (насколько high-poly выходит наружу и уходит внутрь игровой сетки). Каналы:
  color  — цвет, как его получает BSDF (sRGB);
  normal — нормали в касательном пространстве (OpenGL, как ждёт Godot), с микрорельефом стеков;
  mra    — R металл, G шероховатость, какую видит глаз: у лакированных (краска, карбон, диски) — шероховатость лака
           там, где он есть (пыль и грязь его гасят), B — непрозрачность (стёкла: своя прозрачность материала,
           пыль и разводы делают стекло мутнее);
  ao     — AO самой игровой сетки (щели, ниши, отсек), без стёкол, расстояние AO_DIST.
→ _asset_src/coupe_ilya_game/maps/raw/<атлас>_<канал>.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src/coupe_ilya_game"
REC = json.loads((WORK / "lp/parts.json").read_text(encoding="utf-8"))
LP_FILE = WORK / "lp/Coupe_Game_LP.blend"
OUT = WORK / "maps/raw"
OUT.mkdir(parents=True, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("--channels", default="color,normal,mra,ao")
ap.add_argument("--atlases", default="")
ap.add_argument("--samples", type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
CHANNELS = args.channels.split(",")
GROUP_ATLAS = {"body": "body", "glass": "glass", "wheel": "wheel", "wheel_state": "wheel", "bay": "bay",
               "interior": "interior", "const": None}
ATLASES = args.atlases.split(",") if args.atlases else list(REC["atlas_size"])
SAMPLES = {"color": 16, "normal": 8, "mra": 16, "ao": 96}
AO_DIST = 0.12
# стёкла: своя прозрачность и цвет основы (как в build_coupe.py / texture_coupe.py); насколько налёт мутит стекло
GLASS_BASE = {"glass": (0.22, (0.05, 0.06, 0.065)), "lamp_glass": (0.12, (0.80, 0.82, 0.85)),
              "lamp_red": (0.55, (0.55, 0.03, 0.03))}
GLASS_FILM = 0.85
BAKE_MARGIN = {a: max(3, REC["uv_margin_px"][a] // 2 - 1) for a in REC["atlas_size"]}
log = lambda *a: print("COUPE_BAKE", *a, flush=True)

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=REC["source"])
S = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
# объёмный текст номеров — сеткой (запекание берёт сетки)
for o in [o for o in bpy.data.objects if o.type == "FONT"]:
    name = o.name
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.name = name + "•font"
    o.hide_render = True
    mo = bpy.data.objects.new(name, me)
    mo.matrix_world = o.matrix_world.copy()
    for c in o.users_collection:
        c.objects.link(mo)
bpy.context.view_layer.update()
HP = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

# игровые представители (LOD0): из lp-файла, имена совпадут с high-poly и получат .001 — берём по порядку
reps = [m["rep_hp"] for m in REC["meshes"].values() if GROUP_ATLAS[m["group"]] in ATLASES]
need_ao = "ao" in CHANNELS
lod0 = [n for n in REC["objects"]] if need_ao else reps
with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
    asked = [n for n in src.objects if n in set(lod0)]
    dst.objects = list(asked)
lpc = bpy.data.collections.new("LP_BAKE")
S.collection.children.link(lpc)
LP = {}
for name, o in zip(asked, dst.objects):
    lpc.objects.link(o)
    LP[name] = o
for o in bpy.data.objects:                       # подтянутые родители-пустышки
    if o.type == "EMPTY" and o.users_collection == () and o.name not in S.collection.objects:
        lpc.objects.link(o)
bpy.context.view_layer.update()
for o in LP.values():
    o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
    o.visible_volume_scatter = o.visible_shadow = False

S.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != "CPU"
S.cycles.device = "GPU"
S.cycles.use_denoising = False
bk = S.render.bake
bk.margin_type = "EXTEND"
bk.normal_space = "TANGENT"
bk.use_cage = False

images: dict[tuple[str, str], list] = {}


def target(atlas: str, channel: str):
    key = (atlas, channel)
    if key not in images:
        size = REC["atlas_size"][atlas]
        im = bpy.data.images.new(f"{atlas}_{channel}", size, size, alpha=True, float_buffer=(channel == "normal"))
        im.colorspace_settings.name = "sRGB" if channel == "color" else "Non-Color"
        im.generated_color = (0.5, 0.5, 1.0, 0.0) if channel == "normal" else (0, 0, 0, 0)
        images[key] = [im, False]
    return images[key]


def set_target(o, atlas: str, channel: str):
    rec = target(atlas, channel)
    for m in o.data.materials:
        nt = m.node_tree
        node = nt.nodes.get("BAKE_TARGET") or nt.nodes.new("ShaderNodeTexImage")
        node.name = "BAKE_TARGET"
        node.image = rec[0]
        uvn = nt.nodes.get("BAKE_UV") or nt.nodes.new("ShaderNodeUVMap")
        uvn.name = "BAKE_UV"
        uvn.uv_map = "GameUV"
        nt.links.new(uvn.outputs["UV"], node.inputs["Vector"])
        nt.nodes.active = node
    return rec


def source(nt, name: str):
    """Что реально приходит во вход BSDF: сокет (выход стека) или значение."""
    p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if p is None:
        return None, 0.0
    inp = p.inputs[name]
    if inp.links:
        return inp.links[0].from_socket, None
    return None, inp.default_value


def feed(nt, sock_in, src) -> None:
    sock, value = src
    for l in list(sock_in.links):
        nt.links.remove(l)
    if sock is not None:
        nt.links.new(sock, sock_in)
    elif hasattr(value, "__len__"):
        sock_in.default_value = value if len(value) == len(sock_in.default_value) else (*value[:3], 1.0)[:len(sock_in.default_value)]
    else:
        sock_in.default_value = (value, value, value, 1.0) if sock_in.type == "RGBA" else value


def node(nt, kind: str, name: str):
    n = nt.nodes.get(name) or nt.nodes.new(kind)
    n.name = name
    return n


saved: dict[str, object] = {}


def route(channel: str) -> None:
    """Канал → Emission у материалов high-poly (для EMIT); normal — обратно BSDF."""
    for m in bpy.data.materials:
        if m.name.startswith("GAME •") or m.node_tree is None:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None:
            continue
        if m.name not in saved:
            link = out.inputs["Surface"].links[0] if out.inputs["Surface"].links else None
            saved[m.name] = link.from_socket if link else None
        if channel == "normal":
            if saved[m.name] is not None:
                nt.links.new(saved[m.name], out.inputs["Surface"])
            continue
        emit = node(nt, "ShaderNodeEmission", "BAKE_EMIT")
        emit.inputs["Strength"].default_value = 1.0
        if channel == "color":
            feed(nt, emit.inputs["Color"], source(nt, "Base Color"))
        else:
            comb = node(nt, "ShaderNodeCombineColor", "BAKE_COMB")
            feed(nt, comb.inputs["Red"], source(nt, "Metallic"))
            # шероховатость, какую видит глаз: лак там, где он есть
            mix = node(nt, "ShaderNodeMix", "BAKE_COAT_MIX")
            mix.data_type = "FLOAT"
            feed(nt, mix.inputs["Factor"], source(nt, "Coat Weight"))
            feed(nt, mix.inputs["A"], source(nt, "Roughness"))
            feed(nt, mix.inputs["B"], source(nt, "Coat Roughness"))
            nt.links.new(mix.outputs["Result"], comb.inputs["Green"])
            # непрозрачность: стекло — своя прозрачность, налёт мутит (отличие цвета от основы)
            for l in list(comb.inputs["Blue"].links):
                nt.links.remove(l)
            if m.name in GLASS_BASE:
                a0, base = GLASS_BASE[m.name]
                bw = node(nt, "ShaderNodeRGBToBW", "BAKE_BW")
                feed(nt, bw.inputs["Color"], source(nt, "Base Color"))
                lum0 = 0.2126 * base[0] + 0.7152 * base[1] + 0.0722 * base[2]
                diff = node(nt, "ShaderNodeMath", "BAKE_DIFF")
                diff.operation = "SUBTRACT"
                nt.links.new(bw.outputs["Val"], diff.inputs[0])
                diff.inputs[1].default_value = lum0
                ab = node(nt, "ShaderNodeMath", "BAKE_ABS")
                ab.operation = "ABSOLUTE"
                nt.links.new(diff.outputs[0], ab.inputs[0])
                cov = node(nt, "ShaderNodeMapRange", "BAKE_COV")
                nt.links.new(ab.outputs[0], cov.inputs["Value"])
                cov.inputs["From Min"].default_value = 0.0
                cov.inputs["From Max"].default_value = 0.25
                cov.inputs["To Min"].default_value = a0
                cov.inputs["To Max"].default_value = a0 + (1 - a0) * GLASS_FILM
                cov.clamp = True
                nt.links.new(cov.outputs["Result"], comb.inputs["Blue"])
            else:
                comb.inputs["Blue"].default_value = 1.0
            nt.links.new(comb.outputs["Color"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])


def bake_mesh(key: str, rec: dict, channel: str) -> None:
    atlas = GROUP_ATLAS[rec["group"]]
    o = LP[rec["rep_hp"]]
    src = HP[rec["rep_hp"]]
    bpy.ops.object.select_all(action="DESELECT")
    src.hide_render = False
    src.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    t = set_target(o, atlas, channel)
    S.cycles.samples = args.samples or SAMPLES[channel]
    cg = rec["cage"]
    bpy.ops.object.bake(type="NORMAL" if channel == "normal" else "EMIT", use_clear=not t[1],
                        use_selected_to_active=True, cage_extrusion=cg["extrusion_m"], max_ray_distance=cg["max_ray_m"],
                        margin=BAKE_MARGIN[atlas])
    t[1] = True


for ch in [c for c in CHANNELS if c != "ao"]:
    route(ch)
    for key, rec in REC["meshes"].items():
        if GROUP_ATLAS[rec["group"]] in ATLASES:
            bake_mesh(key, rec, ch)
    log(ch, "готово")

if need_ao:
    # AO игровой сетки: все игровые детали LOD0 видны лучам, high-poly и стёкла — нет
    for o in HP.values():
        o.hide_render = True
    coll_of = {name: REC["objects"][name]["collection"] for name in LP}
    for name, o in LP.items():
        g = REC["meshes"][REC["objects"][name]["mesh"]]["group"]
        vis = g not in ("glass", "const")
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_shadow = o.visible_transmission = vis
    # капот открыт: так отсек и смотрят (закрытый капот затенял бы верх двигателя)
    for o in lpc.objects:
        if o.type == "EMPTY" and o.name.startswith("Hood_Hinge"):
            o.rotation_euler.x = -0.87
    bpy.context.view_layer.update()
    S.world = S.world or bpy.data.worlds.new("AO")
    S.world.light_settings.distance = AO_DIST
    # состояния: снятое колесо — кирпичи без колеса, нет аккумулятора — висящие клеммы без него
    OTHER = {"State_Wheel_FL_Off": "State_Wheel_FL_On", "State_Battery_Missing": "State_Battery_Installed"}

    def show_state(state: str) -> None:
        off = OTHER.get(state)
        for name, o in LP.items():
            c = coll_of[name]
            if c in OTHER:
                o.hide_render = c != state
            elif c in OTHER.values():
                o.hide_render = c == off
            else:
                o.hide_render = False

    for key, rec in REC["meshes"].items():
        atlas = GROUP_ATLAS[rec["group"]]
        if atlas not in ATLASES or atlas == "glass":
            continue
        o = LP[rec["rep_hp"]]
        show_state(coll_of[rec["rep_hp"]])
        hidden = False
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        t = set_target(o, atlas, "ao")
        S.cycles.samples = args.samples or SAMPLES["ao"]
        bpy.ops.object.bake(type="AO", use_clear=not t[1], use_selected_to_active=False, margin=BAKE_MARGIN[atlas])
        t[1] = True
        o.hide_render = hidden
    log("ao", "готово")

for (atlas, ch), (im, used) in images.items():
    if not used:
        continue
    path = OUT / f"{atlas}_{ch}.png"
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    if ch == "normal":
        im.use_half_precision = False
    im.save()
    log("сохранено", path.name)
print("COUPE_BAKE_DONE", flush=True)
