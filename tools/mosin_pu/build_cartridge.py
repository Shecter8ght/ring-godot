"""Патрон 7,62×54R (пуля типа ЛПС) — high-poly для просмотра формы.

Источник размеров: чертёж C.I.P.-размеров в Википедии (File:7.62 x 54 R cartridge.svg):
закраина Ø14,48 × 1,60 (фаска донца 20°, 0,6 мм), корпус Ø12,37 → Ø11,61 на 39,70,
скат 37° до Ø8,53 на 44,30, дульце Ø8,53 до 53,72, пуля Ø7,92, длина патрона 77,16.
Капсюль Бердана Ø6,45 (.254"). Оживало пули — касательное, R ≈ 6,6 калибра (оценка по фото).

Запуск: blender --background --factory-startup --python tools/mosin_pu/build_cartridge.py
Оси: донце в начале координат, ось патрона +X (к дулу).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

OUT = os.path.join(L.ASSET_DIR, "models", "04_Патрон", "Mosin_Cartridge_762x54R_v01.blend")
SEG = 96


def case_profile():
    pts = [
        (0.45, 0.0),
        (0.45, 3.26),     # дно гнезда капсюля
        (0.0, 3.26),      # стенка гнезда
        (0.0, 5.59),      # торец донца до фаски
        (0.6, 7.24),      # фаска закраины 20°
        (1.6, 7.24),      # закраина
        (1.6, 6.185),     # передняя плоскость закраины
        (39.70, 5.805),   # корпус до ската
        (44.30, 4.265),   # скат
        (53.72, 4.265),   # дульце
        (53.72, 3.97),    # торец дульца (стенка 0,3)
        (52.60, 3.97),
        (52.60, 0.0),
    ]
    radii = [0, 0.05, 0.10, 0.10, 0.15, 0.15, 0.30, 0.50, 0.50, 0.10, 0.06, 0.0, 0]
    return L.fillet(pts, radii, seg=5)


def primer_profile():
    pts = [(0.42, 0.0), (0.42, 3.225), (0.06, 3.225), (0.06, 0.0)]
    return L.fillet(pts, [0, 0, 0.14, 0], seg=5)


def bullet_profile():
    # Касательное оживало с мнимым острием за 77,16 и усечённым скруглённым носиком:
    # по фото (Commons, Mosin_ammo_clip.JPG) нос пули полнее и тупее острого оживала.
    x0, r0, virt_tip, tip, r_cut = 56.60, 3.96, 78.0, 77.16, 1.0
    lo = virt_tip - x0
    R = (lo * lo + r0 * r0) / (2 * r0)
    cy = r0 - R
    pts = [
        (47.0, 0.0), (47.0, 3.55), (47.6, 3.96),
        (53.30, 3.96), (53.55, 3.82), (54.25, 3.82), (54.50, 3.96),   # канавка обжима у дульца
        (x0, r0),
    ]
    radii = [0, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.0]
    phi_end = math.asin((r_cut - cy) / R)
    n = 40
    for i in range(1, n + 1):
        phi = math.pi / 2 + (phi_end - math.pi / 2) * i / n
        pts.append((x0 + R * math.cos(phi), cy + R * math.sin(phi)))
        radii.append(0.0)
    pts.append((tip, 0.0))
    radii[-1] = 0.9                         # скруглённый носик
    radii.append(0)
    return L.fillet(pts, radii, seg=6)


def build():
    L.reset_scene()
    col = L.collection("Cartridge_762x54R")
    root = L.empty("Cartridge_762x54R", col=col, size=0.02)
    case = L.lathe("Cartridge_Case", case_profile(), SEG, "Case_Steel_Lacquer", col)
    bullet = L.lathe("Cartridge_Bullet", bullet_profile(), SEG, "Bullet_Jacket", col)
    primer = L.lathe("Cartridge_Primer", primer_profile(), SEG, "Primer_Brass", col)
    for ob in (case, bullet, primer):
        ob.parent = root
    lo, hi = L.world_bbox_mm([case, bullet, primer])
    print("CARTRIDGE bbox mm", tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi),
          "size", tuple(round(h - l, 3) for l, h in zip(lo, hi)))
    L.save_blend(OUT)


if __name__ == "__main__":
    build()
