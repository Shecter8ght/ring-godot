"""Анимация рук по видео, шаг 2: точки кистей (hands.json) → углы суставов пальцев в понятиях рига FPS-рук: у каждой
фаланги сгиб (к ладони — плюс) и у основания развод. Углы не зависят от поворота кисти и масштаба — их можно ставить
на любую кисть; пределы и смыкание на предмете — hand_solver.py.

Сгиб считается в плоскости пальца: поперечная ось пальца = (основная фаланга × нормаль ладони); у основания — от
направления «запястье → костяшка» этого пальца. Большой палец по видео ненадёжен у основания (его ось вращения
скрыта): берутся только сгибы второго и концевого суставов.

python -X utf8 tools/anim_from_video/finger_angles.py <hands.json> <сторона Left|Right> <кадр> [кадр …] [--show <out.jpg>]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

CHAINS = {'thumb': (1, 2, 3, 4), 'f_index': (5, 6, 7, 8), 'f_middle': (9, 10, 11, 12), 'f_ring': (13, 14, 15, 16),
          'f_pinky': (17, 18, 19, 20)}


def unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def palm_normal(w, side):
    """Нормаль ладони (от тыла к ладони) по мировым точкам MediaPipe."""
    f = unit(w[9] - w[0])
    a = w[5] - w[17]
    a = unit(a - f * a.dot(f))
    n = np.cross(a, f)
    return n if side == 'Left' else -n


def signed_angle(u, v, axis):
    u, v = unit(u), unit(v)
    return math.atan2(np.dot(np.cross(u, v), axis), np.dot(u, v))


def angles(world, side):
    """→ {палец: [(сгиб, развод), ×3]} в радианах (сгиб к ладони — плюс)."""
    w = np.asarray(world, float)
    pn = palm_normal(w, side)
    out = {}
    for name, idx in CHAINS.items():
        p = [w[i] for i in idx]
        segs = [p[1] - p[0], p[2] - p[1], p[3] - p[2]]
        if name == 'thumb':
            base = segs[0]
        else:
            base = p[0] - w[0]                       # пястная кость: запястье → костяшка
        lat = unit(np.cross(unit(base), pn))         # ось сгиба: поворот base к ладони — плюс
        if np.dot(np.cross(unit(base), unit(base) + pn * 0.1), lat) < 0:
            lat = -lat
        res = []
        prev = base
        for j, s in enumerate(segs):
            flex = signed_angle(prev, s, lat)
            spread = 0.0
            if j == 0 and name != 'thumb':
                # развод: отклонение основной фаланги в плоскости ладони
                inplane = s - pn * s.dot(pn)
                spread = signed_angle(base - pn * base.dot(pn), inplane, pn) * (1 if side == 'Left' else -1)
            res.append((flex, spread))
            prev = s
        if name == 'thumb':
            res[0] = (float('nan'), 0.0)             # основание большого по видео не берём
        out[name] = res
    return out


def hand_at(data, frame, side):
    rec = data['frames'][frame - 1]
    for h in rec['hands']:
        if h['side'] == side:
            return h
    return None


def show(data, hands_path, frames, side, out):
    import cv2
    root = Path(hands_path).parent / 'frames'
    tiles = []
    for fr in frames:
        rec = data['frames'][fr - 1]
        img = cv2.imdecode(np.fromfile(str(root / rec['file']), np.uint8), cv2.IMREAD_COLOR)
        h = hand_at(data, fr, side)
        H, W = img.shape[:2]
        if h is None:
            continue
        pts = np.array([(x * W, y * H) for x, y, _ in h['image']])
        c = pts.mean(0)
        r = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])) * 0.9 + 40
        x0, y0 = int(max(0, c[0] - r)), int(max(0, c[1] - r))
        x1, y1 = int(min(W, c[0] + r)), int(min(H, c[1] + r))
        for i, idx in enumerate(CHAINS.values()):
            col = [(255, 255, 255), (60, 220, 60), (60, 160, 255), (255, 120, 60), (220, 60, 220)][i]
            chain = [0] + list(idx)
            for a, b in zip(chain, chain[1:]):
                cv2.line(img, tuple(int(v) for v in pts[a]), tuple(int(v) for v in pts[b]), col, 3)
        crop = cv2.resize(img[y0:y1, x0:x1], (420, 420))
        cv2.putText(crop, f'{fr} {h["score"]:.2f}', (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
        tiles.append(crop)
    if tiles:
        ok, buf = cv2.imencode('.jpg', np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 88])
        buf.tofile(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hands')
    ap.add_argument('side')
    ap.add_argument('frames', type=int, nargs='+')
    ap.add_argument('--show')
    a = ap.parse_args()
    data = json.loads(Path(a.hands).read_text(encoding='utf-8'))
    for fr in a.frames:
        h = hand_at(data, fr, a.side)
        if h is None:
            print(fr, 'нет кисти', a.side)
            continue
        ang = angles(h['world'], a.side)
        print(fr, f'score {h["score"]:.2f}', '  '.join(
            f'{k}: ' + '/'.join('—' if math.isnan(v[0]) else f'{math.degrees(v[0]):.0f}' for v in vals)
            + (f' разв {math.degrees(vals[0][1]):.0f}' if k != 'thumb' else '') for k, vals in ang.items()))
    if a.show:
        show(data, a.hands, a.frames, a.side, a.show)


if __name__ == '__main__':
    main()
