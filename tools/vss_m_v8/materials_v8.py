# ВСС-М v8: материалы собственным способом (без UCUPaint): слоистые графы Cycles.
# Слои: основа покрытия → износ кромок до металла (выпуклость по Bevel и AO изнутри, рвётся шумом) → царапины
# (маски владельца, трёхпроекционно в координатах объекта) → грязь и пыль в углублениях (AO) → масляная плёнка
# и отпечатки (декали на пустышках, блеск через Coat). Свойства объекта wear / dust / grime / prints масштабируют слои.
import math
import os
import bpy

MASKS = "E:/Models Blender/Маски_АЛЬФА"
TEX = "E:/Games/RING-godot/assets/textures"


# ---------------- изображения ----------------

def image(path, noncolor=True):
    name = os.path.basename(path)
    im = bpy.data.images.get(name)
    if im is None:
        im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
    return im


def mask(rel):
    return image(os.path.join(MASKS, rel))


# ---------------- построитель узлов ----------------

class G:
    def __init__(self, tree):
        self.t = tree
        self.N = tree.nodes
        self.L = tree.links
        self.x = 0

    def n(self, kind, **kw):
        nd = self.N.new(kind)
        for k, v in kw.items():
            if k.startswith("in_"):
                nd.inputs[k[3:]].default_value = v
            else:
                setattr(nd, k, v)
        nd.location = (self.x, 0)
        self.x += 40
        return nd

    def link(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1], b)
        if c is not None:
            self._in(nd.inputs[2], c)
        return nd.outputs[0]

    def _in(self, sock, val):
        if isinstance(val, (int, float)):
            sock.default_value = val
        else:
            self.L.new(val, sock)

    def mix(self, fac, a, b, kind="RGBA", blend="MIX"):
        nd = self.n("ShaderNodeMix", data_type=kind, blend_type=blend, clamp_factor=True)
        if kind == "RGBA":
            self._in(nd.inputs[0], fac)
            self._setc(nd.inputs[6], a); self._setc(nd.inputs[7], b)
            return nd.outputs[2]
        self._in(nd.inputs[0], fac)
        self._in(nd.inputs[2], a); self._in(nd.inputs[3], b)
        return nd.outputs[0]

    def _setc(self, sock, val):
        if isinstance(val, tuple):
            sock.default_value = (*val, 1.0) if len(val) == 3 else val
        else:
            self.L.new(val, sock)

    def maprange(self, v, a, b, c=0.0, d=1.0, interp="LINEAR"):
        nd = self.n("ShaderNodeMapRange", interpolation_type=interp, clamp=True)
        self._in(nd.inputs[0], v)
        nd.inputs[1].default_value = a; nd.inputs[2].default_value = b
        nd.inputs[3].default_value = c; nd.inputs[4].default_value = d
        return nd.outputs[0]

    def objattr(self, name, default=1.0):
        nd = self.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name=name)
        # отсутствует свойство → 0; подставляем default через max(attr, флаг отсутствия) нельзя, поэтому
        # у каждого объекта свойства задаются явно (assign()).
        return nd.outputs["Fac"]

    def objcoord(self):
        return self.n("ShaderNodeTexCoord").outputs["Object"]

    def scaled(self, vec, s, rot=(0, 0, 0), loc=(0, 0, 0)):
        m = self.n("ShaderNodeMapping")
        self.L.new(vec, m.inputs["Vector"])
        m.inputs["Scale"].default_value = s if isinstance(s, tuple) else (s, s, s)
        m.inputs["Rotation"].default_value = rot
        m.inputs["Location"].default_value = loc
        return m.outputs[0]

    def tri(self, img, vec, blend=0.25, extension="REPEAT"):
        nd = self.n("ShaderNodeTexImage", image=img, projection="BOX", projection_blend=blend, extension=extension,
                    interpolation="Cubic")
        self.L.new(vec, nd.inputs["Vector"])
        return nd.outputs["Color"]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dist=0.0, dims="3D"):
        nd = self.n("ShaderNodeTexNoise", noise_dimensions=dims)
        self.L.new(vec, nd.inputs["Vector"])
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = dist
        return nd.outputs["Fac"]

    def bw(self, col):
        nd = self.n("ShaderNodeRGBToBW")
        self.L.new(col, nd.inputs[0])
        return nd.outputs[0]

    def edge(self, radius_mm, lo=0.02, hi=0.25, ao_mm=None):
        bev = self.n("ShaderNodeBevel", samples=8)
        bev.inputs["Radius"].default_value = radius_mm * 0.001
        geo = self.n("ShaderNodeNewGeometry")
        dot = self.n("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        self.L.new(bev.outputs[0], dot.inputs[0]); self.L.new(geo.outputs["Normal"], dot.inputs[1])
        e = self.maprange(self.math("SUBTRACT", 1.0, dot.outputs["Value"]), lo, hi)
        ao = self.n("ShaderNodeAmbientOcclusion", inside=True, only_local=True, samples=8)
        ao.inputs["Distance"].default_value = (ao_mm or radius_mm * 3.0) * 0.001
        conv = self.maprange(self.math("SUBTRACT", 1.0, ao.outputs["AO"]), 0.25, 0.75)
        return self.math("MULTIPLY", e, conv, clamp=True)

    def cavity(self, dist_mm, lo=0.15, hi=0.85):
        ao = self.n("ShaderNodeAmbientOcclusion", only_local=True, samples=8)
        ao.inputs["Distance"].default_value = dist_mm * 0.001
        return self.maprange(self.math("SUBTRACT", 1.0, ao.outputs["AO"]), lo, hi)

    def facing_up(self, lo=0.4, hi=0.95):
        geo = self.n("ShaderNodeNewGeometry")
        sep = self.n("ShaderNodeSeparateXYZ")
        self.L.new(geo.outputs["Normal"], sep.inputs[0])
        return self.maprange(sep.outputs["Z"], lo, hi)


# ---------------- декали (отпечатки) ----------------

DECALS = []   # (имя пустышки, путь маски, invert, материалы)


def decal_mask(g, empties):
    """Сумма отпечатков: картинка в координатах пустышки (XY — плоскость следа, ±1 по размеру), затухание по |Z|."""
    acc = None
    for emp, img, inv in empties:
        tc = g.n("ShaderNodeTexCoord", object=emp)
        v = g.scaled(tc.outputs["Object"], (0.5, 0.5, 0.5), loc=(0.5, 0.5, 0.0))
        im = g.n("ShaderNodeTexImage", image=img, extension="CLIP", interpolation="Cubic")
        g.L.new(v, im.inputs["Vector"])
        val = g.bw(im.outputs["Color"])
        if inv:
            val = g.math("SUBTRACT", 1.0, val)
        val = g.maprange(val, 0.22, 0.85)
        # мягкий край декали: к границе квадрата маска гаснет (у картинок не везде чёрный фон)
        sxy = g.n("ShaderNodeSeparateXYZ"); g.L.new(tc.outputs["Object"], sxy.inputs[0])
        edge_x = g.maprange(g.math("ABSOLUTE", sxy.outputs["X"]), 0.75, 0.98, 1.0, 0.0)
        edge_y = g.maprange(g.math("ABSOLUTE", sxy.outputs["Y"]), 0.75, 0.98, 1.0, 0.0)
        val = g.math("MULTIPLY", val, g.math("MULTIPLY", edge_x, edge_y))
        sep = g.n("ShaderNodeSeparateXYZ"); g.L.new(tc.outputs["Object"], sep.inputs[0])
        zf = g.maprange(g.math("ABSOLUTE", sep.outputs["Z"]), 0.6, 1.0, 1.0, 0.0)
        val = g.math("MULTIPLY", val, zf)
        acc = val if acc is None else g.math("MAXIMUM", acc, val)
    return acc


# ---------------- общий слоистый материал ----------------

_DBG = {}


def _aov(g, name, val):
    """Отладка масок: MASK_DEBUG=имя — материал светится значением этой маски (вместо BSDF)."""
    _DBG[name] = val


def layered(name, P, empties=()):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    g = G(t)
    out = g.n("ShaderNodeOutputMaterial", target="ALL")
    bsdf = g.n("ShaderNodeBsdfPrincipled")
    g.link(bsdf.outputs[0], out.inputs["Surface"])
    obj = g.objcoord()
    wear_k = g.objattr("wear"); dust_k = g.objattr("dust"); grime_k = g.objattr("grime"); oil_k = g.objattr("oil")

    # основа: цвет с крупной вариацией (пятна обработки), микрошероховатость
    v_big = g.noise(obj, P.get("var_scale", 30.0), 3.0, 0.5)
    v_mid = g.noise(obj, P.get("var_scale", 30.0) * 6.0, 4.0, 0.6)
    var = g.math("MULTIPLY_ADD", g.math("ADD", v_big, v_mid), 0.5, -0.5)
    base = g.mix(g.maprange(var, -0.25, 0.25), P["base"], P.get("base2", P["base"]))
    micro = g.noise(obj, P.get("micro_scale", 2500.0), 6.0, 0.7)
    rough = g.math("MULTIPLY_ADD", micro, P["rough"][1] - P["rough"][0], P["rough"][0])
    metal = P.get("metal", 0.0)
    height = g.math("MULTIPLY", micro, P.get("micro_h", 0.15))

    # особая фактура (накатка, шагрень, дерево) задаётся функцией
    if "special" in P:
        base, rough, height, metal = P["special"](g, obj, base, rough, height, metal)

    # износ кромок до основы
    ewear = None
    if "edge" in P:
        E = P["edge"]
        e = g.edge(E["r"], E.get("lo", 0.02), E.get("hi", 0.2))
        brk = g.noise(obj, E.get("brk_scale", 260.0), 8.0, 0.65, 0.3)
        brk2 = g.noise(obj, E.get("brk_scale", 260.0) * 4.5, 6.0, 0.7)
        brk = g.math("MULTIPLY_ADD", brk, 0.7, g.math("MULTIPLY", brk2, 0.45))
        # износ рвётся: примерно половина кромок цела, на остальных — прерывистые потёртости
        ew = g.math("SUBTRACT", g.math("MULTIPLY", e, g.math("MULTIPLY", wear_k, E.get("k", 1.6))),
                    g.maprange(brk, 0.42, 0.72, 1.0, 0.0))
        ewear = g.maprange(ew, 0.05, 0.35)
        _aov(g, "m_edge", ewear)
        halo = g.maprange(ew, -0.25, 0.1)
        base = g.mix(halo, base, E.get("halo_col", P["base"]))
        rough = g.mix(halo, rough, E.get("halo_r", 0.45), kind="FLOAT")
        base = g.mix(ewear, base, E["col"])
        rough = g.mix(ewear, rough, E["rough"], kind="FLOAT")
        metal = g.mix(ewear, metal, E.get("metal", 1.0), kind="FLOAT")
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", ewear, 0.25))

    # царапины: маски владельца в трёх проекциях с разным масштабом и поворотом
    if "scratch" in P:
        S = P["scratch"]
        acc = None
        for i, (img, sc, rot) in enumerate(S["maps"]):
            v = g.scaled(obj, sc, rot=rot)
            c = g.bw(g.tri(img, v, 0.3))
            acc = c if acc is None else g.math("MAXIMUM", acc, c)
        zone = g.maprange(g.noise(obj, S.get("zone_scale", 14.0), 2.0, 0.5), 0.5, 0.66)
        sm = g.math("MULTIPLY", g.maprange(acc, S.get("lo", 0.55), S.get("hi", 0.92)), zone)
        sm = g.math("MULTIPLY", sm, g.math("MULTIPLY", wear_k, S.get("k", 1.0)), clamp=True)
        _aov(g, "m_scratch", sm)
        base = g.mix(sm, base, S["col"])
        rough = g.mix(sm, rough, S["rough"], kind="FLOAT")
        metal = g.mix(sm, metal, S.get("metal", 0.85), kind="FLOAT")
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", sm, 0.35))

    # грязь в углублениях и пыль на верхних гранях
    if "grime" in P:
        R = P["grime"]
        cav = g.cavity(R.get("dist", 4.0), R.get("lo", 0.2), R.get("hi", 0.8))
        dm = g.bw(g.tri(R["mask"], g.scaled(obj, R.get("scale", 14.0)), 0.3))
        dm = g.maprange(dm, 0.05, 0.6, 0.35, 1.0)
        gm = g.math("MULTIPLY", g.math("MULTIPLY", cav, dm), g.math("MULTIPLY", grime_k, R.get("k", 1.0) * 0.45), clamp=True)
        dmask = g.bw(g.tri(R.get("dust_mask", R["mask"]), g.scaled(obj, 11.0, rot=(0.5, 0.2, 1.1)), 0.3))
        up = g.math("MULTIPLY", g.facing_up(0.5, 0.95), g.maprange(dmask, 0.35, 0.85))
        dust = g.math("MULTIPLY", up, g.math("MULTIPLY", dust_k, R.get("dust", 0.35) * 0.12), clamp=True)
        _aov(g, "m_grime", gm)
        _aov(g, "m_dust", dust)
        base = g.mix(gm, base, R["col"])
        rough = g.mix(gm, rough, R.get("rough", 0.9), kind="FLOAT")
        metal = g.mix(gm, metal, 0.0, kind="FLOAT")
        base = g.mix(dust, base, R.get("dust_col", (0.32, 0.30, 0.27)))
        rough = g.mix(dust, rough, 0.95, kind="FLOAT")
        metal = g.mix(dust, metal, 0.0, kind="FLOAT")
        height = g.math("ADD", height, g.math("MULTIPLY", dust, 0.1))

    # масляная плёнка (лёгкая, рваная) и отпечатки — блеск в Coat, лёгкая сероватая дымка в цвете
    coat = None
    if "oil" in P:
        O = P["oil"]
        oil = g.bw(g.tri(O["mask"], g.scaled(obj, O.get("scale", 9.0), rot=(0.3, 0.7, 0.2)), 0.3))
        oil = g.math("MULTIPLY", g.maprange(oil, 0.25, 0.85), g.math("MULTIPLY", oil_k, O.get("k", 0.5)), clamp=True)
        base = g.mix(g.math("MULTIPLY", oil, 0.5), base, (0.004, 0.004, 0.004))
        rough = g.math("SUBTRACT", rough, g.math("MULTIPLY", oil, 0.08))
    if empties:
        pm = decal_mask(g, empties)
        pm = g.math("MULTIPLY", pm, P.get("print_k", 1.0), clamp=True)
        pc = g.math("MULTIPLY", pm, 0.55)
        coat = pc if coat is None else g.math("MAXIMUM", coat, pc)
        base = g.mix(g.math("MULTIPLY", pm, 0.14), base, P.get("print_col", (0.09, 0.09, 0.09)))
        rough = g.mix(g.math("MULTIPLY", pm, 0.35), rough, 0.35, kind="FLOAT")
        height = g.math("ADD", height, g.math("MULTIPLY", pm, 0.05))

    # выход
    if coat is not None:
        _aov(g, "m_coat", coat)
    dbg = os.environ.get("MASK_DEBUG")
    if dbg:
        em = g.n("ShaderNodeEmission")
        if dbg == "m_base":
            g._setc(em.inputs["Color"], base)
        elif dbg in _DBG:
            g._in(em.inputs["Strength"], 1.0)
            cmb = g.n("ShaderNodeCombineXYZ")
            for i in range(3):
                g._in(cmb.inputs[i], _DBG[dbg])
            g.link(cmb.outputs[0], em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (0, 0, 0, 1)
        _DBG.clear()
        g.link(em.outputs[0], out.inputs["Surface"])
        return m
    _DBG.clear()
    g._setc(bsdf.inputs["Base Color"], base)
    bsdf.inputs["Specular IOR Level"].default_value = P.get("spec", 0.5)
    g._in(bsdf.inputs["Roughness"], rough)
    g._in(bsdf.inputs["Metallic"], metal)
    if coat is not None:
        g._in(bsdf.inputs["Coat Weight"], coat)
        bsdf.inputs["Coat Roughness"].default_value = 0.22
        bsdf.inputs["Coat IOR"].default_value = 1.47
    if "coat_const" in P:
        cw, cr = P["coat_const"]
        if coat is None:
            bsdf.inputs["Coat Weight"].default_value = cw
        bsdf.inputs["Coat Roughness"].default_value = cr
    bump = g.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = P.get("bump", 0.35)
    bump.inputs["Distance"].default_value = P.get("bump_d", 0.0002)
    g._in(bump.inputs["Height"], height)
    g.link(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if "coat_normal" not in P and coat is not None:
        g.link(bump.outputs["Normal"], bsdf.inputs["Coat Normal"])
    return m


# ---------------- особые фактуры ----------------

def knurl(x0_mm, x1_mm, pitch_mm=1.15, r_mm=20.0):
    """Ромбическая накатка на трубе вдоль X (ось через z=10 мм): две встречные винтовые серии рисок."""
    def f(g, obj, base, rough, height, metal):
        sep = g.n("ShaderNodeSeparateXYZ"); g.L.new(obj, sep.inputs[0])
        y = sep.outputs["X"]
        ang = g.math("ARCTAN2", g.math("SUBTRACT", sep.outputs["Z"], 0.010), sep.outputs["Y"])
        circ = g.math("MULTIPLY", ang, r_mm * 0.001)
        x = sep.outputs["X"]
        p = pitch_mm * 0.001
        k = math.tan(math.radians(30))
        u1 = g.math("DIVIDE", g.math("ADD", g.math("MULTIPLY", x, k), circ), p)
        u2 = g.math("DIVIDE", g.math("SUBTRACT", g.math("MULTIPLY", x, k), circ), p)
        def triw(u):
            fr = g.math("FRACT", u)
            return g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", fr, 2.0), 1.0))
        h = g.math("MINIMUM", triw(u1), triw(u2))
        zone = g.math("MULTIPLY", g.maprange(x, x0_mm * 0.001, x0_mm * 0.001 + 0.0015),
                      g.maprange(x, x1_mm * 0.001 - 0.0015, x1_mm * 0.001, 1.0, 0.0))
        h = g.math("MULTIPLY", g.maprange(h, 0.0, 0.65), zone)
        height = g.math("ADD", height, g.math("MULTIPLY", h, 2.2))
        # в лунках накатки чуть темнее и грязнее
        base = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, h), zone), base, (0.008, 0.008, 0.008))
        return base, rough, height, metal
    return f


def stipple(z_max_mm):
    """Шагрень цевья: мелкие поры (Voronoi) ниже рёбер."""
    def f(g, obj, base, rough, height, metal):
        vo = g.n("ShaderNodeTexVoronoi", feature="SMOOTH_F1")
        g.L.new(obj, vo.inputs["Vector"])
        vo.inputs["Scale"].default_value = 1400.0
        vo.inputs["Smoothness"].default_value = 0.6
        d = g.maprange(vo.outputs["Distance"], 0.05, 0.5)
        n2 = g.noise(obj, 600.0, 3.0, 0.5)
        sep = g.n("ShaderNodeSeparateXYZ"); g.L.new(obj, sep.inputs[0])
        zone = g.maprange(sep.outputs["Z"], z_max_mm * 0.001, z_max_mm * 0.001 - 0.002, 0.0, 1.0)
        hh = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", d, 0.8), g.math("MULTIPLY", n2, 0.4)), zone)
        height = g.math("ADD", height, g.math("MULTIPLY", hh, 1.2))
        rough = g.math("ADD", rough, g.math("MULTIPLY", zone, 0.06))
        return base, rough, height, metal
    return f


def wood():
    """Берёзовая фанера (клеёный приклад, CC0 Poly Haven «Plywood»): волокна вдоль приклада (X), красноватый лак."""
    alb = image(f"{TEX}/plywood/albedo.jpg", noncolor=False)
    arm = image(f"{TEX}/plywood/arm.jpg")

    def f(g, obj, base, rough, height, metal):
        v = g.scaled(obj, (1.7, 3.6, 3.6), rot=(0.0, 0.0, 0.0))
        col = g.tri(alb, v, 0.35)
        a = g.tri(arm, v, 0.35)
        sepa = g.n("ShaderNodeSeparateColor"); g.L.new(a, sepa.inputs[0])
        hsv = g.n("ShaderNodeHueSaturation")
        hsv.inputs["Hue"].default_value = 0.47
        hsv.inputs["Saturation"].default_value = 1.15
        hsv.inputs["Value"].default_value = 0.46
        # старение лака: крупные пятна потемнее
        age = g.maprange(g.noise(obj, 9.0, 3.0, 0.55), 0.35, 0.7)
        hsv2 = g.mix(age, hsv.outputs[0], (0.07, 0.028, 0.012), blend="MULTIPLY")
        g.L.new(col, hsv.inputs["Color"])
        base = hsv2
        rough = g.math("MULTIPLY_ADD", sepa.outputs["Green"], 0.35, 0.4)
        height = g.math("ADD", height, g.math("MULTIPLY", g.bw(col), 0.6))
        return base, rough, height, 0.0
    return f


# ---------------- набор материалов ----------------

def build_all(prints=None):
    prints = prints or {}
    sc = [mask("09_Царапины/Царапины_длинные_плотные_01.png"), mask("09_Царапины/Царапины_мелкие_01.png"),
          mask("09_Царапины/Царапины_перекрёстные_01.png")]
    dust = mask("03_Пыль_и_частицы/Пыль_плотная_с_частицами_01.png")
    grime = mask("04_Грязь_и_налёт/Грязь_зернистая_плотная_01.png")
    oil = mask("20_Масляные_плёнки_и_смазка/Масло_02_Разбитые_островки.png")
    scr_maps = [(sc[0], 10.0, (0.0, 0.0, 0.0)), (sc[1], 16.0, (0.4, 1.1, 0.2)), (sc[2], 7.0, (1.2, 0.3, 0.9))]
    M = {}
    # фосфатированная сталь (коробка, крышка, органы управления, прицелы): почти чёрная, матовая, лёгкий отлив
    M["Steel_black"] = layered("V8_Steel_Phosphate", {
        "base": (0.0075, 0.0075, 0.008), "base2": (0.012, 0.0115, 0.011), "rough": (0.62, 0.8), "metal": 0.75,
        "micro_scale": 3000.0, "micro_h": 0.12,
        "edge": {"r": 0.45, "lo": 0.03, "hi": 0.18, "col": (0.22, 0.215, 0.21), "rough": 0.3, "metal": 1.0,
                 "halo_col": (0.011, 0.011, 0.0115), "halo_r": 0.55, "k": 1.4, "brk_scale": 220.0},
        "scratch": {"maps": scr_maps, "col": (0.05, 0.05, 0.05), "rough": 0.42, "metal": 0.9, "k": 0.9},
        "grime": {"mask": grime, "dist": 3.5, "col": (0.045, 0.04, 0.034), "rough": 0.92, "dust": 0.25,
                  "dust_col": (0.17, 0.16, 0.145)},
        "oil": {"mask": oil, "k": 0.45}, "bump": 0.3,
    }, prints.get("Steel_black", ()))
    # голая сталь затвора и деталей внутри: темнее серого, в масле
    M["Steel_bare"] = layered("V8_Steel_Bare", {
        "base": (0.06, 0.06, 0.062), "base2": (0.045, 0.043, 0.04), "rough": (0.28, 0.42), "metal": 1.0,
        "edge": {"r": 0.35, "col": (0.42, 0.41, 0.40), "rough": 0.22, "k": 1.4},
        "scratch": {"maps": scr_maps, "col": (0.18, 0.18, 0.18), "rough": 0.25, "metal": 1.0, "k": 1.0},
        "grime": {"mask": grime, "dist": 3.0, "col": (0.012, 0.011, 0.01), "rough": 0.6, "dust": 0.05},
        "oil": {"mask": oil, "k": 0.9}, "bump": 0.25,
    }, prints.get("Steel_bare", ()))
    M["Spring_steel"] = M["Steel_bare"]
    # чернёный анодированный алюминий муфты: кромки рельсов светлые
    M["Alu_anodized"] = layered("V8_Alu_Anodized", {
        "base": (0.009, 0.009, 0.0095), "base2": (0.012, 0.012, 0.013), "rough": (0.42, 0.56), "metal": 0.55,
        "edge": {"r": 0.45, "lo": 0.03, "hi": 0.16, "col": (0.42, 0.42, 0.43), "rough": 0.3, "metal": 1.0,
                 "halo_col": (0.013, 0.013, 0.014), "k": 1.6, "brk_scale": 260.0},
        "scratch": {"maps": scr_maps, "col": (0.2, 0.2, 0.21), "rough": 0.35, "metal": 1.0, "k": 0.7},
        "grime": {"mask": grime, "dist": 4.0, "col": (0.05, 0.045, 0.04), "rough": 0.9, "dust": 0.3,
                  "dust_col": (0.17, 0.16, 0.145)},
        "oil": {"mask": oil, "k": 0.3}, "bump": 0.25,
    }, prints.get("Alu_anodized", ()))
    # глушитель: та же фосфатированная сталь + ромбическая накатка
    M["Suppressor"] = layered("V8_Suppressor", {
        "base": (0.0085, 0.0085, 0.009), "base2": (0.013, 0.0125, 0.012), "rough": (0.6, 0.78), "metal": 0.72,
        "special": knurl(700.0, 851.0),
        "edge": {"r": 0.45, "col": (0.2, 0.195, 0.19), "rough": 0.32, "k": 1.1, "halo_col": (0.011, 0.011, 0.0115)},
        "scratch": {"maps": scr_maps, "col": (0.05, 0.05, 0.05), "rough": 0.45, "k": 1.0},
        "grime": {"mask": grime, "dist": 3.0, "col": (0.04, 0.036, 0.03), "rough": 0.92, "dust": 0.3,
                  "dust_col": (0.17, 0.16, 0.145)},
        "oil": {"mask": oil, "k": 0.2}, "bump": 0.45, "bump_d": 0.00025,
    }, prints.get("Suppressor", ()))
    # полимер цевья: тёмно-коричневый, шагрень по бокам, потёртости светлее и шершавее
    M["Polymer_handguard"] = layered("V8_Polymer_Handguard", {
        "base": (0.0105, 0.0098, 0.009), "base2": (0.0135, 0.0125, 0.0115), "rough": (0.74, 0.88), "metal": 0.0, "spec": 0.28,
        "print_k": 0.55,
        "micro_scale": 1800.0, "micro_h": 0.2, "special": stipple(37.0),
        "edge": {"r": 0.8, "lo": 0.03, "hi": 0.22, "col": (0.05, 0.042, 0.036), "rough": 0.8, "metal": 0.0, "k": 1.0,
                 "halo_col": (0.02, 0.015, 0.012), "halo_r": 0.8},
        "scratch": {"maps": scr_maps, "col": (0.06, 0.05, 0.043), "rough": 0.75, "metal": 0.0, "k": 0.6},
        "grime": {"mask": grime, "dist": 3.0, "col": (0.075, 0.068, 0.058), "rough": 0.95, "dust": 0.35,
                  "dust_col": (0.2, 0.185, 0.165)},
        "bump": 0.4, "print_col": (0.03, 0.028, 0.026),
    }, prints.get("Polymer_handguard", ()))
    # полимер магазина: почти чёрный, мелкая литьевая фактура
    M["Polymer_magazine"] = layered("V8_Polymer_Magazine", {
        "base": (0.008, 0.0078, 0.0075), "base2": (0.011, 0.0107, 0.0104), "rough": (0.66, 0.8), "metal": 0.0, "spec": 0.3,
        "micro_scale": 2200.0, "micro_h": 0.25,
        "edge": {"r": 0.7, "col": (0.045, 0.044, 0.042), "rough": 0.78, "metal": 0.0, "k": 1.0,
                 "halo_col": (0.011, 0.0105, 0.01)},
        "scratch": {"maps": scr_maps, "col": (0.06, 0.058, 0.055), "rough": 0.72, "metal": 0.0, "k": 0.9},
        "grime": {"mask": grime, "dist": 3.0, "col": (0.08, 0.072, 0.062), "rough": 0.95, "dust": 0.3,
                  "dust_col": (0.2, 0.185, 0.165)},
        "bump": 0.35, "print_col": (0.045, 0.043, 0.04),
    }, prints.get("Polymer_magazine", ()))
    # дерево приклада: шпон под лаком, лак протёрт на кромках
    M["Wood_stock"] = layered("V8_Wood_Stock", {
        "base": (0.2, 0.08, 0.04), "rough": (0.35, 0.5), "metal": 0.0, "special": wood(), "micro_h": 0.05,
        "edge": {"r": 1.2, "lo": 0.02, "hi": 0.22, "col": (0.42, 0.25, 0.14), "rough": 0.7, "metal": 0.0, "k": 1.3,
                 "halo_col": (0.16, 0.07, 0.035), "halo_r": 0.55},
        "scratch": {"maps": scr_maps, "col": (0.3, 0.17, 0.09), "rough": 0.6, "metal": 0.0, "k": 0.8},
        "grime": {"mask": grime, "dist": 4.0, "col": (0.05, 0.03, 0.02), "rough": 0.8, "dust": 0.25,
                  "dust_col": (0.25, 0.2, 0.16)},
        "coat_const": (0.3, 0.3), "bump": 0.25, "print_col": (0.1, 0.05, 0.03),
    }, prints.get("Wood_stock", ()))
    M["Rubber"] = layered("V8_Rubber", {
        "base": (0.012, 0.012, 0.012), "rough": (0.78, 0.9), "metal": 0.0, "micro_scale": 1500.0, "micro_h": 0.3,
        "edge": {"r": 0.8, "col": (0.04, 0.04, 0.04), "rough": 0.9, "metal": 0.0, "k": 0.8},
        "grime": {"mask": dust, "dist": 4.0, "col": (0.12, 0.11, 0.1), "rough": 0.95, "dust": 0.4,
                  "dust_col": (0.2, 0.19, 0.17)},
        "bump": 0.4,
    })
    # патрон: гильза — лакированная сталь, оболочка пули — томпак, капсюль с красным лаком
    M["Case_steel_lacquer"] = layered("V8_Case", {
        "base": (0.09, 0.085, 0.045), "base2": (0.075, 0.07, 0.036), "rough": (0.32, 0.45), "metal": 0.7,
        "micro_scale": 4000.0, "micro_h": 0.05,
        "edge": {"r": 0.25, "col": (0.45, 0.43, 0.4), "rough": 0.25, "k": 0.9},
        "grime": {"mask": grime, "dist": 2.0, "col": (0.05, 0.045, 0.03), "rough": 0.7, "dust": 0.1},
        "bump": 0.15,
    })
    M["Bullet_jacket"] = layered("V8_Jacket", {
        "base": (0.62, 0.32, 0.19), "base2": (0.55, 0.28, 0.17), "rough": (0.22, 0.34), "metal": 1.0,
        "micro_scale": 4000.0, "micro_h": 0.05,
        "grime": {"mask": grime, "dist": 2.0, "col": (0.18, 0.1, 0.06), "rough": 0.5, "dust": 0.05},
        "bump": 0.12,
    })
    M["Alu_bare"] = layered("V8_Alu_Machined", {
        "base": (0.42, 0.42, 0.43), "base2": (0.36, 0.36, 0.37), "rough": (0.28, 0.4), "metal": 1.0,
        "scratch": {"maps": scr_maps, "col": (0.6, 0.6, 0.61), "rough": 0.2, "metal": 1.0, "k": 0.8},
        "grime": {"mask": grime, "dist": 2.0, "col": (0.05, 0.045, 0.04), "rough": 0.8, "dust": 0.1},
        "bump": 0.2,
    })
    M["Engraving_fill"] = layered("V8_Engraving_Fill", {
        "base": (0.55, 0.53, 0.48), "base2": (0.4, 0.38, 0.34), "rough": (0.6, 0.8), "metal": 0.0,
        "grime": {"mask": grime, "dist": 1.0, "col": (0.1, 0.09, 0.08), "rough": 0.9, "dust": 0.1},
    })
    M["Inner_black"] = layered("V8_Inner_Black", {"base": (0.006, 0.006, 0.006), "rough": (0.85, 0.95), "metal": 0.0})
    g = bpy.data.materials.get("V8_Glass_Coated") or bpy.data.materials.new("V8_Glass_Coated")
    g.use_nodes = True
    b = g.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.85, 0.9, 0.88, 1.0)
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.52
    if "Thin Film Thickness" in b.inputs:
        # просветление оптики — тонкая плёнка: в бликах линз зелёно-фиолетовые переливы, как у настоящих прицелов
        b.inputs["Coat Weight"].default_value = 0.0
        b.inputs["Thin Film Thickness"].default_value = 420.0
        b.inputs["Thin Film IOR"].default_value = 1.38
    else:
        b.inputs["Coat Weight"].default_value = 0.6
        b.inputs["Coat Tint"].default_value = (0.75, 0.6, 1.0, 1.0)
    M["Glass"] = g
    return M


def assign(M, defaults=None):
    """Замена нейтральных материалов геометрии на слоистые; глушитель — свой материал; свойства слоёв."""
    defaults = defaults or {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        for k, v in {"wear": 1.0, "dust": 1.0, "grime": 1.0, "oil": 1.0}.items():
            if k not in o.keys():
                o[k] = defaults.get(o.name, {}).get(k, v)
        for s in o.material_slots:
            if s.material is None:
                continue
            nm = s.material.name.split(".")[0]
            if o.name.startswith("Suppressor_body") and nm == "Steel_black":
                s.material = M["Suppressor"]
            elif nm in M and M[nm] is not None:
                s.material = M[nm]
