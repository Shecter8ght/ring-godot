"""Котельная зоны 5 снаружи: выход на поверхность и оболочка здания. bpy → GLB (kit — как у остального
убежища: фаски, метрические UV, один mesh на сборку, упрощённые коллизии).

Решение владельца (2026-10-11): запечённого света нет, убежище — здание на открытой местности с
настоящими окнами; в рейд выходят пешком — массивная дверь, коридор, лестница на поверхность, двор.
Котельная полуподвальная: пол на отметке 0, земля снаружи — GROUND (подоконники чуть выше земли).

Собирает:
  Wall_EntrySouth   — торцевая стена тамбура с проёмом под дверь (была глухая);
  BlastDoorFrame / BlastDoorLeaf — прежняя гермодверь, разделённая на раму и створку (створка
                      поворачивается в игре; ось петель — в нуле створки);
  ExitCorridor      — коридор от двери и открытый лестничный спуск с подпорными стенками и перилами;
  ShellUpper        — кирпичные надстройки над центральным залом и северной галереей (раньше между
                      кровлями комнат и перекрытием зала были щели в пустоту);
  FencePanel, YardGate — бетонный забор двора и распахнутые ворота.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_shelter_exterior.py
Затем: tools/godot.cmd --headless --import; tools/godot.cmd --headless res://tools/author_shelter_exterior.tscn
Координаты — Godot X/Y/Z (м), как в kit.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_shelter_assets as kit
import build_shelter_boiler as boiler

OUT = kit.OUT
SRC = kit.SRC
box, cyl, curve, face, begin, collision, export = kit.box, kit.cyl, kit.curve, kit.face, kit.begin, kit.collision, kit.export

# --- Раскладка (её же читает tools/author_shelter_exterior.gd) -----------------------------------
GROUND = 1.2                  # отметка земли над полом котельной
DOOR_Z = 11.72                # плоскость рамы гермодвери (как стояла)
COR_W = 3.0                   # коридор в свету
COR_Z0, COR_Z1 = 12.2, 18.2   # коридор под крышей
COR_H = 2.7
STEPS = 7
STEP_RISE = GROUND / STEPS
STEP_RUN = 0.30
STAIR_Z0 = 18.6
STAIR_Z1 = STAIR_Z0 + STEPS * STEP_RUN
WALL_T = 0.3
LAYOUT = {
    'ground': GROUND, 'door_z': DOOR_Z, 'door_hinge_x': 1.09,
    'corridor': {'w': COR_W, 'z0': COR_Z0, 'z1': COR_Z1, 'h': COR_H},
    'stairs': {'z0': STAIR_Z0, 'z1': STAIR_Z1, 'steps': STEPS},
    'fence': {'panel_w': 2.5, 'panel_h': 2.3},
    'gate': {'w': 4.4},
}


def entry_wall() -> None:
    # проём чуть уже рамы: кромки закрыты её стойками
    boiler.wall('EntrySouth', (-4, 12), (4, 12), 3.25, [(0, 2.2, 0.0, 2.28, 'door')])


def door_frame() -> None:
    begin()
    for x in [-1.17, 1.17]:
        box('Massive jamb', (x, 1.2, 0), (.18, 2.4, .35), 'BareSteel', .018)
    box('Door lintel', (0, 2.35, 0), (2.52, .18, .35), 'BareSteel', .014)
    # порог: стальная полоса заподлицо с полом
    box('Door sill plate', (0, .012, 0), (2.16, .024, .34), 'BareSteel', .004)
    for x in [-1.17, 1.17]:
        collision((x, 1.2, 0), (.18, 2.4, .35))
    collision((0, 2.35, 0), (2.52, .18, .35))
    export('BlastDoorFrame')


def door_leaf() -> None:
    """Створка: ноль — ось петель (правый край, со стороны коридора). Полотно уходит в −X."""
    begin()
    hx = 1.09

    def P(x, y, z):
        return (x - hx, y, z)

    box('Sealed leaf', P(0, 1.14, 0), (2.18, 2.25, .18), 'PaintedSteel', .018)
    for y in [.25, .7, 1.2, 1.7, 2.1]:
        box('Leaf stiffener', P(0, y, .11), (1.99, .07, .055), 'BareSteel', .005)
    for x in [-.7, 0, .7]:
        box('Vertical stiffener', P(x, 1.2, .12), (.07, 2, .06), 'PaintedSteel', .006)
    for y in [.4, 1.3, 2.1]:
        cyl('Hinge', P(1.03, y - .085, .1), P(1.03, y + .085, .1), .065, 'BareSteel')
    # штурвалы с обеих сторон: снаружи (в коридор) и изнутри тамбура
    for z, colour in [(.24, 'RedPaint'), (-.2, 'RedPaint')]:
        pts = [P(-.62 + .23 * math.cos(i * math.tau / 32), 1.18 + .23 * math.sin(i * math.tau / 32), z) for i in range(33)]
        curve('Handwheel', pts, .025, colour)
        for a in [0, 90, 180, 270]:
            cyl('Wheel spoke', P(-.62, 1.18, z), P(-.62 + .21 * math.cos(math.radians(a)), 1.18 + .21 * math.sin(math.radians(a)), z), .015)
        cyl('Wheel shaft', P(-.62, 1.18, 0), P(-.62, 1.18, z), .03, 'BareSteel')
    # засовы изнутри: две тяги к раме
    for y in [.75, 1.62]:
        box('Locking bar', P(-.25, y, -.115), (1.5, .05, .03), 'BareSteel', .006)
    face('Warning plaque', [P(.05, 1.75, .158), P(.85, 1.75, .158), P(.85, 1.89, .158), P(.05, 1.89, .158)], 'Labels', [(0, .5), (1, .5), (1, .625), (0, .625)])
    collision(P(0, 1.14, 0), (2.18, 2.25, .2))
    export('BlastDoorLeaf')


def corridor() -> None:
    begin()
    hw = COR_W / 2
    zc, zl = (COR_Z0 + COR_Z1) / 2, COR_Z1 - COR_Z0
    # пол коридора и площадка перед лестницей
    floor_z1 = STAIR_Z0
    box('Corridor floor', (0, -.10, (COR_Z0 + floor_z1) / 2), (COR_W + .6, .2, floor_z1 - COR_Z0), 'WetConcrete', .008)
    collision((0, -.10, (COR_Z0 + floor_z1) / 2), (COR_W + .6, .2, floor_z1 - COR_Z0))
    # стены коридора (под крышей) и подпорные стенки спуска (на 0.3 выше земли — отбойник)
    curb = GROUND + .3
    for sx in (-1, 1):
        x = sx * (hw + WALL_T / 2)
        box('Corridor wall', (x, COR_H / 2, zc), (WALL_T, COR_H, zl), 'RawConcrete', .012)
        collision((x, COR_H / 2, zc), (WALL_T, COR_H, zl))
        box('Corridor dado', (sx * (hw - .004), .75, zc), (.012, 1.5, zl), 'PaintedConcrete', .003)
        box('Damp plinth', (sx * (hw - .012), .13, (COR_Z0 + STAIR_Z1) / 2), (.03, .26, STAIR_Z1 - COR_Z0), 'DampConcrete', .004)
        zr0, zr1 = COR_Z1, STAIR_Z1 + .5
        box('Retaining wall', (x, curb / 2, (zr0 + zr1) / 2), (WALL_T, curb, zr1 - zr0), 'RawConcrete', .012)
        collision((x, curb / 2, (zr0 + zr1) / 2), (WALL_T, curb, zr1 - zr0))
        box('Retaining cap', (x, curb + .03, (zr0 + zr1) / 2), (WALL_T + .08, .06, zr1 - zr0 + .04), 'RawConcrete', .01)
        # перила из трубы над подпорной стенкой
        rail = curb + .75
        for z in [zr0 + .2 + k * (zr1 - zr0 - .4) / 3 for k in range(4)]:
            cyl('Rail post', (x, curb, z), (x, rail, z), .022, 'PaintedSteel', verts=10)
        cyl('Hand rail', (x, rail, zr0 + .1), (x, rail, zr1 - .1), .025, 'PaintedSteel', verts=12)
        cyl('Mid rail', (x, curb + .4, zr0 + .1), (x, curb + .4, zr1 - .1), .016, 'PaintedSteel', verts=10)
        # невидимая стенка по перилам: через них не перелезают
        collision((x, curb + .5, (zr0 + zr1) / 2), (.1, 1.0, zr1 - zr0))
    # перекрытие коридора с козырьком над порталом и балками
    box('Corridor roof', (0, COR_H + .1, zc + .15), (COR_W + 2 * WALL_T + .2, .2, zl + .5), 'RawConcrete', .01)
    collision((0, COR_H + .1, zc + .15), (COR_W + 2 * WALL_T + .2, .2, zl + .5))
    for z in [COR_Z0 + 1.0 + k * 2.0 for k in range(3)]:
        box('Roof beam', (0, COR_H - .12, z), (COR_W, .24, .2), 'RawConcrete', .01)
    box('Portal lintel', (0, COR_H - .2, COR_Z1 - .1), (COR_W, .4, .2), 'RawConcrete', .012)
    # кабель и труба вдоль стены
    cyl('Conduit', (-hw + .06, 2.25, COR_Z0 + .1), (-hw + .06, 2.25, COR_Z1 - .1), .02, 'GalvanizedSteel', verts=10)
    cyl('Heating pipe', (hw - .1, .45, COR_Z0 + .1), (hw - .1, .45, COR_Z1 - .1), .045, 'RustedSteel', verts=12)
    # трап у подножия лестницы: дождь сюда попадает
    box('Drain grate', (0, .006, STAIR_Z0 - .22), (.5, .012, .26), 'BareSteel', .003)
    # ступени: бетон с уголком по кромке
    for i in range(STEPS):
        top = (i + 1) * STEP_RISE
        z0 = STAIR_Z0 + i * STEP_RUN
        zlen = STAIR_Z1 + .5 - z0
        box('Stair step', (0, top / 2, z0 + zlen / 2), (COR_W, top, zlen), 'RawConcrete', .006)
        box('Step nosing', (0, top - .012, z0 + .02), (COR_W - .04, .024, .04), 'BareSteel', .004)
        collision((0, top / 2, z0 + STEP_RUN / 2 if i < STEPS - 1 else z0 + zlen / 2), (COR_W, top, STEP_RUN if i < STEPS - 1 else zlen))
    export('ExitCorridor')


def shell_upper() -> None:
    """Кирпичные надстройки: центральный зал (перекрытие 4.5) и северная галерея (5.0) выше комнат (3.25)."""
    begin()
    t = .3
    roof = 3.45                # верх плит над комнатами и тамбуром
    hub_top, gal_top = 4.7, 5.2
    for x in (-8, 8):
        box('Hub clerestory', (x, (roof + hub_top) / 2, 0), (t, hub_top - roof, 16), 'Brick', .012)
        box('Gallery parapet', (x, (roof + gal_top) / 2, -9.5), (t, gal_top - roof, 3), 'Brick', .012)
        box('Parapet cap', (x, hub_top + .04, 0), (t + .1, .08, 16.1), 'RawConcrete', .008)
    box('Hub clerestory south', (0, (roof + hub_top) / 2, 8), (16 + t, hub_top - roof, t), 'Brick', .012)
    box('Parapet cap south', (0, hub_top + .04, 8), (16.4, .08, t + .1), 'RawConcrete', .008)
    box('Gallery step', (0, (hub_top + gal_top) / 2, -8), (16 + t, gal_top - hub_top, t), 'Brick', .012)
    # кровельная стяжка: плиты перекрытий сверху — рубероид (тёмная плоскость чуть выше плит)
    for name, x, z, w, d, y in [('Hub', 0, 0, 16, 16, hub_top), ('Gallery', 0, -9.5, 16, 3, gal_top),
                                ('West', -13, -2, 10, 18, roof), ('East', 13, -2, 10, 18, roof), ('Entry', 0, 10, 8, 4, roof)]:
        box('Roofing felt ' + name, (x, y + .012, z), (w + .3, .024, d + .3), 'Rubber', .004)
    export('ShellUpper')


def fence_panel() -> None:
    """Плита железобетонного забора 2.5 × 2.3 м на «стакане»: рама и рельефные квадраты."""
    begin()
    w, h, t = 2.5, 2.3, .1
    box('Fence slab', (0, .25 + h / 2, 0), (w - .02, h, t), 'RawConcrete', .01)
    box('Fence frame top', (0, .25 + h - .07, 0), (w - .02, .14, t + .06), 'RawConcrete', .012)
    box('Fence frame foot', (0, .25 + .1, 0), (w - .02, .2, t + .06), 'RawConcrete', .012)
    for x in (-w / 2 + .08, w / 2 - .08):
        box('Fence frame side', (x, .25 + h / 2, 0), (.14, h, t + .06), 'RawConcrete', .012)
    cols, rows = 4, 3
    cw, rh = (w - .4) / cols, (h - .5) / rows
    for i in range(cols):
        for j in range(rows):
            cx = -w / 2 + .2 + (i + .5) * cw
            cy = .25 + .24 + (j + .5) * rh
            for z in (-1, 1):
                box('Fence relief', (cx, cy, z * (t / 2 + .012)), (cw - .12, rh - .12, .03), 'RawConcrete', .012)
    for x in (-w / 2 + .3, w / 2 - .3):
        box('Fence socket', (x, .14, 0), (.5, .28, .45), 'DampConcrete', .03)
    collision((0, .25 + h / 2, 0), (w, h + .5, t + .1))
    export('FencePanel')


def yard_gate() -> None:
    """Ворота двора: два столба и две распахнутые наружу створки из трубы и листа."""
    begin()
    w, h = LAYOUT['gate']['w'], 2.2
    for sx in (-1, 1):
        px = sx * (w / 2 + .09)
        box('Gate post', (px, h / 2 + .1, 0), (.18, h + .2, .18), 'BareSteel', .012)
        box('Gate post cap', (px, h + .22, 0), (.22, .04, .22), 'BareSteel', .006)
        collision((px, h / 2, 0), (.2, h + .4, .2))
        # створка распахнута наружу (+Z) на 105°: рисуем вдоль её собственной оси
        a = math.radians(105.0)
        lw = w / 2 - .04
        ux, uz = -sx * math.cos(a), math.sin(a)      # вдоль створки от петли

        def L(u, y, off=0.0, _px=px, _ux=ux, _uz=uz, _sx=sx):
            return (_px - _sx * .09 + _ux * u - _uz * off * _sx, y, _uz * u + _ux * off * _sx)

        for y in (.18, h - .02):
            cyl('Gate rail', L(.0, y), L(lw, y), .03, 'PaintedSteel', verts=10)
        for u in (.0, lw / 2, lw):
            cyl('Gate stile', L(u, .18), L(u, h - .02), .03, 'PaintedSteel', verts=10)
        cyl('Gate brace', L(.0, .18), L(lw, h - .02), .02, 'PaintedSteel', verts=10)
        # лист — узкими полосами (kit.box поворачивается только вокруг вертикали)
        yaw = math.degrees(math.atan2(-uz, ux))
        mid = L(lw / 2, (h + .16) / 2)
        box('Gate sheet', mid, (lw - .06, h - .3, .004), 'PaintedSteel', .001, yaw)
        collision(mid, (lw, h, .12), yaw)
    export('YardGate')


if __name__ == '__main__':
    previous = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    entry_wall()
    door_frame()
    door_leaf()
    corridor()
    shell_upper()
    fence_panel()
    yard_gate()
    previous.update(kit.ASSETS)
    (OUT / 'manifest.json').write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'exterior_layout.json').write_text(json.dumps(LAYOUT, ensure_ascii=False, indent=2), encoding='utf-8')
    for o in bpy.context.scene.objects:
        o.hide_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC / 'shelter_exterior.blend'))
    print('EXTERIOR_DONE', len(kit.ASSETS), sum(v['triangles'] for v in kit.ASSETS.values()), flush=True)
