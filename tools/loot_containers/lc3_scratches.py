"""Сейф и ячейка: 2–3 короткие тонкие царапины у штурвала / ручки — в развёртку по картам геометрии, в плоскости двери
(круг 4: «должны быть видны на safe_dial.png»). Штрихи заданы смещениями от центра штурвала в мм (прямые или чуть дугой,
2–4 см, 2,5 мм толщиной); их рисунок повторяет царапины по ходу руки, цвет кладёт Painter (на ~22/255 светлее краски).
  _asset_src/loot_containers/wear_v03/<набор>_scr_alpha.png

  python -X utf8 -I tools/loot_containers/lc3_scratches.py
"""
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "loot_containers"))
import lc3_zones as Z  # noqa: E402

# набор: (деталь двери, деталь-ручка, штрихи [(x0, z0, x1, z1, изгиб)] в мм от центра ручки; z вверх)
SETS = {
    "lc_safe": ("СН_дверца", "СН_ручка_штурвал",
                [(-70, -26, -22, -48, 6), (24, -52, 76, -36, -5), (-82, 4, -42, 22, 4)]),
    "lc_cell": ("СЯ_дверца", "СЯ_ручка", [(-40, -14, -10, -24, 4), (14, -22, 44, -12, -3)]),
}


def main() -> None:
    for game, (door, handle, strokes) in SETS.items():
        g = Z.load_geo(game)
        pos, nrm = g["pos"], g["nrm"]
        h, w = pos.shape[:2]
        m = Z.FZ.core(Z.FZ.parts(g, door), 3) & (nrm[..., 1] < -0.9)
        hc = pos[Z.FZ.parts(g, handle)].mean(0)
        u = ((pos[..., 0] - hc[0]) * 1000.0)       # мм вправо от центра ручки
        v = ((pos[..., 2] - hc[2]) * 1000.0)       # мм вверх
        scale = 4.0                                 # пикселей рабочей картинки на мм
        size = 400
        img = Image.new("L", (size * 2, size * 2), 0)
        d = ImageDraw.Draw(img)
        for x0, z0, x1, z1, bend in strokes:
            n = 12
            pts = []
            for i in range(n + 1):
                t = i / n
                x = x0 + (x1 - x0) * t
                z = z0 + (z1 - z0) * t + bend * np.sin(np.pi * t)
                pts.append((size + x * scale / 1.0, size - z * scale / 1.0))
            d.line(pts, fill=255, width=int(5.5 * scale))
        a = np.array(img.resize((size * 2, size * 2))).astype(np.float32) / 255.0
        px = np.clip((size + u * scale).astype(int), 0, size * 2 - 1)
        py = np.clip((size - v * scale).astype(int), 0, size * 2 - 1)
        alpha = np.where(m, a[py, px], 0.0)
        cv2.imwrite(str(Z.OUT / f"{game}_scr_alpha.png"), (alpha * 255).astype(np.uint8))
        print(game, "доля царапин %.5f" % (alpha > 0.5).mean())


if __name__ == "__main__":
    main()
