"""Электрика общежития, износ (этап 2): места в развёртке по картам геометрии print_bake.py (положение и нормаль каждого
пикселя в осях корня набора, метры). Рисунок следа кладёт Painter (sp_electrics_wear.py) — эти карты только ограничивают
место (у мух — сами мухи).

  python -X utf8 tools/dorm_modules/electrics_wear_zones.py [набор …]   # → _asset_src/dorm_electrics/wear/<набор>_<зона>.png

Интервью 2026-11-01: как в Таркове; чёрные концы трубок, мухи и пыль в плафонах, захватанные выключатели, пожелтевший
пластик; закрашены при ремонтах — вперемешку (варианты износа «краска» и «побелка» у настенного); ржавчины нет. Зоны:
  up — грани к небу (пыль); tube_ends — тёмная полоса у концов колбы (выгорела); flies / fly_dust — мухи и пыль на дне
  рассеивателя и плафона изнутри (flies_through / dust_through — они же снаружи стекла размытой тенью);
  touch — где трогают (рычажок, клавиша, вокруг гнёзд); soot — копоть у гнёзд розетки;
  haze — налёт на колбе у цоколя; paint — что закрашено при ремонте (провод и коробка — целиком с пропусками,
  выключатели и розетки — по краю и брызгами).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # карты геометрии — EXR; до первого import cv2
import cv2  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as P  # noqa: E402
from wear_zones import noise, smooth  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "dorm_electrics"
ITEMS = ["el_tube", "el_bulb", "el_lsp", "el_lpo", "el_plafond", "el_pendant", "el_switch_round", "el_socket_round",
         "el_switch_white", "el_socket_white", "el_box", "el_wire_flat", "el_wire_twisted"]
WALL = ("el_switch_round", "el_socket_round", "el_switch_white", "el_socket_white", "el_box", "el_wire_flat",
        "el_wire_twisted")


def part(g, prefix):
    ids = [k for k, v in g["names"].items() if v.split("__")[0] == prefix or v == prefix]
    return np.isin(g["part_id"], ids)


def flies(g, mask, centers, angles, soft=False):
    """Мухи: тёмное продолговатое тельце 6–8 мм с крылышками посветлее, лежат как попало. soft — они же сквозь
    молочное стекло снаружи: расплывшейся тенью (расстояние — только в плане, стекло под ними почти горизонтально)."""
    pos = g["pos"]
    out = np.zeros(pos.shape[:2], np.float32)
    lo, hi = (0.2, 1.5) if soft else (0.7, 1.0)
    for c, a in zip(centers, angles):
        ax = np.array([np.cos(a), np.sin(a), 0.0], np.float32)
        ay = np.array([-np.sin(a), np.cos(a), 0.0], np.float32)
        d = pos - np.array(c, np.float32)
        if soft:
            d[..., 2] = 0
        u, v = d @ ax, d @ ay
        body = 1 - smooth(np.sqrt((u / 0.0036) ** 2 + (v / 0.0014) ** 2), lo, hi)
        wing = (1 - smooth(np.sqrt(((u + 0.0012) / 0.0028) ** 2 + (np.abs(v) - 0.0018) ** 2 / 0.0015 ** 2), lo, hi)) * 0.45
        out = np.maximum(out, np.maximum(body, wing))
    return out * mask * (0.55 if soft else 1.0)


def zones(game: str) -> None:
    g = P.load_geo(BASE, game)
    valid = g["part_id"] > 0
    pos, nrm = g["pos"], g["nrm"]
    h, w = valid.shape
    rng = np.random.default_rng(sum(map(ord, game)))  # hash() у строк меняется от запуска к запуску
    maps = {"up": smooth(nrm[..., 2], 0.15, 0.75)}
    if game == "el_tube":
        glass = part(g, "Трубка_люминофор")
        x = pos[..., 0]
        band = np.zeros((h, w), np.float32)
        ends = [(-0.585, 1, -0.045), (0.585, -1, -0.045), (-0.585, 1, 0.045)]
        for xe, s, y in ends:
            d = (x - xe) * s
            on = np.abs(pos[..., 1] - y) < 0.03
            k = rng.uniform(0.75, 1.0)
            ring = np.exp(-((d - 0.025) / 0.011) ** 2) + 0.6 * np.exp(-(d / 0.035) ** 2)
            band = np.maximum(band, ring * k * on * (d > -0.002))
        maps["tube_ends"] = np.clip(band * (0.75 + 0.25 * noise(h, w, 24, 7)), 0, 1) * glass
    if game == "el_lpo":
        dif = part(g, "Рассеиватель_опал")
        inner = dif & (nrm[..., 2] > 0.6)
        low = inner * (1 - smooth(np.abs(pos[..., 1] - pos[..., 1][inner].mean()), 0.02, 0.06))
        cs = [(rng.uniform(-0.55, 0.55), pos[..., 1][inner].mean() + rng.uniform(-0.025, 0.025),
               float(np.median(pos[..., 2][inner]))) for _ in range(14)]
        ang = rng.uniform(0, np.pi, len(cs))
        maps["flies"] = flies(g, inner, cs, ang)
        maps["fly_dust"] = low * (0.5 + 0.5 * noise(h, w, 64, 11))
        # снаружи дна — то же сквозь молочный пластик (у корыта с толщиной; без неё карта пустая)
        outer = dif & (nrm[..., 2] < -0.6)
        maps["flies_through"] = flies(g, outer, cs, ang, soft=True)
        out_low = outer * (1 - smooth(np.abs(pos[..., 1] - pos[..., 1][inner].mean()), 0.02, 0.06))
        maps["dust_through"] = out_low * (0.5 + 0.5 * noise(h, w, 24, 11)) * 0.5
    if game == "el_plafond":
        gl = part(g, "Плафон_стекло")
        r = np.linalg.norm(pos[..., :2], axis=-1)
        inner = gl & (nrm[..., 2] > 0.45)
        cs = []
        for _ in range(9):
            rr, a = rng.uniform(0.0, 0.07), rng.uniform(0, 2 * np.pi)
            cs.append((rr * np.cos(a), rr * np.sin(a), -0.082 + 0.0))
        # мухи ложатся на дно купола: высота точки — по ближайшему пикселю стекла
        zz = []
        for cx, cy, _ in cs:
            dd = (pos[..., 0] - cx) ** 2 + (pos[..., 1] - cy) ** 2 + (~inner) * 9.0
            i = np.unravel_index(np.argmin(dd), dd.shape)
            zz.append(float(pos[i][2]))
        cs = [(c[0], c[1], z) for c, z in zip(cs, zz)]
        ang = rng.uniform(0, np.pi, len(cs))
        maps["flies"] = flies(g, inner, cs, ang)
        maps["fly_dust"] = inner * (1 - smooth(r, 0.05, 0.1)) * (0.5 + 0.5 * noise(h, w, 64, 13))
        # снаружи купола — расплывшиеся тени мух и серое пятно пыли на дне, как их видно снизу сквозь стекло
        outer = gl & (nrm[..., 2] < -0.45)
        maps["flies_through"] = flies(g, outer, cs, ang, soft=True)
        maps["dust_through"] = outer * (1 - smooth(r, 0.04, 0.11)) * (0.5 + 0.5 * noise(h, w, 24, 13)) * 0.5
    if game == "el_bulb":
        gl = part(g, "Лампа_стекло")
        maps["haze"] = gl * smooth(pos[..., 2], -0.76, -0.72) * (0.6 + 0.4 * noise(h, w, 48, 17))
    if game in ("el_switch_round", "el_switch_white"):
        front = nrm[..., 1] < -0.3
        rr = np.sqrt(pos[..., 0] ** 2 + pos[..., 2] ** 2)
        lever = part(g, "Карболит") & np.isin(g["part_id"], [k for k, v in g["names"].items() if "__" in v])
        key = part(g, "Пластик_белый") & np.isin(g["part_id"], [k for k, v in g["names"].items() if "__" in v])
        r0 = 0.018 if game == "el_switch_round" else 0.03
        maps["touch"] = np.clip((front * (1 - smooth(rr, r0 * 0.6, r0))) + lever + key * 0.9, 0, 1) * \
            (0.6 + 0.4 * noise(h, w, 32, 19))
    if game in ("el_socket_round", "el_socket_white"):
        front = nrm[..., 1] < -0.3
        soot = np.zeros((h, w), np.float32)
        for xh in (-0.0095, 0.0095):
            d = np.sqrt((pos[..., 0] - xh) ** 2 + pos[..., 2] ** 2)
            soot = np.maximum(soot, 1 - smooth(d, 0.0025, 0.006 + 0.002 * rng.random()))
        maps["soot"] = soot * front * (0.6 + 0.4 * noise(h, w, 16, 23))
        rr = np.sqrt(pos[..., 0] ** 2 + pos[..., 2] ** 2)
        maps["touch"] = front * (1 - smooth(rr, 0.012, 0.024)) * (0.6 + 0.4 * noise(h, w, 32, 29))
    if game in WALL:
        nz = noise(h, w, 48, 31)
        if game in ("el_wire_flat", "el_wire_twisted", "el_box"):
            # закрашено целиком (кисть шла по стене): слой сплошной, мелкие пропуски с чёткой кромкой и места тоньше
            # (самопроверка: плавная маска давала полупрозрачный «камуфляж»)
            skips = smooth(noise(h, w, 96, 41), 0.16, 0.22)
            maps["paint"] = skips * (0.85 + 0.15 * nz)
        else:
            # выключатели и розетки: по краю (кисть обводила) и брызги на лице
            rr = np.sqrt(pos[..., 0] ** 2 + pos[..., 2] ** 2)
            # край — по контуру изделия: у круглых по радиусу, у квадратной рамки 80 мм — по квадрату (самопроверка:
            # по радиусу краска заходила на рамку кругом)
            r_edge = 0.024 if "round" in game else 0.035
            outline = rr if "round" in game else np.maximum(np.abs(pos[..., 0]), np.abs(pos[..., 2]))
            rim = smooth(outline, r_edge, r_edge + 0.006)
            # брызги — редкие капли, гуще к краю, куда шла кисть
            specks = (noise(h, w, 10, 37) > 0.965).astype(np.float32) * smooth(rr, r_edge * 0.45, r_edge)
            # кромка кисти — чёткая неровная граница, не размытая полоса
            edge = smooth(rim * (0.5 + 0.5 * nz), 0.4, 0.48)
            maps["paint"] = np.clip(np.maximum(edge, specks * 0.9), 0, 1)
    out = BASE / "wear"
    out.mkdir(parents=True, exist_ok=True)
    for k, v in maps.items():
        v = np.where(valid, v, 0)
        cv2.imwrite(str(out / f"{game}_{k}.png"), (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8))
    print("ZONES", game, sorted(maps), flush=True)


if __name__ == "__main__":
    only = sys.argv[1:]
    for game in ITEMS:
        if not only or game in only:
            zones(game)
