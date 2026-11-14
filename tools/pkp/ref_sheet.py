# ПКП: лист-оглавление скачанных снимков-образцов (мелкие картинки с именами) — чтобы выбрать нужный, не открывая все.
#   python -X utf8 tools/pkp/ref_sheet.py <папка refs/web> <выход.png> [папка_внутри …] [--cols 5] [--w 480]
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    a = sys.argv[1:]
    root, out = a[0], a[1]
    cols = 5; w = 480; only = []
    i = 2
    while i < len(a):
        if a[i] == "--cols": cols = int(a[i + 1]); i += 2
        elif a[i] == "--w": w = int(a[i + 1]); i += 2
        else: only.append(a[i]); i += 1
    files = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if os.path.isdir(p) and (not only or d in only):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    files.append((d, f, os.path.join(p, f)))
    h = int(w * 0.66)
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 18)), (20, 20, 22))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    for k, (d, f, path) in enumerate(files):
        try:
            im = Image.open(path).convert("RGB")
        except Exception:
            continue
        im.thumbnail((w - 4, h - 2))
        x = (k % cols) * w; y = (k // cols) * (h + 18)
        sheet.paste(im, (x + 2, y + 18))
        dr.text((x + 3, y + 2), f"{d[:3]}/{f[:52]}", fill=(255, 220, 120), font=font)
    sheet.save(out)
    print("SHEET", out, sheet.size, len(files))


main()
