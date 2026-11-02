"""Вещи общежития, партия 3: печать этапа 1 слоем для Painter (prints/uv/<набор>[__<вариант>]_print_*).

  python -X utf8 tools/dorm_modules/items3_prints.py [набор …]

Картинки владельца (ChatGPT по RING_Dorm_Items/картинки/ПРОМТЫ.md) ложатся на бумагу по развёртке самого листа (карта
«prm», print_bake.py) — без искажений на волне, завёрнутом угле и рулоне; картины — по лицу картинки в раме, обложки
учебников и тетрадей — по осям каждой книги (items3_frames.py), корешки — подписью снизу вверх, остальная крышка — цветом
обложки. Кодом: трафареты военных ящиков, печать коробки (знаки, вымышленная марка), календарь (фото владельца + сетка
месяца), правила общежития, страницы раскрытых книги и тетради, подписи клавиш (латиница и кириллица), марки чемодана,
сумки и техники. Все марки и названия вымышлены. Варианты картинок одного листа — свои наборы печати
(<набор>__<картинка>), Painter выгружает их отдельными картами (items3_sp.py prints).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as A  # noqa: E402
import print_designs as PD  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "_asset_src" / "dorm_items3"
PICS = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Items/картинки")
SANS, SANS_B, SERIF, SERIF_B, MONO_B = PD.SANS, PD.SANS_B, PD.SERIF, PD.SERIF_B, PD.COND
INK = (0.08, 0.08, 0.07)
NL = chr(10)


# ------------------------------------------------------------------------------------------------ общее
def geo(game: str) -> dict:
    g = A.load_geo(BASE, game)
    p = BASE / "prints" / "geo" / f"{game}_prm.exr"
    if p.exists():
        g["prm"] = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)[..., ::-1].astype(np.float32)
    return g


def parts(g: dict, base: str) -> np.ndarray:
    """Все сетки слота base (с метками «__…» тоже)."""
    ids = [k for k, v in g["names"].items() if v.split("__")[0] == base]
    return np.isin(g["part_id"], ids)


def part(g: dict, name: str) -> np.ndarray:
    return A.part_mask(g, name)


def pic(name: str) -> np.ndarray:
    im = Image.open(PICS / f"{name}.png").convert("RGBA")
    return np.asarray(im).astype(np.float32) / 255.0


def fit(img: np.ndarray, aspect: float) -> np.ndarray:
    """Картинка под пропорции места (ширина / высота): обрезка по середине, без растяжения."""
    h, w = img.shape[:2]
    if w / h > aspect:
        nw = int(round(h * aspect))
        x0 = (w - nw) // 2
        return img[:, x0:x0 + nw]
    nh = int(round(w / aspect))
    y0 = (h - nh) // 2
    return img[y0:y0 + nh]


def to_np(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGBA")).astype(np.float32) / 255.0


def rgb255(c) -> tuple:
    return tuple(int(round(v * 255)) for v in c)


def solid(mask: np.ndarray, color) -> np.ndarray:
    prn = np.zeros(mask.shape + (4,), np.float32)
    prn[..., :3] = color
    prn[..., 3] = mask
    return prn


def over(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """b поверх a (обе RGBA, не премножены)."""
    ab = b[..., 3:4]
    out = a.copy()
    out[..., 3:4] = ab + a[..., 3:4] * (1 - ab)
    out[..., :3] = np.where(out[..., 3:4] > 1e-6, (b[..., :3] * ab + a[..., :3] * a[..., 3:4] * (1 - ab))
                            / np.maximum(out[..., 3:4], 1e-6), 0)
    return out


def save(game: str, prn: np.ndarray, rough=None, metal=None, key: str | None = None) -> None:
    A.save_layer(BASE, game if key is None else f"{game}__{key}", [(prn, metal, rough, 1.0)])


def by_prm(g: dict, mask: np.ndarray, img: np.ndarray, aspect: float) -> np.ndarray:
    """Картинка по развёртке листа: u слева направо, v снизу вверх; изнанка (−1) — без печати."""
    u, v = g["prm"][..., 0], g["prm"][..., 1]
    ok = mask & (u > -0.5) & (v > -0.5)
    return A.sample(fit(img, aspect), np.clip(u, 0, 1), np.clip(1 - v, 0, 1), ok)


def plane(g: dict, mask: np.ndarray, img: np.ndarray, front, right) -> np.ndarray:
    """Плоское лицо (картина, страница): пиксели маски, смотрящие к front, — самые передние; картинка — на их габарит
    (вправо — right), обрезкой под пропорции."""
    n = np.array(front, float)
    n /= np.linalg.norm(n)
    ua = np.array(right, float)
    ua -= n * (ua @ n)
    ua /= np.linalg.norm(ua)
    va = np.cross(ua, n)                    # вниз по картинке
    face = mask & ((g["nrm"] @ n) > 0.9)
    depth = g["pos"] @ n
    # одиночные пиксели запекания на краях островов уводили «самое переднее» — берётся почти самое
    top = np.percentile(depth[face], 99.9)
    face &= (depth > top - 0.0008) & (depth < top + 0.0008)
    pu, pv = g["pos"] @ ua, g["pos"] @ va
    u0, u1 = np.percentile(pu[face], (0.05, 99.95))
    v0, v1 = np.percentile(pv[face], (0.05, 99.95))
    return A.sample(fit(img, (u1 - u0) / (v1 - v0)), (pu - u0) / (u1 - u0), (pv - v0) / (v1 - v0), face)


def decal(g: dict, mask: np.ndarray, im: Image.Image, c, n, right, w_mm: float, h_mm: float, depth=0.03,
          cos_min=0.35) -> np.ndarray:
    return A.decal(g, mask, to_np(im), c, n, right, w_mm, h_mm, depth, cos_min)


# ------------------------------------------------------------------------------------------------ бумага по листу
PAPER = {
    # набор: (пропорции листа, [(ключ варианта, картинка или функция)])
    "it_poster": (600 / 900, ["plakat_tb", "plakat_pozhar", "plakat_go"]),
    "it_poster_torn": (600 / 900, ["plakat_pozhar", "plakat_tb", "plakat_go"]),
    "it_poster_curl": (600 / 900, ["plakat_go", "plakat_tb", "plakat_pozhar"]),
    "it_poster_s": (420 / 594, ["plakat_gruppa", "plakat_film"]),
    "it_poster_s_curl": (420 / 594, ["plakat_film", "plakat_gruppa"]),
    "it_clip": (210 / 297, ["vyrezka_1", "vyrezka_2", "pravila"]),
    "it_calendar": (296 / 430, ["kalendar"]),
    "it_chart": (700 / 1000, ["tablica_fizika", "mendeleev"]),
    "it_drawing": (841 / 594, ["chertezh"]),
    "it_drawing_roll": (841 / 594, ["chertezh"]),
}


def calendar_page() -> np.ndarray:
    """Лист настенного календаря 296 × 430: фото владельца сверху, месяц и сетка дней; года нет (не привязывать
    время сюжета), первое число — четверг."""
    px = 6.0
    W, H = 296, 430
    im = Image.new("RGBA", (int(W * px), int(H * px)), (246, 244, 238, 255))
    photo = Image.open(PICS / "kalendar_foto.png").convert("RGBA")
    pw, ph = int(280 * px), int(187 * px)
    pa = fit(np.asarray(photo).astype(np.float32) / 255, 280 / 187)
    im.paste(Image.fromarray((pa * 255).astype(np.uint8)).resize((pw, ph), Image.LANCZOS), (int(8 * px), int(8 * px)))
    d = ImageDraw.Draw(im)
    red, ink, grey = (178, 32, 30, 255), (34, 34, 36, 255), (120, 118, 112, 255)
    d.text((W / 2 * px, 222 * px), "ОКТЯБРЬ", font=PD.font(SERIF_B, 17 * px / PD.PX), fill=red, anchor="mm")
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    x0, cw, y0, rh = 26, 40.7, 248, 27
    fh = PD.font(SANS_B, 7 * px / PD.PX)
    fn = PD.font(SANS_B, 13 * px / PD.PX)
    for i, s in enumerate(days):
        d.text(((x0 + cw * i) * px, y0 * px), s, font=fh, fill=red if i >= 5 else grey, anchor="mm")
    d.line([(14 * px, (y0 + 7) * px), ((W - 14) * px, (y0 + 7) * px)], fill=grey, width=int(0.5 * px))
    start = 3
    for k in range(31):
        cell = start + k
        r, c = divmod(cell, 7)
        d.text(((x0 + cw * c) * px, (y0 + 22 + rh * r) * px), str(k + 1), font=fn, fill=red if c >= 5 else ink,
               anchor="mm")
    d.text((W / 2 * px, (H - 9) * px), "Типография «Северная печать» · заказ 1187 · тираж 5000",
           font=PD.font(SANS, 3.2 * px / PD.PX), fill=grey, anchor="mm")
    return to_np(im)


RULES = [
    "Проживающие обязаны соблюдать чистоту и порядок в комнатах и местах общего пользования.",
    "Вход в общежитие — по пропускам. Посетители допускаются с 9.00 до 22.00 с записью у вахтёра.",
    "Тишина в общежитии — с 23.00 до 7.00.",
    "Запрещается пользоваться в комнатах электроплитками, кипятильниками и самодельными нагревателями.",
    "Запрещается курить в комнатах, коридорах и на лестницах.",
    "Запрещается переносить мебель и инвентарь из комнаты в комнату без разрешения коменданта.",
    "Уходя из комнаты, выключить свет и электроприборы, закрыть окна и воду.",
    "О неисправностях сантехники и электропроводки сообщать дежурному.",
    "Порча имущества общежития возмещается проживающим.",
    "За нарушение правил проживающий может быть выселен.",
]


def rules_sheet() -> np.ndarray:
    """Правила проживания, лист А4 (машинопись, печать коменданта — без названия учреждения)."""
    px = 8.0
    W, H = 210, 297
    im = Image.new("RGBA", (int(W * px), int(H * px)), (243, 241, 233, 255))
    d = ImageDraw.Draw(im)
    ink = (30, 30, 32, 255)
    d.text((W / 2 * px, 26 * px), "ПРАВИЛА", font=PD.font(SERIF_B, 11 * px / PD.PX), fill=ink, anchor="mm")
    d.text((W / 2 * px, 38 * px), "ВНУТРЕННЕГО РАСПОРЯДКА В ОБЩЕЖИТИИ", font=PD.font(SERIF_B, 5.6 * px / PD.PX),
           fill=ink, anchor="mm")
    f = PD.font(SERIF, 4.0 * px / PD.PX)
    y = 54
    for i, s in enumerate(RULES, 1):
        words, line, lines = s.split(), "", []
        for w in words:
            t = (line + " " + w).strip()
            if f.getlength(t) > (W - 44) * px:
                lines.append(line)
                line = w
            else:
                line = t
        lines.append(line)
        d.text((20 * px, y * px), f"{i}.", font=f, fill=ink, anchor="lm")
        for ln in lines:
            d.text((27 * px, y * px), ln, font=f, fill=ink, anchor="lm")
            y += 6.4
        y += 2.6
    d.text((20 * px, (y + 14) * px), "Комендант общежития  ____________  /  ____________ /", font=f, fill=ink, anchor="lm")
    # круглая печать фиолетовым: кольцо и «ДЛЯ ДОКУМЕНТОВ»
    cx, cy, r = 150, y + 30, 16
    stamp = (88, 60, 150, 200)
    d.ellipse([((cx - r) * px, (cy - r) * px), ((cx + r) * px, (cy + r) * px)], outline=stamp, width=int(0.7 * px))
    d.ellipse([((cx - r + 3.5) * px, (cy - r + 3.5) * px), ((cx + r - 3.5) * px, (cy + r - 3.5) * px)], outline=stamp,
              width=int(0.5 * px))
    d.text((cx * px, cy * px), "ДЛЯ\nДОКУМЕНТОВ", font=PD.font(SANS_B, 3.2 * px / PD.PX), fill=stamp, anchor="mm",
           align="center")
    return to_np(im)


# элементы: номер → (знак, атомная масса строкой, название); масса в скобках — у радиоактивных (самый устойчивый изотоп)
ELEMENTS = {
    1: ("H", "1,008", "Водород"), 2: ("He", "4,0026", "Гелий"), 3: ("Li", "6,94", "Литий"), 4: ("Be", "9,0122", "Бериллий"),
    5: ("B", "10,81", "Бор"), 6: ("C", "12,011", "Углерод"), 7: ("N", "14,007", "Азот"), 8: ("O", "15,999", "Кислород"),
    9: ("F", "18,998", "Фтор"), 10: ("Ne", "20,180", "Неон"), 11: ("Na", "22,990", "Натрий"), 12: ("Mg", "24,305", "Магний"),
    13: ("Al", "26,982", "Алюминий"), 14: ("Si", "28,086", "Кремний"), 15: ("P", "30,974", "Фосфор"),
    16: ("S", "32,06", "Сера"), 17: ("Cl", "35,45", "Хлор"), 18: ("Ar", "39,948", "Аргон"), 19: ("K", "39,098", "Калий"),
    20: ("Ca", "40,078", "Кальций"), 21: ("Sc", "44,956", "Скандий"), 22: ("Ti", "47,867", "Титан"),
    23: ("V", "50,942", "Ванадий"), 24: ("Cr", "51,996", "Хром"), 25: ("Mn", "54,938", "Марганец"),
    26: ("Fe", "55,845", "Железо"), 27: ("Co", "58,933", "Кобальт"), 28: ("Ni", "58,693", "Никель"),
    29: ("Cu", "63,546", "Медь"), 30: ("Zn", "65,38", "Цинк"), 31: ("Ga", "69,723", "Галлий"), 32: ("Ge", "72,630", "Германий"),
    33: ("As", "74,922", "Мышьяк"), 34: ("Se", "78,971", "Селен"), 35: ("Br", "79,904", "Бром"), 36: ("Kr", "83,798", "Криптон"),
    37: ("Rb", "85,468", "Рубидий"), 38: ("Sr", "87,62", "Стронций"), 39: ("Y", "88,906", "Иттрий"),
    40: ("Zr", "91,224", "Цирконий"), 41: ("Nb", "92,906", "Ниобий"), 42: ("Mo", "95,95", "Молибден"),
    43: ("Tc", "[98]", "Технеций"), 44: ("Ru", "101,07", "Рутений"), 45: ("Rh", "102,91", "Родий"),
    46: ("Pd", "106,42", "Палладий"), 47: ("Ag", "107,87", "Серебро"), 48: ("Cd", "112,41", "Кадмий"),
    49: ("In", "114,82", "Индий"), 50: ("Sn", "118,71", "Олово"), 51: ("Sb", "121,76", "Сурьма"), 52: ("Te", "127,60", "Теллур"),
    53: ("I", "126,90", "Иод"), 54: ("Xe", "131,29", "Ксенон"), 55: ("Cs", "132,91", "Цезий"), 56: ("Ba", "137,33", "Барий"),
    57: ("La", "138,91", "Лантан"), 58: ("Ce", "140,12", "Церий"), 59: ("Pr", "140,91", "Празеодим"),
    60: ("Nd", "144,24", "Неодим"), 61: ("Pm", "[145]", "Прометий"), 62: ("Sm", "150,36", "Самарий"),
    63: ("Eu", "151,96", "Европий"), 64: ("Gd", "157,25", "Гадолиний"), 65: ("Tb", "158,93", "Тербий"),
    66: ("Dy", "162,50", "Диспрозий"), 67: ("Ho", "164,93", "Гольмий"), 68: ("Er", "167,26", "Эрбий"),
    69: ("Tm", "168,93", "Тулий"), 70: ("Yb", "173,05", "Иттербий"), 71: ("Lu", "174,97", "Лютеций"),
    72: ("Hf", "178,49", "Гафний"), 73: ("Ta", "180,95", "Тантал"), 74: ("W", "183,84", "Вольфрам"), 75: ("Re", "186,21", "Рений"),
    76: ("Os", "190,23", "Осмий"), 77: ("Ir", "192,22", "Иридий"), 78: ("Pt", "195,08", "Платина"), 79: ("Au", "196,97", "Золото"),
    80: ("Hg", "200,59", "Ртуть"), 81: ("Tl", "204,38", "Таллий"), 82: ("Pb", "207,2", "Свинец"), 83: ("Bi", "208,98", "Висмут"),
    84: ("Po", "[209]", "Полоний"), 85: ("At", "[210]", "Астат"), 86: ("Rn", "[222]", "Радон"), 87: ("Fr", "[223]", "Франций"),
    88: ("Ra", "[226]", "Радий"), 89: ("Ac", "[227]", "Актиний"), 90: ("Th", "232,04", "Торий"),
    91: ("Pa", "231,04", "Протактиний"), 92: ("U", "238,03", "Уран"), 93: ("Np", "[237]", "Нептуний"),
    94: ("Pu", "[244]", "Плутоний"), 95: ("Am", "[243]", "Америций"), 96: ("Cm", "[247]", "Кюрий"), 97: ("Bk", "[247]", "Берклий"),
    98: ("Cf", "[251]", "Калифорний"), 99: ("Es", "[252]", "Эйнштейний"), 100: ("Fm", "[257]", "Фермий"),
    101: ("Md", "[258]", "Менделевий"), 102: ("No", "[259]", "Нобелий"), 103: ("Lr", "[266]", "Лоуренсий"),
    104: ("Rf", "[267]", "Резерфордий"), 105: ("Db", "[268]", "Дубний"), 106: ("Sg", "[269]", "Сиборгий"),
    107: ("Bh", "[270]", "Борий"), 108: ("Hs", "[269]", "Хассий"), 109: ("Mt", "[278]", "Мейтнерий"),
    110: ("Ds", "[281]", "Дармштадтий"),
}
# короткая форма: ряд → восемь клеток групп I…VIII (номер или тройка номеров у VIII, сторона клетки: L — главная
# подгруппа, R — побочная; у VIII тройки — слева, благородные газы — справа)
SHORT = [
    (1, 1, [(1, "L"), None, None, None, None, None, None, (2, "R")]),
    (2, 2, [(3, "L"), (4, "L"), (5, "L"), (6, "L"), (7, "L"), (8, "L"), (9, "L"), (10, "R")]),
    (3, 3, [(11, "L"), (12, "L"), (13, "L"), (14, "L"), (15, "L"), (16, "L"), (17, "L"), (18, "R")]),
    (4, 4, [(19, "L"), (20, "L"), (21, "R"), (22, "R"), (23, "R"), (24, "R"), (25, "R"), ((26, 27, 28), "L")]),
    (4, 5, [(29, "R"), (30, "R"), (31, "L"), (32, "L"), (33, "L"), (34, "L"), (35, "L"), (36, "R")]),
    (5, 6, [(37, "L"), (38, "L"), (39, "R"), (40, "R"), (41, "R"), (42, "R"), (43, "R"), ((44, 45, 46), "L")]),
    (5, 7, [(47, "R"), (48, "R"), (49, "L"), (50, "L"), (51, "L"), (52, "L"), (53, "L"), (54, "R")]),
    (6, 8, [(55, "L"), (56, "L"), (57, "R"), (72, "R"), (73, "R"), (74, "R"), (75, "R"), ((76, 77, 78), "L")]),
    (6, 9, [(79, "R"), (80, "R"), (81, "L"), (82, "L"), (83, "L"), (84, "L"), (85, "L"), (86, "R")]),
    (7, 10, [(87, "L"), (88, "L"), (89, "R"), (104, "R"), (105, "R"), (106, "R"), (107, "R"), ((108, 109, 110), "L")]),
]
BLOCK_S = {1, 2, 3, 4, 11, 12, 19, 20, 37, 38, 55, 56, 87, 88}
BLOCK_P = set(range(5, 11)) | set(range(13, 19)) | set(range(31, 37)) | set(range(49, 55)) | set(range(81, 87))
BLOCK_F = set(range(58, 72)) | set(range(90, 104))
# цвета клеток как в кабинетных таблицах: s — розовые, p — жёлтые, d — голубые, f — зелёные
BLOCK_COL = {"s": (236, 180, 190), "p": (246, 226, 140), "d": (168, 204, 232), "f": (186, 222, 170)}


def block(z: int) -> str:
    return "s" if z in BLOCK_S else "p" if z in BLOCK_P else "f" if z in BLOCK_F else "d"


def mendeleev() -> np.ndarray:
    """Периодическая система, короткая форма (как в кабинетах химии 70–90-х), лист 700 × 1000: периоды и ряды,
    группы I–VIII с подгруппами, высшие оксиды и летучие водородные соединения, лантаноиды и актиноиды."""
    px = 4.0
    W, H = 700, 1000
    im = Image.new("RGBA", (int(W * px), int(H * px)), (247, 245, 238, 255))
    d = ImageDraw.Draw(im)
    ink, red, grey = (28, 28, 30, 255), (170, 30, 28, 255), (90, 90, 92, 255)

    def T(x, y, s, size, font=SANS, fill=ink, anchor="mm"):
        d.text((x * px, y * px), s, font=PD.font(font, size * px / PD.PX), fill=fill, anchor=anchor)

    def box(x0, y0, x1, y1, fill=None, width=0.5):
        d.rectangle([(x0 * px, y0 * px), (x1 * px, y1 * px)], fill=fill, outline=ink, width=max(1, int(width * px)))
    T(W / 2, 30, "ПЕРИОДИЧЕСКАЯ СИСТЕМА ЭЛЕМЕНТОВ", 26, SERIF_B)
    T(W / 2, 58, "Д. И. МЕНДЕЛЕЕВА", 20, SERIF_B, red)
    x0, cw, pw, rw = 22, 77, 18, 18
    gx = x0 + pw + rw
    y_head, hh, rh = 82, 26, 60
    box(x0, y_head, gx + 8 * cw, y_head + hh)
    T(x0 + pw / 2, y_head + hh / 2, "Пер.", 5.5)
    T(x0 + pw + rw / 2, y_head + hh / 2, "Ряды", 5.5)
    for g in range(8):
        box(gx + g * cw, y_head, gx + (g + 1) * cw, y_head + hh)
        T(gx + (g + 0.5) * cw, y_head + hh / 2, f"{['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'][g]}", 13, SERIF_B)
    y = y_head + hh
    periods = {}
    for period, row, cells in SHORT:
        periods.setdefault(period, [y, y])
        periods[period][1] = y + rh
        box(x0 + pw, y, x0 + pw + rw, y + rh)
        T(x0 + pw + rw / 2, y + rh / 2, str(row), 10)
        for g, cell in enumerate(cells):
            cx0 = gx + g * cw
            box(cx0, y, cx0 + cw, y + rh)
            if cell is None:
                continue
            zs, side = cell
            zs = zs if isinstance(zs, tuple) else (zs,)
            if len(zs) == 3:
                for k, z in enumerate(zs):
                    sym, mass, name = ELEMENTS[z]
                    bx = cx0 + 2 + k * (cw - 4) / 3
                    d.rectangle([(bx * px, (y + 2) * px), ((bx + (cw - 4) / 3 - 1) * px, (y + rh - 2) * px)],
                                fill=BLOCK_COL[block(z)] + (255,))
                    T(bx + (cw - 4) / 6, y + 18, sym, 11, SANS_B)
                    T(bx + (cw - 4) / 6, y + 7, str(z), 5.5)
                    T(bx + (cw - 4) / 6, y + 32, mass, 4.2)
                    T(bx + (cw - 4) / 6, y + 42, name, 3.4)
                continue
            z = zs[0]
            sym, mass, name = ELEMENTS[z]
            d.rectangle([((cx0 + 1.5) * px, (y + 1.5) * px), ((cx0 + cw - 1.5) * px, (y + rh - 1.5) * px)],
                        fill=BLOCK_COL[block(z)] + (255,))
            if side == "L":
                T(cx0 + 6, y + 20, sym + ("*" if z == 57 else "**" if z == 89 else ""), 17, SANS_B, anchor="lm")
                T(cx0 + cw - 6, y + 12, str(z), 9, SANS_B, anchor="rm")
            else:
                T(cx0 + cw - 6, y + 20, sym + ("*" if z == 57 else "**" if z == 89 else ""), 17, SANS_B, anchor="rm")
                T(cx0 + 6, y + 12, str(z), 9, SANS_B, anchor="lm")
            T(cx0 + cw / 2, y + 38, mass, 7)
            T(cx0 + cw / 2, y + 50, name, 6)
        y += rh
    for period, (ya, yb) in periods.items():
        box(x0, ya, x0 + pw, yb)
        T(x0 + pw / 2, (ya + yb) / 2, str(period), 14, SERIF_B)
    for label_, items in ((NL.join(["Высшие", "оксиды"]), ["R₂O", "RO", "R₂O₃", "RO₂", "R₂O₅", "RO₃", "R₂O₇", "RO₄"]),
                          (NL.join(["Летучие", "водородные", "соединения"]), ["", "", "", "RH₄", "RH₃", "H₂R", "HR", ""])):
        box(x0, y, gx, y + 22)
        d.multiline_text(((x0 + gx) / 2 * px, (y + 11) * px), label_, font=PD.font(SANS, 4.4 * px / PD.PX), fill=ink,
                         anchor="mm", align="center", spacing=0)
        for g, s in enumerate(items):
            box(gx + g * cw, y, gx + (g + 1) * cw, y + 22)
            if s:
                T(gx + (g + 0.5) * cw, y + 11, s, 9)
        y += 22
    y += 14
    for title, zs in (("* Лантаноиды", range(58, 72)), ("** Актиноиды", range(90, 104))):
        T(x0, y + 6, title, 8, SANS_B, red, anchor="lm")
        y += 14
        sw = (W - 2 * x0) / 7
        for k, z in enumerate(zs):
            r_, c_ = divmod(k, 7)
            bx, by = x0 + c_ * sw, y + r_ * 36
            box(bx, by, bx + sw, by + 36, fill=BLOCK_COL["f"] + (255,))
            sym, mass, name = ELEMENTS[z]
            T(bx + 6, by + 13, sym, 12, SANS_B, anchor="lm")
            T(bx + sw - 6, by + 9, str(z), 7, SANS_B, anchor="rm")
            T(bx + sw / 2, by + 24, mass, 5.5)
            T(bx + sw / 2, by + 31, name, 5)
        y += 2 * 36 + 10
    for k, (b, s) in enumerate((("s", "s-элементы"), ("p", "p-элементы"), ("d", "d-элементы"), ("f", "f-элементы"))):
        bx = x0 + k * 160
        box(bx, y, bx + 16, y + 10, fill=BLOCK_COL[b] + (255,))
        T(bx + 22, y + 5, s, 6, anchor="lm")
    T(W / 2, H - 12, "Учебное наглядное пособие · таблица № 1 · заказ 214", 5, fill=grey)
    return to_np(im)


def paper_img(key: str) -> np.ndarray:
    if key == "kalendar":
        return calendar_page()
    if key == "pravila":
        return rules_sheet()
    if key == "mendeleev":
        return mendeleev()
    return pic(key)


def paper(game: str) -> None:
    aspect, keys = PAPER[game]
    g = geo(game)
    mask = parts(g, "Бумага")
    for i, key in enumerate(keys):
        prn = by_prm(g, mask, paper_img(key), aspect)
        save(game, prn, key=None if i == 0 else key)
        print("PRINT", game, key, flush=True)


# ------------------------------------------------------------------------------------------------ картины
def frames(game: str, keys: list) -> None:
    g = geo(game)
    mask = parts(g, "Бумага")
    # лицо картины смотрит к −Y (висящая рама наклонена на 4,5°: средняя нормаль самых «лицевых» пикселей)
    nrm = g["nrm"][mask & (g["nrm"][..., 1] < -0.9)]
    front = nrm.mean(0)
    for i, key in enumerate(keys):
        prn = plane(g, mask, pic(key), front, (1.0, 0.0, 0.0))
        save(game, prn, key=None if i == 0 else key)
        print("PRINT", game, key, flush=True)


# ------------------------------------------------------------------------------------------------ книги и тетради
BOOKS = {
    # картинка: (название на корешок, автор, цвет надписи корешка)
    "uchebnik_1": ("СОПРОТИВЛЕНИЕ МАТЕРИАЛОВ", "В. Г. Пашков", (0.93, 0.93, 0.9)),
    "uchebnik_2": ("ВЫСШАЯ МАТЕМАТИКА · Т. 2", "Н. С. Ермолин", (0.85, 0.7, 0.38)),
    "uchebnik_3": ("НАЧЕРТАТЕЛЬНАЯ ГЕОМЕТРИЯ", "А. И. Крылова", (0.9, 0.88, 0.82)),
    "uchebnik_4": ("ТЕОРЕТИЧЕСКАЯ МЕХАНИКА", "С. М. Тарасов", (0.1, 0.2, 0.45)),
}
# книги без картинки владельца (в ряду): цвет переплёта, название, автор, цвет надписи
PLAIN = [((0.32, 0.12, 0.1), "ДЕТАЛИ МАШИН", "Л. Б. Савин", (0.86, 0.72, 0.4)),
         ((0.12, 0.26, 0.2), "ОБЩАЯ ХИМИЯ", "О. Р. Глинская", (0.9, 0.88, 0.8))]


def edge_color(img: np.ndarray) -> tuple:
    """Цвет обложки — средний по краю картинки (фон переплёта)."""
    h, w = img.shape[:2]
    b = max(4, w // 25)
    ring = np.concatenate([img[:b].reshape(-1, 4), img[-b:].reshape(-1, 4), img[:, :b].reshape(-1, 4),
                           img[:, -b:].reshape(-1, 4)])
    return tuple(float(x) for x in np.median(ring[:, :3], axis=0))


def spine_strip(title: str, author: str, color, L_mm: float, T_mm: float) -> np.ndarray:
    """Корешок развёрнутой полосой: текст вдоль (слева — низ книги), автор у низа, название — посередине."""
    px = 12.0
    im = Image.new("RGBA", (int(L_mm * px), max(8, int(T_mm * px))), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = min(T_mm * 0.42, 6.0)
    col = rgb255(color) + (255,)
    d.text((L_mm * 0.55 * px, T_mm / 2 * px), title, font=PD.font(SERIF_B, size * px / PD.PX), fill=col, anchor="mm")
    d.text((L_mm * 0.08 * px, T_mm / 2 * px), author.split()[-1], font=PD.font(SERIF, size * 0.8 * px / PD.PX),
           fill=col, anchor="lm")
    return to_np(im)


def covers(game: str, items: list, base: str, spines: bool) -> None:
    """Крышки книг (тетрадей) набора по осям items3_frames.py: вся крышка — цветом обложки, лицевая — картинкой,
    корешок — подписью. items — по одному на книгу (снизу вверх / слева направо): ключ картинки или PLAIN[i]."""
    g = geo(game)
    fr = json.loads((BASE / "prints" / "geo" / f"{game}_frames.json").read_text(encoding="utf-8"))
    mask = parts(g, base)
    prn = np.zeros(mask.shape + (4,), np.float32)
    pos, nrm = g["pos"], g["nrm"]
    for f, item in zip(fr, items):
        c = np.array(f["center"])
        Lv, Wv, Tv = (np.array(f[k]) for k in ("length", "width", "thick"))
        Ls, Ws, Ts = f["size"]
        d = pos - c
        dl, dw, dt = d @ Lv, d @ Wv, d @ Tv
        inside = mask & (np.abs(dl) < Ls / 2 + 0.002) & (np.abs(dw) < Ws / 2 + 0.002) & (np.abs(dt) < Ts / 2 + 0.002)
        if isinstance(item, str):
            img = pic(item)
            col = edge_color(img)
            title, author, tcol = BOOKS.get(item, ("", "", (1, 1, 1)))
        else:
            img = None
            col, title, author, tcol = item
        prn = over(prn, solid(inside.astype(np.float32), col))
        if img is not None:
            # лицевая крышка: у книги — у верхней грани габарита; у тетради (тонкая, угол загнут — габарит выше
            # крышки) — верхняя половина
            face = inside & ((nrm @ Tv) > 0.8) & (dt > (Ts / 2 - 0.0015 if Ts > 0.008 else 0.0))
            u = (dw + Ws / 2) / Ws
            v = (Ls / 2 - dl) / Ls
            prn = over(prn, A.sample(fit(img, Ws / Ls), np.clip(u, 0, 1), np.clip(v, 0, 1), face))
        if spines and title:
            sp = inside & ((nrm @ -Wv) > 0.45) & (dw < -Ws / 2 + Ts * 0.7)
            strip = spine_strip(title, author, tcol, Ls * 1000, Ts * 1000)
            u = (dl + Ls / 2) / Ls
            v = (dt + Ts / 2) / Ts
            prn = over(prn, A.sample(strip, np.clip(u, 0, 1), np.clip(v, 0, 1), sp))
    save(game, prn)
    print("PRINT", game, len(fr), "книг", flush=True)


def book_variants(game: str, keys: list, base: str) -> None:
    """Одиночная книга (тетрадь): основной вариант — первая картинка, остальные — свои наборы печати."""
    for i, key in enumerate(keys):
        covers(game, [key], base, spines=base == "Переплёт")
        if i:
            src = BASE / "prints" / "uv"
            for suf in ("_print_color.png", "_print_alpha.png", "_print.json"):
                os.replace(src / f"{game}{suf}", src / f"{game}__{key}{suf}")
    covers(game, [keys[0]], base, spines=base == "Переплёт")


def page_spread(w_mm: float, h_mm: float, kind: str) -> Image.Image:
    """Разворот: учебник — две колонки строк и формулы плашками; тетрадь — клетка 5 мм и поля."""
    px = 8.0
    im = Image.new("RGBA", (int(w_mm * px), int(h_mm * px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(7)
    if kind == "book":
        f = PD.font(SERIF, 2.3 * px / PD.PX)
        words = ("напряжение деформация сечение момент сила опора балка изгиб упругость стержень нагрузка "
                 "равновесие точка тело плоскость").split()
        for side in (0, 1):
            x0 = (side * w_mm / 2 + (16 if side == 0 else 12)) * px
            x1 = ((side + 1) * w_mm / 2 - (12 if side == 0 else 16)) * px
            y = 18.0
            while y < h_mm - 18:
                if rng.random() < 0.08:
                    d.text(((x0 + x1) / 2, y * px), "σ = N / F ≤ [σ]", font=PD.font(SERIF, 2.8 * px / PD.PX),
                           fill=(40, 40, 40, 255), anchor="mm")
                    y += 7
                    continue
                line, x = [], x0
                while True:
                    w = rng.choice(words)
                    if x + f.getlength(w + " ") > x1:
                        break
                    line.append(w)
                    x += f.getlength(w + " ")
                d.text((x0, y * px), " ".join(line), font=f, fill=(46, 46, 48, 255), anchor="lm")
                y += 3.6
            d.text((((side + 0.5) * w_mm / 2) * px, (h_mm - 10) * px), str(118 + side), font=f,
                   fill=(46, 46, 48, 255), anchor="mm")
    else:
        line = (150, 170, 190, 160)
        for k in range(int(w_mm / 5) + 1):
            d.line([(k * 5 * px, 0), (k * 5 * px, h_mm * px)], fill=line, width=1)
        for k in range(int(h_mm / 5) + 1):
            d.line([(0, k * 5 * px), (w_mm * px, k * 5 * px)], fill=line, width=1)
        for x in (25, w_mm - 25):
            d.line([(x * px, 0), (x * px, h_mm * px)], fill=(205, 60, 60, 220), width=2)
    return im


def open_pages(game: str, pages: str, kind: str, cover_col) -> None:
    """Раскрытые книга / тетрадь: страницы разворотом сверху, крышки — цветом обложки."""
    g = geo(game)
    pm = parts(g, pages) & (g["nrm"][..., 2] > 0.3)
    p = g["pos"][pm]
    (x0, y0), (x1, y1) = np.percentile(p[:, :2], 0.2, axis=0), np.percentile(p[:, :2], 99.8, axis=0)
    spread = page_spread((x1 - x0) * 1000, (y1 - y0) * 1000, kind)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    prn = decal(g, pm, spread, (cx, cy, p[:, 2].mean()), (0, 0, 1), (1, 0, 0), (x1 - x0) * 1000, (y1 - y0) * 1000,
                depth=0.05, cos_min=0.3)
    cover = parts(g, "Переплёт" if kind == "book" else "Обложка_тетради")
    prn = over(solid(cover.astype(np.float32), cover_col), prn)
    save(game, prn)
    print("PRINT", game, flush=True)


def lo(a: np.ndarray) -> float:
    """Почти наименьшее: одиночные пиксели запекания на краях островов уводят настоящий минимум."""
    return float(np.percentile(a, 1))


def hi(a: np.ndarray) -> float:
    return float(np.percentile(a, 99))


# ------------------------------------------------------------------------------------------------ трафареты, коробка
BRIDGE = set("ОАБВДРЯЮ0689ФQ")


def stencil(lines: list, w_mm: float, h_mm: float, color=(0.07, 0.07, 0.06)) -> Image.Image:
    """Трафарет краской: моноширинный жирный, у букв с замкнутыми полостями — перемычка посередине, край с
    напылом, краска неровная. lines: (текст, кегль мм, y мм)."""
    px = 10.0
    im = Image.new("L", (int(w_mm * px), int(h_mm * px)), 0)
    d = ImageDraw.Draw(im)
    for s, size, y in lines:
        f = PD.font(MONO_B, size * px / PD.PX)
        adv = f.getlength("М")
        x = (w_mm * px - adv * len(s)) / 2
        d.text((x, y * px), s, font=f, fill=255, anchor="lm")
        for i, ch in enumerate(s):
            if ch.upper() in BRIDGE:
                cx = x + adv * (i + 0.5)
                bw = max(1.0, size * 0.09 * px)
                d.rectangle([(cx - bw / 2, (y - size * 0.6) * px), (cx + bw / 2, (y + size * 0.6) * px)], fill=0)
    im = im.filter(ImageFilter.GaussianBlur(0.35 * px))
    a = np.asarray(im).astype(np.float32) / 255
    rng = np.random.default_rng(3)
    noise = cv2.GaussianBlur(rng.random(a.shape).astype(np.float32), (0, 0), 2.5 * px)
    noise = (noise - noise.min()) / max(1e-6, noise.max() - noise.min())
    a = np.clip(a * (0.72 + 0.38 * noise), 0, 0.95)
    out = np.zeros(a.shape + (4,), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def crate(game: str, front_lines: list, lid_lines: list, front_wh, lid_wh) -> None:
    g = geo(game)
    body = parts(g, "Дерево_окраска") & ~part(g, "Дерево_окраска__крышка")
    lid = part(g, "Дерево_окраска__крышка")
    fp = g["pos"][body & (g["nrm"][..., 1] < -0.9)]
    lp = g["pos"][lid & (g["nrm"][..., 2] > 0.9)]
    zc = (lo(fp[:, 2]) + hi(fp[:, 2])) / 2
    prn = decal(g, body, stencil(front_lines, *front_wh), (0.0, lo(fp[:, 1]), zc), (0, -1, 0), (1, 0, 0), *front_wh,
                depth=0.02)
    prn = over(prn, decal(g, lid, stencil(lid_lines, *lid_wh), (lp[:, 0].mean(), lp[:, 1].mean(), hi(lp[:, 2])),
                          (0, 0, 1), (1, 0, 0), *lid_wh, depth=0.02))
    save(game, prn, rough=0.78)
    print("PRINT", game, flush=True)


def carton_marks() -> Image.Image:
    """Печать флексо одним цветом на длинной стороне коробки 600 × 400: вымышленная марка, состав, знаки
    «беречь от влаги» и «верх», маркировка короба."""
    px = 8.0
    W, H = 560, 340
    im = Image.new("RGBA", (int(W * px), int(H * px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (52, 34, 24, 235)
    d.text((W / 2 * px, 70 * px), "«ЗЕРНОВИЦА»", font=PD.font(SERIF_B, 46 * px / PD.PX), fill=ink, anchor="mm")
    d.text((W / 2 * px, 118 * px), "КРУПА ГРЕЧНЕВАЯ ЯДРИЦА", font=PD.font(SANS_B, 20 * px / PD.PX), fill=ink, anchor="mm")
    d.text((W / 2 * px, 148 * px), "12 пачек × 900 г", font=PD.font(SANS, 15 * px / PD.PX), fill=ink, anchor="mm")
    f = PD.font(SANS, 8 * px / PD.PX)
    d.text((40 * px, 300 * px), "Дата изготовления ____________   Партия ______", font=f, fill=ink, anchor="lm")
    d.text((40 * px, 318 * px), "Короб гофрированный Т-23 · 600 × 400 × 400 · ГОСТ 9142", font=f, fill=ink,
           anchor="lm")
    # знаки: зонт (беречь от влаги) и две стрелки (верх) в рамках
    for k, sx in enumerate((410, 470)):
        x0, y0, s = sx * px, 200 * px, 48 * px
        d.rectangle([(x0, y0), (x0 + s, y0 + s)], outline=ink, width=int(1.6 * px))
        if k == 0:
            cx, cy = x0 + s / 2, y0 + s * 0.42
            d.pieslice([(cx - s * 0.34, cy - s * 0.3), (cx + s * 0.34, cy + s * 0.3)], 180, 360, fill=ink)
            d.line([(cx, cy), (cx, cy + s * 0.36)], fill=ink, width=int(1.8 * px))
            d.arc([(cx - s * 0.12, cy + s * 0.26), (cx, cy + s * 0.42)], 0, 180, fill=ink, width=int(1.8 * px))
            for dx in (-0.22, 0.0, 0.22):
                d.line([(cx + dx * s, y0 + s * 0.06), (cx + dx * s - s * 0.05, y0 + s * 0.13)], fill=ink,
                       width=int(1.2 * px))
        else:
            for dx in (-0.16, 0.16):
                cx = x0 + s / 2 + dx * s
                d.line([(cx, y0 + s * 0.85), (cx, y0 + s * 0.3)], fill=ink, width=int(2.2 * px))
                d.polygon([(cx - s * 0.12, y0 + s * 0.36), (cx + s * 0.12, y0 + s * 0.36), (cx, y0 + s * 0.12)],
                          fill=ink)
            d.line([(x0 + s * 0.2, y0 + s * 0.9), (x0 + s * 0.8, y0 + s * 0.9)], fill=ink, width=int(2 * px))
    return im


def carton() -> None:
    game = "it_carton"
    g = geo(game)
    body = part(g, "Картон")
    fp = g["pos"][body & (g["nrm"][..., 1] < -0.9)]
    bp = g["pos"][body & (g["nrm"][..., 1] > 0.9)]
    im = carton_marks()
    zc = (lo(fp[:, 2]) + hi(fp[:, 2])) / 2
    prn = decal(g, body, im, (0.0, lo(fp[:, 1]), zc), (0, -1, 0), (1, 0, 0), 560, 340, depth=0.02)
    # и на противоположной стороне (смотрящий с +Y читает слева направо: вправо — −X)
    prn = over(prn, decal(g, body, im, (0.0, hi(bp[:, 1]), zc), (0, 1, 0), (-1, 0, 0), 560, 340, depth=0.02))
    save(game, prn)
    print("PRINT", game, flush=True)


# ------------------------------------------------------------------------------------------------ марки вещей и техники
def logo(s: str, w_mm: float, h_mm: float, color, font=SANS_B, spacing: float = 0.18) -> Image.Image:
    """Марка строкой с разрядкой (вымышленная)."""
    px = 20.0
    im = Image.new("RGBA", (int(w_mm * px), int(h_mm * px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = PD.font(font, h_mm * 0.72 * px / PD.PX)
    adv = [f.getlength(ch) for ch in s]
    gap = h_mm * spacing * px
    total = sum(adv) + gap * (len(s) - 1)
    x = (w_mm * px - total) / 2
    for ch, a in zip(s, adv):
        d.text((x, h_mm / 2 * px), ch, font=f, fill=rgb255(color) + (255,), anchor="lm")
        x += a + gap
    return im


def suitcase() -> None:
    game = "it_suitcase"
    g = geo(game)
    shell = part(g, "Пластик_корпус__створка")
    fp = g["pos"][shell & (g["nrm"][..., 1] < -0.92)]
    c = (fp[:, 0].mean(), lo(fp[:, 1]), hi(fp[:, 2]) - 0.08)
    prn = decal(g, shell, logo("KORVENA", 110, 16, (0.78, 0.78, 0.8)), c, (0, -1, 0), (1, 0, 0), 110, 16, depth=0.03)
    save(game, prn, rough=0.25, metal=1.0)
    print("PRINT", game, flush=True)


def duffel() -> None:
    game = "it_duffel"
    g = geo(game)
    prn = np.zeros(g["pos"].shape[:2] + (4,), np.float32)
    for name in ("Ткань_сумка", "Ткань_сумка__полупустая"):
        m = part(g, name)
        fp = g["pos"][m & (g["nrm"][..., 1] < -0.85)]
        c = (np.median(fp[:, 0]), np.percentile(fp[:, 1], 5), np.median(fp[:, 2]))
        prn = over(prn, decal(g, m, logo("VELTRA", 150, 30, (0.92, 0.92, 0.9), spacing=0.12), c, (0, -1, 0), (1, 0, 0),
                              150, 30, depth=0.06, cos_min=0.3))
    save(game, prn, rough=0.55)
    print("PRINT", game, flush=True)


def monitor() -> None:
    game = "it_monitor"
    g = geo(game)
    bezel = part(g, "Пластик_чёрный")
    sc = g["pos"][part(g, "Экран") & (g["nrm"][..., 1] < -0.9)]
    bp = g["pos"][bezel & (g["nrm"][..., 1] < -0.9) & (g["pos"][..., 2] < lo(sc[:, 2])) &
                  (g["pos"][..., 2] > lo(sc[:, 2]) - 0.03)]
    c = (0.0, lo(bp[:, 1]), (lo(sc[:, 2]) + lo(bp[:, 2])) / 2)
    prn = decal(g, bezel, logo("ORSKEN", 26, 4, (0.62, 0.62, 0.64)), c, (0, -1, 0), (1, 0, 0), 26, 4, depth=0.01)
    save(game, prn)
    print("PRINT", game, flush=True)


def pc() -> None:
    game = "it_pc"
    g = geo(game)
    m = part(g, "Пластик_чёрный")
    fp = g["pos"][m & (g["nrm"][..., 1] < -0.92)]
    c = (np.median(fp[:, 0]), lo(fp[:, 1]), lo(fp[:, 2]) + 0.035)
    prn = decal(g, m, logo("ORSKEN", 34, 5, (0.7, 0.7, 0.72)), c, (0, -1, 0), (1, 0, 0), 34, 5, depth=0.01)
    save(game, prn)
    print("PRINT", game, flush=True)


# подписи клавиш: (латиница / знак, кириллица)
KB_ROWS = [
    ["Esc"] + [f"F{i}" for i in range(1, 13)],
    [("`", "Ё"), "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "←"],
    ["Tab", ("Q", "Й"), ("W", "Ц"), ("E", "У"), ("R", "К"), ("T", "Е"), ("Y", "Н"), ("U", "Г"), ("I", "Ш"), ("O", "Щ"),
     ("P", "З"), ("[", "Х"), ("]", "Ъ"), "\\"],
    ["Caps Lock", ("A", "Ф"), ("S", "Ы"), ("D", "В"), ("F", "А"), ("G", "П"), ("H", "Р"), ("J", "О"), ("K", "Л"),
     ("L", "Д"), (";", "Ж"), ("'", "Э"), "Enter"],
    ["Shift", ("Z", "Я"), ("X", "Ч"), ("C", "С"), ("V", "М"), ("B", "И"), ("N", "Т"), ("M", "Ь"), (",", "Б"),
     (".", "Ю"), ("/", "."), "Shift"],
    ["Ctrl", "Fn", "Alt", "", "Alt", "Fn", "≡", "Ctrl"],
]


def keyboard_keys() -> list:
    """Колпачки клавиатуры как в build_items3.keyboard: (середина верха x, y, ширина, глубина верха, подпись)."""
    from_rows = [(0, [(1, 0)] + [(1, 1 if i == 0 else (0.5 if i in (4, 8) else 0)) for i in range(12)]),
                 (1, [(1, 0)] * 13 + [(2, 0)]), (2, [(1.5, 0)] + [(1, 0)] * 12 + [(1.5, 0)]),
                 (3, [(1.75, 0)] + [(1, 0)] * 11 + [(2.25, 0)]), (4, [(2.25, 0)] + [(1, 0)] * 10 + [(2.75, 0)]),
                 (5, [(1.25, 0)] * 3 + [(6.25, 0)] + [(1.25, 0)] * 4)]
    W, Dk, u = 0.44, 0.135, 0.019
    x0 = -W / 2 + 0.012
    out = []

    def add(x, y, wu, hu, lab):
        out.append((x, y + 0.0006, wu * u - 0.0067, hu * u - 0.0057, lab))
    for row, keys in from_rows:
        y = Dk / 2 - 0.015 - row * u - (0.006 if row > 0 else 0)
        x = x0
        for k, (wu, gap) in enumerate(keys):
            x += gap * u
            add(x + wu * u / 2, y, wu, 1, KB_ROWS[row][k])
            x += wu * u
    xn = x0 + 15.25 * u
    nav = {0: ["PrtSc", "ScrLk", "Pause"], 1: ["Ins", "Home", "PgUp"], 2: ["Del", "End", "PgDn"]}
    for row, labs in nav.items():
        y = Dk / 2 - 0.015 - row * u - (0.006 if row > 0 else 0)
        for i, lab in enumerate(labs):
            add(xn + (i + 0.5) * u, y, 1, 1, lab)
    for row, cols in ((4, {1: "↑"}), (5, {0: "←", 1: "↓", 2: "→"})):
        y = Dk / 2 - 0.015 - row * u - 0.006
        for i, lab in cols.items():
            add(xn + (i + 0.5) * u, y, 1, 1, lab)
    xp = xn + 3.5 * u
    pad = {1: ["Num", "/", "*", "-"], 2: ["7", "8", "9", "+"], 3: ["4", "5", "6"], 4: ["1", "2", "3", "Enter"],
           5: ["0", "", "."]}
    for row in range(1, 6):
        y = Dk / 2 - 0.015 - row * u - 0.006
        for i in range(4):
            if i == 3 and row in (3, 5):
                continue
            if row == 5 and i == 1:
                continue
            lab = pad[row][i] if i < len(pad[row]) else ""
            if i == 3 and row in (2, 4):
                add(xp + (i + 0.5) * u, y - u / 2, 1, 2, lab)
                continue
            wu = 2 if (row == 5 and i == 0) else 1
            add(xp + i * u + wu * u / 2, y, wu, 1, lab)
    return out


def laptop_keys() -> list:
    W, Dn, u = 0.358, 0.245, 0.0185
    rows = [(0.75, [1] * 16), (1, [1] * 13 + [1.5] + [1] * 4), (1, [1.5] + [1] * 12 + [1.0] + [1] * 4),
            (1, [1.75] + [1] * 11 + [1.75] + [1] * 4), (1, [2.3] + [1] * 10 + [2.2] + [1] * 4),
            (1, [1] * 4 + [5.0] + [1] * 4 + [1] * 4)]
    labels = [
        ["Esc"] + [f"F{i}" for i in range(1, 13)] + ["PrtSc", "Ins", "Del"],
        KB_ROWS[1][:13] + ["←", "Num", "/", "*", "-"],
        KB_ROWS[2][:13] + ["\\", "7", "8", "9", "+"],
        KB_ROWS[3][:12] + ["Enter", "4", "5", "6", ","],
        KB_ROWS[4][:11] + ["Shift", "1", "2", "3", "Enter"],
        ["Ctrl", "Fn", "Alt", "≡", "", "Alt", "Ctrl", "◄", "►", "0", ".", "▲", "▼"],
    ]
    out = []
    y = Dn / 2 - 0.028
    for (hgt, keys), labs in zip(rows, labels):
        x = -W / 2 + 0.017
        for wu, lab in zip(keys, labs):
            out.append((x + wu * u / 2, y - hgt * u / 2, wu * u - 0.0032, hgt * u - 0.0032, lab))
            x += wu * u
        y -= hgt * u
    return out


def legend_cell(lab, w_mm: float, h_mm: float, px: float, col) -> Image.Image:
    im = Image.new("RGBA", (max(4, int(w_mm * px)), max(4, int(h_mm * px))), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = rgb255(col) + (255,)
    if isinstance(lab, tuple):
        lat, cyr = lab
        d.text((h_mm * 0.14 * px, h_mm * 0.14 * px), lat, font=PD.font(SANS, h_mm * 0.3 * px / PD.PX), fill=fill,
               anchor="lt")
        d.text(((w_mm - h_mm * 0.14) * px, (h_mm * 0.86) * px), cyr, font=PD.font(SANS, h_mm * 0.28 * px / PD.PX),
               fill=fill, anchor="rb")
    elif lab:
        size = h_mm * (0.34 if len(lab) <= 2 else 0.22)
        d.text((h_mm * 0.14 * px, h_mm * 0.14 * px), lab, font=PD.font(SANS, size * px / PD.PX), fill=fill,
               anchor="lt")
    return im


def keycaps(game: str, keys: list, base: str, top_cos: float = 0.85) -> np.ndarray:
    """Подписи клавиш: пиксель верха колпачка → ближайшая клавиша → её подпись (атлас ячеек, по одной на клавишу)."""
    g = geo(game)
    m = parts(g, base) & (g["nrm"][..., 2] > top_cos)
    idx = np.nonzero(m)
    p = g["pos"][idx]
    cx = np.array([k[0] for k in keys])
    cy = np.array([k[1] for k in keys])
    best = np.argmin((p[:, 0:1] - cx[None]) ** 2 + (p[:, 1:2] - cy[None]) ** 2, axis=1)
    px = 24.0
    cells, x, y, rowh, AW = [], 0, 0, 0, 2048
    ims = []
    for kx, ky, w, h, lab in keys:
        im = legend_cell(lab, w * 1000, h * 1000, px, (0.86, 0.86, 0.84))
        if x + im.width > AW:
            x, y, rowh = 0, y + rowh + 2, 0
        cells.append((x, y, im.width, im.height))
        ims.append(im)
        x += im.width + 2
        rowh = max(rowh, im.height)
    atlas = Image.new("RGBA", (AW, y + rowh + 2), (0, 0, 0, 0))
    for (ax, ay, _, _), im in zip(cells, ims):
        atlas.paste(im, (ax, ay))
    at = to_np(atlas)
    cell = np.array(cells, np.float32)
    kw = np.array([k[2] for k in keys])[best]
    kh = np.array([k[3] for k in keys])[best]
    u = (p[:, 0] - cx[best]) / kw + 0.5
    v = (cy[best] - p[:, 1]) / kh + 0.5
    ok = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    mx = np.full(m.shape, -10, np.float32)
    my = np.full(m.shape, -10, np.float32)
    mx[idx] = np.where(ok, cell[best, 0] + u * (cell[best, 2] - 1), -10)
    my[idx] = np.where(ok, cell[best, 1] + v * (cell[best, 3] - 1), -10)
    return cv2.remap(at, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def keyboard() -> None:
    prn = keycaps("it_keyboard", keyboard_keys(), "Клавиши")
    save("it_keyboard", prn)
    print("PRINT it_keyboard", flush=True)


def laptop() -> None:
    game = "it_laptop"
    prn = keycaps(game, laptop_keys(), "Клавиши")
    g = geo(game)
    lid = part(g, "Корпус_ноутбук__крышка")
    # крышка открыта на 115°: наружная сторона смотрит назад и вниз
    n = np.array([0.0, math.sin(math.radians(115)), math.cos(math.radians(115))])
    face = lid & ((g["nrm"] @ n) > 0.95)
    c = g["pos"][face].mean(0)
    prn = over(prn, decal(g, lid, logo("ORSKEN", 44, 7, (0.5, 0.5, 0.52)), c, n, (-1, 0, 0), 44, 7, depth=0.01))
    save(game, prn)
    print("PRINT", game, flush=True)


# ------------------------------------------------------------------------------------------------ запуск
def run(game: str) -> None:
    if game in PAPER:
        paper(game)
    elif game == "it_frame":
        frames(game, ["kartina_1", "kartina_2", "kartina_3"])
    elif game == "it_frame_pl":
        frames(game, ["kartina_3", "kartina_2", "kartina_1"])
    elif game == "it_book":
        book_variants(game, ["uchebnik_1", "uchebnik_2", "uchebnik_3", "uchebnik_4"], "Переплёт")
    elif game == "it_book_stack":
        covers(game, ["uchebnik_2", "uchebnik_1", "uchebnik_3", "uchebnik_4"], "Переплёт", spines=True)
    elif game == "it_book_row":
        covers(game, ["uchebnik_1", "uchebnik_2", PLAIN[0], "uchebnik_3", "uchebnik_4", PLAIN[1]], "Переплёт",
               spines=True)
    elif game == "it_book_open":
        open_pages(game, "Обрез", "book", edge_color(pic("uchebnik_1")))
    elif game == "it_notebook":
        book_variants(game, ["tetrad_1", "tetrad_2"], "Обложка_тетради")
    elif game == "it_notebook48":
        covers(game, ["tetrad_obshchaya"], "Обложка_тетради", spines=False)
    elif game == "it_notebook_stack":
        covers(game, ["tetrad_2", "tetrad_1", "tetrad_2", "tetrad_1", "tetrad_1"], "Обложка_тетради", spines=False)
    elif game == "it_notebook_open":
        open_pages(game, "Бумага", "notebook", edge_color(pic("tetrad_1")))
    elif game == "it_ammo":
        crate(game, [("7,62 ПС ГЖ", 26, 30), ("880 шт.   ВЕС 26 кг", 13, 62), ("ПАРТИЯ 17-83-412", 11, 84)],
              [("7,62 ПС", 30, 34), ("ВСКРЫТЬ ЗДЕСЬ ▼", 11, 72)], (440, 100), (420, 100))
    elif game == "it_zip":
        crate(game, [("ЗИП-К 4731", 40, 42), ("ГРУППОВОЙ   КОМПЛЕКТ № 3", 18, 92), ("ВЕС 64 кг", 15, 124)],
              [("ЗИП", 70, 60), ("ВЕРХ", 20, 118)], (900, 150), (880, 150))
    elif game == "it_carton":
        carton()
    elif game == "it_suitcase":
        suitcase()
    elif game == "it_duffel":
        duffel()
    elif game == "it_monitor":
        monitor()
    elif game == "it_pc":
        pc()
    elif game == "it_keyboard":
        keyboard()
    elif game == "it_laptop":
        laptop()


GAMES = (list(PAPER) + ["it_frame", "it_frame_pl", "it_book", "it_book_stack", "it_book_row", "it_book_open",
                        "it_notebook", "it_notebook48", "it_notebook_stack", "it_notebook_open", "it_ammo", "it_zip",
                        "it_carton", "it_suitcase", "it_duffel", "it_monitor", "it_pc", "it_keyboard", "it_laptop"])

if __name__ == "__main__":
    for name in (sys.argv[1:] or GAMES):
        run(name)
