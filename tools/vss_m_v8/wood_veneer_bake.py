# ВСС-М v8: основа приклада из фото шпона (v6, образцы владельца с Fab: светлая серо-бежевая боковина с тёмным
# волокном, на срезах — охристые и тёмные слои со своим рисунком и рваными границами). Приклад — клеёная фанера:
# каждый слой — лист шпона, его рисунок лежит в плоскости XZ (листы параллельны боковинам), поэтому цвет точки —
# фото слоя в (x, z); номер слоя — по ширине приклада (Y). Чётные слои — охристые, волокно вдоль приклада; нечётные —
# тёмные, волокно поперёк (на гребне и низе видны торцы). Толщина слоёв гуляет, границы рваные вдоль волокна, клеевые
# швы тонкие. Строго плоские боковины — лицевой шпон из отдельного фото, слева и справа — разные места листа.
# Фото — Poly Haven, CC0 (_asset_src/vss_m_v8/wood_photos/<id>/license.txt), масштаб 1:1 (образец 1000 × 1000 мм).
# Карты запекаются излучением в развёртку приклада: <вариант>_color.png (sRGB), <вариант>_height.png (рельеф для
# Painter), ids.png (R — лицевой шпон, G — тёмный слой, B — клеевой шов: маски для стека).
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/wood_veneer_bake.py -- <папка> <вариант,вариант|ids> [размер]
import sys
import bpy

PHOTOS = "E:/Games/RING-godot/_asset_src/vss_m_v8/wood_photos"
LAYER_MM = 1.8
# яркость фото (1-й и 99-й процентили, значения файла): растягивается до 0…1 — тёмное волокно к 0
LUM = {"oak_veneer_03": (0.732, 0.852), "ash_veneer": (0.505, 0.66), "red_oak_veneer": (0.602, 0.751),
       "silver_oak_veneer_01": (0.715, 0.816), "black_oak_veneer": (0.338, 0.474)}
# лицевой шпон боковин: фото, линейные цвета тёмного волокна и светлой древесины, крутизна
FACES = {
    "A_dub_volnistyi": ("oak_veneer_03", (0.15, 0.092, 0.042), (0.58, 0.46, 0.27), 1.0),
    "B_yasen": ("ash_veneer", (0.15, 0.095, 0.045), (0.57, 0.45, 0.27), 1.0),
    "C_krasnyi_dub": ("red_oak_veneer", (0.15, 0.09, 0.04), (0.57, 0.44, 0.25), 1.0),
}
# слои на срезах: охристый (волокно вдоль) и тёмный (волокно поперёк)
OCHRE = ("silver_oak_veneer_01", (0.26, 0.17, 0.06), (0.52, 0.37, 0.12), 0.7)
DARK = ("black_oak_veneer", (0.05, 0.03, 0.018), (0.2, 0.12, 0.07), 1.0)
C_GLUE = (0.03, 0.017, 0.009)
# места листа для боковин (доли образца): слева и справа — разные
SIDE_OFF = ((0.12, 0.18), (0.52, 0.61))


class G:
    """Сборка узлов одного материала запекания."""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.nt.nodes.clear()
        self.L = self.nt.links

    def n(self, kind, **kw):
        x = self.nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(x, k, v)
        return x

    def link(self, a, b):
        if isinstance(a, (int, float)):
            b.default_value = a
        else:
            self.L.new(a, b)

    def op(self, o, a, b=None):
        x = self.n("ShaderNodeMath", operation=o)
        for i, v in enumerate((a, b)):
            if v is not None:
                self.link(v, x.inputs[i])
        return x.outputs[0]

    def rng(self, x, a0, a1, b0, b1, smooth=False):
        r = self.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR")
        self.link(x, r.inputs["Value"])
        for k, v in (("From Min", a0), ("From Max", a1), ("To Min", b0), ("To Max", b1)):
            r.inputs[k].default_value = v
        return r.outputs["Result"]

    def vec(self, u, v):
        c = self.n("ShaderNodeCombineXYZ")
        self.link(u, c.inputs[0])
        self.link(v, c.inputs[1])
        return c.outputs[0]

    def mix(self, f, a, b, kind="RGBA"):
        x = self.n("ShaderNodeMix", data_type=kind)
        if kind == "RGBA":
            ia, ib = 6, 7
        elif kind == "VECTOR":
            ia, ib = 4, 5
        else:
            ia, ib = 2, 3
        self.link(f, x.inputs["Factor"])
        for i, v in ((ia, a), (ib, b)):
            if isinstance(v, tuple):
                x.inputs[i].default_value = v + (1.0,) if (kind == "RGBA" and len(v) == 3) else v
            else:
                self.link(v, x.inputs[i])
        out = {"RGBA": 2, "VECTOR": 1, "FLOAT": 0}[kind]
        return x.outputs[out]

    def photo(self, pid, uv):
        """Яркость фото в точке uv (доли образца), растянутая до 0…1 по процентилям."""
        img = self.n("ShaderNodeTexImage", interpolation="Cubic")
        img.image = bpy.data.images.load(f"{PHOTOS}/{pid}/diffuse_8k.jpg", check_existing=True)
        img.image.colorspace_settings.name = "Non-Color"
        self.L.new(uv, img.inputs["Vector"])
        bw = self.n("ShaderNodeRGBToBW")
        self.L.new(img.outputs["Color"], bw.inputs[0])
        lo, hi = LUM[pid]
        r = self.n("ShaderNodeMapRange", clamp=True)
        self.L.new(bw.outputs[0], r.inputs["Value"])
        r.inputs["From Min"].default_value = lo
        r.inputs["From Max"].default_value = hi
        return r.outputs["Result"]

    def grade(self, g, lo, hi, gamma):
        return self.mix(self.op("POWER", g, gamma), lo, hi)


def build(mode, face):
    g = G(f"_wood_v6_{mode}")
    out = g.n("ShaderNodeOutputMaterial")
    emit = g.n("ShaderNodeEmission")
    g.L.new(emit.outputs[0], out.inputs["Surface"])
    geo = g.n("ShaderNodeNewGeometry")
    pm = g.n("ShaderNodeVectorMath", operation="SCALE")
    g.L.new(geo.outputs["Position"], pm.inputs[0])
    pm.inputs["Scale"].default_value = 1000.0
    p = g.n("ShaderNodeSeparateXYZ")
    g.L.new(pm.outputs[0], p.inputs[0])
    x, y, z = p.outputs["X"], p.outputs["Y"], p.outputs["Z"]
    nrm = g.n("ShaderNodeSeparateXYZ")
    g.L.new(geo.outputs["Normal"], nrm.inputs[0])

    # номер слоя по ширине: толщина гуляет (две синусоиды, производная < 1 — порядок слоёв сохраняется),
    # слои слегка волнистые по длине, границы рваные вдоль волокна (шум, вытянутый по X)
    t = g.op("MULTIPLY", y, 1.0 / LAYER_MM)
    tau = 6.2832
    t = g.op("ADD", t, g.op("MULTIPLY", g.op("SINE", g.op("MULTIPLY", t, tau * 0.37)), 0.12))
    t = g.op("ADD", t, g.op("MULTIPLY", g.op("SINE", g.op("ADD", g.op("MULTIPLY", t, tau * 0.61), 1.3)), 0.08))
    for scale, amp, det in ((0.03, 1.3, 2.0), (0.006, 2.2, 1.0)):
        nz = g.n("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = det
        g.L.new(pm.outputs[0], nz.inputs["Vector"])
        t = g.op("ADD", t, g.op("MULTIPLY", g.op("SUBTRACT", nz.outputs["Fac"], 0.5), amp))
    fib_v = g.n("ShaderNodeVectorMath", operation="MULTIPLY")
    g.L.new(pm.outputs[0], fib_v.inputs[0])
    fib_v.inputs[1].default_value = (0.09, 2.2, 2.2)
    fib = g.n("ShaderNodeTexNoise")
    fib.inputs["Scale"].default_value = 1.0
    fib.inputs["Detail"].default_value = 6.0
    fib.inputs["Roughness"].default_value = 0.65
    g.L.new(fib_v.outputs[0], fib.inputs["Vector"])
    t = g.op("ADD", t, g.op("MULTIPLY", g.op("SUBTRACT", fib.outputs["Fac"], 0.5), 0.55))
    idx = g.op("FLOOR", t)
    fr = g.op("FRACT", t)
    dark = g.op("FLOORED_MODULO", idx, 2.0)
    edge = g.op("MINIMUM", fr, g.op("SUBTRACT", 1.0, fr))
    glue = g.rng(edge, 0.0, 0.055, 1.0, 0.0, smooth=True)

    # свой кусок листа и тон у каждого слоя
    def hsh(seed):
        w = g.n("ShaderNodeTexWhiteNoise", noise_dimensions="1D")
        g.L.new(g.op("ADD", idx, seed), w.inputs["W"])
        return w.outputs["Value"]
    ou, ov, tone = hsh(0.0), hsh(37.13), hsh(71.7)
    xm, zm = g.op("MULTIPLY", x, 0.001), g.op("MULTIPLY", z, 0.001)
    # охристые — волокно вдоль приклада (u = x), тёмные — поперёк (u = z)
    g_och = g.photo(OCHRE[0], g.vec(g.op("ADD", xm, ou), g.op("ADD", zm, ov)))
    g_drk = g.photo(DARK[0], g.vec(g.op("ADD", zm, ou), g.op("ADD", xm, ov)))
    # лицевой шпон: место листа по стороне
    side = g.rng(nrm.outputs["Y"], -0.01, 0.01, 0.0, 1.0)
    fu = g.op("ADD", xm, g.mix(side, SIDE_OFF[0][0], SIDE_OFF[1][0], "FLOAT"))
    fv = g.op("ADD", zm, g.mix(side, SIDE_OFF[0][1], SIDE_OFF[1][1], "FLOAT"))
    pid, f_lo, f_hi, f_gam = FACES[face] if face else FACES["A_dub_volnistyi"]
    g_face = g.photo(pid, g.vec(fu, fv))
    facem = g.rng(g.op("ABSOLUTE", nrm.outputs["Y"]), 0.94, 0.985, 0.0, 1.0, smooth=True)

    if mode == "ids":
        c = g.n("ShaderNodeCombineColor")
        g.L.new(facem, c.inputs[0])
        nf = g.op("SUBTRACT", 1.0, facem)
        g.L.new(g.op("MULTIPLY", dark, nf), c.inputs[1])
        g.L.new(g.op("MULTIPLY", glue, nf), c.inputs[2])
        g.L.new(c.outputs[0], emit.inputs["Color"])
        return g.m
    if mode == "height":
        # тёмное волокно — поры и бороздки; на срезе рельеф слабее, у тёмных (торцевых) слоёв — пористее,
        # клеевой шов — чуть утоплен
        h_face = g.rng(g_face, 0.0, 1.0, 0.18, 0.72)
        h_cut = g.mix(dark, g.rng(g_och, 0.0, 1.0, 0.36, 0.62), g.rng(g_drk, 0.0, 1.0, 0.3, 0.58), "FLOAT")
        h_cut = g.op("SUBTRACT", h_cut, g.op("MULTIPLY", glue, 0.14))
        h = g.mix(facem, h_cut, h_face, "FLOAT")
        c = g.n("ShaderNodeCombineColor")
        for i in range(3):
            g.L.new(h, c.inputs[i])
        g.L.new(c.outputs[0], emit.inputs["Color"])
        return g.m
    c_och = g.grade(g_och, OCHRE[1], OCHRE[2], OCHRE[3])
    c_drk = g.grade(g_drk, DARK[1], DARK[2], DARK[3])
    tk =g.rng(tone, 0.0, 1.0, 0.8, 1.15)
    tkv = g.n("ShaderNodeCombineColor")
    for i in range(3):
        g.L.new(tk, tkv.inputs[i])
    cut = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    cut.inputs["Factor"].default_value = 1.0
    g.L.new(g.mix(dark, c_och, c_drk), cut.inputs[6])
    g.L.new(tkv.outputs[0], cut.inputs[7])
    cut = g.mix(g.op("MULTIPLY", glue, 0.7), cut.outputs[2], C_GLUE)
    c_face = g.grade(g_face, f_lo, f_hi, f_gam)
    # на скруглении у боковины сначала виден срез самого лицевого шпона — его тон, а не охристый слой
    # (иначе окна и контур обведены жёлтой линией)
    rim = g.rng(g.op("ABSOLUTE", nrm.outputs["Y"]), 0.7, 0.94, 0.0, 0.85, smooth=True)
    cut = g.mix(rim, cut, c_face)
    g.L.new(g.mix(facem, cut, c_face), emit.inputs["Color"])
    return g.m


def bake(o, mode, face, path, size):
    img = bpy.data.images.new(f"wood_{mode}", size, size, alpha=False)
    img.colorspace_settings.name = "sRGB" if mode == "color" else "Non-Color"
    mat = build(mode, face)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    o.data.materials.clear()
    o.data.materials.append(mat)
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", mode, face, path)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out, which = a[0], a[1].split(",")
    size = int(a[2]) if len(a) > 2 else 4096
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = 4
    sc.render.bake.margin = 16
    o = bpy.data.objects["Wood_stock_v8"]
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    for w in which:
        if w == "ids":
            bake(o, "ids", None, f"{out}/ids.png", size)
            continue
        bake(o, "color", w, f"{out}/{w}_color.png", size)
        bake(o, "height", w, f"{out}/{w}_height.png", size)


main()
