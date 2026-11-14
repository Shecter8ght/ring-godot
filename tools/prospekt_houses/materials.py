"""Материалы дома 7 для Cycles: плиточные фото-наборы PBR в мировых координатах (трипланарно по Geometry.Position — одинаково
у всех экземпляров модуля), крупная неоднородность фото-масками владельца, грязь по форме (AO, высота над землёй, потёки).
Чисто процедурных шумов в рисунке нет; White Noise — только как случайный индекс ячейки (какая штора, у какого окна трещина).
Запускается из house7_finish.py (Blender)."""
import math
import os

import bpy
import numpy as np

TEX = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures"
_img = {}
_mean = {}


def load(name, cs="sRGB"):
    key = (name, cs)
    if key in _img:
        return _img[key]
    p = os.path.join(TEX, name)
    im = bpy.data.images.load(p, check_existing=True)
    im.colorspace_settings.name = cs
    _img[key] = im
    return im


def mean_lin(name):
    """Средняя яркость фото-основы в линейном пространстве (для нормировки контраста тона)."""
    if name not in _mean:
        im = load(name)
        a = np.empty(len(im.pixels), np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(-1, 4)[:, :3]
        _mean[name] = float(a.mean())
    return _mean[name]


class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.mat = mat
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.l = self.nt.links
        self.n.clear()
        self.out = self.n.new("ShaderNodeOutputMaterial")
        self.geo = self.n.new("ShaderNodeNewGeometry")
        self.pos = self.sep(self.geo.outputs["Position"])
        self.nrm = self.sep(self.geo.outputs["Normal"])
        self._w = None

    # -------- низкоуровневое
    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, (tuple, list)):
            sock.default_value = v
        else:
            self.l.new(v, sock)

    def node(self, t, **kw):
        nd = self.n.new(t)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def sep(self, vec):
        s = self.node("ShaderNodeSeparateXYZ")
        self.l.new(vec, s.inputs[0])
        return s

    def math(self, op, a, b=None, clamp=False):
        m = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(m.inputs[0], a)
        if b is not None:
            self.put(m.inputs[1], b)
        return m.outputs[0]

    def comb(self, x, y, z):
        c = self.node("ShaderNodeCombineXYZ")
        self.put(c.inputs[0], x); self.put(c.inputs[1], y); self.put(c.inputs[2], z)
        return c.outputs[0]

    def mixc(self, fac, a, b, blend="MIX"):
        m = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.put(m.inputs[0], fac)
        self.put(m.inputs[6], a)
        self.put(m.inputs[7], b)
        return m.outputs[2]

    def rng(self, v, a0, a1, b0, b1, clamp=True):
        m = self.node("ShaderNodeMapRange", clamp=clamp)
        self.put(m.inputs[0], v)
        self.put(m.inputs[1], a0); self.put(m.inputs[2], a1); self.put(m.inputs[3], b0); self.put(m.inputs[4], b1)
        return m.outputs[0]

    def r(self, col):
        s = self.node("ShaderNodeSeparateColor")
        self.l.new(col, s.inputs[0])
        return s.outputs[0]

    def rgb(self, r, g, b, a=None):
        c = self.node("ShaderNodeCombineColor")
        self.put(c.inputs[0], r); self.put(c.inputs[1], g); self.put(c.inputs[2], b)
        return c.outputs[0]

    def const(self, rgb):
        c = self.node("ShaderNodeRGB")
        c.outputs[0].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        return c.outputs[0]

    # -------- трипланарная проекция по мировым координатам
    def weights(self):
        if self._w:
            return self._w
        ax = self.math("POWER", self.math("ABSOLUTE", self.nrm.outputs[0]), 4.0)
        ay = self.math("POWER", self.math("ABSOLUTE", self.nrm.outputs[1]), 4.0)
        az = self.math("POWER", self.math("ABSOLUTE", self.nrm.outputs[2]), 4.0)
        s = self.math("ADD", self.math("ADD", ax, ay), az)
        t1 = self.math("DIVIDE", ay, self.math("MAXIMUM", self.math("ADD", ax, ay), 1e-6))
        wz = self.math("DIVIDE", az, self.math("MAXIMUM", s, 1e-6))
        self._w = (t1, wz)
        return self._w

    def tri(self, name, scale, cs="sRGB", rot=0.0, vst=1.0, off=(0.0, 0.0)):
        """Картинка, размазанная по миру: 1 единица UV = scale метров; vst > 1 растягивает по вертикали (потёки)."""
        im = load(name, cs)
        P = self.pos.outputs
        planes = ((P[1], P[2]), (P[0], P[2]), (P[0], P[1]))
        outs = []
        for (u, v) in planes:
            c = self.comb(u, v, 0.0)
            mp = self.node("ShaderNodeMapping", vector_type="POINT")
            self.put(mp.inputs[0], c)
            mp.inputs[1].default_value = (off[0], off[1], 0)
            mp.inputs[2].default_value = (0, 0, rot)
            mp.inputs[3].default_value = (1.0 / scale, 1.0 / (scale * vst), 1.0)
            t = self.node("ShaderNodeTexImage", image=im, interpolation="Linear", extension="REPEAT")
            self.l.new(mp.outputs[0], t.inputs[0])
            outs.append(t.outputs[0])
        t1, wz = self.weights()
        m1 = self.mixc(t1, outs[0], outs[1])
        return self.mixc(wz, m1, outs[2])

    # -------- составные куски
    def tint_lum(self, alb, tint, mean, c):
        """Цвет = tint · (1 + (яркость фото / среднее − 1) · c): тон задан, рисунок фото сохранён."""
        bw = self.node("ShaderNodeRGBToBW")
        self.l.new(alb, bw.inputs[0])
        k = self.math("ADD", 1.0, self.math("MULTIPLY", self.math("SUBTRACT", self.math("DIVIDE", bw.outputs[0], mean), 1.0), c))
        k = self.math("MAXIMUM", k, 0.05)
        kc = self.rgb(k, k, k)
        return self.mixc(1.0, self.const(tint), kc, "MULTIPLY")

    def hash_cell(self, sx, sy, sz, ox=0.0, oy=0.0, oz=0.0, salt=0.0):
        """Случайное число 0…1 на ячейку мира (какая штора, какое окно треснуло)."""
        P = self.pos.outputs
        fx = self.math("FLOOR", self.math("DIVIDE", self.math("ADD", P[0], ox), sx))
        fy = self.math("FLOOR", self.math("DIVIDE", self.math("ADD", P[1], oy), sy))
        fz = self.math("FLOOR", self.math("DIVIDE", self.math("ADD", P[2], oz), sz))
        v = self.comb(self.math("ADD", fx, salt), fy, fz)
        wn = self.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
        self.l.new(v, wn.inputs[0])
        return wn.outputs[0]

    def ao(self, dist, local=False):
        a = self.node("ShaderNodeAmbientOcclusion", samples=8)
        a.inputs["Distance"].default_value = dist
        a.only_local = local
        return a.outputs["AO"]


def dirt(N, col, rough, splash=0.0, streak=0.0, crev=0.0, algae=0.0, dirt_col=(0.045, 0.040, 0.034), scale_big=7.0):
    """Грязь по форме: брызги снизу (высота над землёй × фото-маска), потёки (вертикально вытянутая фото-маска × укрытость
    от дождя), грязь в углах (AO), зеленоватый налёт у земли на северной стороне."""
    z = N.pos.outputs[2]
    out_f = None
    terms = []
    if splash > 0:
        gm = N.r(N.tri("masks/m_grain.png", 1.6, "Non-Color"))
        rag = N.r(N.tri("masks/m_grain.png", 0.55, "Non-Color", off=(0.37, 0.11)))          # рваная граница: высота сдвинута маской
        zr = N.math("ADD", z, N.math("MULTIPLY", N.math("SUBTRACT", rag, 0.35), 0.7))
        band = N.rng(zr, 0.15, 0.80, 1.0, 0.0)
        gm = N.rng(gm, 0.05, 0.6, 0.3, 1.0)
        terms.append(N.math("MULTIPLY", N.math("MULTIPLY", band, gm), splash))
    if streak > 0:
        # потёки: тонкие, вытянутые вниз (фото-маска зерна ×12 по вертикали), начинаются под горизонтальными швами / перекрытиями
        # (фаза по высоте этажа), только в местах, укрытых от дождя (AO), и вразнобой (крупная облачная маска)
        sm = N.r(N.tri("masks/m_grain.png", 0.9, "Non-Color", vst=12.0, off=(0.31, 0.17)))
        seam = N.math("POWER", N.math("FRACT", N.math("DIVIDE", N.math("SUBTRACT", z, 4.5), 3.0)), 1.5)
        gate = N.rng(N.r(N.tri("masks/m_plaque.png", 9.0, "Non-Color", off=(0.2, 0.6))), 0.03, 0.4, 0.0, 1.0)
        shelter = N.math("ADD", 0.3, N.math("MULTIPLY", 0.7, N.math("SUBTRACT", 1.0, N.ao(1.0))))
        st = N.math("MULTIPLY", N.math("MULTIPLY", N.rng(sm, 0.25, 0.8, 0.0, 1.0), seam), N.math("MULTIPLY", gate, shelter))
        terms.append(N.math("MULTIPLY", st, streak * 1.8))
    if crev > 0:
        terms.append(N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.ao(0.28)), crev))
    f = None
    for t in terms:
        f = t if f is None else N.math("ADD", f, t)
    if f is None:
        return col, rough
    f = N.math("MINIMUM", f, 0.68)
    col2 = N.mixc(f, col, N.const(dirt_col))
    rough2 = N.math("ADD", rough, N.math("MULTIPLY", f, 0.25), clamp=True)
    if algae > 0:
        north = N.rng(N.nrm.outputs[1], 0.15, 0.8, 0.0, 1.0)
        band = N.rng(z, 0.05, 1.1, 1.0, 0.0)
        pm = N.r(N.tri("masks/m_plaque.png", 2.3, "Non-Color", off=(0.5, 0.2)))
        af = N.math("MULTIPLY", N.math("MULTIPLY", north, band), N.math("MULTIPLY", N.rng(pm, 0.05, 0.5, 0.0, 1.0), algae))
        col2 = N.mixc(af, col2, N.const((0.09, 0.13, 0.05)))
    return col2, rough2


def principled(N, col, rough, metal=0.0, bump=None, bump_str=0.4, bump_dist=0.01, spec=0.5, alpha=None, extra=None):
    p = N.node("ShaderNodeBsdfPrincipled")
    N.put(p.inputs["Base Color"], col)
    N.put(p.inputs["Roughness"], rough)
    N.put(p.inputs["Metallic"], metal)
    p.inputs["Specular IOR Level"].default_value = spec
    if bump is not None:
        b = N.node("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump_str
        b.inputs["Distance"].default_value = bump_dist
        N.l.new(bump, b.inputs["Height"])
        N.l.new(b.outputs[0], p.inputs["Normal"])
    if alpha is not None:
        N.put(p.inputs["Alpha"], alpha)
    if extra:
        for k, v in extra.items():
            N.put(p.inputs[k], v)
    N.l.new(p.outputs[0], N.out.inputs[0])
    return p


def base(N, key, scale, rot=0.0, vst=1.0):
    col = N.tri("%s_albedo.jpg" % key, scale, "sRGB", rot, vst)
    rough = N.r(N.tri("%s_rough.jpg" % key, scale, "Non-Color", rot, vst))
    h = N.r(N.tri("%s_height.jpg" % key, scale, "Non-Color", rot, vst))
    return col, rough, h


def lin(rgb255):
    f = lambda c: ((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92
    return tuple(f(c) for c in rgb255)


# ------------------------------------------------------------------ материалы
def m_panel_beige(mat):
    N = NT(mat)
    col, rough, h = base(N, "plaster", 1.5)
    col = N.tint_lum(col, lin((240, 188, 158)), mean_lin("plaster_albedo.jpg"), 0.55)
    mb = N.r(N.tri("masks/m_plaque.png", 14.0, "Non-Color", off=(0.1, 0.4)))     # мягкая облачная мраморность ±3 %, без направленных мазков
    k = N.math("ADD", 0.97, N.math("MULTIPLY", mb, 0.06))
    col = N.mixc(1.0, col, N.rgb(k, k, k), "MULTIPLY")
    col, rough = dirt(N, col, N.math("MULTIPLY", rough, 0.95), splash=0.6, streak=1.0, crev=0.6, algae=0.25)
    principled(N, col, rough, bump=h, bump_str=0.15, bump_dist=0.004)


def m_dark_panel(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_dark", 1.0)
    col = N.tint_lum(col, lin((52, 54, 58)), mean_lin("metal_dark_albedo.jpg"), 0.5)
    mb = N.r(N.tri("masks/m_marble.png", 9.0, "Non-Color", off=(0.7, 0.1)))
    k = N.math("ADD", 0.92, N.math("MULTIPLY", mb, 0.2))
    col = N.mixc(1.0, col, N.rgb(k, k, k), "MULTIPLY")
    col, rough = dirt(N, col, N.math("MAXIMUM", N.math("MULTIPLY", rough, 0.9), 0.5), splash=0.5, streak=0.75, crev=0.6,
                      dirt_col=(0.12, 0.115, 0.105))                    # пыль и светлые потёки извести под плитами
    lime = N.r(N.tri("masks/m_streak.png", 2.6, "Non-Color", vst=1.8, off=(0.2, 0.55)))
    lf = N.math("MULTIPLY", N.rng(lime, 0.25, 0.8, 0.0, 0.5), N.math("SUBTRACT", 1.0, N.ao(0.8)))
    col = N.mixc(lf, col, N.const(lin((150, 146, 138))))
    principled(N, col, rough, metal=0.15, bump=h, bump_str=0.2, bump_dist=0.003)


def m_concrete(mat):
    N = NT(mat)
    col, rough, h = base(N, "conc", 2.0)
    col = N.tint_lum(col, lin((164, 157, 147)), mean_lin("conc_albedo.jpg"), 0.7)
    mb = N.r(N.tri("masks/m_marble.png", 5.0, "Non-Color", off=(0.2, 0.7)))
    mb2 = N.r(N.tri("masks/m_plaque.png", 13.0, "Non-Color", off=(0.1, 0.1)))
    k = N.math("ADD", 0.9, N.math("MULTIPLY", N.math("ADD", mb, mb2), 0.12))
    col = N.mixc(1.0, col, N.rgb(k, k, k), "MULTIPLY")
    # отверстия от стяжек сеткой 0,6 × 1,2 м: тёмная точка и впадина (по высоте), координаты — мир
    P = N.pos.outputs
    pu = N.math("ADD", N.math("MULTIPLY", N.math("ADD", P[0], P[1]), 1.0), 0.0)
    fu = N.math("SUBTRACT", N.math("DIVIDE", pu, 1.2), N.math("FLOOR", N.math("DIVIDE", pu, 1.2)))
    fv = N.math("SUBTRACT", N.math("DIVIDE", P[2], 0.6), N.math("FLOOR", N.math("DIVIDE", P[2], 0.6)))
    du = N.math("SUBTRACT", fu, 0.5)
    dv = N.math("SUBTRACT", fv, 0.5)
    d = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", du, du), N.math("MULTIPLY", dv, dv)))
    tie = N.rng(d, 0.012, 0.022, 1.0, 0.0)                             # диск диаметром 2 см на каждой ячейке
    col = N.mixc(N.math("MULTIPLY", tie, 0.85), col, N.const(lin((30, 28, 26))))
    col, rough = dirt(N, col, rough, splash=0.9, streak=1.0, crev=0.5, algae=0.55, dirt_col=(0.05, 0.048, 0.044))
    principled(N, col, N.math("MAXIMUM", rough, 0.62), bump=N.math("SUBTRACT", h, N.math("MULTIPLY", tie, 0.25)),
               bump_str=0.45, bump_dist=0.01)


def m_alu(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_light", 0.8)
    col = N.tint_lum(col, lin((40, 41, 44)), mean_lin("metal_light_albedo.jpg"), 0.2)
    col, rough = dirt(N, col, N.math("MAXIMUM", N.math("MULTIPLY", rough, 0.6), 0.38), splash=0.4, crev=0.7,
                      dirt_col=(0.1, 0.095, 0.085))
    principled(N, col, rough, metal=0.35, bump=h, bump_str=0.05, bump_dist=0.001, extra={"Coat Weight": 0.0})


def m_steel(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_light", 0.8)
    col = N.tint_lum(col, lin((120, 122, 124)), mean_lin("metal_light_albedo.jpg"), 0.5)
    # шлифованная сталь с пылью: не зеркало (шероховатость не ниже 0,5), пыль и брызги заметнее
    col, rough = dirt(N, col, N.math("MAXIMUM", N.math("MULTIPLY", rough, 0.9), 0.5), splash=0.8, crev=0.8,
                      dirt_col=(0.16, 0.15, 0.135))
    principled(N, col, rough, metal=0.85, bump=h, bump_str=0.1, bump_dist=0.001)


def m_glass(mat, dark=False):
    N = NT(mat)
    dust = N.r(N.tri("masks/m_grain.png", 0.7, "Non-Color", vst=9.0, off=(0.5, 0.2)))      # вертикальные дождевые разводы
    sp = N.r(N.tri("masks/m_grain.png", 1.3, "Non-Color", off=(0.3, 0.6)))                 # редкие брызги
    h = N.hash_cell(3.4, 3.4, 3.0, oy=0.0, oz=-0.9, salt=0.0)
    dirty = N.math("LESS_THAN", N.math("FRACT", N.math("MULTIPLY", h, 7.31)), 0.02)          # 1–2 окна на весь дом «побелённые»
    cracked = N.math("LESS_THAN", h, 0.05)                                                    # ~5 % с трещиной
    z = N.pos.outputs[2]
    bottom = N.rng(N.math("FRACT", N.math("DIVIDE", N.math("SUBTRACT", z, 4.5), 3.0)), 0.0, 0.35, 0.8, 0.0)   # сильнее по низу окна
    # и по углам рамы: AO только своей сетки и на 8 см — иначе цепь, замок и ручки перед стеклом
    # «затемняли» его своим чётким силуэтом (чёрный дубль на cam_chain)
    corner = N.math("SUBTRACT", 1.0, N.ao(0.08, local=True))
    base_dirt = N.math("MULTIPLY", N.rng(dust, 0.3, 0.85, 0.0, 1.0), N.math("ADD", 0.14, N.math("ADD", N.math("MULTIPLY", bottom, 0.22), N.math("MULTIPLY", corner, 0.3))))
    base_dirt = N.math("ADD", base_dirt, N.math("MULTIPLY", N.rng(sp, 0.3, 0.9, 0.0, 1.0), 0.05))
    if dark:
        base_dirt = N.math("MULTIPLY", base_dirt, 1.9)
    d = N.math("MINIMUM", N.math("ADD", base_dirt, N.math("MULTIPLY", dirty, 0.45)), 0.8 if dark else 0.7)
    cr = N.r(N.tri("masks/m_crack.png", 1.7, "Non-Color", off=(0.22, 0.15)))
    cf = N.math("MULTIPLY", cracked, N.rng(cr, 0.1, 0.5, 0.0, 1.0))
    d = N.math("MINIMUM", N.math("ADD", d, cf), 1.0)
    # грязное стекло вестибюля чуть матовее: отражение ручек и цепи в нём размыто, а не чёрный чёткий дубль
    rough = N.math("ADD", 0.07 if dark else 0.02, N.math("MULTIPLY", d, 0.3))
    col = N.mixc(d, N.const(lin((128, 136, 134) if dark else (208, 216, 214))), N.const(lin((60, 56, 50) if dark else (92, 88, 80))))
    principled(N, col, rough, extra={"Transmission Weight": 1.0, "IOR": 1.5})


def m_wood(mat):
    N = NT(mat)
    col, rough, h = base(N, "wood", 0.6, rot=math.pi / 2)         # волокна вдоль рейки (вертикально)
    col = N.tint_lum(col, lin((178, 122, 74)), mean_lin("wood_albedo.jpg"), 0.9)
    z = N.pos.outputs[2]
    fade = N.rng(N.math("FRACT", N.math("DIVIDE", N.math("SUBTRACT", z, 4.5), 3.0)), 0.7, 1.0, 0.0, 0.55)       # выгоревшее сверху
    gm = N.r(N.tri("masks/m_marble.png", 3.0, "Non-Color", off=(0.4, 0.9)))
    col = N.mixc(N.math("MAXIMUM", fade, N.math("MULTIPLY", N.rng(gm, 0.1, 0.6, 0.0, 0.5), 1.0)), col, N.const(lin((128, 114, 100))))
    col, rough = dirt(N, col, N.math("MAXIMUM", rough, 0.55), splash=0.3, crev=0.5, dirt_col=(0.05, 0.04, 0.035))
    principled(N, col, rough, bump=h, bump_str=0.35, bump_dist=0.004)


def m_perf(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_dark", 0.7)
    col = N.tint_lum(col, lin((46, 47, 50)), mean_lin("metal_dark_albedo.jpg"), 0.4)
    col, rough = dirt(N, col, N.math("MAXIMUM", N.math("MULTIPLY", rough, 0.8), 0.45), splash=0.3, crev=0.5, dirt_col=(0.1, 0.1, 0.09))
    alpha = N.r(N.tri("perf_alpha.png", 0.96, "Non-Color"))
    principled(N, col, rough, metal=0.7, alpha=N.math("GREATER_THAN", alpha, 0.5))


def m_interior(mat):
    N = NT(mat)
    principled(N, N.const(lin((26, 20, 16))), 0.95)


def m_lamp(mat):
    """Света нет: матовый рассеиватель с пылью (владелец: дом заброшен)."""
    N = NT(mat)
    col = N.mixc(N.rng(N.r(N.tri("masks/m_grain.png", 0.3, "Non-Color")), 0.1, 0.7, 0.0, 0.45), N.const(lin((196, 192, 182))), N.const(lin((92, 86, 76))))
    principled(N, col, 0.7)


def _curtain(mat, tulle):
    N = NT(mat)
    col, rough, h = base(N, "fabric", 0.5)
    hh = N.hash_cell(3.4, 3.4, 3.0, oz=-0.9, salt=3.0)
    c1 = N.const(lin((222, 216, 198)))      # молочный
    c2 = N.const(lin((190, 172, 146)))      # бежевый
    c3 = N.const(lin((146, 156, 164)))      # серо-голубой
    c4 = N.const(lin((188, 160, 118)))      # охра
    if tulle:
        c1 = N.const(lin((236, 234, 226)))
        c2 = N.const(lin((222, 218, 206)))
        c3 = N.const(lin((228, 230, 232)))
        c4 = N.const(lin((232, 226, 212)))
    pick = N.mixc(N.math("GREATER_THAN", hh, 0.25), c1, c2)
    pick = N.mixc(N.math("GREATER_THAN", hh, 0.5), pick, c3)
    pick = N.mixc(N.math("GREATER_THAN", hh, 0.75), pick, c4)
    lum = N.tint_lum(col, (1.0, 1.0, 1.0), mean_lin("fabric_albedo.jpg"), 0.5)
    col = N.mixc(1.0, pick, lum, "MULTIPLY")
    col, rough = dirt(N, col, N.math("MAXIMUM", rough, 0.8), splash=0.0, crev=0.5, dirt_col=(0.11, 0.1, 0.09))
    if tulle:
        al = N.math("ADD", 0.45, N.math("MULTIPLY", N.r(N.tri("fabric_height.jpg", 0.5, "Non-Color")), 0.3))
        principled(N, col, 0.9, bump=h, bump_str=0.2, bump_dist=0.002, alpha=al, extra={"Sheen Weight": 0.3})
    else:
        principled(N, col, 0.9, bump=h, bump_str=0.4, bump_dist=0.003, extra={"Sheen Weight": 0.5})


def m_curtain(mat):
    _curtain(mat, False)


def m_tulle(mat):
    _curtain(mat, True)


def m_soil(mat):
    N = NT(mat)
    col, rough, h = base(N, "soil", 0.8)
    col = N.mixc(1.0, col, N.const((0.55, 0.5, 0.45)), "MULTIPLY")
    principled(N, col, N.math("MAXIMUM", rough, 0.85), bump=h, bump_str=0.6, bump_dist=0.01)


def m_green(mat):
    N = NT(mat)
    hh = N.hash_cell(0.6, 0.6, 0.6)
    g1 = N.const(lin((70, 104, 40)))
    g2 = N.const(lin((106, 128, 48)))
    col = N.mixc(hh, g1, g2)
    principled(N, col, 0.7, extra={"Subsurface Weight": 0.0})


def m_dry(mat):
    N = NT(mat)
    principled(N, N.const(lin((150, 126, 80))), 0.75)


def m_flower(mat):
    N = NT(mat)
    principled(N, N.const(lin((240, 214, 70))), 0.6)


def m_roof(mat):
    N = NT(mat)
    col, rough, h = base(N, "roof", 1.2)
    col = N.tint_lum(col, lin((70, 68, 66)), mean_lin("roof_albedo.jpg"), 0.8)
    mb = N.r(N.tri("masks/m_marble.png", 6.0, "Non-Color", off=(0.9, 0.3)))
    col = N.mixc(N.rng(mb, 0.05, 0.6, 0.0, 0.5), col, N.const(lin((40, 40, 40))))
    principled(N, col, N.math("MAXIMUM", rough, 0.85), bump=h, bump_str=0.8, bump_dist=0.01)


def m_galv(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_light", 0.9)
    col = N.tint_lum(col, lin((150, 154, 156)), mean_lin("metal_light_albedo.jpg"), 0.6)
    col, rough = dirt(N, col, N.math("MAXIMUM", rough, 0.4), splash=0.3, streak=0.6, crev=0.7, dirt_col=(0.1, 0.09, 0.08))
    principled(N, col, rough, metal=0.9, bump=h, bump_str=0.1, bump_dist=0.001)


def m_door(mat):
    N = NT(mat)
    col, rough, h = base(N, "metal_dark", 0.8)
    col = N.tint_lum(col, lin((64, 74, 68)), mean_lin("metal_dark_albedo.jpg"), 0.5)
    z = N.pos.outputs[2]
    near = N.rng(N.math("ABSOLUTE", N.math("SUBTRACT", z, 1.1)), 0.05, 0.35, 1.0, 0.0)
    gm = N.r(N.tri("masks/m_grain.png", 0.5, "Non-Color"))
    chip = N.math("MULTIPLY", near, N.rng(gm, 0.15, 0.55, 0.0, 1.0))       # сбитая у ручки краска
    col = N.mixc(chip, col, N.const(lin((150, 150, 150))))
    col, rough = dirt(N, col, N.math("MAXIMUM", rough, 0.5), splash=0.6, streak=0.5, crev=0.6, dirt_col=(0.08, 0.075, 0.07))
    principled(N, col, rough, metal=N.math("MULTIPLY", chip, 0.9), bump=h, bump_str=0.2, bump_dist=0.002)


def m_plaster(mat):
    N = NT(mat)
    col, rough, h = base(N, "plaster", 1.5)
    col = N.tint_lum(col, lin((226, 216, 204)), mean_lin("plaster_albedo.jpg"), 0.5)
    principled(N, col, rough, bump=h, bump_str=0.15, bump_dist=0.003)


def m_tile(mat):
    N = NT(mat)
    col, rough, h = base(N, "tile", 1.2)
    col = N.tint_lum(col, lin((128, 124, 118)), mean_lin("tile_albedo.jpg"), 0.6)
    principled(N, col, N.math("MULTIPLY", rough, 0.55), bump=h, bump_str=0.3, bump_dist=0.002)


def m_asphalt(mat):
    N = NT(mat)
    col, rough, h = base(N, "asphalt", 3.0)
    col = N.tint_lum(col, lin((64, 64, 66)), mean_lin("asphalt_albedo.jpg"), 0.9)
    wet = N.r(N.tri("masks/m_smear.png", 9.0, "Non-Color", off=(0.2, 0.2)))
    wet2 = N.r(N.tri("masks/m_marble.png", 14.0, "Non-Color", off=(0.5, 0.5)))
    wf = N.rng(N.math("MULTIPLY", wet, wet2), 0.02, 0.35, 0.0, 1.0)         # мокрые участки (пятнами)
    col = N.mixc(N.math("MULTIPLY", wf, 0.6), col, N.const(lin((34, 34, 36))))
    rough = N.math("SUBTRACT", N.math("MULTIPLY", rough, 0.95), N.math("MULTIPLY", wf, 0.45), clamp=True)
    principled(N, col, N.math("MAXIMUM", rough, 0.22), bump=h, bump_str=0.5, bump_dist=0.01)


def m_apron(mat):
    N = NT(mat)
    col, rough, h = base(N, "conc", 2.5)
    col = N.tint_lum(col, lin((150, 146, 138)), mean_lin("conc_albedo.jpg"), 0.7)
    cr = N.r(N.tri("masks/m_crack.png", 2.6, "Non-Color", off=(0.31, 0.5)))
    col = N.mixc(N.rng(cr, 0.1, 0.5, 0.0, 0.9), col, N.const(lin((30, 28, 26))))
    pm = N.r(N.tri("masks/m_plaque.png", 4.0, "Non-Color", off=(0.6, 0.6)))
    col = N.mixc(N.rng(pm, 0.05, 0.6, 0.0, 0.5), col, N.const(lin((70, 66, 60))))
    col, rough = dirt(N, col, N.math("MAXIMUM", rough, 0.7), splash=0.4, crev=0.5, dirt_col=(0.05, 0.048, 0.044))
    principled(N, col, rough, bump=h, bump_str=0.5, bump_dist=0.01)


def m_chain(mat):
    """Потемневшая оцинковка: ржавчина в зазорах (AO) и пятнами по фото-маске."""
    N = NT(mat)
    col, rough, h = base(N, "metal_light", 0.4)
    col = N.tint_lum(col, lin((104, 104, 106)), mean_lin("metal_light_albedo.jpg"), 0.5)
    rust = N.math("ADD", N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.ao(0.012)), 0.9),
                  N.math("MULTIPLY", N.rng(N.r(N.tri("masks/m_plaque.png", 0.25, "Non-Color")), 0.1, 0.6, 0.0, 1.0), 0.45))
    col = N.mixc(N.math("MINIMUM", rust, 0.9), col, N.const(lin((120, 62, 34))))
    principled(N, col, N.math("MAXIMUM", rough, 0.5), metal=0.9, bump=h, bump_str=0.1, bump_dist=0.0005)


def m_notice(mat):
    N = NT(mat)
    uv = N.node("ShaderNodeTexCoord")
    t = N.node("ShaderNodeTexImage", image=load("notice.png", "sRGB"), interpolation="Linear", extension="CLIP")
    N.l.new(uv.outputs["UV"], t.inputs[0])
    p = principled(N, t.outputs[0], 0.85)
    N.l.new(t.outputs[0], p.inputs["Emission Color"])        # бумага ловит дневной свет через стекло: без этого за тёмным стеклом лист не читается
    p.inputs["Emission Strength"].default_value = 1.1


def m_tape(mat):
    N = NT(mat)
    principled(N, N.const(lin((200, 190, 150))), 0.4, alpha=0.45)


def m_sleeve(mat):
    N = NT(mat)
    principled(N, N.const((1, 1, 1, 1)), 0.18, extra={"Transmission Weight": 1.0, "IOR": 1.45})


def m_police(mat):
    N = NT(mat)
    principled(N, N.const(lin((150, 150, 150))), 0.9)


MATS = {
    "panel_beige": m_panel_beige, "dark_panel": m_dark_panel, "concrete": m_concrete, "alu_frame": m_alu, "steel": m_steel,
    "glass": m_glass, "wood": m_wood, "perf_metal": m_perf, "interior": m_interior, "lamp": m_lamp,
    "штора_заглушка": m_curtain, "тюль_заглушка": m_tulle, "земля": m_soil,
    # свои материалы объектов
    "roof_membrane": m_roof, "galvanized": m_galv, "door_steel": m_door, "plaster_light": m_plaster, "floor_tile": m_tile,
    "asphalt_wet": m_asphalt, "apron": m_apron, "glass_dark": lambda mt: m_glass(mt, True), "chain_steel": m_chain,
    "notice": m_notice, "tape": m_tape, "sleeve": m_sleeve, "preview_police": m_police, "weed_green": m_green, "weed_dry": m_dry, "weed_flower": m_flower,
}


def get(name):
    m = bpy.data.materials.get(name + "_F")
    if m:
        return m
    m = bpy.data.materials.new(name + "_F")
    MATS[name](m)
    return m


def decal_mat(name, mask, col, strength, scale_alpha=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    N = NT(m)
    uv = N.node("ShaderNodeTexCoord")
    t = N.node("ShaderNodeTexImage", image=load(mask, "Non-Color"), interpolation="Linear", extension="REPEAT")
    N.l.new(uv.outputs["UV"], t.inputs[0])
    a = N.math("MULTIPLY", N.r(t.outputs[0]), strength, clamp=True)
    principled(N, N.const(col), 0.9, alpha=a)
    return m
