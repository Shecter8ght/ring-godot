"""Клёны и тополя зоны 1 → Godot (python, PIL): карты WebP, настройки импорта, материалы.

    python -X utf8 tools/zone01_trees/godot_assets.py

Берёт выгрузку tools/zone01_trees/export_game.py (сетки assets/zone01/trees/*.glb, атласы PNG в _asset_src/zone01_trees/textures)
и пишет (функциями растений «Проспекта», tools/prospekt_plants/godot_assets.py):
  assets/zone01/trees/textures/*.webp (атласы веточек и дальние виды) и их .import (нормали — как карты нормалей);
  assets/zone01/trees/materials/<имя слота>.tres — шейдеры проекта: листва и дальний вид — spruce_foliage (ветер, затенение
  в кроне по цвету вершин, просвет, сырость в дождь), кора — spruce_bark (старая бороздчатая внизу, гладкая выше, мох с севера,
  ветер, сырость); гладкая кора ветвей — карты растений «Проспекта» (assets/models/plants/textures), они уже в игре;
  .import сеток — без автоматических LOD движка (свои LOD — узлы DistrictScatter карты).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/prospekt_plants"))
import godot_assets as PG  # noqa: E402

PG.SRC_TEX = ROOT / "_asset_src/zone01_trees/textures"
PG.OUT = ROOT / "assets/zone01/trees"
PG.TEX = PG.OUT / "textures"
PG.MATS = PG.OUT / "materials"
PG.RES = "res://assets/zone01/trees"
color = PG.color

PLANTS_TEX = "res://assets/models/plants/textures"
MAT = {"maple": "Maple", "negundo": "Negundo", "poplar": "Z1Poplar"}
# листва поздней осенью: просвет тёплый (жёлтый лист светится на солнце), оттенок — чуть тусклее фото, разброс между деревьями
LEAVES = {"maple": ((0.3, 0.2, 0.05), (0.86, 0.84, 0.78), 0.14), "negundo": ((0.26, 0.22, 0.06), (0.86, 0.85, 0.78), 0.12),
          "poplar": ((0.22, 0.22, 0.07), (0.85, 0.86, 0.8), 0.12)}
# старая бороздчатая кора внизу тополей, м (как в PBR-файле, tools/zone01_trees/pbr.py)
POPLAR_OLD = {"0": 8.0, "1": 7.0, "2": 2.2}


def materials() -> None:
    foliage = "res://src/world/spruce_foliage.gdshader"
    bark = "res://src/world/spruce_bark.gdshader"
    for kind, m in MAT.items():
        tex = {k: PG.webp(f"{kind}_{k}") for k in ("atlas_albedo", "atlas_normal", "far_albedo", "far_normal")}
        tr, tint, var = LEAVES[kind]
        PG.tres(f"Plant{m}Leaves", foliage, {"translucency": color(tr), "tint": color(tint), "alpha_cut": "0.4", "variation": var},
                {"albedo_tex": tex["atlas_albedo"], "normal_tex": tex["atlas_normal"]})
        PG.tres(f"Plant{m}Far", foliage, {"translucency": color(tr), "tint": color(tint), "alpha_cut": "0.45", "variation": var,
                                          "far": "true"},
                {"albedo_tex": tex["far_albedo"], "normal_tex": tex["far_normal"]})
    brown = {"old_albedo": "res://assets/textures/bark_brown_02/albedo.jpg", "old_normal": "res://assets/textures/bark_brown_02/normal.jpg",
             "old_arm": "res://assets/textures/bark_brown_02/arm.jpg"}
    furrowed = {"old_albedo": "res://assets/textures/bark001/albedo.jpg", "old_normal": "res://assets/textures/bark001/normal.jpg"}
    shrub = {"young_albedo": f"{PLANTS_TEX}/shrub_bark_albedo.webp", "young_normal": f"{PLANTS_TEX}/shrub_bark_normal.webp",
             "young_arm": f"{PLANTS_TEX}/shrub_bark_arm.webp"}
    poplar_young = {"young_albedo": f"{PLANTS_TEX}/poplar_bark_young_albedo.webp",
                    "young_normal": f"{PLANTS_TEX}/poplar_bark_young_normal.webp", "young_arm": f"{PLANTS_TEX}/poplar_bark_young_arm.webp"}
    # клён остролистный: весь ствол — серо-бурая бороздчатая (фото Poly Haven), ветви — гладкая буроватая
    PG.tres("PlantMapleBark", bark, {"old_height": 100.0, "old_saturation": 0.5, "old_tint": color((0.8, 0.8, 0.8)), "moss": 0.5},
            {**brown, **shrub})
    PG.tres("PlantMapleBranch", bark, {"old_height": 0.0, "young_tint": color((0.78, 0.7, 0.62)), "moss": 0.0}, {**brown, **shrub})
    # ясенелистный: кора светлее, молодые ветви с сизо-зелёным налётом
    PG.tres("PlantNegundoBark", bark, {"old_height": 100.0, "old_saturation": 0.42, "old_tint": color((1.0, 0.98, 0.95)),
                                       "moss": 0.35}, {**brown, **shrub})
    PG.tres("PlantNegundoBranch", bark, {"old_height": 0.0, "young_tint": color((0.86, 0.95, 0.8)), "moss": 0.0}, {**brown, **shrub})
    # тополь: внизу старая бороздчатая (Bark001), выше — серо-зелёная гладкая; высота своя у экземпляра
    for key, h in POPLAR_OLD.items():
        PG.tres(f"PlantZ1PoplarBark_{key}", bark, {"old_height": h, "old_saturation": 0.45, "old_tint": color((0.8, 0.8, 0.78)),
                                                    "young_tint": color((1, 1, 1)), "moss": 0.5}, {**furrowed, **poplar_young})
    PG.tres("PlantZ1PoplarBranch", bark, {"old_height": 0.0, "young_tint": color((1, 1, 1)), "moss": 0.0}, {**furrowed, **poplar_young})
    # сухие сучья и обломки — серая выветренная кора (не светлее ствола: в игре светлые торчали «гвоздями»)
    for m in MAT.values():
        PG.tres(f"Plant{m}Dead", bark, {"old_height": 0.0, "young_tint": color((0.72, 0.69, 0.65)), "moss": 0.0}, {**brown, **shrub})


def main() -> None:
    materials()
    PG.glb_imports()
    print("клёны и тополя зоны 1 → Godot: материалы %d, карты %d, сеток %d" % (
        len(list(PG.MATS.glob("*.tres"))), len(list(PG.TEX.glob("*.webp"))), len(list(PG.OUT.glob("*.glb")))))


if __name__ == "__main__":
    main()
