# ПП по мотивам KRISS Vector Gen II: ствол 5.5″ (139.7 мм от зеркала затвора) с патронником .45 ACP и резьбой
# 16 × 1 LH под колпачок; колпачок резьбы Ø18.9 с прямым рифлением (снимки KRISS, владельца 04).
import math
import bmesh
import bpy
from lib import MM, BARREL_LEN, BARREL_R, BORE_R, CAP_X, CAP_R, lathe, prism_yz, prism_xz, cyl, boolean, v

CHAMBER_R = 6.10          # патронник .45 ACP (гильза Ø12.0)
CHAMBER_LEN = 22.8
BREECH_R = 11.0           # казённая часть Ø22 (внутри коробки)
THREAD_R = 7.95           # резьба M16 × 1 (под колпачком)
CAP_FRONT_R = 5.9         # отверстие колпачка — по каналу


def knurl_section(r_out, depth, n, seg=6):
    """Сечение с прямым рифлением: n впадин с круглым дном (синус), вершины тоже скруглены."""
    pts = []
    tot = n * seg * 2
    for k in range(tot):
        a = 2 * math.pi * k / tot
        r = r_out - depth * (0.5 - 0.5 * math.cos(n * a))
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def build(ctx):
    C = ctx["coll"]["Barrel"]
    # ствол: казённая часть Ø22 с фаской → Ø16.7 до резьбы → резьба Ø15.9 до среза; канал и патронник — внутренний контур
    outer = [(0.0, BREECH_R - 0.8), (0.8, BREECH_R), (32.0, BREECH_R), (36.0, BARREL_R), (CAP_X[0] - 0.5, BARREL_R),
             (CAP_X[0], THREAD_R), (BARREL_LEN - 0.6, THREAD_R), (BARREL_LEN, THREAD_R - 0.6)]
    inner = [(BARREL_LEN, BORE_R + 0.4), (BARREL_LEN - 0.6, BORE_R), (CHAMBER_LEN + 2.0, BORE_R), (CHAMBER_LEN, CHAMBER_R),
             (1.2, CHAMBER_R), (0.0, CHAMBER_R + 1.0)]
    b = lathe("Barrel", outer + inner, C, "Steel_black", seg=96)
    # колпачок резьбы: гладкая основа + рифлёная середина; спереди — отверстие по каналу
    x0, x1 = CAP_X
    cap = lathe("Thread_cap", [(x0, THREAD_R + 0.05), (x0, CAP_R - 1.0), (x0 + 1.0, CAP_R), (x1 - 1.6, CAP_R),
                               (x1, CAP_R - 1.6), (x1, CAP_FRONT_R + 0.6), (x1 - 0.6, CAP_FRONT_R),
                               (BARREL_LEN + 0.05, CAP_FRONT_R), (BARREL_LEN + 0.05, THREAD_R + 0.05)],
                C, "Steel_black", seg=128)
    # рифление: 40 канавок на середине длины колпачка (по снимку владельца 04 — прямое)
    kn = prism_yz("_kn", [(y, z) for y, z in knurl_section(CAP_R + 0.3, 0.8, 40)], x0 + 3.0, x1 - 3.2, C)
    # резец = кольцо снаружи колпачка минус рифлёный цилиндр → впадины рифления
    big = lathe("_cut", [(x0 + 3.0, 0.0), (x0 + 3.0, CAP_R + 3.0), (x1 - 3.2, CAP_R + 3.0), (x1 - 3.2, 0.0)], C, seg=128)
    boolean(big, kn)
    boolean(cap, big)
    # вырез под коготь выбрасывателя на казённом срезе справа (коготь выходит за зеркало на 2.6 мм)
    from lib import box, fillet as _fl
    from part_bolt import EXT_Z
    boolean(b, box("_extn", -1.0, 3.2, -12.5, -5.25, EXT_Z[0] - 0.4, EXT_Z[1] + 0.4, C))
    # подающий скос снизу: патрон из губок магазина (Z −18) поднимается в патронник по наклонной
    ramp = prism_xz("_ramp", _fl([(-1.0, -12.0), (-1.0, -4.2), (1.0, -4.2), (6.5, -6.4), (6.5, -12.0)], [0, 0, 1.0, 1.0, 0], 4),
                    -4.6, 4.6, C)
    boolean(b, ramp)
    # нарезы у дула: 6 канавок ≈1.0 × 0.18 на последних 24 мм (видны в отверстие колпачка), шаг витка не показываем
    for k in range(6):
        a = 2 * math.pi * k / 6 + math.pi / 12
        cy, cz = math.cos(a) * (BORE_R - 0.62), math.sin(a) * (BORE_R - 0.62)
        g = cyl("_rf", BARREL_LEN - 24.0, BARREL_LEN - 1.8, 0.8, C, seg=12, cy=cy, cz=cz)   # не до среза (Д18)
        boolean(b, g)
    from lib import finish_small

    def breech(center, normal):
        return center.x < 8.0
    finish_small(b, w=0.5, seg=3, exclude=breech)
    # у казённого среза фаски нет: вырез под коготь и скос дают там тонкие клинья, фаска их выплёскивала за срез
    finish_small(cap, w=0.15, seg=2)
    cap["owner"] = "Barrel"               # навёрнут на резьбу ствола
    return {"barrel": b, "cap": cap}
