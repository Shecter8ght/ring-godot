"""Побелка → старый слой с синькой → штукатурка → кирпич, v03 — узлы материала Blender (карты gen_plaster_v3.py,
тайл 2 × 2 м; штукатурка — фотоскан из paint_v3, кирпич — red_bricks_04 в своём масштабе 2,5 м).

Два живых износа: облетание побелки (wash) и отвал штукатурки до кирпича (loss). Как у краски v03, по полю и его
крутизне считается расстояние до кромки в мм:
- побелка: чешуйки у кромки приподняты, тонкая светлая грань, в ступеньке грязь; где побелка облетела — местами
  старый слой с синькой, ниже штукатурка; толстая побелка в старых местах растрескалась сеткой;
- штукатурка до кирпича: у края видна осыпающаяся толщина слоя, на кирпиче у края тень, остатки раствора;
- поверх всего, кроме кирпича: длинные трещины штукатурки, разводы протечек с каймой, плесень (ползунками).
under="concrete" — на потолке под штукатуркой бетон плиты вместо кирпича.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paint_v3 import KIT as PAINT_KIT, F, chans, img, out_normal, rgb_param  # noqa: E402
from texture_layers import _c, param, vmix  # noqa: E402
import parallax  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/plaster_v3"
PLASTER_DEPTH_M = 0.02         # штукатурка с побелкой поверх кирпича / бетона


def scaled(g, vec, k: float):
    mp = g.node("ShaderNodeMapping")
    g.link(vec, mp.inputs["Vector"])
    mp.inputs["Scale"].default_value = (k, k, k)
    return mp.outputs[0]


def wash_v3(g, vec, wash_wear, loss_wear, frame=None, under: str = "brick", stains=None, mold=None, coords=None):
    """Возвращает (цвет, шероховатость, нормаль). stains / mold — множители разводов и плесени (сокеты или числа).
    coords(позиция) → координаты карт той же раскладки: с ними отвал до кирпича — яма в толщину штукатурки
    (parallax.march: торец слоя на дальней стороне, кирпич сдвинут вдаль по взгляду)."""
    f = F(g)
    col_wash = rgb_param(g, "Цвет побелки", "d3d0c5")
    col_old = rgb_param(g, "Цвет старой побелки (синька)", "c6cccb")
    share_old = param(g, "Старая побелка, доля", 0.7)
    k_stain = param(g, "Разводы протечек, сила", 1.0)
    k_mold = param(g, "Плесень, сила", 1.0)
    if stains is not None:
        k_stain = f.mul(k_stain, stains)
    if mold is not None:
        k_mold = f.mul(k_mold, mold)

    EW, LGW, DUW, DVW = chans(g, img(g, "wash_peel.png", vec, folder=KIT))
    EL, LGL, DUL, DVL = chans(g, img(g, "loss_peel.png", vec, folder=KIT))
    QW, CUPW, RFW, QL = chans(g, img(g, "wash_masks.png", vec, folder=KIT))
    TONE, STAIN, MOLD, THIN = chans(g, img(g, "wash_tone.png", vec, folder=KIT))
    RES, CRUMB, ETL, ETW = chans(g, img(g, "loss_masks.png", vec, folder=KIT))
    wn = chans(g, img(g, "wash_normal.png", vec, folder=KIT))
    cn = chans(g, img(g, "wash_cup_normal.png", vec, folder=KIT))
    pl_alb = img(g, "plaster_albedo.jpg", vec, True, folder=PAINT_KIT).outputs["Color"]
    pl_n = chans(g, img(g, "plaster_normal.jpg", vec, folder=PAINT_KIT))
    pl_r = img(g, "plaster_rough.jpg", vec, folder=PAINT_KIT).outputs["Color"]

    # ---------------------------------------------------------------- расстояния до кромок, мм
    Gw = f("MAXIMUM", f("POWER", 10.0, f.sub(f.mul(LGW, 5.0), 5.0)), 0.0004)
    Gl = f("MAXIMUM", f("POWER", 10.0, f.sub(f.mul(LGL, 5.0), 5.0)), 0.0004)
    s_w = f("MINIMUM", f("MAXIMUM", f("DIVIDE", f.sub(EW, wash_wear), Gw), -80.0), 80.0)
    s_l = f("MINIMUM", f("MAXIMUM", f("DIVIDE", f.sub(EL, loss_wear), Gl), -80.0), 80.0)
    duw, dvw = f.unpack(DUW), f.unpack(DVW)
    dul, dvl = f.unpack(DUL), f.unpack(DVL)
    flaked = f.inv(f.ss(-0.15, 0.15, s_w))
    hole = f.inv(f.ss(-0.2, 0.2, s_l))
    in_w = f("MAXIMUM", f.mul(s_w, -1.0), 0.0)
    in_l = f("MAXIMUM", f.mul(s_l, -1.0), 0.0)

    # ---------------------------------------------------------------- побелка
    dmg = f.inv(f.ss(0.0, 9.0, s_w))
    lift = f.mul(f("POWER", dmg, 1.3), f.add(0.35, f.mul(RFW, 0.65)))
    crack_w = f.inv(f.ss(0.85, 1.6, f.mul(QW, 4.0)))
    crack_l = f.inv(f.ss(0.85, 1.7, f.mul(QL, 4.0)))
    plaster = g.mix(1.0, pl_alb, g.tint(_c("c2bcb0"), 1.0), "MULTIPLY")
    plaster = g.tint(plaster, 1.08)
    white = g.tint(col_wash, f.add(0.72, f.mul(TONE, 0.56)))
    white = g.mix(f.mul(THIN, 0.18), white, g.tint(plaster, 1.1))
    white = g.mix(f.mul(crack_w, 0.55), white, _c("858075"))
    rim_w = f.mul(f.inv(f.ss(0.05, 0.4, s_w)), f.inv(flaked))
    white = g.mix(f.mul(rim_w, 0.25), white, _c("f2f0e8"))
    # Где верхняя побелка облетела: старый слой с синькой (держится крепче), под ним штукатурка; грязь в ступеньке.
    t_old = f.mul(share_old, f.add(0.06, f.mul(THIN, 0.1)))
    s_old = f("DIVIDE", f.add(f.sub(EW, wash_wear), t_old), Gw)
    old = f.mul(flaked, f.ss(-0.2, 0.2, s_old))
    under_w = g.mix(old, plaster, g.tint(col_old, f.add(0.85, f.mul(TONE, 0.3))))
    foot = f.mul(flaked, f.inv(f.ss(0.0, 0.7, in_w)))
    under_w = g.tint(under_w, f.sub(1.0, f.mul(foot, 0.3)))
    c = g.mix(flaked, white, under_w)
    r = f.lerp(flaked, f.add(0.9, f.mul(THIN, 0.04)), f.lerp(old, g.lum(pl_r), 0.88))
    # Длинные трещины штукатурки — через побелку и штукатурку.
    c = g.mix(f.mul(crack_l, 0.85), c, _c("3f3a33"))
    # Протечки и плесень (не на кирпиче).
    c = g.mix(f("MINIMUM", f.mul(STAIN, f.mul(k_stain, 0.6)), 1.0), c, _c("b09a74"), "MULTIPLY")
    m = f("MINIMUM", f.mul(MOLD, k_mold), 1.0)
    c = g.mix(f.mul(m, 0.85), c, _c("2f332a"))
    r = f.lerp(m, r, 0.75)

    # ---------------------------------------------------------------- штукатурка до кирпича / бетона
    rimw = f.add(3.0, f.mul(CRUMB, 7.0))
    rim_l = f.mul(f.inv(hole), f.inv(f.ss(0.0, rimw, s_l)))
    c = g.mix(rim_l, c, g.mix(1.0, pl_alb, g.tint(_c("8c867b"), 1.0), "MULTIPLY"))
    r = f.lerp(rim_l, r, 0.95)
    shade = f.mul(hole, f.inv(f.ss(0.0, 22.0, in_l)))
    wall = None
    bottom_vec = vec
    if coords is not None:
        def hole_at(pos):
            uv = coords(pos)
            el, _, _, _ = chans(g, img(g, "loss_peel.png", uv, folder=KIT))
            return f("LESS_THAN", el, loss_wear), {"uv": uv}

        wall, t_wall, _, bottom, n_wall = parallax.march(g, PLASTER_DEPTH_M, 8, hole_at)
        bottom_vec = bottom["uv"]
    if under == "brick":
        bvec = scaled(g, bottom_vec, 0.72)             # кирпич 250 мм: тайл скана против тайла 2 м
        b_alb = img(g, "brick_albedo.jpg", bvec, True, folder=KIT).outputs["Color"]
        b_n = chans(g, img(g, "brick_normal.jpg", bvec, folder=KIT))
        b_r = img(g, "brick_rough.jpg", bvec, folder=KIT).outputs["Color"]
        base = g.mix(0.35, b_alb, g.lum(b_alb))            # старый пыльный кирпич — тусклее
        base = g.tint(base, 0.8)
        near = f.inv(f.ss(0.0, 25.0, in_l))
        res = f.ss(0.55, 0.62, f.add(RES, f.mul(near, 0.35)))
        base = g.mix(f.mul(res, 0.85), base, g.mix(1.0, pl_alb, g.tint(_c("a8a296"), 1.0), "MULTIPLY"))
        rb = f.lerp(res, g.lum(b_r), 0.92)
        bnx, bny, bnz = f.unpack(b_n[0]), f.unpack(b_n[1]), f.unpack(b_n[2])
    else:
        base = g.mix(1.0, pl_alb, g.tint(_c("8f8d88"), 1.0), "MULTIPLY")
        rb = 0.9
        bnx, bny, bnz = f.mul(f.unpack(pl_n[0]), 0.3), f.mul(f.unpack(pl_n[1]), 0.3), f.unpack(pl_n[2])
    base = g.tint(base, f.sub(1.0, f.mul(shade, 0.7)))
    if wall is not None:
        # Торец слоя: сверху тонкая побелка, ниже серая штукатурка с крупным зерном, к кирпичу темнее.
        side = g.mix(1.0, pl_alb, g.tint(_c("9c968a"), 1.0), "MULTIPLY")
        side = g.mix(f.inv(f.ss(0.02, 0.06, t_wall)), side, col_wash)
        side = g.tint(side, f.sub(1.0, f.mul(t_wall, 0.45)))
        base = g.mix(wall, base, side)
        rb = f.lerp(wall, rb, 0.95)
    color = g.mix(hole, c, base)
    rough = f.lerp(hole, r, rb)

    # ---------------------------------------------------------------- нормаль
    wx = f.add(f.unpack(wn[0]), f.mul(f.mul(f.unpack(cn[0]), lift), 0.8))
    wy = f.add(f.unpack(wn[1]), f.mul(f.mul(f.unpack(cn[1]), lift), 0.8))
    wx = f.sub(wx, f.mul(f.mul(duw, rim_w), 0.5))
    wy = f.sub(wy, f.mul(f.mul(dvw, rim_w), 0.5))
    ux = f.mul(f.unpack(pl_n[0]), 0.3)
    uy = f.mul(f.unpack(pl_n[1]), 0.3)
    nx = f.lerp(flaked, wx, ux)
    ny = f.lerp(flaked, wy, uy)
    nz = f.lerp(flaked, f.unpack(wn[2]), f.unpack(pl_n[2]))
    # Осыпающийся край штукатурки — скат к кирпичу.
    nx = f.sub(nx, f.mul(f.mul(dul, rim_l), 1.4))
    ny = f.sub(ny, f.mul(f.mul(dvl, rim_l), 1.4))
    nx = f.lerp(hole, nx, bnx)
    ny = f.lerp(hole, ny, bny)
    nz = f.lerp(hole, nz, bnz)
    n = out_normal(g, nx, ny, nz, frame)
    if wall is not None:
        n_side = parallax.vmath(g, "NORMALIZE", parallax.vmath(g, "ADD", n_wall, parallax.vmath(g, "SCALE", g.geo.outputs["Normal"], scale=0.3)))
        n = vmix(g, f.mul(hole, wall), n, n_side)
    return color, rough, n
