"""Материалы слотов моделей двора (зона 1, объект 5): assets/zone01/materials/<Слот>.tres.

python tools/build_zone01_materials.py
Слоты называет Blender-генератор (tools/build_khrushchevka.py и др.); здесь каждому — PBR-текстура
Poly Haven (CC0) с оттенком и шейдер старения src/world/facade_aged.gdshader, или простая краска.
UV у моделей в метрах; масштаб плитки — uv_scale = 1 / размер плитки, м.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/zone01/materials"
GRIME = "res://assets/shelter/textures/grime/"

# слот: (текстура Poly Haven, плитка м, оттенок RGB, металл, параметры старения)
AGED = {
    "PanelConcrete": ("rough_concrete", 1.6, (1.08, 1.06, 1.0), False, dict(streaks=0.75, roof_runoff=0.5, contrast=0.3, normal_scale=0.3)),
    "Mastic": ("concrete_wall_008", 2.0, (0.55, 0.53, 0.5), False, dict(streaks=0.3)),
    "Plinth": ("concrete_wall_007", 2.5, (0.78, 0.77, 0.74), False, dict(splash=0.8, moss=0.4)),
    "Brick": ("whitewashed_brick", 1.6, (1.05, 1.04, 1.0), False, dict(streaks=0.6, roof_runoff=0.4, contrast=0.8)),
    "BrickRed": ("red_bricks_04", 1.8, (0.85, 0.8, 0.78), False, dict(splash=0.7, moss=0.35)),
    "Lintel": ("concrete_wall_007", 2.0, (0.92, 0.91, 0.88), False, dict(streaks=0.6)),
    "Concrete": ("concrete_floor_02", 2.5, (0.85, 0.84, 0.8), False, dict(streaks=0.3, splash=0.4)),
    "Paint": ("concrete_wall_008", 1.5, (0.55, 0.6, 0.58), False, dict(streaks=0.2)),
    "Roofing": ("tarred_gravel", 3.0, (0.75, 0.75, 0.75), False, dict(streaks=0.0, splash=0.0, moss=0.3)),
    "Slate": ("worn_corrugated_iron", 1.4, (0.62, 0.63, 0.6), False, dict(streaks=0.3, splash=0.0, moss=0.45)),
    "Galv": ("rusty_metal_sheet", 1.5, (0.78, 0.8, 0.82), True, dict(streaks=0.3, splash=0.0)),
    "RustMetal": ("rusty_metal_sheet", 1.2, (0.9, 0.82, 0.75), True, dict(streaks=0.3)),
    "DoorMetal": ("rusty_metal_sheet", 1.6, (0.55, 0.62, 0.66), True, dict(streaks=0.3, splash=0.6)),
    "CorrGreen": ("worn_corrugated_iron", 1.4, (0.55, 0.72, 0.5), False, dict(streaks=0.4)),
    "CorrYellow": ("worn_corrugated_iron", 1.4, (1.0, 0.85, 0.5), False, dict(streaks=0.4)),
    "CorrBlue": ("worn_corrugated_iron", 1.4, (0.55, 0.7, 0.9), False, dict(streaks=0.4)),
    "CorrGrey": ("worn_corrugated_iron", 1.4, (0.82, 0.83, 0.82), False, dict(streaks=0.4)),
    "Plywood": ("plywood", 2.4, (0.85, 0.8, 0.72), False, dict(streaks=0.5, splash=0.3)),
    "WoodPlanks": ("wood_planks_grey", 2.0, (0.9, 0.88, 0.85), False, dict(streaks=0.4)),
    "BenchWood": ("wood_planks_grey", 1.5, (0.8, 0.66, 0.48), False, dict(streaks=0.2, splash=0.3)),
    "PaintGreenMetal": ("rusty_metal_sheet", 1.2, (0.42, 0.6, 0.45), True, dict(streaks=0.4, splash=0.5)),
    "GarageMetal": ("rusty_metal_sheet", 1.5, (0.78, 0.55, 0.4), True, dict(streaks=0.5, splash=0.6)),
    "GarageBlue": ("rusty_metal_sheet", 1.5, (0.45, 0.58, 0.72), True, dict(streaks=0.5, splash=0.6)),
    "PlayRed": ("rusty_metal_sheet", 1.0, (0.95, 0.4, 0.32), True, dict(streaks=0.2)),
    "PlayBlue": ("rusty_metal_sheet", 1.0, (0.4, 0.55, 0.85), True, dict(streaks=0.2)),
    "PlayYellow": ("rusty_metal_sheet", 1.0, (1.0, 0.85, 0.4), True, dict(streaks=0.2)),
    "Sand": ("gravel_stones", 1.5, (1.05, 0.92, 0.72), False, dict(streaks=0.0, splash=0.0, moss=0.0, contrast=0.5)),
    "YardAsphalt": ("worn_asphalt", 4.0, (0.92, 0.92, 0.9), False, dict(streaks=0.0, splash=0.0, moss=0.15, contrast=0.85)),
    "YardWalk": ("worn_asphalt", 3.0, (1.12, 1.1, 1.06), False, dict(streaks=0.0, splash=0.0, moss=0.2, contrast=0.7)),
    "Curb": ("concrete_wall_007", 1.5, (0.95, 0.94, 0.9), False, dict(streaks=0.0, splash=0.6, moss=0.4, splash_height=0.3)),
    "BarkDark": ("bark_brown_02", 1.2, (0.8, 0.76, 0.72), False, dict(streaks=0.0, splash=0.5, moss=0.5, roof_runoff=0.0)),
}

# простая краска: альбедо, шероховатость, металл
FLAT = {
    "Glass": ((0.06, 0.07, 0.075), 0.08, 0.55),
    "Interior": ((0.035, 0.032, 0.03), 1.0, 0.0),
    "Void": ((0.01, 0.01, 0.01), 1.0, 0.0),
    "Curtain1": ((0.62, 0.58, 0.46), 0.95, 0.0),
    "Curtain2": ((0.42, 0.17, 0.14), 0.95, 0.0),
    "Curtain3": ((0.5, 0.53, 0.58), 0.95, 0.0),
    "FrameWhite": ((0.66, 0.65, 0.6), 0.7, 0.0),
    "FrameTeal": ((0.1, 0.36, 0.37), 0.6, 0.0),
    "FrameBrown": ((0.3, 0.19, 0.12), 0.65, 0.0),
    "FramePVC": ((0.8, 0.8, 0.78), 0.45, 0.0),
    "Railing": ((0.12, 0.36, 0.37), 0.55, 0.3),
    "GasPipe": ((0.72, 0.56, 0.12), 0.5, 0.2),
    "Bars": ((0.1, 0.1, 0.1), 0.6, 0.5),
    "LampHead": ((0.35, 0.37, 0.37), 0.5, 0.6),
    "Wire": ((0.04, 0.04, 0.04), 0.6, 0.3),
}

# свои текстуры (tools/build_zone01_foliage_textures.py): кора берёзы, листва с альфой
TEXTURED = {
    "BarkBirch": ("res://assets/zone01/textures/bark_birch.png", "res://assets/textures/bark_brown_02/normal.jpg", 1.4, False),
    # (оттенок берёзы — в FOLIAGE_TINT: белая кора не должна светиться)
    "LeavesBirch": ("res://assets/zone01/textures/leaves_birch.png", "", 1.0, True),
    "LeavesMaple": ("res://assets/zone01/textures/leaves_maple.png", "", 1.0, True),
    "GrassTuft": ("res://assets/zone01/textures/grass_tufts.png", "", 1.0, True),
}


def aged(name: str, tex: str, tile: float, tint, metal: bool, extra: dict) -> str:
    params = dict(contrast=1.0, albedo_color=f"Color({tint[0]}, {tint[1]}, {tint[2]}, 1)", uv_scale=round(1.0 / tile, 4),
                  use_metal="true" if metal else "false", splash=0.55, streaks=0.45, moss=0.25, roof_runoff=0.35)
    params.update({k: v for k, v in extra.items()})
    lines = [
        '[gd_resource type="ShaderMaterial" load_steps=7 format=3]', "",
        '[ext_resource type="Shader" path="res://src/world/facade_aged.gdshader" id="1"]',
        f'[ext_resource type="Texture2D" path="res://assets/textures/{tex}/albedo.jpg" id="2"]',
        f'[ext_resource type="Texture2D" path="res://assets/textures/{tex}/normal.jpg" id="3"]',
        f'[ext_resource type="Texture2D" path="res://assets/textures/{tex}/arm.jpg" id="4"]',
        f'[ext_resource type="Texture2D" path="{GRIME}macro.png" id="5"]',
        f'[ext_resource type="Texture2D" path="{GRIME}streaks.png" id="6"]', "",
        "[resource]", f'resource_name = "{name}"', 'shader = ExtResource("1")',
        'shader_parameter/albedo_tex = ExtResource("2")', 'shader_parameter/normal_tex = ExtResource("3")',
        'shader_parameter/orm_tex = ExtResource("4")', 'shader_parameter/macro_tex = ExtResource("5")',
        'shader_parameter/streak_tex = ExtResource("6")',
    ]
    lines += [f"shader_parameter/{k} = {v}" for k, v in params.items()]
    return "\n".join(lines) + "\n"


def flat(name: str, color, rough: float, metal: float) -> str:
    return "\n".join([
        '[gd_resource type="StandardMaterial3D" format=3]', "", "[resource]", f'resource_name = "{name}"',
        f"albedo_color = Color({color[0]}, {color[1]}, {color[2]}, 1)", f"roughness = {rough}", f"metallic = {metal}",
        "metallic_specular = 0.5",
    ]) + "\n"


# оттенок альбедо листвы (рендер атласа ели светлее, чем крона в тени)
FOLIAGE_TINT = {"BarkBirch": (0.72, 0.72, 0.7), "FirBranchCards": (0.62, 0.68, 0.6), "LeavesMaple": (0.6, 0.56, 0.44), "LeavesBirch": (0.86, 0.84, 0.68),
                "GrassTuft": (0.85, 0.82, 0.7)}


def textured(name: str, albedo: str, normal: str, tile: float, foliage: bool) -> str:
    ext = [f'[ext_resource type="Texture2D" path="{albedo}" id="1"]']
    body = [f'resource_name = "{name}"', 'albedo_texture = ExtResource("1")', "roughness = 0.85"]
    if normal:
        ext.append(f'[ext_resource type="Texture2D" path="{normal}" id="2"]')
        body += ["normal_enabled = true", 'normal_texture = ExtResource("2")', "normal_scale = 0.6"]
    if foliage:
        # карточки листвы: отсечение по альфе, видны с обеих сторон, просвечивают на солнце
        body += ["transparency = 2", "alpha_scissor_threshold = 0.45", "cull_mode = 2", "backlight_enabled = true",
                 "backlight = Color(0.35, 0.3, 0.12, 1)", "texture_filter = 5", "vertex_color_use_as_albedo = true"]
        if name in FOLIAGE_TINT:
            t = FOLIAGE_TINT[name]
            body += [f"albedo_color = Color({t[0]}, {t[1]}, {t[2]}, 1)", "backlight = Color(0.12, 0.14, 0.08, 1)"]
    elif name in FOLIAGE_TINT:
        t = FOLIAGE_TINT[name]
        body += [f"albedo_color = Color({t[0]}, {t[1]}, {t[2]}, 1)"]
    else:
        body += [f"uv1_scale = Vector3({round(1 / tile, 4)}, {round(1 / tile, 4)}, 1)", "texture_filter = 5"]
    head = [f'[gd_resource type="StandardMaterial3D" load_steps={len(ext) + 1} format=3]', ""]
    return "\n".join(head + ext + ["", "[resource]"] + body) + "\n"


SPRUCE_TREES = ["spruce_forest_a", "spruce_forest_b", "spruce_open", "spruce_young_a", "spruce_young_b"]


def shader_mat(name: str, shader: str, textures: dict, params: dict) -> str:
    ext = [f'[ext_resource type="Shader" path="{shader}" id="1"]']
    lines = []
    for i, (key, path) in enumerate(textures.items(), start=2):
        ext.append(f'[ext_resource type="Texture2D" path="{path}" id="{i}"]')
        lines.append(f'shader_parameter/{key} = ExtResource("{i}")')
    lines += [f"shader_parameter/{k} = {v}" for k, v in params.items()]
    return "\n".join([f'[gd_resource type="ShaderMaterial" load_steps={len(ext) + 1} format=3]', ""] + ext +
                     ["", "[resource]", f'resource_name = "{name}"', 'shader = ExtResource("1")'] + lines) + "\n"


def spruce_materials() -> None:
    """Ель (tools/build_spruce.py): хвоя, дальние силуэты, кора ствола (старая/молодая), ветки, шишки."""
    t = "res://assets/zone01/textures/"
    fol = "res://src/world/spruce_foliage.gdshader"
    bark = "res://src/world/spruce_bark.gdshader"
    pine, knot = "res://assets/textures/pine_bark/", "res://assets/textures/knotted_pine_bark/"
    files = {"SpruceNeedles": shader_mat("SpruceNeedles", fol, {"albedo_tex": t + "spruce_atlas_albedo.png",
                                                                 "normal_tex": t + "spruce_atlas_normal.png"}, {})}
    for tree in SPRUCE_TREES:
        files[f"SpruceFar_{tree}"] = shader_mat(f"SpruceFar_{tree}", fol, {"albedo_tex": t + f"{tree}_far_albedo.png",
                                                                          "normal_tex": t + f"{tree}_far_normal.png"},
                                                {"far": "true", "alpha_cut": 0.5})
    both = {"old_albedo": pine + "albedo.jpg", "old_normal": pine + "normal.jpg", "old_arm": pine + "arm.jpg",
            "young_albedo": knot + "albedo.jpg", "young_normal": knot + "normal.jpg", "young_arm": knot + "arm.jpg"}
    files["SpruceTrunk"] = shader_mat("SpruceTrunk", bark, both, {"old_height": 7.0})
    files["SpruceTrunkYoung"] = shader_mat("SpruceTrunkYoung", bark, both, {"old_height": 0.0, "moss": 0.25})
    files["SpruceBranch"] = shader_mat("SpruceBranch", bark, both, {"old_height": 0.0, "moss": 0.0,
                                                                    "young_tint": "Color(0.62, 0.56, 0.5, 1)"})
    files["SpruceDeadBranch"] = shader_mat("SpruceDeadBranch", bark, both, {"old_height": 0.0, "moss": 0.0,
                                                                            "young_tint": "Color(0.72, 0.7, 0.68, 1)"})
    files["SpruceCone"] = shader_mat("SpruceCone", bark, both, {"old_height": 100.0, "moss": 0.0, "old_saturation": 1.0,
                                                                "old_tint": "Color(0.75, 0.55, 0.4, 1)", "uv_scale": 3.0})
    for name, text in files.items():
        (OUT / f"{name}.tres").write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (tex, tile, tint, metal, extra) in AGED.items():
        (OUT / f"{name}.tres").write_text(aged(name, tex, tile, tint, metal, extra), encoding="utf-8")
    for name, (color, rough, metal) in FLAT.items():
        (OUT / f"{name}.tres").write_text(flat(name, color, rough, metal), encoding="utf-8")
    for name, (albedo, normal, tile, foliage) in TEXTURED.items():
        (OUT / f"{name}.tres").write_text(textured(name, albedo, normal, tile, foliage), encoding="utf-8")
    spruce_materials()
    print(f"zone01 materials: {len(AGED) + len(FLAT) + len(TEXTURED)}")


if __name__ == "__main__":
    main()
