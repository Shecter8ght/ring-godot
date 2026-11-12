# АСТЕН-919: пересечения деталей по их полям расстояний (обычный Python).
#   python -X utf8 tools/asten919/check_overlaps.py <папка полей> [--json отчёт.json]
# Для каждой пары деталей (поля из build.py) считает объём общей части глубже DEPTH мм в каждой из поз POSES.
# Позы: battery (всё на месте), slide_back (затвор на задержке, рычаг задержки поднят), trigger (спуск выжат,
# предохранитель утоплен), catch (кнопка магазина нажата), lock (защёлка затвора опущена).
# Сетки без поля (пружины, патроны) не проверяются — патроны и пружину магазина проверял их построитель.
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dims import *  # noqa: E402

DEPTH = 0.2           # мм: мельче — касание и шаг сетки
STRIDE = 3
# пары, которым положено сидеть друг в друге (посадки с натягом, резьба)
IGNORE = {frozenset(p) for p in [("Barrel_Threaded", "Thread_Protector"), ("Barrel", "Barrel_Threaded"),
                                 ("MOS_Screw_L", "Slide"), ("MOS_Screw_R", "Slide"), ("Front_Sight", "Slide"),
                                 ("Trigger_Housing", "Ejector"), ("Rear_Sight", "Slide")]}
VARIANT = {"Barrel_Threaded", "Thread_Protector"}


def roty(deg, pivot):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    p = np.array(pivot, float)
    return R, p - R @ p


def shift(d):
    return np.eye(3), np.array(d, float)


def compose(*tr):
    R = np.eye(3); t = np.zeros(3)
    for R2, t2 in tr:
        R = R2 @ R; t = R2 @ t + t2
    return R, t


def poses(man):
    """Словарь поз: имя → {деталь: (R, t)} в мм."""
    by = {p["name"]: p for p in man}
    slide_kids = [p["name"] for p in man if p.get("parent") in ("Slide", "MOS_Cover_Plate")] + ["Slide"]
    px, pz = PIN_TRIGGER
    trig = roty(TRIGGER_DEG, (px, 0, pz))
    sp = by["Trigger_Safety"]["pivot"]
    out = {"battery": {}}
    sb = {n: shift((-SLIDE_TRAVEL, 0, 0)) for n in slide_kids}
    sb["Slide_Stop"] = roty(STOP_UP_DEG, (px, 0, pz))
    sb["Barrel"] = compose(roty(-BARREL_TILT, (67.0, 0, 0)), shift((-BARREL_BACK, 0, 0)))
    sb["Barrel_Threaded"] = sb["Barrel"]; sb["Thread_Protector"] = sb["Barrel"]
    out["slide_back"] = sb
    out["trigger"] = {"Trigger": trig, "Trigger_Safety": compose(roty(SAFETY_DEG, sp), trig), "Trigger_Safety_Pin": trig}
    out["catch"] = {"Mag_Catch": shift((0, -CATCH_IN, 0))}
    a = math.radians(LOCK_DEG)
    out["lock"] = {"Slide_Lock": shift((-math.sin(a) * LOCK_DOWN, 0, -math.cos(a) * LOCK_DOWN))}
    return out


def main():
    src = os.path.abspath(sys.argv[1])
    man = json.load(open(os.path.join(src, "manifest.json"), encoding="utf-8"))
    fields = {}
    for p in man:
        path = os.path.join(src, p["file"])
        if not os.path.exists(path):
            continue
        d = np.load(path)
        if "field" not in d:
            continue
        fields[p["name"]] = (d["field"], float(d["h"]), d["lo"])
    names = sorted(fields)
    # опорные точки каждой детали: центры вокселей глубже DEPTH
    pts = {}
    for n in names:
        A, h, lo = fields[n]
        sub = A[::STRIDE, ::STRIDE, ::STRIDE]
        idx = np.argwhere(sub < -DEPTH)
        pts[n] = (idx * STRIDE * h + lo, (STRIDE * h) ** 3)
    report = []
    for pose, tr in poses(man).items():
        for i, a in enumerate(names):
            Pa, va = pts[a]
            if len(Pa) == 0:
                continue
            Ra, ta = tr.get(a, (np.eye(3), np.zeros(3)))
            Wa = Pa @ Ra.T + ta
            lo_a, hi_a = Wa.min(axis=0), Wa.max(axis=0)
            for b in names:
                if a == b or frozenset((a, b)) in IGNORE:
                    continue
                if (a in VARIANT) != (b in VARIANT) and not ({a, b} & {"Slide", "Guide_Rod", "Frame"}):
                    continue
                if pose != "battery" and a not in tr and b not in tr:
                    continue
                B, hb, lob = fields[b]
                Rb, tb = tr.get(b, (np.eye(3), np.zeros(3)))
                # грубый отсев по габаритам (в осях b)
                Q = (Wa - tb) @ Rb
                ijk = np.round((Q - lob) / hb).astype(int)
                ok = np.all((ijk >= 0) & (ijk < np.array(B.shape)), axis=1)
                if not ok.any():
                    continue
                v = B[ijk[ok, 0], ijk[ok, 1], ijk[ok, 2]].astype(np.float32)
                hit = v < -DEPTH
                n = int(hit.sum())
                if n:
                    vol = n * va
                    c = Wa[ok][hit].mean(axis=0)
                    if a < b or True:
                        report.append({"pose": pose, "a": a, "b": b, "mm3": round(vol, 2), "at": [round(float(x), 1) for x in c]})
    # пара встречается дважды (a в b и b в a) — оставляем большее
    best = {}
    for r in report:
        k = (r["pose"], frozenset((r["a"], r["b"])))
        if k not in best or r["mm3"] > best[k]["mm3"]:
            best[k] = r
    rows = sorted(best.values(), key=lambda r: (-r["mm3"]))
    for r in rows:
        print(f"OVERLAP {r['pose']:11s} {r['a']:20s} × {r['b']:20s} {r['mm3']:8.2f} мм3  около {r['at']}")
    print("PAIRS", len(rows), "деталей с полем", len(names))
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)


main()
