"""Купе Ильи: наложение контуров чертежа на ортогональные снимки check_views.py.

    python -X utf8 tools/coupe_ilya/overlay.py <папка снимков> <префикс>

Красным — внешний контур вида с чертежа (обычный CLE; ширина по плану расширена под CLE 53
только в модели, поэтому на виде сверху и спереди модель шире красной линии у крыльев).
Пишет <префикс>_<вид>_overlay.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import drawing  # noqa: E402

folder = Path(sys.argv[1])
prefix = sys.argv[2]
views = json.loads((folder / f"{prefix}_views.json").read_text(encoding="utf-8"))
ol = drawing.outlines(drawing.load_layers())


def to_px(view: dict, u: float, v: float) -> tuple[float, float]:
    """(u — вправо в кадре, v — вверх в кадре), метры относительно центра → пиксели."""
    w, h = view["res"]
    k = w / view["width_m"]
    return w / 2 + u * k, h / 2 - v * k


for name, view in views.items():
    img_path = folder / f"{prefix}_{name}.png"
    if not img_path.exists():
        continue
    im = Image.open(img_path).convert("RGB")
    dr = ImageDraw.Draw(im)
    cx, cy, cz = view["center"]
    if name == "side":
        # Камера слева (+X): вправо в кадре — +Y (корма), вверх — Z
        pts = [to_px(view, y - cy, z - cz) for y, z in ol["side"]]
    elif name == "front":
        # Спереди (−Y): вправо в кадре — +X (левый борт машины), вверх — Z
        pts = [to_px(view, x - cx, z - cz) for x, z in ol["front"]]
    elif name == "rear":
        pts = [to_px(view, -(x - cx), z - cz) for x, z in ol["rear"]]
    elif name == "top":
        # Сверху: вправо — +Y (корма), вверх в кадре — −X
        pts = [to_px(view, y - cy, -(x - cx)) for x, y in ol["plan"]]
    else:
        continue
    dr.line(pts, fill=(230, 30, 30), width=2)
    out = folder / f"{prefix}_{name}_overlay.png"
    im.save(out)
    print(out)
