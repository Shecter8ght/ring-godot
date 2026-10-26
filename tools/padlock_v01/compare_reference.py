"""Place untouched reference/candidate crops together; only composite the render's background."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
ref=Image.open(WORK/'references'/'reference_01_front34.png').convert('RGB')
raw=Image.open(WORK/'checks'/'reference_view_v05_raw.png').convert('RGBA')
assert ref.size==raw.size==(1280,720)
bg=Image.new('RGBA',raw.size,(51,51,51,255));bg.alpha_composite(raw);candidate=bg.convert('RGB')
candidate.save(WORK/'previews'/'reference_view_v05.png')
pair=Image.new('RGB',(1280,752),(42,42,42))
pair.paste(ref.crop((320,0,960,720)),(0,0));pair.paste(candidate.crop((320,0,960,720)),(640,0))
d=ImageDraw.Draw(pair);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
d.text((16,727),'Референс владельца · Fab',fill=(225,225,225),font=font)
d.text((656,727),'Замок v05 · приближённый ракурс и свет',fill=(225,225,225),font=font)
pair.save(WORK/'previews'/'reference_comparison_v05.png')
print('REFERENCE_COMPARISON_READY',WORK/'previews'/'reference_comparison_v05.png')
