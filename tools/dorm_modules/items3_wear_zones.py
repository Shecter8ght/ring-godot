"""Вещи общежития, партия 3, износ (этап 2): места в развёртке по картам геометрии print_bake.py (положение, нормаль,
деталь, у листов — развёртка печати «prm»). Рисунок следа кладёт Painter (sp_items3_wear.py) — эти карты ограничивают
место; пометки ручкой и карандашом — сами штрихи (рисуются в координатах листа или обложки).

  python -X utf8 tools/dorm_modules/items3_wear_zones.py [набор …]   # → _asset_src/dorm_items3/wear/<набор>[__<картинка>]_<зона>.png

Интервью 2026-11-02: степень — «слабее» (брошено недавно: пыль, отпечатки, мелкие следы), но всё выбранное есть.
Ящики и вещи жильцов — сбитые углы и кромки, ржавчина на металле, пыль и грязь, коробка отсырела; бумага на стенах —
выцвела и пожелтела, пятна сырости, пыль и мухи, карандаш и ручка; техника и учебное — пыль и отпечатки, затёртое от
рук, учебники потрёпаны, пятна и пометки.
Зоны: up — грани к небу (пыль); edge — выпуклые рёбра (сколы, стёртые кромки); corner — у углов коробок (бьют сильнее);
floor — низ у стоящего на полу; kick — низ фасада (сапоги); rust — фурнитура; touch — где берут; wet — сырость низа
коробки; yellow / damp / rust_pins / top_dust / corners / pen / pencil — бумага; keys — затёртые клавиши; rings —
кольца от кружек; ink — надписи на обложках тетрадей; fray — потёртые углы и корешок книг.
Детали, сдвинутые на время текстур (items3_uv.OFFSETS), возвращаются на место до расчёта.
"""
from __future__ import annotations

import ast
import json
import math
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import furniture2_wear_zones as W  # noqa: E402
import items3_prints as IP  # noqa: E402
from furniture_wear_zones import rings  # noqa: E402
from wear_zones import blobs, noise, smooth  # noqa: E402

BASE = HERE.parents[1] / "_asset_src" / "dorm_items3"
ON_FLOOR = ("it_ammo", "it_zip", "it_trunk", "it_toolbox", "it_suitcase", "it_duffel", "it_carton", "it_pc")
PAPER_SETS = ("it_poster", "it_poster_torn", "it_poster_curl", "it_poster_s", "it_poster_s_curl", "it_clip",
              "it_calendar", "it_chart", "it_drawing", "it_drawing_roll")
# размер листа, мм (ширина, высота) — пометки рисуются в его координатах
SHEET_MM = {"it_poster": (600, 900), "it_poster_torn": (600, 900), "it_poster_curl": (600, 900), "it_poster_s": (420, 594),
            "it_poster_s_curl": (420, 594), "it_clip": (210, 297), "it_calendar": (296, 430), "it_chart": (700, 1000),
            "it_drawing": (841, 594), "it_drawing_roll": (841, 594)}
# советские и старые листы желтеют сильнее, афиши и вырезки моложе
YELLOW = {"it_poster": 1.0, "it_poster_torn": 1.0, "it_poster_curl": 1.0, "it_chart": 0.9, "it_drawing": 0.7,
          "it_drawing_roll": 0.7, "it_calendar": 0.6, "it_clip": 0.6, "it_poster_s": 0.45, "it_poster_s_curl": 0.45}
INK, PENCIL = 255, 255


def offsets() -> dict:
    """items3_uv.OFFSETS без импорта (тот модуль требует bpy)."""
    tree = ast.parse((HERE / "items3_uv.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "OFFSETS")
    src = ast.get_source_segment((HERE / "items3_uv.py").read_text(encoding="utf-8"), node.value)
    return eval(src, {})  # словарь со списковыми включениями — literal_eval их не берёт


def load(game: str) -> dict:
    g = IP.geo(game)
    for name, off in offsets().get(game, {}).items():
        m = W.parts(g, name)
        g["pos"][m] -= np.array(off, np.float32)
    return g


def save(game: str, maps: dict, valid: np.ndarray) -> None:
    out = BASE / "wear"
    out.mkdir(parents=True, exist_ok=True)
    for k, v in maps.items():
        v = np.where(valid, v, 0)
        cv2.imwrite(str(out / f"{game}_{k}.png"), (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8))


# ------------------------------------------------------------------------------------------------ штрихи от руки
def hand_line(d: ImageDraw.ImageDraw, x: float, y: float, length: float, h: float, px: float, rng, width: float) -> None:
    """Строка «от руки»: слова петлями разной высоты с наклоном, пробелы между словами; пишущий нажимает неровно."""
    pts = []
    t = 0.0
    while t < length:
        word = rng.uniform(6, 22) * h / 4
        n = max(3, int(word / (h * 0.45)))
        for k in range(n * 6):
            s = k / (n * 6)
            xx = x + t + s * word + 0.25 * h * math.sin(s * n * 2 * math.pi + 1.3)
            yy = y - h * 0.5 * (1 + math.sin(s * n * 2 * math.pi)) * rng.uniform(0.75, 1.0) * (1.4 if rng.random() < 0.06 else 1)
            pts.append((xx * px, yy * px))
        d.line(pts, fill=INK, width=max(1, int(width * px)), joint="curve")
        pts = []
        t += word + rng.uniform(2.5, 5) * h / 4


def circle_mark(d, cx, cy, r, px, rng, width) -> None:
    """Обведено от руки: неровный эллипс, конец заходит за начало."""
    a0 = rng.uniform(0, 2 * math.pi)
    pts = []
    for k in range(48):
        a = a0 + 2 * math.pi * 1.12 * k / 47
        rr = r * (1 + 0.08 * math.sin(a * 3 + a0))
        pts.append(((cx + rr * 1.15 * math.cos(a)) * px, (cy + rr * 0.9 * math.sin(a)) * px))
    d.line(pts, fill=INK, width=max(1, int(width * px)), joint="curve")


def page_img(w_mm: float, h_mm: float, px: float) -> tuple:
    im = Image.new("L", (int(w_mm * px), int(h_mm * px)), 0)
    return im, ImageDraw.Draw(im)


def by_page(g: dict, mask: np.ndarray, im: Image.Image) -> np.ndarray:
    """Картинка штрихов (L) по развёртке листа: u — слева, v — снизу; только лицо листа."""
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
    u, v = g["prm"][..., 0], g["prm"][..., 1]
    ok = mask & (u > -0.5)
    h, w = a.shape
    mx = np.where(ok, np.clip(u, 0, 1) * (w - 1), -10).astype(np.float32)
    my = np.where(ok, np.clip(1 - v, 0, 1) * (h - 1), -10).astype(np.float32)
    return cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def paper(game: str) -> None:
    g = load(game)
    valid = g["part_id"] > 0
    paper_m = W.parts(g, "Бумага")
    u, v = g["prm"][..., 0], g["prm"][..., 1]
    front = paper_m & (u > -0.5)
    Wm, Hm = SHEET_MM[game]
    xs, ys = u * Wm, (1 - v) * Hm             # мм от левого верхнего угла листа
    # расстояние до края листа (мм), на изнанке — по положению в пространстве не считаем: ей хватает общего тона
    de = np.minimum.reduce([xs, Wm - xs, ys, Hm - ys])
    shp = valid.shape
    nz = W.fbm(g, cells=(0.25, 0.1, 0.04), seed=3)
    maps = {}
    k = YELLOW[game]
    # пожелтело: весь лист слабо, к краям и сверху (свет из окна, табачный дым) — сильнее, пятнами
    maps["yellow"] = paper_m * np.clip(k * (0.45 + 0.35 * nz + 0.4 * (1 - smooth(np.where(front, de, 99), 0, 60))), 0, 1)
    # сырость: два-три развода снизу и у одного края, ободок высохшей воды темнее (blobs с ring — в мм листа)
    rng = np.random.default_rng(hash(game) % 1000)
    damp = np.zeros(shp, np.float32)
    for _ in range(2 + int(rng.integers(0, 2))):
        cx = rng.uniform(0.1, 0.9) * Wm
        cy = rng.uniform(0.62, 0.98) * Hm
        r = rng.uniform(0.08, 0.2) * min(Wm, Hm)
        d = np.hypot(xs - cx, (ys - cy) * 0.8) / r * (0.8 + 0.4 * noise(*shp, 60, int(rng.integers(0, 99))))
        damp = np.maximum(damp, 0.35 * (1 - smooth(d, 0.55, 1.0)) + 0.85 * np.exp(-((d - 0.93) / 0.05) ** 2))
    maps["damp"] = front * damp
    # ржавые следы у кнопок: кнопки в 15 мм от углов (и посередине верха у советских)
    pins = [(15, 15), (Wm - 15, 15), (15, Hm - 15), (Wm - 15, Hm - 15)] + ([(Wm / 2, 15)] if Wm > 450 else [])
    rp = np.zeros(shp, np.float32)
    for px_, py_ in pins:
        d = np.hypot(xs - px_, ys - py_)
        rp = np.maximum(rp, np.exp(-((d - 6.5) / 2.2) ** 2) * (0.5 + 0.5 * noise(*shp, 20, 7)))
    maps["rust_pins"] = front * rp
    # пыль на верхней кромке и мухи по всему листу (карта — лист, рисунок точек — маской в Painter)
    maps["top_dust"] = paper_m * np.maximum(1 - smooth(np.where(front, ys, 99), 3, 70), W.edge_zone(g, 0.0005, 0.004) * 0.5)
    maps["flies"] = front * 1.0
    # захватанные нижние углы: за них приподнимали лист
    cr = np.minimum(np.hypot(xs, ys - Hm), np.hypot(xs - Wm, ys - Hm))
    maps["corners"] = front * (1 - smooth(cr, 15, 70)) * (0.6 + 0.4 * nz)

    # пометки: ручка и карандаш — в координатах листа
    pxm = 4.0
    rng = np.random.default_rng(17 + len(game))
    pen, dp = page_img(Wm, Hm, pxm)
    pencil, dc = page_img(Wm, Hm, pxm)
    if game == "it_calendar":
        # даты обведены ручкой, прошедшие дни зачёркнуты карандашом (сетка — items3_prints.calendar_page)
        x0, cw, y0, rh = 26, 40.7, 248, 27
        for day in (7, 15, 22):
            r_, c_ = divmod(3 + day - 1, 7)
            circle_mark(dp, x0 + cw * c_, y0 + 22 + rh * r_, 9, pxm, rng, 0.9)
        for day in range(1, 13):
            r_, c_ = divmod(3 + day - 1, 7)
            cx, cy = x0 + cw * c_, y0 + 22 + rh * r_
            dc.line([((cx - 7) * pxm, (cy - 6) * pxm), ((cx + 7) * pxm, (cy + 6) * pxm)], fill=PENCIL, width=4)
            dc.line([((cx + 7) * pxm, (cy - 6) * pxm), ((cx - 7) * pxm, (cy + 6) * pxm)], fill=PENCIL, width=4)
        hand_line(dp, 14, 397, 90, 5, pxm, rng, 0.8)
    elif game == "it_clip":
        hand_line(dc, 120, 284, 70, 4, pxm, rng, 0.7)
    elif game in ("it_chart", "it_drawing", "it_drawing_roll"):
        hand_line(dc, Wm * 0.62, Hm * 0.93, Wm * 0.25, 6, pxm, rng, 0.9)
    else:
        # плакаты: дата и подпись ручкой в нижнем поле, карандашный росчерк сбоку
        hand_line(dp, Wm * 0.06, Hm * 0.965, Wm * 0.3, 7, pxm, rng, 1.0)
        hand_line(dc, Wm * 0.7, Hm * 0.08, Wm * 0.2, 6, pxm, rng, 0.9)
    maps["pen"] = by_page(g, paper_m, pen)
    maps["pencil"] = by_page(g, paper_m, pencil)
    # дерево реек, багет и стекло картин — пыль сверху и мухи
    maps["up"] = smooth(g["nrm"][..., 2], 0.15, 0.75)
    save(game, maps, valid)
    print("ZONES", game, sorted(maps), flush=True)


# ------------------------------------------------------------------------------------------------ клавиши
WORN = {"W", "A", "S", "D", "", "Shift", "Ctrl", "Enter", "←", "Space", "Alt", "Esc", "Tab"}


def keys_zone(g: dict, keys: list, base: str) -> np.ndarray:
    """Затёртые клавиши: верх колпачков WASD, пробела, Shift, Ctrl, Enter, Backspace — сильнее в середине."""
    m = W.parts(g, base) & (g["nrm"][..., 2] > 0.85)
    idx = np.nonzero(m)
    p = g["pos"][idx]
    cx = np.array([k[0] for k in keys])
    cy = np.array([k[1] for k in keys])
    best = np.argmin((p[:, 0:1] - cx[None]) ** 2 + (p[:, 1:2] - cy[None]) ** 2, axis=1)
    lab = [k[4] for k in keys]
    worn = np.array([1.0 if (isinstance(l_, tuple) and l_[0] in WORN) or l_ in WORN else 0.0 for l_ in lab], np.float32)
    kw = np.array([k[2] for k in keys])[best]
    kh = np.array([k[3] for k in keys])[best]
    du = (p[:, 0] - cx[best]) / kw
    dv = (p[:, 1] - cy[best]) / kh
    centre = 1 - smooth(np.hypot(du, dv * 1.2), 0.15, 0.55)
    out = np.zeros(m.shape, np.float32)
    out[idx] = worn[best] * (0.35 + 0.65 * centre)
    # остальные клавиши — слабее (тоже трогали)
    out[idx] = np.maximum(out[idx], 0.25 * centre)
    return out


# ------------------------------------------------------------------------------------------------ обложки
# поля «по ___ / ученика ___» на картинках тетрадей: (u0, u1, v строк сверху), доли обложки
LABELS = {"tetrad_1": (0.38, 0.72, (0.47, 0.535)), "tetrad_2": (0.44, 0.78, (0.12, 0.17)),
          "tetrad_obshchaya": (0.3, 0.72, (0.62,))}


def cover_coords(g: dict, f: dict, mask: np.ndarray):
    c = np.array(f["center"])
    Lv, Wv, Tv = (np.array(f[k]) for k in ("length", "width", "thick"))
    Ls, Ws, Ts = f["size"]
    d = g["pos"] - c
    dl, dw, dt = d @ Lv, d @ Wv, d @ Tv
    inside = mask & (np.abs(dl) < Ls / 2 + 0.002) & (np.abs(dw) < Ws / 2 + 0.002) & (np.abs(dt) < Ts / 2 + 0.002)
    face = inside & ((g["nrm"] @ Tv) > 0.8) & (dt > (Ts / 2 - 0.0015 if Ts > 0.008 else 0.0))
    return inside, face, (dw + Ws / 2) / Ws, (Ls / 2 - dl) / Ls, Ls, Ws


def covers(game: str, items: list, base: str) -> None:
    g = load(game)
    valid = g["part_id"] > 0
    fr = json.loads((BASE / "prints" / "geo" / f"{game}_frames.json").read_text(encoding="utf-8"))
    mask = W.parts(g, base)
    shp = valid.shape
    ink = np.zeros(shp, np.float32)
    fray = np.zeros(shp, np.float32)
    rng = np.random.default_rng(23)
    for f, item in zip(fr, items):
        inside, face, cu, cv, Ls, Ws = cover_coords(g, f, mask)
        # потёрты углы и края крышек, у книг — концы корешка
        corner = np.minimum.reduce([np.hypot(cu, cv), np.hypot(1 - cu, cv), np.hypot(cu, 1 - cv), np.hypot(1 - cu, 1 - cv)])
        fray = np.maximum(fray, inside * np.maximum(1 - smooth(corner * min(Ws, Ls), 0.004, 0.03),
                                                     (1 - smooth(np.minimum(cv, 1 - cv) * Ls, 0.002, 0.012)) * (cu < 0.08)))
        if isinstance(item, str) and item in LABELS:
            u0, u1, rows = LABELS[item]
            pxm = 6.0
            im, d = page_img(Ws * 1000, Ls * 1000, pxm)
            for vr in rows:
                hand_line(d, (u0 + 0.06) * Ws * 1000, vr * Ls * 1000 - 1.0, (u1 - u0 - 0.08) * Ws * 1000, 4.5, pxm, rng, 0.75)
            a = np.asarray(im).astype(np.float32) / 255
            h, w = a.shape
            mx = np.where(face, np.clip(cu, 0, 1) * (w - 1), -10).astype(np.float32)
            my = np.where(face, np.clip(cv, 0, 1) * (h - 1), -10).astype(np.float32)
            ink = np.maximum(ink, cv2.remap(cv2.GaussianBlur(a, (0, 0), 0.6), mx, my, cv2.INTER_LINEAR,
                                            borderMode=cv2.BORDER_CONSTANT, borderValue=0))
    maps = {"ink": ink, "fray": fray, "up": smooth(g["nrm"][..., 2], 0.15, 0.75), "edge": W.edge_zone(g, 0.0008, 0.004)}
    # кольцо от кружки — на верхней обложке (стопка, одиночная)
    if fr and abs(fr[-1]["thick"][2]) > 0.7:
        top = fr[-1]
        c = np.array(top["center"]) + np.array(top["thick"]) * top["size"][2] / 2
        c = c + np.array(top["width"]) * top["size"][1] * 0.15 + np.array(top["length"]) * top["size"][0] * 0.12
        maps["rings"] = rings(g, [(tuple(c), 0.037)], seed=5) * mask
    save(game, maps, valid)
    print("ZONES", game, sorted(maps), flush=True)


def open_pages(game: str, pages: str) -> None:
    """Раскрытые: на полях страниц — подчёркнуто и приписано ручкой; страницы у края захватаны."""
    g = load(game)
    valid = g["part_id"] > 0
    pm = W.parts(g, pages) & (g["nrm"][..., 2] > 0.3)
    p = g["pos"][pm]
    (x0, y0), (x1, y1) = np.percentile(p[:, :2], 0.2, axis=0), np.percentile(p[:, :2], 99.8, axis=0)
    wmm, hmm = (x1 - x0) * 1000, (y1 - y0) * 1000
    pxm = 6.0
    im, d = page_img(wmm, hmm, pxm)
    rng = np.random.default_rng(31)
    for k in range(5 if game == "it_notebook_open" else 2):
        side = k % 2
        xs = (0.08 + 0.5 * side) * wmm
        hand_line(d, xs, (0.15 + 0.12 * k) * hmm, 0.34 * wmm, 4.5, pxm, rng, 0.75)
    a = np.asarray(im).astype(np.float32) / 255
    h, w = a.shape
    u = (g["pos"][..., 0] - x0) / (x1 - x0)
    v = (y1 - g["pos"][..., 1]) / (y1 - y0)
    mx = np.where(pm, np.clip(u, 0, 1) * (w - 1), -10).astype(np.float32)
    my = np.where(pm, np.clip(v, 0, 1) * (h - 1), -10).astype(np.float32)
    ink = cv2.remap(cv2.GaussianBlur(a, (0, 0), 0.6), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    edge_x = np.minimum(np.abs(g["pos"][..., 0] - x0), np.abs(x1 - g["pos"][..., 0]))
    maps = {"ink": ink, "touch": pm * (1 - smooth(edge_x, 0.005, 0.05)), "up": smooth(g["nrm"][..., 2], 0.15, 0.75),
            "edge": W.edge_zone(g, 0.0008, 0.004)}
    save(game, maps, valid)
    print("ZONES", game, sorted(maps), flush=True)


# ------------------------------------------------------------------------------------------------ предметы
def items(game: str) -> None:
    g = load(game)
    valid = g["part_id"] > 0
    pos, nrm = g["pos"], g["nrm"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    h = z - np.percentile(z[valid], 0.5)
    shp = valid.shape
    maps = {"up": smooth(nrm[..., 2], 0.15, 0.75), "edge": W.edge_zone(g)}
    if game in ON_FLOOR:
        maps["floor"] = 1 - smooth(h, 0.02, 0.15)
    lo3, hi3 = np.percentile(pos[valid], 1, axis=0), np.percentile(pos[valid], 99, axis=0)
    # углы габарита — там бьют при переноске и о пол
    dc = np.min([np.linalg.norm(pos - np.array([cx, cy, cz]), axis=-1)
                 for cx in (lo3[0], hi3[0]) for cy in (lo3[1], hi3[1]) for cz in (lo3[2], hi3[2])], axis=0)
    corner = 1 - smooth(dc, 0.03, 0.12)

    if game in ("it_ammo", "it_zip", "it_trunk", "it_toolbox"):
        # брошено недавно: сбито у самых углов и у нижней кромки, пятнами — не по каждой кромке доски
        tight = 1 - smooth(dc, 0.015, 0.06)
        patch = smooth(noise(*shp, 36, 31), 0.45, 0.7)
        maps["corner"] = tight * maps["edge"]
        maps["hits"] = maps["edge"] * np.maximum(tight, (1 - smooth(h, 0.0, 0.025)) * 0.7) * patch
        maps["kick"] = (nrm[..., 1] < -0.7) * (1 - smooth(h, 0.02, 0.14)) * smooth(noise(*shp, 40, 12), 0.35, 0.7)
        hw = W.parts(g, "Фурнитура_сталь", "Цинк_банка")
        maps["rust"] = hw * (0.5 + 0.5 * noise(*shp, 30, 21))
        if game == "it_toolbox":
            maps["touch"] = W.near(g, W.parts(g, "Пластик_чёрный"), 0.06)
    if game == "it_suitcase":
        maps["corner"] = corner * maps["edge"]
        maps["touch"] = W.near(g, W.parts(g, "Пластик_чёрный"), 0.05)
        maps["wheels"] = W.parts(g, "Резина") * 1.0
    if game == "it_duffel":
        bag = W.parts(g, "Ткань_сумка")
        maps["floor"] = bag * (1 - smooth(h, 0.0, 0.08)) * (0.6 + 0.4 * noise(*shp, 40, 4))
        maps["touch"] = W.parts(g, "Стропа") * 1.0
        maps["scuff"] = bag * W.fbm(g, cells=(0.05, 0.02), seed=9) * (1 - smooth(h, 0.02, 0.2))
    if game == "it_carton":
        card = W.parts(g, "Картон", "Картон_срез")
        # отсырел низ: граница неровная волной, выше — пара потёков
        line = 0.035 + 0.03 * W.vnoise(x * 3 + y * 3, z, 0.08, 7)
        maps["wet"] = card * (1 - smooth(h - line, -0.004, 0.01))
        maps["drips"] = card * W.drip(pos, card, [0.4, 0.0], 0.12, 0.03, 13) * (h > 0.02)
        maps["corner"] = card * corner * (0.5 + 0.5 * maps["edge"])
        tape = W.parts(g, "Скотч")
        maps["tape_edge"] = tape * W.edge_zone(g, 0.0004, 0.004)
    if game == "it_pc":
        maps["touch"] = (nrm[..., 1] < -0.7) * (z > hi3[2] - 0.08)
        maps["mesh_dust"] = W.parts(g, "Сетка_фасад") * 1.0
        maps["glass"] = W.parts(g, "Стекло_тёмное") * 1.0
    if game == "it_monitor":
        sc = W.parts(g, "Экран")
        maps["screen"] = sc * 1.0
        maps["touch"] = (nrm[..., 1] < -0.7) * (z < np.percentile(z[sc], 1) + 0.002) * W.parts(g, "Пластик_чёрный")
    if game == "it_keyboard":
        maps["keys"] = keys_zone(g, IP.keyboard_keys(), "Клавиши")
    if game == "it_mouse":
        # кнопки и бока — где лежат пальцы (перед — к −Y)
        maps["touch"] = (1 - smooth(y - lo3[1], 0.01, 0.07)) * (z > lo3[2] + 0.01) + \
            (np.abs(nrm[..., 0]) > 0.6) * (z > lo3[2] + 0.008) * 0.6
    if game == "it_laptop":
        maps["keys"] = keys_zone(g, IP.laptop_keys(), "Клавиши")
        base_top = W.parts(g, "Корпус_ноутбук") & (nrm[..., 2] > 0.9) & ~W.parts(g, "Корпус_ноутбук__крышка")
        maps["touch"] = base_top * (1 - smooth(y - lo3[1], 0.02, 0.11))   # подставка для запястий
        maps["lid"] = W.parts(g, "Корпус_ноутбук__крышка") * 1.0
        maps["screen"] = W.parts(g, "Экран") * 1.0
    if game == "it_tube":
        body = W.parts(g, "Тубус_пластик")
        # держат за середину, концы шаркают о пол
        mid = np.exp(-((x - 0.02) / 0.15) ** 2)
        maps["touch"] = body * mid
        maps["ends"] = body * (1 - smooth(np.minimum(np.abs(x - lo3[0]), np.abs(hi3[0] - x)), 0.0, 0.05))
    save(game, maps, valid)
    print("ZONES", game, sorted(maps), flush=True)


def run(game: str) -> None:
    if game in PAPER_SETS:
        paper(game)
    elif game == "it_book":
        covers(game, ["uchebnik_1"], "Переплёт")
    elif game == "it_book_stack":
        covers(game, ["uchebnik_2", "uchebnik_1", "uchebnik_3", "uchebnik_4"], "Переплёт")
    elif game == "it_book_row":
        covers(game, ["uchebnik_1", "uchebnik_2", "x", "uchebnik_3", "uchebnik_4", "x"], "Переплёт")
    elif game == "it_notebook":
        covers(game, ["tetrad_1"], "Обложка_тетради")
    elif game == "it_notebook48":
        covers(game, ["tetrad_obshchaya"], "Обложка_тетради")
    elif game == "it_notebook_stack":
        covers(game, ["tetrad_2", "tetrad_1", "tetrad_2", "tetrad_1", "tetrad_1"], "Обложка_тетради")
    elif game == "it_book_open":
        open_pages(game, "Обрез")
    elif game == "it_notebook_open":
        open_pages(game, "Бумага")
    else:
        items(game)


GAMES = ["it_ammo", "it_zip", "it_trunk", "it_toolbox", "it_suitcase", "it_duffel", "it_carton", *PAPER_SETS,
         "it_frame", "it_frame_pl", "it_pc", "it_monitor", "it_keyboard", "it_mouse", "it_laptop", "it_tube",
         "it_notebook", "it_notebook_open", "it_notebook_stack", "it_notebook48", "it_book", "it_book_open",
         "it_book_stack", "it_book_row"]

if __name__ == "__main__":
    for name in (sys.argv[1:] or GAMES):
        run(name)
