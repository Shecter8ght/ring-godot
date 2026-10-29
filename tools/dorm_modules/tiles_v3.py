"""Плитка душевых 200 × 200 v03 — узлы материала Blender (карты gen_tiles_v3.py, тайл 2 × 2 м = 10 × 10 плиток).

Глазурь с бликами, ломающимися по плиткам (каждая чуть косо), цек, потёки ржавчины, известковый налёт; шов утоплен,
грязный, у пола темнее. Доли — ползунки, места повреждений собираются пятнами по миру:
- выбитая плитка — яма в толщину плитки (parallax.march): видна кромка соседней плитки (глазурь сверху, черепок
  ниже), на дне клей со следами зубчатого шпателя;
- скол — черепок без глазури; трещина — тёмная линия через плитку.
Координаты от мира: на полу — x, y, на стене — вдоль стены и по высоте (как у краски), рисунок без швов на стыках.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paint_v3 import F, chans, img, out_normal, rgb_param  # noqa: E402
from texture_layers import _c, param, vmix  # noqa: E402
import parallax  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/tiles_v3"
TILE_DEPTH_M = 0.008           # толщина плитки над слоем клея


def surface_coords(g, scale: float, pos=None):
    """Пол (нормаль вверх / вниз) — мир x, y; стена — вдоль стены (x или y мира) и z. Рамка T, B, N — в мире."""
    p = pos if pos is not None else g.geo.outputs["Position"]
    px, py, pz = g.sep(p)
    nx, ny, nz = g.sep(g.geo.outputs["Normal"])
    floor = g.math("GREATER_THAN", g.math("ABSOLUTE", nz), 0.5)
    m = g.math("GREATER_THAN", g.math("ABSOLUTE", nx), g.math("ABSOLUTE", ny))
    u_wall = g.mixf(m, px, py)
    u = g.mixf(floor, u_wall, px)
    v = g.mixf(floor, pz, py)
    vec = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", u, scale), vec.inputs[0])
    g.link(g.math("MULTIPLY", v, scale), vec.inputs[1])
    t = g.node("ShaderNodeCombineXYZ")
    g.link(g.mixf(floor, g.math("SUBTRACT", 1.0, m), 1.0), t.inputs[0])
    g.link(g.mixf(floor, m, 0.0), t.inputs[1])
    b = g.node("ShaderNodeCombineXYZ")
    g.link(floor, b.inputs[1])
    g.link(g.math("SUBTRACT", 1.0, floor), b.inputs[2])
    return vec.outputs[0], (t.outputs[0], b.outputs[0], g.geo.outputs["Normal"])


def tiles_v3(g, glaze_hex: str = "cfcdc2", floor_dirt: float = 0.0, body_hex: str = "bba78c"):
    """Возвращает (цвет, шероховатость, нормаль). floor_dirt — на полу грязнее и меньше блеска; body_hex — черепок
    (у метлахской плитки окрашен насквозь — скол того же цвета, что и плитка)."""
    f = F(g)
    miss = param(g, "Выбито, доля", 0.06)
    chip_p = param(g, "Скол, доля", 0.12)
    crk_p = param(g, "Треснуло, доля", 0.16)
    k_rust = param(g, "Ржавые потёки, сила", 1.0)
    k_lime = param(g, "Известковый налёт, сила", 1.0)
    glaze = rgb_param(g, "Цвет глазури", glaze_hex)
    vec, frame = surface_coords(g, 0.5)

    RID, DE, CRK, CHIP = chans(g, img(g, "tile_masks.png", vec, folder=KIT))
    TONE, CRAZE, RUST, LIME = chans(g, img(g, "tile_tone.png", vec, folder=KIT))
    tn = chans(g, img(g, "tile_normal.png", vec, folder=KIT))
    _, _, BISC, GDIRT = chans(g, img(g, "tile_glue.png", vec, folder=KIT))

    def m_at(pos):
        """Порог «выбита» по шуму в центре плитки (сетка 0,2 м мира совпадает с раскладкой): одно решение на плитку."""
        q = parallax.vmath(g, "FLOOR", parallax.vmath(g, "ADD", parallax.vmath(g, "SCALE", pos, scale=5.0), (0.0002, 0.0002, 0.0002)))
        c = parallax.vmath(g, "SCALE", parallax.vmath(g, "ADD", q, (0.5, 0.5, 0.5)), scale=0.2)
        nz = g.noise(c, 0.8, 3.0, 0.5)
        return f.mul(miss, f("MAXIMUM", f.sub(f.mul(nz, 1.6), 0.3), 0.0))

    m1 = m_at(g.geo.outputs["Position"])
    spot =f("DIVIDE", m1, f("MAXIMUM", miss, 0.0001))           # 0…1 — насколько здесь «плохое место»
    m2 = f.add(m1, f.mul(chip_p, spot))
    m3 = f.add(m2, f.mul(crk_p, spot))
    missing = f("LESS_THAN", RID, m1)
    chipped = f.mul(f.mul(f("GREATER_THAN", RID, m1), f("LESS_THAN", RID, m2)), CHIP)
    cracked = f.mul(f.mul(f("GREATER_THAN", RID, m2), f("LESS_THAN", RID, m3)), CRK)
    de = f.mul(DE, 8.0)
    grout = f.inv(f.ss(0.0, 0.25, de))

    # ---------------------------------------------------------------- глазурь, шов
    # Низ стены грязнее: брызги, мыльный налёт, в швах плесень (по высоте над полом, до ~0,6 м).
    z = g.sep(g.geo.outputs["Position"])[2]
    low = f.mul(f.inv(f.ss(0.05, 0.6, z)), f.inv(floor_dirt))
    c = g.tint(glaze, f.add(0.78, f.mul(TONE, 0.44)))
    c = g.mix(f.mul(CRAZE, 0.35), c, _c("8c8a82"))
    rust_w = f.mul(f.mul(RUST, k_rust), f.inv(floor_dirt))
    c = g.mix(f("MINIMUM", rust_w, 1.0), c, _c("7a4620"), "MULTIPLY")
    # Общая плёнка: мыльный налёт и пыль желтят глазурь пятнами.
    c = g.mix(f.mul(f.add(0.15, f.mul(GDIRT, 0.3)), f.inv(floor_dirt)), c, _c("b8ad94"), "MULTIPLY")
    c = g.mix(f("MINIMUM", f.mul(LIME, f.mul(k_lime, f.add(0.12, f.mul(low, 0.3)))), 1.0), c, _c("dcd6c4"))
    c = g.mix(f.add(f.mul(low, 0.35), f.mul(floor_dirt, f.add(0.25, f.mul(GDIRT, 0.35)))), c, _c("8a8070"), "MULTIPLY")
    grout_c = g.tint(_c("7e7a72"), f.sub(1.0, f.mul(GDIRT, 0.6)))
    grout_c = g.mix(f("MINIMUM", f.add(f.mul(low, 0.9), f.mul(floor_dirt, 0.5)), 1.0), grout_c, _c("2c2a24"))
    c = g.mix(grout, c, grout_c)
    c = g.mix(f.mul(cracked, 0.9), c, _c("2a2722"))
    bisc = g.tint(_c(body_hex), f.add(0.8, f.mul(BISC, 0.35)))
    c = g.mix(chipped, c, bisc)
    r = f.add(0.07, f.add(f.mul(f.mul(LIME, k_lime), 0.35), f.mul(CRAZE, 0.08)))
    r = f.add(r, f.add(f.mul(floor_dirt, 0.3), f.mul(low, 0.15)))
    r = f.lerp(grout, r, 0.92)
    r = f.lerp(chipped, r, 0.85)

    # ---------------------------------------------------------------- яма выбитой плитки
    def hole_at(pos):
        uv, _ = surface_coords(g, 0.5, pos)
        rid, dek, _, _ = chans(g, img(g, "tile_masks.png", uv, folder=KIT))
        return f("LESS_THAN", rid, m_at(pos)), {"uv": uv, "de": dek}

    wall, t_wall, _, bottom, n_wall = parallax.march(g, TILE_DEPTH_M, 8, hole_at)
    RIDGE, GLUE_T, _, _ = chans(g, img(g, "tile_glue.png", bottom["uv"], folder=KIT))
    glue = g.tint(_c("8f8a7e"), f.add(0.7, f.mul(GLUE_T, 0.4)))
    glue = g.mix(f.mul(RIDGE, 0.3), glue, _c("a8a396"))
    ao = f.inv(f.ss(0.0, 10.0, f.add(f.mul(bottom["de"], 8.0), 1.5)))
    glue = g.tint(glue, f.sub(1.0, f.mul(ao, 0.55)))
    # Кромка соседней плитки: сверху глазурь ~0,5 мм, ниже черепок; книзу темнее.
    edge = g.mix(f.ss(0.05, 0.12, t_wall), glaze, g.tint(_c(body_hex), 0.95))
    edge = g.tint(edge, f.sub(1.1, f.mul(t_wall, 0.5)))
    hole_c = g.mix(wall, glue, edge)
    color = g.mix(missing, c, hole_c)
    rough = f.lerp(missing, r, f.lerp(wall, 0.9, 0.8))

    # ---------------------------------------------------------------- нормаль
    n_tile = out_normal(g, f.unpack(tn[0]), f.unpack(tn[1]), f.unpack(tn[2]), frame)
    n_glue = g.bump(f.add(f.mul(RIDGE, 0.8), f.mul(GLUE_T, 0.2)), 0.7, 0.0008)
    n_side = parallax.vmath(g, "NORMALIZE", parallax.vmath(g, "ADD", n_wall, parallax.vmath(g, "SCALE", g.geo.outputs["Normal"], scale=0.35)))
    normal = vmix(g, missing, n_tile, vmix(g, wall, n_glue, n_side))
    return color, rough, normal
