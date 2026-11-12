"""Контейнеры для лута, v02: структурные карты признаков конструкции в развёртке — строчки ткани, сварной валик, точки контактной
сварки. Острова развёртки = выкроенные панели, их границы — настоящие швы, поэтому признаки кладутся вдоль границ острова:
расстояние до границы и длина дуги ближайшей точки границы (cv2.distanceTransformWithLabels) дают и профиль, и пунктир.

  python -X utf8 tools/loot_containers/lc2_struct.py [набор …]    # → _asset_src/loot_containers/maps_v02/<набор>/<набор>_struct.png
Вход — uv_dump.json (lc2_dump_uv.py). Каналы: R — нить строчки (0..1), G — высота 0,5 = ровно (валик выше, ямка ниже), B — 0.
Масштаб в мм — по площади острова в 3D против площади в UV (у каждого объекта свой).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "_asset_src" / "loot_containers"
SPEC = Path("E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/finish-spec.json")
RES = {"lc_safe": 4096, "lc_cell": 2048, "lc_gun": 4096, "lc_file": 4096, "lc_cash": 4096, "lc_bag": 4096, "lc_aid": 2048}

# слот → вид признака
KIND = {"bag_cloth": "stitch2", "bag_lining": "stitch1", "bag_webbing": "web", "bag_tape": "stitch1",
        "safe_body_out": "bead", "cell_body": "spot", "gun_body": "spot", "file_body": "spot", "aid_body": "spot"}
BEAD_OK = ("корпус", "рама", "дверца")
BEAD_NO = ("__внутри", "петли", "механизм", "трейзер", "полка")


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def object_maps(polys, res, area3d_m2):
    """Маска острова, плотность пикс/мм, обрезка по габариту."""
    pts_all = [np.array([[u * res, (1 - v) * res] for u, v in p["uv"]]) for p in polys]
    allp = np.concatenate(pts_all)
    x0, y0 = np.floor(allp.min(0)).astype(int) - 8
    x1, y1 = np.ceil(allp.max(0)).astype(int) + 8
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, res), min(y1, res)
    w, h = x1 - x0, y1 - y0
    if w < 20 or h < 20:
        return None
    mask = np.zeros((h, w), np.uint8)
    uv_area = 0.0
    for pts in pts_all:
        q = ((pts - [x0, y0]) * 16).astype(np.int32)
        cv2.fillPoly(mask, [q], 255, lineType=cv2.LINE_8, shift=4)
        x, y = pts[:, 0], pts[:, 1]
        uv_area += 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    pxmm = (uv_area / max(area3d_m2 * 1e6, 1e-9)) ** 0.5
    return mask, (x0, y0), pxmm


def features(mask, pxmm, kind, name):
    """Возвращает (R, G) float32 в размере маски."""
    h, w = mask.shape
    cs, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    S = np.zeros((h, w), np.float32)
    border = np.zeros((h, w), np.uint8)
    for c in cs:
        c = c[:, 0, :]
        if len(c) < 6:
            continue
        seg = np.hypot(*np.diff(np.vstack([c, c[:1]]), axis=0).T)
        s = np.concatenate([[0], np.cumsum(seg)[:-1]]) / pxmm
        S[c[:, 1], c[:, 0]] = s + 0.001
        border[c[:, 1], c[:, 0]] = 1
    ys, xs = np.nonzero(border)
    if len(ys) == 0:
        return np.zeros((h, w), np.float32), np.full((h, w), 0.5, np.float32)
    inv = np.where(border > 0, 0, 255).astype(np.uint8)
    dist, lab = cv2.distanceTransformWithLabels(inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    table = np.zeros(lab.max() + 2, np.float32)
    table[lab[ys, xs]] = S[ys, xs]
    s_mm = table[lab]
    d = dist / pxmm
    inside = mask > 0
    R = np.zeros((h, w), np.float32)
    G = np.full((h, w), 0.5, np.float32)
    if kind in ("stitch2", "stitch1", "web"):
        pitch, on = 3.4, 2.5
        dash = (np.mod(s_mm, pitch) < on).astype(np.float32)
        dash = np.minimum(dash, smooth(np.mod(s_mm, pitch), 0.0, 0.5) + 0.0) * 1.0 + 0 * dash
        dash = (smooth(np.mod(s_mm, pitch), 0.0, 0.45) * (1 - smooth(np.mod(s_mm, pitch), on - 0.5, on))).astype(np.float32)
        lines = {"stitch2": (3.0, 6.0), "stitch1": (2.6,), "web": (2.2,)}[kind]
        thr = 0.0
        for d0 in lines:
            thr = np.maximum(thr, 1 - smooth(np.abs(d - d0), 0.28, 0.62))
        R = (thr * dash * inside).astype(np.float32)
        G = 0.5 + 0.20 * R
        # лёгкая складка (ужим ткани) вдоль шва: ткань собирается у строчки
        G += 0.07 * (1 - smooth(np.abs(d - (lines[0] + 1.2)), 0.0, 1.8)) * inside
    elif kind == "bead":
        # зачищенный валик: ширина 7 мм, высота 0,7 мм, мягкая чешуя «ёлочкой» (шаг 2,4 мм) — под краской
        prof = (1 - smooth(d, 0.8, 3.6))
        ripple = 0.80 + 0.20 * np.cos(2 * np.pi * (s_mm / 2.4 + 0.6 * d / 3.6))
        G = 0.5 + 0.42 * prof * ripple * inside
    elif kind == "spot":
        pitch = 36.0
        sc = np.mod(s_mm, pitch) - pitch / 2
        # точка сварки: ямка Ø4 мм на расстоянии 9 мм от кромки
        r2 = (d - 9.0) ** 2 + sc ** 2
        dimple = np.exp(-r2 / (2 * 1.5 ** 2))
        G = 0.5 - 0.38 * dimple * inside
    return R, G


def run(games):
    dump = json.load(open(BASE / "v02" / "uv_dump.json", encoding="utf-8"))
    spec = json.load(open(SPEC, encoding="utf-8"))
    slot_of = {}
    for sl in spec["slots"]:
        for p in sl["parts"]:
            slot_of.setdefault(p, sl["id"])
    for game in games:
        res = RES[game]
        R = np.zeros((res, res), np.float32)
        G = np.full((res, res), 0.5, np.float32)
        for ob in dump[game]:
            slot = slot_of.get(ob["name"])
            kind = KIND.get(slot)
            if not kind:
                continue
            if kind == "bead" and (not any(k in ob["name"] for k in BEAD_OK) or any(k in ob["name"] for k in BEAD_NO)):
                continue
            area = sum(p["area"] for p in ob["polys"])
            r = object_maps(ob["polys"], res, area)
            if r is None:
                continue
            mask, (x0, y0), pxmm = r
            fr, fg = features(mask, pxmm, kind, ob["name"])
            h, w = mask.shape
            sel = mask > 0
            R[y0:y0 + h, x0:x0 + w][sel] = np.maximum(R[y0:y0 + h, x0:x0 + w][sel], fr[sel])
            G[y0:y0 + h, x0:x0 + w][sel] = fg[sel]
            print(game, ob["name"], kind, f"{pxmm:.2f} px/mm")
        out = BASE / "maps_v02" / game
        out.mkdir(parents=True, exist_ok=True)
        img = np.stack([R, G, np.zeros_like(R)], -1)
        cv2.imwrite(str(out / f"{game}_struct.png"), cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))


if __name__ == "__main__":
    run(sys.argv[1:] or list(RES))
