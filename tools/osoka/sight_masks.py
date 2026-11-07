"""«Осока», тепловизор ПН-36Т «ПОЛЫНЬ»: маска маркировки белой краской по картам развёртки (tools/osoka/sight_tex.py →
Polyn_maps.npz: положение мм, нормаль, номер детали в каждом пикселе).

    python -X utf8 tools/osoka/sight_masks.py          → _asset_src/osoka_polyn/tex/masks/Polyn_stencil.png

Надписи вымышленные (интервью 2026-11-07: «Да, всё белой краской»), как «1ПН97 / ЮРВ0161» на снимке Кузьмина «Армия-2016»:
на левом боку корпуса вверху — «ПН-36Т «ПОЛЫНЬ»» и мельче «№ 0213»; вокруг латунного основания переключателя —
«ВЫКЛ», «ДЕНЬ», «ТЕПЛО» по положениям рычажка и риски. Строки читаются, стоя слева (перёд прицела — слева).
Оси карт — оси файла прицела (начало — точка крепления на «Осоке»: x 1214, y 2, z 49.5 её осей).
Шрифт — DejaVu Sans Bold из поставки matplotlib (свободная лицензия, кириллица; у Inter «А» без перекладины).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/osoka_polyn/tex'
OUT = TEX / 'masks'
FONT = r'D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf'
PX_MM = 16.0                   # разрешение холста надписей, пикс/мм
CONDENSE = 0.86                # сжатие букв по ширине
CAP = 0.73                     # высота прописной DejaVu от кегля
O = (1214.0, 2.0, 49.5)        # точка крепления в осях «Осоки» (sight_build.ROOT)
LEFT_Y = 48.0 + 109.0 / 2 - O[1]          # левый бок корпуса, мм (YC + W/2)
# корпус: x 1125…1240, низ z 78, верх 211 (оси «Осоки»); плоский левый бок — до z 181 (выше крыша скруглена R 30);
# блок названия — середина корпуса, под скруглением крыши
NAME_C = (1182.5 - O[0], 171.0 - O[2])
NAME_LINES = [("ПН-36Т  «ПОЛЫНЬ»", 5.2, 0.0), ("№ 0213", 3.0, -7.5)]
# переключатель: центр (sight_build.SW = XF − 49, ZB + 34), рычажок от центра назад: ВЫКЛ +50°, ДЕНЬ 0°, ТЕПЛО −50°
SW_C = (1240.0 - 49.0 - O[0], 78.0 + 34.0 - O[2])
SW_LABELS = [("ВЫКЛ", 50.0), ("ДЕНЬ", 0.0), ("ТЕПЛО", -50.0)]
SW_R_TEXT, SW_TICK = 25.0, (12.6, 15.6)
log = lambda *a: print('POLYN_MASKS', *a, flush=True)


def font(cap):
    return ImageFont.truetype(FONT, int(round(cap / CAP * PX_MM)))


def text_img(text, cap):
    f = font(cap)
    d = ImageDraw.Draw(Image.new('L', (8, 8)))
    tw = int(d.textlength(text, font=f)) + 8
    line = Image.new('L', (tw, int(cap / CAP * PX_MM * 1.5)), 0)
    ImageDraw.Draw(line).text((4, 0), text, font=f, fill=255)
    line = line.crop(line.getbbox())
    return line.resize((max(1, int(line.width * CONDENSE)), line.height), Image.LANCZOS)


def canvas():
    """Холст левого бока в осях вида слева: u = −x (перёд слева), v = z; пиксель (0, 0) — (U0, V0) мм."""
    u0, u1 = -(1240.0 - O[0]) - 2, -(1125.0 - O[0]) + 2
    v0, v1 = 78.0 - O[2] - 2, 211.0 - O[2] + 2
    W, H = int((u1 - u0) * PX_MM), int((v1 - v0) * PX_MM)
    img = Image.new('L', (W, H), 0)

    def at(u, v):
        return (u - u0) * PX_MM, (v1 - v) * PX_MM

    def paste(line, u, v):
        x, y = at(u, v)
        img.paste(line, (int(x - line.width / 2), int(y - line.height / 2)), line)

    for text, cap, dv in NAME_LINES:
        paste(text_img(text, cap), -NAME_C[0], NAME_C[1] + dv)
    d = ImageDraw.Draw(img)
    su, sv = -SW_C[0], SW_C[1]
    for text, deg in SW_LABELS:
        a = math.radians(deg)
        du, dv = math.cos(a), math.sin(a)           # рычажок назад (+u) и вверх на deg
        paste(text_img(text, 2.6), su + du * SW_R_TEXT, sv + dv * SW_R_TEXT)
        p0 = at(su + du * SW_TICK[0], sv + dv * SW_TICK[0])
        p1 = at(su + du * SW_TICK[1], sv + dv * SW_TICK[1])
        d.line([p0, p1], fill=255, width=int(0.7 * PX_MM))
    return np.asarray(img, np.float32) / 255.0, (u0, v1)


def stencil():
    m = np.load(TEX / 'Polyn_maps.npz')
    pos, nrm, filled, pid = m['pos'], m['nrm'].astype(np.float32), m['filled'], m['pid']
    parts = json.loads((TEX / 'parts.json').read_text(encoding='utf-8'))
    body = [p['pid'] for p in parts if p['name'] == 'Thermal_body']
    on = filled & np.isin(pid, body) & (nrm[..., 1] > 0.97) & (np.abs(pos[..., 1] - LEFT_Y) < 0.8)
    img, (u0, v1) = canvas()
    pu = (-pos[..., 0] - u0) * PX_MM
    pv = (v1 - pos[..., 2]) * PX_MM
    H, W = img.shape
    ok = on & (pu >= 0) & (pu < W - 1) & (pv >= 0) & (pv < H - 1)
    out = np.zeros(pos.shape[:2], np.float32)
    iu, iv = pu[ok].astype(np.int32), pv[ok].astype(np.int32)
    fu, fv = pu[ok] - iu, pv[ok] - iv
    out[ok] = (img[iv, iu] * (1 - fu) * (1 - fv) + img[iv, iu + 1] * fu * (1 - fv) +
               img[iv + 1, iu] * (1 - fu) * fv + img[iv + 1, iu + 1] * fu * fv)
    return out, int(on.sum()), int((out > 0.5).sum()), img


def main():
    out, n_face, n_txt, img = stencil()
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'L').save(OUT / 'Polyn_stencil.png')
    Image.fromarray((img * 255).astype(np.uint8), 'L').save(OUT / 'Polyn_stencil_canvas.png')
    log('левый бок: пикселей', n_face, 'надписи:', n_txt)
    (OUT / 'masks.json').write_text(json.dumps({'name': NAME_LINES, 'name_center': NAME_C, 'switch': SW_LABELS,
                                                'switch_center': SW_C}, ensure_ascii=False),
                                    encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
