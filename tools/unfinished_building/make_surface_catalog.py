from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "high"
paths = sorted(path for path in SOURCE.glob("*/*_4K_Albedo.jpg") if not (path.parent / f"{path.parent.name}.fbx").exists())
cell_w, cell_h = 260, 286
columns = 6
rows = (len(paths) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (28, 30, 32))
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 19)
for index, path in enumerate(paths):
    image = Image.open(path).convert("RGB")
    image.thumbnail((cell_w - 8, cell_w - 8), Image.Resampling.LANCZOS)
    x = (index % columns) * cell_w
    y = (index // columns) * cell_h
    sheet.paste(image, (x + (cell_w - image.width) // 2, y + (cell_w - image.height) // 2))
    draw.text((x + 10, y + cell_w + 2), path.parent.name, font=font, fill=(235, 235, 235))
out = ROOT / "_asset_src" / "unfinished_building" / "surfaces.jpg"
sheet.save(out, quality=90)
print(out)
