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

PLAN_LISTS = ("surfaces", "slabs", "walls", "boxes", "columns", "stairs", "ramps", "beams", "lamps", "signs",
              "ground_holes", "walk_holes")


# ------------------------------------------------------------------ патч и помощники (как в build_prospekt.py)
class Patch:
    def __init__(self, name: str) -> None:
        self.name = name
        self.remove: dict = {"items": [], "pieces": [], "nodes": []}
        self.add: dict = {k: [] for k in PLAN_LISTS}
        self.add["items"] = []
        self._base: dict | None = None
        self.log: list[str] = []

    # --- снимок до правок
    def base(self) -> dict:
        if self._base is None:
            try:
                raw = subprocess.run(["git", "show", f"{BASE_REV}:{SNAPSHOT_PATH}"], cwd=ROOT, check=True,
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
        raise KeyError(f"нет вещи {kit} у ({x}; {z}) в снимке {BASE_REV}")

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
        data = {"stage": self.name, "base_rev": BASE_REV, "remove": self.remove,
                "add": {k: v for k, v in self.add.items() if v}}
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


STAGES = {"1_street": stage_1_street}


def main() -> None:
    names = sys.argv[1:] or ["1_street"]
    for name in names:
        if name not in STAGES:
            raise SystemExit(f"нет этапа {name}; есть: {', '.join(STAGES)}")
        p = STAGES[name]()
        path = p.save()
        print(f"{path}: убрать вещей {len(p.remove['items'])} правил, кусков {len(p.remove['pieces'])}, узлов {len(p.remove['nodes'])}; "
              + ", ".join(f"{k} {len(v)}" for k, v in p.add.items() if v))
        for line_ in p.log:
            print("  ", line_)


if __name__ == "__main__":
    main()
