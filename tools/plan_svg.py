"""Чертёж сектора сверху из данных: data/sectors/<id>.json → docs/plans/<id>.svg.

Рисует помещения (кольцевые секторы и прямоугольные постройки), проёмы по видам, точки эвакуации
и спавна, запертую часть кольца, компас и масштаб. Нужен, чтобы обсуждать планировку до сборки
в Godot и видеть, что лежит в данных.

    python tools/plan_svg.py data/sectors/f1_ring.json
Север — это -Z в игре (угол a = -90°), на чертеже вверху.
"""
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

PX = 2.4  # пикселей на метр

FILL = {
    "atrium": "#dfe8ee", "gallery": "#eceae4", "retail": "#f3e3c8", "storage": "#d9d6cf",
    "office": "#e6dcea", "utility": "#d3dde0", "security": "#e9d2cc", "corridor": "#f1f0ec",
    "yard": "#c9cbc9", "parking": "#bfc4c6",
}
OPEN_KIND = {  # цвет, толщина, штрих
    "storefront": ("#3d8fc4", 3.2, None), "door": ("#ffffff", 3.4, None), "open": ("#ffffff", 3.4, None),
    "entrance": ("#1fb5c9", 4.5, None), "shutter": ("#e08a2c", 3.2, "4 3"), "gate": ("#d8b41c", 4.2, None),
    "locked": ("#c8322c", 4.5, None), "barrier": ("#c8322c", 3.0, "2 3"),
}


def xy(a, r):
    t = math.radians(a)
    return r * math.cos(t) * PX, r * math.sin(t) * PX


def arc_pts(a0, a1, r, step=1.0):
    n = max(2, int(abs(a1 - a0) * math.radians(1) * r / step) + 1)
    return [xy(a0 + (a1 - a0) * i / (n - 1), r) for i in range(n)]


def poly(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def room_pts(rm):
    if rm.get("shape") == "rect":
        a, r = rm["c"]["a"], rm["c"]["r"]
        w, d = rm["size"]
        t = math.radians(a)
        rad = (math.cos(t), math.sin(t))
        tan = (-math.sin(t), math.cos(t))
        cx, cy = r * rad[0], r * rad[1]
        out = []
        for sw, sd in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            out.append(((cx + tan[0] * w / 2 * sw + rad[0] * d / 2 * sd) * PX,
                        (cy + tan[1] * w / 2 * sw + rad[1] * d / 2 * sd) * PX))
        return out
    a0, a1 = rm["a"]
    r0, r1 = rm["r"]
    return arc_pts(a0, a1, r1) + arc_pts(a1, a0, max(r0, 0.01))


def centroid(rm):
    if rm.get("shape") == "rect":
        return xy(rm["c"]["a"], rm["c"]["r"])
    return xy(sum(rm["a"]) / 2, sum(rm["r"]) / 2)


def room_size_px(rm):
    """Сколько места под подпись: ширина по дуге и глубина, px."""
    if rm.get("shape") == "rect":
        return rm["size"][0] * PX, rm["size"][1] * PX
    rm_mid = sum(rm["r"]) / 2
    return math.radians(rm["a"][1] - rm["a"][0]) * rm_mid * PX, (rm["r"][1] - rm["r"][0]) * PX


def wrap(name, max_chars):
    words, lines, cur = name.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


## Цвет постройки по BlockoutBuilding.Kind: 0 здание, 1 паркинг, 2 мачта, 3 навес, 4 остановка.
BUILDING_FILL = {0: "#d3dde0", 1: "#bfc4c6", 2: "#9fa9ad", 3: "#e7e5df", 4: "#e7e5df"}


def parse_level(tscn):
    """Постройки (BlockoutBuilding), точки появления и эвакуации из .tscn уровня: положение,
    оси X/Z базиса и экспортированные свойства. Нет файла — пустые списки."""
    out = {"buildings": [], "spawns": [], "extractions": [], "items": []}
    if not tscn.exists():
        return out
    text = tscn.read_text(encoding="utf-8")
    ext = dict(re.findall(r'\[ext_resource [^\]]*path="([^"]+)"[^\]]*id="([^"]+)"\]', text))
    ids = {v: k for k, v in ext.items()}
    for block in re.split(r"\n(?=\[node )", text):
        m = re.match(r'\[node name="([^"]+)" parent="([^"]+)" instance=ExtResource\("([^"]+)"\)\]', block)
        if not m:
            continue
        scene = ids.get(m.group(3), "")
        props = dict(re.findall(r"^(\w+) = (.+)$", block, re.M))
        t = [float(v) for v in re.findall(r"-?[\d.]+(?:e-?\d+)?", props.get("transform", "Transform3D(1,0,0,0,1,0,0,0,1,0,0,0)"))[1:]] \
            if "transform" in props else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        # Transform3D(3) — отбрасываем «3» из имени; дальше 9 чисел базиса по столбцам и 3 — начало
        node = {"bx": t[0:3], "bz": t[6:9], "o": t[9:12],
                "name": props.get("display_name", '""').strip('"')}
        if scene.endswith("blockout_building.tscn"):
            sz = [float(v) for v in re.findall(r"-?[\d.]+", props.get("size", "Vector2(20, 16)"))[1:]]
            node.update({"size": sz, "kind": int(props.get("kind", 0)), "levels": int(props.get("levels", 3))})
            out["buildings"].append(node)
        elif scene.endswith("spawn_point.tscn"):
            out["spawns"].append(node)
        elif scene.endswith("extraction_point.tscn"):
            node["key"] = props.get("required_key", '""').strip('"')
            node["switch"] = props.get("required_switch", '""').strip('"')
            out["extractions"].append(node)
        elif scene.endswith("key_pickup.tscn") or scene.endswith("power_switch.tscn"):
            node["switch"] = scene.endswith("power_switch.tscn")
            out["items"].append(node)
    return out


def main(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    ring = d.get("ring", {})
    site = ring.get("site_r", 130)
    outer = ring.get("outer_r", 90)
    half = (site + 45) * PX
    s = []
    W = H = 2 * half
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-half:.0f} {-half:.0f} {W:.0f} {H + 150:.0f}" '
             f'font-family="Segoe UI, Arial, sans-serif">')
    s.append('<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<rect width="8" height="8" fill="#e4e4e2"/><line x1="0" y1="0" x2="0" y2="8" stroke="#b9b9b6" stroke-width="2"/></pattern></defs>')
    s.append(f'<rect x="{-half}" y="{-half}" width="{W}" height="{H + 150}" fill="#f6f6f3"/>')

    # всё кольцо бледно — чтобы было видно, какая часть открыта
    zones = ring.get("zones", {})
    s.append(f'<circle r="{outer * PX:.1f}" fill="url(#hatch)" stroke="#9a9a96" stroke-width="1.5"/>')
    for k, (r0, r1) in zones.items():
        s.append(f'<circle r="{r1 * PX:.1f}" fill="none" stroke="#b5b5b1" stroke-width="0.8"/>')
    sec = ring.get("sectors_deg", 60)
    a0_open, a1_open = d["angle"]
    for i in range(int(360 / sec)):
        a = a0_open + i * sec
        x, y = xy(a, outer)
        s.append(f'<line x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}" stroke="#a8a8a4" stroke-width="0.8" stroke-dasharray="6 5"/>')
    mid_locked = (a1_open + a0_open + 360) / 2
    lx, ly = xy(mid_locked, outer * 0.72)
    s.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="22" fill="#8a8a86" text-anchor="middle" font-weight="600">ЗАКРЫТО</text>')
    s.append(f'<text x="{lx:.0f}" y="{ly + 22:.0f}" font-size="13" fill="#8a8a86" text-anchor="middle">3 сектора: роллеты опущены, видно сквозь</text>')

    rooms = d["rooms"]
    # сначала улица, потом здание, потом постройки
    order = sorted(rooms, key=lambda rm: (rm.get("shape") == "rect", not rm.get("outdoor", False)))
    for rm in order:
        fill = FILL.get(rm["type"], "#eeeeee")
        if rm.get("locked"):
            fill = "url(#hatch)"
        stroke = "#7b7b77" if rm.get("outdoor") else "#3c3c3a"
        sw = 0.8 if rm.get("outdoor") else 1.3
        s.append(f'<polygon points="{poly(room_pts(rm))}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        if rm.get("key"):
            s.append(f'<polygon points="{poly(room_pts(rm))}" fill="none" stroke="#b0402f" stroke-width="2" stroke-dasharray="5 3"/>')

    for o in d.get("openings", []):
        color, width, dash = OPEN_KIND.get(o["kind"], ("#ff00ff", 3, None))
        if o["wall"] == "arc":
            pts = arc_pts(o["a"][0], o["a"][1], o["r"], 0.5)
        else:
            pts = [xy(o["a"], o["r"][0]), xy(o["a"], o["r"][1])]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        s.append(f'<polyline points="{poly(pts)}" fill="none" stroke="{color}" stroke-width="{width}"{da} stroke-linecap="butt"/>')

    # подписи помещений; узкие длинные — вдоль дуги, узкие радиальные — вдоль радиуса
    for rm in order:
        if rm.get("label") is False:
            continue
        x, y = centroid(rm)
        if "label_a" in rm:
            x, y = xy(rm["label_a"], sum(rm["r"]) / 2)
        wpx, hpx = room_size_px(rm)
        rot = 0.0
        if rm.get("shape") != "rect":
            a_mid = rm.get("label_a", sum(rm["a"]) / 2)
            if hpx < 22 and wpx > 60:
                rot = a_mid + 90
            elif wpx < 30 and hpx > wpx:
                rot = a_mid
                wpx, hpx = hpx, wpx
            rot = (rot + 180) % 360 - 180
            if rot > 90:
                rot -= 180
            elif rot < -90:
                rot += 180
        big = rm["type"] in ("atrium",) or wpx > 120 and hpx > 90
        fs = 15 if big else (8.5 if hpx < 22 else 10.5)
        lines = wrap(rm["name"], max(6, int(wpx / (fs * 0.56))))
        extra = []
        if rm.get("key"):
            extra.append(("ключ: " + rm["key"], "#b0402f"))
        total = len(lines) + len(extra)
        y0 = y - (total - 1) * fs * 0.55
        if rot:
            s.append(f'<g transform="rotate({rot:.1f} {x:.1f} {y:.1f})">')
        for i, ln in enumerate(lines):
            s.append(f'<text x="{x:.0f}" y="{y0 + i * fs * 1.1:.0f}" font-size="{fs}" text-anchor="middle" '
                     f'dominant-baseline="middle" fill="#1f1f1e" font-weight="{600 if big else 500}">{escape(ln)}</text>')
        for j, (t, col) in enumerate(extra):
            s.append(f'<text x="{x:.0f}" y="{y0 + (len(lines) + j) * fs * 1.1:.0f}" font-size="9" text-anchor="middle" '
                     f'dominant-baseline="middle" fill="{col}">{escape(t)}</text>')
        if rot:
            s.append("</g>")

    # названия секторов снаружи
    for sc in d.get("sectors", []):
        a = sum(sc["a"]) / 2
        x, y = xy(a, site + 28)
        s.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="20" text-anchor="middle" fill="#2c4a5a" font-weight="700">'
                 f'{escape(sc["name"].upper())}</text>')

    # постройки, спавны и эвакуации из сцены уровня (их двигают руками в редакторе)
    level = parse_level(Path("scenes/levels") / (Path(path).stem + ".tscn"))
    for b in level["buildings"]:
        pts = []
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, lz = b["size"][0] * 0.5 * sx, b["size"][1] * 0.5 * sz
            wx = b["o"][0] + b["bx"][0] * lx + b["bz"][0] * lz
            wz = b["o"][2] + b["bx"][2] * lx + b["bz"][2] * lz
            pts.append((wx * PX, wz * PX))
        fill = BUILDING_FILL.get(b["kind"], "#d3dde0")
        s.append(f'<polygon points="{poly(pts)}" fill="{fill}" stroke="#3c3c3a" stroke-width="1.3"/>')
        name = b["name"] or ""
        if b["kind"] == 1:
            name += f' · {b["levels"]} уровня'
        if name:
            x, y = b["o"][0] * PX, b["o"][2] * PX
            for i, ln in enumerate(wrap(name, max(8, int(b["size"][0] * PX / 7)))):
                s.append(f'<text x="{x:.0f}" y="{y + i * 15:.0f}" font-size="13" text-anchor="middle" '
                         f'dominant-baseline="middle" fill="#1f1f1e" font-weight="600">{escape(ln)}</text>')
    for e in level["extractions"]:
        x, y = e["o"][0] * PX, e["o"][2] * PX
        s.append(f'<polygon points="{x:.1f},{y - 13:.1f} {x + 12:.1f},{y + 9:.1f} {x - 12:.1f},{y + 9:.1f}" fill="#27a348" stroke="#0d4f1f" stroke-width="1.5"/>')
        s.append(f'<text x="{x + 16:.0f}" y="{y + 4:.0f}" font-size="11.5" fill="#0d4f1f" font-weight="700">{escape(e["name"])}</text>')
    for it in level["items"]:
        x, y = it["o"][0] * PX, it["o"][2] * PX
        col = "#d98a1c" if it["switch"] else "#c9a100"
        s.append(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" fill="{col}" stroke="#4a3500" stroke-width="1.2" transform="rotate(45 {x:.1f} {y:.1f})"/>')
        s.append(f'<text x="{x + 10:.0f}" y="{y + 4:.0f}" font-size="10.5" fill="#5a4200" font-weight="700">{escape(it["name"])}</text>')
    for sp in level["spawns"]:
        x, y = sp["o"][0] * PX, sp["o"][2] * PX
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#2f6fd6" stroke="#fff" stroke-width="2"/>')
        s.append(f'<text x="{x + 12:.0f}" y="{y + 4:.0f}" font-size="11" fill="#1f4a93" font-weight="600">{escape(sp["name"])}</text>')

    for e in d.get("extractions", []):
        x, y = xy(e["a"], e["r"])
        s.append(f'<polygon points="{x:.1f},{y - 13:.1f} {x + 12:.1f},{y + 9:.1f} {x - 12:.1f},{y + 9:.1f}" fill="#27a348" stroke="#0d4f1f" stroke-width="1.5"/>')
        s.append(f'<text x="{x + 16:.0f}" y="{y + 4:.0f}" font-size="11.5" fill="#0d4f1f" font-weight="700">{escape(e["name"])}</text>')
    for sp in d.get("spawns", []):
        x, y = xy(sp["a"], sp["r"])
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#2f6fd6" stroke="#fff" stroke-width="2"/>')
        s.append(f'<text x="{x + 12:.0f}" y="{y + 4:.0f}" font-size="11" fill="#1f4a93" font-weight="600">{escape(sp["name"])}</text>')

    # заголовок, компас, масштаб, легенда
    tx, ty = -half + 24, half - 150
    s.append(f'<text x="{tx}" y="{ty}" font-size="34" font-weight="800" fill="#1a1a19">{escape(d["name"])}</text>')
    info = [f'кольцо Ø{2 * outer:.0f} м, атриум Ø{2 * ring.get("atrium_r", 0):.0f} м, сектор {sec}°']
    for k, (r0, r1) in zones.items():
        info.append(f"{k}: r {r0:g}–{r1:g} м")
    for i, t in enumerate(info):
        s.append(f'<text x="{tx}" y="{ty + 26 + i * 17}" font-size="13" fill="#444">{escape(t)}</text>')
    cx, cy = half - 60, -half + 70
    s.append(f'<circle cx="{cx}" cy="{cy}" r="30" fill="none" stroke="#333" stroke-width="1.2"/>'
             f'<polygon points="{cx},{cy - 28} {cx + 7},{cy} {cx - 7},{cy}" fill="#333"/>'
             f'<text x="{cx}" y="{cy - 36}" font-size="15" text-anchor="middle" font-weight="700">С</text>')
    by = half + 30
    bx = -half + 24
    s.append(f'<rect x="{bx}" y="{by}" width="{50 * PX}" height="8" fill="#333"/>'
             f'<rect x="{bx + 50 * PX}" y="{by}" width="{50 * PX}" height="8" fill="#fff" stroke="#333"/>')
    for m in (0, 50, 100):
        s.append(f'<text x="{bx + m * PX}" y="{by + 24}" font-size="12" text-anchor="middle">{m} м</text>')
    legend = [("storefront", "витрина"), ("door", "дверь"), ("entrance", "вход в ТЦ"), ("shutter", "роллета"),
              ("gate", "ворота"), ("locked", "заперто навсегда"), ("barrier", "ограждение")]
    lx = bx + 300
    for i, (k, t) in enumerate(legend):
        col, w, dash = OPEN_KIND[k]
        x = lx + (i % 4) * 150
        y = by + (i // 4) * 26
        da = f' stroke-dasharray="{dash}"' if dash else ""
        bg = '<rect x="{0}" y="{1}" width="34" height="10" fill="#8c8c88"/>'.format(x - 2, y - 1) if col == "#ffffff" else ""
        s.append(f'{bg}<line x1="{x}" y1="{y + 4}" x2="{x + 30}" y2="{y + 4}" stroke="{col}" stroke-width="{w}"{da}/>'
                 f'<text x="{x + 40}" y="{y + 8}" font-size="12.5">{t}</text>')
    y = by + 60
    s.append(f'<polygon points="{lx},{y - 8} {lx + 8},{y + 6} {lx - 8},{y + 6}" fill="#27a348"/>'
             f'<text x="{lx + 16}" y="{y + 4}" font-size="12.5">эвакуация</text>'
             f'<circle cx="{lx + 158}" cy="{y}" r="7" fill="#2f6fd6"/><text x="{lx + 172}" y="{y + 4}" font-size="12.5">спавн</text>'
             f'<rect x="{lx + 296}" y="{y - 7}" width="30" height="14" fill="none" stroke="#b0402f" stroke-width="2" stroke-dasharray="5 3"/>'
             f'<text x="{lx + 336}" y="{y + 4}" font-size="12.5">по ключу</text>'
             f'<rect x="{lx + 450}" y="{y - 6}" width="12" height="12" fill="#c9a100" transform="rotate(45 {lx + 456} {y})"/>'
             f'<text x="{lx + 470}" y="{y + 4}" font-size="12.5">ключ / рубильник</text>')
    s.append("</svg>")

    out = Path("docs/plans") / (Path(path).stem + ".svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(s), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/sectors/f1_ring.json")
