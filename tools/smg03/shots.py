# ПП по мотивам KRISS Vector Gen II: проверочные снимки (Workbench, глина) и сверка наложением на снимки KRISS.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/smg03/shots.py -- <папка> [вид,…] [ключ=значение …]
# Виды: photoA / photoB — ортокамера ровно в масштабе снимка KRISS (1.797 пикс/мм, 1600 × 1000) слева / справа, рядом
# пишется compare_<вид>.png — модель поверх снимка (50 %); left, right, top, bottom, front, rear, q34, q34fr, q34rl,
# q34r — глина (размер кадра — ключ res=<ширина>x<высота>);
# zoom:<имя>:<x>:<z>:<ширина мм>:<сторона +Y|-Y|top|front|rear|q|q-|qlow|qback|qfront(-)> — крупный план.
# Ключи: ctrl.<свойство>=<число> — положение органов управления (пустышка SMG03_Controls).
import math
import os
import sys

import bpy
from mathutils import Vector

S = 1.797
BY_A, MX_A = 451.5, 256.0
X0_A = MX_A + 139.7 * S
PHOTO_DIR = "E:/Models Blender/WEAPONS/Vector — модель/refs/web/kriss_usa"
PHOTO_A = "orig_kv_sbr_5_5in_blk_30rd_A__83111.1707345817.jpg"
PHOTO_B = "orig_kv_sbr_5_5in_blk_30rd_B__86426.1707341769.jpg"


def setup_render(w, h):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.62, 0.62, 0.64)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_specular_highlight = True
    sc.display.render_aa = "16"
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"


def cam(name, loc, look, ortho_scale=None, lens=50.0, up=Vector((0, 0, 1))):
    c = bpy.data.objects.get(name)
    if c is None:
        c = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        bpy.context.scene.collection.objects.link(c)
    c.location = loc
    d = (Vector(look) - Vector(loc)).normalized()
    c.rotation_euler = d.to_track_quat("-Z", "Y" if abs(d.dot(up)) > 0.99 else "Y").to_euler()
    q = d.to_track_quat("-Z", "Y")
    # «вверх» камеры — мировой Z (или −X для вида сверху)
    right = d.cross(up).normalized() if abs(d.dot(up)) < 0.99 else Vector((0, 1, 0))
    upv = right.cross(d).normalized()
    from mathutils import Matrix
    m = Matrix((right, upv, -d)).transposed()
    c.rotation_euler = m.to_euler()
    if ortho_scale:
        c.data.type = "ORTHO"
        c.data.ortho_scale = ortho_scale
    else:
        c.data.type = "PERSP"
        c.data.lens = lens
    c.data.clip_start = 0.001
    c.data.clip_end = 20
    bpy.context.scene.camera = c
    return c


def bounds():
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get() or o.hide_render:
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def photo_view(kind, out):
    setup_render(1600, 1000)
    # центр снимка (800, 500) в осях модели
    if kind == "A":
        xc = (X0_A - 800) / S
        loc = Vector((xc * 1e-3, 1.0, (BY_A - 500) / S * 1e-3))
        look = loc - Vector((0, 1, 0))
    else:
        # B: x_B = 1598 − x_A, y_B = y_A − 2
        xa = 1598 - 800
        xc = (X0_A - xa) / S
        loc = Vector((xc * 1e-3, -1.0, (BY_A - 2 - 500) / S * 1e-3))
        look = loc + Vector((0, 1, 0))
    cam("Cam_photo", loc, look, ortho_scale=1600 / S * 1e-3)
    p = os.path.join(out, f"photo{kind}.png")
    render(p)
    try:
        import numpy as np
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.array(im.pixels[:]).reshape(h, w, 4)[::-1]
        ph = bpy.data.images.load(os.path.join(PHOTO_DIR, PHOTO_A if kind == "A" else PHOTO_B))
        pw, phh = ph.size
        b = np.array(ph.pixels[:]).reshape(phh, pw, 4)[::-1]
        alpha = a[:, :, 3:4] * 0.55
        tint = np.array([0.95, 0.35, 0.15, 1.0])
        comp = b * (1 - alpha) + (a * 0.5 + tint * 0.5) * alpha
        # контур модели — жёлтой линией
        m = a[:, :, 3] > 0.5
        edge = m ^ np.roll(m, 1, 0) | m ^ np.roll(m, 1, 1)
        comp[edge] = (1.0, 0.9, 0.0, 1.0)
        comp[:, :, 3] = 1.0
        outim = bpy.data.images.new("cmp", pw, phh)
        outim.pixels[:] = comp[::-1].ravel()
        outim.filepath_raw = os.path.join(out, f"compare_photo{kind}.png")
        outim.file_format = "PNG"
        outim.save()
    except Exception as e:
        print("COMPARE_FAIL", e)


def clay_view(name, out, w=1600, h=1000):
    """Глина: ортовиды (дуло вправо на видах сбоку, сверху и снизу) и 3/4 в перспективе с четырёх сторон:
    q34 — спереди слева, q34fr — спереди справа, q34rl — сзади слева, q34r — сзади справа."""
    setup_render(w, h)
    lo, hi = bounds()
    c = (lo + hi) / 2
    size = hi - lo
    dirs = {"left": Vector((0, 1, 0)), "right": Vector((0, -1, 0)), "top": Vector((0, 0, 1)), "bottom": Vector((0, 0, -1)),
            "front": Vector((1, 0, 0)), "rear": Vector((-1, 0, 0)), "q34": Vector((0.55, 0.75, 0.38)),
            "q34fr": Vector((0.55, -0.75, 0.38)), "q34rl": Vector((-0.6, 0.7, 0.35)),
            "q34r": Vector((-0.6, -0.7, 0.35))}
    d = dirs[name].normalized()
    if name.startswith("q34"):
        cam("Cam_clay", c + d * size.length * 0.85 * 1.6, c, lens=50.0)
    else:
        # по ширине кадра — H, по высоте — V; ортомасштаб — по ширине, с запасом 8 %
        H, V = {"left": (size.x, size.z), "right": (size.x, size.z), "top": (size.x, size.y),
                "bottom": (size.x, size.y), "front": (size.y, size.z), "rear": (size.y, size.z)}[name]
        # сверху — левый борт вверху кадра, снизу — правый; дуло вправо в обоих
        up = {"top": Vector((0, 1, 0)), "bottom": Vector((0, -1, 0))}.get(name, Vector((0, 0, 1)))
        cam("Cam_clay", c + d * 1.0, c, ortho_scale=max(H, V * w / h) * 1.08, up=up)
    render(os.path.join(out, f"{name}.png"))


def zoom_view(spec, out):
    _z, name, x, z, wmm, side = spec.split(":")
    x, z, wmm = float(x) * 1e-3, float(z) * 1e-3, float(wmm) * 1e-3
    setup_render(1200, 900)
    if side in ("+Y", "-Y"):
        s = 1 if side == "+Y" else -1
        cam("Cam_zoom", Vector((x, s * 1.0, z)), Vector((x, 0, z)), ortho_scale=wmm)
    elif side == "top":
        cam("Cam_zoom", Vector((x, 0, 1.0)), Vector((x, 0, 0)), ortho_scale=wmm, up=Vector((1, 0, 0)))
    elif side == "front":
        cam("Cam_zoom", Vector((1.0, 0, z)), Vector((0, 0, z)), ortho_scale=wmm)
    elif side == "rear":
        cam("Cam_zoom", Vector((-1.0, 0, z)), Vector((0, 0, z)), ortho_scale=wmm)
    else:
        # q — перспектива сверху-спереди-слева на точку
        dirs = {"q": (0.5, 0.7, 0.5), "q-": (0.5, -0.7, 0.5), "qlow": (0.6, 0.6, -0.5), "qlow-": (0.6, -0.6, -0.5),
                "qback": (-0.5, 0.7, 0.4), "qback-": (-0.5, -0.7, 0.4), "qfront": (0.9, 0.35, 0.25), "qfront-": (0.9, -0.35, 0.25)}
        d = Vector(dirs[side]).normalized()
        cam("Cam_zoom", Vector((x, 0, z)) + d * (wmm * 2.2), Vector((x, 0, z)), lens=40)
    render(os.path.join(out, f"zoom_{name}.png"))


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    os.makedirs(out, exist_ok=True)
    views = a[1].split(",") if len(a) > 1 and "=" not in a[1] else ["photoA", "photoB", "left", "top", "front", "q34"]
    ctrl = bpy.data.objects.get("SMG03_Controls")
    res = (1600, 1000)
    for kv in a[1:]:
        if kv.startswith("res="):
            res = tuple(int(t) for t in kv[4:].split("x"))
        if "=" in kv and kv.startswith("ctrl.") and ctrl is not None:
            k, val = kv[5:].split("=")
            ctrl[k] = float(val)
    if ctrl is not None:
        ctrl.update_tag()
        bpy.context.view_layer.update()
    for vname in views:
        if vname.startswith("photo"):
            photo_view(vname[-1], out)
        elif vname.startswith("zoom:"):
            zoom_view(vname, out)
        else:
            clay_view(vname, out, *res)
        print("SHOT", vname)


main()
