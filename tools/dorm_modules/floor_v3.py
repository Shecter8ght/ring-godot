"""Паркет «ёлочкой» v03 — узлы материала Blender (карты gen_floor_v3.py, тайл 2,1 м, раскладка под 45°).

Дерево по планкам — скан дуба; лак старый: янтарный тон, царапины всех направлений, вмятины, разводы воды;
по проходу (пятна по миру, ползунок) лак вытерт — дерево светлее, серее и грязнее, блеска нет. Выбитые и обломанные (конец поперёк, полоса вдоль, угол) планки —
яма в толщину планки (parallax.march: дальняя стенка и сдвинутое дно), на дне мастика: битум с гребнями шпателя, прилипшее дерево, пыль, тень у краёв ямы; треснувшие — раскол вдоль волокон.
Доли — ползунки, выбитые места собираются пятнами по миру. Координаты — от мира: рисунок без швов на стыках.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paint_v3 import F, chans, img, out_normal, rgb_param  # noqa: E402
from texture_layers import _c, param, vmix, world_noise  # noqa: E402
import parallax  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/floor_v3"
TILE_M = 2.1
PLANK_DEPTH_M = 0.015          # толщина штучной планки над мастикой: яма выбитой планки


def floor_coords(g, pos=None):
    """Пол: мир x, y повёрнуты на 45° (ёлочка вдоль осей тайла), тайл 2,1 м. Рамка T, B, N — в мире."""
    px, py, _ = g.sep(pos if pos is not None else g.geo.outputs["Position"])
    k = 0.70710678 / TILE_M
    u = g.math("MULTIPLY", g.math("ADD", px, py), k)
    v = g.math("MULTIPLY", g.math("SUBTRACT", py, px), k)
    vec = g.node("ShaderNodeCombineXYZ")
    g.link(u, vec.inputs[0])
    g.link(v, vec.inputs[1])
    t = g.node("ShaderNodeCombineXYZ")
    t.inputs[0].default_value, t.inputs[1].default_value = 0.70710678, 0.70710678
    b = g.node("ShaderNodeCombineXYZ")
    b.inputs[0].default_value, b.inputs[1].default_value = -0.70710678, 0.70710678
    n = g.node("ShaderNodeCombineXYZ")
    n.inputs[2].default_value = 1.0
    return vec.outputs[0], (t.outputs[0], b.outputs[0], n.outputs[0])


def floor_v3(g):
    f = F(g)
    miss = param(g, "Выбито, доля", 0.05)
    brk = param(g, "Обломано, доля", 0.14)
    cracked = param(g, "Треснуло, доля", 0.12)
    gouged = param(g, "Сорван лак, доля", 0.25)
    worn_k = param(g, "Лак вытерт, сила", 1.0)
    dirt_k = param(g, "Грязь, сила", 1.0)
    lacquer = rgb_param(g, "Тон старого лака", "8c6c4c")
    vec, frame = floor_coords(g)

    wood = img(g, "floor_wood.png", vec, True, folder=KIT).outputs["Color"]
    fn = chans(g, img(g, "floor_normal.png", vec, folder=KIT))
    RID, GD, SPLIT, RID2 = chans(g, img(g, "floor_masks.png", vec, folder=KIT))
    SCR, DENT, WATER, GRIME = chans(g, img(g, "floor_wear.png", vec, folder=KIT))
    PIECE, FRINGE, GOUGE, CLUSTER = chans(g, img(g, "floor_break.png", vec, folder=KIT))
    bn = chans(g, img(g, "floor_break_normal.png", vec, folder=KIT))

    # Выбитые места собираются пятнами; лак вытерт по проходу — пятна по миру.
    def m_at(cluster):
        """Порог «выбита» планки по её «плохому месту» (одно число на планку из карты)."""
        return f.mul(miss, f("MAXIMUM", f.sub(f.mul(cluster, 1.6), 0.3), 0.0))

    def classes(rid, m):
        """Выбита целиком / обломана (часть по карте облома) — по случайному числу планки."""
        k = f("DIVIDE", m, f("MAXIMUM", miss, 0.0001))                 # 0…1 — насколько здесь плохое место
        m2 = f.add(m, f.mul(brk, k))
        whole = f("LESS_THAN", rid, m)
        part = f.mul(f("GREATER_THAN", rid, m), f("LESS_THAN", rid, m2))
        return whole, part, m2, k

    m_local = m_at(CLUSTER)
    whole, part, m2, spot_k = classes(RID, m_local)
    missing = f("MAXIMUM", whole, f.mul(part, f.ss(0.45, 0.55, PIECE)))
    m3 = f.add(m2, f.mul(cracked, spot_k))
    broken = f.mul(f.mul(f("GREATER_THAN", RID, m2), f("LESS_THAN", RID, m3)), SPLIT)
    # Свежий излом у оставшейся части; выбоины в лаке — у своей доли планок (по второму случайному числу).
    fresh = f.mul(part, FRINGE)
    gouge = f.mul(f("LESS_THAN", RID2, f.mul(gouged, f.add(0.4, spot_k))), GOUGE)
    raw = f("MAXIMUM", fresh, gouge)
    worn = f("MINIMUM", f.mul(f.ss(0.42, 0.75, world_noise(g, 0.35)), worn_k), 1.0)
    gd = f.mul(GD, 4.0)

    # ---------------------------------------------------------------- дерево под старым лаком
    # Старый лак: дерево приглушено, потемнело, тёплое, но не рыжее. Без лака — серое, сухое, светлее.
    calm = g.mix(0.55, wood, g.tint(_c("ffffff"), g.lum(wood)))
    aged = g.mix(1.0, calm, g.tint(lacquer, 0.95), "MULTIPLY")
    bare = g.tint(g.mix(0.7, calm, g.tint(_c("9a8f80"), g.lum(wood))), 0.72)
    c = g.mix(worn, aged, bare)
    c = g.mix(f.mul(f.mul(SCR, 0.12), f.inv(worn)), c, _c("a89478"))                # царапины видны в основном по блеску
    c = g.mix(f.mul(DENT, 0.4), c, _c("3a2c20"))
    c = g.mix(f("MINIMUM", f.mul(WATER, 0.45), 1.0), c, _c("5a5048"), "MULTIPLY")
    c = g.mix(f("MINIMUM", f.mul(f.mul(GRIME, dirt_k), f.add(0.45, f.mul(worn, 0.4))), 1.0), c, _c("6a6056"), "MULTIPLY")
    gap = f.inv(f.ss(0.15, 0.9, gd))
    c = g.mix(f.mul(gap, 0.9), c, _c("17110c"))
    c = g.mix(f.mul(broken, 0.92), c, _c("120d09"))
    # Свежее дерево излома и выбоины — светлое, сухое, без лака; в выбоине уже набилась грязь.
    raw_c = g.tint(g.mix(0.45, calm, _c("a08a6c")), 0.85)
    raw_c = g.mix(f.mul(gouge, 0.6), raw_c, _c("5e4f40"), "MULTIPLY")
    c = g.mix(f.mul(raw, 0.9), c, raw_c)
    r = f.lerp(worn, f.add(0.3, f.mul(RID2, 0.1)), 0.72)
    r = f.add(r, f.add(f.mul(f.mul(SCR, f.inv(worn)), 0.35), f.mul(GRIME, 0.15)))
    r = f.add(r, f.mul(WATER, 0.12))
    r = f.lerp(gap, r, 0.9)
    r = f.lerp(raw, r, 0.85)

    # ---------------------------------------------------------------- яма выбитой планки: стенки и дно
    # Луч от глаза идёт на толщину планки вглубь: упёрся в соседнюю планку — видна её боковая грань, иначе —
    # мастика на дне, сдвинутая вдаль по взгляду.
    def hole_at(pos):
        uv, _ = floor_coords(g, pos)
        rid, gdk, _, _ = chans(g, img(g, "floor_masks.png", uv, folder=KIT))
        pc, _, _, cl = chans(g, img(g, "floor_break.png", uv, folder=KIT))
        w, pt, _, _ = classes(rid, m_at(cl))
        return f("MAXIMUM", w, f.mul(pt, f.ss(0.45, 0.55, pc))), {"uv": uv, "gd": gdk}

    wall, t_wall, _, bottom, n_wall = parallax.march(g, PLANK_DEPTH_M, 8, hole_at)
    MT, RIDGE, RES, DUST = chans(g, img(g, "floor_mastic.png", bottom["uv"], folder=KIT))
    gd_floor = f.mul(bottom["gd"], 4.0)
    mastic = g.tint(_c("151210"), f.add(0.75, f.mul(MT, 0.5)))
    mastic = g.mix(f.mul(RIDGE, 0.2), mastic, _c("26211c"))
    mastic = g.mix(f.mul(RES, 0.7), mastic, g.tint(calm, 0.45))
    mastic = g.mix(f.mul(DUST, 0.5), mastic, _c("4e4943"))
    hole_ao = f.inv(f.ss(0.0, 9.0, gd_floor))
    mastic = g.tint(mastic, f.sub(1.0, f.mul(hole_ao, 0.65)))
    # Боковая грань планки: торец / пласть дуба без лака, книзу темнее (ниже — меньше света).
    # Торец старой планки пропитан мастикой и пылью — темнее лакированного верха; сверху — кромка под лаком.
    side = g.tint(g.mix(0.35, aged, _c("3a2a1c")), f.sub(0.7, f.mul(t_wall, 0.4)))
    side = g.mix(f.mul(f.inv(f.ss(0.0, 0.1, t_wall)), 0.5), side, aged)
    hole_c = g.mix(wall, mastic, side)
    color = g.mix(missing, c, hole_c)
    rough = f.lerp(missing, r, f.lerp(wall, f.lerp(DUST, 0.78, 0.95), 0.85))

    # ---------------------------------------------------------------- нормаль
    nx = f.add(f.unpack(fn[0]), f.mul(f.unpack(bn[0]), raw))
    ny = f.add(f.unpack(fn[1]), f.mul(f.unpack(bn[1]), raw))
    nz = f.unpack(fn[2])
    n_wood = out_normal(g, nx, ny, nz, frame)
    n_mastic = g.bump(f.add(f.mul(RIDGE, 0.4), f.mul(RES, 0.6)), 0.6, 0.0004)
    # Стенка не идеально вертикальная (кромки скруглены, планки отходят) — ловит немного верхнего света.
    n_side = parallax.vmath(g, "NORMALIZE", parallax.vmath(g, "ADD", n_wall, parallax.vmath(g, "SCALE", g.geo.outputs["Normal"], scale=0.45)))
    n_hole = vmix(g, wall, n_mastic, n_side)
    dbg = os.environ.get("FLOOR_V3_DEBUG")
    if dbg:
        # Проверка без света: R — стенка ямы, G — яма, B — свежее дерево; или цвет стенки (side).
        if dbg == "side":
            out_c = side
        else:
            cc = g.node("ShaderNodeCombineColor")
            for i, sck in enumerate((f.mul(wall, missing), missing, raw)):
                g.link(sck, cc.inputs[i])
            out_c = cc.outputs[0]
        em = g.node("ShaderNodeEmission")
        g.link(out_c, em.inputs[0])
        g.link(em.outputs[0], g.out.inputs[0])
    normal = vmix(g, missing, n_wood, n_hole)
    return color, rough, normal
