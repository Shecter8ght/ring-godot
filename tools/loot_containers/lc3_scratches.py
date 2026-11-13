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
        hc = pos[Z.FZ.parts(g, handle)].mean(0)
        # лицо дверцы — сетка с точным именем (у сейфа есть ещё «<имя>__внутри» — изнанка, её не берём)
        ids = [i for i, n in g["names"].items() if n == door]
        dm = Z.FZ.core(np.isin(g["part_id"], ids), 3)
        # развёртка снята на открытой дверце: плоскость лица определяем по самой дверце — нормаль лица = преобладающая
        # нормаль пикселей дверцы у ручки (ближе 20 см), оси листа: «вправо» = [Z × n], «вверх» = Z
        # лицо — ближайшие к ручке пиксели дверцы (ручка стоит прямо на лице): их нормаль и смещение задают плоскость
        idx = np.argwhere(dm)
        dd = np.linalg.norm(pos[dm] - hc, axis=-1)
        sel = idx[np.argsort(dd)[:3000]]
        ns = nrm[sel[:, 0], sel[:, 1]]
        import collections
        key = collections.Counter(map(tuple, np.round(ns, 1))).most_common(1)[0][0]
        n0 = ns[np.all(np.round(ns, 1) == key, axis=1)].mean(0)
        n0 = n0 / np.linalg.norm(n0)
        off = float(np.median(pos[sel[:, 0], sel[:, 1]] @ n0))
        eu = np.cross([0.0, 0.0, 1.0], n0)
        eu /= np.linalg.norm(eu)
        d3 = pos - hc
        m = dm & ((nrm @ n0) > 0.97) & (np.abs(pos @ n0 - off) < 0.003)
        u = (d3 @ eu) * 1000.0
        v = d3[..., 2] * 1000.0
        scale = 4.0                                 # пикселей рабочей картинки на мм
        size = 400
        img = Image.new("L", (size * 2, size * 2), 0)
        d = ImageDraw.Draw(img)
        for x0, z0, x1, z1, bend in strokes:
            x0, z0, x1, z1 = x0 * 0.6, z0 * 0.6, x1 * 0.6, z1 * 0.6
            n = 24
            pts = []
            for i in range(n + 1):
                t = i / n
                x = x0 + (x1 - x0) * t
                z = z0 + (z1 - z0) * t + bend * np.sin(np.pi * t)
                pts.append((size + x * scale / 1.0, size - z * scale / 1.0))
            d.line(pts, fill=255, width=int(2.6 * scale))
        a = np.array(img.resize((size * 2, size * 2))).astype(np.float32) / 255.0
        px = np.clip((size + u * scale).astype(int), 0, size * 2 - 1)
        py = np.clip((size - v * scale).astype(int), 0, size * 2 - 1)
        alpha = np.where(m, a[py, px], 0.0)
        cv2.imwrite(str(Z.OUT / f"{game}_scr_alpha.png"), (alpha * 255).astype(np.uint8))
        print(game, "доля царапин %.5f" % (alpha > 0.5).mean())


if __name__ == "__main__":
    main()
