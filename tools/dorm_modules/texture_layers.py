"""Слоистые материалы общежития (Blender): облупленная краска, побелка → штукатурка → кирпич, паркет «ёлочкой»,
плитка 20 × 20 с выбитыми, треснувшими и сколотыми плитками. Карты — из Designer (sd_paint.py, sd_plaster.py
+ post_cells.py) и gen_floor_maps.py в папке textures комплекта.

Износ на стенах — атрибут цвета вершин «Износ» (R — краска/побелка, G — штукатурка до кирпича, B — грязь),
его раскладывает wear_layout() и можно докрашивать кистью (Vertex Paint). Доли повреждений — узлы «Значение»
в начале каждого материала (подписаны по-русски), их можно крутить в редакторе узлов.
Выполняется из texture_modules.py (общий помощник узлов G).
"""
import math

import bmesh
import bpy
from mathutils import Vector

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures"
PAINT_LINE = 2.0


def tex_paths() -> dict:
    p = {}
    for k in ["crack_mask", "peel_field", "paint_tone", "paint_height", "plaster_tone", "plaster_height"]:
        p["paint_" + k] = f"{KIT}/paint/{k}.png"
    for k in ["wash_field", "wash_crack", "wash_tone", "loss_field", "plaster_crack", "plaster_tone", "plaster_height", "crumble"]:
        p["plaster_" + k] = f"{KIT}/plaster/{k}.png"
    for k in ["parquet_color", "parquet_height", "parquet_id", "parquet_crack", "parquet_mastic"]:
        p[k] = f"{KIT}/parquet/{k}.png"
    for k in ["tile_id", "tile_tone", "tile_height", "tile_crack", "tile_chip", "tile_glue"]:
        p[k] = f"{KIT}/tiles/{k}.png"
    for k in ["albedo", "normal", "arm"]:
        p["brick_" + k] = f"{KIT}/brick/brick_{k}.jpg"
    return p


def param(g, label: str, value: float):
    """Подписанный узел «Значение» — ползунок материала."""
    nd = g.node("ShaderNodeValue")
    nd.label = label
    nd.name = label
    nd.outputs[0].default_value = value
    return nd.outputs[0]


def gray(g, path, vec):
    return g.image(path, vec, False).outputs[0]


def smoothstep(g, e0, e1, x):
    """smoothstep через Map Range (e0, e1 — сокеты или числа)."""
    nd = g.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    for sock, v in ((nd.inputs["From Min"], e0), (nd.inputs["From Max"], e1), (nd.inputs["Value"], x)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        else:
            g.link(v, sock)
    return nd.outputs[0]


def wear_attr(g):
    nd = g.node("ShaderNodeAttribute", attribute_name="Износ", attribute_type="GEOMETRY")
    return g.sep(nd.outputs["Vector"])


def world_noise(g, scale: float):
    return g.noise(g.geo.outputs["Position"], scale, 3.0, 0.5)


# ---------------------------------------------------------------- стена: краска / побелка

def paint_layer(g, P, vec, wear):
    """Масляная краска по штукатурке: отслоение по полю ниже износа, светлая загнутая кромка над порогом."""
    f = gray(g, P["paint_peel_field"], vec)
    crack = gray(g, P["paint_crack_mask"], vec)
    tone = gray(g, P["paint_paint_tone"], vec)
    ph = gray(g, P["paint_paint_height"], vec)
    pt = gray(g, P["paint_plaster_tone"], vec)
    plh = gray(g, P["paint_plaster_height"], vec)
    peeled = g.math("SUBTRACT", 1.0, smoothstep(g, wear, g.math("ADD", wear, 0.006), f))
    rim = g.math("MULTIPLY", smoothstep(g, wear, g.math("ADD", wear, 0.01), f),
                 g.math("SUBTRACT", 1.0, smoothstep(g, g.math("ADD", wear, 0.02), g.math("ADD", wear, 0.045), f)))
    green = g.tint(_c("59654c"), g.math("ADD", g.math("MULTIPLY", tone, 0.45), 0.78))
    green = g.mix(g.math("MULTIPLY", crack, 0.6), green, _c("1f261c"))
    plaster = g.tint(_c("c4baa6"), g.math("ADD", g.math("MULTIPLY", pt, 0.35), 0.8))
    color = g.mix(peeled, green, plaster)
    color = g.mix(g.math("MULTIPLY", rim, 0.85), color, _c("cfd0bc"))
    rough = g.mixf(peeled, g.math("ADD", g.math("MULTIPLY", tone, 0.15), 0.36), 0.88)
    rough = g.mixf(rim, rough, 0.6)
    h_paint = g.math("ADD", 0.55, g.math("SUBTRACT", g.math("MULTIPLY", ph, 0.06), g.math("MULTIPLY", crack, 0.08)))
    height = g.mixf(peeled, h_paint, g.math("MULTIPLY", plh, 0.2))
    height = g.math("ADD", height, g.math("MULTIPLY", rim, 0.35))
    return color, rough, height


def wash_layer(g, P, vec, wash_wear, loss_wear, bvec):
    """Побелка → штукатурка (толщина ~2 см) → кирпич; редкие длинные трещины штукатурки."""
    wf = gray(g, P["plaster_wash_field"], vec)
    wc = gray(g, P["plaster_wash_crack"], vec)
    wt = gray(g, P["plaster_wash_tone"], vec)
    lf = gray(g, P["plaster_loss_field"], vec)
    pc = gray(g, P["plaster_plaster_crack"], vec)
    pt = gray(g, P["plaster_plaster_tone"], vec)
    plh = gray(g, P["plaster_plaster_height"], vec)
    brick = g.image(P["brick_albedo"], bvec).outputs[0]
    white = g.tint(_c("dfe1d9"), g.math("ADD", g.math("MULTIPLY", wt, 0.16), 0.88))
    white = g.mix(g.math("MULTIPLY", wc, 0.12), white, _c("8a8a80"))
    grey = g.tint(_c("a8a296"), g.math("ADD", g.math("MULTIPLY", pt, 0.3), 0.85))
    flaked = g.math("SUBTRACT", 1.0, smoothstep(g, wash_wear, g.math("ADD", wash_wear, 0.006), wf))
    color = g.mix(flaked, white, grey)
    color = g.mix(g.math("MULTIPLY", pc, 0.65), color, _c("3a3630"))
    keep = smoothstep(g, loss_wear, g.math("ADD", loss_wear, 0.05), lf)
    edge = g.math("MULTIPLY", g.math("MULTIPLY", keep, g.math("SUBTRACT", 1.0, keep)), 4.0)
    color = g.mix(g.math("SUBTRACT", 1.0, keep), color, brick)
    color = g.mix(g.math("MULTIPLY", g.math("GREATER_THAN", edge, 0.3), 0.8), color, g.tint(_c("9a9488"), 0.9))
    rough = g.mixf(g.math("SUBTRACT", 1.0, keep), g.mixf(flaked, 0.9, 0.85), 0.8)
    height = g.math("ADD", g.math("MULTIPLY", keep, g.math("ADD", 0.6, g.math("MULTIPLY", plh, 0.05))),
                    g.math("MULTIPLY", g.math("SUBTRACT", 1.0, keep), 0.08))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pc, 0.05))
    return color, rough, height


def _c(h: str) -> tuple:
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def wall(g, P, facade: bool = False) -> None:
    """Стена общежития: до 2,0 м — облупленная масляная краска, выше — побелка по штукатурке по кирпичу,
    между ними полоса-«филёнка», у пола грязь. Износ — атрибут «Износ» плюс пятна по месту (разные копии модуля
    изнашиваются по-разному)."""
    w = wear_attr(g)
    base_paint = param(g, "Износ краски, база", 0.08)
    base_wash = param(g, "Облетание побелки, база", 0.05)
    base_loss = param(g, "Штукатурка до кирпича, база", 0.0)
    # Разброс по месту: где-то стена почти целая, где-то облезла сильно (пятна ~3 м).
    var = g.math("SUBTRACT", g.math("MULTIPLY", world_noise(g, 0.3), 1.4), 0.55)
    paint_wear = g.math("ADD", g.math("ADD", base_paint, g.math("MULTIPLY", w[0], 0.45)), g.math("MULTIPLY", var, 0.4), True)
    wash_wear = g.math("ADD", g.math("ADD", base_wash, g.math("MULTIPLY", w[0], 0.35)), g.math("MULTIPLY", var, 0.25), True)
    loss_wear = g.math("ADD", g.math("ADD", base_loss, g.math("MULTIPLY", w[1], 0.5)), g.math("MULTIPLY", var, 0.1), True)
    vec = g.uv(0.5)
    bvec = g.uv(0.5)
    pc, pr, ph = paint_layer(g, P, vec, paint_wear)
    wc, wr, wh = wash_layer(g, P, vec, wash_wear, loss_wear, bvec)
    z = g.sep(g.tc.outputs["Object"])[2]
    zz = g.math("ADD", z, g.math("MULTIPLY", g.noise(g.tc.outputs["Object"], 1.5, 2.0), 0.012))
    lower = g.math("LESS_THAN", zz, PAINT_LINE)
    line = g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", zz, PAINT_LINE + 0.006)), 0.008)
    color = g.mix(lower, wc, pc)
    color = g.mix(line, color, _c("2f3a2c"))
    dirt = g.math("MULTIPLY", g.math("ADD", w[2], g.math("SUBTRACT", 1.0, g.math("MULTIPLY", z, 4.0), True)), g.noise(g.tc.outputs["Object"], 5.0, 5.0))
    color = g.mix(g.math("MULTIPLY", dirt, 0.8), color, _c("3b3428"), "MULTIPLY")
    rough = g.mixf(lower, wr, pr)
    height = g.mixf(lower, wh, ph)
    if facade:
        obj = g.sep(g.tc.outputs["Object"])
        vt = g.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="WORLD", convert_to="OBJECT")
        g.link(g.geo.outputs["Normal"], vt.inputs[0])
        reveal = g.math("LESS_THAN", g.math("ABSOLUTE", g.sep(vt.outputs[0])[1]), 0.5)
        color = g.mix(reveal, color, wc)
        rough = g.mixf(reveal, rough, wr)
        height = g.mixf(reveal, height, wh)
        outside = g.math("LESS_THAN", obj[1], -0.2)
        facade_col = g.tint(_c("a49f93"), g.math("ADD", g.math("MULTIPLY", gray(g, P["plaster_plaster_tone"], vec), 0.3), 0.8))
        streak = g.noise(g.mix(1.0, g.tc.outputs["Object"], (8.0, 8.0, 0.6, 1.0), "MULTIPLY"), 3.0, 6.0)
        facade_col = g.mix(g.math("MULTIPLY", g.lum(g.ramp(streak, 0.5, 0.75)), 0.5), facade_col, _c("6f675a"))
        color = g.mix(outside, color, facade_col)
        rough = g.mixf(outside, rough, 0.92)
    g.out_bsdf(color, rough, g.bump(height, 1.0, 0.012))


# ---------------------------------------------------------------- паркет и плитка

def rotated_uv(g, scale: float, angle_deg: float):
    mp = g.node("ShaderNodeMapping")
    g.link(g.tc.outputs["UV"], mp.inputs["Vector"])
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(angle_deg))
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    return mp.outputs[0]


def parquet(g, P) -> None:
    """Паркет «ёлочкой» (планка 70 × 350, повёрнут на 45°): часть планок выбита до мастики, часть с расколом
    по волокну. Доли — ползунки; по полу они меняются пятнами (выбитые места кучкуются)."""
    miss = param(g, "Выбито, доля", 0.08)
    cracked = param(g, "Треснуло, доля", 0.15)
    vec = rotated_uv(g, 1 / 2.1, 45.0)
    col = g.image(P["parquet_color"], vec).outputs[0]
    h = gray(g, P["parquet_height"], vec)
    pid = gray(g, P["parquet_id"], vec)
    crk = gray(g, P["parquet_crack"], vec)
    mas = gray(g, P["parquet_mastic"], vec)
    spot = g.math("ADD", g.math("MULTIPLY", world_noise(g, 0.6), 1.6), -0.3)
    m_local = g.math("MULTIPLY", miss, g.math("MAXIMUM", spot, 0.0))
    missing = g.math("LESS_THAN", pid, m_local)
    is_cracked = g.math("MULTIPLY", g.math("MULTIPLY", g.math("GREATER_THAN", pid, m_local),
                                           g.math("LESS_THAN", pid, g.math("ADD", m_local, cracked))), crk)
    mastic = g.mix(g.math("MULTIPLY", mas, 0.6), _c("15110d"), _c("5a564e"))
    lacquer = g.lum(g.ramp(world_noise(g, 1.2), 0.3, 0.8))
    wood = g.mix(g.math("MULTIPLY", lacquer, 0.35), col, g.mix(1.0, col, _c("b8a68c"), "MULTIPLY"))
    color = g.mix(missing, wood, mastic)
    color = g.mix(is_cracked, color, _c("1a120c"))
    rough = g.mixf(missing, g.math("ADD", g.math("MULTIPLY", lacquer, 0.3), 0.35), 0.75)
    height = g.mixf(missing, g.math("SUBTRACT", h, g.math("MULTIPLY", is_cracked, 0.4)), g.math("MULTIPLY", mas, 0.05))
    g.out_bsdf(color, rough, g.bump(height, 1.0, 0.015))


def tile(g, P, wall_part: bool = False) -> None:
    """Плитка 20 × 20: выбитые (клей со следами шпателя), сколотые по углу, треснувшие. На стене — до 2,0 м,
    выше побелка. Доли — ползунки, по месту меняются пятнами."""
    miss = param(g, "Выбито, доля", 0.06)
    chip = param(g, "Скол угла, доля", 0.12)
    crk_p = param(g, "Треснуло, доля", 0.18)
    vec = g.uv(0.5)
    tid = gray(g, P["tile_id"], vec)
    tone = gray(g, P["tile_tone"], vec)
    th = gray(g, P["tile_height"], vec)
    tc = gray(g, P["tile_crack"], vec)
    ch = gray(g, P["tile_chip"], vec)
    gl = gray(g, P["tile_glue"], vec)
    spot = g.math("ADD", g.math("MULTIPLY", world_noise(g, 0.8), 1.6), -0.3)
    k = g.math("MAXIMUM", spot, 0.0)
    m1 = g.math("MULTIPLY", miss, k)
    m2 = g.math("ADD", m1, g.math("MULTIPLY", chip, k))
    m3 = g.math("ADD", m2, g.math("MULTIPLY", crk_p, k))
    missing = g.math("LESS_THAN", tid, m1)
    chipped = g.math("MULTIPLY", g.math("MULTIPLY", g.math("GREATER_THAN", tid, m1), g.math("LESS_THAN", tid, m2)), ch)
    cracked = g.math("MULTIPLY", g.math("MULTIPLY", g.math("GREATER_THAN", tid, m2), g.math("LESS_THAN", tid, m3)), tc)
    hole = g.math("MAXIMUM", missing, chipped)
    body = g.math("GREATER_THAN", th, 0.5)
    tile_col = g.tint(_c("c9cec6"), g.math("ADD", g.math("MULTIPLY", tone, 0.25), 0.78))
    tile_col = g.mix(g.math("SUBTRACT", 1.0, body), tile_col, _c("4f4c45"))
    grime = g.lum(g.ramp(world_noise(g, 2.0), 0.45, 0.8))
    tile_col = g.mix(g.math("MULTIPLY", grime, 0.35), tile_col, _c("7d7563"), "MULTIPLY")
    glue = g.tint(_c("8f8a7e"), g.math("ADD", g.math("MULTIPLY", gl, 0.35), 0.75))
    color = g.mix(hole, tile_col, glue)
    color = g.mix(cracked, color, _c("2a2822"))
    rough = g.mixf(hole, g.mixf(body, 0.9, 0.12), 0.92)
    height = g.mixf(hole, g.math("SUBTRACT", th, g.math("MULTIPLY", cracked, 0.3)), g.math("MULTIPLY", gl, 0.25))
    if wall_part:
        z = g.sep(g.tc.outputs["Object"])[2]
        upper = g.math("GREATER_THAN", z, PAINT_LINE)
        # Над плиткой — побелка (облетание по тому же полю, без кирпича).
        wvec = g.uv(0.5)
        wc, wr, wh = wash_layer(g, P, wvec, param(g, "Облетание побелки, база", 0.2), 0.0, g.uv(0.5))
        color = g.mix(upper, color, wc)
        rough = g.mixf(upper, rough, wr)
        height = g.mixf(upper, height, wh)
    g.out_bsdf(color, rough, g.bump(height, 1.0, 0.006))


# ---------------------------------------------------------------- атрибут износа

def wear_layout(ob, opening=None, grid: float = 0.1) -> None:
    """Сетка 10 см (для кисти) и атрибут «Износ»: R — у пола и у проёма больше, G — пятна до кирпича
    в верхней части, B — грязь у пола. opening = (x0, x1, z1) проёма в координатах объекта."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    mn = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    mx = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    for axis, lo, hi in ((0, mn.x, mx.x), (2, mn.z, mx.z)):
        n = int((hi - lo) / grid)
        for i in range(1, n):
            co = [0.0, 0.0, 0.0]
            co[axis] = lo + i * (hi - lo) / n
            no = [0.0, 0.0, 0.0]
            no[axis] = 1.0
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    bm.to_mesh(me)
    bm.free()
    attr = me.color_attributes.get("Износ") or me.color_attributes.new("Износ", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(me.vertices):
        x, z = v.co.x, v.co.z
        r = max(0.0, 1.0 - z / 0.7) * 0.55
        if opening is not None:
            x0, x1, z1 = opening
            d = min(abs(x - x0), abs(x - x1)) if (x < x0 or x > x1) else 0.0
            if z < z1 + 0.3:
                r += max(0.0, 1.0 - d / 0.4) * 0.45
        n1 = 0.5 + 0.5 * math.sin(x * 2.3 + z * 1.7) * math.sin(x * 0.9 - z * 2.9)
        g = max(0.0, n1 - 0.55) * 1.6 if z > 2.0 else 0.0
        b = max(0.0, 1.0 - z / 0.35)
        attr.data[i].color = (min(1.0, r + 0.15 * n1), min(1.0, g), b, 1.0)
    me.update()
