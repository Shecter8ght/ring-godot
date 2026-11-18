# ВЕРАС-54 v14: кусок снимка образца (плитки Sketchfab, refs/tiles) с сеткой в миллиметрах осей ВЕРАС.
#   python -X utf8 tools/veras54_v14/geo/ref_tiles.py <плитка> <выход.png> [u0 v0 u1 v1] [--zoom 3] [--step 5] [--depth 16.5]
# Плитка — имя файла из refs/tiles: R_x…_z…_f… (правый бок, камера с −Y), L_… (левый бок), T_x…_f… (сверху),
# U_x…_f… (снизу), B_z…_f… (сзади), F_z…_f… (спереди). Камера почти ортогональная: расстояние 6 м (торцы — 6,5 м),
# угол зрения f градусов по вертикали кадра. u, v — оси кадра в мм ВЕРАС: бок — (X, Z); сверху и снизу — (X, Y);
# торцы — (Y, Z). u0 v0 u1 v1 — вырезать прямоугольник в этих мм. --depth — на сколько мм плоскость детали ближе
# к камере, чем плоскость симметрии (борт коробки — 16,5; сверху: высота Z детали минус 20,5).
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "_asset_src", "veras54_v14_geo"))
TILES = os.path.join(ROOT, "refs", "tiles")
DX, DZ = 252.1, -279.5           # оси образца (м) → ВЕРАС (мм): x·1000 + DX, z·1000 + DZ
W, H = 800, 635


def camera(name):
    """(вид, центр u, центр v, мм на пиксель на плоскости симметрии, расстояние, знак u, знак v)."""
    b = os.path.splitext(os.path.basename(name))[0]
    kind = b[0]
    num = {k: float(v) for k, v in re.findall(r"_([xzf])(-?[0-9.]+)", b)}
    f = num["f"]
    dist = 6500.0 if kind in "BF" else 6000.0
    s = 2.0 * dist * math.tan(math.radians(f) / 2.0) / H
    if kind in "RL":
        cu, cv = num["x"] * 1000 + DX, num["z"] * 1000 + DZ
        su = 1 if kind == "R" else -1
        return kind, cu, cv, s, dist, su, 1
    if kind in "TU":
        cu, cv = num["x"] * 1000 + DX, 0.0
        return kind, cu, cv, s, dist, 1, (1 if kind == "T" else -1)
    cu, cv = 0.0, num["z"] * 1000 + DZ
    return kind, cu, cv, s, dist, (-1 if kind == "B" else 1), 1


def main():
    from PIL import Image, ImageDraw, ImageFont
    a = sys.argv[1:]
    tile, out = a[0], a[1]
    zoom, step, depth = 3.0, 5.0, 0.0
    rest = []
    i = 2
    while i < len(a):
        if a[i] == "--zoom": zoom = float(a[i + 1]); i += 2
        elif a[i] == "--step": step = float(a[i + 1]); i += 2
        elif a[i] == "--depth": depth = float(a[i + 1]); i += 2
        else: rest.append(float(a[i])); i += 1
    path = tile if os.path.exists(tile) else os.path.join(TILES, tile)
    kind, cu, cv, s, dist, su, sv = camera(path)
    s *= (dist - depth) / dist

    def to_px(u, v):
        return W / 2 + su * (u - cu) / s, H / 2 - sv * (v - cv) / s

    def to_mm(px, py):
        return cu + su * (px - W / 2) * s, cv - sv * (py - H / 2) * s
    im = Image.open(path).convert("RGB")
    if rest:
        (xa, ya), (xb, yb) = to_px(rest[0], rest[1]), to_px(rest[2], rest[3])
        box = (max(0, int(min(xa, xb))), max(0, int(min(ya, yb))), min(W, int(max(xa, xb)) + 1), min(H, int(max(ya, yb)) + 1))
    else:
        box = (0, 0, W, H)
    crop = im.crop(box).resize((int((box[2] - box[0]) * zoom), int((box[3] - box[1]) * zoom)), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    u_a, v_a = to_mm(box[0], box[1]); u_b, v_b = to_mm(box[2], box[3])
    u0, u1 = sorted((u_a, u_b)); v0, v1 = sorted((v_a, v_b))
    k = math.ceil(u0 / step)
    while k * step <= u1:
        px = (to_px(k * step, 0)[0] - box[0]) * zoom
        major = (k * step) % (step * 2) == 0
        d.line([(px, 0), (px, crop.height)], fill=(255, 220, 0) if major else (150, 130, 0), width=1)
        if major:
            d.text((px + 2, 2), f"{k * step:g}", fill=(255, 255, 0), font=font)
        k += 1
    k = math.ceil(v0 / step)
    while k * step <= v1:
        py = (to_px(0, k * step)[1] - box[1]) * zoom
        major = (k * step) % (step * 2) == 0
        d.line([(0, py), (crop.width, py)], fill=(0, 230, 255) if major else (0, 120, 140), width=1)
        if major:
            d.text((2, py + 1), f"{k * step:g}", fill=(0, 255, 255), font=font)
        k += 1
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    crop.save(out)
    print(f"{kind}: {s:.4f} мм/пикс, кадр u {u0:.1f}…{u1:.1f}, v {v0:.1f}…{v1:.1f} → {out} {crop.size}")


if __name__ == "__main__":
    main()
