# АСТЕН-919: сверка силуэта — вид слева из shots.py (ортография, вид «left») накладывается на снимок ref_23
# в одном масштабе (масштаб и начало координат снимка — data/profiles.json от trace_photo.py).
#   python -X utf8 tools/asten919/compare.py <папка референсов> <left.png> <папка вывода>
# Пишет compare_left_side.png (снимок и модель рядом) и compare_left_overlay.png (наложение 50 % + контур модели).
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
VIEW_C = (20.0, -55.0)      # центр вида «left» в shots.py, мм
VIEW_W = 230.0              # ширина кадра, мм


def imread(p):
    return np.array(Image.open(p).convert("RGB"))[:, :, ::-1].copy()


def imwrite(p, img):
    ok, buf = cv2.imencode(Path(p).suffix, img)
    buf.tofile(str(p))


def main():
    refs = Path(sys.argv[1]); shot = Path(sys.argv[2]); out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    prof = json.load(open(HERE / "data" / "profiles.json", encoding="utf-8"))
    sp = prof["scale_px_mm"]; x0, z0 = prof["origin_px"]
    photo = imread(refs / prof["photo"])
    ren = imread(shot)
    H, W = ren.shape[:2]
    s = W / VIEW_W
    # точка модели (X, Z) → пиксель рендера: u = W/2 − (X − cx)·s, v = H/2 − (Z − cz)·s
    # пиксель снимка (px, py) → модель: X = (x0 − px)/sp, Z = (z0 − py)/sp
    k = s / sp
    M = np.array([[k, 0, W / 2 - (x0 / sp - VIEW_C[0]) * s], [0, k, H / 2 - (z0 / sp - VIEW_C[1]) * s]], np.float32)
    warped = cv2.warpAffine(photo, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    # контур модели: всё, что не фон рендера
    bg = ren[5, 5].astype(int)
    mask = (np.abs(ren.astype(int) - bg).sum(axis=2) > 18).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    over = cv2.addWeighted(warped, 0.5, ren, 0.5, 0)
    cv2.drawContours(over, cnts, -1, (0, 0, 255), 1)
    imwrite(out / "compare_left_overlay.png", over)
    only = warped.copy()
    cv2.drawContours(only, cnts, -1, (0, 0, 255), 1)
    imwrite(out / "compare_left_contour.png", only)
    imwrite(out / "compare_left_side.png", np.vstack([warped, ren]))
    print("COMPARE", out)


main()
