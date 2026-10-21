"""Материалы NPC для просмотра в Blender (Cycles): фото CC0 + износ по маскам вещи (wear.py).

Принцип — как у вещей в Тарков и Deadside: тёмная «отделка» вещи стирается до светлой основы там, где
вещь трут (края, гребни складок, локти, колени, сиденье, швы), во впадинах и у карманов копится грязь,
верх выгорает и пылится, низ — в грязи. Маски берутся из геометрии (атрибуты вершин), разбиваются
фотошумом (пятна бетона, сухая грязь) — поэтому износ не выглядит «по трафарету».
Цвет вещи — параметры функций (тона, оттенок); те же маски потом запекаются в атласы для игры.
"""
from __future__ import annotations

from pathlib import Path

import bpy

import kit_common as kc

TEX = kc.WORK / "tex"
MPFB_USER = Path(bpy.utils.resource_path("USER")) / "extensions" / ".user" / "blender_org" / "mpfb" / "data"


# ---------- узлы ----------

def is_link(v) -> bool:
    """(узел, выход) — связь; кортеж чисел — цвет."""
    return isinstance(v, tuple) and len(v) == 2 and hasattr(v[0], "outputs")


class NodeBuilder:
    def __init__(self, mat: bpy.types.Material):
        mat.use_nodes = True
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.output = self.node("ShaderNodeOutputMaterial", 1400, 0)
        self.bsdf = self.node("ShaderNodeBsdfPrincipled", 1100, 0)
        self.link(self.bsdf, "BSDF", self.output, "Surface")

    def node(self, kind: str, x: float = 0, y: float = 0) -> bpy.types.Node:
        n = self.nt.nodes.new(kind)
        n.location = (x, y)
        return n

    def link(self, a, a_out, b, b_in) -> None:
        # У узла смешивания три выхода «Result» (число, вектор, цвет): цветной — третий, числовой — первый.
        if a.bl_idname == "ShaderNodeMix" and a_out == "Result":
            a_out = 2 if a.data_type == "RGBA" else 0
        self.nt.links.new(a.outputs[a_out], b.inputs[b_in])

    def feed(self, v, node, sock) -> None:
        if is_link(v):
            self.link(v[0], v[1], node, sock)
        elif isinstance(v, (tuple, list)):
            node.inputs[sock].default_value = (*v, 1.0) if len(v) == 3 else v
        else:
            node.inputs[sock].default_value = v

    def math(self, op: str, a=None, b=None, clamp: bool = False, x=0, y=0) -> tuple:
        n = self.node("ShaderNodeMath", x, y)
        n.operation = op
        n.use_clamp = clamp
        for k, v in enumerate((a, b)):
            if v is not None:
                self.feed(v, n, k)
        return (n, 0)

    def add(self, *terms, clamp: bool = True) -> tuple:
        """Сумма масок с весами: add((маска, вес), …) → 0…1."""
        acc = None
        for src, w in terms:
            t = self.math("MULTIPLY", src, w)
            acc = t if acc is None else self.math("ADD", acc, t)
        return self.math("MULTIPLY", acc, 1.0, clamp=clamp)

    def mix(self, fac, a, b, blend: str = "MIX", x=0, y=0) -> tuple:
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = "RGBA"
        n.blend_type = blend
        n.clamp_factor = True
        self.feed(fac, n, 0)
        self.feed(a, n, 6)
        self.feed(b, n, 7)
        return (n, 2)

    def mixf(self, fac, a, b) -> tuple:
        n = self.node("ShaderNodeMix")
        n.data_type = "FLOAT"
        n.clamp_factor = True
        self.feed(fac, n, 0)
        self.feed(a, n, 2)
        self.feed(b, n, 3)
        return (n, 0)

    def ramp(self, src, stops: list[tuple[float, tuple]], interp: str = "LINEAR", x=0, y=0) -> tuple:
        n = self.node("ShaderNodeValToRGB", x, y)
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > len(stops):
            cr.elements.remove(cr.elements[-1])
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for e, (pos, col) in zip(cr.elements, stops):
            e.position = pos
            e.color = (*col, 1.0) if len(col) == 3 else col
        self.link(src[0], src[1], n, "Fac")
        return (n, "Color")

    def remap(self, src, lo: float, hi: float, to_lo: float = 0.0, to_hi: float = 1.0) -> tuple:
        n = self.node("ShaderNodeMapRange")
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        n.inputs["To Min"].default_value = to_lo
        n.inputs["To Max"].default_value = to_hi
        n.clamp = True
        self.feed(src, n, "Value")
        return (n, "Result")

    def gray(self, v) -> tuple:
        """Число → серый цвет (для умножения цвета на число)."""
        n = self.node("ShaderNodeCombineColor")
        for k in range(3):
            self.feed(v, n, k)
        return (n, "Color")

    def bw(self, col) -> tuple:
        n = self.node("ShaderNodeRGBToBW")
        self.feed(col, n, "Color")
        return (n, "Val")

    def hsv(self, col, hue: float = 0.5, sat: float = 1.0, val: float = 1.0) -> tuple:
        n = self.node("ShaderNodeHueSaturation")
        n.inputs["Hue"].default_value = hue
        n.inputs["Saturation"].default_value = sat
        n.inputs["Value"].default_value = val
        self.feed(col, n, "Color")
        return (n, "Color")

    def attr(self, name: str) -> tuple:
        n = self.node("ShaderNodeAttribute")
        n.attribute_type = "GEOMETRY"
        n.attribute_name = name
        return (n, "Fac")

    def ridge(self, name: str = "fold") -> tuple:
        """Гребень складки 0…1 из атрибута fold (> 0)."""
        return self.math("MAXIMUM", self.attr(name), 0.0)

    def valley(self, name: str = "fold") -> tuple:
        return self.math("MAXIMUM", self.math("MULTIPLY", self.attr(name), -1.0), 0.0)

    def ao(self, dist: float) -> tuple:
        n = self.node("ShaderNodeAmbientOcclusion")
        n.inputs["Distance"].default_value = dist
        n.samples = 8
        return (n, "AO")

    def occlusion(self, dist: float) -> tuple:
        """1 — в глубине (под складкой, у шва), 0 — открыто."""
        return self.math("SUBTRACT", 1.0, self.ao(dist), clamp=True)

    def noise(self, vec, scale: float, detail: float = 4.0, rough: float = 0.55, out: str = "Fac") -> tuple:
        n = self.node("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        if vec:
            self.feed(vec, n, "Vector")
        return (n, out)

    def image(self, path: Path, non_color: bool, vector, box: bool = False) -> bpy.types.Node:
        n = self.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(path), check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        if box:
            n.projection = "BOX"
            n.projection_blend = 0.35
        self.feed(vector, n, "Vector")
        return n

    def normal_map(self, col, strength: float) -> tuple:
        n = self.node("ShaderNodeNormalMap")
        n.inputs["Strength"].default_value = strength
        self.feed(col, n, "Color")
        return (n, "Normal")

    def bump(self, height, strength: float, distance: float, normal=None) -> tuple:
        n = self.node("ShaderNodeBump")
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = distance
        self.feed(height, n, "Height")
        if normal is not None:
            self.feed(normal, n, "Normal")
        return (n, "Normal")

    def world_z(self, z_top: float, z_bottom: float) -> tuple:
        """1 — у пола (пыль, грязь), 0 — выше z_top."""
        g = self.node("ShaderNodeNewGeometry")
        sep = self.node("ShaderNodeSeparateXYZ")
        self.link(g, "Position", sep, "Vector")
        return self.remap((sep, "Z"), z_top, z_bottom)

    def out(self, base, rough, normal=None, **inputs) -> None:
        self.feed(base, self.bsdf, "Base Color")
        self.feed(rough, self.bsdf, "Roughness")
        if normal is not None:
            self.feed(normal, self.bsdf, "Normal")
        for k, v in inputs.items():
            self.bsdf.inputs[k.replace("_", " ")].default_value = v


def coords(nb: NodeBuilder, uv_name: str | None, size: tuple[float, float], rot: float = 0.0,
           loc: tuple[float, float] = (0.0, 0.0)) -> tuple:
    """Координаты в метрах → повтор плитки реального размера size (м). uv_name None — объект."""
    if uv_name:
        src = nb.node("ShaderNodeUVMap")
        src.uv_map = uv_name
        sock = (src, "UV")
    else:
        src = nb.node("ShaderNodeTexCoord")
        sock = (src, "Object")
    mp = nb.node("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / size[0], 1.0 / size[1], 1.0 / size[0])
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    mp.inputs["Location"].default_value = (loc[0], loc[1], 0)
    nb.link(src, sock[1], mp, "Vector")
    return (mp, "Vector")


def tex_files(folder: str) -> dict[str, Path]:
    d = TEX / folder
    out = {}
    for f in d.iterdir():
        for key in ("diff", "nor_gl", "rough", "ao", "disp"):
            if f"_{key}_" in f.name:
                out[key] = f
    return out


def photo(nb: NodeBuilder, folder: str, uv_name: str | None, size: tuple[float, float], box: bool = False,
          maps: tuple[str, ...] = ("diff", "nor_gl", "rough")) -> dict[str, tuple]:
    """Фотонабор двумя слоями со сдвигом и поворотом, смешанными пятнами шума: повтор плитки не читается."""
    files = tex_files(folder)
    va = coords(nb, uv_name, size)
    vb = coords(nb, uv_name, (size[0] * 0.93, size[1] * 0.93), rot=0.65, loc=(0.37, 0.61))
    mask = nb.remap(nb.noise(coords(nb, uv_name, (size[0] * 2.5, size[1] * 2.5)), 1.0, 3.0, 0.5), 0.44, 0.56)
    out = {}
    for key in maps:
        if key not in files:
            continue
        nc = key != "diff"
        a = nb.image(files[key], nc, va, box)
        b = nb.image(files[key], nc, vb, box)
        out[key] = nb.mix(mask, (a, "Color"), (b, "Color"))
    return out


def grunge(nb: NodeBuilder, uv_name: str | None, size: float, lo: float = 0.35, hi: float = 0.65) -> tuple:
    """Пятна износа: фото бетона в пятнах (CC0), по яркости — 0…1."""
    files = tex_files("brushed_concrete_2")
    img = nb.image(files["diff"], False, coords(nb, uv_name, (size, size), rot=0.3), box=uv_name is None)
    return nb.remap(nb.bw((img, "Color")), lo, hi)


# ---------- материалы ----------

def mat_leather_jacket(mat: bpy.types.Material, dye: tuple[float, float, float] = (0.515, 0.92, 0.26)) -> None:
    """Куртка из поношенной кожи. dye — (оттенок, насыщенность, яркость) отделки поверх фото."""
    nb = NodeBuilder(mat)
    uv = "UV_Pattern"
    ph = photo(nb, "fabric_leather_01_clean", uv, (0.31, 0.40), maps=("diff", "nor_gl", "rough", "disp"))
    dyed = nb.hsv(ph["diff"], *dye)
    exposed = nb.hsv(ph["diff"], 0.51, 0.85, 0.62)
    g1 = grunge(nb, uv, 0.9)
    g2 = grunge(nb, uv, 0.35, 0.3, 0.7)
    # Стёртая отделка: края, швы, локти, гребни складок, сборки; пятнами.
    wear = nb.add((nb.attr("edge"), 0.7), (nb.attr("seam"), 0.35), (nb.attr("joint"), 0.5),
                  (nb.ridge(), 0.45), (nb.attr("cmp"), 1.0), (nb.attr("sun"), 0.1))
    wear_m = nb.remap(nb.math("MULTIPLY", wear, nb.math("ADD", g1, 0.35)), 0.40, 0.95)
    base = nb.mix(wear_m, dyed, exposed)
    # Грязь во впадинах, у швов, у карманов и на манжетах.
    grime = nb.add((nb.valley(), 0.9), (nb.occlusion(0.05), 1.2), (nb.attr("seam"), 0.25),
                   (nb.attr("touch"), 0.45), (nb.attr("edge"), 0.2))
    grime_m = nb.math("MULTIPLY", grime, nb.math("ADD", nb.math("MULTIPLY", g2, 0.5), 0.55), clamp=True)
    dirty = nb.mix(nb.math("MULTIPLY", grime_m, 0.75), base, (0.016, 0.012, 0.010))
    dust_m = nb.math("MULTIPLY", nb.attr("sun"), nb.math("MULTIPLY", g2, 0.35), clamp=True)
    final = nb.mix(dust_m, dirty, (0.20, 0.17, 0.14))
    rough = nb.remap(ph["rough"], 0.0, 1.0, 0.52, 0.66)
    rough = nb.math("ADD", rough, nb.math("MULTIPLY", wear_m, 0.18))
    rough = nb.math("ADD", rough, nb.math("MULTIPLY", nb.math("MAXIMUM", grime_m, dust_m), 0.18), clamp=True)
    # Заломы кожи (рельеф leather_red_02) — где кожа сжата: локти, сборка у резинки, под мышками.
    crease_files = tex_files("leather_red_02")
    cr = nb.image(crease_files["nor_gl"], True, coords(nb, uv, (0.42, 0.42), rot=1.1))
    cr_m = nb.math("MULTIPLY", nb.add((nb.attr("cmp"), 3.5), (nb.attr("joint"), 0.7)), nb.math("ADD", g2, 0.3), clamp=True)
    nor = nb.mix(cr_m, ph["nor_gl"], (cr, "Color"))
    # Мелкое зерно и поры кожи — картой высоты того же фото поверх нормали.
    normal = nb.bump(nb.bw(ph["disp"]), 0.3, 0.0008, nb.normal_map(nor, 1.25))
    nb.out(final, rough, normal, Specular_IOR_Level=0.38)


def mat_rib(mat: bpy.types.Material, tone: tuple[float, float, float] = (0.011, 0.010, 0.009)) -> None:
    """Трикотаж-рубчик (воротник, манжеты, пояс): рубчик волной, петли — фото вязки, ворс и катышки."""
    nb = NodeBuilder(mat)
    uv = "UV_Pattern"
    wave = nb.node("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 78.0           # рубчик ~4 мм
    wave.inputs["Distortion"].default_value = 0.4
    nb.feed(coords(nb, uv, (1.0, 1.0)), wave, "Vector")
    knit = photo(nb, "knitted_fleece", uv, (0.12, 0.12), maps=("diff", "nor_gl"))
    lint = nb.noise(coords(nb, uv, (1.0, 1.0)), 700.0, 2.0, 0.5)
    pill = nb.remap(nb.noise(coords(nb, uv, (1.0, 1.0)), 260.0, 1.0, 0.5), 0.62, 0.70)
    wear = nb.add((nb.attr("edge"), 0.7), (nb.ridge(), 0.5))
    lum = nb.math("ADD", nb.math("MULTIPLY", (wave, "Fac"), 0.6), nb.math("MULTIPLY", nb.bw(knit["diff"]), 0.8))
    c = nb.mix(lum, tone, tuple(t * 2.6 for t in tone))
    c = nb.mix(nb.math("MULTIPLY", pill, wear, clamp=True), c, (0.06, 0.055, 0.05))
    c = nb.mix(nb.math("MULTIPLY", nb.occlusion(0.03), 0.8), c, (0.004, 0.0035, 0.003))
    h = nb.math("ADD", (wave, "Fac"), nb.math("MULTIPLY", lint, 0.3))
    normal = nb.bump(h, 0.55, 0.0015, nb.normal_map(knit["nor_gl"], 0.8))
    nb.out(c, 0.93, normal, Sheen_Weight=0.35, Sheen_Roughness=0.45)


def mat_camo(mat: bpy.types.Material,
             palette: tuple = ((0.078, 0.074, 0.043), (0.040, 0.050, 0.022), (0.050, 0.034, 0.019),
                               (0.014, 0.014, 0.010), (0.13, 0.12, 0.075)), stitch: bool = False) -> None:
    """Свой лесной камуфляж «Лесополоса»: хаки, оливковые и бурые пятна, тёмные «ветки», светлые
    крапины; рисунок напечатан на ткани — по лекалам (на швах не совпадает, как у настоящих брюк).
    Поверх — саржа, выгорание на коленях и сиденье, грязь книзу, жирные пятна на бёдрах."""
    nb = NodeBuilder(mat)
    uv = "UV_Pattern"
    base_v = coords(nb, uv, (1.0, 2.2))             # пятна вытянуты по долевой нити
    warp = nb.node("ShaderNodeVectorMath")
    warp.operation = "MULTIPLY_ADD"
    wn = nb.noise(base_v, 2.2, 2.0, 0.5, out="Color")
    nb.feed(wn, warp, 0)
    warp.inputs[1].default_value = (0.22, 0.22, 0.22)
    nb.feed(base_v, warp, 2)
    wv = (warp, "Vector")
    c = palette[0]
    for k, (scale, thr, detail) in enumerate(((4.0, 0.50, 4.0), (7.0, 0.56, 5.0), (11.0, 0.60, 5.0), (18.0, 0.68, 3.0))):
        sh = nb.node("ShaderNodeVectorMath")
        sh.operation = "ADD"
        nb.feed(wv, sh, 0)
        sh.inputs[1].default_value = (3.1 * (k + 1), 7.3 * (k + 1), 1.7 * k)
        n = nb.noise((sh, "Vector"), scale, detail, 0.6)
        m = nb.remap(n, thr - 0.006, thr + 0.006)
        c = nb.mix(m, c, palette[k + 1])
    # Саржа: плетение темнит и светлит нить.
    tw = photo(nb, "denim_fabric_05", uv, (0.27, 0.27))
    weave = nb.remap(nb.bw(tw["diff"]), 0.02, 0.35, 0.80, 1.15)
    woven = nb.mix(1.0, c, nb.gray(weave), "MULTIPLY")
    g1 = grunge(nb, uv, 0.8)
    g2 = grunge(nb, uv, 0.3, 0.3, 0.7)
    # Выгорание и потёртость: колени, сиденье, бёдра спереди, гребни складок, края, верх.
    fade = nb.add((nb.attr("joint"), 0.9), (nb.attr("seat"), 0.8), (nb.attr("touch"), 0.35),
                  (nb.ridge(), 0.55), (nb.attr("edge"), 0.35), (nb.attr("sun"), 0.25), (nb.attr("seam"), 0.3))
    fade_m = nb.remap(nb.math("MULTIPLY", fade, nb.math("ADD", g1, 0.4)), 0.30, 0.95)
    faded = nb.hsv(woven, 0.5, 0.70, 1.30)
    col = nb.mix(nb.math("ADD", nb.math("MULTIPLY", fade_m, 0.4), 0.02), woven, faded)
    grime = nb.add((nb.valley(), 0.8), (nb.occlusion(0.05), 1.1), (nb.attr("seam"), 0.2))
    col = nb.mix(nb.math("MULTIPLY", grime, 0.65), col, (0.02, 0.018, 0.014))
    # Жирные пятна на бёдрах (руки вытирают).
    grease = nb.math("MULTIPLY", nb.attr("touch"), nb.remap(g2, 0.55, 0.75), clamp=True)
    col = nb.mix(nb.math("MULTIPLY", grease, 0.7), col, nb.hsv(col, 0.5, 0.9, 0.45))
    # Грязь книзу: сплошная у берцев, выше брызгами.
    mud_files = tex_files("brown_mud_dry")
    mud_c = nb.image(mud_files["diff"], False, coords(nb, None, (0.6, 0.6)), box=True)
    low = nb.world_z(0.42, 0.24)
    splash = nb.remap(nb.noise(coords(nb, None, (1.0, 1.0)), 38.0, 2.0, 0.5), 0.60, 0.64)
    mud_m = nb.add((nb.math("MULTIPLY", low, nb.remap(g1, 0.2, 0.7)), 1.2),
                   (nb.math("MULTIPLY", nb.world_z(0.62, 0.30), splash), 0.9))
    col = nb.mix(mud_m, col, nb.hsv((mud_c, "Color"), 0.5, 0.75, 0.50))
    dust = nb.math("MULTIPLY", nb.world_z(0.55, 0.2), nb.math("MULTIPLY", g2, 0.25), clamp=True)
    col = nb.mix(dust, col, (0.16, 0.14, 0.11))
    rough = nb.remap(tw["rough"], 0.0, 1.0, 0.80, 0.93)
    rough = nb.mixf(grease, rough, 0.62)
    rough = nb.mixf(mud_m, rough, 0.96)
    normal = nb.normal_map(tw["nor_gl"], 0.75)
    if stitch:
        # Строчка нашивной детали в 4 мм от края (атрибут bd — расстояние до края по ткани), пунктир 3,2 мм.
        line = nb.remap(nb.math("ABSOLUTE", nb.math("SUBTRACT", nb.attr("bd"), 0.004)), 0.0009, 0.0004)
        uvn = nb.node("ShaderNodeUVMap")
        uvn.uv_map = uv
        sep = nb.node("ShaderNodeSeparateXYZ")
        nb.link(uvn, "UV", sep, "Vector")
        phase = nb.math("MULTIPLY", nb.math("ADD", (sep, "X"), (sep, "Y")), 2 * 3.14159265 / 0.0032)
        dash = nb.remap(nb.math("SINE", phase), -0.15, 0.25)
        thread = nb.math("MULTIPLY", line, dash, clamp=True)
        col = nb.mix(thread, col, (0.15, 0.14, 0.095))
        normal = nb.bump(nb.math("SUBTRACT", thread, nb.math("MULTIPLY", line, 0.4)), 0.6, 0.0008, normal)
    nb.out(col, rough, normal, Sheen_Weight=0.3, Sheen_Roughness=0.5)


def mat_boot_leather(mat: bpy.types.Material, dye: tuple[float, float, float] = (0.48, 0.80, 0.24)) -> None:
    """Берцы: промасленная кожа (CC0), сбитый носок и сгиб союзки светлее, заломы на сгибе, грязь снизу."""
    nb = NodeBuilder(mat)
    ph = photo(nb, "fabric_leather_02_clean", None, (0.217, 0.50), box=True)
    dyed = nb.hsv(ph["diff"], *dye)
    exposed = nb.hsv(ph["diff"], 0.5, 0.7, 0.60)
    g1 = grunge(nb, None, 0.25)
    scuff = nb.add((nb.attr("toe"), 1.1), (nb.ridge(), 0.6), (nb.attr("flex"), 0.5))
    scuff_m = nb.remap(nb.math("MULTIPLY", scuff, nb.math("ADD", g1, 0.3)), 0.3, 0.8)
    col = nb.mix(scuff_m, dyed, exposed)
    col = nb.mix(nb.math("MULTIPLY", nb.add((nb.valley(), 0.8), (nb.occlusion(0.02), 1.2)), 0.7), col, (0.012, 0.009, 0.007))
    mud = photo(nb, "brown_mud_dry", None, (0.5, 0.5), box=True)
    low = nb.math("MULTIPLY", nb.world_z(0.085, 0.03), nb.remap(g1, 0.15, 0.6))
    mud_m = nb.add((low, 1.4), (nb.math("MULTIPLY", nb.occlusion(0.015), nb.world_z(0.16, 0.06)), 0.6))
    col = nb.mix(mud_m, col, nb.hsv(mud["diff"], 0.5, 0.8, 0.8))
    dust = nb.math("MULTIPLY", nb.world_z(0.24, 0.08), 0.35)
    col = nb.mix(nb.math("MULTIPLY", dust, g1), col, (0.20, 0.17, 0.13))
    rough = nb.remap(ph["rough"], 0.0, 1.0, 0.58, 0.74)
    rough = nb.math("ADD", rough, nb.math("MULTIPLY", scuff_m, 0.15))
    rough = nb.mixf(mud_m, rough, 0.95)
    crease = tex_files("leather_red_02")
    cr = nb.image(crease["nor_gl"], True, coords(nb, None, (0.22, 0.22)), box=True)
    nor = nb.mix(nb.math("ADD", nb.math("MULTIPLY", nb.attr("flex"), 1.3), 0.45, clamp=True), ph["nor_gl"], (cr, "Color"))
    nor = nb.mix(mud_m, nor, mud["nor_gl"])
    nb.out(col, rough, nb.normal_map(nor, 1.9), Specular_IOR_Level=0.4)


def mat_rubber(mat: bpy.types.Material, honeycomb: bool) -> None:
    """Резина ранта и подошвы: сотовый рисунок ранта, грязь в протекторе и снизу."""
    nb = NodeBuilder(mat)
    vec = coords(nb, None, (1.0, 1.0))
    normal = None
    if honeycomb:
        vor = nb.node("ShaderNodeTexVoronoi")
        vor.feature = "DISTANCE_TO_EDGE"
        vor.inputs["Scale"].default_value = 260.0
        vor.inputs["Randomness"].default_value = 0.05
        nb.feed(vec, vor, "Vector")
        normal = nb.bump((vor, "Distance"), 0.8, 0.0008)
    g1 = grunge(nb, None, 0.3)
    mud = photo(nb, "brown_mud_dry", None, (0.4, 0.4), box=True, maps=("diff",))
    mud_m = nb.add((nb.math("MULTIPLY", nb.occlusion(0.012), 1.4), 1.0),
                   (nb.math("MULTIPLY", nb.world_z(0.03, -0.01), g1), 0.8))
    col = nb.mix(mud_m, (0.016, 0.0155, 0.015), nb.hsv(mud["diff"], 0.5, 0.75, 0.5))
    col = nb.mix(nb.math("MULTIPLY", g1, 0.15), col, (0.09, 0.08, 0.065))
    rough = nb.mixf(mud_m, 0.74, 0.95)
    nb.out(col, rough, normal)


def mat_simple(mat: bpy.types.Material, color, rough: float, metal: float = 0.0, bump_scale: float = 0.0,
               grid: bool = False) -> None:
    nb = NodeBuilder(mat)
    nb.bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    nb.bsdf.inputs["Roughness"].default_value = rough
    nb.bsdf.inputs["Metallic"].default_value = metal
    if bump_scale or grid:
        vec = coords(nb, None, (1.0, 1.0))
        if grid:
            wx = nb.node("ShaderNodeTexWave")
            wx.bands_direction = "X"
            wx.inputs["Scale"].default_value = 200.0
            wy = nb.node("ShaderNodeTexWave")
            wy.bands_direction = "Z"
            wy.inputs["Scale"].default_value = 200.0
            for w in (wx, wy):
                nb.feed(vec, w, "Vector")
            h = nb.math("MULTIPLY", (wx, "Fac"), (wy, "Fac"))
        else:
            h = nb.noise(vec, bump_scale, 3.0, 0.5)
        nb.link(*nb.bump(h, 0.5, 0.001), nb.bsdf, "Normal")


def mat_knit(mat: bpy.types.Material, tone: tuple[float, float, float] = (0.013, 0.014, 0.011)) -> None:
    """Балаклава: мелкая вязка (CC0 knitted_fleece), ворс и катышки, у рта — влажное от дыхания."""
    nb = NodeBuilder(mat)
    knit = photo(nb, "knitted_fleece", None, (0.10, 0.10), box=True, maps=("diff", "nor_gl", "rough"))
    lum = nb.remap(nb.bw(knit["diff"]), 0.05, 0.35)
    # Рубчик 1×1: столбики петель идут вдоль головы сверху вниз — фаза по углу вокруг оси головы.
    tc = nb.node("ShaderNodeTexCoord")
    sep = nb.node("ShaderNodeSeparateXYZ")
    nb.link(tc, "Object", sep, "Vector")
    ang = nb.math("ARCTAN2", (sep, "X"), nb.math("ADD", (sep, "Y"), 0.02))
    rib = nb.remap(nb.math("SINE", nb.math("MULTIPLY", ang, 95.0)), -0.6, 0.9)
    c = nb.mix(lum, tone, tuple(t * 3.0 for t in tone))
    pill = nb.remap(nb.noise(coords(nb, None, (1.0, 1.0)), 420.0, 1.0, 0.5), 0.63, 0.70)
    c = nb.mix(nb.math("MULTIPLY", pill, 0.6), c, (0.05, 0.048, 0.042))
    breath = nb.attr("breath")
    c = nb.mix(nb.math("MULTIPLY", breath, 0.6), c, tuple(t * 0.55 for t in tone))
    c = nb.mix(nb.math("MULTIPLY", nb.add((nb.occlusion(0.02), 1.0), (nb.valley(), 0.6)), 0.7), c, (0.003, 0.003, 0.0025))
    c = nb.mix(nb.math("MULTIPLY", nb.math("SUBTRACT", 1.0, rib), 0.45), c, tuple(t * 0.55 for t in tone))
    rough = nb.mixf(breath, 1.0, 0.75)
    normal = nb.bump(rib, 0.5, 0.0012, nb.normal_map(knit["nor_gl"], 1.6))
    nb.out(c, rough, normal, Sheen_Weight=0.25, Sheen_Roughness=0.6, Specular_IOR_Level=0.3)


def mat_skin(mat: bpy.types.Material) -> None:
    """Кожа рук: текстура MakeHuman (CC0), обветренная и в грязи по складкам и у ногтей."""
    nb = NodeBuilder(mat)
    uv = nb.node("ShaderNodeUVMap")
    diff = MPFB_USER / "skins" / "middleage_caucasian_male" / "middleage_lightskinned_male_diffuse.png"
    if diff.exists():
        img = nb.image(diff, False, (uv, "UV"))
        base = nb.mix(1.0, (img, "Color"), (0.86, 0.72, 0.62), "MULTIPLY")
    else:
        base = (0.50, 0.36, 0.29)
    g = grunge(nb, None, 0.12, 0.3, 0.7)
    dirt = nb.math("MULTIPLY", nb.add((nb.occlusion(0.008), 1.6), (g, 0.25)), 0.75, clamp=True)
    col = nb.mix(dirt, base, (0.11, 0.08, 0.06))
    pores = nb.noise(coords(nb, None, (1.0, 1.0)), 900.0, 2.0, 0.5)
    nb.out(col, nb.mixf(dirt, 0.46, 0.65), nb.bump(pores, 0.12, 0.0005),
           Subsurface_Weight=0.25, Subsurface_Scale=0.006)
    nb.bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)


def mat_eye(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    uv = nb.node("ShaderNodeUVMap")
    img = nb.image(MPFB_USER / "eyes" / "materials" / "brownlight_eye.png", False, (uv, "UV"))
    nb.out(nb.hsv((img, "Color"), 0.5, 0.55, 0.9), 0.25, Coat_Weight=1.0, Coat_Roughness=0.03)
