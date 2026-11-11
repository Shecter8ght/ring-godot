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


# ------------------------------------------------------------------ этап 5a: банк «Капитал», участок
BASE_REV_5 = "ab71787a"           # коммит этапа 4 — основа этапа 5
BANK_UX0, BANK_UX1, BANK_UZ0, BANK_UZ1 = N.BU   # -40…-2, -95.3…-61.3


def _fence(p: "Patch", axis: str, c: float, a0: float, a1: float, gaps=()) -> int:
    """Секции bar_fence как у fence_line генератора: шаг 2,5 м, первая в a0 + 1,25."""
    n = 0
    a = a0 + 1.25
    while a < a1:
        if all(abs(a - g[0]) > g[1] * 0.5 + 1.2 for g in gaps):
            if axis == "x":
                p.put("bar_fence", a, c, 90.0)
            else:
                p.put("bar_fence", c, a, 0.0)
            n += 1
        a += 2.5
    return n


def stage_5a_bank_site() -> Patch:
    p = Patch("5a_bank_site", BASE_REV_5)
    # --- 1. забор: убрать южную линию западнее X −2 и западную южнее Z −61,3
    p.log.append("забора убрано: юг %d, запад %d" % (p.drop_items(["bar_fence"], [-44.0, -52.6, -2.05, -52.0]),
                                                    p.drop_items(["bar_fence"], [-43.2, -61.3, -42.8, -52.0])))
    # возврат по Z −61,3 от X −43 до −40 с калиткой 1,5 м у X −41,6: две короткие секции по сторонам разрыва (масштаб по длине)
    gate0, gate1 = -41.6 - 0.75, -41.6 + 0.75
    for a, b in ((-43.0, gate0), (gate1, -40.0)):
        p.put("bar_fence", (a + b) / 2.0, -61.3, 90.0, round((b - a) / 2.5, 3))
    n_east = _fence(p, "z", -2.0, -61.3, -52.3)
    p.log.append(f"забора добавлено: возврат Z −61,3 (2 секции с калиткой), возврат X −2 ({n_east} секций)")
    # --- 2. площадь: столбики по Z −52,8 с разрывом 3,2 м против входа (X −21), покрытие до тротуара, стела
    n_bol = 0
    for sign in (-1.0, 1.0):
        x = -21.0 + sign * 1.6
        while -40.0 - 0.01 <= x <= -2.0 + 0.01:
            p.put("bollard", x, -52.8, 0.0)
            n_bol += 1
            x += sign * 1.6
    p.log.append(f"столбиков {n_bol}")
    p.surface("bank_plaza_walk", "walk", -43.0, -52.3, 6.0, -46.95, 0.0, 0.15)
    p.box(-8.4, 1.3, -50.9, 1.2, 2.6, 0.3, "concrete")
    p.add["signs"].append({"at": [-8.4, 2.0, -50.6], "size": 30.0, "text": "банк «Капитал»"})
    # --- 3. бокс инкассации: стены 4,2, плита крыши, ворота 3,6 × 3,2 в южной стене (центр X −0,8)
    ax0, ax1, az0, az1 = N.ANNEX
    T = 0.25
    h = 4.2 - 0.3
    p.wall_x(az1 - T / 2, ax0, ax1, 0.0, h, [(-0.8, 3.6, 3.2)], T, "wall")        # южная с воротами
    p.wall_x(az0 + T / 2, ax0, ax1, 0.0, h, (), T, "wall")                        # северная
    p.wall_z(ax1 - T / 2, az0, az1, 0.0, h, (), T, "wall")                        # восточная
    p.slab("annex_roof", [ax0, az0, ax1, az1], 4.2, 0.3, "slab")
    # --- 4. наружная лестница: второй марш на север от площадки 2-го этажа до площадки 3-го
    p.remove["pieces"].append({"list": "walls", "rect": [-43.0, -78.0, -39.0, -77.0], "inside": [-42.8, -77.4, -39.9, -77.1],
                               "ymin": 4.4, "ymax": 5.6})
    p.stair((-41.6, 4.5, -77.3), (-41.6, 8.4, -85.1), 1.6, "concrete")
    p.box(-41.4, 8.28, -86.8, 2.6, 0.24, 3.4, "concrete")
    for k in range(6):                                                           # ступенчатое ограждение марша с запада
        za, zb = -77.3 - 1.3 * k, -77.3 - 1.3 * (k + 1)
        y_lo = 4.5 + 3.9 * (k + 1) / 6.0 - 0.3
        p.wall(-42.75, zb, -42.6, za, y_lo, y_lo + 1.3, "steel")
    p.wall(-42.75, -88.5, -42.6, -85.1, 8.4, 9.4, "steel")                       # площадка 3-го этажа: запад и север
    p.wall(-42.75, -88.65, -40.0, -88.5, 8.4, 9.4, "steel")
    # --- 5. задний двор: ДГУ и два бака
    p.box(-9.0, 1.2, -97.2, 6.0, 2.4, 2.4, "steel")
    p.put("m:R02", -35.0, -97.6, 0.0)
    p.put("m:R02", -32.4, -97.6, 0.0)
    return p


# ------------------------------------------------------------------ этап 5b: банк «Капитал», планировка
BASE_REV_5B = "6912a9b3"          # коммит этапа 5a
D_H = 2.415                       # высота дверного проёма (1,17 × 2,42 по правилу масштаба)
W_T = 0.15                        # толщина внутренних перегородок
B_Y = N.BY                        # 0, 4.5, 8.4, 12.3


def _rm_walls(p: "Patch", inside: list, ymin: float, ymax: float) -> None:
    p.remove["pieces"].append({"list": "walls", "rect": inside, "inside": inside, "ymin": ymin, "ymax": ymax})


def _rm_boxes(p: "Patch", inside: list, ymin: float, ymax: float) -> None:
    p.remove["pieces"].append({"list": "boxes", "rect": inside, "inside": inside, "ymin": ymin, "ymax": ymax})


def stage_5b_bank_plan() -> Patch:
    p = Patch("5b_bank_plan", BASE_REV_5B)
    x0, x1, z0, z1 = N.B1                                   # −38…−4, −93.3…−65.3
    Y0, Y1, Y2 = B_Y[0], B_Y[1], B_Y[2]
    h1 = 4.2                                                # высота стен 1-го этажа
    ix0, ix1 = x0 + 0.125, x1 - 0.125                       # внутренние грани наружных стен

    def wx(z, a, b, gaps=(), y0=Y0, h=h1, t=W_T):
        p.wall_x(z, a, b, y0, h, gaps, t, "wall")

    def wz(x, a, b, gaps=(), y0=Y0, h=h1, t=W_T):
        p.wall_z(x, a, b, y0, h, gaps, t, "wall")

    # ======================================================= 1-й этаж: что убрать
    _rm_walls(p, [-37.9, -89.1, -3.9, -65.0], 0.0, 4.25)                     # внутренние стены объёма (кроме линии Z −89,1 и севернее)
    _rm_boxes(p, [-37.9, -89.1, -4.1, -65.3], 0.0, 1.7)                      # касса, стойка, столы, скамьи, банкоматы
    p.drop_items(["bollard"], [-28.0, -75.6, -20.0, -75.0])
    # наружные стены — целиком заново (три стены, проёмы по DOORS_F1)
    _rm_walls(p, [-38.15, -65.5, -3.85, -65.1], 0.0, 4.25)                   # южная
    _rm_walls(p, [-4.15, -93.35, -3.85, -65.25], 0.0, 4.25)                  # восточная
    _rm_walls(p, [-38.15, -93.35, -37.85, -65.25], 0.0, 4.25)                # западная
    # плита первого этажа: тот же прямоугольник, к вырезу Л2 добавлен вырез Л3
    p.remove["pieces"].append({"list": "slabs", "id": "bank_f1", "rect": [-38.0, -93.3, -4.0, -65.3]})
    p.slab("bank_f1", [x0, z0, x1, z1], 0.0, 0.4, "walk", [[-14.8, -92.5, -6.6, -90.1], [-6.6, -78.2, -4.8, -72.3]])

    # ======================================================= 1-й этаж: наружные стены с новыми проёмами
    p.wall_x(z1, x0, x1, Y0, h1, [(-21.0, 2.4, 2.6), (-33.0, 1.6, D_H)] +
             Patch.windows(x0, x1, 3.0, 2.4, 0.4, 3.6, [(-21.0, 2.4), (-33.0, 1.6)]), 0.25, "wall")
    east_win = [w for w in Patch.windows(z0, z1, 4.0, 1.6, 2.2, 3.6, [(-85.0, 1.17)]) if w[0] - w[1] * 0.5 >= -80.3]
    p.wall_z(x1, z0, z1, Y0, h1, [(-85.0, 1.17, D_H)] + east_win, 0.25, "wall")
    p.wall_z(x0, z0, z1, Y0, h1, [(-91.2, 1.17, D_H)] + Patch.windows(z0, z1, 4.0, 1.6, 2.2, 3.6, [(-91.2, 1.17)]), 0.25, "wall")

    # ======================================================= 1-й этаж: перегородки (BANK_F1, DOORS_F1)
    wx(-78.3, ix0, -31.0)                                                    # управляющий | бэк-офис
    wx(-78.3, -18.0, ix1)                                                    # кабины касс, касса, касса пересчёта | зал, спуск
    wx(-70.3, ix0, -28.0)                                                    # управляющий | зона 24/7
    wx(-71.3, -11.0, ix1)                                                    # спуск | VIP
    wx(-68.3, -23.5, -18.5, [(-21.0, 2.4, 2.6)])                             # внутренняя дверь тамбура
    wz(-23.5, -68.3, z1 - 0.125)
    wz(-18.5, -68.3, z1 - 0.125)
    wx(-75.3, -18.0, -11.0, [(-16.2, 1.0, D_H), (-12.8, 1.0, D_H)])          # кабины касс: две двери в зал
    wz(-14.5, -78.3, -75.3)                                                  # перегородка между кабинами
    wz(-31.0, -78.3, -70.3, [(-74.0, 1.17, D_H)])                            # управляющий
    wz(-28.0, -70.3, z1 - 0.125, [(-67.8, 1.17, D_H)])                       # зона 24/7
    wx(-84.0, -24.0, -20.5, [(-21.0, 1.17, D_H)])                            # с/у | коридор
    wx(-83.3, -20.5, -11.0, [(-19.2, 1.17, D_H)])                            # комната персонала | коридор и касса
    wz(-24.0, -89.1, -78.3, [(-80.8, 1.17, D_H)])                            # бэк-офис | с/у, коридор (дверь добавлена: иначе коридор недоступен)
    wz(-20.5, -89.1, -83.3)                                                  # с/у | комната персонала
    wz(-18.0, -83.3, -75.3, [(-80.8, 1.17, D_H)])                            # коридор | касса; кабины
    wz(-11.0, -89.8, -78.3, [(-86.5, 1.17, D_H), (-81.0, 1.17, D_H)])        # персонал, касса | касса пересчёта
    wz(-11.0, -78.3, z1 - 0.125, [(-74.8, 1.6, D_H), (-68.3, 1.17, D_H)])    # зал | спуск, VIP
    # стойка операционистов по Z −78,3 (X −31…−18, высота 1,1) с проходом-калиткой у X −25,5
    for a, b in ((-31.0, -25.5 - 0.585), (-25.5 + 0.585, -18.0)):
        p.box((a + b) / 2.0, 0.55, -78.3, b - a, 1.1, 0.6, "accent")
    for cx in (-29.5, -22.5, -19.2):
        p.box(cx, 1.25, -78.0, 1.2, 0.5, 0.04, "dark", 0.0, False)           # стёкла окон кассиров
    # лестница Л3: марш вдоль восточной стены на X −5,7, вырез в плите, ограждение с запада
    p.stair((-5.7, 0.0, -72.3), (-5.7, -3.2, -78.0), 1.6, "concrete")
    p.box(-6.7, 0.5, -75.25, 0.1, 1.0, 5.9, "steel")
    # мебель 1-го этажа
    for bx in (-36.3, -34.6, -30.8):
        p.box(bx, 0.75, -69.75, 0.7, 1.5, 0.7, "steel")                      # банкоматы
    p.box(-34.5, 0.38, -75.0, 1.8, 0.75, 0.9, "accent")                      # управляющий
    for bx, bz in ((-27.0, -72.5), (-15.5, -72.5), (-15.5, -70.0)):
        p.box(bx, 0.23, bz, 2.6 if bx < -20 else 0.6, 0.45, 0.6 if bx < -20 else 2.6, "accent")   # скамьи зала
    p.box(-7.5, 0.38, -68.3, 2.4, 0.75, 1.0, "accent")                       # VIP
    p.box(-10.3, 0.38, -77.2, 1.0, 0.75, 0.6, "accent")                      # стол поста у двери в спуск
    for bx, bz in ((-35.5, -82.5), (-31.5, -82.5), (-35.5, -86.0), (-31.5, -86.0)):
        p.box(bx, 0.38, bz, 1.6, 0.75, 0.8, "accent")                        # бэк-офис
    p.box(-16.5, 0.38, -86.0, 2.0, 0.75, 1.0, "accent")                      # комната персонала
    p.box(-14.5, 0.38, -79.4, 1.6, 0.75, 0.8, "accent")                      # касса
    p.box(-8.0, 0.38, -83.5, 3.0, 0.75, 1.2, "accent")                       # касса пересчёта: стол
    p.box(-8.0, 0.9, -78.9, 3.0, 1.8, 0.5, "steel")                          # и стеллаж

    # ======================================================= −1
    _rm_walls(p, [-12.2, -79.4, -11.8, -65.2], -3.25, -0.35)                 # стена X −12
    _rm_boxes(p, [-20.9, -89.3, -4.1, -65.3], -3.25, -2.0)                   # пересчёт и стол поста
    p.drop_items(["deposit_wall"], [-16.7, -68.1, -16.3, -67.7])
    p.put("deposit_wall", -16.5, -66.1, 180.0, 1.0, -3.2)                    # ячейки вдоль южной стены депозитария
    p.put("deposit_wall", -11.7, -72.8, 90.0, 1.0, -3.2)                     # и вдоль восточной (между дверями)
    yb, hb = N.BASE_Y, -N.BASE_Y - 0.4                                       # −3,2; высота 2,8
    wz(-11.0, -79.3, -65.3, [(-78.5, 1.17, D_H), (-68.0, 1.17, D_H)], yb, hb)   # депозитарий | спуск Л3, кабины клиентов
    wx(-71.3, -11.0, -4.0, (), yb, hb)                                       # спуск Л3 | кабины клиентов (без двери)
    wz(-14.0, -89.8, -79.3, [(-85.0, 1.17, D_H)], yb, hb)                    # пост охраны | щитовая
    p.box(-18.0, yb + 0.38, -86.5, 2.0, 0.75, 0.8, "accent")                 # стол поста охраны
    for bx in (-12.0, -9.5, -7.0):
        p.box(bx, yb + 1.0, -89.3, 0.6, 2.0, 0.8, "steel")                   # шкафы щитовой
    p.box(-7.5, yb + 0.38, -68.3, 3.0, 0.75, 1.0, "accent")                  # стол пересчёта в кабинах клиентов

    # ======================================================= 2-й и 3-й этажи
    for (y0, h, lvl) in ((Y1, 3.6, 2), (Y2, 3.55, 3)):
        gaps_n = [(-36.0, 1.0, D_H)] if lvl == 2 else [(-39.25, 1.0, D_H), (-36.3, 1.0, D_H)]
        wx(-83.3, -40.0 + 0.125, -28.0, gaps_n, y0, h)
        wz(-28.0, -89.1, -83.3, (), y0, h)
        wz(-34.0, -89.1, -83.3, [(-86.0, 1.0, D_H)] if lvl == 2 else (), y0, h)
        if lvl == 2:
            gaps_c = [(-39.25, 1.0, D_H), (-36.5, 1.0, D_H), (-29.0, 1.17, D_H), (-21.0, 1.17, D_H), (-14.5, 1.17, D_H), (-6.5, 1.17, D_H)]
        else:
            gaps_c = [(-32.0, 1.6, D_H), (-18.5, 1.17, D_H), (-7.5, 1.17, D_H)]
        wx(-80.7, -40.0 + 0.125, -2.0 - 0.125, gaps_c, y0, h)
        for px in ((-38.5, -34.0, -24.0, -18.0, -11.0) if lvl == 2 else (-24.0, -13.0)):
            wz(px, -80.7, -75.3, (), y0, h)
    # вестибюль у западной двери 3-го этажа: Z −89,1…−83,3, перегородка X −38,5
    wz(-38.5, -89.1, -83.3, (), Y2, 3.55)
    # 2-й этаж: перегородка Z −75,3 начинается за вестибюлем (X −40…−38,5 — проход из вестибюля в офис)
    p.remove["pieces"].append({"list": "walls", "rect": [-40.05, -75.4, -30.75, -75.2], "inside": [-40.05, -75.4, -30.75, -75.2],
                               "ymin": 4.45, "ymax": 8.75})
    p.wall_x(-75.3, -38.5, -30.8, Y1, 4.2, (), 0.16, "wall")
    # 3-й этаж: стена X −14 убрана, вместо неё X −22 (Z −75,3…−61,3); стол зала сдвинут
    _rm_walls(p, [-14.1, -75.4, -13.9, -61.2], 8.35, 12.0)
    wz(-22.0, -75.3, -61.3, (), Y2, 3.55)
    _rm_boxes(p, [-26.1, -69.6, -17.9, -67.0], 8.3, 9.3)
    p.box(-12.0, 8.78, -68.3, 8.0, 0.75, 2.4, "accent")                      # зал совещаний
    p.box(-31.0, 8.78, -68.0, 2.4, 0.75, 1.1, "accent")                      # кабинет директора
    p.box(-37.0, 8.78, -77.9, 1.8, 0.75, 0.8, "accent")                      # приёмная
    # 3-й этаж: новая дверь в западной наружной стене на Z −86,5 (окно Z −88,8…−86,8 и простенок пересобираются)
    p.remove["pieces"].append({"list": "walls", "rect": [-40.15, -88.82, -39.85, -85.78], "inside": [-40.15, -88.82, -39.85, -85.78],
                               "ymin": 8.35, "ymax": 12.0})
    p.wall_z(-40.0, -88.8, -85.8, Y2, 3.55, [(-88.0, 1.6, 2.7, 0.9), (-86.5, 1.17, D_H)], 0.24, "wall")
    # мебель 2-го этажа по комнатам
    p.box(-26.5, Y1 + 0.38, -77.9, 1.6, 0.75, 0.8, "accent")                 # кухня
    for bx in (-23.0, -19.2):
        p.box(bx, Y1 + 0.9, -77.5, 0.8, 1.8, 0.8, "dark")                    # ИТ
    p.box(-14.5, Y1 + 0.65, -77.5, 0.8, 1.3, 0.8, "steel")                   # копир.
    p.box(-3.6, Y1 + 0.38, -77.9, 1.5, 0.75, 0.9, "accent")                  # нач. отдела
    return p


# --- данные плана (data/blockouts/prospekt.json): места лута банка в новые комнаты и два маршрута проверки
LOOT_MOVES = [
    ([-33.0, 0.0, -80.7], "окно операциониста", [-29.5, 0.0, -79.4]),
    ([-23.0, 0.0, -80.7], "окно операциониста", [-22.5, 0.0, -79.4]),
    ([-18.0, 0.0, -80.7], "окно операциониста", [-19.2, 0.0, -79.4]),
    ([-37.0, 0.0, -68.3], "кассета банкомата", [-36.3, 0.0, -69.0]),
    ([-18.5, 0.0, -86.8], "сейф кассы", [-12.0, 0.0, -82.4]),
    ([-5.0, 0.0, -79.8], "сейф управляющего", [-36.8, 0.0, -76.6]),
    ([-30.0, 0.0, -73.8], "зал ожидания", [-29.5, 0.0, -73.0]),
    ([-25.0, 4.5, -67.3], "офис 2-го этажа", [-25.0, 4.5, -69.6]),
    ([-4.0, 8.4, -92.3], "сейф директора (ключ)", [-38.7, 8.4, -62.6]),
    ([-34.0, 8.4, -65.3], "зал 3-го этажа", [-6.0, 8.4, -64.0]),
    ([-8.0, -3.2, -75.3], "пересчёт: пачки денег", [-7.5, -3.2, -66.6]),
    ([-19.0, -3.2, -86.7], "пост охраны хранилища", [-18.0, -3.2, -85.4]),
]
ROUTE_BANK_ROOF = [[-21.0, -50.3], [-21.0, -64.3], [-21.0, -69.5], [-21.0, -72.0], [-25.5, -73.5], [-25.5, -80.0], [-28.7, -82.0],
                   [-28.7, -88.6], [-28.7, -89.9], [-28.6, -90.3], [-37.8, -90.3], [-38.0, -92.3], [-28.6, -92.3], [-28.6, -90.5],
                   [-37.8, -90.5], [-37.6, -88.5], [-30.0, -81.3]]
ROUTE_DIG = [[-110.6, -127.3], [-110.6, -149.3], [-47.1, -149.3], [-47.1, -145.8], [-47.1, -131.3], [-47.1, -117.3], [-47.1, -91.3],
             [-47.1, -74.3], [-37.0, -74.3], [-30.0, -76.8], [-22.5, -77.3], [-22.4, -83.3], [-17.8, -84.2], [-20.0, -83.3], [-22.4, -83.3],
             [-22.4, -91.5], [-16.6, -91.6], [-15.0, -91.3], [-6.4, -91.3], [-5.4, -89.3], [-5.4, -88.0], [-9.0, -86.5], [-14.0, -85.5],
             [-19.2, -84.5], [-19.2, -82.0], [-22.0, -80.8], [-25.0, -80.8], [-25.5, -77.0], [-25.5, -74.0]]
ROUTE_LABELS = {"bank_roof": "банк: калитка → зал → за стойку → ядро Л1 → три марша → крыша",
                "dig_to_vault": "двор → восточный спуск → паркинг −1 → подкоп → хранилище → предкладовая → пост → Л2 → первый этаж → зал"}


def _num(v: float) -> str:
    return repr(float(v))


def plan_data_5b() -> None:
    import re
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = path.read_text(encoding="utf-8")
    for old, note, new in LOOT_MOVES:
        rx = re.compile(r'"at": \[%s, %s, %s\],(\n   "kind": "[a-z]+",\n   "tier": "[a-z]+",\n   "note": "%s")' %
                        (re.escape(_num(old[0])), re.escape(_num(old[1])), re.escape(_num(old[2])), re.escape(note)))
        text, n = rx.subn(lambda m: '"at": [%s, %s, %s],%s' % (_num(new[0]), _num(new[1]), _num(new[2]), m.group(1)), text, count=1)
        if n == 0 and ('"at": [%s, %s, %s]' % (_num(new[0]), _num(new[1]), _num(new[2]))) not in text:
            raise SystemExit(f"лут «{note}» не найден ни на старом, ни на новом месте")
    for rid, pts in (("bank_roof", ROUTE_BANK_ROOF), ("dig_to_vault", ROUTE_DIG)):
        rx = re.compile(r'(\{\n   "id": "%s",\n   "label": )"[^"]*"(,\n   "max_open_m": 0.0,\n   "points": \[\n).*?(\n   \])' % rid, re.S)
        body = ",\n".join("    [%s, %s]" % (_num(a), _num(b)) for a, b in pts)
        text, n = rx.subn(lambda m: m.group(1) + '"%s"' % ROUTE_LABELS[rid] + m.group(2) + body + m.group(3), text, count=1)
        if n != 1:
            raise SystemExit(f"маршрут {rid} не найден")
    path.write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ этап 6a: «Вершина», объёмы и двор
import prospekt_vershina_plan as V  # noqa: E402  (чертежи «Вершины»; при импорте ничего не пишет)

BASE_REV_6 = "f5d6b3f6"          # коммит этапа 5b — основа этапа 6
TEMP_SUPPORT_MAT = "steel"        # временные опоры 6a (в 6b их заменят стены): колонны галереи — "concrete"


def _flat(bid: str, rect: tuple, lift: float, floors: int, label: str, balconies: bool = False, glass: bool = False,
          story: float = V.STORY) -> dict:
    cx, cz = (rect[0] + rect[1]) / 2.0, (rect[2] + rect[3]) / 2.0
    return {"id": bid, "parent": "East", "at": [round(cx, 3), round(cz, 3)], "footprint": [round(rect[1] - rect[0], 3), round(rect[3] - rect[2], 3)],
            "floors": floors, "story_height": story, "label": label, "kind": "flats", "lift": round(lift, 3), "script": "flats",
            "extra": {"open_floors": 0, "balconies": balconies, "glass_bands": glass}}


def vershina_buildings() -> list[dict]:
    """Узлы башен, стилобата, кафе двора, въезда и двух башен за забором — одним списком (патч 6a и данные плана)."""
    T = {t["key"]: t for t in V.TOWERS}
    a, b, c, d = T["А"], T["Б"], T["В"], T["Г"]
    out: list[dict] = []
    # А: 38 этажей на стилобате (подъём 18) и верх 6 этажей
    out.append(_flat("Vershina_T1", a["rect"], 18.0, 38, "ЖК «Вершина», башня А — пластина, 44 этажа", False, True))
    out.append(_flat("Vershina_T1_Top", a["top"]["rect"], 18.0 + 38 * V.STORY, 6, "башня А — верх (сужение)", False, True))
    # Б: основание 2 этажа на земле, 46 этажей, верх 12
    bx = b["rect"]
    out.append({"id": "Vershina_T2_Base", "parent": "East", "at": [(bx[0] + bx[1]) / 2.0, (bx[2] + bx[3]) / 2.0], "footprint": [30.0, 30.0],
                "floors": 2, "story_height": 4.65, "label": "башня Б — основание, 2 этажа (закрыто)", "kind": "mass", "lift": 0.0, "script": "build"})
    out.append(_flat("Vershina_T2", bx, 9.3, 46, "ЖК «Вершина», башня Б — самая высокая, 58 этажей", False, True))
    out.append(_flat("Vershina_T2_Top", b["top"]["rect"], 9.3 + 46 * V.STORY, 12, "башня Б — верх (сужение)", False, True))
    # В: две половины
    cr, lo = c["rect"], c["low"]
    west = (cr[0], lo["rect"][0], cr[2], cr[3])
    out.append(_flat("Vershina_T3", west, 0.0, 52, "ЖК «Вершина», башня В — двойная, 52 этажа (западная половина)"))
    out.append(_flat("Vershina_T3_Low", lo["rect"], 0.0, lo["floors"], "башня В — восточная половина, 44 этажа"))
    # Г: на месте, верх уже
    out.append(_flat("Vershina_T4", d["rect"], 0.0, 30, "ЖК «Вершина», башня Г — жилая с лоджиями, 36 этажей", True))
    out.append(_flat("Vershina_T4_Top", d["top"]["rect"], 30 * V.STORY, 6, "башня Г — верх (сужение)", True))
    # стилобат: верхние этажи двух крыльев на высоте 6,0
    out.append(_flat("Vershina_Podium_S", V.WING_S, 6.0, 3, "ЖК «Вершина» · стилобат: офисы (закрыт)", False, True, 4.0))
    out.append(_flat("Vershina_Podium_W", V.WING_W, 6.0, 3, "ЖК «Вершина» · стилобат: фитнес (закрыт)", False, True, 4.0))
    # двор
    pv = V.PAVILION
    out.append({"id": "Vershina_YardCafe", "parent": "East", "at": [(pv[0] + pv[1]) / 2.0, (pv[2] + pv[3]) / 2.0],
                "footprint": [pv[1] - pv[0], pv[3] - pv[2]], "floors": 1, "story_height": 3.6, "label": "кафе двора", "kind": "hall",
                "interior": "shop", "loot_theme": "kiosk", "loot_density": 0.6, "lift": 0.0, "script": "build"})
    rp = V.RAMP
    out.append({"id": "Vershina_ParkingRamp", "parent": "East", "at": [(rp[0] + rp[1]) / 2.0, (rp[2] + rp[3]) / 2.0],
                "footprint": [rp[1] - rp[0], rp[3] - rp[2]], "floors": 1, "story_height": 3.2, "label": "въезд в паркинг −1 (закрыт)",
                "kind": "mass", "lift": 0.0, "script": "build"})
    # башни за забором
    for o, nm in zip(V.OUTSIDE_NEW, ("Outside_New_D1", "Outside_New_D2")):
        r = o["rect"]
        out.append({"id": nm, "parent": "Outside", "at": [(r[0] + r[1]) / 2.0, (r[2] + r[3]) / 2.0], "footprint": [r[1] - r[0], r[3] - r[2]],
                    "floors": o["floors"], "story_height": V.STORY, "label": "", "kind": "mass", "lift": 0.0, "script": "build"})
    return out


# путь от захода «За Вершиной» вдоль северного забора (как П4) к прежним точкам западнее X 30; перебивки обходит с севера / юга
ROUTE_V2N = [[181.3, -135.3], [178.0, -148.5], [150.0, -148.5], [143.5, -151.8], [134.0, -151.8], [128.0, -148.5], [92.5, -148.5],
             [86.0, -152.5], [79.5, -148.5], [58.0, -148.5], [42.0, -128.0], [32.0, -112.0],
             [12.0, -114.0]]


def stage_6a_vershina_site() -> Patch:
    p = Patch("6a_vershina_site", BASE_REV_6)
    p.add_buildings = vershina_buildings()
    p.remove["nodes"] += ["Vershina_Podium", "Vershina_T1", "Vershina_T2", "Vershina_T3", "Vershina_T4"]
    # --- колонны галереи и временные опоры контура крыльев (6b заменит опоры стенами)
    for x in V.COLUMNS_X:
        p.box(x, 3.0, -59.7, 0.8, 6.0, 0.8, "concrete")
    sup = 0
    seen: set = set()
    for (x0, x1, z0, z1) in (V.WING_S, V.WING_W):
        edges = [(False, x0, x1, z0 + 0.4), (False, x0, x1, z1 - 0.4), (True, z0, z1, x0 + 0.4), (True, z0, z1, x1 - 0.4)]
        for vert, lo, hi, fixed in edges:
            n = max(1, int(round((hi - lo) / 8.0)))
            for i in range(n + 1):
                v = lo + (hi - lo) * i / n
                x, z = (fixed, v) if vert else (v, fixed)
                x = min(max(x, x0 + 0.4), x1 - 0.4)
                z = min(max(z, z0 + 0.4), z1 - 0.4)
                if z > -60.5 and V.WING_S[0] <= x <= V.WING_S[1]:
                    continue                                        # южный край крыла — колонны галереи
                key = (round(x, 1), round(z, 1))
                if key in seen:
                    continue
                seen.add(key)
                p.box(x, 3.0, z, 0.8, 6.0, 0.8, TEMP_SUPPORT_MAT)
                sup += 1
    p.log.append(f"временных опор {sup}")
    # --- отделка старого фасада на площади: вещи, козырьки, надпись
    n = p.drop_items(["m:U12_04", "m:U08_04", "m:U08_02", "m:U08_01", "m:U12_01", "m:U08_03"], [49.0, -59.6, 128.0, -57.9])
    p.log.append(f"отделки фасада (вещей) убрано {n}")
    for cx in (71.3, 105.3):
        p.remove["pieces"].append({"list": "boxes", "rect": [cx - 0.3, -58.7, cx + 0.3, -57.5], "mat": "steel"})
    p.remove["pieces"].append({"list": "signs", "rect": [87.8, -59.0, 88.8, -58.0]})
    p.add["signs"].append({"at": [88.3, 16.5, -58.9], "size": 64.0, "text": "ЖК «Вершина» · четыре башни"})
    # --- покрытия
    p.surface("vershina_yard", "walk", 49.3, -146.0, 147.3, -83.3, 0.0, 0.08)
    p.surface("vershina_pass_d", "walk", 127.3, -83.3, 138.3, -59.3, 0.0, 0.08)
    gx0, gx1, gz0, gz1 = V.GARDEN
    p.surface("vershina_garden", "grass", gx0, gz0, gx1, gz1, 0.0, 0.12)
    # --- деревья сада
    for (tx, tz), md, yaw, sc in zip(((80.5, -108.5), (91.5, -108.5), (80.5, -93.5), (91.5, -93.5)),
                                     ("P_linden_a", "P_linden_b", "P_linden_c", "P_linden_a"), (20.0, 110.0, 200.0, 290.0),
                                     (1.15, 1.1, 1.2, 1.05)):
        p.put("tree_round", tx, tz, yaw, sc, 0.0, -1, 0.0, md)
    # --- кафе двора: наружная лестница на крышу вдоль северной стены (марш 1,1 м) и парапет 1,0 коробками
    cx0, cx1, cz0, cz1 = V.PAVILION
    roof = 3.6 + 0.175                                          # верх плиты крыши
    zs = cz0 - 0.15 - 0.1 - 0.55                                # марш вдоль северной стены с зазором 0,1
    p.stair((cx0 + 1.0, 0.0, zs), (cx0 + 9.6, roof, zs), 1.1, "concrete")
    p.box(cx0 + 10.2, roof - 0.12, zs, 1.2, 0.24, 1.1, "concrete")                 # верхняя площадка
    p.box(cx0 + 10.2, roof + 0.5, zs - 0.5, 1.2, 1.0, 0.08, "steel")               # ограждение площадки с севера
    p.box(cx0 + 10.8, roof + 0.5, zs, 0.08, 1.0, 1.1, "steel")                     # и с востока
    rx0, rx1, rz0, rz1 = cx0 - 0.4, cx1 + 0.4, cz0 - 0.4, cz1 + 0.4
    py = roof + 0.5
    gap0, gap1 = cx0 + 9.6, cx0 + 10.8                                              # проход на крышу с площадки
    p.box((rx0 + gap0) / 2.0, py, rz0 + 0.1, gap0 - rx0, 1.0, 0.2, "wall")
    p.box((gap1 + rx1) / 2.0, py, rz0 + 0.1, rx1 - gap1, 1.0, 0.2, "wall")
    p.box((rx0 + rx1) / 2.0, py, rz1 - 0.1, rx1 - rx0, 1.0, 0.2, "wall")
    for x in (rx0 + 0.1, rx1 - 0.1):
        p.box(x, py, (rz0 + rz1) / 2.0, 0.2, 1.0, rz1 - rz0 - 0.4, "wall")
    # --- что переставить: два гаража к восточному забору, контейнер, перебивки обзора
    p.move_item("garage", 171.3, -122.3, 183.5, -95.0, -90.0)
    p.move_item("garage", 174.7, -122.3, 183.5, -91.4, -90.0)
    p.move_item("container20", 131.3, -143.3, 139.0, -148.0)
    p.put("container20", 170.0, -90.0, 0.0, 1.0, 0.0, -1, 0.0, "PC03_C20_BEIGE")
    p.put("container20", 86.0, -149.0, 0.0, 1.0, 0.0, -1, 0.0, "PC03_C20")
    p.put("van", 184.0, -66.0, 90.0)
    return p


def _entry_text(e: dict) -> str:
    """Запись здания в тексте prospekt.json — как у соседних (CTP, SquareCafe, Vershina_T1)."""
    def num(v: float) -> str:
        return repr(round(float(v), 3))
    kind = e.get("kind", "mass")
    s = '  {\n   "id": "%s",\n   "label": "%s",\n   "at": [%s, %s],\n   "size": [%s, %s],\n   "floors": %d,\n   "story_height": %s,\n' % (
        e["id"], e["label"], num(e["at"][0]), num(e["at"][1]), num(e["footprint"][0]), num(e["footprint"][1]), e["floors"], num(e["story_height"]))
    s += '   "yaw": 0.0,\n   "kind": "%s",\n   "lift": %s,\n   "interior": "%s",\n   "loot_theme": "%s",\n   "loot_density": %s,\n' % (
        kind, num(e.get("lift", 0.0)), e.get("interior", ""), e.get("loot_theme", "home" if kind == "flats" else ""), num(e.get("loot_density", 0.0)))
    s += '   "region": "%s",\n   "script": "%s",\n' % (e["parent"], e["script"])
    if e.get("extra"):
        x = e["extra"]
        s += '   "extra": {\n    "open_floors": %d,\n    "balconies": %s,\n    "glass_bands": %s\n   }\n  }' % (
            x["open_floors"], str(x["balconies"]).lower(), str(x["glass_bands"]).lower())
    else:
        s += '   "extra": {}\n  }'
    return s


def _set_buildings(text: str, entries: list[dict], drop: list[str], after: str) -> str:
    """Убрать записи drop и старые записи с теми же id, затем вставить entries после записи after (идемпотентно, текстом)."""
    import re
    for bid in drop + [e["id"] for e in entries]:
        text = re.sub(r'  \{\n   "id": "%s",.*?\n  \},\n' % re.escape(bid), "", text, count=1, flags=re.S)
    m = re.search(r'  \{\n   "id": "%s",.*?\n  \},\n' % re.escape(after), text, flags=re.S)
    if not m:
        raise SystemExit(f"нет записи {after}")
    block = "".join(_entry_text(e) + ",\n" for e in entries)
    return text[:m.end()] + block + text[m.end():]


def plan_data_6a() -> None:
    import re
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = path.read_text(encoding="utf-8")
    text = _set_buildings(text, vershina_buildings(), ["Vershina_Podium"], "CTP")
    rx = re.compile(r'(\{\n   "id": "vershina_to_north",\n   "label": "[^"]*",\n   "max_open_m": [0-9.]+,\n   "points": \[\n)(.*?)(\n   \])', re.S)
    m = rx.search(text)
    if not m:
        raise SystemExit("маршрут vershina_to_north не найден")
    # прежние точки после (12; −114) — без изменений; сами новые точки заменяют всё до неё включительно
    old = re.findall(r"\[(-?[0-9.]+), (-?[0-9.]+)\]", m.group(2))
    keep: list = []
    seen = False
    for a, b in old:
        if seen:
            keep.append((float(a), float(b)))
        if abs(float(a) - 12.0) < 1e-6 and abs(float(b) + 114.0) < 1e-6:
            seen = True
    if not seen:
        raise SystemExit("в маршруте нет точки (12; −114) — это не прежний маршрут")
    body = ",\n".join("    [%s, %s]" % (_num(a), _num(b)) for a, b in ROUTE_V2N)
    body += "".join(",\n    [%s, %s]" % (_num(a), _num(b)) for a, b in keep)
    text = text[:m.start()] + m.group(1) + body + m.group(3) + text[m.end():]
    text = text.replace("за «Вершиной» → вдоль стилобата → дворы → к насыпи", "за «Вершиной» → вдоль северного забора → переулок → дворы → к насыпи")
    path.write_text(text, encoding="utf-8", newline="\n")


STAGES = {"1_street": stage_1_street, "2_backs": stage_2_backs, "3_frontline": stage_3_frontline,
          "4_wash": stage_4_wash, "5a_bank_site": stage_5a_bank_site,
          "5b_bank_plan": stage_5b_bank_plan, "6a_vershina_site": stage_6a_vershina_site}


def main() -> None:
    names = sys.argv[1:] or ["1_street"]
    for name in names:
        if name not in STAGES:
            raise SystemExit(f"нет этапа {name}; есть: {', '.join(STAGES)}")
        p = STAGES[name]()
        path = p.save()
        if name == "4_wash":
            plan_data_4()
        if name == "5b_bank_plan":
            plan_data_5b()
        if name == "6a_vershina_site":
            plan_data_6a()
        print(f"{path}: убрать вещей {len(p.remove['items'])} правил, кусков {len(p.remove['pieces'])}, узлов {len(p.remove['nodes'])}; "
              + ", ".join(f"{k} {len(v)}" for k, v in p.add.items() if v))
        for line_ in p.log:
            print("  ", line_)


if __name__ == "__main__":
    main()
