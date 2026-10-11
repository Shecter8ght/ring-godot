"""Обводка контуров ракетницы с фото владельца (вид строго сбоку) для tools/build_flare_gun_claude.py.

Фото — _asset_src/flare_gun_claude/refs/09.webp (в задании владельца «фото 8»: красная ракетница на ковре,
правая сторона, дуло вправо). Контуры корпуса, накладки, скобы, курка и спуска снимаются по цвету, сглаживаются
и переводятся в миллиметры: u — вперёд от казённого среза ствола, v — вверх от оси ствола.
Масштаб — по наружному диаметру ствола (28 мм, 12-й калибр с толстой стенкой).

python tools/trace_flare_gun_claude.py  → _asset_src/flare_gun_claude/trace/profiles.json и trace_check.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter1d

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
OUT = SRC / "trace"
BARREL_OD_MM = 28.0
BREECH_X = 558.5            # казённый срез ствола на фото, пикс
PIN_HAMMER = (467.3, 322.8)  # оси на фото, пикс
PIN_TRIGGER = (559.3, 317.7)
PIN_HINGE = (766.7, 290.7)
FIRING_TIP = (438.0, 188.0)  # остриё бойка на взведённом курке


def smooth(contour: np.ndarray, sigma: float, eps: float = 0.06, corner_deg: float = 52.0, win: int = 6) -> np.ndarray:
    """Замкнутый контур (N, 2) → гладкая кривая. Настоящие углы (поворот больше corner_deg на длине 2·win пикс)
    остаются углами, участки между ними сглаживаются сильно — иначе кромка на блике идёт волной.
    Точек больше там, где кривизна."""
    pts = contour.astype(np.float64)
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    t = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(64, int(t[-1]))
    ts = np.linspace(0.0, t[-1], n, endpoint=False)
    closed = np.vstack([pts, pts[:1]])
    xy = np.stack([np.interp(ts, t, closed[:, 0]), np.interp(ts, t, closed[:, 1])], axis=1)
    pre = np.stack([gaussian_filter1d(xy[:, 0], 1.5, mode="wrap"), gaussian_filter1d(xy[:, 1], 1.5, mode="wrap")], axis=1)
    a = pre - np.roll(pre, win, axis=0)
    b = np.roll(pre, -win, axis=0) - pre
    turn = np.degrees(np.abs(np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(axis=1))))
    corners = [i for i in range(n) if turn[i] > corner_deg and turn[i] >= max(turn[(i + k) % n] for k in range(-2 * win, 2 * win + 1))]
    corners = [c for k, c in enumerate(corners) if k == 0 or c - corners[k - 1] > win]
    if not corners:
        out = np.stack([gaussian_filter1d(xy[:, 0], sigma, mode="wrap"), gaussian_filter1d(xy[:, 1], sigma, mode="wrap")], axis=1)
    else:
        pad = int(3 * sigma) + 1
        parts = []
        for k, c0 in enumerate(corners):
            c1 = corners[(k + 1) % len(corners)]
            idx = np.arange(c0, c1 + 1 if c1 > c0 else c1 + n + 1) % n
            sgm = pre[idx]
            if len(sgm) < 4:
                parts.append(sgm[:-1])
                continue
            m = min(pad, len(sgm) - 1)
            ext = np.vstack([2 * sgm[0] - sgm[m:0:-1], sgm, 2 * sgm[-1] - sgm[-2:-m - 2:-1]])     # нечётное отражение: концы на месте
            sm = np.stack([gaussian_filter1d(ext[:, 0], sigma, mode="nearest"), gaussian_filter1d(ext[:, 1], sigma, mode="nearest")], axis=1)[m:m + len(sgm)]
            sm[0], sm[-1] = sgm[0], sgm[-1]
            parts.append(sm[:-1])
        out = np.vstack(parts)
    out = cv2.approxPolyDP(out.astype(np.float32).reshape(-1, 1, 2), eps, True).reshape(-1, 2)
    return out.astype(np.float64)


def biggest(mask: np.ndarray) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    return (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255


def outer(mask: np.ndarray) -> np.ndarray:
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cs, key=cv2.contourArea).reshape(-1, 2)


def holes(mask: np.ndarray) -> list:
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    return [c.reshape(-1, 2) for c, h in zip(cs, hier[0]) if h[3] >= 0]


def ell(k: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


im = np.array(Image.open(SRC / "refs/09.webp").convert("RGB"))
H, W = im.shape[:2]
r, g, b = [im[..., i].astype(np.int32) for i in range(3)]
red = ((r > 140) & (r - g > 95) & (r - b > 80)).astype(np.uint8) * 255
red = cv2.morphologyEx(cv2.morphologyEx(red, cv2.MORPH_OPEN, ell(3)), cv2.MORPH_CLOSE, ell(5))
dark = (np.maximum(np.maximum(r, g), b) < 105).astype(np.uint8) * 255
dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, ell(3))
gun = biggest(cv2.morphologyEx(cv2.bitwise_or(red, dark), cv2.MORPH_CLOSE, ell(9)))

# ---- масштаб: высота ствола на участке без деталей
cols = range(815, 905, 6)          # впереди коробки: в столбце только ствол
od = float(np.median([np.flatnonzero(gun[100:300, x]).ptp() + 1 for x in cols]))
top = float(np.median([np.flatnonzero(gun[100:300, x]).min() + 100 for x in cols]))
AXIS_Y = top + od / 2.0 - 0.5
S = BARREL_OD_MM / od
BOTTOM_Y = top + od            # низ ствола = верх коробки под ним


def mm(p) -> list:
    return [round((float(p[0]) - BREECH_X) * S, 3), round((AXIS_Y - float(p[1])) * S, 3)]


def mm_list(c: np.ndarray) -> list:
    return [mm(p) for p in c]


# ---- отверстия: скоба и ушко под шнур
gun_holes = sorted(holes(gun), key=cv2.contourArea, reverse=True)
guard_hole = gun_holes[0]
lanyard = next(c for c in gun_holes[1:] if c[:, 1].mean() > 560 and cv2.contourArea(c) > 300)

# ---- рама: красное с залитыми дырами (накладка, оси, блики), без ствола и без курка
frame = biggest(red).copy()
# рама под курком: верхняя линия закрыта им — мост по прямой между видимыми концами
cv2.fillPoly(frame, [np.array([[362, 268], [366, 256], [421, 242], [427, 268]], np.int32)], 255)
filled = np.zeros_like(frame)
cv2.drawContours(filled, [outer(frame)], -1, 255, -1)
cv2.drawContours(filled, [cv2.convexHull(guard_hole.reshape(-1, 1, 2))], -1, 0, -1)
cv2.drawContours(filled, [lanyard], -1, 0, -1)
frame = filled
frame[: int(round(BOTTOM_Y)) + 1, int(round(BREECH_X)):] = 0      # ствол — отдельной деталью
frame = biggest(cv2.morphologyEx(frame, cv2.MORPH_OPEN, ell(3)))

# ---- рама по толщине — три куска: основа (рукоять и коробка), дуга скобы (тоньше), ушко под шнур (тоньше)
yy, xx = np.mgrid[0:H, 0:W]
GUARD_X, GUARD_Y = 496, 406           # дуга скобы отрезана поперёк нижней перемычки и поперёк передней стойки
bow = frame.copy()
bow[(yy < GUARD_Y) | (xx < GUARD_X)] = 0
bow = biggest(bow)
lc = lanyard.mean(axis=0)
ring = frame.copy()
ring[(xx - lc[0]) ** 2 + (yy - lc[1]) ** 2 > 30.0 ** 2] = 0
ring = biggest(ring)
main = frame.copy()
main[(yy > GUARD_Y + 4) & (xx > GUARD_X + 4)] = 0          # внахлёст 4 пикс с дугой
main[(xx - lc[0]) ** 2 + (yy - lc[1]) ** 2 < 25.0 ** 2] = 0
main = biggest(cv2.morphologyEx(main, cv2.MORPH_OPEN, ell(3)))

# ---- накладка: самая большая «дыра» красного в рукоятке
red_body = biggest(red)
pad_c = max((c for c in holes(red_body) if c[:, 0].mean() < 430 and c[:, 1].mean() > 300), key=cv2.contourArea)
pad = np.zeros_like(red)
cv2.drawContours(pad, [pad_c], -1, 255, -1)
pad = cv2.morphologyEx(pad, cv2.MORPH_OPEN, ell(7))
pad = biggest(pad)
pad_recess = cv2.dilate(pad, ell(3))

# ---- спуск: обведён по точкам с увеличенного фото (по цвету он сливается с тенью), плюс скрытая шейка к оси
TRIGGER_PX = [(245, 400), (205, 460), (178, 530), (170, 590), (185, 650), (225, 700), (290, 735), (310, 722), (262, 690), (232, 640),
              (222, 590), (232, 530), (262, 470), (300, 425), (335, 400), (372, 330), (425, 230), (432, 196), (410, 165), (380, 158),
              (352, 175), (342, 205), (330, 300)]
trig_c = np.array([[430 + x / 3.0, 250 + y / 3.0] for x, y in TRIGGER_PX])
hull = cv2.convexHull(guard_hole.reshape(-1, 1, 2))

# ---- курок (на фото взведён): тёмное над рамой + шейка к оси
n, lab, stats, cents = cv2.connectedComponentsWithStats(cv2.bitwise_and(dark, gun))
ham = np.zeros_like(red)
for i in range(1, n):
    x, y, w, h, a = stats[i]
    if a > 800 and y < 260 and x < 440:
        ham[lab == i] = 255
ham = cv2.morphologyEx(ham, cv2.MORPH_CLOSE, ell(9))
hy, hx = np.nonzero(ham)
base = (float(hx[hy > hy.max() - 5].mean()), float(hy.max()))
cv2.line(ham, (int(base[0]), int(base[1]) - 6), (int(PIN_HAMMER[0]), int(PIN_HAMMER[1])), 255, 30)
cv2.circle(ham, (int(round(PIN_HAMMER[0])), int(round(PIN_HAMMER[1]))), 24, 255, -1)
ham = cv2.morphologyEx(ham, cv2.MORPH_CLOSE, ell(11))

profiles = {
    "source": "refs/09.webp",
    "scale_mm_per_px": round(S, 5),
    "barrel_od_px": od,
    "axis_y_px": AXIS_Y,
    "breech_x_px": BREECH_X,
    "frame": mm_list(smooth(outer(frame), 6.0)),
    "frame_main": mm_list(smooth(outer(main), 6.0)),
    "guard_bow": mm_list(smooth(outer(bow), 5.0)),
    "lanyard_ring": mm_list(smooth(outer(ring), 3.0)),
    "lanyard_center": mm(lc),
    "guard_hole": mm_list(smooth(cv2.convexHull(guard_hole.reshape(-1, 1, 2)).reshape(-1, 2), 5.0, corner_deg=400.0)),
    
    "lanyard_hole": mm_list(smooth(lanyard, 3.0, corner_deg=400.0)),
    "pad": mm_list(smooth(outer(pad), 6.0)),
    "pad_recess": mm_list(smooth(outer(pad_recess), 6.0)),
    "trigger": mm_list(smooth(trig_c, 3.0, corner_deg=400.0)),
    "hammer_cocked": mm_list(smooth(outer(ham), 3.0, corner_deg=60.0)),
    "pin_hammer": mm(PIN_HAMMER),
    "pin_trigger": mm(PIN_TRIGGER),
    "pin_hinge": mm(PIN_HINGE),
    "firing_tip_cocked": mm(FIRING_TIP),
    "muzzle_u": round((float(np.flatnonzero(gun[int(AXIS_Y)]).max()) + 1 - BREECH_X) * S, 3),
    "pad_screw": mm((225.0, 461.7)),
    "plate_big": [mm((586, 277)), mm((707, 325))],
    "plate_small": [mm((586, 332)), mm((697, 360))],
    "barrel_plate": [mm((620, 180)), mm((865, 208))],
}
OUT.mkdir(parents=True, exist_ok=True)
if len(sys.argv) > 1 and sys.argv[1] == "overlay":
    shot = Image.open(SRC / "Просмотр/_overlay.png").convert("RGBA").resize((W, H))
    alpha = (np.array(shot)[..., 3] > 128).astype(np.uint8)
    edge = im.copy()
    cs, _ = cv2.findContours(alpha, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(edge, cs, -1, (0, 255, 255), 1, cv2.LINE_AA)
    photo = Image.fromarray(im)
    mix = Image.blend(photo, Image.alpha_composite(photo.convert("RGBA"), shot).convert("RGB"), 0.6)
    sheet = Image.new("RGB", (W * 2, H))
    sheet.paste(Image.fromarray(edge), (0, 0))
    sheet.paste(mix, (W, 0))
    sheet.save(SRC / "Просмотр/00_sverka_s_foto.png")
    (SRC / "Просмотр/_overlay.png").unlink()
    solid = []
    for mask in (gun, alpha * 255):
        m = np.zeros_like(gun)
        cv2.drawContours(m, [outer(mask.astype(np.uint8))], -1, 255, -1)
        solid.append(m > 0)
    print("OVERLAY silhouette match %.1f %% (intersection / union of filled outlines)" % (100.0 * (solid[0] & solid[1]).sum() / (solid[0] | solid[1]).sum()))
    sys.exit(0)
(OUT / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")

# ---- проверочная картинка: контуры поверх фото
vis = im.copy()


def draw(name: str, color: tuple) -> None:
    pts = np.array([[p[0] / S + BREECH_X, AXIS_Y - p[1] / S] for p in profiles[name]], np.float32)
    cv2.polylines(vis, [np.round(pts).astype(np.int32).reshape(-1, 1, 2)], True, color, 1, cv2.LINE_AA)


for name, color in (("frame_main", (0, 255, 255)), ("guard_bow", (255, 128, 0)), ("lanyard_ring", (255, 128, 0)), ("guard_hole", (255, 255, 0)), ("lanyard_hole", (255, 255, 0)), ("pad", (0, 255, 0)),
                    ("trigger", (255, 0, 255)), ("hammer_cocked", (80, 160, 255))):
    draw(name, color)
for p in (PIN_HAMMER, PIN_TRIGGER, PIN_HINGE, FIRING_TIP):
    cv2.circle(vis, (int(round(p[0])), int(round(p[1]))), 3, (255, 255, 255), -1)
Image.fromarray(vis).resize((W * 2, H * 2), Image.LANCZOS).save(OUT / "trace_check.png")
print("TRACE scale", round(S, 4), "mm/px; OD px", od, "axis y", AXIS_Y, "muzzle u", profiles["muzzle_u"])
for key in ("frame", "frame_main", "guard_bow", "lanyard_ring", "guard_hole", "lanyard_hole", "pad", "trigger", "hammer_cocked"):
    a = np.array(profiles[key])
    print(" ", key, len(a), "pts  u", a[:, 0].min(), a[:, 0].max(), " v", a[:, 1].min(), a[:, 1].max())
