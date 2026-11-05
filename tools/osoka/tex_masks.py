"""«Осока», маски этапа 1 по картам развёртки (tools/osoka/game_tex.py → <набор>_maps.npz: положение мм и нормаль в
каждом пикселе): трафаретные надписи белой краской на трубе и светлый отсек датчика ракеты.

    python -X utf8 tools/osoka/tex_masks.py            → _asset_src/osoka/tex/masks/Tube_stencil.png, Missile_sensor.png

Надписи — вымышленные (правило навыка: реальные индексы и бренды не переносятся): «ТП-36 «ОСОКА»», «ЗР-36 № 0417
11-25», «НЕ БРОСАТЬ». Как у настоящей трубы (интервью 2026-11-05: «трафаретом, как у настоящей») — белой краской на
левом боку трубы между задней обоймой и антабкой, строки вдоль трубы, читаются слева (перёд трубы — слева). Шрифт —
DejaVu Sans Bold из поставки matplotlib (свободная лицензия, кириллица), сжат по ширине до 0.8 — как узкий трафаретный.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/osoka/tex'
OUT = TEX / 'masks'
FONT = r'D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf'
TUBE_R = 38.47                 # наружный радиус трубы, мм (dims.TUBE_R)
PX_MM = 8.0                    # разрешение холста надписей, пикс/мм
CONDENSE = 0.8                 # сжатие букв по ширине
# блок надписей: центр по X (мм от заднего торца трубы), угол середины блока от +Y к +Z (левый бок, чуть выше оси),
# строки: текст, высота прописной, мм, сдвиг строки от середины блока по дуге, мм (вверх — к +Z)
BLOCK_X = 720.0
BLOCK_ANG = 30.0
LINES = [("ТП-36  «ОСОКА»", 13.0, 13.0), ("ЗР-36   № 0417   11-25", 8.5, -4.0), ("НЕ БРОСАТЬ", 8.5, -18.0)]
CAP = 0.73                     # высота прописной DejaVu от кегля
# отсек датчика ракеты: от сопла 1062…1225 мм (part_missile), корень ракеты в трубе — X 18 мм (dims.MISSILE_X0)
SENSOR_X = (18.0 + 1062.0, 18.0 + 1225.0)
log = lambda *a: print('OSOKA_MASKS', *a, flush=True)


def stencil_canvas():
    """Холст надписей в координатах развёртки трубы: u — вдоль трубы от переда к заду (читается слева направо, перёд
    слева), v — по дуге вверх. Возврат: картинка (0…1) и привязка (u0, v0 мм в пикселе 0)."""
    W = int(420 * PX_MM); H = int(70 * PX_MM)
    img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(img)
    for text, cap, dv in LINES:
        size = cap / CAP * PX_MM
        f = ImageFont.truetype(FONT, int(round(size)))
        # строка шириной по тексту, затем сжатие по ширине
        tw = int(d.textlength(text, font=f)) + 4
        line = Image.new('L', (tw, int(size * 1.4)), 0)
        ImageDraw.Draw(line).text((2, 0), text, font=f, fill=255)
        bb = line.getbbox()
        line = line.crop(bb)
        line = line.resize((max(1, int(line.width * CONDENSE)), line.height), Image.LANCZOS)
        cx, cy = W // 2, H // 2 - int(dv * PX_MM)
        img.paste(line, (cx - line.width // 2, cy - line.height // 2), line)
    return np.asarray(img, np.float32) / 255.0, (W / (2 * PX_MM), H / (2 * PX_MM))


def tube_stencil():
    m = np.load(TEX / 'Tube_maps.npz')
    pos, nrm, filled = m['pos'], m['nrm'].astype(np.float32), m['filled']
    r = np.hypot(pos[..., 1], pos[..., 2])
    radial = (nrm[..., 1] * pos[..., 1] + nrm[..., 2] * pos[..., 2]) / np.maximum(r, 1e-6)
    on = filled & (np.abs(r - TUBE_R) < 0.6) & (radial > 0.9) & (pos[..., 0] > 0.0) & (pos[..., 0] < 1500.0)
    canvas, (hu, hv) = stencil_canvas()
    ang = np.degrees(np.arctan2(pos[..., 2], pos[..., 1]))
    u = (BLOCK_X - pos[..., 0])                              # вдоль трубы: перёд (больше X) — слева
    v = np.radians(ang - BLOCK_ANG) * TUBE_R                 # по дуге вверх
    pu = (u + hu) * PX_MM
    pv = (hv - v) * PX_MM
    H, W = canvas.shape
    ok = on & (pu >= 0) & (pu < W - 1) & (pv >= 0) & (pv < H - 1)
    out = np.zeros(pos.shape[:2], np.float32)
    iu, iv = pu[ok].astype(np.int32), pv[ok].astype(np.int32)
    fu, fv = pu[ok] - iu, pv[ok] - iv
    out[ok] = (canvas[iv, iu] * (1 - fu) * (1 - fv) + canvas[iv, iu + 1] * fu * (1 - fv) +
               canvas[iv + 1, iu] * (1 - fu) * fv + canvas[iv + 1, iu + 1] * fu * fv)
    return out, int((out > 0.5).sum())


def missile_sensor():
    m = np.load(TEX / 'Missile_maps.npz')
    pos, filled = m['pos'], m['filled']
    x = pos[..., 0]
    out = (filled & (x >= SENSOR_X[0]) & (x <= SENSOR_X[1])).astype(np.float32)
    return out, int(out.sum())


def save(a, name):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'L').save(OUT / name)
    log(name, a.shape)


def main():
    t, n = tube_stencil()
    save(t, 'Tube_stencil.png')
    log('трафарет: пикселей', n)
    s, n2 = missile_sensor()
    save(s, 'Missile_sensor.png')
    log('отсек датчика: пикселей', n2)
    (OUT / 'masks.json').write_text(json.dumps({'stencil': {'block_x': BLOCK_X, 'block_ang': BLOCK_ANG,
                                                             'lines': LINES}, 'sensor_x': SENSOR_X},
                                               ensure_ascii=False), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
