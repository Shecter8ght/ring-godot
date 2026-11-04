# ПП по мотивам KRISS Vector: контур складного приклада (как KVA-FSBL00 — для Gen I / Gen II до 2017 с шарниром
# на коробке) со снимка товара (refs/web/folding_stock_KVA-FSBL00.jpg, вид слева, 1200 × 900, лёгкая перспектива).
# Масштаб: от оси шарнира до тыльной грани затыльника — 211 мм (TFB: длина CRB 34.8″ с прикладом и 26.5″ сложенным —
# 8.3″ = 211 мм; Wikipedia SMG: 24.3″ / 16″ — те же 8.3″). Верх приклада — на уровне верха коробки (Z 46.5).
#   python -X utf8 tools/smg03/trace_stock.py <снимок> <наложение.png>
# Пишет tools/smg03/data/stock_profile.json: контуры (мм модели): ложе (body) и затыльник (pad), окно в ложе.
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PIN_X_PX = 47.0          # ось шарнира на снимке (вертикальный штифт слева)
END_X_PX = 1192.0        # тыльная грань затыльника
TOP_Y_PX = 62.0          # верх ложа у шарнира
LEN_MM = 211.0
HINGE_X = -271.0         # ось шарнира в модели (5 мм позади торца коробки X −266)
TOP_Z = 51.0
X_SHIFT = 4.0           # ложе ближе к торцу коробки: зазор 1.7 мм (проверка 04.11)
PAD_X_PX = 1032.0        # передняя грань резинового затыльника (по снимку)


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def main():
    img = imread(sys.argv[1])
    s = (END_X_PX - PIN_X_PX) / LEN_MM
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m = (g < 200).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    # подпись EVIKE внизу справа и шарнир со штифтом слева — убираем из маски ложа
    m[855:, 940:] = 0
    m[:, :int(PIN_X_PX + 4)] = 0

    def to_mm(px, py):
        return round(HINGE_X + X_SHIFT - (px - PIN_X_PX) / s, 2), round(TOP_Z - (py - TOP_Y_PX) / s, 2)
    out = {"scale_px_mm": s, "hinge_x": HINGE_X}
    for nm, (x0, x1) in {"body": (0, PAD_X_PX), "pad": (PAD_X_PX - 6, 1200)}.items():
        mm = m.copy()
        mm[:, :int(x0)] = 0
        mm[:, int(x1):] = 0
        if nm == "body":
            # у шарнира — вырезы под проушины коробки сверху и снизу кулака (Z 18.5…28.1 и 37.4…47.5, до X −276.2)
            for za, zb in ((18.5, 28.1), (42.1, 53.0)):
                x_px = int(PIN_X_PX + (HINGE_X + X_SHIFT - (-278.2)) * s)
                mm[int(TOP_Y_PX + (TOP_Z - zb) * s):int(TOP_Y_PX + (TOP_Z - za) * s), :x_px] = 0
        # углы контура — скруглить в плоскости (радиус с запасом над радиусом кромок приклада в 3D)
        r = int(round((4.4 if nm == "body" else 3.4) * s))
        el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        mm = cv2.morphologyEx(cv2.morphologyEx(mm, cv2.MORPH_OPEN, el), cv2.MORPH_CLOSE, el)
        cnts, hier = cv2.findContours(mm, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        oi = max((i for i in range(len(cnts)) if hier[0][i][3] < 0), key=lambda i: cv2.contourArea(cnts[i]))
        holes = [i for i in range(len(cnts)) if hier[0][i][3] == oi and cv2.contourArea(cnts[i]) > 2000]
        conv = lambda c: [to_mm(px, py) for px, py in cv2.approxPolyDP(c, 1.2, True)[:, 0, :].astype(float)]
        out[nm] = {"outer": conv(cnts[oi]), "holes": [conv(cnts[i]) for i in holes]}
        print(nm, len(out[nm]["outer"]), [len(h) for h in out[nm]["holes"]])
    p = Path(__file__).with_name("data") / "stock_profile.json"
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
    if len(sys.argv) > 2:
        vis = img.copy()
        for nm in ("body", "pad"):
            for poly in [out[nm]["outer"]] + out[nm]["holes"]:
                pts = np.array([((HINGE_X + X_SHIFT - x) * s + PIN_X_PX, (TOP_Z - z) * s + TOP_Y_PX) for x, z in poly], np.int32)
                cv2.polylines(vis, [pts], True, (0, 0, 255) if nm == "body" else (0, 160, 0), 2)
        ok, buf = cv2.imencode(".png", vis)
        buf.tofile(sys.argv[2])
    xs = [p[0] for p in out["body"]["outer"] + out["pad"]["outer"]]
    zs = [p[1] for p in out["body"]["outer"] + out["pad"]["outer"]]
    print("X", min(xs), max(xs), "Z", min(zs), max(zs))


main()
