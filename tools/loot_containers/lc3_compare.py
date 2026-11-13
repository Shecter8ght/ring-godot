"""Листы сверки v03: образец владельца слева, наш кадр справа (одна высота). Запуск (системный Python с PIL):
  python -X utf8 tools/loot_containers/lc3_compare.py [gun safe cash]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Loot_Containers")
OBR = LIB / "Образцы_владельца_2026-11-13"
OUT = LIB / "Просмотр" / "finish_v03"
# лист: (образец, наш кадр, обрезка нашего кадра по долям (x0, y0, x1, y1) или None)
SHEETS = {
    "gun": ("gun_locker_owner.png", "gun_open.png", None),
    "safe": ("safe_sketchfab_1.jpg", "safe_closed.png", None),
    "cash": ("cashier_sketchfab_1.jpg", "cash_closed.png", None),
}


def main() -> None:
    names = sys.argv[1:] or list(SHEETS)
    for n in names:
        a, b, crop = SHEETS[n]
        ia = Image.open(OBR / a).convert("RGB")
        ib = Image.open(OUT / b).convert("RGB")
        if crop:
            w, h = ib.size
            ib = ib.crop((int(w * crop[0]), int(h * crop[1]), int(w * crop[2]), int(h * crop[3])))
        h = 900
        ia = ia.resize((int(ia.width * h / ia.height), h), Image.LANCZOS)
        ib = ib.resize((int(ib.width * h / ib.height), h), Image.LANCZOS)
        sheet = Image.new("RGB", (ia.width + ib.width + 12, h), (40, 40, 40))
        sheet.paste(ia, (0, 0))
        sheet.paste(ib, (ia.width + 12, 0))
        d = ImageDraw.Draw(sheet)
        d.text((10, 10), "образец владельца", fill=(255, 255, 0))
        d.text((ia.width + 22, 10), "наш кадр v03", fill=(255, 255, 0))
        sheet.save(OUT / f"сверка_{n}.png")
        print("ok", n)


if __name__ == "__main__":
    main()
