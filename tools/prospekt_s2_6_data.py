"""«Проспект», «Ярус», редакция 3 — данные плана и рейдовой сцены (вызывается из tools/prospekt_patch.py).

Правит текстом (повтор не дублирует): data/blockouts/prospekt.json (места лута, маршруты проверки, место прогулки 7) и
scenes/levels/prospekt.tscn (ящики лута корпуса, посты, метки пролога). Подогнанные по физике места ящиков — в
tools/prospekt_s2_6_loot.json (их пишет tools/prospekt_s2_6_loot.py после перепечённой навигации); пока файла нет — ставятся
заготовки LOOT_MOVES.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "tools" / "prospekt_s2_6_loot.json"

# ящик: (старое место (x, y узла, z), заготовка нового (x, z, пол))
LOOT_MOVES: dict[str, tuple] = {
    "Loot_128": ((-136.1, 0.6, 64.0), (-134.0, 69.5, 0.0)), "Loot_129": ((-136.1, 0.6, 74.0), (-134.0, 76.0, 0.0)),
    "Loot_130": ((-130.1, 0.6, 64.0), (-128.0, 72.5, 0.0)), "Loot_131": ((-130.1, 0.6, 74.0), (-122.0, 69.5, 0.0)),
    "Loot_132": ((-124.1, 0.6, 64.0), (-122.0, 76.0, 0.0)), "Loot_133": ((-124.1, 0.6, 74.0), (-116.0, 72.5, 0.0)),
    "Loot_134": ((-78.1, 0.6, 64.0), (-104.0, 69.5, 0.0)), "Loot_135": ((-78.1, 0.6, 74.0), (-104.0, 76.0, 0.0)),
    "Loot_136": ((-72.1, 0.6, 64.0), (-98.0, 72.5, 0.0)), "Loot_137": ((-72.1, 0.6, 74.0), (-92.0, 69.5, 0.0)),
    "Loot_138": ((-84.1, 0.6, 64.0), (-92.0, 76.0, 0.0)), "Loot_139": ((-84.1, 0.6, 74.0), (-86.0, 72.5, 0.0)),
    "Loot_140": ((-130.0, 0.6, 56.0), (-99.8, 64.7, 0.0)), "Loot_141": ((-125.4, 0.6, 53.0), (-87.2, 64.7, 0.0)),
    "Loot_142": ((-77.4, 0.6, 53.0), (-76.0, 60.5, 0.0)), "Loot_143": ((-65.4, 0.6, 53.0), (-127.0, 60.5, 0.0)),
    "Loot_146": ((-140.0, 0.6, 75.0), (-139.5, 56.0, 0.0)), "Loot_148": ((-112.0, 0.6, 60.0), (-121.5, 64.8, 0.0)),
    "Loot_331": ((-122.293, 0.62, 51.293), (-137.5, 60.3, 0.0)), "Loot_332": ((-81.0, 0.62, 51.5), (-80.0, 60.3, 0.0)),
    "Loot_333": ((-116.0, 0.62, 51.5), (-70.0, 60.3, 0.0)),
    "Loot_334": ((-134.0, 0.62, 66.0), (-80.0, 69.5, 0.0)), "Loot_335": ((-128.0, 0.62, 74.0), (-80.0, 76.0, 0.0)),
    "Loot_336": ((-82.0, 0.62, 64.0), (-74.0, 72.5, 0.0)), "Loot_337": ((-76.0, 0.62, 72.0), (-86.0, 69.5, 0.0)),
    "Loot_342": ((-120.5, 6.6, 53.0), (-136.0, 52.2, 6.0)), "Loot_343": ((-95.0, 6.6, 53.0), (-127.0, 52.2, 6.0)),
    "Loot_344": ((-66.0, 7.5, 53.0), (-139.5, 58.0, 6.0)),
    "Loot_345": ((-138.0, 7.6, 64.0), (-138.0, 68.0, 6.0)), "Loot_346": ((-130.0, 7.6, 72.0), (-132.0, 72.2, 6.0)),
    "Loot_347": ((-121.0, 6.6, 77.0), (-121.0, 77.0, 6.0)),
    "Loot_348": ((-80.0, 6.6, 64.0), (-104.0, 72.0, 6.0)), "Loot_349": ((-70.5, 6.6, 74.0), (-75.0, 53.0, 6.0)),
}

NODE_MOVES = [
    ("Hall_Cart", "Vector3(-127, 0.05, 65.5)"), ("Hall_Till", "Vector3(-100.5, 0.05, 66.5)"),
    ("Yarus_Hall", "Vector3(-104, 0.05, 72)"), ("AI_Yarus_Hall", "Vector3(-104, 0.05, 72)"),
]

# ------------------------------------------------------------------------------------------------ маршруты
# часть «Яруса» в прологе: тамбур → вестибюль → турникеты → зал (проход между стеллажами) → приёмка (−100; 80)
PROLOGUE_MID = [[-108.0, 52.0], [-108.0, 58.0], [-113.0, 60.0], [-113.0, 66.0], [-110.0, 66.5], [-110.0, 78.6], [-100.0, 78.6], [-100.0, 79.0]]
ROUTE_STAFF = [[-96.0, 44.0], [-96.0, 46.0], [-96.0, 49.5], [-66.0, 49.5], [-66.0, 50.6], [-63.2, 50.6], [-63.2, 81.0], [-63.2, 82.5],
               [-71.5, 82.5], [-71.5, 85.85], [-67.9, 85.85], [-67.9, 87.4], [-67.9, 90.0], [-68.6, 92.0], [-68.6, 100.8], [-72.0, 100.8],
               [-75.0, 94.8], [-100.0, 94.8], [-100.0, 113.0], [-98.0, 115.0]]
def _stair_route(xa: float, xb: float, xn: float, head: list, tail: list) -> list:
    """Подъём по четырём маршам: колонка xa (F1, F3), колонка xb (F2, F4); заходить на марш — по оси колонки (поручни сбоку)."""
    return (head + [[xa, 56.0], [xa, 53.8], [xb, 53.8], [xb, 55.0], [xb, 57.0], [xb, 58.2], [xa, 58.2], [xa, 56.0], [xa, 53.8],
                    [xb, 53.8], [xb, 55.0], [xb, 57.0], [xb, 58.8]] + tail)


WEST_STAIR = _stair_route(-119.175, -121.125, -120.6, [[-108.0, 52.0], [-111.0, 56.0], [-116.0, 58.2], [-119.175, 58.2]], [[-119.0, 60.6]])
EAST_STAIR = _stair_route(-84.825, -82.875, -83.4, [[-108.0, 52.0], [-100.0, 56.0], [-90.0, 58.2], [-84.825, 58.2]], [[-84.0, 60.6]])
ROUTE_VERT = ([[-108.0, 40.0], [-108.0, 46.0]] + WEST_STAIR +
              [[-118.0, 62.8], [-66.0, 62.8], [-66.0, 64.5], [-64.0, 65.0], [-64.0, 66.8], [-64.0, 77.0], [-64.0, 79.0], [-70.0, 79.0],
               [-91.0, 79.0], [-91.0, 81.5], [-91.0, 86.0], [-91.0, 90.0],
               [-106.5, 90.0], [-106.5, 116.5], [-140.8, 116.5], [-140.8, 102.0], [-136.0, 102.0], [-136.0, 114.0], [-98.0, 114.0],
               [-98.0, 123.0], [-96.0, 127.0]])
ROUTE_PUBLIC = ([[-108.0, 40.0], [-108.0, 46.0]] + EAST_STAIR +
                [[-84.0, 62.8], [-129.0, 62.8], [-129.0, 68.0], [-129.0, 63.0], [-141.0, 62.5], [-143.7, 62.5], [-143.7, 64.5],
                 [-143.7, 68.8], [-143.7, 70.5], [-143.7, 72.0], [-143.7, 77.5], [-143.7, 79.0]])
ROUTE_LABELS = {
    "prologue": "пролог: кордон → кофейня → переход → «Ярус» (тамбур, вестибюль, турникеты, зал, приёмка) → склад → док → двор разгрузки → калитка → сквер → вагоны → тоннель",
    "prologue_staff": "пролог: тамбур «Яруса» → вестибюль → галерея → служебный коридор → ЛК-1 → служебный двор → склад → к доку",
    "yarus_vertical": "«Ярус»: тамбур → вестибюль → западная лестница → галерея 2 эт. → служебный коридор → коридор администрации → «к мосткам» → мостки → лестница на пол склада → док → двор",
    "yarus_public": "«Ярус»: вестибюль → восточная лестница → галерея 2 эт. → «Техно» → наружная западная лестница → земля"}


def _num(v: float) -> str:
    return repr(float(v))


def _pts(pts: list) -> str:
    return ",\n".join("    [%s, %s]" % (_num(a), _num(b)) for a, b in pts)


def _fmt(v: float) -> str:
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _targets() -> dict:
    """Новое место ящика: подогнанное по физике (prospekt_s2_6_loot.json) или заготовка."""
    snapped = json.loads(SNAP.read_text(encoding="utf-8")) if SNAP.exists() else {}
    out = {}
    for name, (old, cand) in LOOT_MOVES.items():
        s = snapped.get(name)
        out[name] = (float(s[0]), float(s[1]), float(s[2])) if s else (cand[0], cand[1], cand[2])
    return out


def plan_data(p=None) -> None:
    targets = _targets()
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = open(path, encoding="utf-8", newline="").read()
    # --- места лута плана: запись по старому месту (x, пол, z) → новое
    at_re = re.compile(r'"at": \[(-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\]')
    moved = 0
    for name, (old, _cand) in LOOT_MOVES.items():
        nx, nz, nf = targets[name]
        olds = [(old[0], old[1] - 0.6, old[2]), (_cand[0], _cand[2], _cand[1]), (nx, nf, nz)]     # прежнее, заготовка, уже поставленное
        done = False
        for m in at_re.finditer(text):
            x, y, z = (float(m.group(i)) for i in (1, 2, 3))
            if any(abs(x - o[0]) < 0.002 and abs(y - o[1]) < 0.002 and abs(z - o[2]) < 0.002 for o in olds):
                text = text[:m.start()] + '"at": [%s, %s, %s]' % (_fmt(nx), _fmt(nf), _fmt(nz)) + text[m.end():]
                moved += 1
                break
    # --- маршруты
    # пролог: середина «Яруса»
    if "[-113.0, 66.0]" not in text:
        rx = re.compile(r'\[-108\.0, 52\.0\],\n    \[-108\.0, 64\.0\],\n    \[-108\.0, 78\.0\],\n    \[-100\.0, 79\.0\]')
        text, n = rx.subn(lambda m: _pts(PROLOGUE_MID).lstrip(), text, count=1)
        if n != 1:
            raise SystemExit("prospekt.json: нет середины маршрута prologue")
    text = re.sub(r'("id": "prologue",\n   "label": )"[^"]*"', lambda m: m.group(1) + '"%s"' % ROUTE_LABELS["prologue"], text, count=1)
    for rid, pts in (("prologue_staff", ROUTE_STAFF), ("yarus_vertical", ROUTE_VERT)):
        rx = re.compile(r'(\{\n   "id": "%s",\n   "label": )"[^"]*"(,\n   "max_open_m": [0-9.]+,\n   "points": \[\n).*?(\n   \])' % rid, re.S)
        text, n = rx.subn(lambda m: m.group(1) + '"%s"' % ROUTE_LABELS[rid] + m.group(2) + _pts(pts) + m.group(3), text, count=1)
        if n != 1:
            raise SystemExit(f"маршрут {rid} не найден")
    block = ('  {\n   "id": "yarus_public",\n   "label": "%s",\n   "max_open_m": 0.0,\n   "points": [\n%s\n   ]\n  }'
             % (ROUTE_LABELS["yarus_public"], _pts(ROUTE_PUBLIC)))
    if '"id": "yarus_public"' in text:
        rx = re.compile(r'(\{\n   "id": "yarus_public",\n   "label": )"[^"]*"(,\n   "max_open_m": [0-9.]+,\n   "points": \[\n).*?(\n   \])', re.S)
        text = rx.sub(lambda m: m.group(1) + '"%s"' % ROUTE_LABELS["yarus_public"] + m.group(2) + _pts(ROUTE_PUBLIC) + m.group(3), text, count=1)
    else:
        key = '  {\n   "id": "south_to_site"'
        if key not in text:
            raise SystemExit("prospekt.json: нет south_to_site")
        text = text.replace(key, block + ",\n" + key, 1)
    # --- место прогулки 7
    text = text.replace('"label": "Супермаркет «Ярус»",\n   "at": [-102.0, 68.0],\n   "spawn": [-108.0, 44.0],\n   "look": [-108.0, 68.0]',
                        '"label": "Супермаркет «Ярус»",\n   "at": [-102.0, 55.0],\n   "spawn": [-108.0, 44.0],\n   "look": [-102.0, 56.0]')
    open(path, "w", encoding="utf-8", newline="").write(text)
    # --- рейдовая сцена: ящики, посты, метки
    path = ROOT / "scenes" / "levels" / "prospekt.tscn"
    text = open(path, encoding="utf-8", newline="").read()
    for name, pos in NODE_MOVES:
        rx = re.compile(r'(\[node name="%s" [^\n]*\]\n(?:transform = [^\n]*\n)?position = )Vector3\([^)]*\)' % re.escape(name))
        text, n = rx.subn(lambda mm: mm.group(1) + pos, text, count=1)
        if n != 1:
            raise SystemExit(f"prospekt.tscn: нет узла {name}")
    for name, (old, _cand) in LOOT_MOVES.items():
        nx, nz, nf = targets[name]
        rx = re.compile(r'(\[node name="%s" [^\n]*\]\n(?:transform = [^\n]*\n)?position = )Vector3\([^)]*\)' % re.escape(name))
        text, n = rx.subn(lambda mm: mm.group(1) + "Vector3(%s, %s, %s)" % (_fmt(nx), _fmt(nf + 0.6), _fmt(nz)), text, count=1)
        if n != 1:
            raise SystemExit(f"prospekt.tscn: нет ящика {name}")
    open(path, "w", encoding="utf-8", newline="").write(text)
    print(f"  данные: ящиков переставлено {len(LOOT_MOVES)} (в плане {moved}), маршруты prologue, prologue_staff, yarus_vertical, yarus_public, место 7, посты и метки")
