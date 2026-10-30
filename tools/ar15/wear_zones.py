# AR-15 «ГРАНЬ-15», этап 2 (износ): маски МЕСТ хвата рукояти, запечённые в развёртку набора текстур (UVMap — та же,
# что в проекте Painter). Клипов рук от первого лица у AR-15 ещё нет (tools/wear_from_use нечем кормить), поэтому места —
# по форме рукояти и правому хвату: ладонь — спинка и правый бок (кроме переда), пальцы — передние выемки и кончики на
# переднем крае левого бока, большой палец — левый бок вверху, низ — торец. Рисунок следа (отпечаток, развод, пыль) —
# фото-маски CC0 в Painter (sp_ar15_wear.py); здесь только «где».
#   blender -b <AR15_uv_v03.blend> --python tools/ar15/wear_zones.py -- <папка вывода> [размер 2048]
# Пишет grip_zone_<palm|fingers|thumb|base>.png (ч/б, 16 бит) в папку вывода.
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

from lib import GRIP_TOP_Z, GRIP_SCREW_X  # noqa: F401  (ось рукояти — те же числа, что в part_grip)

MM = 0.001
ANGLE = math.radians(18.0)                       # part_grip.ANGLE
TOP = Vector((-147.0, 0.0, GRIP_TOP_Z))           # part_grip.TOP (TOP_CX, GRIP_TOP_Z)
DOWN = Vector((-math.sin(ANGLE), 0.0, -math.cos(ANGLE)))
FWD = Vector((math.cos(ANGLE), 0.0, -math.sin(ANGLE)))
ZONES = ("palm", "fingers", "thumb", "base")


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def window(x, a0, a1, b0, b1):
    """1 между a1 и b0, плавно к нулю до a0 и после b1."""
    return sstep(a0, a1, x) * (1.0 - sstep(b0, b1, x))


def weights(o):
    me = o.data
    mw = o.matrix_world
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    nor = np.empty(n * 3); me.vertices.foreach_get("normal", nor)
    nor = nor.reshape(n, 3)
    M = np.array(mw)
    p = (co @ M[:3, :3].T + M[:3, 3]) / MM
    nw = nor @ np.linalg.inv(M[:3, :3])
    nw /= np.linalg.norm(nw, axis=1, keepdims=True) + 1e-12
    d = p - np.array(TOP)
    s = d @ np.array(DOWN)                      # вниз по рукояти от площадки, мм
    u = d @ np.array(FWD)                       # вперёд поперёк оси, мм
    nb, nf, ny, nd = nw @ -np.array(FWD), nw @ np.array(FWD), nw[:, 1], nw @ np.array(DOWN)
    # доля по глубине сечения: 0 — спинка, 1 — перёд (по ближайшим к этой высоте точкам)
    bins = np.floor(s / 2.0).astype(int)
    umin, umax = {}, {}
    for b, uu in zip(bins, u):
        umin[b] = min(umin.get(b, 1e9), uu)
        umax[b] = max(umax.get(b, -1e9), uu)
    t = np.array([(uu - umin[b]) / max(umax[b] - umin[b], 1.0) for b, uu in zip(bins, u)])
    palm = np.maximum(sstep(0.25, 0.6, nb), 0.85 * sstep(0.4, 0.8, -ny) * (1.0 - sstep(0.55, 0.85, t)))
    palm *= window(s, 4.0, 12.0, 92.0, 102.0)
    front = sstep(0.3, 0.7, nf) * window(s, 30.0, 38.0, 98.0, 104.0)
    tips = 0.8 * sstep(0.4, 0.8, ny) * sstep(0.55, 0.85, t) * window(s, 34.0, 42.0, 96.0, 102.0)
    fingers = np.maximum(front, tips)
    thumb = sstep(0.4, 0.8, ny) * window(s, -2.0, 4.0, 22.0, 32.0) * window(t, 0.1, 0.3, 0.75, 0.9)
    # торец и его кромка; вниз смотрит ещё низ выступа под скобой (s ≈ 35) — он не «низ»
    base = np.maximum(sstep(0.5, 0.85, nd) * sstep(80.0, 92.0, s), 0.6 * sstep(97.0, 102.0, s))
    return {"palm": palm, "fingers": fingers, "thumb": thumb, "base": base}


def bake(o, w, out_dir, size):
    me = o.data
    attr = me.color_attributes.get("wz") or me.color_attributes.new("wz", "FLOAT_COLOR", "POINT")
    mat = bpy.data.materials.new("wz_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "wz"
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    old = list(me.materials)
    me.materials.clear(); me.materials.append(mat)
    S = bpy.context.scene
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 1
    S.render.bake.margin = 16
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    o.hide_set(False); o.hide_render = False
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    me.uv_layers.active = me.uv_layers["UVMap"]
    os.makedirs(out_dir, exist_ok=True)
    keys = list(ZONES)
    for k in keys:
        vals = w[k]
        data = np.zeros((len(me.vertices), 4), dtype=np.float32)
        data[:, 0] = data[:, 1] = data[:, 2] = vals
        data[:, 3] = 1.0
        attr.data.foreach_set("color", data.ravel())
        img = bpy.data.images.new(f"grip_zone_{k}", size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        nt.nodes.active = tex
        bpy.ops.object.bake(type="EMIT")
        img.filepath_raw = os.path.join(out_dir, f"grip_zone_{k}.png")
        img.file_format = "PNG"
        S.render.image_settings.color_depth = "16"
        img.save_render(img.filepath_raw)
        print("ZONE", k, "доля >0.5:", round(float((vals > 0.5).mean()), 3), "→", img.filepath_raw)
    me.materials.clear()
    for m in old:
        me.materials.append(m)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out_dir = a[0]
    size = int(a[1]) if len(a) > 1 else 2048
    o = bpy.data.objects["Pistol_grip"]
    bake(o, weights(o), out_dir, size)


if __name__ == "__main__":
    main()
