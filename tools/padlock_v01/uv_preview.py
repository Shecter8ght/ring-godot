import colorsys
import json
from pathlib import Path
from PIL import Image,ImageDraw

work=Path(__file__).resolve().parents[2]/"_asset_src"/"padlock_v01"/"checks"
data=json.loads((work/"uv_layout.json").read_text(encoding="utf-8"))
image=Image.new("RGB",(1200,1200),(20,20,23));draw=ImageDraw.Draw(image)
for i,part in enumerate(data):
    color=tuple(round(v*255) for v in colorsys.hsv_to_rgb(i*.618%1,.45,.8))
    for polygon in part["polygons"]:
        draw.polygon([(u*1199,(1-v)*1199) for u,v in polygon],fill=color)
image.save(work/"uv_layout.png")
print(work/"uv_layout.png")
