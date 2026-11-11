"""«Проспект»: перенос чертежей в блокаут — сборка патча этапа (docs/tasks/prospekt_north_vershina_build.md).

Сцена prospekt_study.tscn — источник правды, генератор build_prospekt.py её сотрёт, поэтому правки идут патчами:
этот скрипт собирает data/blockouts/prospekt_patch_<этап>.json (разделы «remove» и «add»), а tools/prospekt_apply_patch.gd
(headless) убирает и добавляет узлы в сцене. Числа — из словарей чертежей (prospekt_north_side_plan.py,
prospekt_vershina_plan.py), модули при импорте ничего не пишут.

    python -X utf8 tools/prospekt_patch.py 1_street        # → data/blockouts/prospekt_patch_1_street.json
    tools/godot.cmd --headless res://tools/prospekt_apply_patch.tscn -- 1_street

Формат патча (метры, X — восток, Z — юг):
  remove.items   [{"kits": [набор…], "rect": [x0, z0, x1, z1]}]       вещи (PropSpot) по набору и прямоугольнику
  remove.pieces  [{"list": "boxes", "rect": […], "mat": "stripe", "id": "…"}]   куски улиц (PlanPiece): центр в прямоугольнике
  remove.nodes   ["Имя узла здания", …]                               узлы сцены по имени (поиск по всему дереву)
  add.<список плана>   записи как у генератора: surfaces, slabs, walls, boxes, columns, stairs, ramps, beams, lamps,
                       signs, ground_holes, walk_holes
  add.buildings  узлы зданий-объёмов {id, parent, at: [x, z], footprint: [w, d], floors, story_height, label, kind}
  add.items      записи наполнения [набор или «m:модель», x, z, поворот°, масштаб, подъём, оттенок, крен°, модель]
Повторный запуск apply убирает узлы с тем же meta patch_stage и ставит заново; убранное «remove» не возвращается.

Исходные записи для «переставить» берутся из снимка плана ДО правок (BASE_REV), чтобы патч собирался воспроизводимо.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospekt_north_side_plan as N  # noqa: E402  (при импорте ничего не пишет)

OUT = ROOT / "data" / "blockouts"
SNAPSHOT_PATH = "data/blockouts/prospekt_snapshot.json"
BASE_REV = "b4dd4fdf"          # снимок плана до этапа 1 (коммит «Проспект»: снимок плана после переноса «Зерна» v13)
BASE_REV_2 = "31286a76"        # снимок плана после этапа 1 — основа этапа 2 (тылы)

PLAN_LISTS = ("surfaces", "slabs", "walls", "boxes", "columns", "stairs", "ramps", "beams", "lamps", "signs",
              "ground_holes", "walk_holes")


# ------------------------------------------------------------------ патч и помощники (как в build_prospekt.py)
class Patch:
    def __init__(self, name: str, base_rev: str = BASE_REV) -> None:
        self.name = name
        self.base_rev = base_rev
        self.add_buildings: list = []
        self.remove: dict = {"items": [], "pieces": [], "nodes": []}
        self.add: dict = {k: [] for k in PLAN_LISTS}
        self.add["items"] = []
        self._base: dict | None = None
        self.log: list[str] = []

    # --- снимок до правок
    def base(self) -> dict:
        if self._base is None:
            try:
                raw = subprocess.run(["git", "show", f"{self.base_rev}:{SNAPSHOT_PATH}"], cwd=ROOT, check=True,
                                     capture_output=True).stdout
                self._base = json.loads(raw.decode("utf-8"))
            except Exception:
                self._base = json.loads((ROOT / SNAPSHOT_PATH).read_text(encoding="utf-8"))
        return self._base

    def find_item(self, kit: str, x: float, z: float, tol: float = 0.06) -> list:
        """Запись наполнения из снимка до правок: набор kit у точки (x, z)."""
        for it in self.base()["filler"]["items"]:
            if it[0] == kit and abs(it[1] - x) <= tol and abs(it[2] - z) <= tol:
                return list(it)
        raise KeyError(f"нет вещи {kit} у ({x}; {z}) в снимке {self.base_rev}")

    # --- вещи
    def drop_items(self, kits: list[str], rect: list[float]) -> int:
        """Убрать все вещи наборов kits в прямоугольнике [x0, z0, x1, z1]; вернуть, сколько их было в снимке."""
        n = sum(1 for it in self.base()["filler"]["items"]
                if it[0] in kits and rect[0] <= it[1] <= rect[2] and rect[1] <= it[2] <= rect[3])
        self.remove["items"].append({"kits": kits, "rect": [round(v, 3) for v in rect]})
        return n

    def drop_item(self, kit: str, x: float, z: float) -> list:
        rec = self.find_item(kit, x, z)
        self.remove["items"].append({"kits": [kit], "rect": [x - 0.06, z - 0.06, x + 0.06, z + 0.06]})
        return rec

    def move_item(self, kit: str, x: float, z: float, nx: float, nz: float, yaw: float | None = None) -> None:
        """Переставить вещь: прежнюю убрать, запись с новыми x, z (и поворотом) добавить."""
        rec = self.drop_item(kit, x, z)
        rec[1], rec[2] = round(nx, 3), round(nz, 3)
        if yaw is not None:
            rec[3] = round(yaw, 1)
        self.add["items"].append(rec)

    def put(self, kit: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, dy: float = 0.0, tint: float = -1,
            roll: float = 0.0, model: str = "") -> None:
        item: list = [kit, round(x, 3), round(z, 3), round(yaw, 1)]
        if model:
            item += [s, dy, tint, roll, model]
        elif s != 1.0 or dy != 0.0 or tint >= 0 or roll != 0.0:
            item += [s, dy]
            if tint >= 0 or roll != 0.0:
                item.append(tint)
            if roll != 0.0:
                item.append(roll)
        self.add["items"].append(item)

    # --- куски улиц
    def surface(self, sid: str, mat: str, x0: float, z0: float, x1: float, z1: float, y: float = 0.0, t: float = 0.08) -> None:
        self.add["surfaces"].append({"id": sid, "mat": mat, "rect": [min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)],
                                     "y": y, "t": t})

    def wall(self, x0: float, z0: float, x1: float, z1: float, y0: float, y1: float, mat: str = "wall") -> None:
        self.add["walls"].append({"rect": [min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)], "y0": y0, "y1": y1, "mat": mat})

    def box(self, x: float, y: float, z: float, sx: float, sy: float, sz: float, mat: str = "wall", yaw: float = 0.0,
            solid: bool = True) -> None:
        self.add["boxes"].append({"at": [round(x, 3), round(y, 3), round(z, 3)], "size": [round(sx, 3), round(sy, 3), round(sz, 3)],
                                  "mat": mat, "yaw": round(yaw, 2), "solid": solid})

    def slab(self, sid: str, rect: list, y_top: float, t: float = 0.3, mat: str = "slab", holes=()) -> None:
        self.add["slabs"].append({"id": sid, "rect": [round(v, 3) for v in rect], "y_top": y_top, "t": t, "mat": mat,
                                  "holes": [[round(v, 3) for v in h] for h in holes]})

    def stair(self, a: tuple, b: tuple, width: float, mat: str = "concrete") -> None:
        """Марш от a до b (x, y, z): ступени по 17 см."""
        self.add["stairs"].append({"from": [round(v, 3) for v in a], "to": [round(v, 3) for v in b], "width": width,
                                   "count": max(6, int(abs(b[1] - a[1]) / 0.17 + 0.5)), "mat": mat})

    def beam(self, a: tuple, b: tuple, w: float, d: float, mat: str = "concrete") -> None:
        self.add["beams"].append([[round(v, 3) for v in a], [round(v, 3) for v in b], w, d, mat])

    # --- стены с проёмами в мировых осях (как wall_x / wall_z / windows в build_prospekt.py, без поворотных рам)
    def wall_x(self, z: float, x0: float, x1: float, y0: float, h: float, gaps=(), t: float = 0.25, mat: str = "wall") -> None:
        """Стена вдоль x (z = const) с проёмами (x, ширина, верх[, низ]); низ > 0 — окно с подоконником."""
        x = x0
        for c in sorted(gaps, key=lambda g: g[0]):
            a, b = c[0] - c[1] * 0.5, c[0] + c[1] * 0.5
            top = min(c[2], h)
            low = c[3] if len(c) > 3 else 0.0
            if a - x > 0.01:
                self.wall(x, z - t * 0.5, a, z + t * 0.5, y0, y0 + h, mat)
            if h - top > 0.01:
                self.wall(a, z - t * 0.5, b, z + t * 0.5, y0 + top, y0 + h, mat)
            if low > 0.01:
                self.wall(a, z - t * 0.5, b, z + t * 0.5, y0, y0 + low, mat)
            x = b
        if x1 - x > 0.01:
            self.wall(x, z - t * 0.5, x1, z + t * 0.5, y0, y0 + h, mat)

    def wall_z(self, x: float, z0: float, z1: float, y0: float, h: float, gaps=(), t: float = 0.25, mat: str = "wall") -> None:
        """То же вдоль z (x = const); проёмы (z, ширина, верх[, низ])."""
        z = z0
        for c in sorted(gaps, key=lambda g: g[0]):
            a, b = c[0] - c[1] * 0.5, c[0] + c[1] * 0.5
            top = min(c[2], h)
            low = c[3] if len(c) > 3 else 0.0
            if a - z > 0.01:
                self.wall(x - t * 0.5, z, x + t * 0.5, a, y0, y0 + h, mat)
            if h - top > 0.01:
                self.wall(x - t * 0.5, a, x + t * 0.5, b, y0 + top, y0 + h, mat)
            if low > 0.01:
                self.wall(x - t * 0.5, a, x + t * 0.5, b, y0, y0 + low, mat)
            z = b
        if z1 - z > 0.01:
            self.wall(x - t * 0.5, z, x + t * 0.5, z1, y0, y0 + h, mat)

    @staticmethod
    def windows(a0: float, a1: float, step: float, w: float, low: float, top: float, doors=()) -> list:
        """Окна через шаг по стене от a0 до a1 мимо дверей [(центр, ширина)]."""
        out = []
        a = a0 + step * 0.5
        while a < a1 - w * 0.5:
            if all(abs(a - d[0]) > (w + d[1]) * 0.5 + 0.6 for d in doors) and a - w * 0.5 > a0 + 0.4:
                out.append((a, w, top, low))
            a += step
        return out

    def save(self) -> Path:
        path = OUT / f"prospekt_patch_{self.name}.json"
        add = {k: v for k, v in self.add.items() if v}
        if self.add_buildings:
            add["buildings"] = self.add_buildings
        data = {"stage": self.name, "base_rev": self.base_rev, "remove": self.remove, "add": add}
        # перевод строки — LF (рабочая копия проекта — CRLF через autocrlf, но JSON данных пишем как есть)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        return path


# ------------------------------------------------------------------ этап 1: улица, северная сторона
X_MIN, X_MAX = -162.0, 6.0          # западнее −162 — «Зерно» и пролог, не трогать
ROAD_END_X = 0.0                    # покрытие road_w и тротуар walk_wn кончаются на X 0 (дальше — плаза)
CURB_Z = N.CURB                     # −35.15, старая кромка тротуара
NEW_EDGE = N.LANE_EDGE              # −32.65, новая кромка там, где полоса стала тротуаром
POCKET_Z = (CURB_Z + NEW_EDGE) / 2.0   # −33.9 — ось кармана
WALK_T = 0.15                       # толщина тротуара, как у walk_wn
CURB_H, CURB_W = 0.15, 0.2          # бордюр: коробка stripe 0.15 × 0.2, как у существующих
BULB_BOLLARD_Z = -32.9
BOLLARD_PITCH = 2.5
TREE_Z = -38.4
STRIP_Z = -37.7                     # полоса у бордюра для урн и тумб (−38.4…−37.0)
POLES_X = [-142.0, -110.0, -78.0, -46.0, -14.0]     # опоры контактной сети (не трогать)


def _gaps(x0: float, x1: float, pockets: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Куски полосы x0…x1 между карманами: там полоса у бордюра становится тротуаром."""
    out: list[tuple[float, float]] = []
    x = x0
    for a, b in sorted(pockets):
        if a > x:
            out.append((x, min(a, x1)))
        x = max(x, b)
    if x < x1:
        out.append((x, x1))
    return [g for g in out if g[1] - g[0] > 1.0]


def stage_1_street() -> Patch:
    p = Patch("1_street")
    pk = {k: (x0, x1, n) for k, x0, x1, n, _ in N.POCKETS}
    k2, k3, k5 = pk["К2"], pk["К3"], pk["К5"]
    bay = N.BUS_BAY
    # карманы и остановка остаются асфальтом (скосы торцов 2,5 м в этом этапе не делаются — торцы прямоугольные)
    asphalt = [(k2[0], k2[1]), (k3[0], bay[1]), (k5[0], k5[1])]
    # K3 (…−71.5) и остановка (−71…) разделяет полоса 0,5 м: слишком узко для тротуара — остаётся асфальтом
    walks = [g for g in _gaps(X_MIN, ROAD_END_X, asphalt)]

    # 1. тротуар на месте полосы у бордюра и бордюр по новой кромке
    for i, (a, b) in enumerate(walks, 1):
        p.surface(f"walk_s{i}", "walk", a, CURB_Z, b, NEW_EDGE, 0.0, WALK_T)
        p.box((a + b) / 2.0, CURB_H / 2.0, NEW_EDGE - CURB_W / 2.0, b - a, CURB_H, CURB_W, "stripe", 0.0, True)
        for edge, side in ((a, 1.0), (b, -1.0)):
            # торцевой бордюр на границе с асфальтом; на X 0 тротуар переходит в плазу — торца нет, на X_MIN — торец есть
            if abs(edge - ROAD_END_X) < 0.01:
                continue
            p.box(edge + side * CURB_W / 2.0, CURB_H / 2.0, POCKET_Z, CURB_W, CURB_H, NEW_EDGE - CURB_Z, "stripe", 0.0, True)

    # 2. разметка мест в карманах: поперечные линии (светлая полоса поверх асфальта, как у остальной разметки)
    def line(x: float) -> None:
        p.box(x, 0.085, POCKET_Z, 0.15, 0.02, NEW_EDGE - CURB_Z - 0.3, "stripe", 0.0, False)

    n_lines = 0
    for lx in (k2[0] + 0.4, k2[1] - 0.4):                     # К2: одно место на 12 м — ограничивающие линии
        line(lx)
        n_lines += 1
    step = 6.9                                                 # К3: 4 места по 6,9 м (27,6 из 32,5 м; остаток — въезд)
    for i in range(k3[2] + 1):                                 # 5 линий на 4 места от западного края +1,5 м
        line(k3[0] + 1.5 + i * step)
        n_lines += 1
    for lx in (k5[1] - 9.0, k5[1] - 0.5):                      # К5: высадка и одно место 8,5 м
        line(lx)
        n_lines += 1
    p.log.append(f"линий разметки {n_lines}")

    # 3. столбики m:U02_04 у старого бордюра — убрать, на выступах — по кромке через 2,5 м
    p.log.append("столбиков убрано %d" % p.drop_items(["m:U02_04"], [X_MIN, -36.5, X_MAX, -35.3]))
    half_x = [it[1] for it in p.base()["filler"]["items"] if it[0] == "half_sphere" and -136 <= it[1] <= -104
              and -37 <= it[2] <= -35]
    n_bol = 0
    for a, b in walks:
        x = a + 1.0
        while x <= min(b - 0.5, X_MAX - 4.0):
            ok = True
            if -136.0 <= a < b <= -104.0 and (abs(x + 126.0) < 3.5 or any(abs(x - hx) < 0.9 for hx in half_x)):
                ok = False                                        # зебра и уже стоящие полусферы у перехода
            if ok:
                p.put("m:U02_04", x, BULB_BOLLARD_Z, 90.0)
                n_bol += 1
            x += BOLLARD_PITCH
    p.log.append(f"столбиков поставлено {n_bol}")

    # 4. машины и фургоны из полосы: в карман или прочь
    p.move_item("van", -40.0, -33.9, -10.0, POCKET_Z)            # К5: фургон из остановки на место у банка
    p.move_item("truck", -98.0, -33.9, k3[0] + 1.5 + step * 0.5, POCKET_Z)   # К3: грузовик на первое место между линиями
    p.put("bus_city", -45.0, POCKET_Z, 90.0, 1.0, 0.0, 8.0, 0.0, "PV_bus12")  # остановка: один автобус у площадки

    # 5. деревья: у фасадов (Z −44.3) убрать, в полосу у бордюра на X из TREES_X (≥ −162, от опор ≥ 3 м)
    old_trees = [it for it in p.base()["filler"]["items"] if it[0] == "tree_birch" and X_MIN <= it[1] <= X_MAX
                 and -44.8 <= it[2] <= -43.8]
    p.drop_items(["tree_birch"], [X_MIN, -44.8, X_MAX, -43.8])
    xs = sorted(x for x in N.TREES_X if x >= X_MIN)
    fixed: list[float] = []
    for x in xs:
        while any(abs(x - px) < 3.0 for px in POLES_X) or -160.0 <= x <= -150.0:
            x -= 2.0
        fixed.append(x)
    old_trees.sort(key=lambda it: it[1])
    for i, x in enumerate(fixed):
        rec = list(old_trees[min(i, len(old_trees) - 1)])
        rec[1], rec[2] = round(x, 2), TREE_Z
        p.add["items"].append(rec)
    p.log.append(f"деревьев убрано {len(old_trees)}, поставлено {len(fixed)} (X {fixed})")

    # 6. остановка: павильон открытой стороной к дороге (набор: задняя стена по −Z, вход по +Z), скамья, урна; ларьки рядом
    p.put("bus_stop", -45.0, -39.0, 0.0)
    p.put("bench", -39.0, -38.7, 0.0)
    p.drop_items(["m:U01_04"], [-48.5, -40.5, -46.5, -37.0])      # три дорожных конуса, попадавшие под павильон
    kiosks = [it for it in p.base()["filler"]["items"] if it[0] == "kiosk" and abs(it[1] + 50.0) < 0.1]
    p.drop_items(["kiosk"], [-50.1, -45.5, -49.9, -39.2])
    for i, rec in enumerate(sorted(kiosks, key=lambda it: it[2])):
        r = list(rec)
        r[1], r[2], r[3] = round(-41.0 + 3.4 * i, 2), -42.9, 0.0   # ряд вдоль тротуара, окна на улицу; проход БЦ 11 / банк (X −57…−46) свободен
        p.add["items"].append(r)

    # 7. трансформаторные с разделительной — в служебный проезд за первой линией; мешающие машины убрать
    p.move_item("ktp", -96.0, -15.65, -80.0, -64.7)
    p.move_item("ktp", -170.0, -15.65, -134.0, -64.7)
    for kit, x, z in (("m:U14_01", -79.43, -64.3), ("car_wreck", -80.12, -66.58), ("m:U14_01", -134.33, -64.3)):
        p.drop_item(kit, x, z)

    # 8. урны и тумба из середины тротуара — в полосу у бордюра; урна остановки у павильона
    p.move_item("m:U02_05", -146.0, -41.67, -146.0, STRIP_Z)
    p.move_item("m:U05_04", -94.0, -41.67, -94.0, STRIP_Z)
    p.move_item("m:U02_05", -42.0, -41.67, -37.0, -38.6)         # урна остановки рядом со скамьёй
    p.move_item("m:U05_04", -16.0, -41.67, -16.0, STRIP_Z)
    p.move_item("ad_column", -80.0, -43.32, -81.5, STRIP_Z)

    # переход через проспект на X −126: он начинается на новой кромке — светофор, знак, плиты, полусферы на 2,5 м южнее
    for kit, x, z in (("m:U15_02", -130.0, -36.14), ("m:U06_02", -132.5, -37.46), ("signal_arm", -132.5, -37.13)):
        p.move_item(kit, x, z, x, z + (NEW_EDGE - CURB_Z))
    for x in (-126.6, -126.0, -125.4):
        p.move_item("m:U05_05", x, -37.13, x, -37.13 + (NEW_EDGE - CURB_Z))
    for x in half_x:
        p.move_item("half_sphere", x, -35.98, x, -35.98 + (NEW_EDGE - CURB_Z))
    return p


# ------------------------------------------------------------------ этап 2: тылы (лист 5, поз. 3–6, 16–18)
SLOT_W = 2.5                        # ширина места
MARK_W, MARK_H = 0.1, 0.02          # разметка мест: как в паркинге −1 (полоса 0,1 × 0,02)
LOT_T = 0.05                        # толщина покрытия стоянки
CAR_JITTER_X, CAR_JITTER_Z, CAR_JITTER_YAW = 0.12, 0.2, 6.0   # «брошенная» стоянка: лёгкий разброс; 2,5 − 2·0,12 > 2,2 м между центрами
FILL = 0.6                          # заполнение рядов


def _slots(x0: float, x1: float) -> list[float]:
    """Центры мест по оси X на отрезке x0…x1 (целое число мест по 2,5 м от x0)."""
    n = int((x1 - x0) / SLOT_W + 1e-6)
    return [x0 + SLOT_W * (i + 0.5) for i in range(n)]


def _marks(p: "Patch", x0: float, x1: float, zc: float, depth: float = 4.9) -> int:
    """Поперечные линии разметки мест на отрезке x0…x1 (по оси Z — от zc − depth/2 до zc + depth/2)."""
    n = int((x1 - x0) / SLOT_W + 1e-6)
    for i in range(n + 1):
        p.box(x0 + SLOT_W * i, LOT_T + MARK_H / 2.0, zc, MARK_W, MARK_H, depth, "stripe", 0.0, False)
    return n + 1


def stage_2_backs() -> Patch:
    import random
    rng = random.Random(20261111)
    p = Patch("2_backs", BASE_REV_2)
    items = p.base()["filler"]["items"]
    svc0, svc1 = N.SERVICE                     # −66.5, −59.3
    rows = N.LOT_ROWS                          # [(−71.8, −66.5), (−84.9, −79.6)]
    row_z = [(a + b) / 2.0 for a, b in rows]   # центры рядов
    aisle_z = (rows[0][0] + rows[1][1]) / 2.0  # ось проезда между рядами: −75.7
    lot_zs = (-86.3, svc0)                     # покрытие стоянок −86.3…−66.5 (северный край прежний)

    # --- 3. въезд во двор: проезжая часть и тротуары вместо drive_e / drive_w
    p.remove["pieces"].append({"list": "surfaces", "id": "drive_e", "rect": [-114.0, -153.0, -108.0, -46.0]})
    p.remove["pieces"].append({"list": "surfaces", "id": "drive_w", "rect": [-122.0, -116.0, -113.0, -46.0]})
    d0, d1 = N.DRIVE
    walk_t = 0.08
    p.surface("drive_road", "road", d0, -152.8, d1, -46.95, 0.0, 0.08)
    p.surface("drive_walk_w", "walk", d0 - 3.0, -113.3, d0, -46.95, 0.0, walk_t)
    p.surface("drive_walk_e", "walk", d1, -113.3, d1 + 4.2, -46.95, 0.0, walk_t)
    # шлагбаум поперёк проезда (стойка у западной кромки, стрела на восток, масштаб 1,3 = ширина проезда) и будка у тротуара
    bar_z = -62.6
    p.put("barrier_arm", d0 + 0.25, bar_z, 90.0, 1.3)
    p.put("booth", d0 - 1.5, bar_z, 0.0)
    n_bol = p.drop_items(["m:U02_04"], [-121.0, -33.5, -111.0, -32.3])
    p.log.append(f"въезд: столбиков этапа 1 на кромке убрано {n_bol}")
    # трансформаторная у (−120; −131,3) стояла на кромке проезда — на запад от проезда
    p.move_item("ktp", -120.0, -131.3, -123.8, -131.3)

    # --- 1. служебный проезд и стоянка: покрытия
    p.remove["pieces"].append({"list": "surfaces", "id": "lot_w", "rect": [-197.0, -87.0, -121.0, -61.0]})
    p.remove["pieces"].append({"list": "surfaces", "id": "lot_e", "rect": [-109.0, -87.0, -45.0, -61.0]})
    lots = N.LOTS_X                            # [(−196, −123), (−108, −46)]
    for name, (x0, x1) in zip(("w", "e"), lots):
        p.surface(f"lot_{name}", "parking", x0, lot_zs[0], x1, lot_zs[1], 0.0, LOT_T)
        p.surface(f"service_{name}", "road", x0, svc0, x1, svc1, 0.0, LOT_T)
    n_marks = 0
    slot_xs: list[list[float]] = [[], []]      # центры мест по рядам (оба участка)
    for (x0, x1) in lots:
        for r, zc in enumerate(row_z):
            n_marks += _marks(p, x0, x1, zc)
            slot_xs[r] += _slots(x0, x1)
    p.log.append(f"разметка стоянок: линий {n_marks}, мест {len(slot_xs[0])} + {len(slot_xs[1])}")

    # --- 2. машины стоянок — по местам двух рядов (кит m:U14_01: машины на поверхности; «car*» с подъёмом −7,3 — паркинг −1, не трогаем)
    rect = [-197.0, -90.0, -45.0, -58.5]
    cars = [list(it) for it in items if it[0] == "m:U14_01" and rect[0] <= it[1] <= rect[2] and rect[1] <= it[2] <= rect[3]]
    p.drop_items(["m:U14_01"], rect)
    models = [c[8] for c in cars]
    by_row: list[list[list]] = [[c for c in cars if c[2] > -75.0], [c for c in cars if c[2] <= -75.0]]
    target = [int(round(len(slot_xs[r]) * FILL)) for r in range(2)]
    taken: list[set[int]] = [set(), set()]
    final: list[tuple] = []
    for r in range(2):
        for c in sorted(by_row[r], key=lambda c: c[1]):
            # ближайшее свободное место к прежнему X
            order = sorted((i for i in range(len(slot_xs[r])) if i not in taken[r]), key=lambda i: abs(slot_xs[r][i] - c[1]))
            taken[r].add(order[0])
            final.append((r, order[0], c[8], False))
        while len(taken[r]) < target[r]:
            i = rng.randrange(len(slot_xs[r]))
            if i in taken[r]:
                continue
            taken[r].add(i)
            final.append((r, i, rng.choice(models), True))
    n_old = sum(1 for f in final if not f[3])
    for r, i, model, new in final:
        x = slot_xs[r][i] + rng.uniform(-CAR_JITTER_X, CAR_JITTER_X)
        z = row_z[r] + rng.uniform(-CAR_JITTER_Z, CAR_JITTER_Z)
        yaw = (0.0 if r == 0 else 180.0) + rng.uniform(-CAR_JITTER_YAW, CAR_JITTER_YAW)
        p.put("m:U14_01", x, z, yaw, 1.0, 0.0, -1, 0.0, model)
    all_slots = len(slot_xs[0]) + len(slot_xs[1])
    p.log.append(f"машины стоянок: было {len(cars)}, переставлено {n_old}, добавлено {len(final) - n_old}, итого {len(final)} "
                 f"из {all_slots} мест ({100 * len(final) // all_slots} %)")

    # фонари, кадки, вехи и знаки стоянок — на границу служебного проезда и ряда 1 (Z −66.5), а не на ось проезда между рядами,
    # где они мешают проезду (исправление после приёмки этапа 2); лежачие полицейские (m:U06_01) остаются на проезде
    # на оси; там, где у кромки стоит бак или трансформаторная, вещь сдвинута по X на 3 м
    blockers = [bx + dx for bx in (-185.0, -150.0, -100.0, -66.0) for dx in (-1.75, 1.75)] + [-80.0, -134.0]
    moved = 0
    for kit in ("m:U12_03", "m:U02_02", "m:U06_01", "m:U07_04", "m:U03_03"):
        for it in items:
            if it[0] == kit and -197 <= it[1] <= -45 and -80 <= it[2] <= -68:
                if kit == "m:U06_01":
                    p.move_item(kit, it[1], it[2], it[1], aisle_z)
                    continue
                nx = it[1]
                if any(abs(nx - b) < 1.6 for b in blockers):
                    nx += 3.0
                p.move_item(kit, it[1], it[2], nx, svc0)
                moved += 1
    p.log.append(f"вещей стоянок на границу проезда и ряда 1 (Z {svc0}): {moved}")

    # контейнерные площадки: по два бака у северной кромки проезда, рядом мусор у двух из них
    for bx in (-185.0, -150.0, -100.0, -66.0):
        for dx in (-1.75, 1.75):
            p.put("m:R02", bx + dx, -65.2, 0.0)
    p.put("trash_pile", -181.0, -64.3, 40.0, 0.8)
    p.put("trash_pile", -96.0, -64.3, 200.0, 0.8)

    # --- 4. вывески первых этажей «Панорамы» на южных фасадах
    names = [("продукты", "салон красоты"), ("стоматология", "ремонт обуви"), ("зоотовары", "пункт выдачи"), ("нотариус", "химчистка")]
    low_ac = [it[1] for it in items if it[0] == "ac_unit" and -200 <= it[1] <= -40 and abs(it[2] + 87.1) < 0.2 and it[5] < 6.0]
    face_z = round(N.PAN_Z[1] + 0.4, 2)                   # −86.9
    for (x0, x1, _), pair in zip(N.PANORAMA, names):
        picks: list[float] = []
        for target_x in (x0 + 7.5, x1 - 7.5):
            cand = sorted((x0 + 4.0 + 0.5 * k for k in range(int((x1 - x0 - 8.0) / 0.5) + 1)), key=lambda x: abs(x - target_x))
            for x in cand:
                if all(abs(x - a) > 2.8 for a in low_ac) and all(abs(x - q) > 10.0 for q in picks):
                    picks.append(x)
                    break
        for x, text in zip(picks, pair):
            p.add["signs"].append({"at": [round(x, 2), 3.6, face_z], "size": 36.0, "text": text})
    p.log.append(f"вывесок {len(p.add['signs'])}")

    # --- 5. дворовый проезд до Банковского переулка (съезд через тротуар переулка X 17,5…21)
    yz0, yz1 = N.YARD_ROAD
    p.surface("yard_road_e", "road", -42.0, yz0, 17.5, yz1, 0.0, 0.08)
    p.surface("yard_road_e2", "road", 17.5, yz0, 21.0, -149.8, 0.0, 0.08)
    p.surface("yard_cross", "road", 17.5, -149.8, 21.0, yz1, 0.0, 0.17)
    p.move_item("m:R02", 19.1, -146.8, 19.1, -136.6)
    p.move_item("tree_birch", 18.9, -146.0, 18.9, -133.0)

    # --- 6. служебная стоянка за банком
    bx0, bx1, bz0, bz1 = -40.0, -8.0, -143.0, -103.0
    p.surface("bank_lot", "parking", bx0, bz0, bx1, bz1, 0.0, LOT_T)
    bank_rows = [(-143.0, -137.7, 0.0), (-124.6, -119.3, 180.0), (-119.3, -114.0, 0.0)]
    bank_slots: list[tuple[float, float, float]] = []
    nm = 0
    for a, b, yaw in bank_rows:
        zc = (a + b) / 2.0
        nm += _marks(p, bx0, bx1, zc)
        for x in _slots(bx0, bx1):
            bank_slots.append((x, zc, yaw))
    pool = list(dict.fromkeys(models))
    for (x, zc, yaw) in rng.sample(bank_slots, 9):
        p.put("m:U14_01", x + rng.uniform(-CAR_JITTER_X, CAR_JITTER_X), zc + rng.uniform(-CAR_JITTER_Z, CAR_JITTER_Z),
              yaw + rng.uniform(-CAR_JITTER_YAW, CAR_JITTER_YAW), 1.0, 0.0, -1, 0.0, rng.choice(pool))
    p.log.append(f"стоянка за банком: линий {nm}, мест {len(bank_slots)}, машин 9")
    p.move_item("container20", -28.0, -137.3, -11.0, -132.5, 90.0)
    p.move_item("trash_pile", -30.0, -121.3, -38.6, -105.4)
    p.move_item("bags", -28.8, -120.5, -37.4, -104.6)

    # --- 7. ЦТП с котельной и три трубы; грузовик — на служебную стоянку
    p.add_buildings.append({"id": "CTP", "parent": "East", "at": [5.5, -129.0], "footprint": [19.0, 14.0], "floors": 1,
                            "story_height": 6.0, "label": "ЦТП и котельная квартала (закрыто)", "kind": "mass"})
    for x in (9.0, 11.5, 14.0):
        p.box(x, 9.0, -119.5, 1.4, 18.0, 1.4, "rust", 0.0, True)
    p.move_item("truck", 2.0, -122.3, -18.0, -108.5)
    return p


# ------------------------------------------------------------------ этап 3: первая линия (лист 5, поз. 2)
BASE_REV_3 = "44f6a481"           # коммит этапа 2 — основа этапов 3 и 4
UP_Y = 4.175                      # низ второго этажа павильонов первой линии (как у их стен и плит)
ROOF_Y = 8.025                    # верх плиты крыши павильонов


def stage_3_frontline() -> Patch:
    p = Patch("3_frontline", BASE_REV_3)
    fz, bz = N.FACADE, N.BACK     # −48.3, −59.3
    # 1. перемычка аптека — «Modus»: объём X −146…−143 на втором этаже, под ним проход 3 м; высоты — как у соседних павильонов
    bx0, bx1 = -146.0, -143.0
    p.slab("bridge_floor", [bx0, bz, bx1, fz], UP_Y, 0.3, "slab")
    p.slab("bridge_roof", [bx0 + 0.2, bz - 0.2, bx1 - 0.2, fz + 0.2], ROOF_Y, 0.25, "slab")   # между парапетами соседних крыш
    win = [((bx0 + bx1) / 2.0, 1.4, 2.3, 0.9)]
    for z in (fz, bz):
        p.wall_x(z, bx0, bx1, UP_Y, 3.6, win, 0.25, "wall")
    p.wall(bx0 + 0.2, bz - 0.2, bx1 - 0.2, bz, ROOF_Y, ROOF_Y + 1.0, "concrete")     # парапет крыши, как у соседей
    p.wall(bx0 + 0.2, fz, bx1 - 0.2, fz + 0.2, ROOF_Y, ROOF_Y + 1.0, "concrete")
    # 2. щель пекарня — БЦ 11: закрыта по обоим фасадам на всю высоту
    for z in (fz, bz):
        p.wall_x(z, -94.0, -92.2, 0.0, ROOF_Y, (), 0.25, "wall")
    # 3. перемычка-ворота над въездом во двор и надпись на ней с юга
    p.box(-115.5, 5.2, -49.2, 15.0, 1.2, 1.5, "concrete")
    p.add["signs"].append({"at": [-115.5, 5.2, -48.1], "size": 40.0, "text": "двор ЖК «Панорама»"})
    # 4. контейнер на проезжей части переулка (22,6; −118) стоял в полосе маршрута «за «Вершиной» → к насыпи» (прямая от (131; −131)
    # к (12; −114) задевает его угол): проверка проходила только за счёт случайных обходов ходока — он на 4 м севернее, вне полосы
    p.move_item("container20", 22.6, -118.0, 22.6, -125.0)
    return p


# ------------------------------------------------------------------ этап 4: автомойка «Блеск» (лист 8)
def stage_4_wash() -> Patch:
    p = Patch("4_wash", BASE_REV_3)
    x0, x1, z0, z1 = N.WASH                       # 6.8, 17.0, −92, −66
    H = N.WASH_H                                  # 5.0
    T = 0.25
    cx0, cx1, cz0, cz1 = x0 + T / 2, x1 - T / 2, z0 + T / 2, z1 - T / 2     # оси наружных стен: грани — ровно по контуру
    tx0 = N.TUNNEL[0]                             # 11.2 — стена между тоннелем и боковым блоком
    gate_x = (tx0 + x1) / 2.0                     # 14.1
    DOOR_W, DOOR_H = 1.17, 2.415

    # --- 1. что убрать: прежняя мойка, контейнеры за ней, старая надпись, берёзы и столбики переулка
    p.remove["nodes"].append("CarWash")
    p.log.append("контейнеров убрано %d" % p.drop_items(["container20"], [11.0, -103.0, 13.0, -101.5]))
    p.remove["pieces"].append({"list": "signs", "rect": [11.5, -77.5, 12.5, -76.3]})
    p.log.append("берёз убрано %d" % (p.drop_items(["tree_birch"], [18.5, -62.5, 19.3, -61.5])
                                       + p.drop_items(["tree_birch"], [18.5, -104.5, 19.3, -103.5])))
    p.log.append("столбиков устья убрано %d" % p.drop_items(["m:U02_04"], [21.5, -57.9, 29.5, -56.9]))

    # --- 2. покрытие площадок и съезды через западный тротуар переулка
    p.surface("wash_road", "road", 6.0, -121.5, 17.5, -59.3, 0.0, 0.08)
    p.surface("wash_cross_n", "road", 17.5, -104.0, 21.0, -96.0, 0.0, 0.17)
    p.surface("wash_cross_s", "road", 17.5, -66.0, 21.0, -60.0, 0.0, 0.17)

    # --- 3. здание: наружные стены с воротами и дверями, внутренняя стена, перегородки, крыша с парапетом
    p.wall_x(cz1, cx0 - T / 2, cx1 + T / 2, 0.0, H - 0.3, [(9.0, 1.6, DOOR_H), (gate_x, 4.0, 3.6)], T, "wall")       # южная
    p.wall_x(cz0, cx0 - T / 2, cx1 + T / 2, 0.0, H - 0.3, [(9.0, DOOR_W, DOOR_H), (gate_x, 4.0, 3.6)], T, "wall")    # северная
    p.wall_z(cx0, cz0, cz1, 0.0, H - 0.3, (), T, "wall")                                                      # западная
    wins = [(z0 + 0.6 + 1.2 + 3.0 * i, 2.4, 3.3, 0.9) for i in range(8)]                                    # «стекло» — окна без стёкол
    p.wall_z(cx1, cz0, cz1, 0.0, H - 0.3, wins, T, "wall")
    doors = [(-70.0, DOOR_W, DOOR_H), (-76.5, DOOR_W, DOOR_H), (-81.0, DOOR_W, DOOR_H), (-87.5, DOOR_W, DOOR_H)]
    p.wall_z(tx0, cz0, cz1, 0.0, H - 0.3, doors, T, "wall")
    for z in (-74.0, -79.0, -83.0):
        p.wall_x(z, cx0, tx0, 0.0, H - 0.3, (), 0.15, "wall")
    p.slab("wash_roof", [x0, z0, x1, z1], H, 0.3, "slab")
    for r in ([x0, z0, x1, z0 + 0.2], [x0, z1 - 0.2, x1, z1], [x0, z0, x0 + 0.2, z1], [x1 - 0.2, z0, x1, z1]):
        p.wall(r[0], r[1], r[2], r[3], H, H + 0.4, "wall")                              # парапет 0,4
    # портал мойки: две рамы на Z −89 и −83 по краям тоннеля; проезд 3,9 м между стойками
    for zz in (-89.0, -83.0):
        for xx in (12.0, 16.2):
            p.box(xx, 1.65, zz, 0.3, 3.3, 0.3, "steel")
        p.box(gate_x, 3.45, zz, 4.5, 0.3, 0.3, "accent")
    # оборудование: касса, баки, стеллаж
    p.box(8.0, 0.55, -71.5, 2.0, 1.1, 0.6, "accent")
    p.box(7.9, 0.9, -89.0, 1.2, 1.8, 1.2, "steel")
    p.box(7.9, 0.9, -85.5, 1.2, 1.8, 1.2, "steel")
    p.box(7.35, 1.0, -81.0, 0.6, 2.0, 3.2, "steel")
    p.box(7.35, 1.5, -80.2, 0.4, 0.4, 0.5, "accent")
    p.add["signs"].append({"at": [12.0, 5.6, -65.6], "size": 40.0, "text": "автомойка «Блеск»"})

    # --- 4. площадки: навес с пылесосами, шиномонтаж, стела
    vx0, vx1, vz0, vz1 = N.VACUUM
    p.slab("wash_canopy", [vx0, vz0, vx1, vz1], 3.4, 0.2, "slab")
    for xx, zz in ((vx0 + 0.2, vz0 + 0.2), (vx1 - 0.2, vz0 + 0.2), (vx0 + 0.2, vz1 - 0.2), (vx1 - 0.2, vz1 - 0.2)):
        p.box(xx, 1.6, zz, 0.2, 3.2, 0.2, "steel")
    p.box(9.0, 0.75, -101.0, 0.6, 1.5, 0.6, "accent")
    p.box(11.0, 0.75, -101.0, 0.6, 1.5, 0.6, "accent")
    sx0, sx1, sz0, sz1 = N.TIRE_SHOP
    p.put("container20", (sx0 + sx1) / 2.0, (sz0 + sz1) / 2.0, 90.0, 1.0, 0.0, -1, 0.0, "PC03_C20_BLUE")   # длинной стороной вдоль X
    p.add["signs"].append({"at": [(sx0 + sx1) / 2.0, 2.0, sz1 + 0.4], "size": 30.0, "text": "шиномонтаж"})
    p.box(8.0, 4.5, -60.4, 1.2, 9.0, 0.4, "accent")
    p.add["signs"].append({"at": [8.0, 6.5, -60.1], "size": 30.0, "text": "автомойка 24"})
    return p


# места лута мойки и убранная запись здания — данные плана, не узлы: правятся в data/blockouts/prospekt.json (идемпотентно, текстом,
# чтобы не менять остальное форматирование файла)
WASH_LOOT = [
    ([8.0, 0.08, -71.0], "register", "common", "автомойка «Блеск»: касса клиентской"),
    ([7.6, 0.08, -76.5], "cabinet", "common", "автомойка «Блеск»: шкафчик бытовки"),
    ([8.3, 0.08, -81.0], "crate", "common", "автомойка «Блеск»: стеллаж химии"),
    ([10.4, 0.08, -89.6], "crate", "common", "автомойка «Блеск»: ящик техпомещения"),
    ([10.0, 0.08, -109.4], "crate", "common", "шиномонтаж: ящик у контейнера"),
]


def plan_data_4() -> None:
    import re
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'  \{\n   "id": "CarWash",.*?\n  \},\n', "", text, count=1, flags=re.S)
    add = ""
    for at, kind, tier, note in WASH_LOOT:
        if note in text:
            continue
        add += (',\n  {\n   "at": [%s, %s, %s],\n   "kind": "%s",\n   "tier": "%s",\n   "note": "%s",\n   "yaw": 0.0\n  }'
                % (at[0], at[1], at[2], kind, tier, note))
    if add:
        i = text.index('"loot": [')
        j = text.index("\n ],", i)          # конец массива loot
        text = text[:j].rstrip("\n") + add + text[j:]
    path.write_text(text, encoding="utf-8", newline="\n")


STAGES = {"1_street": stage_1_street, "2_backs": stage_2_backs, "3_frontline": stage_3_frontline,
          "4_wash": stage_4_wash}


def main() -> None:
    names = sys.argv[1:] or ["1_street"]
    for name in names:
        if name not in STAGES:
            raise SystemExit(f"нет этапа {name}; есть: {', '.join(STAGES)}")
        p = STAGES[name]()
        path = p.save()
        if name == "4_wash":
            plan_data_4()
        print(f"{path}: убрать вещей {len(p.remove['items'])} правил, кусков {len(p.remove['pieces'])}, узлов {len(p.remove['nodes'])}; "
              + ", ".join(f"{k} {len(v)}" for k, v in p.add.items() if v))
        for line_ in p.log:
            print("  ", line_)


if __name__ == "__main__":
    main()
