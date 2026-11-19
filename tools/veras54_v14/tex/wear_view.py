"""ВЕРАС-54 v14, износ: проверка мест без Painter — карты мест набора (wear_place.py) точками в ортогональном виде
сбоку / сверху / снизу в мм (по картам положения wear_maps.py): серое — деталь, цветное — место.

    python -X utf8 tools/veras54_v14/tex/wear_view.py <набор> <место>[,<место>…] [right|left|top|bottom] [мм/пикс]
      → _asset_src/veras54_v14/tex/wear/view/<набор>_<вид>.png
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wear_place as W  # noqa: E402

VIEWS = {"right": (0, 2, (0, -1, 0), False), "left": (0, 2, (0, 1, 0), True), "top": (0, 1, (0, 0, 1), False),
         "bottom": (0, 1, (0, 0, -1), False), "rear": (1, 2, (-1, 0, 0), False), "front": (1, 2, (1, 0, 0), True)}
COLORS = [(255, 80, 40), (60, 200, 255), (255, 220, 0), (120, 255, 90), (255, 90, 255)]


def main():
    a = sys.argv[1:]
    name, kinds = a[0], a[1].split(",")
    view = a[2] if len(a) > 2 else "right"
    mmpx = float(a[3]) if len(a) > 3 else 0.25
    names, obj, pos, nrm = W.load(name)
    n = pos.shape[0]
    ia, ib, d, flip = VIEWS[view]
    d = np.array(d, np.float32)
    vis = (obj >= 0) & ((nrm * d).sum(-1) > 0.05)
    depth = (pos * d).sum(-1)
    u, v = pos[..., ia], pos[..., ib]
    if flip:
        u = -u
    uu, vv = u[vis], v[vis]
    u0, v1 = uu.min(), vv.max()
    W_, H_ = int((uu.max() - u0) / mmpx) + 2, int((v1 - vv.min()) / mmpx) + 2
    px = ((u[vis] - u0) / mmpx).astype(int)
    py = ((v1 - v[vis]) / mmpx).astype(int)
    dep = depth[vis]
    order = np.argsort(dep)                 # ближе к глазу — позже (поверх)
    img = np.zeros((H_, W_, 3), np.uint8) + 25
    shade = (90 + 80 * np.clip((nrm[vis] * np.array([0.3, -0.5, 0.8])).sum(-1), 0, 1)).astype(np.uint8)
    col = np.stack([shade] * 3, -1).astype(np.float32)
    for k, kind in enumerate(kinds):
        m = np.asarray(Image.open(f"{W.OUT}/{name}_{kind}.png").convert("L").resize((n, n)), np.float32)[vis] / 255.0
        c = np.array(COLORS[k % len(COLORS)], np.float32)
        col = col * (1 - m[:, None]) + c * m[:, None]
    img[py[order], px[order]] = col[order].astype(np.uint8)
    os.makedirs(f"{W.OUT}/view", exist_ok=True)
    out = f"{W.OUT}/view/{name}_{view}.png"
    Image.fromarray(img).save(out)
    print(out, img.shape)


if __name__ == "__main__":
    main()
