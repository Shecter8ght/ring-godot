# ПКП: наложение проверочного кадра (shots.py, виды ref13 / ref14 — камерами образцов) на рендер-образец владельца.
#   python -X utf8 tools/pkp/compare.py <папка кадров> <папка образцов refs/owner> <папка вывода> [13 14]
#       [--crop x0 y0 x1 y1] [--zoom 2] [--name имя]
# Пишет cmp_<N>_blend.png (пополам) и cmp_<N>_edge.png (образец серым, кромки модели красным, кромки образца
# зелёным: совпавшие места жёлтые).
import os
import sys

import numpy as np
from PIL import Image, ImageFilter


def edges(im, thr):
    g = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1])); gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    return (gx + gy) > thr


def main():
    a = sys.argv[1:]
    shots, refs, out = a[0], a[1], a[2]
    which = []; crop = None; zoom = 1.0; name = ""
    i = 3
    while i < len(a):
        if a[i] == "--crop": crop = tuple(int(v) for v in a[i + 1:i + 5]); i += 5
        elif a[i] == "--zoom": zoom = float(a[i + 1]); i += 2
        elif a[i] == "--name": name = a[i + 1]; i += 2
        else: which.append(a[i]); i += 1
    os.makedirs(out, exist_ok=True)
    for n in which or ["13", "14"]:
        ref = Image.open(os.path.join(refs, n + ".png")).convert("RGB")
        shot = Image.open(os.path.join(shots, f"ref{n}.png")).convert("RGB").resize(ref.size, Image.LANCZOS)
        if crop:
            ref = ref.crop(crop); shot = shot.crop(crop)
        if zoom != 1.0:
            sz = (int(ref.width * zoom), int(ref.height * zoom))
            ref = ref.resize(sz, Image.LANCZOS); shot = shot.resize(sz, Image.LANCZOS)
        Image.blend(ref, shot, 0.5).save(os.path.join(out, f"cmp_{n}{name}_blend.png"))
        r = np.asarray(ref).astype(np.float32)
        base = np.clip(r * 0.9, 0, 255)
        er = edges(ref, 14.0); es = edges(shot, 14.0)
        img = base.copy()
        img[er] = img[er] * 0.3 + np.array([0, 200, 60]) * 0.7
        img[es] = img[es] * 0.2 + np.array([255, 40, 40]) * 0.8
        both = er & es
        img[both] = (255, 230, 60)
        Image.fromarray(img.astype(np.uint8)).save(os.path.join(out, f"cmp_{n}{name}_edge.png"))
        print("CMP", n, os.path.join(out, f"cmp_{n}{name}_edge.png"))


main()
