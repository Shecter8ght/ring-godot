from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "catalog"
paths = sorted(SOURCE.glob("*.png"))
cell_w, cell_h = 280, 304
columns = 5
rows = (len(paths) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (28, 30, 32))
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
for index, path in enumerate(paths):
    image = Image.open(path).convert("RGBA")
    image.thumbnail((cell_w - 8, cell_w - 8), Image.Resampling.LANCZOS)
    x = (index % columns) * cell_w
    y = (index // columns) * cell_h
    sheet.paste(image, (x + (cell_w - image.width) // 2, y + (cell_w - image.height) // 2), image)
    draw.text((x + 12, y + cell_w + 2), path.stem, font=font, fill=(235, 235, 235))
out = ROOT / "_asset_src" / "unfinished_building" / "catalog.jpg"
sheet.save(out, quality=92)
print(out)
