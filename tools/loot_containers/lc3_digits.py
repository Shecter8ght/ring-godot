"""Касса: вымышленные зелёные сегментные цифры «0.00» на окнах индикаторов (кассира и покупателя) — в развёртку набора по
картам геометрии: у каждого пикселя окна считается положение в плоскости экрана (оси — горизонталь мира и вертикаль,
нормаль к зрителю), в этих осях рисуется семисегментный текст. Результат:
  _asset_src/loot_containers/wear_v03/lc_cash_digits_alpha.png — маска цифр (в Painter слой цвета по ней, lc3_stacks.screens_layer);
  _asset_src/loot_containers/maps_v03/lc_cash/lc_cash_emissive.png — свечение (файл просмотра подключает как Emission; в карты
  Painter не входит — в нашем пресете glTF канала излучения нет).

  python -X utf8 -I tools/loot_containers/lc3_digits.py
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

SCREENS = ["КМ_дисплей_кассира_экран", "КМ_дисплей_покупателя_экран"]
# сегменты цифры 0 (a b c d e f), в координатах ячейки 0…1 × 0…1.8
SEG0 = [((0.12, 0.0), (0.88, 0.0)), ((0.95, 0.06), (0.95, 0.84)), ((0.95, 0.96), (0.95, 1.74)),
        ((0.12, 1.8), (0.88, 1.8)), ((0.05, 0.96), (0.05, 1.74)), ((0.05, 0.06), (0.05, 0.84))]


def text_image(w: int, h: int, text: str = "0.00") -> np.ndarray:
    """Семисегментные «0.00» справа, высота знака — 55 % окна; серая картинка 0…255."""
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    ch_h = h * 0.55
    sc = ch_h / 1.8
    pitch = 1.25 * sc
    x = w * 0.92
    y0 = h * 0.22
    thick = max(2, int(0.16 * sc))
    for c in reversed(text):
        if c == ".":
            x -= 0.35 * sc
            d.ellipse([x - thick, y0 + 1.8 * sc - thick, x + thick, y0 + 1.8 * sc + thick], fill=255)
            x -= 0.35 * sc
        else:
            x -= pitch
            for (a, b) in SEG0:
                d.line([(x + a[0] * sc, y0 + a[1] * sc), (x + b[0] * sc, y0 + b[1] * sc)], fill=255, width=thick)
    return np.array(im.filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(0.8)))


def main() -> None:
    g = Z.load_geo("lc_cash")
    pos, nrm = g["pos"], g["nrm"]
    h, w = pos.shape[:2]
    alpha = np.zeros((h, w), np.float32)
    for name in SCREENS:
        m = Z.FZ.core(Z.FZ.parts(g, name), 3)
        fr = m & (nrm[..., 1] < -0.3)
        if fr.sum() > 50:
            nd = nrm[fr].mean(0)
            nd /= np.linalg.norm(nd)
            m = m & ((nrm @ nd) > 0.97)           # только лицо окна: торцы и обратная сторона — без цифр
        pts = pos[m]
        if len(pts) < 50:
            print("нет окна", name)
            continue
        c = pts.mean(0)
        _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
        n = vt[2] if vt[2][1] < 0 else -vt[2]            # нормаль к зрителю (−Y)
        eh = np.array([1.0, 0.0, 0.0]) - n * n[0]
        eh /= np.linalg.norm(eh)
        ev = np.cross(n, eh)
        if ev[2] < 0:
            ev = -ev
        u = (pts - c) @ eh
        v = (pts - c) @ ev
        u0, u1 = np.percentile(u, [1, 99])
        v0, v1 = np.percentile(v, [1, 99])
        tw, th = 512, int(512 * (v1 - v0) / max(u1 - u0, 1e-6))
        th = max(th, 32)
        img = text_image(tw, th).astype(np.float32) / 255.0
        px = np.clip(((u - u0) / (u1 - u0) * (tw - 1)).astype(int), 0, tw - 1)
        py = np.clip(((v1 - v) / (v1 - v0) * (th - 1)).astype(int), 0, th - 1)
        alpha[m] = img[py, px]
        print(name, "пикселей", int(m.sum()), "размер окна, мм: %.0f × %.0f" % ((u1 - u0) * 1000, (v1 - v0) * 1000))
    a8 = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    out = ROOT / "_asset_src" / "loot_containers"
    (out / "wear_v03").mkdir(parents=True, exist_ok=True)
    (out / "maps_v03" / "lc_cash").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / "wear_v03" / "lc_cash_digits_alpha.png"), a8)
    em = np.zeros((h, w, 3), np.uint8)
    em[..., 1] = a8                                       # зелёный (BGR → G)
    em[..., 0] = (a8 * 0.12).astype(np.uint8)
    cv2.imwrite(str(out / "maps_v03" / "lc_cash" / "lc_cash_emissive.png"), em)
    print("готово, доля цифр %.4f" % (a8 > 128).mean())


if __name__ == "__main__":
    main()
