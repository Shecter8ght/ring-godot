"""Печать и маркировка на карты этапа 1 (заводская отделка): макеты print_designs.py ложатся на развёртку вещей по
картам геометрии print_bake.py — банки обёрткой по цилиндру, этикетки по своему листу (у оборота листа печати нет),
пачка по граням, надписи на оставленном свете — плоской наклейкой на свою деталь, этикетка тушёнки на банке свечи —
выцветшая и рваная.

  python -X utf8 tools/dorm_modules/print_apply.py [вещь …]

Карты Painter не теряются: первая же запись сохраняет их рядом как *_plain.png, печать всегда кладётся на них заново.
Там, где печать краской по металлу (банки, фонарь, мигалка), металличность снимается, блеск — краски.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRINTS = ROOT / "_asset_src" / "dorm_clutter" / "prints"
SETS = {"clutter": ROOT / "_asset_src" / "dorm_clutter", "found": ROOT / "_asset_src" / "dorm_found_lights"}
PX_MM = 10.0  # макеты — 10 пикс/мм


def load_geo(base: Path, game: str):
    g = {}
    for k in ("pos", "nrm", "part"):
        a = cv2.imread(str(base / "prints" / "geo" / f"{game}_{k}.exr"), cv2.IMREAD_UNCHANGED)
        g[k] = a[..., ::-1].astype(np.float32)  # BGR → RGB = XYZ
    parts = json.loads((base / "prints" / "geo" / f"{game}_parts.json").read_text(encoding="utf-8"))
    g["part_id"] = np.rint(g["part"][..., 0]).astype(np.int32)
    g["names"] = {int(k): v for k, v in parts.items()}
    return g


def part_mask(g, name: str) -> np.ndarray:
    ids = [k for k, v in g["names"].items() if v == name]
    return np.isin(g["part_id"], ids)


def design(name: str) -> np.ndarray:
    im = cv2.imread(str(PRINTS / f"{name}.png"), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255.0


def sample(img: np.ndarray, u: np.ndarray, v: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Макет по долям (u вправо, v вниз), где ok; вне — прозрачно."""
    h, w = img.shape[:2]
    mx = np.where(ok, u * (w - 1), -10).astype(np.float32)
    my = np.where(ok, v * (h - 1), -10).astype(np.float32)
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def wrap(g, mask, img, z0, z1, phase=0.0, center=(0.0, 0.0), skip_caps=True) -> np.ndarray:
    """Обёртка по цилиндру вокруг оси Z через center: u — угол, v — сверху вниз от z1 к z0."""
    x, y, z = g["pos"][..., 0] - center[0], g["pos"][..., 1] - center[1], g["pos"][..., 2]
    u = (np.arctan2(y, x) / (2 * math.pi) + phase) % 1.0
    v = (z1 - z) / (z1 - z0)
    ok = mask & (v >= 0) & (v <= 1)
    if skip_caps:
        ok &= np.abs(g["nrm"][..., 2]) < 0.75
    return sample(img, u, v, ok)


def label(g, mask, img, z0, z1, a0, a1) -> np.ndarray:
    """Этикетка по своему листу: угол a0…a1 (град), высота z0…z1; оборот листа (нормаль к оси) — без печати."""
    x, y, z = g["pos"][..., 0], g["pos"][..., 1], g["pos"][..., 2]
    a = np.degrees(np.arctan2(y, x))
    a = np.where(a < a0, a + 360, a)
    u = (a - a0) / (a1 - a0)
    v = (z1 - z) / (z1 - z0)
    r = np.sqrt(x * x + y * y) + 1e-9
    outward = (g["nrm"][..., 0] * x + g["nrm"][..., 1] * y) / r > 0.1
    ok = mask & outward & (u >= 0) & (u <= 1) & (v >= -0.05) & (v <= 1.05)
    return sample(img, u, np.clip(v, 0, 1), ok)


def decal(g, mask, img, c, n, uaxis, w_mm, h_mm, depth=0.03, cos_min=0.35) -> np.ndarray:
    """Плоская наклейка: центр c, нормаль n, вправо uaxis (мм-размер макета)."""
    c, n, ua = np.array(c), np.array(n, float), np.array(uaxis, float)
    n /= np.linalg.norm(n)
    ua /= np.linalg.norm(ua)
    va = np.cross(ua, n)  # вниз по макету
    d = g["pos"] - c
    u = (d @ ua) / (w_mm / 1000) + 0.5
    v = (d @ va) / (h_mm / 1000) + 0.5
    ok = mask & (np.abs(d @ n) < depth) & ((g["nrm"] @ n) > cos_min) & (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    return sample(img, u, v, ok)


def bbox(g, mask):
    p = g["pos"][mask]
    return p.min(axis=0), p.max(axis=0)


def compose(base: Path, game: str, layers: list) -> None:
    """layers: (печать RGBA, металличность под печатью или None — не трогать, блеск печати или None, непрозрачность)."""
    mdir = base / "maps" / game
    for k in ("baseColor", "occlusionRoughnessMetallic"):
        src, plain = mdir / f"{game}_{k}.png", mdir / f"{game}_{k}_plain.png"
        if not plain.exists():
            shutil.copyfile(src, plain)
    col = cv2.cvtColor(cv2.imread(str(mdir / f"{game}_baseColor_plain.png"), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    orm = cv2.cvtColor(cv2.imread(str(mdir / f"{game}_occlusionRoughnessMetallic_plain.png"), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    for prn, metal, rough, opa in layers:
        a = prn[..., 3:4] * opa
        col = col * (1 - a) + prn[..., :3] * a
        if rough is not None:
            orm[..., 1] = orm[..., 1] * (1 - a[..., 0]) + rough * a[..., 0]
        if metal is not None:
            orm[..., 2] = orm[..., 2] * (1 - a[..., 0]) + metal * a[..., 0]
    cv2.imwrite(str(mdir / f"{game}_baseColor.png"), cv2.cvtColor((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(mdir / f"{game}_occlusionRoughnessMetallic.png"), cv2.cvtColor((np.clip(orm, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print("PRINTED", game, len(layers), "слоёв", flush=True)


def worn(prn: np.ndarray, seed: int, fade: float, torn: float) -> np.ndarray:
    """Выцветание к бумаге и рваные пятна (крупный шум с порогом)."""
    rng = np.random.default_rng(seed)
    h, w = prn.shape[:2]
    noise = cv2.resize(rng.random((h // 128 + 2, w // 128 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    noise += 0.25 * cv2.resize(rng.random((h // 32 + 2, w // 32 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    out = prn.copy()
    paper = np.array([0.80, 0.76, 0.62], np.float32)
    out[..., :3] = out[..., :3] * (1 - fade) + paper * fade
    out[..., 3] *= (noise > torn * 1.25).astype(np.float32)
    return out


# ---------------------------------------------------------------- вещи

def clutter(game: str) -> None:
    base = SETS["clutter"]
    g = load_geo(base, game)
    L = []
    if game in ("clutter_can", "clutter_can_dented", "clutter_can_crushed"):
        m = part_mask(g, "Банка_алюминий")
        z0, z1, des = {"clutter_can": (0.012, 0.150, "can_posad"), "clutter_can_dented": (0.012, 0.126, "can_posad"),
                       "clutter_can_crushed": (0.006, 0.050, "can_val")}[game]
        L.append((wrap(g, m, design(des), z0, z1, phase=0.37), 0.0, 0.32, 1.0))
    elif game in ("clutter_bottle_vodka", "clutter_bottle_vodka_worn"):
        m = part_mask(g, "Этикетка_бумага")
        L.append((label(g, m, design("vodka_front"), 0.050, 0.135, -62, 62), None, None, 1.0))
        L.append((label(g, m, design("vodka_back"), 0.060, 0.110, 145, 215), None, None, 1.0))
        L.append((label(g, m, design("vodka_neck"), 0.236, 0.249, -195, 155), None, 0.35, 1.0))
    elif game == "clutter_bottle_beer":
        m = part_mask(g, "Этикетка_бумага")
        L.append((label(g, m, design("beer_front"), 0.040, 0.112, -75, 75), None, None, 1.0))
        L.append((label(g, m, design("beer_shoulder"), 0.170, 0.188, -50, 50), None, None, 1.0))
    elif game == "clutter_bottle_broken":
        # горлышко лежит: вернуть оси целой бутылки (обратно повороту build_clutter.broken_bottle)
        p = g["pos"].copy()
        p[..., 2] -= 0.0335
        y, z = p[..., 1].copy(), p[..., 2].copy()
        p[..., 1], p[..., 2] = z, -y  # поворот на −90° вокруг X
        p[..., 2] += 0.13
        nr = g["nrm"].copy()
        ny, nz = nr[..., 1].copy(), nr[..., 2].copy()
        nr[..., 1], nr[..., 2] = nz, -ny
        g2 = dict(g, pos=p, nrm=nr)
        m = part_mask(g, "Этикетка_бумага")
        L.append((label(g2, m, design("beer_shoulder"), 0.170, 0.188, -50, 50), None, None, 1.0))
    elif game == "clutter_butts":
        m = part_mask(g, "Пачка_бумага")
        ang = math.radians(-20)
        ca, sa = math.cos(ang), math.sin(ang)
        x, y = g["pos"][..., 0] - 0.21, g["pos"][..., 1] - 0.05
        lx, ly = x * ca - y * sa, x * sa + y * ca
        nx, ny = g["nrm"][..., 0] * ca - g["nrm"][..., 1] * sa, g["nrm"][..., 0] * sa + g["nrm"][..., 1] * ca
        nz = g["nrm"][..., 2]
        u, v = (lx + 0.028) / 0.056, (0.044 - ly) / 0.088
        top, bot = m & (nz > 0.5), m & (nz < -0.5)
        side = m & ~top & ~bot
        L.append((sample(design("pack_front"), u, v, top), None, 0.3, 1.0))
        L.append((sample(design("pack_back"), 1 - u, v, bot), None, 0.3, 1.0))
        edge = np.where(np.abs(nx) > np.abs(ny), np.where(nx > 0, 0.999, 0.0), 0.5)  # бока — цвет края лица
        L.append((sample(design("pack_front"), edge, v, side), None, 0.3, 1.0))
    if L:
        compose(base, game, L)


def found(game: str) -> None:
    base = SETS["found"]
    g = load_geo(base, game)
    L = []
    white, black = None, None
    if game == "found_flashlight":
        m = part_mask(g, "Фонарь_корпус")
        lo, hi = bbox(g, m)
        c = ((lo[0] + hi[0]) / 2, lo[1] + (hi[1] - lo[1]) * 0.42, hi[2])
        L.append((decal(g, m, design("luch2"), c, (0, 0, 1), (0, 1, 0), 44, 9), 0.0, 0.45, 0.95))
    elif game == "found_lantern":
        m = part_mask(g, "Лампа_корпус")
        front = m & (g["nrm"][..., 1] < -0.6)
        lo, hi = bbox(g, front)
        c = ((lo[0] + hi[0]) / 2, lo[1], lo[2] + 0.022)
        L.append((decal(g, m, design("turist"), c, (0, -1, 0), (1, 0, 0), 56, 14, depth=0.04), None, 0.5, 0.95))
    elif game == "found_chemlight":
        m = part_mask(g, "Химсвет_трубка")
        lo, hi = bbox(g, m)
        c = ((lo[0] + hi[0]) / 2 - 0.005, (lo[1] + hi[1]) / 2, hi[2])
        L.append((decal(g, m, design("hs15"), c, (0, 0, 1), (1, 0, 0), 96, 10), None, 0.3, 0.9))
    elif game == "found_beacon":
        m = part_mask(g, "Мигалка_корпус")
        front = m & (g["nrm"][..., 1] < -0.7)
        lo, hi = bbox(g, front)
        c = ((lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2 - 0.008)  # ниже середины — сверху лапы кронштейна линзы
        L.append((decal(g, m, design("fs1"), c, (0, -1, 0), (1, 0, 0), 64, 40, depth=0.03), None, 0.4, 1.0))
    elif game == "found_candles":
        m = part_mask(g, "Банка_жесть")
        tall = m & (g["pos"][..., 2] > 0.05) & (np.abs(g["nrm"][..., 2]) < 0.4)
        p = g["pos"][tall]
        cx, cy = float(p[:, 0].mean()), float(p[:, 1].mean())
        near = m & ((g["pos"][..., 0] - cx) ** 2 + (g["pos"][..., 1] - cy) ** 2 < 0.045 ** 2)
        prn = worn(wrap(g, near, design("stew"), 0.012, 0.072, phase=0.1, center=(cx, cy)), 7, 0.45, 0.45)
        L.append((prn, 0.0, 0.8, 0.9))
    if L:
        compose(base, game, L)


def main() -> None:
    only = sys.argv[1:]
    for game in ("clutter_can", "clutter_can_dented", "clutter_can_crushed", "clutter_bottle_vodka",
                 "clutter_bottle_vodka_worn", "clutter_bottle_beer", "clutter_bottle_broken", "clutter_butts"):
        if not only or game in only:
            clutter(game)
    for game in ("found_flashlight", "found_lantern", "found_chemlight", "found_beacon", "found_candles"):
        if not only or game in only:
            found(game)


if __name__ == "__main__":
    main()
