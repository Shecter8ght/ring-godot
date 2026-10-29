"""Слоистые материалы общежития (Blender), v03: облупленная краска (paint_v3), побелка → штукатурка → кирпич
(plaster_v3), паркет «ёлочкой» (floor_v3), плитка 200 × 200 (tiles_v3). Карты — gen_*_v3.py в папке textures комплекта.

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
    """Карты v02, которые ещё нужны: тон штукатурки для наружной грани фасада."""
    return {"plaster_plaster_tone": f"{KIT}/plaster/plaster_tone.png"}


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


# ---------------------------------------------------------------- стена

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
    import paint_v3
    import plaster_v3
    import tiles_v3
    # Координаты от мира: рисунок краски и побелки идёт через стыки модулей без шва.
    vec, frame = paint_v3.wall_coords(g, 0.5)
    pc, pr, pn = paint_v3.paint_v3(g, vec, paint_wear, frame)
    wc, wr, n_wash = plaster_v3.wash_v3(g, vec, wash_wear, loss_wear, frame,
                                        coords=lambda pos: tiles_v3.surface_coords(g, 0.5, pos)[0])
    z = g.sep(g.tc.outputs["Object"])[2]
    zz = g.math("ADD", z, g.math("MULTIPLY", g.noise(g.tc.outputs["Object"], 1.5, 2.0), 0.012))
    lower = g.math("LESS_THAN", zz, PAINT_LINE)
    line = g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", zz, PAINT_LINE + 0.006)), 0.008)
    color = g.mix(lower, wc, pc)
    color = g.mix(line, color, _c("2f3a2c"))
    dirt = g.math("MULTIPLY", g.math("ADD", w[2], g.math("SUBTRACT", 1.0, g.math("MULTIPLY", z, 4.0), True)), g.noise(g.tc.outputs["Object"], 5.0, 5.0))
    color = g.mix(g.math("MULTIPLY", dirt, 0.8), color, _c("3b3428"), "MULTIPLY")
    rough = g.mixf(lower, wr, pr)
    normal = vmix(g, lower, n_wash, pn)
    if facade:
        obj = g.sep(g.tc.outputs["Object"])
        vt = g.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="WORLD", convert_to="OBJECT")
        g.link(g.geo.outputs["Normal"], vt.inputs[0])
        reveal = g.math("LESS_THAN", g.math("ABSOLUTE", g.sep(vt.outputs[0])[1]), 0.5)
        color = g.mix(reveal, color, wc)
        rough = g.mixf(reveal, rough, wr)
        normal = vmix(g, reveal, normal, n_wash)
        outside = g.math("LESS_THAN", obj[1], -0.2)
        facade_col = g.tint(_c("a49f93"), g.math("ADD", g.math("MULTIPLY", gray(g, P["plaster_plaster_tone"], vec), 0.3), 0.8))
        streak = g.noise(g.mix(1.0, g.tc.outputs["Object"], (8.0, 8.0, 0.6, 1.0), "MULTIPLY"), 3.0, 6.0)
        facade_col = g.mix(g.math("MULTIPLY", g.lum(g.ramp(streak, 0.5, 0.75)), 0.5), facade_col, _c("6f675a"))
        color = g.mix(outside, color, facade_col)
        rough = g.mixf(outside, rough, 0.92)
        normal = vmix(g, outside, normal, n_wash)
    g.out_bsdf(color, rough, normal)


def vmix(g, fac, a, b):
    """Смешение векторов (нормалей) узлом Mix."""
    nd = g.node("ShaderNodeMix", data_type="VECTOR")
    ins = {s.identifier: s for s in nd.inputs}
    g.link(fac, ins["Factor_Float"])
    g.link(a, ins["A_Vector"])
    g.link(b, ins["B_Vector"])
    return next(s for s in nd.outputs if s.identifier == "Result_Vector")


# ---------------------------------------------------------------- паркет и плитка

def parquet(g, P) -> None:
    """Паркет «ёлочкой» v03 (floor_v3.py): дуб под старым лаком, выбитые и обломанные планки — ямы в толщину планки."""
    import floor_v3
    color, rough, normal = floor_v3.floor_v3(g)
    g.out_bsdf(color, rough, normal)


def tile(g, P, wall_part: bool = False) -> None:
    """Плитка 200 × 200 v03 (tiles_v3.py). На стене — до 2,0 м, выше побелка v03; на полу — тёмная метлахская."""
    import plaster_v3
    import tiles_v3
    if not wall_part:
        color, rough, normal = tiles_v3.tiles_v3(g, "7d5f4c", 1.0, "6a4f3f")
        g.out_bsdf(color, rough, normal)
        return
    color, rough, normal = tiles_v3.tiles_v3(g)
    vec, frame = tiles_v3.surface_coords(g, 0.5)
    w = wear_attr(g)
    wash = g.math("ADD", param(g, "Облетание побелки, база", 0.2), g.math("MULTIPLY", w[0], 0.35), True)
    wc, wr, wn = plaster_v3.wash_v3(g, vec, wash, 0.0, frame, mold=1.6,
                                    coords=lambda pos: tiles_v3.surface_coords(g, 0.5, pos)[0])
    z = g.sep(g.tc.outputs["Object"])[2]
    upper = g.math("GREATER_THAN", z, PAINT_LINE)
    g.out_bsdf(g.mix(upper, color, wc), g.mixf(upper, rough, wr), vmix(g, upper, normal, wn))


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
