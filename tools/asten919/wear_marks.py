# АСТЕН-919, этап 2 (износ): маски следов использования в развёртке наборов (обычный Python: numpy, scipy, PIL).
#   python -X utf8 tools/asten919/wear_marks.py [набор …]
# Вход — <набор>_maps.npz (wear_maps.py: положение, нормаль и деталь каждого пикселя развёртки). Место следа задано в
# осях пистолета, в миллиметрах, а рисунок следа — фото-маска из библиотеки владельца E:/Models Blender/Маски_АЛЬФА
# (его отпечатки и мазки, масляные пятна, следы трения, царапины; скачанные CC0 ambientCG) проекцией на поверхность:
# каждый отпечаток — отдельный штамп своего размера и поворота. Процедурного шума в рисунке нет; случайны только места
# и повороты штампов на магазине (счётчик с постоянным зерном — результат повторяется).
# Заказ владельца 2026-11-12: «засаленность, как потным пальцем касаешься и ведёшь по поверхности — градиентный
# блестящий след» на насечках затвора и на нижней части магазина; на верхней четверти магазина «с рандомом» —
# потёртости и царапины от вставки в шахту; остальное — на усмотрение, как можно натуральнее.
# Правки владельца (вторая итерация): затёртости до металла на насечках; следы зуба в вырезе затворной задержки; лёгкие
# затёртости до металла на кнопке магазина и рычажках разборки; у выбрасывателя — следы вылетающих гильз, подтёки
# масла и лёгкий блеск; на задних углах затвора — лёгкие, не одинаковые и не резкие затёртости до металла, «как будто
# просто за срок эксплуатации вытерлось о кобуру, одежду».
# Выход — <WORK>/wear/<набор>_<вид>.png (8 бит, белое — след): grease (жир: блеск), polish (заполировано контактом),
# scuff (затёртый полимер), scratch (царапины), bare (покрытие вытерто до металла), brass (латунь гильз), oil (масло).
# Слои по ним — tools/asten919/sp_asten_wear.py.
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dims import *  # noqa: E402,F403
import tex_sets as T  # noqa: E402

LIB = "E:/Models Blender/Маски_АЛЬФА"
CC0 = LIB + "/50_Скачанные_CC0_ambientCG_ShareTextures"
MAPS = os.environ.get("ASTEN_WEAR_MAPS", T.WORK + "/wear_maps")
OUT = os.environ.get("ASTEN_WEAR_OUT", T.WORK + "/wear")
Image.MAX_IMAGE_PIXELS = None

# рисунки следов: имя → файл библиотеки владельца
IMG = {
    "drag_r2": "01_Отпечатки_пальцев/Отпечаток_смазанный_вправо_02.png",      # отпечаток с длинным хвостом вправо
    "drag_r1": "01_Отпечатки_пальцев/Отпечаток_смазанный_вправо_01.png",
    "drag_r3": "01_Отпечатки_пальцев/Отпечаток_смазанный_вправо_03.png",
    "drag_d1": "01_Отпечатки_пальцев/Отпечаток_смазанный_по_диагонали_01.png",
    "drag_d2": "01_Отпечатки_пальцев/Отпечаток_смазанный_по_диагонали_02.png",
    "drag_dn": "01_Отпечатки_пальцев/Отпечаток_смазанный_вниз_01.png",
    "rubbed": "01_Отпечатки_пальцев/Отпечаток_растёртый_01.png",
    "print_1": "01_Отпечатки_пальцев/Отпечаток_грязный_01.png",
    "print_2": "01_Отпечатки_пальцев/Отпечаток_грязный_02.png",
    "print_3": "01_Отпечатки_пальцев/Отпечаток_грязный_03.png",
    "oil_film": "20_Масляные_плёнки_и_смазка/Масло_01_Тонкая_плёнка.png",
    "oil_drag": "20_Масляные_плёнки_и_смазка/Масло_05_Капля_размазанная.png",
    "oil_torn": "20_Масляные_плёнки_и_смазка/Масло_08_Рваный_мазок.png",
    "palm_rub": "02_Отпечатки_ладоней/Ладонь_растёртая_01.png",
    "palm_part": "02_Отпечатки_ладоней/Ладонь_частичная_01.png",
    "rub_short": "18_Следы_резины_и_контакта/Резина_01_Короткий_мазок.png",
    "rub_torn": "18_Следы_резины_и_контакта/Резина_03_Рваные_полоски.png",
    "rub_arc": "18_Следы_резины_и_контакта/Резина_04_Дуговой_сдвиг.png",
    "rub_double": "18_Следы_резины_и_контакта/Резина_06_Двойной_мазок.png",
    "rub_fine": "18_Следы_резины_и_контакта/Резина_07_Тонкие_риски.png",
    "rub_broken": "18_Следы_резины_и_контакта/Резина_09_Прерывистое_трение.png",
    "scr_long": "09_Царапины/Царапины_длинные_плотные_01.png",
    "scr_small": "09_Царапины/Царапины_мелкие_01.png",
    "scr_cross": "09_Царапины/Царапины_перекрёстные_01.png",
    "cc_scr_lines": CC0 + "/ambientCG/Scratches001/Scratches001_2K-PNG_Opacity.png",     # тонкие параллельные риски
    "cc_scr_lines2": CC0 + "/ambientCG/Scratches004/Scratches004_2K-PNG_Opacity.png",
    "cc_streaks": CC0 + "/ambientCG/Smear005/Smear005_2K-PNG_Opacity.png",                # продольные мазки
    "wipe": "06_Разводы_и_следы_протирания/Протирание_по_диагонали_01.png",              # пятна протирания
    "wipe_arc": "06_Разводы_и_следы_протирания/Протирание_дугами_с_грязью_01.png",
    "worn": "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png",            # потёртости покрытия
    "oil_threads": "20_Масляные_плёнки_и_смазка/Масло_06_Нити_смазки.png",
    "oil_mixed": "20_Масляные_плёнки_и_смазка/Масло_10_Смешанный_перенос.png",
    "oil_spots": "20_Масляные_плёнки_и_смазка/Масло_07_Полупрозрачные_пятна.png",
}
_cache = {}
# жировой след — мазок, а не оттиск: гребни папиллярного рисунка смягчены (σ в пикселях рисунка 1254 px ≈ 0,2 мм)
SOFT = {"grease": 6.0, "bare": 9.0, "oil": 3.0}
# виды следов, у которых готовая карта ещё размывается в развёртке (σ, пикселей набора): вытертое за годы — без
# резкой границы
BLUR = {"bare": 4.0}
GAIN = {"bare": 2.0}       # после размытия тонкие кромки тускнеют — вернуть силу


def img(name, soft=0.0):
    if soft:
        key = (name, soft)
        if key not in _cache:
            _cache[key] = ndimage.gaussian_filter(img(name), soft * img(name).shape[0] / 1254.0)
        return _cache[key]
    if name not in _cache:
        p = IMG[name]
        im = Image.open(p if os.path.isabs(p) else f"{LIB}/{p}").convert("L")
        _cache[name] = np.asarray(im, np.float32) / 255.0
    return _cache[name]


def sample(im, fu, fv, wrap=False):
    """Рисунок в точках (fu вправо, fv вверх, 0…1); за краем — 0 или повтор."""
    h, w = im.shape
    x = fu * (w - 1)
    y = (1.0 - fv) * (h - 1)
    return ndimage.map_coordinates(im, [y, x], order=1, mode="wrap" if wrap else "constant", cval=0.0)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


# оси магазина: A — вдоль трубы вверх, S — вперёд поперёк трубы (как в part_magazine)
A = np.array([SIN, 0.0, COS])
S = np.array([COS, 0.0, -SIN])
Y = np.array([0.0, 1.0, 0.0])
X = np.array([1.0, 0.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


def mag_point(a, s, y):
    """Точка магазина по координате вдоль оси a, поперёк s (перед 0, зад −MAG_DEPTH) и y — в осях пистолета."""
    c0 = s + COS * MAG_REF[0] - SIN * MAG_REF[1]
    return np.array([COS * c0 + SIN * a, y, -SIN * c0 + COS * a])


class Set:
    def __init__(self, name):
        d = np.load(f"{MAPS}/{name}_maps.npz")
        self.name = name
        ids = d["ids"]
        self.shape = ids.shape
        self.idx = np.nonzero(ids.ravel() > 0)[0]                 # только пиксели с деталью
        self.pos = d["pos"].reshape(-1, 3)[self.idx].astype(np.float32)
        self.nrm = d["nrm"].reshape(-1, 3)[self.idx].astype(np.float32)
        self.ids = ids.ravel()[self.idx]
        self.names = [str(x) for x in d["ids_names"]]
        self.layers = {}

    def part(self, *names):
        want = [i for i, n in enumerate(self.names) if n in names]
        return np.isin(self.ids, want)

    def layer(self, kind):
        if kind not in self.layers:
            self.layers[kind] = np.zeros(len(self.idx), np.float32)
        return self.layers[kind]

    def centre(self, part, n, face=0.5):
        """Середина поверхности детали, обращённой по n (кнопка, перо спуска, площадка)."""
        m = self.part(part) & (self.nrm @ np.asarray(n, np.float32) > face)
        return self.pos[m].mean(axis=0).astype(np.float64)

    def stamp(self, kind, name, at, n, up, size, rot=0.0, parts=None, strength=1.0, depth=8.0, face=0.25,
              flip=False, weight=None):
        """Штамп рисунка name: середина at (мм), смотрит по n, «верх» рисунка — up, сторона size мм (или (ш, в)),
        поворот rot° против часовой, если смотреть на поверхность. Ложится на грани, обращённые к n (не круче face),
        не глубже depth мм от плоскости штампа; flip — зеркально по горизонтали. weight(pos, индексы) — множитель по месту."""
        im = img(name, SOFT.get(kind, 0.0))
        n = unit(n)
        v = unit(np.asarray(up, np.float64) - n * np.dot(up, n))
        u = np.cross(v, n)                                        # «право» рисунка, если смотреть на поверхность
        r = math.radians(rot)
        u, v = u * math.cos(r) + v * math.sin(r), -u * math.sin(r) + v * math.cos(r)
        w, h = (size, size) if np.isscalar(size) else size
        at = np.asarray(at, np.float64)
        d = self.pos - at.astype(np.float32)
        near = (d * d).sum(axis=1) < (0.75 * max(w, h)) ** 2 + depth * depth
        if parts:
            near &= self.part(*parts)
        ii = np.nonzero(near)[0]
        if not len(ii):
            return 0
        d = d[ii].astype(np.float64)
        pu, pv, pn = d @ u, d @ v, d @ n
        fc = self.nrm[ii].astype(np.float64) @ n
        ok = (np.abs(pu) < w / 2) & (np.abs(pv) < h / 2) & (np.abs(pn) < depth) & (fc > face)
        ii, pu, pv, fc = ii[ok], pu[ok], pv[ok], fc[ok]
        if not len(ii):
            return 0
        fu = pu / w + 0.5
        val = sample(im, 1.0 - fu if flip else fu, pv / h + 0.5) * strength * np.clip((fc - face) / 0.35, 0.0, 1.0)
        if weight is not None:
            val = val * weight(self.pos[ii], ii)
        lay = self.layer(kind)
        lay[ii] = np.maximum(lay[ii], val.astype(np.float32))
        return int((val > 0.05).sum())

    def edge(self):
        """Скруглённые кромки и углы по нормали: 0 на плоскости, 1 — нормаль посередине между гранями."""
        return np.clip((1.0 - np.abs(self.nrm).max(axis=1)) / 0.22, 0.0, 1.0)

    def tile(self, name, u, v, period, origin=(0.0, 0.0, 0.0), soft=0.0):
        """Рисунок name плиткой period мм в плоскости (u, v) — значения во всех пикселях набора."""
        d = self.pos.astype(np.float64) - np.asarray(origin, np.float64)
        return sample(img(name, soft), (d @ unit(u)) / period % 1.0, (d @ unit(v)) / period % 1.0, wrap=True).astype(np.float32)

    def add(self, kind, values):
        lay = self.layer(kind)
        np.maximum(lay, values.astype(np.float32), out=lay)

    def save(self):
        os.makedirs(OUT, exist_ok=True)
        for kind, lay in self.layers.items():
            if kind == "grease":          # фото-маски отпечатков тусклые (среднее ~0,3): жир — в полную силу
                lay = np.clip(lay * 1.9, 0.0, 1.0) ** 0.9
            full = np.zeros(self.shape[0] * self.shape[1], np.float32)
            full[self.idx] = np.clip(lay, 0.0, 1.0)
            if kind in BLUR:               # размытие только по своим пикселям (края островов не темнеют)
                cov = np.zeros_like(full)
                cov[self.idx] = 1.0
                num = ndimage.gaussian_filter(full.reshape(self.shape), BLUR[kind])
                den = ndimage.gaussian_filter(cov.reshape(self.shape), BLUR[kind])
                full = (np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0) * cov.reshape(self.shape)).ravel()
                full = np.clip(full * GAIN.get(kind, 1.0), 0.0, 1.0)
            Image.fromarray(np.uint8(full.reshape(self.shape) * 255.0 + 0.5)).save(f"{OUT}/{self.name}_{kind}.png")
            print(f"  {self.name}_{kind}: {100.0 * (lay > 0.08).mean():.2f} % поверхности набора, среднее по следу "
                  f"{float(lay[lay > 0.08].mean()) if (lay > 0.08).any() else 0:.2f}")


# ------------------------------------------------------------------------------------------------------- затвор
def slide():
    s = Set("slide")
    hw = SLIDE_HW
    steel = ("Slide", "MOS_Cover_Plate")
    # засаленные следы на задних насечках (X −27,5…−64): большой палец слева, указательный и средний справа; палец
    # ложится на насечки и съезжает назад при отведении затвора — хвост следа к затыльнику. В пазах жира меньше:
    # палец идёт по гребням.

    def ridges(p, ii):
        return np.clip((np.abs(p[:, 1]) - (hw - 0.42)) / 0.3, 0.3, 1.0)
    L = dict(n=Y, up=Z, parts=steel, weight=ridges)          # левый борт: «право» рисунка — к затыльнику (−X)
    R = dict(n=-Y, up=Z, parts=steel, weight=ridges, flip=True)
    s.stamp("grease", "drag_r2", (-37.0, hw, 1.5), size=40, rot=-6, **L)
    s.stamp("grease", "drag_r1", (-52.0, hw, -3.5), size=27, rot=12, strength=0.75, **L)
    s.stamp("grease", "rubbed", (-29.0, hw, 6.0), size=24, rot=40, strength=0.6, **L)
    s.stamp("grease", "drag_r3", (-39.0, -hw, 4.5), size=31, rot=8, **R)
    s.stamp("grease", "drag_r2", (-51.0, -hw, -2.5), size=37, rot=-5, strength=0.9, **R)
    s.stamp("grease", "drag_d2", (-28.0, -hw, -1.0), size=27, rot=20, strength=0.65, **R)
    # ладонь при отведении «сверху»: мазок на крышке выреза и у целика
    s.stamp("grease", "oil_drag", (-38.0, 0.0, SLIDE_TOP), n=Z, up=-X, size=24, rot=75, strength=0.5, parts=steel)
    # отдельные частичные отпечатки на гладких бортах и сверху (берут за затвор, проверяют патронник)
    s.stamp("grease", "print_1", (54.0, hw, 0.5), n=Y, up=Z, size=17, rot=25, strength=0.5, parts=steel)
    s.stamp("grease", "print_3", (27.0, -hw, -3.0), n=-Y, up=Z, size=16, rot=-30, strength=0.45, parts=steel)
    s.stamp("grease", "print_2", (72.0, 0.5, SLIDE_TOP), n=Z, up=-X, size=15, rot=110, strength=0.4, parts=steel)
    # мелкие риски от кобуры и одежды по бортам и верху, гуще к дулу; рисунок — мелкие царапины владельца
    out = (np.abs(s.nrm[:, 1]) > 0.75) | (s.nrm[:, 2] > 0.75)
    w = np.where(out & s.part(*steel), 0.14 + 0.22 * np.clip((s.pos[:, 0] - 60.0) / 50.0, 0.0, 1.0), 0.0)
    side = np.abs(s.nrm[:, 1]) > 0.75
    pat = np.where(side, s.tile("scr_small", X, Z, 70.0), s.tile("scr_small", X, Y, 70.0, origin=(13.0, 7.0, 0.0)))
    s.add("scratch", w * pat)
    slide_bare(s)
    slide_port(s, hw)
    # где покрытие вытерто до металла, жировая плёнка не должна его прятать
    s.layers["grease"] *= 1.0 - 0.65 * np.clip(s.layers["bare"] * 2.0, 0.0, 1.0)
    s.save()


def slide_bare(s):
    """Покрытие вытерто до металла — мягко, пятнами, по-разному слева и справа."""
    hw = SLIDE_HW
    p, n = s.pos, s.nrm
    steel = s.part("Slide", "MOS_Cover_Plate")
    e = s.edge()
    left = p[:, 1] > 0
    # пятна потёртости владельца — разные для левого и правого борта и для верха
    pl = s.tile("worn", X, Z, 64.0, origin=(7.0, 0, 3.0), soft=9.0)
    pr = s.tile("wipe", X, Z, 71.0, origin=(-19.0, 0, -11.0), soft=9.0)
    pt = s.tile("wipe_arc", X, Y, 58.0, origin=(5.0, 9.0, 0), soft=9.0)
    top = n[:, 2] > 0.6
    patch = np.clip(np.where(top, pt, np.where(left, pl, pr)) * 2.4, 0.0, 1.0)

    # 1) задние насечки: пальцы стирают покрытие на площадках между пазами и на их кромках, сильнее посередине
    #    высоты и там, где берутся чаще; в пазах покрытие цело
    u = (SERR_X0 - p[:, 0]) % (SERR_W + SERR_GAP)
    in_serr = (p[:, 0] < SERR_X0 + 1.2) & (p[:, 0] > SERR_X0 - SERR_N * (SERR_W + SERR_GAP) - 0.8) \
        & (p[:, 2] < 8.6) & (np.abs(p[:, 1]) > hw - 0.7)
    land = (u >= SERR_W - 0.15) & (np.abs(p[:, 1]) > hw - 0.14)
    grab = np.exp(-((p[:, 2] - 1.0) / 8.0) ** 2) * (0.55 + 0.45 * np.exp(-((p[:, 0] + 44.0) / 15.0) ** 2))
    side_k = np.where(left, 1.0, 0.8)
    w = np.where(in_serr & steel, np.maximum(0.62 * land, 0.95 * e) * grab * side_k * (0.25 + 0.75 * patch), 0.0)
    s.add("bare", w)

    # 2) задние углы и кромки затвора: о кобуру и одежду, не одинаково — слева сильнее, сверху слабее, пятнами
    rear = np.clip(1.0 - (p[:, 0] - SLIDE_X0) / 15.0, 0.0, 1.0) ** 1.4
    k = np.where(top, 0.55, np.where(left, 1.0, 0.7))
    corner = np.clip(e * 1.25, 0.0, 1.0)
    s.add("bare", np.where(steel, np.clip(corner * rear * k * 1.3 * (0.12 + 0.88 * patch), 0.0, 1.0), 0.0))
    # и чуть — передние углы у дула (кобура)
    front = np.clip((p[:, 0] - 100.0) / 13.0, 0.0, 1.0)
    s.add("bare", np.where(steel, corner * front * 0.45 * (0.1 + 0.9 * patch), 0.0))

    # 3) вырез под зуб затворной задержки (левый борт снизу, X 27…51): упорная стенка, потолок у неё и кромка
    #    выреза — блестящие следы работы зуба; ниже по кромке борта — дорожка, где зуб скользит
    a, b = STOP_NOTCH_X
    zone = steel & left & (p[:, 0] > a - 1.2) & (p[:, 0] < b + 6.5) & (p[:, 2] < STOP_NOTCH_TOP + 1.3) & (p[:, 1] > hw - 3.4)
    wall = np.clip((n[:, 0] - 0.35) / 0.4, 0.0, 1.0) * np.clip(1.0 - (p[:, 0] - a) / 2.2, 0.0, 1.0)
    roof = np.clip((-n[:, 2] - 0.4) / 0.4, 0.0, 1.0) * np.clip(1.0 - (p[:, 0] - a) / 7.0, 0.0, 1.0) * 0.8
    track = np.clip((-n[:, 2] - 0.2) / 0.5, 0.0, 1.0) * np.clip((p[:, 0] - a) / 6.0, 0.0, 1.0) * 0.45
    lip = e * np.clip(1.0 - (p[:, 0] - a) / 12.0, 0.0, 1.0) * 0.85
    s.add("bare", np.where(zone, np.maximum.reduce([wall, roof, track, lip]) * (0.45 + 0.55 * patch), 0.0))
    # ободок на борту вокруг выреза: зуб, входя и выходя, обтирает кромку — шире у упорной стенки
    x, z = p[:, 0], p[:, 2]
    zb = np.where(x <= a + 5.0, STOP_NOTCH_TOP,
                  STOP_NOTCH_TOP + (SLIDE_BOT - STOP_NOTCH_TOP) * np.clip((x - a - 5.0) / (b + 1.0 - a), 0.0, 1.0))
    d = np.where(x >= a, np.maximum(z - zb, 0.0), np.hypot(a - x, np.maximum(z - STOP_NOTCH_TOP, 0.0)))
    along = np.clip(1.0 - (x - a) / 16.0, 0.3, 1.0)
    rim = np.clip(1.0 - d / 1.1, 0.0, 1.0) * along
    flank = steel & left & (p[:, 1] > hw - 0.2) & (x > a - 1.3) & (x < b + 6.0) & (z < STOP_NOTCH_TOP + 1.3)
    s.add("bare", np.where(flank, rim * 0.8 * (0.4 + 0.6 * patch), 0.0))


def slide_port(s, hw):
    """Правый борт у выбрасывателя: латунные мазки от вылетающих гильз, подтёки масла из паза выбрасывателя и из-под
    окна, лёгкий масляный блеск вокруг."""
    st = ("Slide", "Extractor")
    Rr = dict(n=-Y, up=Z, parts=st)                    # правый борт: «право» рисунка — к дулу (+X)
    # гильза летит вправо-назад-вверх: мазки за окном над выбрасывателем и на задней кромке окна
    s.stamp("brass", "rub_fine", (-5.0, -hw, 5.2), size=9, rot=140, strength=0.8, **Rr)
    s.stamp("brass", "rub_fine", (-10.5, -hw, 7.0), size=7, rot=150, strength=0.6, **Rr)
    s.stamp("brass", "rub_fine", (-2.0, -hw, 2.8), size=6, rot=125, strength=0.7, **Rr)
    s.stamp("brass", "rub_fine", (1.2, -hw, 4.0), size=8, rot=160, strength=0.85, **Rr)
    s.stamp("brass", "rub_short", (-3.0, -7.5, SLIDE_TOP), n=Z, up=-X, size=9, rot=60, strength=0.6, parts=st)
    # масло: тонкая плёнка вокруг паза выбрасывателя, подтёки вниз от паза и от нижней кромки окна
    s.stamp("oil", "oil_film", (-9.0, -hw, -0.5), size=19, rot=20, strength=0.32, **Rr)
    s.stamp("oil", "oil_drag", (-12.5, -hw, -4.6), size=11, rot=-90, strength=0.9, **Rr)
    s.stamp("oil", "oil_threads", (-3.5, -hw, -5.0), size=9, rot=-80, strength=0.75, **Rr)
    s.stamp("oil", "oil_drag", (21.0, -hw, -4.0), size=9, rot=-97, strength=0.7, **Rr)
    # выбрасыватель сам в масле
    s.stamp("oil", "oil_mixed", (-9.0, -hw, 0.0), size=22, strength=0.6, n=-Y, up=Z, parts=("Extractor",))


# -------------------------------------------------------------------------------------------------------- рамка
def frame():
    s = Set("frame")
    fr = ("Frame",)
    gy = GRIP_HW
    # заполированные и засаленные ладонью щёчки рукояти: рисунок — растёртая ладонь владельца, по вершинам пупырышков
    s.stamp("polish", "palm_rub", (-47.0, gy, -74.0), n=Y, up=A, size=92, strength=0.75, parts=fr, depth=10)
    s.stamp("polish", "palm_part", (-47.0, -gy, -74.0), n=-Y, up=A, size=92, strength=0.75, parts=fr, depth=10, flip=True)
    # спинка рукояти под ладонью и передняя грань под пальцами
    s.stamp("polish", "oil_film", mag_point(-52.0, -MAG_DEPTH - 12.0, 0.0), n=-S, up=A, size=(26, 70), strength=0.6,
            parts=fr, depth=14, face=0.1)
    s.stamp("polish", "oil_torn", mag_point(-58.0, 8.0, 0.0), n=S, up=A, size=(24, 52), rot=90, strength=0.55, parts=fr,
            depth=12, face=0.1)
    # указательный палец вдоль рамки над скобой (правая сторона) и большой — слева над рукоятью: засаленный след
    s.stamp("grease", "drag_r2", (5.0, -FRAME_HW, -17.5), n=-Y, up=Z, size=28, rot=4, strength=0.42, parts=fr, depth=5)
    s.stamp("grease", "rubbed", (-36.0, FRAME_HW, -24.0), n=Y, up=Z, size=25, rot=-20, strength=0.65, parts=fr, depth=6)
    # низ скобы: палец левой руки
    s.stamp("grease", "print_2", (-2.0, 0.0, -58.5), n=-Z, up=X, size=15, strength=0.4, parts=fr, depth=6)
    s.save()


# ------------------------------------------------------------------------------- ствол и органы управления
def barrel_polish(s, part):
    """Ствол трётся о затвор: продольные блестящие мазки сверху у дула и на казённике, поясок у дульного отверстия
    затвора. Рисунок — продольные мазки (ambientCG Smear005) вдоль ствола."""
    m = s.part(part)
    p, n = s.pos, s.nrm
    ang = np.arctan2(p[:, 1], p[:, 2]) * BARREL_R          # длина дуги по окружности ствола, мм
    fu = (p[:, 0] / 42.0) % 1.0
    fv = (ang / 42.0) % 1.0
    pat = sample(img("cc_streaks"), fu, fv, wrap=True)
    top = np.clip((n[:, 2] - 0.15) / 0.5, 0.0, 1.0)
    front = np.clip((p[:, 0] - 62.0) / 14.0, 0.0, 1.0) * top
    hood = np.clip((30.0 - p[:, 0]) / 8.0, 0.0, 1.0) * np.clip((n[:, 2] - 0.55) / 0.3, 0.0, 1.0)
    ring = np.clip(1.0 - np.abs(p[:, 0] - 104.0) / 7.0, 0.0, 1.0) * 0.6
    outer = np.hypot(p[:, 1], p[:, 2]) > BARREL_R - 0.6      # наружная поверхность, не канал
    s.add("polish", np.where(m & outer, np.maximum(np.maximum(front, hood * 0.8), ring) * pat, 0.0))


def parts():
    s = Set("parts")
    barrel_polish(s, "Barrel")
    # перо спуска, кнопка магазина, площадка задержки: жир с пальца
    c = s.centre("Trigger", X)
    s.stamp("grease", "rubbed", c, n=X, up=Z, size=17, rot=15, strength=0.8, parts=("Trigger", "Trigger_Safety"), face=0.1)
    c = s.centre("Mag_Catch", Y)
    s.stamp("grease", "print_1", c + np.array([0.5, 0.0, -0.5]), n=Y, up=Z, size=15, rot=-15, strength=0.8, parts=("Mag_Catch",))
    c = s.centre("Slide_Stop", Y, face=0.6)
    s.stamp("grease", "print_2", c, n=Y, up=Z, size=12, rot=30, strength=0.7, parts=("Slide_Stop",))
    c = s.centre("Slide_Lock", Y, face=0.6)
    s.stamp("grease", "print_3", c, n=Y, up=Z, size=11, strength=0.5, parts=("Slide_Lock",))
    # лёгкие затёртости до металла: вершины рифления кнопки магазина и концов защёлки затвора («рычажки разборки»),
    # верх зуба задержки — пятнами по рисунку следов трения владельца
    e = s.edge()
    for part, sides, k in (("Mag_Catch", (1,), 0.40), ("Slide_Lock", (1, -1), 0.40)):
        m = s.part(part)
        for sg in sides:
            ysg = s.pos[:, 1] * sg
            face = m & (s.nrm[:, 1] * sg > 0.25)
            if not face.any():
                continue
            ymax = float(ysg[face].max())
            tops = np.clip(1.0 - (ymax - ysg) / 0.3, 0.0, 1.0)            # самые выступающие 0,3 мм — гребни
            c0 = s.pos[face].mean(axis=0).astype(np.float64)
            pat = s.tile("rub_broken" if sg > 0 else "rub_torn", X, Z, 17.0, origin=c0 + np.array([3.0, 0, 5.0]), soft=5.0)
            s.add("bare", np.where(face, np.maximum(tops, 0.6 * e) * k * np.clip(0.15 + pat * 1.9, 0.0, 1.0), 0.0))
    m = s.part("Slide_Stop")
    tx0, tx1 = STOP_TOOTH_X
    tooth = m & (s.pos[:, 0] > tx0 - 0.4) & (s.pos[:, 0] < tx1 + 1.2) & (s.pos[:, 2] > -11.6)
    s.add("bare", np.where(tooth, np.clip(0.35 + 0.65 * np.maximum(e, np.clip((s.nrm[:, 2] - 0.3) / 0.5, 0, 1)), 0, 1) * 0.45, 0.0))
    s.save()


def barrel_t():
    s = Set("barrel_t")
    barrel_polish(s, "Barrel_Threaded")
    s.save()


# ------------------------------------------------------------------------------------------------------ магазин
def magazine():
    s = Set("magazine")
    body = ("Magazine_Body",)
    low = ("Magazine_Body", "Magazine_Floorplate")
    p = s.pos.astype(np.float64)
    a = p @ A
    sc = COS * (p[:, 0] - MAG_REF[0]) - SIN * (p[:, 2] - MAG_REF[1])
    mb = s.part(*body)
    a_top, a_bot = float(a[mb].max()), float(a[mb].min())
    hy = MAG_HW
    rng = np.random.default_rng(919)
    print(f"  магазин: корпус вдоль оси {a_bot:.1f}…{a_top:.1f} мм")

    # --- низ: засаленные следы пальцев (большой слева, два пальца справа), палец съезжает вдоль корпуса вверх
    s.stamp("grease", "drag_r2", mag_point(a_bot + 27.0, -15.0, hy), n=Y, up=A, size=35, rot=84, parts=low)
    s.stamp("grease", "drag_dn", mag_point(a_bot + 17.0, -25.0, hy), n=Y, up=A, size=24, rot=170, strength=0.7, parts=low)
    s.stamp("grease", "drag_r3", mag_point(a_bot + 31.0, -11.0, -hy), n=-Y, up=A, size=29, rot=96, flip=True, parts=low)
    s.stamp("grease", "drag_r1", mag_point(a_bot + 16.0, -22.0, -hy), n=-Y, up=A, size=25, rot=80, flip=True, strength=0.85, parts=low)
    s.stamp("grease", "oil_drag", mag_point(a_bot + 24.0, 0.0, 0.0), n=S, up=A, size=(20, 34), rot=90, strength=0.7, parts=low, face=0.1)
    s.stamp("grease", "rubbed", mag_point(a_bot + 14.0, -MAG_DEPTH, 2.0), n=-S, up=A, size=20, strength=0.55, parts=low, face=0.1)
    # пятка: большим пальцем досылают магазин
    c = s.centre("Magazine_Floorplate", -A)
    s.stamp("grease", "print_1", c, n=-A, up=S, size=19, rot=20, strength=0.8, parts=("Magazine_Floorplate",))
    s.stamp("scratch", "scr_cross", c, n=-A, up=S, size=48, strength=0.5, parts=("Magazine_Floorplate",))

    # --- верхняя четверть «с рандомом»: зона трения о шахту, длина от губок меняется по обводу корпуса
    theta = np.arctan2(p[:, 1], sc + MAG_DEPTH / 2)
    n = s.nrm.astype(np.float64)
    ny, ns = np.abs(n @ Y), np.abs(n @ S)
    side = ny >= ns
    # пятна протирания владельца: ими рвётся и граница зоны, и сама сетка царапин — трётся не всё подряд
    patch = np.where(side, s.tile("wipe", A, S, 58.0, origin=(0, 0, 7.0)), s.tile("wipe", A, Y, 58.0, origin=(0, 5.0, 0)))
    patch = np.clip(patch * 2.2, 0.0, 1.0)
    length = 27.0 + 16.0 * (patch - 0.35) + sum(amp * np.sin(k * theta + ph) for k, amp, ph in
                                                 zip((1, 2, 3, 5), (5.0, 4.0, 3.0, 2.0), rng.uniform(0, 2 * math.pi, 4)))
    t = (a - (a_top - length)) / np.maximum(length, 1.0)             # 0 — нижняя граница зоны, 1 — верх
    zone = np.clip(t / 0.35, 0.0, 1.0) * (0.45 + 0.55 * np.clip(t, 0.0, 1.0)) * mb
    outward = (np.maximum(ny, ns) > 0.5) & (np.abs(n @ A) < 0.6)
    corner = 1.0 + 1.6 * np.clip(2.0 * ny * ns, 0.0, 1.0)            # скруглённые углы трутся сильнее
    # царапины вдоль хода магазина: тонкие параллельные риски (ambientCG Scratches001 / 004), длинные — владельца
    lines = np.where(side, s.tile("cc_scr_lines", A, S, 46.0), s.tile("cc_scr_lines", A, Y, 46.0, origin=(0, 3.0, 0)))
    lines2 = np.where(side, s.tile("cc_scr_lines2", A + 0.10 * S, S, 61.0), s.tile("cc_scr_lines2", A + 0.10 * Y, Y, 61.0))
    longs = np.where(side, s.tile("scr_long", A, S, 85.0, origin=(0, 0, 11.0)), s.tile("scr_long", A, Y, 85.0))
    scr = np.clip(1.5 * lines + 1.2 * lines2 + 0.9 * longs, 0.0, 1.0) * (0.18 + 0.82 * patch)
    s.add("scratch", np.where(outward, zone * np.clip(corner * 0.62, 0.0, 1.0) * scr, 0.0))
    # затёртости (матовые пятна трения): штампы следов контакта владельца в случайных местах зоны, вытянуты вдоль хода
    rubs = ("rub_short", "rub_torn", "rub_broken", "rub_double", "rub_fine", "rub_arc")
    faces = ((Y, lambda q: mag_point(a_top - q, rng.uniform(-MAG_DEPTH + 5, -5), hy)),
             (-Y, lambda q: mag_point(a_top - q, rng.uniform(-MAG_DEPTH + 5, -5), -hy)),
             (S, lambda q: mag_point(a_top - q, 0.0, rng.uniform(-6, 6))),
             (-S, lambda q: mag_point(a_top - q, -MAG_DEPTH, rng.uniform(-7, 7))))
    zone_w = zone.astype(np.float32)
    for nn, where in faces:
        for _ in range(6):
            q = abs(rng.normal(0.0, 13.0)) + 3.0                    # гуще у губок
            s.stamp("scuff", rubs[rng.integers(len(rubs))], where(q), n=nn, up=A, size=float(rng.uniform(15, 30)),
                    rot=float(rng.uniform(35, 75)), strength=float(rng.uniform(0.55, 1.0)), parts=body, depth=7, face=0.15,
                    flip=bool(rng.integers(2)), weight=lambda pp, ii: np.clip(1.4 * zone_w[ii], 0.0, 1.0))
    s.save()


BUILD = {"slide": slide, "frame": frame, "parts": parts, "barrel_t": barrel_t, "magazine": magazine}

if __name__ == "__main__":
    for name in (sys.argv[1:] or list(BUILD)):
        print("НАБОР", name)
        BUILD[name]()
