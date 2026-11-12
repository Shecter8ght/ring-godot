"""Контейнеры для лута, v02: файл просмотра отделки на ФОТО-основах (ambientCG CC0, _asset_src/textures) — материалы-узлы Blender по слотам
finish-spec.json: фото-набор (высота → Bump, яркость → вариации цвета, шероховатость) трипланарно по координатам объекта в мм-масштабе,
плюс структурные карты в развёртке (lc2_struct.py: строчки, сварной валик, точки сварки) и печать v01 (prints/uv).

  blender --background <RING_Loot_Containers_uv_v01.blend> --python tools/loot_containers/lc2_review.py -- <выход.blend> [shots <папка> [ключ,ключ]]

Все слоты v01 сохранены, замена — только фото-основа и признаки конструкции. Без Sheen и «глушащих» настроек: чёрное — чёрное.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE)).replace("\\", "/")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "asset_kit", "finish"))
import build_furniture as B  # noqa: E402
import mlib as L  # noqa: E402
import render_cards as RC  # noqa: E402

TEX = ROOT + "/_asset_src/textures"
BASE = ROOT + "/_asset_src/loot_containers"
SPEC = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/finish-spec.json"
MEANS = json.load(open(BASE + "/v02/photo_means.json"))
WALL = 1.4
PLACE = {"lc_safe": ("floor", 0.7, 1.3), "lc_cell": ("wall", 0.6, 1.0), "lc_gun": ("floor", 1.0, 1.9),
         "lc_file": ("floor", 0.7, 0.7), "lc_cash": ("floor", 0.6, 0.6), "lc_bag": ("floor", 0.8, 0.9),
         "lc_aid": ("wall", 0.6, 1.0)}
TITLES = {"lc_safe": "Сейф напольный", "lc_cell": "Сейф-ячейка", "lc_gun": "Оружейный шкаф", "lc_file": "Картотечный шкаф",
          "lc_cash": "Кассовое место", "lc_bag": "Медицинская сумка", "lc_aid": "Аптечка настенная"}

# ---------------------------------------------------------------- узлы


class Mat:
    def __init__(self, name):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        for n in list(self.nt.nodes):
            self.nt.nodes.remove(n)
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.bsdf = self.nt.nodes.new("ShaderNodeBsdfPrincipled")
        self.nt.links.new(self.bsdf.outputs["BSDF"], self.out.inputs["Surface"])
        self.coords = self.nt.nodes.new("ShaderNodeTexCoord")
        self._maps = {}
        self._imgs = {}
        self.y = 0

    def node(self, t, **kw):
        n = self.nt.nodes.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        self.y -= 40
        n.location = (-900 + (len(self.nt.nodes) % 7) * 160, self.y)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def val(self, v):
        n = self.node("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def math(self, op, a, b=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                self.link(x, n.inputs[i])
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        if isinstance(fac, (int, float)):
            n.inputs[0].default_value = fac
        else:
            self.link(fac, n.inputs[0])
        for i, x in ((6, a), (7, b)):
            if isinstance(x, (tuple, list)):
                n.inputs[i].default_value = (*x[:3], 1.0)
            else:
                self.link(x, n.inputs[i])
        return n.outputs[2]

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT")
        for i, x in ((0, fac), (2, a), (3, b)):
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                self.link(x, n.inputs[i])
        return n.outputs[0]

    def mapping(self, tile):
        """Трипланарная привязка по координатам объекта: tile — сторона кадра фото в метрах."""
        if tile not in self._maps:
            m = self.node("ShaderNodeMapping")
            m.inputs["Scale"].default_value = (1 / tile,) * 3
            self.link(self.coords.outputs["Object"], m.inputs["Vector"])
            self._maps[tile] = m.outputs[0]
        return self._maps[tile]

    def image(self, path, data, tile=None, uv=False, blend=0.18, interp="Cubic"):
        n = self.node("ShaderNodeTexImage")
        im = bpy.data.images.load(path, check_existing=True)
        im.colorspace_settings.name = "Non-Color" if data else "sRGB"
        n.image = im
        n.interpolation = interp
        if uv:
            self.link(self.nt.nodes.new("ShaderNodeUVMap").outputs[0], n.inputs["Vector"])
        else:
            n.projection = "BOX"
            n.projection_blend = blend
            self.link(self.mapping(tile), n.inputs["Vector"])
        return n

    def photo(self, pid, tile, what):
        """what: color / height / rough / metal → выход сокета."""
        key = (pid, tile, what)
        if key not in self._imgs:
            f = {"color": "color", "height": "height", "rough": "roughness", "metal": "metalness"}[what]
            p = f"{TEX}/{pid}/{f}_2k.jpg"
            n = self.image(p, what != "color", tile)
            self._imgs[key] = n.outputs["Color"]
        return self._imgs[key]

    def lum_ratio(self, pid, tile, k):
        """Яркость фото относительно среднего: вариации цвета основы (1 — без вариаций, k — доля)."""
        bw = self.node("ShaderNodeRGBToBW")
        self.link(self.photo(pid, tile, "color"), bw.inputs[0])
        r = self.math("DIVIDE", bw.outputs[0], max(MEANS[pid]["lum"], 1e-3))
        r = self.math("MINIMUM", r, 3.0)
        return self.mixf(k, 1.0, r)

    def bump(self, height, dist, strength=1.0, normal=None):
        n = self.node("ShaderNodeBump")
        n.inputs["Distance"].default_value = dist
        n.inputs["Strength"].default_value = strength
        self.link(height, n.inputs["Height"])
        if normal is not None:
            self.link(normal, n.inputs["Normal"])
        return n.outputs["Normal"]

    def noise(self, scale, detail=3.0, rough=0.6, w=None):
        n = self.node("ShaderNodeTexNoise", noise_dimensions="3D")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        self.link(self.coords.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def set(self, **kw):
        for k, v in kw.items():
            sock = self.bsdf.inputs[k]
            if isinstance(v, (int, float, tuple, list)):
                sock.default_value = v if not isinstance(v, (tuple, list)) else (*v[:3], 1.0)
            else:
                self.link(v, sock)


def srgb_to_lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


# ---------------------------------------------------------------- рецепты


def structure(m, game, slot_kind):
    """Карты развёртки: структура (R нить, G высота) и печать. Возвращает (thread, height, print_rgb, print_a)."""
    sp = f"{BASE}/maps_v02/{game}/{game}_struct.png"
    th = hh = None
    if slot_kind and os.path.exists(sp):
        sep = m.node("ShaderNodeSeparateColor")
        m.link(m.image(sp, True, uv=True, interp="Linear").outputs["Color"], sep.inputs[0])
        th, hh = sep.outputs[0], sep.outputs[1]
    pr = pa = None
    pc = f"{BASE}/prints/uv/{game}_print_color.png"
    if os.path.exists(pc):
        pr = m.image(pc, False, uv=True, interp="Linear").outputs["Color"]
        a = m.image(f"{BASE}/prints/uv/{game}_print_alpha.png", True, uv=True, interp="Linear")
        sep = m.node("ShaderNodeSeparateColor")
        m.link(a.outputs["Color"], sep.inputs[0])
        pa = sep.outputs[0]
    return th, hh, pr, pa


def finalize(m, color, rough, metal, normal, ctx, ink_cloth=False, **extra):
    """Печать поверх цвета / блеска, нить строчки, структурный рельеф."""
    th, hh, pr, pa = ctx
    if pa is not None:
        if ink_cloth:      # краска трафарета чуть закрывает плетение: цвет краски × яркость ткани
            pr = m.mix(0.35, pr, m.mix(1.0, pr, pr, "MULTIPLY"))
        color = m.mix(pa, color, pr)
        rough = m.mixf(pa, rough, 0.5)
        metal = m.mixf(pa, metal, 0.0)
    m.set(**{"Base Color": color, "Roughness": rough, "Metallic": metal}, **extra)
    if normal is not None:
        m.link(normal, m.bsdf.inputs["Normal"])


def paint(m, game, code, color, rough, pid="Metal027", tile=0.5, grain=0.00028, hammer=False, peel=0.0, coat=0.0, kind=None, wavy=0.0):
    """Порошковая краска / эмаль по фото: зерно (высота фото), цветовые вариации по яркости фото, «апельсиновая корка»,
    молотковая эмаль — чешуйки ямок (Voronoi), сварной валик и точки сварки — из структурной карты."""
    ctx = structure(m, game, kind)
    th, hh, pr, pa = ctx
    var = m.lum_ratio(pid, tile, 0.5)
    lin = srgb_to_lin(color)
    nz = m.noise(3.0, 2.0)
    soft = m.mixf(0.12, 1.0, m.math("MULTIPLY", nz, 2.0))
    col = m.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    col.inputs[0].default_value = 1.0
    col.inputs[6].default_value = (*lin, 1.0)
    vv = m.node("ShaderNodeCombineColor")
    pv = m.math("MULTIPLY", var, soft)
    for i in range(3):
        m.link(pv, vv.inputs[i])
    m.link(vv.outputs[0], col.inputs[7])
    color_out = col.outputs[2]
    r0 = m.photo(pid, tile, "rough")
    ro = m.mixf(1.0, rough, m.math("ADD", rough, m.math("SUBTRACT", r0, MEANS[pid]["rough"])))
    nrm = m.bump(m.photo(pid, tile, "height"), grain, 1.0)
    if peel:
        pk = m.noise(260.0, 1.0, 0.5)
        nrm = m.bump(pk, peel, 1.0, nrm)
    if hammer:
        v = m.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="F1")
        v.inputs["Scale"].default_value = 230.0
        v.inputs["Randomness"].default_value = 1.0
        m.link(m.coords.outputs["Object"], v.inputs["Vector"])
        sep0 = m.node("ShaderNodeSeparateColor")
        m.link(v.outputs["Color"], sep0.inputs[0])
        depth = m.mixf(sep0.outputs[1], 0.55, 1.0)
        bowl = m.math("POWER", m.math("MINIMUM", m.math("MULTIPLY", v.outputs["Distance"], 1.9), 1.0), 1.6)
        bowl = m.math("MULTIPLY", bowl, depth)
        nrm = m.bump(bowl, 0.0006, 1.0, nrm)
        sep = m.node("ShaderNodeSeparateColor")
        m.link(v.outputs["Color"], sep.inputs[0])
        cell = m.mixf(0.14, 1.0, m.math("MULTIPLY", sep.outputs[0], 2.0))
        # дно ямки темнее, кромка светлее (отражающая краска молотковой эмали)
        pool = m.mixf(0.35, 0.72, 1.18)
        edge_mix = m.mixf(bowl, 0.70, 1.30)
        cv = m.node("ShaderNodeCombineColor")
        pv2 = m.math("MULTIPLY", cell, edge_mix)
        for i in range(3):
            m.link(pv2, cv.inputs[i])
        color_out = m.mix(1.0, color_out, cv.outputs[0], "MULTIPLY")
        ro = m.math("ADD", ro, m.math("MULTIPLY", sep.outputs[1], 0.10))
    if wavy:   # «хлопун»: тонкий лист чуть волнится между рёбрами — блик плывёт
        nrm = m.bump(m.noise(3.2, 1.0, 0.5), wavy, 1.0, nrm)
    if hh is not None:
        nrm = m.bump(hh, 0.002, 1.0, nrm)
    finalize(m, color_out, ro, 0.0, nrm, ctx, **({"Coat Weight": coat, "Coat Roughness": 0.15} if coat else {}))
    m.set(**{"Specular IOR Level": 0.5})


def metal(m, game, color, rough, pid=None, tile=0.3, grain=0.0001, tint2=None, scratch=0.0, kind=None, aniso=0.0, hei=None):
    ctx = structure(m, game, kind)
    lin = srgb_to_lin(color)
    ro = rough
    nrm = None
    if pid:
        r0 = m.photo(pid, tile, "rough")
        ro = m.math("ADD", rough, m.math("MULTIPLY", m.math("SUBTRACT", r0, MEANS[pid]["rough"]), 1.0))
        nrm = m.bump(m.photo(pid, tile, "height"), grain, 1.0)
    finalize(m, lin, ro, 1.0, nrm, ctx, **({"Anisotropic": aniso} if aniso else {}))


def zinc(m, game, rough=0.32, kind=None):
    """Оцинковка с кристаллом («спангл»): ячейки Voronoi — у каждой своя яркость и свой наклон блика; пассивирование —
    жёлто-радужный отлив по фасету (Layer Weight)."""
    ctx = structure(m, game, kind)
    v = m.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="F1")
    v.inputs["Scale"].default_value = 90.0
    v.inputs["Randomness"].default_value = 1.0
    m.link(m.coords.outputs["Object"], v.inputs["Vector"])
    sep = m.node("ShaderNodeSeparateColor")
    m.link(v.outputs["Color"], sep.inputs[0])
    br = m.mixf(sep.outputs[0], 0.62, 0.92)
    lw = m.node("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    tintc = m.mix(m.math("MULTIPLY", sep.outputs[1], 0.8), (0.80, 0.78, 0.74), (0.74, 0.76, 0.82))
    tintc = m.mix(m.math("MULTIPLY", lw.outputs["Facing"], 0.55), tintc, (0.86, 0.78, 0.55))
    cv = m.node("ShaderNodeCombineColor")
    for i in range(3):
        m.link(br, cv.inputs[i])
    colr = m.mix(1.0, tintc, cv.outputs[0], "MULTIPLY")
    h = m.math("MULTIPLY", v.outputs["Distance"], 1.0)
    nrm = m.bump(m.math("ADD", h, m.math("MULTIPLY", sep.outputs[2], 0.6)), 0.00018, 1.0)
    ro = m.math("ADD", rough, m.math("MULTIPLY", sep.outputs[1], 0.18))
    finalize(m, colr, ro, 1.0, nrm, ctx)


def plastic(m, game, color, rough, pid="Plastic018A", tile=0.12, grain=0.00018, var=0.35, kind=None):
    ctx = structure(m, game, kind)
    lin = srgb_to_lin(color)
    v = m.lum_ratio(pid, tile, var)
    cv = m.node("ShaderNodeCombineColor")
    for i in range(3):
        m.link(v, cv.inputs[i])
    col = m.mix(1.0, lin, cv.outputs[0], "MULTIPLY")
    r0 = m.photo(pid, tile, "rough")
    ro = m.math("ADD", rough, m.math("SUBTRACT", r0, MEANS[pid]["rough"]))
    nrm = m.bump(m.photo(pid, tile, "height"), grain, 1.0)
    finalize(m, col, ro, 0.0, nrm, ctx)
    m.set(**{"Specular IOR Level": 0.5})


def wrinkle(m, game, color=(0.05, 0.05, 0.052), rough=0.38, kind=None):
    """Чёрная «морщинистая» (муаровая) краска стальных деталей: искажённый шум → хребты."""
    ctx = structure(m, game, kind)
    n1 = m.node("ShaderNodeTexNoise", noise_dimensions="3D")
    n1.inputs["Scale"].default_value = 110.0
    n1.inputs["Detail"].default_value = 6.0
    n1.inputs["Distortion"].default_value = 1.4
    m.link(m.coords.outputs["Object"], n1.inputs["Vector"])
    ridge = m.math("ABSOLUTE", m.math("SUBTRACT", n1.outputs["Fac"], 0.5))
    ridge = m.math("SUBTRACT", 1.0, m.math("MULTIPLY", ridge, 4.0, clamp=True))
    nrm = m.bump(ridge, 0.0009, 1.0)
    nrm = m.bump(m.photo("Metal027", 0.5, "height"), 0.00025, 1.0, nrm)
    ro = m.mixf(ridge, rough + 0.10, rough - 0.08)
    col = m.mix(m.math("MULTIPLY", ridge, 0.12), srgb_to_lin(color), (0.13, 0.13, 0.135))
    finalize(m, col, ro, 0.0, nrm, ctx)


def fabric(m, game, color, tile=0.10, pid="Fabric035", weave=0.00085, rough=0.84, kind=None, thread=None, k=0.8, ink=False):
    ctx = structure(m, game, kind)
    th, hh, pr, pa = ctx
    lin = srgb_to_lin(color)
    v = m.lum_ratio(pid, tile, k)
    cv = m.node("ShaderNodeCombineColor")
    for i in range(3):
        m.link(v, cv.inputs[i])
    col = m.mix(1.0, lin, cv.outputs[0], "MULTIPLY")
    # складки: низкочастотный шум меняет блеск ткани (на сгибах — блестит иначе)
    nz = m.noise(14.0, 3.0, 0.55)
    ro = m.mixf(nz, rough - 0.14, rough + 0.06)
    nrm = m.bump(m.photo(pid, tile, "height"), weave, 1.0)
    if hh is not None:
        nrm = m.bump(hh, 0.0016, 1.0, nrm)
        tc = tuple(min(1.0, c * 2.2 + 0.05) for c in lin) if thread is None else thread
        col = m.mix(m.math("MULTIPLY", th, 0.95), col, tc)
    finalize(m, col, ro, 0.0, nrm, ctx, ink_cloth=ink)


def tape_reflective(m, game, kind=None):
    """Светоотражающая лента: ячейки микропризм (мелкий Voronoi — у каждой свой наклон блика), серебристо-серая подложка."""
    ctx = structure(m, game, kind)
    v = m.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="DISTANCE_TO_EDGE")
    v.inputs["Scale"].default_value = 1500.0
    m.link(m.coords.outputs["Object"], v.inputs["Vector"])
    v2 = m.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="F1")
    v2.inputs["Scale"].default_value = 1500.0
    m.link(m.coords.outputs["Object"], v2.inputs["Vector"])
    sep = m.node("ShaderNodeSeparateColor")
    m.link(v2.outputs["Color"], sep.inputs[0])
    nrm = m.bump(m.math("MULTIPLY", sep.outputs[0], 1.0), 0.00006, 1.0)
    nrm = m.bump(m.math("MINIMUM", m.math("MULTIPLY", v.outputs["Distance"], 6.0), 1.0), 0.00004, 1.0, nrm)
    ro = m.mixf(sep.outputs[1], 0.16, 0.42)
    col = m.mix(sep.outputs[2], (0.30, 0.31, 0.31), (0.52, 0.53, 0.52))
    if ctx[0] is not None:
        col = m.mix(m.math("MULTIPLY", ctx[0], 0.9), col, (0.18, 0.18, 0.18))
    m.set(**{"Coat Weight": 0.5, "Coat Roughness": 0.08})
    finalize(m, col, ro, 0.35, nrm, ctx)


def paper(m, game, color, rough=0.62, pid="Paper001", tile=0.2, sat=False, kind=None):
    ctx = structure(m, game, kind)
    lin = srgb_to_lin(color)
    v = m.lum_ratio(pid, tile, 0.25)
    cv = m.node("ShaderNodeCombineColor")
    for i in range(3):
        m.link(v, cv.inputs[i])
    col = m.mix(1.0, lin, cv.outputs[0], "MULTIPLY")
    nrm = m.bump(m.photo(pid, tile, "height"), 0.00012, 1.0)
    finalize(m, col, rough, 0.0, nrm, ctx)


def felt(m, game, color=(0.05, 0.05, 0.052), kind=None):
    ctx = structure(m, game, kind)
    lin = srgb_to_lin(color)
    v = m.lum_ratio("Fabric034", 0.12, 0.8)
    cv = m.node("ShaderNodeCombineColor")
    for i in range(3):
        m.link(v, cv.inputs[i])
    col = m.mix(1.0, lin, cv.outputs[0], "MULTIPLY")
    nrm = m.bump(m.photo("Fabric034", 0.12, "height"), 0.0016, 1.0)
    finalize(m, col, 0.96, 0.0, nrm, ctx)


def glass(m, game, color, rough, alpha=1.0, emit=None):
    ctx = structure(m, game, None)
    finalize(m, color, rough, 0.0, None, ctx)
    if alpha < 1:
        m.set(Alpha=alpha)


# код → построитель (m, game, slot_id)
def build(code, game, slot_id):
    m = Mat(f"{game}:{slot_id}")
    kind = {"bag_cloth": "stitch2", "bag_lining": "stitch1", "bag_webbing": "web", "bag_tape": "stitch1",
            "safe_body_out": "bead", "cell_body": "spot", "gun_body": "spot", "file_body": "spot", "aid_body": "spot"}.get(slot_id)
    P = {
        "PW-GRA-SAT": lambda: paint(m, game, code, (0.145, 0.15, 0.158), 0.36, "Metal027", 0.5, 0.00028, hammer=True, kind=kind),
        "PW-LGR-SAT": lambda: paint(m, game, code, (0.60, 0.61, 0.60), 0.36, "Metal029", 0.5, 0.0002, peel=0.00012, coat=0.12, kind=kind, wavy=0.010),
        "PW-GRY-SAT": lambda: paint(m, game, code, (0.38, 0.39, 0.40), 0.42, "Metal029", 0.5, 0.0002, peel=0.00030, kind=kind),
        "PW-SGN-SAT": lambda: paint(m, game, code, (0.27, 0.32, 0.27), 0.38, "Metal029", 0.5, 0.0002, peel=0.00022, coat=0.12, kind=kind, wavy=0.012),
        "PW-WHT-SMO": lambda: paint(m, game, code, (0.76, 0.76, 0.74), 0.20, "Metal029", 0.5, 0.00012, peel=0.00016, coat=0.5, kind=kind, wavy=0.008),
        "PT-BLK-SAT": lambda: paint(m, game, code, (0.078, 0.078, 0.081), 0.42, "Metal029", 0.5, 0.00022, peel=0.00018),
        "PT-BLK-MAT": lambda: metal(m, game, (0.03, 0.03, 0.033), 0.34, "Metal063", 0.3, 0.00005),
        "CR-GLS": lambda: metal(m, game, (0.80, 0.80, 0.80), 0.045, "Metal044A", 0.1, 0.00004),
        "CR-SAT": lambda: metal(m, game, (0.74, 0.75, 0.75), 0.26, "Metal044A", 0.1, 0.00005),
        "NI-PLT-SAT": lambda: metal(m, game, (0.72, 0.71, 0.68), 0.24, "Metal045A", 0.1, 0.00005),
        "SS-BRU": lambda: metal(m, game, (0.62, 0.62, 0.62), 0.34, "Metal009", 0.12, 0.00018, aniso=0.5),
        "ST-BRT-SAT": lambda: metal(m, game, (0.60, 0.60, 0.60), 0.28, "Metal009", 0.12, 0.00008),
        "AL-EXT-ANO": lambda: metal(m, game, (0.70, 0.70, 0.72), 0.30, "Metal009", 0.10, 0.00012),
        "ZN-SHT-SPG": lambda: zinc(m, game),
        "RB-BLK-MAT": lambda: plastic(m, game, (0.095, 0.095, 0.095), 0.85, "Rubber002", 0.2, 0.0004, 0.2),
        "PL-BGE-TEX": lambda: plastic(m, game, (0.62, 0.59, 0.52), 0.48, "Plastic018A", 0.12, 0.00022),
        "PL-DGR-TEX": lambda: plastic(m, game, (0.15, 0.155, 0.16), 0.5, "Plastic018A", 0.10, 0.0002),
        "PL-LGR-TEX": lambda: plastic(m, game, (0.48, 0.48, 0.47), 0.5, "Plastic018A", 0.10, 0.0002),
        "PL-RED-TEX": lambda: plastic(m, game, (0.55, 0.07, 0.06), 0.46, "Plastic018A", 0.10, 0.0002),
        "PL-GRN-TEX": lambda: plastic(m, game, (0.12, 0.4, 0.18), 0.46, "Plastic018A", 0.10, 0.0002),
        "PL-BLU-TEX": lambda: plastic(m, game, (0.08, 0.2, 0.5), 0.46, "Plastic018A", 0.10, 0.0002),
        "PL-YEL-SMO": lambda: plastic(m, game, (0.86, 0.56, 0.06), 0.40, "Plastic010", 0.2, 0.00006, 0.15),
        "PL-BLK-TEX": lambda: plastic(m, game, (0.09, 0.09, 0.09), 0.60, "Plastic012A", 0.12, 0.00025, 0.5),
        "PL-BLK-GLS": lambda: plastic(m, game, (0.05, 0.05, 0.052), 0.14, "Plastic006", 0.2, 0.00004, 0.0),
        "GL-LCD-MAT": lambda: glass(m, game, (0.02, 0.03, 0.026), 0.35),
        "GL-SMK": lambda: glass(m, game, (0.03, 0.03, 0.03), 0.06, alpha=0.4),
        "PP-LBL-SAT": lambda: paper(m, game, (0.86, 0.86, 0.84), 0.30, "Paper001", 0.2),
        "PP-LBL-MAT": lambda: paper(m, game, (0.84, 0.83, 0.80), 0.68, "Paper003", 0.2),
        "CB-KRF-MAT": lambda: paper(m, game, (0.6, 0.45, 0.29), 0.86, "Cardboard004", 0.15),
        "FB-OXF-RED": lambda: fabric(m, game, (0.42, 0.045, 0.045), 0.10, "Fabric035", 0.00085, 0.82, kind, ink=True),
        "FB-BLK-WEB": lambda: fabric(m, game, (0.035, 0.035, 0.037), 0.06, "Fabric041", 0.0006, 0.80, kind, k=0.9),
        "FB-POL-GRY": lambda: fabric(m, game, (0.19, 0.19, 0.2), 0.12, "Fabric082A", 0.0003, 0.78, kind, k=0.5),
        "RF-SLV-TAP": lambda: tape_reflective(m, game, kind),
        "FM-DGR-MAT": lambda: felt(m, game, (0.10, 0.10, 0.11)),
        "FT-BLK-MAT": lambda: felt(m, game, (0.05, 0.05, 0.052)),
    }
    if code == "PT-BLK-SAT" and slot_id == "cash_drawer":
        wrinkle(m, game)
    elif code in P:
        P[code]()
    else:
        raise KeyError(code)
    return m.mat


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[0]
    shots = argv[2] if len(argv) > 2 and argv[1] == "shots" else None
    only = argv[3].split(",") if len(argv) > 3 and argv[3] else None
    spec = json.load(open(SPEC, encoding="utf-8"))
    slot_of = {}
    for sl in spec["slots"]:
        for p in sl["parts"]:
            slot_of.setdefault(p, sl)
    for o in list(bpy.data.objects):
        if o.name.startswith("_src_"):
            bpy.data.objects.remove(o)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    x = 0.0
    spots = {}
    for game, (how, wc, wo) in PLACE.items():
        cache = {}
        for suffix, width, tag in (("__closed", wc, "закрыто"), ("", wo, "открыто")):
            coll = bpy.data.collections[game + suffix]
            coll.hide_viewport = False
            coll.hide_render = False
            cx = x + width / 2
            m = Matrix.Translation((cx, WALL if how == "wall" else 0.0, 1.3 if how == "wall" else 0.0))
            for ob in coll.objects:
                ob.hide_viewport = False
                ob.hide_render = False
                ob.matrix_world = m
                ob.data.materials.clear()
                nm = ob.name[2:] if ob.name.startswith("c:") else ob.name
                nm = nm.rsplit(".", 1)[0] if nm.rsplit(".", 1)[-1].isdigit() else nm
                sl = slot_of.get(nm)
                if sl is None:
                    print("НЕТ СЛОТА", ob.name)
                    continue
                key = sl["id"]
                if key not in cache:
                    cache[key] = build(sl["finish"], game, sl["id"])
                ob.data.materials.append(cache[key])
                for p in ob.data.polygons:
                    p.use_smooth = True
                ob.data.set_sharp_from_angle(angle=math.radians(40))
            spots[(game, tag)] = m.translation.copy()
            x += width + 0.12
        x += 0.35
    st = L.collection("Студия")
    B.studio(st, x)
    sc = bpy.context.scene
    sc.world = RC.world_studio(strength=1.0)
    # скользящий ключевой свет: фактура читается рельефом тени
    ld = bpy.data.lights.new("Скользящий свет", "AREA")
    ld.energy, ld.size, ld.size_y = 90.0, 1.2, 0.6
    lo = bpy.data.objects.new("Скользящий свет", ld)
    st.objects.link(lo)
    lo.location = (-1.4, -0.9, 0.9)
    lo.rotation_euler = (math.radians(75), 0, math.radians(-55))
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 128
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    if shots:
        render_shots(shots, spots, only)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


# (имя, набор, состояние, цель от корня, расстояние, азимут°, возвышение°, фокусное мм, угол света°)
SHOTS = [
    ("bag_2m", "lc_bag", "закрыто", (0, 0, 0.15), 2.0, -30, 22, 50),
    ("bag_open", "lc_bag", "открыто", (0, 0, 0.15), 1.4, -25, 28, 50),
    ("bag_macro", "lc_bag", "закрыто", (-0.15, -0.12, 0.23), 0.45, -20, 25, 85),
    ("bag_macro2", "lc_bag", "закрыто", (0.0, -0.11, 0.30), 0.45, -35, 45, 85),
    ("safe_2m", "lc_safe", "закрыто", (0, 0, 0.36), 2.0, -28, 12, 50),
    ("safe_macro", "lc_safe", "закрыто", (0.0, -0.22, 0.52), 0.55, -18, 8, 85),
    ("safe_corner", "lc_safe", "закрыто", (-0.2, -0.23, 0.68), 0.55, -48, 10, 85),
    ("safe_open", "lc_safe", "открыто", (0.0, 0.0, 0.36), 2.2, -40, 14, 50),
    ("gun_2m", "lc_gun", "закрыто", (0, 0, 0.9), 3.4, -22, 8, 50),
    ("gun_macro", "lc_gun", "закрыто", (0.0, -0.23, 1.3), 0.6, -25, 8, 85),
    ("gun_open", "lc_gun", "открыто", (0, 0, 0.9), 3.6, -20, 8, 50),
    ("file_2m", "lc_file", "открыто", (0, -0.1, 0.7), 2.6, -30, 12, 50),
    ("file_macro", "lc_file", "открыто", (0.0, -0.32, 1.22), 0.6, -22, 8, 85),
    ("cash_2m", "lc_cash", "закрыто", (0, 0, 0.15), 1.0, -20, 38, 50),
    ("cash_macro", "lc_cash", "закрыто", (-0.05, -0.1, 0.16), 0.45, 0, 55, 85),
    ("aid_2m", "lc_aid", "закрыто", (0, -0.05, 0.0), 1.2, -12, 6, 50),
    ("aid_macro", "lc_aid", "открыто", (0, -0.05, 0.0), 0.5, -25, 10, 85),
    ("cell_open", "lc_cell", "открыто", (-0.06, -0.1, 0.12), 0.9, -25, 10, 50),
    ("cell_macro", "lc_cell", "закрыто", (-0.0, -0.1, 0.12), 0.5, -20, 10, 85),
]


def render_shots(folder, spots, only) -> None:
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1000, 750
    sc.cycles.samples = 48
    cam = bpy.data.cameras.new("проверка")
    co = bpy.data.objects.new("проверка", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    for name, game, state, off, dist, az, el, lens in SHOTS:
        if only and name not in only:
            continue
        base = spots[(game, state)]
        tgt = base + V(off)
        a, e = math.radians(az - 90), math.radians(el)
        co.location = tgt + V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
        co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
        cam.lens = lens
        sc.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, flush=True)


if __name__ == "__main__":
    main()
