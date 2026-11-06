from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
image = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((10, 10, 502, 502), radius=115, fill='#161d28', outline='#364356', width=5)
for x, height, color in [(130, 115, '#b5a4d9'), (199, 265, '#edb27f'), (268, 193, '#edb27f'), (337, 80, '#8abfaf')]:
    draw.rounded_rectangle((x, (512-height)//2, x+34, (512+height)//2), radius=17, fill=color)
image.resize((256, 256), Image.Resampling.LANCZOS).save(root/'assets'/'icon.png')
image.save(root/'assets'/'icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
