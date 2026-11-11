"""Set Zerno's texture and mesh options after the first Godot import."""
from pathlib import Path
import re

ASSETS = Path(__file__).resolve().parents[2] / "assets/models/props/zerno"
MAPS = ASSETS / "maps"


def settings(path, options):
    before = path.read_text(encoding="utf-8-sig")
    after = before
    for name, value in options.items():
        after = re.sub(r"^" + re.escape(name) + r"=.*$", f"{name}={value}", after, flags=re.M)
    if after != before:
        path.write_text(after, encoding="utf-8")


for path in ASSETS.glob("*.glb.import"):
    settings(path, {"meshes/generate_lods": "false", "meshes/light_baking": "0",
                    "meshes/force_disable_compression": "true", "meshes/ensure_tangents": "true"})

for directory in (ASSETS, MAPS):
    for path in directory.glob("*.import"):
        if not path.name.endswith((".jpg.import", ".png.import")):
            continue
        name = path.name
        options = {"mipmaps/generate": "true", "compress/mode": "2", "detect_3d/compress_to": "0"}
        if "_normal" in name or "nor_gl" in name:
            options.update({"compress/normal_map": "1", "roughness/mode": "1"})
        elif "_orm" in name:
            normal = path.with_name(name.replace("_orm.png.import", "_normal.png"))
            if normal.exists():
                target = normal.relative_to(ASSETS).as_posix()
                options.update({"roughness/mode": "3",
                                "roughness/src_normal": f'"res://assets/models/props/zerno/{target}"'})
        elif "_color" in name and any(tag in name for tag in ("print", "facade_sign")):
            options["compress/mode"] = "0"
        elif "_color" in name:
            options["compress/high_quality"] = "true"
        if name in ("ceramic_local.png.import", "stock_floor.png.import", "case_cracks.png.import"):
            options.update({"compress/mode": "0", "process/fix_alpha_border": "false"})
        if name == "ceramic_rough.jpg.import":
            options.update({"roughness/mode": "6",
                            "roughness/src_normal": '"res://assets/models/props/zerno/maps/ceramic_normal.png"'})
        settings(path, options)
