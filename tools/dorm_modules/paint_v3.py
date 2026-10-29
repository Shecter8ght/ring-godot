"""Облупленная масляная краска v03 — узлы материала Blender (карты gen_paint_v3.py, тайл 2 × 2 м).

Износ w — доля снятой краски в этом месте (атрибут «Износ», пятна по месту, ползунок «Износ краски, база»).
По картам E и её крутизне материал считает s — расстояние до кромки отслоения в миллиметрах (s > 0 — краска,
s < 0 — голое место) — и по нему рисует всё, что живёт у кромки при любом износе:
- кромка: тонкая светлая грань толщины краски, у ступеньки грязь;
- загиб: местами краска у кромки скатана валиком (ширина 1–4 мм) — светлая изнанка, за ним тень на штукатурке;
- у кромки (до ~2 см) края кусков приподняты «блюдцем», трещины шире и темнее;
- под краской: шпаклёвка пятнами (чаще у кромки), местами старый слой краски ступенькой, штукатурка с грязью и
  зеленоватым следом краски у кромки.
Нормали собираются из карт и направления крутизны без производных экрана — тот же расчёт пойдёт в шейдер Godot.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texture_layers import param, smoothstep, _c  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/paint_v3"


def img(g, name: str, vec, color: bool = False, folder: str = KIT):
    nd = g.node("ShaderNodeTexImage")
    im = bpy.data.images.load(f"{folder}/{name}", check_existing=True)
    im.colorspace_settings.name = "sRGB" if color else "Non-Color"
    im.alpha_mode = "CHANNEL_PACKED"
    nd.image = im
    nd.interpolation = "Linear"
    g.link(vec, nd.inputs["Vector"])
    return nd


def chans(g, nd):
    sc = g.node("ShaderNodeSeparateColor")
    g.link(nd.outputs["Color"], sc.inputs[0])
    return sc.outputs[0], sc.outputs[1], sc.outputs[2], nd.outputs["Alpha"]


def rgb_param(g, label: str, hexcolor: str):
    nd = g.node("ShaderNodeRGB")
    nd.label = label
    nd.name = label
    nd.outputs[0].default_value = _c(hexcolor)
    return nd.outputs[0]


class F:
    """Короткая запись арифметики узлами."""

    def __init__(self, g):
        self.g = g

    def __call__(self, op, a, b=None, clamp=False):
        return self.g.math(op, a, b, clamp)

    def add(self, a, b):
        return self.g.math("ADD", a, b)

    def sub(self, a, b):
        return self.g.math("SUBTRACT", a, b)

    def mul(self, a, b):
        return self.g.math("MULTIPLY", a, b)

    def lerp(self, t, a, b):
        return self.g.mixf(t, a, b)

    def inv(self, a):
        return self.g.math("SUBTRACT", 1.0, a)

    def ss(self, e0, e1, x):
        return smoothstep(self.g, e0, e1, x)

    def unpack(self, x):
        """0…1 из карты → −1…1."""
        return self.g.math("SUBTRACT", self.g.math("MULTIPLY", x, 2.0), 1.0)


def wall_coords(g, scale: float = 0.5):
    """Координаты стены от мира: вдоль стены (x или y мира — по тому, куда смотрит грань) и по высоте.
    Рисунок идёт через стыки модулей без шва. Возвращает (вектор для карт, рамку T, B, N для нормали)."""
    px, py, pz = g.sep(g.geo.outputs["Position"])
    nx, ny, _ = g.sep(g.geo.outputs["Normal"])
    m = g.math("GREATER_THAN", g.math("ABSOLUTE", nx), g.math("ABSOLUTE", ny))
    u = g.mixf(m, px, py)
    vec = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", u, scale), vec.inputs[0])
    g.link(g.math("MULTIPLY", pz, scale), vec.inputs[1])
    t = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("SUBTRACT", 1.0, m), t.inputs[0])
    g.link(m, t.inputs[1])
    bvec = g.node("ShaderNodeCombineXYZ")
    bvec.inputs[2].default_value = 1.0
    return vec.outputs[0], (t.outputs[0], bvec.outputs[0], g.geo.outputs["Normal"])


def out_normal(g, nx, ny, nz, frame):
    """Нормаль из составляющих в осях карты: с рамкой (T, B, N) — в мире (n = nx·T + ny·B + nz·N), без неё —
    касательные развёртки через узел Normal Map."""
    if frame is not None:
        acc = None
        for comp, axis in zip((nx, ny, nz), frame):
            sc = g.node("ShaderNodeVectorMath", operation="SCALE")
            g.link(axis, sc.inputs[0])
            g.link(comp, sc.inputs["Scale"])
            if acc is None:
                acc = sc.outputs[0]
            else:
                ad = g.node("ShaderNodeVectorMath", operation="ADD")
                g.link(acc, ad.inputs[0])
                g.link(sc.outputs[0], ad.inputs[1])
                acc = ad.outputs[0]
        nw = g.node("ShaderNodeVectorMath", operation="NORMALIZE")
        g.link(acc, nw.inputs[0])
        return nw.outputs[0]
    vec_n = g.node("ShaderNodeCombineXYZ")
    for i, sck in enumerate((nx, ny, nz)):
        g.link(sck, vec_n.inputs[i])
    nrm = g.node("ShaderNodeVectorMath", operation="NORMALIZE")
    g.link(vec_n.outputs[0], nrm.inputs[0])
    enc = g.node("ShaderNodeVectorMath", operation="MULTIPLY_ADD")
    g.link(nrm.outputs[0], enc.inputs[0])
    enc.inputs[1].default_value = (0.5, 0.5, 0.5)
    enc.inputs[2].default_value = (0.5, 0.5, 0.5)
    nm = g.node("ShaderNodeNormalMap")
    g.link(enc.outputs[0], nm.inputs["Color"])
    return nm.outputs[0]


def paint_v3(g, vec, wear, frame=None):
    """Слой краски. Возвращает (цвет, шероховатость, нормаль-вектор). frame = (T, B, N) — оси карты в мире
    (координаты от мира, wall_coords); без неё — касательные развёртки (узел Normal Map)."""
    f = F(g)
    col_paint = rgb_param(g, "Цвет краски", "4c6e5a")
    col_old = rgb_param(g, "Цвет старого слоя", "b5a987")
    share_old = param(g, "Старый слой, доля", 0.6)
    share_curl = param(g, "Загиб кромки, доля", 1.0)
    t_paint = param(g, "Рельеф краски, сила", 1.0)
    gloss = param(g, "Шероховатость краски", 0.24)

    E, LG, DU, DV = chans(g, img(g, "peel.png", vec))
    Q, CUP, RND, NOCURL = chans(g, img(g, "paint_masks.png", vec))
    TONE, DRIP, SPECK, CHALK = chans(g, img(g, "paint_tone.png", vec))
    PUTTY, OLD, GRIME, CURL = chans(g, img(g, "under_masks.png", vec))
    OC, OE, PC, ET = chans(g, img(g, "under_cells.png", vec))
    pn = chans(g, img(g, "paint_normal.png", vec))
    cn = chans(g, img(g, "cup_normal.png", vec))
    pl_alb = img(g, "plaster_albedo.jpg", vec, True).outputs["Color"]
    pl_n = chans(g, img(g, "plaster_normal.jpg", vec))
    pl_r = img(g, "plaster_rough.jpg", vec).outputs["Color"]

    # Расстояние до кромки, мм.
    G = f("POWER", 10.0, f.sub(f.mul(LG, 5.0), 5.0))
    s = f("DIVIDE", f.sub(E, wear), f("MAXIMUM", G, 0.0004))
    s = f("MINIMUM", f("MAXIMUM", s, -80.0), 80.0)
    du, dv = f.unpack(DU), f.unpack(DV)
    peeled = f.inv(f.ss(-0.15, 0.15, s))
    inside = f("MAXIMUM", f.mul(s, -1.0), 0.0)                     # мм вглубь голого места

    # ---------------------------------------------------------------- краска
    dmg = f.inv(f.ss(0.0, 18.0, s))
    opening = f.add(1.0, f.mul(dmg, 1.4))
    crack = f.inv(f.ss(f.mul(opening, 0.85), f.mul(opening, 1.6), f.mul(Q, 4.0)))
    lift = f.mul(f("POWER", dmg, 1.4), f.add(0.4, f.mul(RND, 0.6)))
    tone = f.add(0.7, f.mul(TONE, 0.6))
    c = g.tint(col_paint, tone)
    c = g.mix(f.mul(CHALK, 0.08), c, _c("a7ad9b"))
    c = g.mix(f.mul(DRIP, 0.28), c, _c("4e4a36"))
    c = g.mix(f.mul(SPECK, 0.85), c, _c("1f1b15"))
    c = g.mix(f.mul(crack, 0.93), c, _c("241e18"))
    rim = f.mul(f.inv(f.ss(0.05, 0.5, s)), f.inv(peeled))
    c = g.mix(f.mul(rim, 0.12), c, _c("c3c4b2"))
    r_paint = f.add(f.add(gloss, f.mul(f.inv(TONE), 0.1)), f.add(f.mul(CHALK, 0.1), f.mul(SPECK, 0.15)))
    r_paint = f.lerp(crack, f.add(r_paint, f.mul(DRIP, 0.08)), 0.88)

    # ---------------------------------------------------------------- загиб кромки
    cw = f.add(2.4, f.mul(CURL, 3.8))
    t = f("DIVIDE", inside, cw)
    # Загиб — только на кромке большого поля краски (по гладкой части E), не у островков и одиночных дырок.
    s_main = f("ABSOLUTE", f("DIVIDE", f.sub(ET, wear), f("MAXIMUM", G, 0.0004)))
    main = f.inv(f.ss(2.5, 7.0, s_main))
    pres = f("MINIMUM", f.mul(f.mul(f.mul(f.ss(0.4, 0.72, CURL), share_curl), f.inv(NOCURL)), main), 1.0)
    in_curl = f.mul(f.mul(pres, f.ss(0.0, 0.04, t)), f.inv(f.ss(0.9, 1.0, t)))
    x = f("MINIMUM", f("MAXIMUM", f.sub(f.mul(t, 2.0), 1.0), -1.0), 1.0)
    nzc = f("SQRT", f("MAXIMUM", f.sub(1.0, f.mul(x, x)), 0.0))
    # Сверху валика — лицо краски, к внешнему краю видна светлая изнанка; низ в тени.
    under_side = g.mix(f.mul(f.ss(0.0, 0.9, x), 0.45), g.tint(col_paint, 1.05), _c("d6d4c6"))
    curl_c = g.tint(under_side, f.add(0.35, f.mul(nzc, 0.65)))
    shadow = f.mul(f.mul(pres, f.ss(0.95, 1.05, t)), f.inv(f.ss(1.1, 2.3, t)))

    # ---------------------------------------------------------------- под краской
    # Слои снимаются ступеньками: сверху зелёный, под ним местами старый слой, ниже шпаклёвка, потом штукатурка.
    # Каждый нижний слой отходит по тому же полю E со своим порогом (держится крепче): маленький выпавший кусок
    # открывает слой целиком, у длинной кромки остаётся полоса — шире, где поле пологое. Кромка слоя рвётся по
    # своей мелкой сетке кусков (старый слой ~8 мм, шпаклёвка ~12 мм).
    Gs = f("MAXIMUM", G, 0.0004)
    t_old = f.mul(f.add(f.mul(f("MAXIMUM", f.sub(OLD, 0.5), 0.0), 0.3), f.mul(f.sub(OC, 0.5), 0.025)), share_old)
    t_putty = f.add(f.mul(f("MAXIMUM", f.sub(PUTTY, 0.3), 0.0), 0.22), f.mul(f.sub(PC, 0.5), 0.03))
    s_old = f("DIVIDE", f.add(f.sub(E, wear), t_old), Gs)
    s_putty = f("DIVIDE", f.add(f.add(f.sub(E, wear), t_old), t_putty), Gs)
    old = f.mul(peeled, f.ss(-0.2, 0.2, s_old))
    putty = f.mul(f.mul(peeled, f.inv(old)), f.ss(-0.2, 0.2, s_putty))
    plaster = g.tint(_c("c4b6a8"), 1.0)
    plaster = g.mix(1.0, pl_alb, plaster, "MULTIPLY")
    plaster = g.tint(plaster, 1.05)
    plaster = g.mix(f.mul(GRIME, 0.6), plaster, _c("6d625a"), "MULTIPLY")
    plaster = g.mix(f.mul(f.inv(f.ss(0.0, 5.0, inside)), 0.2), plaster, col_paint)
    # Шпаклёвка: светлая, но не бумажная — пятна грязи, поры и следы шпателя из скана штукатурки (обесцвеченного).
    pl_l = g.lum(pl_alb)
    putty_c = g.tint(_c("c2bba8"), f.add(0.55, f.mul(pl_l, 0.75)))
    putty_c = g.mix(f.mul(GRIME, 0.5), putty_c, _c("7d6f5c"), "MULTIPLY")
    u = g.mix(putty, plaster, putty_c)
    u = g.mix(old, u, g.tint(col_old, f.add(0.8, f.mul(TONE, 0.4))))
    step_dirt = f.mul(f.inv(f.ss(0.0, 0.9, inside)), f.inv(pres))
    u = g.tint(u, f.sub(1.0, f.add(f.mul(step_dirt, 0.5), f.mul(shadow, 0.7))))
    r_under = f.lerp(putty, g.lum(pl_r), 0.9)
    r_under = f.lerp(old, r_under, 0.72)

    ledge_o = f.mul(old, f.inv(f.ss(0.05, 0.5, s_old)))
    ledge_p = f.mul(putty, f.inv(f.ss(0.05, 0.6, s_putty)))
    foot = f.mul(f.mul(peeled, f.inv(f.add(old, putty))), f.inv(f.ss(0.0, 0.8, f.mul(s_putty, -1.0))))
    u = g.tint(u, f.sub(1.0, f.mul(f("MINIMUM", foot, 1.0), 0.35)))
    color = g.mix(peeled, c, u)
    color = g.mix(in_curl, color, curl_c)
    rough = f.lerp(peeled, r_paint, r_under)
    rough = f.lerp(in_curl, rough, 0.75)

    # ---------------------------------------------------------------- нормаль
    k = t_paint
    px = f.add(f.unpack(pn[0]), f.mul(f.mul(f.unpack(cn[0]), lift), 0.8))
    py = f.add(f.unpack(pn[1]), f.mul(f.mul(f.unpack(cn[1]), lift), 0.8))
    px = f.sub(px, f.mul(f.mul(du, rim), 0.6))
    py = f.sub(py, f.mul(f.mul(dv, rim), 0.6))
    px, py = f.mul(px, k), f.mul(py, k)
    pls = f.sub(0.45, f.mul(putty, 0.2))
    ux = f.sub(f.mul(f.unpack(pl_n[0]), pls), f.mul(du, f.add(f.mul(ledge_o, 0.35), f.mul(ledge_p, 0.3))))
    uy = f.sub(f.mul(f.unpack(pl_n[1]), pls), f.mul(dv, f.add(f.mul(ledge_o, 0.35), f.mul(ledge_p, 0.3))))
    nx = f.lerp(peeled, px, ux)
    ny = f.lerp(peeled, py, uy)
    nz = f.lerp(peeled, f.unpack(pn[2]), f.unpack(pl_n[2]))
    # Валик: нормаль по сечению трубки поперёк кромки.
    nx = f.lerp(in_curl, nx, f.mul(f.mul(x, du), -0.9))
    ny = f.lerp(in_curl, ny, f.mul(f.mul(x, dv), -0.9))
    nz = f.lerp(in_curl, nz, nzc)
    nrm_out = out_normal(g, nx, ny, nz, frame)
    dbg = os.environ.get("PAINT_V3_DEBUG")
    if dbg:
        # Проверка масок: R — загиб, G — шпаклёвка, B — старый слой (или имя канала), без света.
        masks = {"curl": in_curl, "putty": putty, "old": old, "peeled": peeled, "lift": lift, "crack": crack}
        if dbg == "layers":
            cc = g.node("ShaderNodeCombineColor")
            for i, k in enumerate(("curl", "putty", "old")):
                g.link(masks[k], cc.inputs[i])
            color = cc.outputs[0]
        else:
            color = masks[dbg]
        em = g.node("ShaderNodeEmission")
        g.link(color, em.inputs[0])
        g.link(em.outputs[0], g.out.inputs[0])
    return color, rough, nrm_out
