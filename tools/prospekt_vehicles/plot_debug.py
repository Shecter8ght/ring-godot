"""Отладка раскладки: контуры несобравшихся панелей (uv вида) → картинка."""
import sys
import numpy as np
from PIL import Image, ImageDraw
z = np.load(sys.argv[1])
groups = {}
for k in z.files:
    groups.setdefault(k.split("_outer")[0].split("_hole")[0], []).append((k, z[k]))
for gname, items in groups.items():
    allp = np.vstack([v for _, v in items])
    lo, hi = allp.min(0), allp.max(0)
    sc = 1400 / max(hi - lo)
    img = Image.new("RGB", (int((hi - lo)[0] * sc) + 40, int((hi - lo)[1] * sc) + 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, v in items:
        pts = [((x - lo[0]) * sc + 20, (hi[1] - y) * sc + 20) for x, y in v]
        d.line(pts + [pts[0]], fill=(200, 0, 0) if "outer" in k else (0, 0, 200), width=2)
        d.ellipse([pts[0][0] - 5, pts[0][1] - 5, pts[0][0] + 5, pts[0][1] + 5], outline=(0, 150, 0))
    out = sys.argv[2] + f"_{gname}.png"
    img.save(out)
    print(out)
