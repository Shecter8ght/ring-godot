"""«Проспект», ограждения и город: лёгкая резкость карт после выгрузки Painter — цвет и шероховатость отдельно
(навык «дерево и крашеный металл»: слабая резкость в конце; сильная шумит). В API Painter фильтр поверх слоёв не
ставится, поэтому — здесь, нерезкой маской.

    python -X utf8 tools/prospekt_city/sharpen_maps.py <папка textures> [набор …]

Без наборов — все <набор>_baseColor.png с парой _occlusionRoughnessMetallic.png, кроме плиточных карт проволоки.
"""
import sys
from pathlib import Path

from PIL import Image, ImageFilter

SKIP = ("Razor", "Barbed", "Rebar")


def main() -> None:
    folder = Path(sys.argv[1])
    sets = sys.argv[2:] or [p.name[:-len("_baseColor.png")] for p in folder.glob("*_baseColor.png")]
    for ts in sets:
        if ts in SKIP:
            continue
        bc, orm = folder / f"{ts}_baseColor.png", folder / f"{ts}_occlusionRoughnessMetallic.png"
        if not bc.exists() or not orm.exists():
            continue
        im = Image.open(bc)
        # Painter при нехватке видеопамяти выгружает набор пустым (одним цветом) — предупредить, круг повторить
        lo, hi = im.convert("L").getextrema()
        if hi - lo < 6:
            print(f"ПУСТАЯ КАРТА: {ts} — набор не посчитан (видеопамять?), повторить sp_cycle.sh")
        rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
        if im.mode == "RGBA":
            rgb.putalpha(im.getchannel("A"))
        rgb.save(bc)
        o = Image.open(orm).convert("RGB")
        r, g, b = o.split()
        g = g.filter(ImageFilter.UnsharpMask(radius=1.2, percent=30, threshold=2))
        Image.merge("RGB", (r, g, b)).save(orm)
        print("резкость:", ts)


if __name__ == "__main__":
    main()
