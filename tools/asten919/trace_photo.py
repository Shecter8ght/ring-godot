# АСТЕН-919 (прототип — Glock 17 Gen4 MOS): перенос контуров с бокового снимка владельца ref_23.webp
# (Glock 22 Gen4, оливковая рамка, левая сторона, почти ортография; рамка и затвор G22 Gen4 снаружи те же, что у G17 Gen4).
# Рамка отделяется по цвету (оливковая), затвор — по яркости на белом фоне. Масштаб — по длине затвора 186 мм (Glock).
# Оси модели: мм, +X к дулу, +Z вверх, −Y — правая сторона стрелка; начало — зеркало затвора на оси канала ствола
# (зеркало в 73 мм от заднего торца затвора: 186 − (114 − 1), ствол выступает из затвора на ~1 мм).
#   python -X utf8 tools/asten919/trace_photo.py <папка референсов> <папка вывода>
# Пишет: data/profiles.json (контур рамки, проём скобы, тёмные детали на рамке, габарит затвора — мм), в папку вывода —
# overlay.png (контуры поверх снимка) и grid_<участок>.png (участки ×4 с сеткой модели: линии через 5 мм).
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
PHOTO = "ref_23.webp"
SLIDE_LEN = 186.0
BREECH_FROM_REAR = 73.0
BORE_BELOW_TOP = 10.8          # ось канала ниже верха затвора (оценка: ref_13 — 11.3, толщина крыши + радиус ствола — 10.3)


def load(path):
    return np.array(Image.open(path).convert("RGB"))[:, :, ::-1].copy()


def imwrite(path, img):
    ok, buf = cv2.imencode(Path(path).suffix, img)
    buf.tofile(str(path))


def masks(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    H, S, V = (hsv[..., k].astype(int) for k in range(3))
    olive = ((H > 28) & (H < 58) & (S > 28) & (V > 35) & (V < 215)).astype(np.uint8) * 255
    fg = (((V < 175)) | (olive > 0)).astype(np.uint8) * 255
    return olive, fg, V


def main():
    ref_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    im = load(ref_dir / PHOTO)
    olive, fg, V = masks(im)
    h, w = olive.shape

    # --- затвор: верх, торцы (строки в середине высоты затвора: тени туда не попадают) ---
    cols = np.where(fg[90:150].mean(axis=0) > 128)[0]
    # задний торец — последний столбец; передний — где начинается полная высота (ствол выступает левее)
    x_rear = int(cols.max())
    top_by_col = np.array([np.argmax(fg[:, x] > 0) if fg[:, x].any() else h for x in range(w)])
    y_top = float(np.median(top_by_col[300:700]))
    # передний торец — по строкам над стволом и под скруглением верхней кромки (ствол выступает левее и ниже)
    ya = int(y_top + 12); yb = int(y_top + 20)
    x_front = int(np.where(fg[ya:yb].mean(axis=0) > 128)[0].min())
    scale = (x_rear - x_front) / SLIDE_LEN      # пикс/мм
    x0 = x_rear - BREECH_FROM_REAR * scale       # зеркало затвора
    z0 = y_top + BORE_BELOW_TOP * scale          # ось канала

    def to_mm(px, py):
        return (x0 - px) / scale, (z0 - py) / scale

    def to_px(x, z):
        return x0 - x * scale, z0 - z * scale

    # --- рамка: оливковая область, мелкие дыры (точки, тени фактуры) закрыть ---
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(olive, cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    oi = max((i for i in range(len(cnts)) if hier[0][i][3] < 0), key=lambda i: cv2.contourArea(cnts[i]))
    holes = sorted((i for i in range(len(cnts)) if hier[0][i][3] == oi and cv2.contourArea(cnts[i]) > 25),
                   key=lambda i: -cv2.contourArea(cnts[i]))

    def conv(c, eps=0.45):
        c = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        return [[round(v, 2) for v in to_mm(px, py)] for px, py in c]

    feats = []
    for i in holes:
        c = cnts[i]
        x, y, bw, bh = cv2.boundingRect(c)
        cx, cz = to_mm(x + bw / 2, y + bh / 2)
        feats.append({"center": [round(cx, 2), round(cz, 2)], "size": [round(bw / scale, 2), round(bh / scale, 2)],
                      "area_mm2": round(cv2.contourArea(c) / scale ** 2, 1), "contour": conv(c, 0.35)})
    data = {
        "photo": PHOTO, "scale_px_mm": round(scale, 4), "origin_px": [round(x0, 2), round(z0, 2)],
        "slide": {"x_rear": -BREECH_FROM_REAR, "x_front": SLIDE_LEN - BREECH_FROM_REAR, "z_top": BORE_BELOW_TOP,
                  "px": {"x_rear": x_rear, "x_front": x_front, "y_top": y_top}},
        "frame_outer": conv(cnts[oi]),
        "frame_holes": feats,
    }
    (HERE / "data").mkdir(exist_ok=True)
    with open(HERE / "data" / "profiles.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("SCALE", round(scale, 4), "px/mm; slide px", x_front, x_rear, "top", y_top, "origin px", round(x0, 1), round(z0, 1))
    print("FRAME pts", len(data["frame_outer"]), "holes", len(feats))
    for ft in feats[:14]:
        print("  hole", ft["center"], ft["size"], ft["area_mm2"])
    xs = [p[0] for p in data["frame_outer"]]; zs = [p[1] for p in data["frame_outer"]]
    print("FRAME bbox X", min(xs), max(xs), "Z", min(zs), max(zs))

    # --- наложение и участки с сеткой ---
    ov = im.copy()
    cv2.drawContours(ov, [cnts[oi]], -1, (0, 0, 255), 1)
    for i in holes:
        cv2.drawContours(ov, [cnts[i]], -1, (255, 0, 255), 1)
    imwrite(out_dir / "overlay.png", ov)
    K = 4
    big = cv2.resize(im, (w * K, h * K), interpolation=cv2.INTER_CUBIC)
    for xm in range(-90, 125, 5):
        px, _ = to_px(xm, 0)
        col = (0, 0, 255) if xm % 10 == 0 else (0, 160, 255)
        cv2.line(big, (int(px * K), 0), (int(px * K), h * K), col, 1)
        if xm % 10 == 0:
            for yy in range(40, h * K, 500):
                cv2.putText(big, str(xm), (int(px * K) + 3, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    for zm in range(-135, 25, 5):
        _, py = to_px(0, zm)
        col = (255, 0, 0) if zm % 10 == 0 else (255, 160, 0)
        cv2.line(big, (0, int(py * K)), (w * K, int(py * K)), col, 1)
        if zm % 10 == 0:
            for xx in range(40, w * K, 600):
                cv2.putText(big, str(zm), (xx, int(py * K) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    regions = {"front": (-5, 125, -40, 18), "mid": (-45, 45, -50, 18), "rear": (-95, -15, -50, 18),
               "guard": (-25, 50, -70, -10), "grip_top": (-100, -20, -80, -10), "grip_low": (-115, -30, -135, -65)}
    for name, (xa, xb, za, zb) in regions.items():
        pxa, pya = to_px(xb, zb); pxb, pyb = to_px(xa, za)
        crop = big[max(0, int(pya * K)):int(pyb * K), max(0, int(pxa * K)):int(pxb * K)]
        imwrite(out_dir / f"grid_{name}.jpg", crop)


main()
