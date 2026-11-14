# ПКП: подбор камеры снимка-образца по силуэту уже построенных деталей.
#   blender --background <файл.blend> --python tools/pkp/fit_cam.py -- <снимок 13|14> <папка refs/owner> [x0:x1,x0:x1 …]
#       [подъём от:до:шаг] [поворот от:до:шаг]
# Перебирает подъём камеры над осью оружия (elev, градусы) и поворот кадра вокруг оптической оси (roll); сдвиг кадра
# по вертикали и горизонтали подбирается сам (перебором сдвига маски). Мера — доля несовпавших пикселей силуэта
# в заданных полосах кадра (по X): там должны быть только уже построенные детали (ствол, приклад).
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refmap  # noqa: E402

MM = 0.001


def set_cam(co, cam, img, elev, roll):
    eye, tgt, f = refmap.camera(img)
    eye = Vector(eye); tgt = Vector(tgt)
    # подъём: камера поворачивается вокруг оси оружия (оси X через цель)
    R = Matrix.Rotation(math.radians(elev) * (1.0 if eye.y < 0 else -1.0), 3, "X")
    eye2 = tgt + R @ (eye - tgt)
    co.location = eye2 * MM
    q = (tgt - eye2).to_track_quat("-Z", "Y")
    co.rotation_euler = (q @ Matrix.Rotation(math.radians(roll), 3, "Z").to_quaternion()).to_euler()
    cam.type = "PERSP"; cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0
    cam.lens = f * 36.0 / 1920.0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    img = argv[0]; refs = argv[1]
    bands = [tuple(int(v) for v in b.split(":")) for b in argv[2].split(",")] if len(argv) > 2 else [(0, 1920)]
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"; sc.display.shading.color_type = "SINGLE"; sc.display.shading.single_color = (1, 1, 1)
    sc.display.render_aa = "OFF"
    sc.render.film_transparent = True
    sc.render.resolution_x = 960; sc.render.resolution_y = 540; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    cam = bpy.data.cameras.new("fit_cam"); co = bpy.data.objects.new("fit_cam", cam)
    sc.collection.objects.link(co); sc.camera = co
    cam.clip_start = 0.05; cam.clip_end = 20.0
    def load(path, half):
        """Картинка → массив (высота, ширина, 4), верх кадра — первая строка; half — уменьшить вдвое усреднением."""
        im = bpy.data.images.load(path, check_existing=False)
        w, h = im.size
        a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
        bpy.data.images.remove(im)
        a = a.reshape(h, w, 4)[::-1]
        if half:
            a = a.reshape(h // 2, 2, w // 2, 2, 4).mean(axis=(1, 3))
        return a
    ref = load(os.path.join(refs, img + ".png"), True)
    rmask = ref[:, :, :3].sum(axis=2) > 0.12
    sel = np.zeros(960, bool)
    for a, b in bands:
        sel[a // 2:b // 2] = True
    tmp = os.path.join(bpy.app.tempdir, "fit_cam.png")
    best = None
    rows = []
    def span(i, default):
        if len(argv) > i:
            a, b, st = [float(v) for v in argv[i].split(":")]
            return [a + st * k for k in range(int(round((b - a) / st)) + 1)]
        return default
    for elev in span(3, [-8, -6, -4, -2, 0, 2, 4, 6, 8]):
        for roll in span(4, [-0.6, -0.3, 0.0, 0.3, 0.6]):
            set_cam(co, cam, img, elev, roll)
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            m = load(tmp, False)[:, :, 3] > 0.5
            loc = None
            for dy in range(-10, 11):
                for dx in (-2, -1, 0, 1, 2):
                    mm_ = np.roll(np.roll(m, dy, axis=0), dx, axis=1)
                    err = np.logical_xor(mm_, rmask)[:, sel].sum()
                    if loc is None or err < loc[0]:
                        loc = (int(err), dy, dx)
            rows.append((loc[0], elev, roll, loc[1] * 2, loc[2] * 2))
            if best is None or loc[0] < best[0]:
                best = rows[-1]
    rows.sort()
    for r in rows[:12]:
        print("FIT err=%d elev=%+.1f roll=%+.2f сдвиг_вниз_пикс=%+d сдвиг_вправо_пикс=%+d" % r)
    print("BEST", best)


main()
