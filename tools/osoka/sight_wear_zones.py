"""«Осока», тепловизор ПН-36Т «ПОЛЫНЬ», износ этап 2 v1 — маски МЕСТ в развёртке набора Polyn: где и почему след.
Тем же кодом, что у «Осоки» (tools/osoka/wear_zones.py: карты положения / нормали / номера детали, шум, фото-маски
отпечатков CC0, царапины, кольца у крепежа); здесь — места прицела.

    python -X utf8 tools/osoka/sight_wear_zones.py
→ _asset_src/osoka_polyn/tex/wear/Polyn_<место>.png (белое — след есть) и Polyn_zones_preview.png.

Интервью 2026-11-07: «Как у «Осоки»» (рабочий: следы только с причиной, аккуратно и дозированно; тон тёплый и холодный,
светлый и тёмный), прибор многоразовый (снимают с отстрелянной трубы и ставят на новую, носят в сумке — потёрт как
пусковой механизм), следы — лицо и руки, установка на трубу, удары и сумка, пыль и тон краски.
Оси карт — оси файла прицела (начало — точка крепления на «Осоке»: x 1214, y 2, z 49.5 её осей; +X вперёд, +Y влево).

Тон (крашеный корпус и блок кнопок): sun / low — сверху чёрная краска чуть выгорела (светлее, теплее), снизу темнее и
холоднее; пятна четырёх оттенков (корпус небольшой — пятна 3–6 см); wipe — разводы протирки (блеск); dust — пыль на крыше
пятнами; cavity — пыль в углах и щелях по AO заводской выгрузки.
Места: face_oil — наглазник засален лицом (раструб и край); focus — кольцо фокуса крутят пальцами (вершины рифления
глаже); diopter — кольцо диоптрий: вершины рифления местами до алюминия; batt — крышку отсека питания откручивают;
keys — кнопки (центр); switch — рычажок переключателя (головка), латунное основание по ходу рычажка; cap_tab — язычок
крышки объектива и край крышки под пальцем; prints_left / prints_right — отпечатки и разводы ладоней на боках;
marking_rub — надписи у переключателя и местами в названии стёрты пальцами; mount_bare — губки лапы, рельс и губки
площадки по кромкам до алюминия (ставят и снимают); mount_scuff — риски по лапе вдоль трубы; knobs — головки прижимных
винтов (вершины рифления — сталь); bumps — выступающие углы и рёбра корпуса, передняя кромка оправы объектива, край
крышки отсека (удары и сумка: кромки местами до алюминия); rubber_scuff — ссадины на резине (раструб, кольцо фокуса,
крышка объектива); rings — грязь кольцом у винтов, кнопок, разъёма; accent — длинная царапина на правом боку (сумка).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import wear_zones as W

ROOT = Path(__file__).resolve().parents[2]
W.TEX = ROOT / '_asset_src/osoka_polyn/tex'
W.OUT = W.TEX / 'wear'
W.SCENE = json.loads((W.TEX / 'scene.json').read_text(encoding='utf-8'))
W.LO = np.array(W.SCENE['min_mm']) - 30.0
W.HI = np.array(W.SCENE['max_mm']) + 30.0
smooth, patches, line = W.smooth, W.patches, W.line


def prints(m, sel, stamps, u, v):
    """Отпечатки и разводы (ambientCG, CC0) — как wear_zones.prints, но каждое пятно в мягком круглом окне: фото-маски
    разводов заполняют весь квадрат, и у пятна оставался прямой край квадрата (зоны v1)."""
    out = np.zeros_like(m.x)
    for name, kind, size, cu, cv_, rot, flip in stamps:
        im = W.stamp_image(W.cc0(name, kind), size, u, v, cu, cv_, rot, flip)
        win = np.exp(-(((u - cu) ** 2 + (v - cv_) ** 2) / (0.3 * size) ** 2))
        out = np.maximum(out, np.clip((im - 0.08) / 0.5, 0.0, 1.0) * win)
    return np.where(sel, out, 0.0)
EYE = (46.0, 86.5)          # ось окуляра (y, z)
OBJ = (46.0, 103.5)         # ось объектива (y, z)
BODY = dict(x=(-89.0, 26.0), y=(-8.5, 100.5), z=(28.5, 161.5))


def tone(m):
    paint = m.slots('body')
    out = {}
    out['sun'] = np.where(paint, smooth(0.05, 0.95, m.nz) * np.clip(0.55 + 0.35 * m.noise(11, 40.0), 0, 1), 0.0)
    out['low'] = np.where(paint, (1 - smooth(-0.9, 0.0, m.nz)) * np.clip(0.55 + 0.35 * m.noise(12, 35.0), 0, 1), 0.0)
    for k, (nm, sig, cov) in enumerate((('warm_light', 38.0, 0.16), ('warm_dark', 28.0, 0.12),
                                         ('cool_light', 32.0, 0.12), ('cool_dark', 45.0, 0.18))):
        out[nm] = patches(m, 21 + k, sig, cov, soft=0.9, mask=paint)
    n = m.noise(41, 2.0, aniso=(10.0, 1.0, 1.0))
    out['wipe'] = np.where(paint & (m.nz > -0.5), smooth(0.9, 1.9, n) * np.clip(0.4 + 0.5 * m.noise(42, 60.0), 0, 1),
                           0.0)
    up = smooth(0.55, 0.9, m.nz)
    out['dust'] = np.where(m.filled & ~m.slots('germanium', 'glass'), up * patches(m, 43, 14.0, 0.35), 0.0)
    ao = cv2.imread(str(W.TEX / f'maps_v1/{m.name}_occlusionRoughnessMetallic.png'))
    if ao is not None:
        ao = ao[..., 2].astype(np.float32) / 255.0
        if ao.shape != m.x.shape:
            ao = cv2.resize(ao, m.x.shape[::-1], interpolation=cv2.INTER_AREA)
        # прицел компактный: AO запекания по всей сборке низкий на больших площадях (медиана 0.68, у рифлёных колец —
        # всюду), и пыль «по AO» легла пятнами везде (проба 2). Углы и щели — где AO заметно ниже, чем вокруг (~5 мм)
        f = m.filled.astype(np.float32)
        sig = 5.0 * 9.2
        num = cv2.GaussianBlur(ao * f, (0, 0), sig)
        den = cv2.GaussianBlur(f, (0, 0), sig)
        local = num / np.maximum(den, 1e-4)
        cav = smooth(0.12, 0.35, local - ao) * smooth(0.02, 0.15, ao)
        brk = smooth(-0.5, 0.8, m.noise(44, 1.0)) * (0.55 + 0.45 * smooth(-0.3, 0.7, m.nz))
        out['cavity'] = np.where(m.filled & ~m.slots('germanium', 'glass'), cav * brk, 0.0)
    return out


def edge_band(m):
    """Кромки и скругления: у игровой сетки со скруглением — нормаль не по осям; у сетки без фаски (кронштейн, оправы)
    скругление в карте нормалей — отклонение от плоской. Без этого генератор кромок в маске «места» сыпал пятнами
    по плоским стенкам (камуфляж вокруг окуляра и спереди, износ v1 проба 1)."""
    geo = 1.0 - smooth(0.93, 0.985, np.max(np.abs(m.nrm), axis=-1))
    nm = cv2.imread(str(W.TEX / 'normals/Polyn_normal.png'), cv2.IMREAD_UNCHANGED)
    dev = np.zeros_like(m.x)
    if nm is not None:
        nm = nm[..., ::-1].astype(np.float32) / (65535.0 if nm.dtype == np.uint16 else 255.0)
        if nm.shape[:2] != m.x.shape:
            nm = cv2.resize(nm, m.x.shape[::-1], interpolation=cv2.INTER_AREA)
        dev = smooth(0.12, 0.35, np.hypot(nm[..., 0] - 0.5, nm[..., 1] - 0.5) * 2.0)
    return np.where(m.filled, np.maximum(geo, dev), 0.0)


def places(m):
    out = {}
    x, y, z = m.x, m.y, m.z
    edge = edge_band(m)
    re = np.hypot(y - EYE[0], z - EYE[1])
    ro = np.hypot(y - OBJ[0], z - OBJ[1])
    # наглазник: раструб и край засалены лицом (сильнее у края, изнутри тоже)
    cup = m.of('Thermal_eyecup')
    out['face_oil'] = np.where(cup, smooth(-128.0, -144.0, x) * np.clip(0.55 + 0.45 * m.noise(51, 6.0), 0, 1), 0.0)
    # кольцо фокуса — крутят пальцами: по всему кругу, пятнами; вершины рифления дадут рельеф в Painter
    fr = m.of('Thermal_focus_ring')
    out['focus'] = np.where(fr & (ro > 39.0), np.clip(0.35 + 0.65 * smooth(-0.6, 0.8, m.noise(52, 8.0)), 0, 1), 0.0)
    # кольцо диоптрий (анодированное, рифлёное) — вершины рифления местами до алюминия (рисунок — генератор кромок)
    out['diopter'] = np.where(m.of('Thermal_diopter_ring') & (re > 28.0), smooth(-0.4, 0.8, m.noise(53, 5.0)), 0.0) * edge
    # крышка отсека питания — откручивают: рифление гладкое пятнами, торец у головки
    out['batt'] = np.where(m.of('Thermal_batt_cap', 'Thermal_batt_knob'), np.clip(0.4 + 0.6 * m.noise(54, 7.0), 0, 1),
                           0.0)
    # кнопки: центр
    kc = np.minimum(np.hypot(x + 84.0, y - 46.0), np.hypot(x + 70.0, y - 46.0))
    out['keys'] = np.where(m.of('Thermal_key_0', 'Thermal_key_1'), 1 - smooth(1.5, 4.5, kc), 0.0)
    # переключатель: головка рычажка и сам рычажок (пальцы), латунь по ходу рычажка (кольцо у края основания)
    sw = np.hypot(x + 23.0, z - 62.5)
    knob = m.of('Thermal_switch_knob')
    lever = m.of('Thermal_switch_lever')
    base = m.of('Thermal_switch_base')
    out['switch'] = np.where(knob, 1.0, 0.0) + np.where(lever, 0.5 + 0.5 * smooth(8.0, 16.0, sw), 0.0) + \
        np.where(base & (m.ny > 0.8), smooth(6.0, 9.5, sw) * (1 - smooth(10.5, 11.6, sw)), 0.0)
    # язычок крышки объектива и край крышки над ним (большой палец)
    lid = m.of('Thermal_cap', 'Thermal_cap_tab')
    out['cap_tab'] = np.where(m.of('Thermal_cap_tab'), 1.0, 0.0) + \
        np.where(lid & ~m.of('Thermal_cap_tab'), np.exp(-((y - 46.0) / 12.0) ** 2) * smooth(70.0, 58.0, z), 0.0)
    # отпечатки и разводы ладоней на боках корпуса: слева у переключателя (переключают), справа спереди (ставят на трубу)
    side_l = m.of('Thermal_body') & (m.ny > 0.95)
    side_r = m.of('Thermal_body') & (m.ny < -0.95)
    pl = prints(m, side_l, [('Fingerprints003', 'Opacity', 34.0, -38.0, 80.0, 20.0, False),
                            ('Smear004', 'Roughness', 40.0, -5.0, 100.0, 170.0, False),
                            ('Fingerprints007', 'Opacity', 28.0, -60.0, 120.0, -30.0, True)], x, z)
    pr = prints(m, side_r, [('Fingerprints005', 'Opacity', 32.0, 5.0, 95.0, -10.0, True),
                            ('Smear006', 'Roughness', 44.0, -30.0, 70.0, 15.0, False),
                            ('Fingerprints003', 'Opacity', 26.0, -55.0, 125.0, 60.0, False)], x, z)
    out['prints_left'] = pl * 0.85
    out['prints_right'] = pr * 0.85
    # надписи: у переключателя стёрты пальцами сильнее, название — местами
    st = cv2.imdecode(np.fromfile(str(W.TEX / 'masks/Polyn_stencil.png'), np.uint8), cv2.IMREAD_GRAYSCALE)
    st = st.astype(np.float32) / 255.0
    if st.shape != m.x.shape:
        st = cv2.resize(st, m.x.shape[::-1], interpolation=cv2.INTER_AREA)
    near_sw = np.exp(-(sw / 22.0) ** 2)
    out['marking_rub'] = st * smooth(0.5, 1.4, m.noise(55, 0.9) + 1.2 * near_sw)
    # лапа и площадка: кромки губок до алюминия (рисунок — генератор кромок), рельс по кромкам
    br = m.of('Thermal_bracket')
    jaw_foot = br & (x > -14.0) & (x < 14.0) & (z < 16.0)
    jaw_top = br & (z > 22.0)
    out['mount_bare'] = (np.where(jaw_foot | jaw_top, 1.0, 0.0) + np.where(m.of('Thermal_rail'), 1.0, 0.0)) * edge *         smooth(-0.6, 0.6, m.noise(63, 2.0))
    fsc = m.noise(56, 0.35, aniso=(30.0, 1.0, 1.0))
    out['mount_scuff'] = np.where(jaw_foot & (np.abs(m.nx) < 0.5), smooth(1.0, 2.0, fsc), 0.0)
    out['knobs'] = np.where(m.of('Thermal_foot_knob', 'Thermal_rail_knob'), 1.0, 0.0) * edge
    # удары и сумка: выступающие места — углы и рёбра корпуса (сверху, сзади, по бокам), передняя кромка оправы объектива,
    # край крышки отсека питания; рисунок — генератор кромок, пятнами
    bx = m.of('Thermal_body', 'Thermal_key_pad')
    ext = np.maximum.reduce([smooth(BODY['z'][1] - 22.0, BODY['z'][1] - 2.0, z),
                             smooth(BODY['x'][0] + 18.0, BODY['x'][0] + 2.0, x),
                             smooth(BODY['y'][1] - 10.0, BODY['y'][1] - 1.0, y),
                             smooth(BODY['y'][0] + 10.0, BODY['y'][0] + 1.0, y),
                             smooth(BODY['x'][1] - 20.0, BODY['x'][1] - 1.0, x) * smooth(BODY['z'][1] - 40.0, BODY['z'][1], z)])
    b1 = np.where(bx, ext * patches(m, 57, 8.0, 0.3, mask=bx), 0.0)
    b2 = np.where(m.of('Thermal_obj_bezel') & (x > 108.0), smooth(-0.5, 0.7, m.noise(58, 3.0)), 0.0)
    b3 = np.where(m.of('Thermal_batt_cap_face') & (x > 61.5), smooth(-0.4, 0.8, m.noise(59, 3.0)), 0.0)
    out['bumps'] = np.maximum.reduce([b1, b2, b3]) * edge
    # ссадины на резине: внешний раструб наглазника, передняя кромка кольца фокуса, край крышки объектива
    rs = np.where(cup & (re > 25.0) & (x < -135.0), 1.0, 0.0) + \
        np.where(fr & (x > 92.0), 1.0, 0.0) + np.where(m.of('Thermal_cap') & (ro > 43.0), 1.0, 0.0)
    out['rubber_scuff'] = np.clip(rs, 0, 1) * smooth(0.3, 1.2, m.noise(60, 1.5))
    # грязь кольцом у крепежа, кнопок, разъёма (рвано)
    rings = W.ring_around(m, ['*screw*', 'Thermal_key_bezel_*', 'Thermal_conn_flange', 'Thermal_switch_base',
                              'Thermal_cap_pin'], inner=0.1, outer=2.2)
    out['rings'] = rings * np.clip(0.35 + 0.65 * smooth(-0.5, 0.6, m.noise(61, 1.2)), 0, 1)
    # акцент: длинная тонкая царапина на правом боку (протащили в сумке)
    out['accent'] = np.where(side_r, line(m, (-72.0, 58.0), (-12.0, 74.0), 0.08, 0.16, x, z, seed=62), 0.0)
    return out


def main():
    m = W.Maps('Polyn')
    log = []
    prev = np.zeros(m.x.shape + (3,), np.float32)
    prev[m.filled] = 0.22
    for nm, a in tone(m).items():
        log.append(f'Polyn {nm}: {W.save("Polyn", nm, a):.1f} %')
    for k, (nm, a) in enumerate(places(m).items()):
        log.append(f'Polyn {nm}: {W.save("Polyn", nm, a):.2f} %')
        c = np.array(W.COLORS[k % len(W.COLORS)], np.float32)
        a = np.clip(a, 0, 1)[..., None]
        prev = prev * (1 - a) + a * c
    cv2.imwrite(str(W.OUT / 'Polyn_zones_preview.png'),
                cv2.resize((prev[..., ::-1] * 255).astype(np.uint8), (2048, 2048), interpolation=cv2.INTER_AREA))
    print('\n'.join(log))


if __name__ == '__main__':
    main()
