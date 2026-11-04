# ПП по мотивам KRISS Vector Gen II (wpn_smg_03): перенос контуров с заводских снимков KRISS USA (Vector SBR Gen 2 5.5″,
# чёрный, слева A и справа B, 1600 × 1000, почти ортография). Масштаб — по шагу планки MIL-STD-1913 (10 мм = 17.97 пикс,
# 1.797 пикс/мм; длина по снимку 608 мм против заводских 610 — 0.3 %).
# Оси модели: мм, +X к дулу, +Z вверх, −Y — правая сторона стрелка; начало — зеркало затвора на оси канала
# (дульный срез под колпачком резьбы минус ствол 5.5″ = 139.7 мм).
#   python -X utf8 tools/smg03/trace_photos.py <папка снимков> <папка вывода>
# Пишет: silhouette_A.json / silhouette_B.json — наружный контур и отверстия силуэта (мм, в осях модели; B зеркален,
# чтобы ложился на A), overlay_AB.png — A и зеркальный B наложением, grid_<участок>.png — участки снимков ×4
# с сеткой модели (линии через 5 мм, подписи через 10 мм) — по ним снимаются положения мелких деталей.
import json
import sys
from pathlib import Path

import cv2
import numpy as np

S = 1.797                       # пикс/мм
PHOTO_A = "orig_kv_sbr_5_5in_blk_30rd_A__83111.1707345817.jpg"
PHOTO_B = "orig_kv_sbr_5_5in_blk_30rd_B__86426.1707341769.jpg"
BORE_Y_A = 451.5                # ось канала на снимке A (середина колпачка и ствола)
MUZZLE_X_A = 256.0              # дульный срез под колпачком (A, пиксели)
BARREL_MM = 139.7
THRESH = 200


def imread(path):
    """cv2.imread не открывает пути с кириллицей на Windows — читаем байты сами."""
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite(path, img):
    ok, buf = cv2.imencode(Path(path).suffix, img)
    buf.tofile(str(path))


def a_to_model(px, py):
    x0 = MUZZLE_X_A + BARREL_MM * S
    return (x0 - px) / S, (BORE_Y_A - py) / S


def model_to_a(x, z):
    x0 = MUZZLE_X_A + BARREL_MM * S
    return x0 - x * S, BORE_Y_A - z * S


def mask(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m = (g < THRESH).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return m


def contours_mm(m, to_model, eps=0.6):
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer_i = max((i for i in range(len(cnts)) if hier[0][i][3] < 0), key=lambda i: cv2.contourArea(cnts[i]))
    holes = [i for i in range(len(cnts)) if hier[0][i][3] == outer_i and cv2.contourArea(cnts[i]) > 200]

    def conv(c):
        c = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        return [list(map(lambda v: round(v, 2), to_model(px, py))) for px, py in c]
    return {"outer": conv(cnts[outer_i]), "holes": [conv(cnts[i]) for i in holes]}


def align_b(mb, ma):
    """B — правая сторона: зеркалим по горизонтали и подбираем сдвиг, при котором силуэты совпадают лучше всего."""
    mb = cv2.flip(mb, 1)
    best = None
    for dy in range(-14, 15):
        for dx in range(-30, 31):
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            sh = cv2.warpAffine(mb, M, (mb.shape[1], mb.shape[0]))
            inter = np.logical_and(sh > 0, ma > 0).sum()
            uni = np.logical_or(sh > 0, ma > 0).sum()
            iou = inter / uni
            if best is None or iou > best[0]:
                best = (iou, dx, dy, sh)
    return best


def grid_crop(img, x0, x1, z0, z1, k, out):
    """Участок снимка A между x0..x1, z0..z1 (мм модели) ×k с сеткой модели."""
    pa, pb = model_to_a(x1, z1), model_to_a(x0, z0)
    l, t = int(min(pa[0], pb[0])) - 2, int(min(pa[1], pb[1])) - 2
    r, b = int(max(pa[0], pb[0])) + 2, int(max(pa[1], pb[1])) + 2
    crop = cv2.resize(img[t:b, l:r], None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    crop = cv2.convertScaleAbs(crop, alpha=1.9, beta=10)      # тёмная деталь на тёмном — поднять контраст
    for xm in range(int(x0) // 5 * 5, int(x1) + 6, 5):
        px = (model_to_a(xm, 0)[0] - l) * k
        major = xm % 10 == 0
        cv2.line(crop, (int(px), 0), (int(px), crop.shape[0]), (0, 160, 255) if major else (0, 90, 160), 1)
        if major:
            cv2.putText(crop, str(xm), (int(px) + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 255), 1)
    for zm in range(int(z0) // 5 * 5, int(z1) + 6, 5):
        py = (model_to_a(0, zm)[1] - t) * k
        major = zm % 10 == 0
        cv2.line(crop, (0, int(py)), (crop.shape[1], int(py)), (255, 160, 0) if major else (160, 90, 0), 1)
        if major:
            cv2.putText(crop, str(zm), (2, int(py) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 0, 0), 1)
    imwrite(out, crop)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    ia = imread(src / PHOTO_A)
    ib = imread(src / PHOTO_B)
    ma, mb = mask(ia), mask(ib)
    sa = contours_mm(ma, a_to_model)
    (dst / "silhouette_A.json").write_text(json.dumps(sa, ensure_ascii=False), encoding="utf-8", newline="\n")
    iou, dx, dy, mb_al = align_b(mb, ma)
    print(f"B зеркальный на A: совпадение {iou:.4f}, сдвиг {dx}, {dy} пикс")
    sb = contours_mm(mb_al, a_to_model)
    (dst / "silhouette_B.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8", newline="\n")
    ov = np.full(ia.shape, 255, np.uint8)
    ov[ma > 0] = (60, 60, 200)
    ov[mb_al > 0] = (ov[mb_al > 0] * 0.5 + np.array((200, 120, 40)) * 0.5).astype(np.uint8)
    imwrite(dst / "overlay_AB.png", ov)
    # участки для снятия мелких деталей
    parts = {"front": (-30, 70, -80, 60), "mid": (-120, -20, -100, 60), "rear": (-230, -110, -100, 60),
             "low": (-150, -40, -200, -60), "grip": (-260, -150, -180, -30)}
    for nm, (x0, x1, z0, z1) in parts.items():
        grid_crop(ia, x0, x1, z0, z1, 4, dst / f"grid_A_{nm}.png")
    # B зеркальный — те же участки
    ib_al = cv2.warpAffine(cv2.flip(ib, 1), np.float32([[1, 0, dx], [0, 1, dy]]), (ib.shape[1], ib.shape[0]),
                           borderValue=(255, 255, 255))
    for nm, (x0, x1, z0, z1) in parts.items():
        grid_crop(ib_al, x0, x1, z0, z1, 4, dst / f"grid_B_{nm}.png")
    print("outer A", len(sa["outer"]), "holes", [len(h) for h in sa["holes"]])


main()
