"""Ковёр общежития: карты без Painter — ворс своим генератором (furniture_prints.py) и износ по зонам
(furniture_wear_zones.py) теми же числами, что у мебели в Painter (sp_furniture_wear.py: выгорело, пыль сверху,
засалено, ржавчина гвоздей).

  python -X utf8 tools/dorm_modules/carpet_maps.py   # → _asset_src/dorm_furniture/maps/furn_carpet (этап 1)
                                                     #   и maps_worn/furn_carpet (износ); карты 4K, как развёртка

Вид ковра целиком из генератора (заливку CP-WOL-RED печать ворса закрывает всю), а Painter на проекте ковра 4K падал
при создании (2026-11-01, дважды, журнал обрывается без ошибки) — карты собираются здесь. Гвозди — фосфат PH-GRY-MAT
(слот nails в finish-spec.json), с износом — ржавчина пятнами.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # карты геометрии — EXR; до первого import cv2
import cv2  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as A  # noqa: E402
from wear_zones import noise  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "dorm_furniture"
GAME = "furn_carpet"
CATALOG = Path(__file__).resolve().parents[1] / "asset_kit" / "finish" / "finishes.json"
FADE = 0.14  # как furn_carpet в sp_furniture_wear.PROFILES


def finish(code: str) -> dict:
    return next(f for f in json.loads(CATALOG.read_text(encoding="utf-8"))["finishes"] if f["code"] == code)


def read(name: str, flags=cv2.IMREAD_UNCHANGED) -> np.ndarray:
    return cv2.imread(str(BASE / "prints" / "uv" / f"{GAME}_{name}.png"), flags)


def zone(name: str) -> np.ndarray:
    im = cv2.imread(str(BASE / "wear" / f"{GAME}_{name}.png"), cv2.IMREAD_GRAYSCALE)
    return im.astype(np.float32) / 255.0


def lum(c: np.ndarray) -> np.ndarray:
    return (c @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]


def save(folder: str, col: np.ndarray, nrm: np.ndarray, ao: np.ndarray, rough: np.ndarray, metal: np.ndarray) -> None:
    out = BASE / folder / GAME
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / f"{GAME}_baseColor.png"), cv2.cvtColor((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8),
                                                                 cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out / f"{GAME}_normal.png"), nrm)
    orm = np.stack([metal, rough, ao], -1)  # BGR: синий — металл, зелёный — шероховатость, красный — затенение
    cv2.imwrite(str(out / f"{GAME}_occlusionRoughnessMetallic.png"), (np.clip(orm, 0, 1) * 255 + 0.5).astype(np.uint8))
    print("MAPS", out, flush=True)


def main() -> None:
    g = A.load_geo(BASE, GAME)
    wool = A.part_mask(g, "Ковёр_шерсть")
    nails = A.part_mask(g, "Гвоздь_сталь")
    col = cv2.cvtColor(read("print_color", cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rough = read("print_rough", cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    hgt = read("print_height").astype(np.float32) / 65535.0
    nrm16 = read("print_normal")
    nrm = (nrm16.astype(np.float32) / 257.0 + 0.5).astype(np.uint8)
    # затенение в глубине ворса — по высоте пучков
    lo, hi = np.percentile(hgt[wool], [3, 97])
    ao = np.where(wool, 0.72 + 0.28 * np.clip((hgt - lo) / (hi - lo), 0, 1), 1.0).astype(np.float32)
    metal = np.zeros(wool.shape, np.float32)
    ph = finish("PH-GRY-MAT")["base"]
    col[nails] = ph["color"]
    rough[nails] = ph["rough"]
    metal[nails] = ph["metal"]
    nrm[nails] = (255, 128, 128)  # BGR плоской нормали
    save("maps", col, nrm, ao, rough, metal)

    # износ: выгорело от окна (насыщенность серым и чуть светлее), пыль на верхних гранях волн, засалено у изголовья
    h, w = wool.shape
    fade = zone("fade")[..., None] * wool[..., None]
    a1 = min(FADE * 1.2, 0.3) * fade
    col = col * (1 - a1) + lum(col) * a1
    a2 = FADE * 0.5 * fade
    col = col * (1 - a2) + (1 - (1 - col) * (1 - np.array([0.22, 0.21, 0.19], np.float32))) * a2
    rough = rough + 0.02 * fade[..., 0]
    dust = zone("up") * (0.4 + 0.6 * noise(h, w, 48, 61)) * 0.2 * wool
    col = col * (1 - dust[..., None]) + np.array([0.60, 0.57, 0.51], np.float32) * dust[..., None]
    rough = rough * (1 - dust) + 0.9 * dust
    # засалено ровно, с лёгкой неровностью: пятнистая маска «мазками» на ворсе читалась облаком грязи
    smear = 0.6 + 0.4 * noise(h, w, 160, 71)
    gr = zone("greasy") * smear * 0.45 * wool
    col = col * (1 - gr[..., None] * (1 - np.array([0.70, 0.66, 0.60], np.float32)))
    rough = rough - 0.15 * 0.7 * gr
    # гвозди: ржавчина пятнами, где ржавь — не металл
    rust = nails * np.clip((noise(h, w, 6, 83) - 0.35) * 2.5, 0, 1)
    col = col * (1 - rust[..., None] * 0.85) + np.array([0.32, 0.17, 0.08], np.float32) * rust[..., None] * 0.85
    rough = rough * (1 - rust) + 0.85 * rust
    metal = metal * (1 - rust)
    save("maps_worn", col, nrm, ao, np.clip(rough, 0, 1), metal)


if __name__ == "__main__":
    main()
