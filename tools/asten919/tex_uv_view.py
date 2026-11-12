# АСТЕН-919: картинка раскладки развёртки набора (обычный Python с PIL) — каждая деталь своим цветом.
#   python -X utf8 tools/asten919/tex_uv_view.py <набор>_tris.npz <out.png> [размер 2048]
import colorsys
import sys

import numpy as np
from PIL import Image, ImageDraw

d = np.load(sys.argv[1])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2048
im = Image.new("RGB", (n, n), (18, 18, 20))
dr = ImageDraw.Draw(im)
names = list(d["names"])
tri = d["tri"]
obj = d["obj"]
for i, nm in enumerate(names):
    r, g, b = colorsys.hsv_to_rgb((i * 0.381966) % 1.0, 0.55, 0.95)
    col = (int(r * 255), int(g * 255), int(b * 255))
    for t in tri[obj == i]:
        dr.polygon([(float(u) * n, (1.0 - float(v)) * n) for u, v in t], fill=col)
    a = tri[obj == i]
    area = float(np.abs(0.5 * ((a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 2, 0] - a[:, 0, 0]) * (a[:, 1, 1] - a[:, 0, 1]))).sum())
    print(f"{nm:24s} {area * 100:5.1f} % атласа, треугольников {len(a)}")
im.save(sys.argv[2])
