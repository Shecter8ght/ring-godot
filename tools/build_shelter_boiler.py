"""Котельная зоны 5: перестройка оболочки убежища и бывший котельный зал с тиром. bpy → GLB.

Убежище — отдельная локация (котельная), а не подвал ТЦ: наружные стены кирпичные, с окнами из
армированного стекла; перегородки — побелённый кирпич; к складу примыкает высокий котельный зал
(два остановленных котла, газоходы, насосы, магистрали) с тиром на пять дорожек.
Использует функции kit из build_shelter_assets.py (тот же стиль: фаски, метрические UV, один mesh
на сборку, упрощённые коллизии). Пишет только свои ассеты в manifest, остальные не трогает.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_shelter_boiler.py
Координаты — Godot X/Y/Z (м), как в kit.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_shelter_assets as kit

OUT = kit.OUT
SRC = kit.SRC
box, cyl, curve, face, begin, collision, export = kit.box, kit.cyl, kit.curve, kit.face, kit.begin, kit.collision, kit.export

kit.COLORS.update({
    'Brick': (.42, .22, .15), 'Whitewash': (.70, .69, .64), 'PeelingPaint': (.40, .26, .22),
    'BoilerSteel': (.30, .34, .36), 'FlueRust': (.34, .24, .18), 'WiredGlass': (.62, .66, .66),
    'ButtonGreen': (.12, .45, .18), 'ButtonRed': (.55, .10, .08), 'ButtonYellow': (.70, .52, .10),
    'RangePaper': (.86, .84, .76),
})
kit.TILE.update({'Brick': 2, 'Whitewash': 2, 'PeelingPaint': 2.5, 'BoilerSteel': 1.5, 'FlueRust': 1.5, 'WiredGlass': 1})

# --- Раскладка котельного зала (её же читает author_shelter_scene.gd) -------------------------
HALL_X0, HALL_X1, HALL_Z0, HALL_Z1, HALL_H = 18.0, 62.4, -11.0, 7.0, 8.0
FIRING_X = 25.0                       # огневой рубеж: отсюда меряется дистанция до мишени
COUNTER_X = 24.55                     # стойка рубежа (центр по X), верх 0.95
LANES = [(-4.2, 'paper'), (-1.8, 'paper'), (0.6, 'paper'), (3.0, 'mannequin'), (5.4, 'mannequin')]
DIVIDERS = [-5.4, -3.0, -0.6, 1.8, 4.2, 6.6]
RAIL_Y = 2.85                         # ось подвесной направляющей бумажных мишеней
RAIL_X0, RAIL_X1 = 25.2, 58.2
BOILERS = [(34.0, -8.4), (47.5, -8.4)]
BOILER_L, BOILER_W = 8.0, 3.2
PUMPS = [(20.3, -9.85), (21.75, -9.85), (23.2, -9.85)]
STORAGE_DOOR_Z = 4.0
GUN_CABINET = (18.24, 0.0, 0.6)       # шкаф стойки тира на западной стене зала
LAYOUT = {
    'hall': {'x0': HALL_X0, 'x1': HALL_X1, 'z0': HALL_Z0, 'z1': HALL_Z1, 'h': HALL_H},
    'firing_x': FIRING_X, 'counter_x': COUNTER_X, 'counter_top': .95,
    'lanes': [{'z': z, 'kind': k} for z, k in LANES], 'rail_y': RAIL_Y, 'rail_x1': RAIL_X1,
    'boilers': [{'x': x, 'z': z, 'length': BOILER_L} for x, z in BOILERS],
    'pumps': [{'x': x, 'z': z} for x, z in PUMPS],
    'storage_door_z': STORAGE_DOOR_Z, 'gun_cabinet': list(GUN_CABINET),
}


# --- Стены с проёмами: двери до 2.3 м, окна с подоконником, рамой, импостами и стеклом -----------
def _plane(alongx: bool, fixed: float):
    def P(u, v, off=0.0):
        return (u, v, fixed + off) if alongx else (fixed + off, v, u)
    def S(du, dv, dd):
        return (du, dv, dd) if alongx else (dd, dv, du)
    return P, S


def window(P, S, name: str, lo: float, hi: float, bottom: float, top: float, seed: int) -> None:
    w, h = hi - lo, top - bottom
    c, m = (lo + hi) / 2, (bottom + top) / 2
    t, d = .07, .16
    # стальная рама — по периметру проёма, в глубине стены
    box('Window frame head', P(c, top - t / 2), S(w, t, d), 'PaintedSteel', .006)
    box('Window frame foot', P(c, bottom + t / 2), S(w, t, d), 'PaintedSteel', .006)
    for u in (lo + t / 2, hi - t / 2):
        box('Window frame jamb', P(u, m), S(t, h, d), 'PaintedSteel', .006)
    cols = max(2, round(w / .62))
    rows = max(2, round(h / .55))
    cw, rh = (w - 2 * t) / cols, (h - 2 * t) / rows
    for i in range(1, cols):
        box('Window mullion', P(lo + t + i * cw, m), S(.035, h - 2 * t, .07), 'PaintedSteel', .004)
    for j in range(1, rows):
        box('Window transom', P(c, bottom + t + j * rh), S(w - 2 * t, .035, .07), 'PaintedSteel', .004)
    for i in range(cols):
        for j in range(rows):
            pu, pv = lo + t + (i + .5) * cw, bottom + t + (j + .5) * rh
            # часть стёкол давно выбита и зашита фанерой — как в любой брошенной котельной
            if (i * 7 + j * 3 + seed) % 6 == 0:
                box('Plywood patch', P(pu, pv, .025), S(cw - .02, rh - .02, .018), 'OldWood', .003)
            else:
                box('Wired glass pane', P(pu, pv), S(cw - .01, rh - .01, .008), 'WiredGlass', 0)
    # бетонный подоконник с обеих сторон и капельник
    box('Window sill', P(c, bottom - .03), S(w + .12, .06, .52), 'RawConcrete', .01)
    collision(P(c, m), S(w, h, .2))


def wall(name: str, a, b, height: float, openings=(), upper='Brick', lower='PaintedConcrete', band=1.5) -> None:
    begin()
    x1, z1 = a
    x2, z2 = b
    alongx = z1 == z2
    start, end = (x1, x2) if alongx else (z1, z2)
    P, S = _plane(alongx, z1 if alongx else x1)
    rects = []
    cur = start
    for c, w, bottom, top, kind in sorted(openings):
        lo, hi = c - w / 2, c + w / 2
        if lo > cur:
            rects.append((cur, lo, 0.0, height))
        if bottom > 0:
            rects.append((lo, hi, 0.0, bottom))
        if top < height:
            rects.append((lo, hi, top, height))
        cur = hi
    if end > cur:
        rects.append((cur, end, 0.0, height))
    for u0, u1, v0, v1 in rects:
        pos, size = P((u0 + u1) / 2, (v0 + v1) / 2), S(u1 - u0, v1 - v0, .4)
        box('Masonry', pos, size, upper, .014)
        collision(pos, size)
        # Окрашенная панель снизу отделена швом; кладка или побелка видна над ней.
        if v0 < band:
            bv = min(v1, band)
            box('Painted dado', P((u0 + u1) / 2, (v0 + bv) / 2), S(u1 - u0 + .009, bv - v0, .409), lower, .005)
        if v0 < .26:
            pv = min(v1, .26)
            box('Damp plinth', P((u0 + u1) / 2, (v0 + pv) / 2), S(u1 - u0 + .04, pv - v0, .44), 'DampConcrete', .005)
    for idx, (c, w, bottom, top, kind) in enumerate(sorted(openings)):
        lo, hi = c - w / 2, c + w / 2
        if kind == 'door':
            for u in (lo, hi):
                box('Steel doorway liner', P(u, 1.14), S(.11, 2.28, .46), 'BareSteel', .007)
            box('Doorway lintel plate', P(c, top + .04), S(w + .2, .08, .46), 'BareSteel', .006)
        else:
            window(P, S, name, lo, hi, bottom, top, idx + len(name))
    export('Wall_' + name)


def walls() -> None:
    door = lambda c: (c, 2.0, 0.0, 2.3, 'door')
    win = lambda c, w=1.4, b=1.3, t=2.7: (c, w, b, t, 'window')
    # Наружные стены котельной — красный кирпич; перегородки — побелённый кирпич.
    wall('North', (-18, -11), (18, -11), 5, [win(-6.9, 1.3, 3.0, 4.6), win(6.9, 1.3, 3.0, 4.6), win(12.0)])
    wall('West', (-18, -11), (-18, 7), 3.25, [win(-5.9, 1.2), win(-1.0), win(5.6)])
    wall('East', (18, -11), (18, 7), HALL_H, [door(STORAGE_DOOR_Z)])
    for side, x in [('West', -8), ('East', 8)]:
        for room, z0, z1, d in [('Living', -11, -5, -6.8), ('Trader', -5, 1, -2), ('Armory', 1, 7, 4)]:
            wall(side + room, (x, z0), (x, z1), 3.25, [door(d)], upper='Whitewash')
    for side, x0, x1 in [('West', -18, -8), ('East', 8, 18)]:
        for name, z in [('NorthDivide', -5), ('MidDivide', 1)]:
            wall(side + name, (x0, z), (x1, z), 3.25, upper='Whitewash')
    wall('WestSouth', (-18, 7), (-8, 7), 3.25, [win(-11.8)])
    wall('EastSouth', (8, 7), (18, 7), 3.25, [win(17.0, 1.2)])
    wall('EntryWest', (-4, 8), (-4, 12), 3.25)
    wall('EntryEast', (4, 8), (4, 12), 3.25)
    wall('EntrySouth', (-4, 12), (4, 12), 3.25)
    wall('BaySouthWest', (-8, 8), (-4, 8), 3.25)
    wall('BaySouthEast', (4, 8), (8, 8), 3.25)
    wall('HubWestReturn', (-8, 7), (-8, 8), 3.25)
    wall('HubEastReturn', (8, 7), (8, 8), 3.25)
    # Котельный зал: высокие окна под потолком над котлами и вдоль тира.
    wall('HallNorth', (HALL_X0, HALL_Z0), (HALL_X1, HALL_Z0), HALL_H,
         [win(x, 2.4, 5.3, 7.4) for x in (22.0, 28.0, 41.0, 55.0, 59.5)], lower='PeelingPaint', band=1.8)
    wall('HallSouth', (HALL_X0, HALL_Z1), (HALL_X1, HALL_Z1), HALL_H,
         [win(x, 2.0, 2.6, 6.6) for x in (27.0, 33.0, 39.0, 45.0, 51.0, 57.0)], lower='PeelingPaint', band=1.8)
    wall('HallEast', (HALL_X1, HALL_Z0), (HALL_X1, HALL_Z1), HALL_H, lower='PeelingPaint', band=1.8)


def hall_shell() -> None:
    cx, cz = (HALL_X0 + HALL_X1) / 2 + .2, (HALL_Z0 + HALL_Z1) / 2
    w, d = HALL_X1 - HALL_X0 + .4, HALL_Z1 - HALL_Z0
    begin()
    box('Hall floor', (cx, -.10, cz), (w, .2, d), 'IndustrialConcreteFloor', .009)
    collision((cx, -.10, cz), (w, .2, d))
    export('Floor_BoilerHall')
    begin()
    box('Roof slab', (cx, HALL_H + .1, cz), (w, .2, d), 'RawConcrete', .008)
    collision((cx, HALL_H + .1, cz), (w, .2, d))
    # Фермы покрытия: нижний и верхний пояс, стойки и раскосы; прогоны поверх.
    bottom, top = HALL_H - 1.1, HALL_H - .06
    for x in (21.5, 27.5, 33.0, 40.0, 45.5, 50.0, 56.5):
        box('Truss bottom chord', (x, bottom, cz), (.14, .16, d - .4), 'PaintedSteel', .01)
        box('Truss top chord', (x, top, cz), (.14, .12, d - .4), 'PaintedSteel', .01)
        n = 9
        for k in range(n + 1):
            z = HALL_Z0 + .2 + k * (d - .4) / n
            cyl('Truss post', (x, bottom, z), (x, top, z), .04, 'PaintedSteel', verts=10)
            if k < n:
                z2 = HALL_Z0 + .2 + (k + 1) * (d - .4) / n
                a, b = ((x, bottom, z), (x, top, z2)) if k % 2 == 0 else ((x, top, z), (x, bottom, z2))
                cyl('Truss diagonal', a, b, .035, 'PaintedSteel', verts=10)
    for z in [HALL_Z0 + .6 + i * 2.9 for i in range(7)]:
        box('Roof purlin', (cx, HALL_H - .02, z), (w - .4, .12, .1), 'BareSteel', .006)
    export('Ceiling_BoilerHall')


# --- Котёл: топка в обшивке, верхний барабан в изоляции, горелка, газоход до кровли ----------------
def boiler() -> None:
    begin()
    L, W = BOILER_L, BOILER_W
    box('Boiler foundation', (0, .15, 0), (L + .7, .3, W + .7), 'RawConcrete', .03)
    box('Furnace casing', (0, 1.95, 0), (L, 3.3, W), 'BoilerSteel', .06)
    # шов обшивки каждые 1.1 м и два пояса жёсткости
    x = -L / 2 + 1.1
    while x < L / 2 - .3:
        for side in (-1, 1):
            box('Casing panel seam', (x, 1.95, side * (W / 2 + .012)), (.05, 3.2, .026), 'BoilerSteel', .008)
        x += 1.1
    for y in (1.15, 2.55):
        for side in (-1, 1):
            box('Stiffener band', (0, y, side * (W / 2 + .02)), (L + .04, .09, .04), 'BareSteel', .01)
    box('Casing roof', (0, 3.63, 0), (L + .04, .06, W + .04), 'BareSteel', .01)
    for xs in (-2.7, 0, 2.7):
        box('Drum saddle', (xs, 3.82, 0), (.32, .32, 1.15), 'BareSteel', .02)
    cyl('Upper drum cladding', (-L / 2 + .45, 4.45, 0), (L / 2 - .45, 4.45, 0), .62, 'DirtyAluminum', verts=32)
    for end, sign in ((-L / 2 + .45, -1), (L / 2 - .45, 1)):
        cyl('Drum dished head', (end, 4.45, 0), (end + sign * .22, 4.45, 0), .62, 'DirtyAluminum', r2=.42, verts=32)
    xb = -L / 2 + .9
    while xb < L / 2 - .5:
        cyl('Cladding band', (xb - .012, 4.45, 0), (xb + .012, 4.45, 0), .632, 'BareSteel', verts=32)
        xb += .8
    for xs in (-1.6, 1.4):
        cyl('Safety valve body', (xs, 5.05, 0), (xs, 5.42, 0), .075, 'RedPaint', verts=16)
        cyl('Safety valve lever', (xs, 5.38, 0), (xs + .55, 5.38, 0), .016, 'BareSteel', verts=8)
        cyl('Lever weight', (xs + .5, 5.30, 0), (xs + .5, 5.40, 0), .06, 'BareSteel', verts=12)
    # водоуказательные стёкла на торце барабана
    for z in (-.32, .32):
        cyl('Gauge glass column', (-L / 2 + .15, 4.1, z), (-L / 2 + .15, 4.8, z), .025, 'Glass', verts=10)
        for y in (4.1, 4.8):
            cyl('Gauge cock', (-L / 2 + .15, y, z), (-L / 2 + .03, y, z), .03, 'BareSteel', verts=10)
    # фронт: плита, горелка с вентилятором, газовая линия, гляделки, манометры
    fx = -L / 2
    box('Front plate', (fx - .06, 1.95, 0), (.12, 3.3, W + .1), 'PaintedSteel', .02)
    box('Burner mounting flange', (fx - .17, 1.5, 0), (.08, 1.05, 1.05), 'BareSteel', .02)
    cyl('Burner housing', (fx - .2, 1.5, 0), (fx - .95, 1.5, 0), .38, 'OchreSteel', verts=28)
    cyl('Burner fan motor', (fx - .95, 1.5, 0), (fx - 1.35, 1.5, 0), .22, 'BoilerSteel', verts=24)
    cyl('Air damper box', (fx - .55, 1.88, 0), (fx - .55, 2.15, 0), .18, 'OchreSteel', verts=16)
    curve('Gas supply line', [(fx - .6, .3, 1.35), (fx - .6, 1.5, 1.35), (fx - .6, 1.5, .4)], .05, 'OchreSteel')
    for y in (.8, 1.2):
        cyl('Gas valve body', (fx - .6, y - .07, 1.35), (fx - .6, y + .07, 1.35), .08, 'OchreSteel', verts=16)
        cyl('Gas valve handle', (fx - .6, y, 1.35), (fx - .82, y, 1.35), .015, 'RedPaint', verts=8)
    for z in (-.85, .85):
        box('Inspection door', (fx - .15, 2.85, z), (.07, .52, .52), 'BareSteel', .02)
        cyl('Inspection door wing nut', (fx - .19, 2.85, z), (fx - .26, 2.85, z), .05, 'BareSteel', verts=12)
        cyl('Sight glass', (fx - .19, 2.4, z), (fx - .23, 2.4, z), .045, 'Glass', verts=16)
    for z in (-.9, 0, .9):
        cyl('Pressure gauge case', (fx - .13, 3.3, z), (fx - .21, 3.3, z), .11, 'BareSteel', verts=24)
        cyl('Pressure gauge dial', (fx - .212, 3.3, z), (fx - .218, 3.3, z), .095, 'Paper', verts=24)
        cyl('Gauge siphon', (fx - .17, 3.18, z), (fx - .17, 3.0, z), .012, 'BareSteel', verts=8)
    # газоход: патрубок сзади, стояк до кровли с фланцами и растяжками
    rx = L / 2 + .5
    box('Flue outlet', (rx, 2.9, 0), (1.0, 1.05, 1.05), 'FlueRust', .03)
    box('Flue riser', (rx, (3.4 + HALL_H) / 2, 0), (.95, HALL_H - 3.4, .95), 'FlueRust', .03)
    y = 3.6
    while y < HALL_H - .3:
        box('Duct flange', (rx, y, 0), (1.06, .06, 1.06), 'BareSteel', .01)
        y += 1.2
    cyl('Explosion relief cap', (rx + .53, 2.9, 0), (rx + .62, 2.9, 0), .3, 'BareSteel', verts=20)
    # лестница и ограждение площадки обслуживания на крыше топки
    lz = W / 2 + .35
    for dz in (-.22, .22):
        cyl('Ladder stile', (fx + .7, .3, lz + dz), (fx + .7, 4.65, lz + dz), .025, 'PaintedSteel', verts=10)
    y = .55
    while y < 3.7:
        cyl('Ladder rung', (fx + .7, y, lz - .22), (fx + .7, y, lz + .22), .016, 'BareSteel', verts=8)
        y += .3
    for side in (-1, 1):
        zz = side * (W / 2 - .05)
        xs = -L / 2 + .2
        while xs <= L / 2 - .1:
            cyl('Platform rail post', (xs, 3.66, zz), (xs, 4.72, zz), .022, 'OchreSteel', verts=8)
            xs += 1.3
        curve('Platform top rail', [(-L / 2 + .2, 4.72, zz), (L / 2 - .1, 4.72, zz)], .025, 'OchreSteel')
        curve('Platform knee rail', [(-L / 2 + .2, 4.2, zz), (L / 2 - .1, 4.2, zz)], .018, 'OchreSteel')
    face('Boiler nameplate', [(fx - .125, 2.2, -.55), (fx - .125, 2.2, .55), (fx - .125, 2.42, .55), (fx - .125, 2.42, -.55)], 'Labels', [(0, 0), (1, 0), (1, .125), (0, .125)])
    collision((0, 1.95, 0), (L + .25, 3.9, W + .25))
    collision((0, 4.45, 0), (L - .6, 1.3, 1.3))
    collision((rx, HALL_H / 2 + 1.4, 0), (1.06, HALL_H - 2.8, 1.06))
    collision((fx - .7, 1.5, 0), (1.3, .9, .9))
    export('Boiler')


def pump() -> None:
    begin()
    box('Pump plinth', (0, .1, 0), (1.15, .2, .62), 'RawConcrete', .02)
    box('Base frame', (0, .24, 0), (1.05, .08, .48), 'BoilerSteel', .01)
    cyl('Motor body', (-.48, .5, 0), (.02, .5, 0), .2, 'ButtonGreen', verts=24)
    for i in range(10):
        a = i * math.tau / 10
        cyl('Motor cooling fin', (-.46, .5 + .205 * math.sin(a), .205 * math.cos(a)), (-.06, .5 + .205 * math.sin(a), .205 * math.cos(a)), .012, 'ButtonGreen', verts=6)
    cyl('Fan cowl', (-.48, .5, 0), (-.62, .5, 0), .19, 'BareSteel', verts=24)
    cyl('Coupling guard', (.02, .5, 0), (.2, .5, 0), .12, 'OchreSteel', verts=16)
    cyl('Volute', (.2, .5, 0), (.42, .5, 0), .26, 'BoilerSteel', verts=28)
    cyl('Suction branch', (.42, .5, 0), (.6, .5, 0), .1, 'BoilerSteel', verts=16)
    cyl('Discharge branch', (.3, .5, 0), (.3, 1.05, 0), .085, 'BoilerSteel', verts=16)
    cyl('Discharge flange', (.3, 1.05, 0), (.3, 1.09, 0), .14, 'BareSteel', verts=16)
    cyl('Gauge stem', (.3, .9, 0), (.3, .9, .16), .012, 'BareSteel', verts=8)
    cyl('Gauge', (.3, .9, .16), (.3, .9, .2), .055, 'Paper', verts=16)
    collision((0, .55, 0), (1.25, 1.1, .64))
    export('CirculationPump')


def kip_panel() -> None:
    begin()
    box('Panel cabinet', (0, 1.05, 0), (1.6, 2.1, .45), 'BoilerSteel', .02)
    box('Panel face', (0, 1.25, .235), (1.5, 1.2, .02), 'PaintedSteel', .006)
    for i, x in enumerate((-.55, -.2, .15, .5)):
        cyl('Recorder dial', (x, 1.55, .245), (x, 1.55, .29), .12, 'BareSteel', verts=24)
        cyl('Dial face', (x, 1.55, .292), (x, 1.55, .296), .1, 'Paper', verts=24)
        cyl('Selector knob', (x, 1.12, .245), (x, 1.12, .28), .03, 'Rubber', verts=12)
        cyl('Pilot lamp', (x, .92, .245), (x, .92, .265), .022, 'ButtonRed' if i % 2 else 'ButtonGreen', verts=12)
    box('Mnemonic strip', (0, 1.78, .246), (1.4, .05, .006), 'IndustrialTrim', 0)
    face('Panel label', [(-.4, 1.9, .247), (.4, 1.9, .247), (.4, 1.98, .247), (-.4, 1.98, .247)], 'Labels', [(0, .75), (1, .75), (1, .875), (0, .875)])
    collision((0, 1.05, 0), (1.6, 2.1, .46))
    export('KipPanel')


# --- Зал: магистрали, ограждение котлов, тир (рубеж, кабины, направляющие, улавливатель) ---------
def gate_valve(at, axis_y=True) -> None:
    x, y, z = at
    cyl('Gate valve body', (x, y - .16, z), (x, y + .16, z), .17, 'RedPaint', verts=16)
    cyl('Valve bonnet', (x, y, z), (x + .45, y, z), .06, 'RedPaint', verts=12)
    pts = [(x + .47, y + .2 * math.cos(i * math.tau / 24), z + .2 * math.sin(i * math.tau / 24)) for i in range(25)]
    curve('Valve handwheel', pts, .018, 'RedPaint')
    for a in (0, 120, 240):
        r = math.radians(a)
        cyl('Handwheel spoke', (x + .47, y, z), (x + .47, y + .19 * math.cos(r), z + .19 * math.sin(r)), .012, 'RedPaint', verts=6)


def hall_structure() -> None:
    begin()
    zw = HALL_Z0 + .55
    # подающая и обратная магистрали вдоль северной стены, в изоляции под металлом
    for y, r in ((6.0, .17), (6.55, .15)):
        curve('Header pipe', [(19.0, y, zw), (57.5, y, zw)], r, 'DirtyAluminum')
        x = 19.6
        while x < 57.4:
            cyl('Cladding seam', (x - .01, y, zw), (x + .01, y, zw), r + .012, 'BareSteel', verts=20)
            x += 1.0
        x = 20.0
        while x < 57.4:
            box('Pipe wall bracket', (x, y - r - .06, HALL_Z0 + .32), (.08, .08, .5), 'BareSteel', .006)
            x += 3.0
    for bx, bz in BOILERS:
        for dx, y in ((-2.4, 6.55), (2.2, 6.0)):
            curve('Boiler riser', [(bx + dx, 5.05, bz), (bx + dx, y, bz), (bx + dx, y, zw)], .11, 'DirtyAluminum')
            gate_valve((bx + dx, 5.55, bz))
    # спуск магистралей к насосам в северо-западном углу
    for y, dz in ((6.0, 0.0), (6.55, .45)):
        curve('Header drop', [(19.0, y, zw + dz), (19.0, 1.5, zw + dz), (PUMPS[0][0] + .3, 1.5, zw + dz)], .13, 'DirtyAluminum')
    gate_valve((19.0, 3.0, zw))
    gate_valve((19.0, 3.4, zw + .45))
    for px, pz in PUMPS:
        curve('Pump connection', [(px + .3, 1.09, pz), (px + .3, 1.5, pz), (px + .3, 1.5, zw)], .085, 'BoilerSteel')
    # ограждение полосы котлов от тира, жёлтое
    zr = -5.75
    x = 25.4
    while x <= 61.5:
        cyl('Guard rail post', (x, 0, zr), (x, 1.1, zr), .03, 'OchreSteel', verts=10)
        x += 1.5
    for y in (1.1, .55):
        curve('Guard rail', [(25.4, y, zr), (61.6, y, zr)], .028, 'OchreSteel')
    collision((43.5, .55, zr), (36.2, 1.1, .08))
    # огневой рубеж: стойка с деревянной столешницей, кабины между дорожками
    zc0, zc1 = DIVIDERS[0], DIVIDERS[-1]
    box('Firing counter top', (COUNTER_X, .925, (zc0 + zc1) / 2), (.62, .05, zc1 - zc0), 'OldWood', .012)
    box('Counter front skirt', (COUNTER_X + .29, .55, (zc0 + zc1) / 2), (.03, .7, zc1 - zc0), 'PaintedSteel', .006)
    z = zc0 + .1
    while z <= zc1:
        for dx in (-.26, .26):
            box('Counter leg', (COUNTER_X + dx, .45, z), (.05, .9, .05), 'PaintedSteel', .006)
        z += 1.2
    collision((COUNTER_X, .475, (zc0 + zc1) / 2), (.62, .95, zc1 - zc0))
    for zd in DIVIDERS:
        box('Booth divider panel', (23.95, 1.05, zd), (1.9, 1.95, .05), 'OldWood', .01)
        box('Divider acoustic pad', (23.95, 1.25, zd), (1.7, 1.3, .1), 'Canvas', .03)
        cyl('Divider post front', (24.9, 0, zd), (24.9, 2.05, zd), .03, 'PaintedSteel', verts=10)
        cyl('Divider post back', (23.0, 0, zd), (23.0, 2.05, zd), .03, 'PaintedSteel', verts=10)
        collision((23.95, 1.05, zd), (1.9, 2.1, .12))
    # жёлтая черта рубежа и разметка дистанций на полу
    face('Firing line paint', [(FIRING_X - .05, .004, zc1), (FIRING_X + .05, .004, zc1), (FIRING_X + .05, .004, zc0), (FIRING_X - .05, .004, zc0)], 'IndustrialTrim', [(0, .5), (12, .5), (12, .625), (0, .625)])
    for dist in (5, 10, 15, 20, 25, 30):
        box('Distance stripe', (FIRING_X + dist, .003, (zc0 + zc1) / 2), (.05, .006, zc1 - zc0), 'Paper', 0)
    # подвесные направляющие бумажных мишеней и напольные рельсы манекенов
    for z, kind in LANES:
        if kind == 'paper':
            cx = (RAIL_X0 + RAIL_X1) / 2
            box('Rail I-beam web', (cx, RAIL_Y, z), (RAIL_X1 - RAIL_X0, .18, .014), 'PaintedSteel', .003)
            for dy in (-.09, .09):
                box('Rail I-beam flange', (cx, RAIL_Y + dy, z), (RAIL_X1 - RAIL_X0, .014, .12), 'PaintedSteel', .003)
            x = RAIL_X0 + .4
            while x < RAIL_X1:
                cyl('Rail hanger rod', (x, RAIL_Y + .1, z), (x, HALL_H - 1.1, z), .014, 'BareSteel', verts=8)
                x += 4.0
            box('Rail end stop', (RAIL_X1 + .05, RAIL_Y - .02, z), (.08, .22, .16), 'RedPaint', .01)
        else:
            for dz in (-.28, .28):
                box('Floor rail', ((RAIL_X0 + RAIL_X1) / 2, .018, z + dz), (RAIL_X1 - RAIL_X0, .036, .06), 'BareSteel', .004)
            x = RAIL_X0 + .3
            while x < RAIL_X1:
                box('Rail sleeper', (x, .006, z), (.12, .012, .8), 'Rubber', .002)
                x += 1.5
    # предохранительные экраны над дорожками: дерево к стрелку, сталь за ним
    for bx in (36.0, 48.0):
        for y0, y1 in ((3.4, 4.6),):
            face('Baffle timber face', [(bx, y0, zc1), (bx, y0, zc0), (bx + .7, y1, zc0), (bx + .7, y1, zc1)], 'OldWood')
            face('Baffle steel back', [(bx + .02, y0, zc0), (bx + .02, y0, zc1), (bx + .72, y1, zc1), (bx + .72, y1, zc0)], 'RustedSteel')
            for z in (zc0 + .3, (zc0 + zc1) / 2, zc1 - .3):
                cyl('Baffle hanger', (bx + .35, (y0 + y1) / 2, z), (bx + .35, HALL_H - 1.1, z), .016, 'BareSteel', verts=8)
    # пулеулавливатель: наклонные стальные листы, резиновая крошка в блоках, мешки с песком
    bx0 = 59.1
    for z0 in [zc0 + i * 2.0 for i in range(6)]:
        z1 = min(z0 + 2.0, zc1)
        face('Deflector plate', [(bx0, .9, z1), (bx0, .9, z0), (bx0 + 2.3, 5.2, z0), (bx0 + 2.3, 5.2, z1)], 'BareSteel')
    for i in range(6):
        z = zc0 + .5 + i * 2.0
        box('Rubber granulate block', (60.4, .45, z), (1.9, .9, 1.9), 'Rubber', .06)
    collision((60.6, 2.6, (zc0 + zc1) / 2), (3.2, 5.2, zc1 - zc0))
    for row, y in enumerate((.14, .4, .66)):
        z = zc0 + .25 + (row % 2) * .3
        while z < zc1 - .2:
            box('Sandbag', (58.75, y, z), (.42, .26, .6), 'Canvas', .1)
            z += .62
    collision((58.75, .4, (zc0 + zc1) / 2), (.45, .8, zc1 - zc0))
    # порог прохода из склада в зал
    box('Hall door threshold', (18.0, .007, STORAGE_DOOR_Z), (1.1, .014, 2.0), 'BareSteel', .003)
    export('HallStructure')


# --- Пульт дорожки, тележки мишеней, шкаф стойки тира -------------------------------------------
def range_console() -> None:
    # Лицом к стрелку (+Z), три грибковые кнопки: ближе — жёлтая, сменить лист — красная,
    # дальше — зелёная; между ними окно табло дистанции.
    begin()
    box('Console housing', (0, .07, 0), (.98, .14, .3), 'PaintedSteel', .02)
    box('Sloped face', (0, .145, .02), (.95, .02, .27), 'Rubber', .008)
    for x, mat in ((-.36, 'ButtonYellow'), (0.0, 'ButtonRed'), (.36, 'ButtonGreen')):
        cyl('Button collar', (x, .15, .05), (x, .175, .05), .055, 'BareSteel', verts=20)
        cyl('Mushroom button', (x, .175, .05), (x, .215, .05), .045, mat, verts=20)
    box('Display window', (-.18, .158, -.07), (.2, .012, .08), 'Screen', .004)
    box('Display window right', (.18, .158, -.07), (.2, .012, .08), 'Screen', .004)
    export('RangeConsole')


def carrier_paper() -> None:
    # Тележка на нижней полке двутавра, тяга вниз и планка с зажимами листа (верх листа — 1.97 м).
    begin()
    for dx in (-.11, .11):
        for dz in (-.075, .075):
            cyl('Trolley wheel', (dx, RAIL_Y - .07, dz - .02), (dx, RAIL_Y - .07, dz + .02), .045, 'Rubber', verts=16)
    box('Trolley body', (0, RAIL_Y - .16, 0), (.32, .1, .2), 'OchreSteel', .015)
    cyl('Drop rod', (0, RAIL_Y - .21, 0), (0, 2.02, 0), .014, 'BareSteel', verts=8)
    box('Clip bar', (0, 1.995, 0), (.66, .04, .03), 'BareSteel', .006)
    for x in (-.25, .25):
        box('Bulldog clip', (x, 1.975, .02), (.06, .05, .03), 'BareSteel', .004)
    export('RangeCarrierPaper')


def carrier_floor() -> None:
    # Тележка манекена на напольных рельсах: рама, колёса по рельсам, площадка и стойка.
    begin()
    box('Cart frame', (0, .11, 0), (.62, .07, .7), 'OchreSteel', .015)
    for dx in (-.24, .24):
        for dz in (-.28, .28):
            cyl('Cart wheel', (dx - .04, .07, dz), (dx + .04, .07, dz), .055, 'BareSteel', verts=16)
    box('Stand plate', (0, .16, 0), (.5, .03, .5), 'Rubber', .01)
    box('Front armour plate', (0, .3, .32), (.6, .3, .02), 'BareSteel', .006)
    export('RangeCarrierFloor')


def gun_cabinet() -> None:
    # Настенный шкаф тира без дверец: щит, полки-ложементы под стволы, полка с наушниками.
    begin()
    box('Cabinet back', (0, 1.25, -.05), (2.4, 2.1, .04), 'OldWood', .008)
    box('Cabinet frame top', (0, 2.32, .06), (2.5, .08, .26), 'PaintedSteel', .01)
    box('Cabinet frame bottom', (0, .18, .06), (2.5, .36, .26), 'PaintedSteel', .01)
    for x in (-1.22, 1.22):
        box('Cabinet side', (x, 1.25, .06), (.06, 2.2, .26), 'PaintedSteel', .01)
    for x in (-.85, -.45, -.05, .35, .75):
        for y in (.48, 1.62):
            curve('Barrel cradle', [(x - .05, y, -.02), (x - .05, y, .1), (x + .05, y, .1), (x + .05, y, -.02)], .012, 'Rubber')
    box('Pistol shelf', (0, 1.95, .06), (2.3, .03, .22), 'OldWood', .006)
    face('Cabinet label', [(-.5, 2.2, .1), (.5, 2.2, .1), (.5, 2.28, .1), (-.5, 2.28, .1)], 'Labels', [(0, .5), (1, .5), (1, .625), (0, .625)])
    collision((0, 1.2, .05), (2.5, 2.4, .3))
    export('RangeGunCabinet')


if __name__ == '__main__':
    previous = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    walls()
    hall_shell()
    boiler()
    pump()
    kip_panel()
    hall_structure()
    range_console()
    carrier_paper()
    carrier_floor()
    gun_cabinet()
    kit.signs(range(13, 16))
    previous.update(kit.ASSETS)
    (OUT/'manifest.json').write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'boiler_layout.json').write_text(json.dumps(LAYOUT, ensure_ascii=False, indent=2), encoding='utf-8')
    for o in bpy.context.scene.objects:
        o.hide_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC/'shelter_boiler.blend'))
    print('BOILER_DONE', len(kit.ASSETS), sum(v['triangles'] for v in kit.ASSETS.values()), flush=True)
