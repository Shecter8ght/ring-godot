from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PATHS = [ROOT / "assets" / "models" / "unfinished_building" / "textures", ROOT / "assets" / "textures" / "unfinished_building"]

def set_value(text, key, value):
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, f"{key}={value}", text, flags=re.MULTILINE)
    return text + f"\n{key}={value}\n"

count = 0
for folder in PATHS:
    for path in folder.rglob("*.import"):
        text = path.read_text(encoding="utf-8")
        if 'importer="texture"' not in text:
            continue
        text = set_value(text, "compress/mode", "2")
        text = set_value(text, "mipmaps/generate", "true")
        text = set_value(text, "detect_3d/compress_to", "0")
        is_normal = "_4K_Normal" in path.name
        text = set_value(text, "compress/normal_map", "1" if is_normal else "0")
        if "_AO-" in path.name and "_Roughness" in path.name:
            text = set_value(text, "roughness/mode", "3")
        elif "_4K_Roughness" in path.name:
            text = set_value(text, "roughness/mode", "6")
        else:
            text = set_value(text, "roughness/mode", "1")
        if "Roughness" in path.name:
            normal_name = path.name.split("_4K_")[0] + "_4K_Normal.jpg"
            normal_path = path.parent / normal_name
            if normal_path.exists():
                resource = "res://" + normal_path.relative_to(ROOT).as_posix()
                text = set_value(text, "roughness/src_normal", f'"{resource}"')
        path.write_text(text, encoding="utf-8")
        count += 1
print(f"CONFIGURED {count}")
