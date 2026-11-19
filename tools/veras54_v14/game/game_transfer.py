"""ВЕРАС-54 v14: перенос карт подробной модели на игровую сетку — одной командой, без Blender и видеокарты
(образец — «Частокол», tools/pkp/game_transfer.py; способ тот же).

python -X utf8 tools/veras54_v14/game/game_transfer.py [<папка карт> …] [--out <папка>] [--only Body,Front,Mag]

Папка карт — выгрузка Painter подробной модели (<набор>_baseColor / _occlusionRoughnessMetallic / _normal.png, наборы
tools/veras54_v14/tex/tex_sets.SETS). Без папки — принятая сейчас (DEFAULT: «Карты v14/Износ v03»). Можно несколько:
набор берётся из последней папки, где он есть (например, «Износ v03» и папка, куда владелец выгрузил один набор после
кисти).
Адреса — из game_bake.py (_asset_src/veras54_v14/game/bake): для каждого текселя игрового атласа набор исходника, точка
в его развёртке и поворот касательного базиса. Выборка — трилинейная по пирамиде карты исходника: уровень по тому,
сколько текселей исходника приходится на тексель игрового атласа (как у видеокарты), иначе мелкий рисунок износа рябит.
  цвет  — пирамида в линейном свете (среднее sRGB темнит), обратно в sRGB;
  ORM   — R: меньшее из затенения исходника и затенения игровой сетки в сборе (game_bake ao), G — шероховатость, B — металл;
  нормаль — карта исходника (Painter: зерно и высота износа, OpenGL) поворачивается из касательного базиса исходника
           в базис игровой сетки (матрица game_bake frame): рельеф подробной формы (заклёпки, клейма, насечки, вафли
           магазина) приходит с её нормалью — та же нормаль, что дало бы запекание Blender.
Поля островов добираются «push-pull» по пирамиде (как tools/asten919/game_pack.py): mip-уровни в игре не тянут фон в швы.
→ <out>/veras54_<Атлас>_100_{albedo,orm,normal}.png и перенос.json (откуда, когда, доля попаданий по атласам).
Папку «Игровая версия/Карты v13» не трогает (другая папка).
"""
from __future__ import annotations

import argparse
import os
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/tex'))
import tex_sets as T  # noqa: E402

WORK = Path(os.environ.get('VERAS14_GAME_WORK') or ROOT / '_asset_src/veras54_v14/game')   # своя папка (проба)
BAKE = WORK / 'bake'
LP_JSON = WORK / 'lp/parts.json'
DEFAULT = [T.MODEL_DIR + '/Карты v14/Износ v03']
OUT = T.MODEL_DIR + '/Игровая версия/Карты v14'
SET_NAMES = list(T.SETS)                    # номер набора в адресах = место в tex_sets.SETS + 1
SUFFIX = {'color': 'baseColor', 'orm': 'occlusionRoughnessMetallic', 'normal': 'normal'}
CHUNK = 4096                                # ширина «строки» точек для cv2.remap (стороны карты < 32767)
log = lambda *a: print('VERAS14_TRANSFER', *a, flush=True)  # noqa: E731


def read(path: Path) -> np.ndarray:
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f'не читается {path}')
    if im.ndim == 2:
        im = np.repeat(im[..., None], 3, 2)
    im = im[..., :3][..., ::-1]                                   # BGR → RGB
    if im.dtype == np.uint8:
        return im.astype(np.uint16) * 257
    return im.astype(np.uint16)


def write(path: Path, im: np.ndarray) -> None:
    out = np.clip(im * 255.0 + 0.5, 0, 255).astype(np.uint8)
    if out.ndim == 3:
        out = out[..., ::-1]
    ok, buf = cv2.imencode('.png', out)
    if not ok:
        raise SystemExit(f'не пишется {path}')
    buf.tofile(str(path))


_LIN = None


def srgb_to_lin16(im16: np.ndarray) -> np.ndarray:
    """sRGB 16 бит → линейный свет 16 бит (таблицей)."""
    global _LIN
    if _LIN is None:
        c = np.arange(65536, dtype=np.float64) / 65535.0
        lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        _LIN = np.round(lin * 65535.0).astype(np.uint16)
    return _LIN[im16]


def lin_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


class Pyramid:
    """Пирамида карты (uint16, RGB): уровень 0 — сама карта, дальше вдвое меньше (среднее по площади)."""

    def __init__(self, im: np.ndarray):
        self.levels = [im]

    def level(self, k: int) -> np.ndarray:
        while len(self.levels) <= k:
            a = self.levels[-1]
            if min(a.shape[:2]) <= 1:
                return a
            self.levels.append(cv2.resize(a, ((a.shape[1] + 1) // 2, (a.shape[0] + 1) // 2),
                                          interpolation=cv2.INTER_AREA))
        return self.levels[k]

    def sample(self, uv: np.ndarray, lod: np.ndarray) -> np.ndarray:
        """Трилинейная выборка в точках uv (развёртка исходника, v вверх) на дробном уровне lod → float32 0…1."""
        n = len(uv)
        out = np.zeros((n, 3), np.float32)
        lod = np.clip(lod, 0.0, 12.0)
        l0 = np.floor(lod).astype(np.int32)
        t = (lod - l0).astype(np.float32)
        for lv in np.unique(l0):
            sel = np.flatnonzero(l0 == lv)
            for k, w in ((int(lv), 1.0 - t[sel]), (int(lv) + 1, t[sel])):
                if k > int(lv) and not (w > 1e-4).any():
                    continue
                a = self.level(k)
                h, wd = a.shape[:2]
                q = uv[sel]
                mx = (q[:, 0] * wd - 0.5).astype(np.float32)
                my = ((1.0 - q[:, 1]) * h - 0.5).astype(np.float32)
                m = len(sel)
                rows = (m + CHUNK - 1) // CHUNK
                pad = rows * CHUNK - m
                mx = np.pad(mx, (0, pad)).reshape(rows, CHUNK)
                my = np.pad(my, (0, pad)).reshape(rows, CHUNK)
                v = cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                v = v.reshape(-1, 3)[:m].astype(np.float32) / 65535.0
                out[sel] += v * w[:, None]
        return out


def footprint(sid: np.ndarray, uv: np.ndarray, sizes: dict) -> np.ndarray:
    """Уровень пирамиды на тексель: log2 числа текселей исходника на тексель атласа (по соседям того же набора)."""
    h, w = sid.shape
    S = np.zeros(h * w, np.float32)
    for s, size in sizes.items():
        S[sid.ravel() == s] = size
    S = S.reshape(h, w)

    def step(a, b, sa, sb):
        d = np.linalg.norm((b - a), axis=-1) * sa
        ok = (sa > 0) & (sa == sb) & (d < 48.0)
        return np.where(ok, d, np.nan)
    sidf = np.where(sid > 0, sid, -1).astype(np.float32)
    sx = np.full((h, w), np.nan, np.float32)
    sy = np.full((h, w), np.nan, np.float32)
    same_x = sidf[:, 1:] == sidf[:, :-1]
    same_y = sidf[1:, :] == sidf[:-1, :]
    dx = step(uv[:, :-1], uv[:, 1:], np.where(same_x, S[:, :-1], 0), S[:, 1:])
    dy = step(uv[:-1, :], uv[1:, :], np.where(same_y, S[:-1, :], 0), S[1:, :])
    sx[:, :-1] = dx
    sx[:, 1:] = np.fmax(sx[:, 1:], dx)          # слева или справа — что есть
    sy[:-1, :] = dy
    sy[1:, :] = np.fmax(sy[1:, :], dy)
    f = np.fmax(sx, sy)
    # где соседей того же набора нет (край острова в один тексель) — медиана набора
    for s in sizes:
        m = sid == s
        bad = m & ~np.isfinite(f)
        if bad.any():
            good = f[m & np.isfinite(f)]
            f[bad] = float(np.median(good)) if len(good) else 1.0
    f = np.where(np.isfinite(f), f, 1.0)
    return np.log2(np.maximum(f, 1.0)).astype(np.float32)


def push_pull(im: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Пустое (mask = 0) — средним заполненного по пирамиде; заполненное не меняется (как game_pack АСТЕН-919)."""
    chans = im if im.ndim == 3 else im[..., None]
    levels = [(chans * mask[..., None], mask.astype(np.float32))]
    while min(levels[-1][1].shape) > 1:
        c, w = levels[-1]
        h2, w2 = (c.shape[0] + 1) // 2, (c.shape[1] + 1) // 2
        c = cv2.resize(c, (w2, h2), interpolation=cv2.INTER_AREA) * 4
        ww = cv2.resize(w, (w2, h2), interpolation=cv2.INTER_AREA) * 4
        c = c.reshape(h2, w2, -1)
        levels.append((c, ww))
    fill = levels[-1][0] / np.maximum(levels[-1][1], 1e-6)[..., None]
    for c, w in reversed(levels[:-1]):
        up = cv2.resize(fill, (c.shape[1], c.shape[0]), interpolation=cv2.INTER_LINEAR).reshape(c.shape)
        avg = c / np.maximum(w, 1e-6)[..., None]
        k = np.clip(w, 0, 1)[..., None]
        fill = avg * k + up * (1 - k)
    out = np.where(mask[..., None] > 0, chans, fill)
    return out if im.ndim == 3 else out[..., 0]


def find_maps(folders: list, set_name: str) -> dict:
    """Карты набора из последней папки, где он есть: {канал: путь}, папка."""
    for f in reversed(folders):
        p = {k: Path(f) / f'{set_name}_{suf}.png' for k, suf in SUFFIX.items()}
        if all(x.exists() for x in p.values()):
            return p
    return {}


def transfer(atlas: str, folders: list, out_dir: Path, rep: dict) -> None:
    t0 = time.time()
    hit = np.load(BAKE / f'{atlas}_hit.npz')
    sid, uv = hit['set'], hit['uv']
    h, w = sid.shape
    M = np.load(BAKE / f'{atlas}_frame.npz')['m'].reshape(h, w, 3, 3)
    ao_lp = np.load(BAKE / f'{atlas}_ao.npz')['ao'].astype(np.float32) if (BAKE / f'{atlas}_ao.npz').exists() else None
    present = [int(s) for s in np.unique(sid) if s > 0]
    maps, sizes = {}, {}
    for s in present:
        name = SET_NAMES[s - 1]
        p = find_maps(folders, name)
        if not p:
            raise SystemExit(f'набора {name} нет ни в одной папке: {folders}')
        maps[s] = p
        with open(p['color'], 'rb') as fh:              # ширина из заголовка PNG (IHDR), без чтения карты
            sizes[s] = int.from_bytes(fh.read(24)[16:20], 'big')
    lod = footprint(sid, uv, sizes)
    flat_sid = sid.ravel()
    flat_uv = uv.reshape(-1, 2)
    flat_lod = lod.ravel()
    color = np.zeros((h * w, 3), np.float32)
    orm = np.zeros((h * w, 3), np.float32)
    nrm = np.zeros((h * w, 3), np.float32)
    used = {}
    for s in present:
        idx = np.flatnonzero(flat_sid == s)
        q, ld = flat_uv[idx], flat_lod[idx]
        name = SET_NAMES[s - 1]
        im = read(maps[s]['color'])
        color[idx] = Pyramid(srgb_to_lin16(im)).sample(q, ld)
        del im
        orm[idx] = Pyramid(read(maps[s]['orm'])).sample(q, ld)
        nrm[idx] = Pyramid(read(maps[s]['normal'])).sample(q, ld)
        used[name] = {'folder': str(maps[s]['color'].parent), 'size': sizes[s], 'texels': int(len(idx)),
                      'lod_median': round(float(np.median(ld)), 2)}
        log(atlas, name, f'{len(idx)} текселей, уровень ~{np.median(ld):.2f}', f'{time.time() - t0:.0f} с')
    valid = (flat_sid > 0).reshape(h, w).astype(np.float32)
    # нормаль: карта исходника → базис игровой сетки
    n_hp = nrm.reshape(h, w, 3) * 2.0 - 1.0
    n_lp = np.einsum('hwij,hwj->hwi', M.astype(np.float32), n_hp)
    n_lp /= np.maximum(np.linalg.norm(n_lp, axis=-1, keepdims=True), 1e-6)
    n_lp = np.where(valid[..., None] > 0, n_lp, np.array([0.0, 0.0, 1.0], np.float32))
    del n_hp, M
    orm = orm.reshape(h, w, 3)
    if ao_lp is not None:
        orm[..., 0] = np.where(valid > 0, np.minimum(orm[..., 0], ao_lp), orm[..., 0])
    color = lin_to_srgb(push_pull(color.reshape(h, w, 3), valid))
    orm = push_pull(orm, valid)
    n = push_pull(n_lp * 0.5 + 0.5, valid) * 2.0 - 1.0
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    tag = f'veras54_{atlas}_100'
    write(out_dir / f'{tag}_albedo.png', color)
    write(out_dir / f'{tag}_orm.png', orm)
    write(out_dir / f'{tag}_normal.png', n * 0.5 + 0.5)
    rep[atlas] = {'size': w, 'hit': round(float(valid.mean()), 4), 'sets': used, 'sec': round(time.time() - t0, 1)}
    log(atlas, 'готово', f'попаданий {valid.mean():.3f}', f'{time.time() - t0:.0f} с')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folders', nargs='*')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    folders = [str(Path(f).resolve()) for f in (a.folders or DEFAULT)]
    for f in folders:
        if not Path(f).is_dir():
            raise SystemExit(f'нет папки {f}')
    out_dir = Path(a.out).resolve()
    if 'Карты v13' in str(out_dir):
        raise SystemExit('папку «Карты v13» не трогать')
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = json.loads(LP_JSON.read_text(encoding='utf-8'))
    atlases = [x for x in a.only.split(',') if x] or list(rec['atlases'])
    rep = {}
    t0 = time.time()
    for atlas in atlases:
        transfer(atlas, folders, out_dir, rep)
    info = {'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'folders': folders, 'atlases': rep,
            'lp': str(LP_JSON.parent / 'VERAS54_Game_LP.blend'), 'sec': round(time.time() - t0, 1)}
    path = out_dir / 'перенос.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if a.only and old.get('atlases'):
        old['atlases'].update(rep)
        info['atlases'] = old['atlases']
    path.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('перенесено', atlases, 'из', folders, '→', out_dir, f'{time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
