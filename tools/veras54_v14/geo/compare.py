# ВЕРАС-54 v14: листы сверки наших кадров (shots.py) со снимками образца теми же камерами.
#   python -X utf8 tools/veras54_v14/geo/compare.py <папка кадров> <папка листов> [вид,вид…] [--zoom 1] [--crop x0 y0 x1 y1] [--ov] [--name _суффикс]
# Лист: образец | наш кадр | наложение (образец — красным, наш — голубым; совпало — серое). --crop — прямоугольник
# в пикселях кадра 800 × 635, --zoom — увеличение листа, --ov — только наложение, --name — суффикс имени листа.
import glob
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "_asset_src", "veras54_v14_geo"))


def ref_for(name):
    for pat in (os.path.join(ROOT, "refs", "tiles", name + ".jpg"), os.path.join(ROOT, "refs", "sketchfab", name + "__*.jpg")):
        g = glob.glob(pat)
        if g:
            return g[0]
    return None


def main():
    a = sys.argv[1:]
    shots, out = a[0], a[1]
    only = None; zoom = 1.0; crop = None; ov_only = False; suffix = ""
    i = 2
    while i < len(a):
        if a[i] == "--zoom": zoom = float(a[i + 1]); i += 2
        elif a[i] == "--crop": crop = tuple(int(v) for v in a[i + 1:i + 5]); i += 5
        elif a[i] == "--ov": ov_only = True; i += 1
        elif a[i] == "--name": suffix = a[i + 1]; i += 2
        else: only = set(a[i].split(",")); i += 1
    os.makedirs(out, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(shots, "*.jpg"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if only and name not in only:
            continue
        r = ref_for(name)
        if not r:
            continue
        ref = Image.open(r).convert("RGB")
        our = Image.open(path).convert("RGB").resize(ref.size, Image.LANCZOS)
        red = ref.convert("L").point(lambda v: min(255, int(v * 2.0)))
        cy = our.convert("L")
        ov = Image.merge("RGB", (red, cy, cy))
        parts = [ov] if ov_only else [ref, our, ov]
        if crop:
            parts = [p.crop(crop) for p in parts]
        if zoom != 1.0:
            parts = [p.resize((int(p.width * zoom), int(p.height * zoom)), Image.LANCZOS) for p in parts]
        w, h = parts[0].size
        sheet = Image.new("RGB", (w * len(parts) + 6 * (len(parts) - 1), h), (255, 0, 255))
        for k, p in enumerate(parts):
            sheet.paste(p, (k * (w + 6), 0))
        ImageDraw.Draw(sheet).text((6, h - 14), name, fill=(255, 220, 0))
        sheet.save(os.path.join(out, name + suffix + ".jpg"), quality=88)
        print("SHEET", name)


if __name__ == "__main__":
    main()
