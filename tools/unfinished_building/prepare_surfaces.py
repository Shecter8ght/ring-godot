from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "high"
OUT = ROOT / "assets" / "textures" / "unfinished_building"
SURFACES = ["ugtkadmg", "ugtmehro", "uflnbcofw", "ug3sbcady", "ugkjec3ew", "ugqldhflw"]
CHANNELS = ["Albedo", "Normal", "Roughness", "AO", "Displacement"]
for asset_id in SURFACES:
    target = OUT / asset_id
    target.mkdir(parents=True, exist_ok=True)
    for channel in CHANNELS:
        source = SOURCE / asset_id / f"{asset_id}_4K_{channel}.jpg"
        if source.exists():
            shutil.copy2(source, target / source.name)
            print(source.name)
print(OUT)
