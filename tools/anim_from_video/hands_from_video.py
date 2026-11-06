"""Анимация рук по видео (опыт, владелец 2026-11-06: «разложить на кадры и по ним выставить позы рук и оружия … этот
процесс автоматизировать, а то пальцы то изломаны, то пересечения»). Шаг 1: кадры видео и точки кистей.

Видео — настоящие перезарядки (не чужие игры: их анимацию не переносим). Кадры — ffmpeg с заданной частотой из отрезка;
кисти — MediaPipe Hands (21 точка на кисть: запястье, по 4 на палец; image — доли кадра и относительная глубина, world —
метры от середины кисти). Сглаживание — фильтр One Euro по каждой координате (дрожание без запаздывания на быстрых
движениях). Итог — JSON по кадрам и лист с точками поверх кадров (самопроверка).

python -X utf8 tools/anim_from_video/hands_from_video.py <видео> <папка> [--from С] [--to С] [--fps 30] [--sheet N] [--tiles] [--frames]
→ <папка>/frames/f0001.jpg…, <папка>/hands.json, <папка>/sheet.jpg
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

FINGERS = {'thumb': (1, 2, 3, 4), 'index': (5, 6, 7, 8), 'middle': (9, 10, 11, 12), 'ring': (13, 14, 15, 16),
           'pinky': (17, 18, 19, 20)}
ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / '_asset_src/anim_video/models/hand_landmarker.task'   # Apache 2.0, storage.googleapis.com/mediapipe-models
EDGES = [(0, 1), (0, 5), (0, 17), (5, 9), (9, 13), (13, 17)] + [(f[i], f[i + 1]) for f in FINGERS.values() for i in range(3)] \
    + [(1, 2)]


class OneEuro:
    """Фильтр One Euro (Casiez, 2012): мало сглаживает на быстром движении, сильно — на медленном."""

    def __init__(self, freq, min_cutoff=1.2, beta=0.02, d_cutoff=1.0):
        self.freq, self.min_cutoff, self.beta, self.d_cutoff = freq, min_cutoff, beta, d_cutoff
        self.x = self.dx = None

    @staticmethod
    def _alpha(cutoff, freq):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau * freq)

    def __call__(self, x):
        x = np.asarray(x, float)
        if self.x is None:
            self.x, self.dx = x, np.zeros_like(x)
            return x
        dx = (x - self.x) * self.freq
        a_d = self._alpha(self.d_cutoff, self.freq)
        self.dx = a_d * dx + (1 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * np.abs(self.dx)
        a = self._alpha(cutoff, self.freq)
        self.x = a * x + (1 - a) * self.x
        return self.x


def extract(video, out, start, end, fps):
    frames = out / 'frames'
    frames.mkdir(parents=True, exist_ok=True)
    for f in frames.glob('*.jpg'):
        f.unlink()
    cmd = ['ffmpeg', '-v', 'error', '-y']
    if start is not None:
        cmd += ['-ss', str(start)]
    if end is not None:
        cmd += ['-to', str(end)] if start is None else ['-t', str(end - start)]
    cmd += ['-i', str(video), '-vf', f'fps={fps}', '-q:v', '2', str(frames / 'f%04d.jpg')]
    subprocess.run(cmd, check=True)
    return sorted(frames.glob('*.jpg'))


def read_img(p):
    """cv2.imread не открывает пути с кириллицей — через байты."""
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def _marker(mode, model):
    from mediapipe.tasks.python import BaseOptions, vision
    rm = vision.RunningMode.VIDEO if mode == 'video' else vision.RunningMode.IMAGE
    return vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model)), running_mode=rm, num_hands=2,
        min_hand_detection_confidence=0.35, min_hand_presence_confidence=0.35, min_tracking_confidence=0.35))


def _windows(w, h):
    """Окна для поиска мелких кистей: детектор ладони смотрит кадр в 192 × 192, кисть в 1080p — ~25 точек; в окне
    800 × 800 — вдвое крупнее. Окна внахлёст + кадр целиком."""
    s = min(800, h)
    xs = sorted({0, max(0, w - s)} | {int(x) for x in np.linspace(0, max(0, w - s), 4)})
    ys = sorted({0, max(0, h - s)})
    return [(0, 0, w, h)] + [(x, y, s, s) for y in ys for x in xs]


def _bbox(pts, w, h):
    q = np.asarray(pts)[:, :2] * [w, h]
    return np.concatenate([q.min(0), q.max(0)])


def _iou(a, b):
    lo = np.maximum(a[:2], b[:2])
    hi = np.minimum(a[2:], b[2:])
    inter = np.prod(np.clip(hi - lo, 0, None))
    area = lambda r: np.prod(r[2:] - r[:2])
    return inter / max(area(a) + area(b) - inter, 1e-6)


def detect(paths, fps, model=MODEL, tiles=False):
    """MediaPipe 1.x (Tasks API). Без tiles — режим видео (отслеживание между кадрами); с tiles — каждый кадр окнами
    внахлёст (мелкие и закрытые оружием кисти находятся чаще), повторы склеиваются по пересечению рамок.
    Сторона — как называет MediaPipe (для съёмки без зеркала — верно, проверено на «live fire and reload»).
    Сглаживание — после, по каждой стороне; разрыв больше 3 кадров — фильтр заново."""
    import mediapipe as mp
    marker = _marker('tiles' if tiles else 'video', model)
    raw = []
    for i, p in enumerate(paths):
        img = read_img(p)
        h, w = img.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        found = []
        wins = _windows(w, h) if tiles else [(0, 0, w, h)]
        for (x0, y0, ww, hh) in wins:
            crop = np.ascontiguousarray(rgb[y0:y0 + hh, x0:x0 + ww])
            frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)
            res = marker.detect(frame) if tiles else marker.detect_for_video(frame, int(round(i * 1000.0 / fps)))
            for lm, wl, hd in zip(res.hand_landmarks, res.hand_world_landmarks, res.handedness):
                img_pts = np.array([[(x0 + q.x * ww) / w, (y0 + q.y * hh) / h, q.z * ww / w] for q in lm])
                world = np.array([[q.x, q.y, q.z] for q in wl])
                found.append({'side': hd[0].category_name, 'score': float(hd[0].score), 'image': img_pts, 'world': world,
                              'box': _bbox(img_pts, w, h)})
        keep = []
        for f in sorted(found, key=lambda f: -f['score']):
            if all(_iou(f['box'], k['box']) < 0.3 for k in keep):
                keep.append(f)
        # две кисти одной стороны — вторую (слабее) отдать другой стороне, если она свободна
        sides = {}
        for f in keep[:2]:
            if f['side'] in sides:
                other = 'Left' if f['side'] == 'Right' else 'Right'
                if other in sides:
                    continue
                f['side'] = other
            sides[f['side']] = f
        raw.append((p.name, (w, h), sides))
    marker.close()
    out, filt, last = [], {}, {}
    for i, (name, (w, h), sides) in enumerate(raw):
        rec = {'frame': i + 1, 'file': name, 'size': [w, h], 'hands': []}
        for side, f in sides.items():
            if side not in filt or i - last.get(side, -99) > 3:
                filt[side] = (OneEuro(fps), OneEuro(fps))
            last[side] = i
            img_pts = filt[side][0](f['image'])
            world = filt[side][1](f['world'])
            rec['hands'].append({'side': side, 'score': round(f['score'], 3),
                                 'image': np.round(img_pts, 5).tolist(), 'world': np.round(world, 5).tolist()})
        out.append(rec)
    return out


def sheet(paths, data, out, n):
    pick = np.linspace(0, len(paths) - 1, min(n, len(paths))).astype(int)
    tiles = []
    for i in pick:
        img = read_img(paths[i])
        h, w = img.shape[:2]
        for hand in data[i]['hands']:
            pts = [(int(x * w), int(y * h)) for x, y, _ in hand['image']]
            col = (60, 220, 60) if hand['side'] == 'Right' else (60, 120, 255)
            for a, b in EDGES:
                cv2.line(img, pts[a], pts[b], col, 2)
            for q in pts:
                cv2.circle(img, q, 3, (255, 255, 255), -1)
        cv2.putText(img, f'{data[i]["frame"]}', (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
        tiles.append(cv2.resize(img, (480, int(480 * h / w))))
    cols = 4
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]
    ok, buf = cv2.imencode('.jpg', np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    buf.tofile(str(out / 'sheet.jpg'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--from', dest='start', type=float)
    ap.add_argument('--to', dest='end', type=float)
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--sheet', type=int, default=16)
    ap.add_argument('--tiles', action='store_true', help='искать кисти окнами внахлёст (медленнее, находит чаще)')
    ap.add_argument('--frames', action='store_true', help='кадры уже лежат в <папка>/frames (сняты из плеера) — видео не резать')
    a = ap.parse_args()
    out = Path(a.out)
    paths = sorted((out / 'frames').glob('*.[jp][pn]g')) if a.frames else extract(Path(a.video), out, a.start, a.end, a.fps)
    data = detect(paths, a.fps, tiles=a.tiles)
    (out / 'hands.json').write_text(json.dumps({'video': str(a.video), 'from': a.start, 'to': a.end, 'fps': a.fps,
                                                'frames': data}, ensure_ascii=False), encoding='utf-8')
    found = sum(1 for d in data if d['hands'])
    both = sum(1 for d in data if len(d['hands']) == 2)
    print('HANDS кадров', len(data), 'с кистями', found, 'с обеими', both)
    sheet(paths, data, out, a.sheet)


if __name__ == '__main__':
    main()
