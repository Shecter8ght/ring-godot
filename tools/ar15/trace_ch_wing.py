# AR-15 «ГРАНЬ-15»: обводка крыла рукоятки заряжания по образцу владельца (снимок сзади-сверху, рыжие крылья) →
# контур и окно в мм в системе модели → tools/ar15/ch_wing_trace.json; плюс наложение контура на снимок для сверки.
# python -X utf8 tools/ar15/trace_ch_wing.py <снимок> [наложение.png]
import json
import sys
from pathlib import Path

import cv2
import numpy as np

# масштаб снимка: поперёк — от края средней плиты (x 300 пикс) до конца крыла соответствует y 16.5 … 32 мм модели;
# вдоль оси снимок смотрит сзади-сверху — ось сжата, K_AXIAL подобран так, чтобы длина крыла была ~19 мм
PX_INNER, Y_INNER, Y_TIP = 300.0, 16.5, 32.6
K_AXIAL = 0.84
PY_FRONT = 182.0               # передняя кромка у плиты на снимке → x = CH_REAR + X_FRONT
X_FRONT = 10.4


def wing_masks(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    b, g, r = [img[:, :, k].astype(int) for k in range(3)]
    tan = (r > 110) & (r - b > 30) & (r >= g) & (g >= b) & (hsv[:, :, 1] > 50)
    m = (tan * 255).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return m


def main():
    src = sys.argv[1]
    img = cv2.imread(src)
    m = wing_masks(img)
    left = m.copy()
    left[:, 330:] = 0
    cnts, hier = cv2.findContours(left, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    # наружный контур — самый большой без родителя, окно — его самый большой ребёнок
    outer_i = max((i for i in range(len(cnts)) if hier[0][i][3] < 0), key=lambda i: cv2.contourArea(cnts[i]))
    kids = [i for i in range(len(cnts)) if hier[0][i][3] == outer_i]
    hole_i = max(kids, key=lambda i: cv2.contourArea(cnts[i]))
    px_per_mm = (PX_INNER - cnts[outer_i][:, 0, 0].min()) / (Y_TIP - Y_INNER)

    def to_mm(c, eps):
        c = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        pts = [((PY_FRONT - py) / (px_per_mm * K_AXIAL) + X_FRONT, (PX_INNER - px) / px_per_mm + Y_INNER) for px, py in c]
        return pts

    outer = to_mm(cnts[outer_i], 1.4)
    hole = to_mm(cnts[hole_i], 2.0)
    out = {"outer": outer, "hole": hole, "px_per_mm": px_per_mm, "k_axial": K_AXIAL,
           "note": "x — от CH_REAR вперёд (мм), y — наружу от оси (мм), левое крыло"}
    Path(__file__).with_name("ch_wing_trace.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TRACE outer", len(outer), "hole", len(hole), "px/mm", round(px_per_mm, 2))
    if len(sys.argv) > 2:
        vis = img.copy()
        cv2.drawContours(vis, [cv2.approxPolyDP(cnts[outer_i], 1.4, True)], -1, (0, 255, 0), 1)
        cv2.drawContours(vis, [cv2.approxPolyDP(cnts[hole_i], 2.0, True)], -1, (0, 0, 255), 1)
        cv2.imwrite(sys.argv[2], vis)


main()
