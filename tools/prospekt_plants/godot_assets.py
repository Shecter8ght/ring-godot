"""Растения «Проспекта» → Godot (python, PIL): карты WebP, настройки импорта, материалы и записи индекса моделей.

    python -X utf8 tools/prospekt_plants/godot_assets.py

Берёт выгрузку tools/prospekt_plants/game.py (сетки assets/models/plants/*.glb, отчёт _asset_src/prospekt_plants/game.json,
атласы и кору PNG в _asset_src/prospekt_plants/textures) и пишет:
  assets/models/plants/textures/*.webp (не больше 2K) и их .import (нормали — как карты нормалей);
  assets/models/plants/materials/<имя слота>.tres — шейдеры проекта: листва и дальний вид — spruce_foliage (ветер, затенение
  в кроне по цвету вершин, просвет), кора берёзы — birch_bark (береста, чёрный трещиноватый низ, мох), остальная — spruce_bark
  (старая кора внизу, гладкая выше, мох с севера); у всех — ветер spruce_wind и сырость в дождь;
  .import сеток — без автоматических LOD движка (у карточек они «съедают» крону; свои LOD — в индексе);
  data/urban95_models.json — записи P_<вид> (группа: экземпляр по позиции) и P_<ключ> (lods, cell, materials_dir, solids).
Индекс дописывается: файл перечитывается перед записью, чужие записи не трогаются.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC_TEX = ROOT / "_asset_src/prospekt_plants/textures"
OUT = ROOT / "assets/models/plants"
TEX = OUT / "textures"
MATS = OUT / "materials"
REPORT = ROOT / "_asset_src/prospekt_plants/game.json"
INDEX = ROOT / "data/urban95_models.json"
RES = "res://assets/models/plants"
MAX_TEX = 2048

LABEL = {"birch": "Берёза повислая", "linden": "Липа мелколистная", "poplar": "Тополь берлинский", "lilac": "Сирень обыкновенная",
         "hedge": "Живая изгородь (кизильник)"}
NAMES = {"birch_a": "взрослая, 16 м", "birch_b": "двуствольная, 14 м", "birch_c": "молодая, 8 м", "linden_a": "взрослая, 15 м",
         "linden_b": "средняя, 11 м", "linden_c": "молодая уличная, 7 м", "poplar_a": "взрослый, 21 м",
         "poplar_b": "кронированный, 15 м", "lilac_a": "старая, 3,2 м", "lilac_b": "средняя, 2,6 м", "lilac_c": "молодая, 2,1 м",
         "hedge_a": "4,2 м", "hedge_b": "2,1 м, торец", "hedge_c": "4,2 м, пролом"}
MAT = {"birch": "Birch", "linden": "Linden", "poplar": "Poplar", "lilac": "Lilac", "hedge": "Hedge"}
# дальность смены LOD по клетке пачки (м): LOD0, LOD1, дальний; клетка пачки
RANGES = {"birch": (40, 140, 700), "linden": (40, 140, 700), "poplar": (45, 150, 750), "lilac": (35, 140, 320), "hedge": (35, 140, 320)}
# (у кустов LOD1 лёгкий и держится до 140 м: дальний вид — две плоскости, с дрона сверху он «крестик»)
CELL = {"birch": 24.0, "linden": 24.0, "poplar": 24.0, "lilac": 16.0, "hedge": 16.0}
# ствол — коробка: диаметр на 1,3 м × k, высота до кроны (не выше 4 м, не ниже 2,5 м)
TRUNK = {"birch_a": (0.34, 1.0), "birch_b": (0.26, 1.7), "birch_c": (0.13, 1.0), "linden_a": (0.5, 0.95), "linden_b": (0.32, 0.95),
         "linden_c": (0.15, 1.0), "poplar_a": (0.72, 0.95), "poplar_b": (0.76, 0.95)}
CROWN_BASE = {"birch_a": 5.2, "birch_b": 4.2, "birch_c": 2.0, "linden_a": 3.3, "linden_b": 2.6, "linden_c": 2.2, "poplar_a": 4.6,
              "poplar_b": 7.0}
HEDGE = {"hedge_a": (4.2, 0.85, 1.05), "hedge_b": (2.1, 0.85, 1.0), "hedge_c": (4.2, 0.85, 1.05)}
# листва: просвет, оттенок (небольшое затемнение фото), разброс тона между деревьями
# (в игре на солнце сирень и липа выходили «кислотными» — тон приглушён, просвет слабее)
LEAVES = {"birch": ((0.28, 0.24, 0.07), (0.86, 0.88, 0.82), 0.16), "linden": ((0.17, 0.2, 0.05), (0.8, 0.84, 0.76), 0.12),
          "poplar": ((0.19, 0.22, 0.07), (0.84, 0.87, 0.8), 0.12), "lilac": ((0.14, 0.18, 0.04), (0.76, 0.8, 0.72), 0.1),
          "hedge": ((0.12, 0.15, 0.04), (0.78, 0.82, 0.74), 0.08)}

TEX_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="{src}"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map={nm}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def webp(name: str) -> str:
    """PNG-сырьё → WebP в игре (≤ 2K). Нормали и атласы с альфой — без потерь, кора — с потерями q92."""
    src = SRC_TEX / f"{name}.png"
    im = Image.open(src)
    if max(im.size) > MAX_TEX:
        k = MAX_TEX / max(im.size)
        im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
    normal = name.endswith("_normal")
    lossless = normal or "atlas" in name or "far" in name or name.endswith("_arm")
    if normal or name.endswith("_arm"):
        im = im.convert("RGB")
    TEX.mkdir(parents=True, exist_ok=True)
    dst = TEX / f"{name}.webp"
    im.save(dst, "WEBP", lossless=lossless, quality=92 if not lossless else 100, method=5)
    res = f"{RES}/textures/{name}.webp"
    # настройки импорта — только если их ещё нет: готовый .import хранит uid и путь импорта (иначе каждый прогон —
    # новый uid и обязательный переимпорт); у нормалей проверяется флаг карты нормалей
    imp = TEX / f"{name}.webp.import"
    if not imp.exists():
        imp.write_text(TEX_IMPORT.format(src=res, nm=1 if normal else 0), encoding="utf-8", newline="\n")
    elif normal and "compress/normal_map=1" not in imp.read_text(encoding="utf-8"):
        t = imp.read_text(encoding="utf-8").replace("compress/normal_map=0", "compress/normal_map=1")
        imp.write_text(t, encoding="utf-8", newline="\n")
    return res


def tres(name: str, shader: str, params: dict, textures: dict) -> None:
    """ShaderMaterial: textures — параметр → путь res://, params — параметр → значение (строкой Godot)."""
    lines = [f'[gd_resource type="ShaderMaterial" load_steps={2 + len(textures)} format=3]', "",
             f'[ext_resource type="Shader" path="{shader}" id="1"]']
    ids = {}
    for i, (k, path) in enumerate(textures.items()):
        ids[k] = str(i + 2)
        lines.append(f'[ext_resource type="Texture2D" path="{path}" id="{i + 2}"]')
    lines += ["", "[resource]", f'resource_name = "{name}"', 'shader = ExtResource("1")']
    for k in textures:
        lines.append(f'shader_parameter/{k} = ExtResource("{ids[k]}")')
    for k, v in params.items():
        lines.append(f"shader_parameter/{k} = {v}")
    MATS.mkdir(parents=True, exist_ok=True)
    (MATS / f"{name}.tres").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def color(c: tuple) -> str:
    return "Color(%g, %g, %g, 1)" % c


def materials(report: dict) -> None:
    foliage = "res://src/world/spruce_foliage.gdshader"
    tex = {}
    for kind in MAT:
        tex[kind] = {k: webp(f"{kind}_{k}") for k in ("atlas_albedo", "atlas_normal", "far_albedo", "far_normal")}
    for b in ("poplar_bark_young", "shrub_bark"):
        for c in ("albedo", "normal", "arm"):
            tex[f"{b}_{c}"] = webp(f"{b}_{c}")
    for kind, m in MAT.items():
        tr, tint, var = LEAVES[kind]
        tres(f"Plant{m}Leaves", foliage, {"translucency": color(tr), "tint": color(tint), "alpha_cut": "0.4", "variation": var},
             {"albedo_tex": tex[kind]["atlas_albedo"], "normal_tex": tex[kind]["atlas_normal"]})
        tres(f"Plant{m}Far", foliage, {"translucency": color(tr), "tint": color(tint), "alpha_cut": "0.45", "variation": var,
                                       "far": "true"},
             {"albedo_tex": tex[kind]["far_albedo"], "normal_tex": tex[kind]["far_normal"]})
    # берёза: береста зоны 1 и чёрный трещиноватый низ (своя высота у каждого экземпляра)
    birch = {"birch_albedo": "res://assets/zone01/textures/birch_bark_albedo.png", "birch_normal": "res://assets/zone01/textures/birch_bark_normal.png",
             "birch_arm": "res://assets/zone01/textures/birch_bark_arm.png", "dark_albedo": "res://assets/textures/bark001/albedo.jpg",
             "dark_normal": "res://assets/textures/bark001/normal.jpg", "noise_tex": "res://assets/terrain/zone01_noise.png"}
    for key, h in (("a", 1.8), ("b", 1.3), ("c", 0.3)):
        tres(f"PlantBirchBark_{key}", "res://src/world/birch_bark.gdshader", {"dark_height": h}, birch)
    tres("PlantBirchBranch", "res://src/world/birch_bark.gdshader", {"branch": "true"}, birch)
    bark = "res://src/world/spruce_bark.gdshader"
    brown = {"old_albedo": "res://assets/textures/bark_brown_02/albedo.jpg", "old_normal": "res://assets/textures/bark_brown_02/normal.jpg",
             "old_arm": "res://assets/textures/bark_brown_02/arm.jpg"}
    shrub = {"young_albedo": tex["shrub_bark_albedo"], "young_normal": tex["shrub_bark_normal"], "young_arm": tex["shrub_bark_arm"]}
    poplar_young = {"young_albedo": tex["poplar_bark_young_albedo"], "young_normal": tex["poplar_bark_young_normal"],
                    "young_arm": tex["poplar_bark_young_arm"]}
    furrowed = {"old_albedo": "res://assets/textures/bark001/albedo.jpg", "old_normal": "res://assets/textures/bark001/normal.jpg"}
    # липа: весь ствол — бороздчатая кора (фото Poly Haven, серее), ветви — гладкая
    tres("PlantLindenBark", bark, {"old_height": 100.0, "old_saturation": 0.6, "old_tint": color((0.92, 0.92, 0.92)), "moss": 0.5},
         {**brown, **shrub})
    tres("PlantLindenBranch", bark, {"old_height": 0.0, "young_tint": color((0.85, 0.8, 0.75)), "moss": 0.0}, {**brown, **shrub})
    # тополь: внизу старая бороздчатая (Bark001), выше — серо-зелёная гладкая
    for key, h in (("a", 7.5), ("b", 6.0)):
        tres(f"PlantPoplarBark_{key}", bark, {"old_height": h, "old_saturation": 0.45, "old_tint": color((0.8, 0.8, 0.78)),
                                              "young_tint": color((1, 1, 1)), "moss": 0.5}, {**furrowed, **poplar_young})
    tres("PlantPoplarBranch", bark, {"old_height": 0.0, "young_tint": color((1, 1, 1)), "moss": 0.0}, {**furrowed, **poplar_young})
    # сирень и кизильник: гладкая серая
    tres("PlantLilacBark", bark, {"old_height": 0.0, "young_tint": color((1, 1, 1)), "moss": 0.0}, {**brown, **shrub})
    tres("PlantHedgeBark", bark, {"old_height": 0.0, "young_tint": color((0.85, 0.72, 0.6)), "moss": 0.0}, {**brown, **shrub})


def glb_imports() -> None:
    """Сетки растений — без автоматических LOD (свои LOD в индексе), с касательными для карт нормалей."""
    for glb in sorted(OUT.glob("*.glb")):
        imp = glb.with_suffix(".glb.import")
        res = f"{RES}/{glb.name}"
        if imp.exists():
            t = imp.read_text(encoding="utf-8")
            t = t.replace("meshes/generate_lods=true", "meshes/generate_lods=false")
            if "meshes/generate_lods" not in t:
                t = t.rstrip() + "\nmeshes/generate_lods=false\n"
        else:
            t = ("[remap]\n\nimporter=\"scene\"\nimporter_version=1\ntype=\"PackedScene\"\n\n[deps]\n\n"
                 f"source_file=\"{res}\"\n\n[params]\n\nmeshes/ensure_tangents=true\nmeshes/generate_lods=false\n"
                 "meshes/create_shadow_meshes=true\n")
        imp.write_text(t, encoding="utf-8", newline="\n")


def game_aabb(lo: list, hi: list) -> dict:
    """Габарит Blender (Z вверх) → игра (Y вверх, лицо −Y Blender → +Z)."""
    glo = (lo[0], lo[2], -hi[1])
    ghi = (hi[0], hi[2], -lo[1])
    return {"center": [round((glo[i] + ghi[i]) * 0.5, 4) for i in range(3)], "size": [round(ghi[i] - glo[i], 4) for i in range(3)]}


def solids(key: str) -> list:
    if key in HEDGE:
        L, W, Hh = HEDGE[key]
        return [[[0.0, round(Hh * 0.48, 3), 0.0], [L, round(Hh * 0.96, 3), round(W * 0.9, 3)]]]
    if key in TRUNK:
        d, k = TRUNK[key]
        h = min(4.0, max(2.5, CROWN_BASE[key]))
        w = round(d * 0.85 * k, 3)
        return [[[0.0, round(h * 0.5, 3), 0.0], [w, h, w]]]
    return []                                          # кусты — без коллизии (как серый набор bush_big)


def index(report: dict) -> int:
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    models = idx["models"]
    n = 0
    for kind, plants in report.items():
        group = f"P_{kind}"
        lo_all = [1e9, 1e9, 1e9]
        hi_all = [-1e9, -1e9, -1e9]
        variants = []
        r0, r1, r2 = RANGES[kind]
        for key, rep in plants.items():
            mid = f"P_{key}"
            lo, hi = rep["lod0"]["lo"], rep["lod0"]["hi"]
            for i in range(3):
                lo_all[i] = min(lo_all[i], lo[i])
                hi_all[i] = max(hi_all[i], hi[i])
            models[mid] = {
                "id": mid, "name": f"{LABEL[kind]}, {NAMES[key]}", "file": f"{RES}/{key}_lod0.glb",
                "triangles": rep["lod0"]["triangles"], "materials": 3, "aabb": game_aabb(lo, hi), "root_offset": [0, 0, 0],
                "lods": [{"file": f"{RES}/{key}_lod0.glb", "end": r0, "triangles": rep["lod0"]["triangles"]},
                         {"file": f"{RES}/{key}_lod1.glb", "end": r1, "triangles": rep["lod1"]["triangles"]},
                         {"file": f"{RES}/{key}_far.glb", "end": r2, "triangles": rep["far"]["triangles"]}],
                "cell": CELL[kind], "materials_dir": f"{RES}/materials", "solids": solids(key)}
            variants.append(mid)
            n += 1
        models[group] = {"id": group, "name": f"{LABEL[kind]} — экземпляры вперемешку", "file": "", "triangles": 0, "materials": 0,
                         "aabb": game_aabb(lo_all, hi_all), "root_offset": [0, 0, 0], "variants": variants}
    # перечитать перед записью: индекс правят и другие (транспорт, Urban 95) — дописать только своё
    fresh = json.loads(INDEX.read_text(encoding="utf-8"))
    for k, v in models.items():
        if k.startswith("P_") and not k.startswith("PV_"):
            fresh["models"][k] = v
    INDEX.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return n


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    materials(report)
    glb_imports()
    n = index(report)
    print("растения → Godot: %d экземпляров, материалы %d, карты %d" % (n, len(list(MATS.glob("*.tres"))), len(list(TEX.glob("*.webp")))))


if __name__ == "__main__":
    main()
