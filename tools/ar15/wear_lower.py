# AR-15 «ГРАНЬ-15», этап 2 (износ): места износа нижнего ресивера с органами управления и видимых частей УСМ —
# попиксельно по геометрическим картам наборов lower и internals (tools/ar15/wear_maps.py). План — asset-state.md
# модели, «Этап 2 — карта износа по деталям» (сведено со справкой агента; решения владельца 30.10: сквозь FDE — точки
# чёрного анодирования только на местах удара; протёртый FDE — глаже и темнее; нагар только внутри).
#   python -X utf8 tools/ar15/wear_lower.py [папка]       (папка по умолчанию — _asset_src/ar15/tex/wear)
# Пишет lower_zone_<зона>_L.png и internals_zone_<зона>_L.png (ч/б 8 бит, по развёртке набора) и
# lower_zones_preview.png (зоны цветом поверх заводского цвета — для проверки).
# Хват правый: левая рука держит шахту и жмёт задержку и левую кнопку магазина, правая — рукоять, указательный — спуск и
# кнопку магазина, большой — переводчик. Координаты, мм: X — к дулу, Y — влево, Z — вверх.
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WEAR = "E:/Games/RING-godot/_asset_src/ar15/tex/wear"
BASE = "E:/Models Blender/WEAPONS/AR-15 — модель/Текстуры_этап1_v6_песок"
SEED = 1530

# точки модели (tools/ar15/lib.py)
TAKEDOWN = (-150.3, -15.6, 4.6)          # ось разборки (x, z, радиус головки)
PIVOT = (17.8, -15.2, 4.2)               # ось сборки
SELECTOR = (-129.9, -26.2)
TRIGGER_PIN = (-99.1, -31.0)
HAMMER_PIN = (-78.7, -23.5)
MAG_BUTTON = (-62.4, -26.2)
PORT_X = (-74.2, 10.4)                   # окно выброса (крышка бьёт по борту под ним)
WELL_X = (-58.0, 16.0)                   # шахта с раструбом
GUARD_X = (-112.0, -62.0)                # скоба


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def window(x, a0, a1, b0, b1):
    return sstep(a0, a1, x) * (1.0 - sstep(b0, b1, x))


def load(name, folder):
    d = np.load(os.path.join(folder, f"{name}_maps.npz"))
    names = list(d["ids_names"])
    return d["pos"], d["nrm"].astype(np.float32), d["ids"], names


def by_x(mask, x, v, lo, hi, step, fn):
    """Значение fn(v) по полосам X шириной step (верхняя кромка борта, низ раструба), между серединами полос — линейно:
    ступенями по полосам маска прыгала на каждой границе — вертикальные полоски «штрихкодом» (проба 30.10)."""
    cs, vs = [], []
    for x0 in np.arange(lo, hi, step):
        m = mask & (x >= x0) & (x < x0 + step)
        if m.sum() > 20:
            cs.append(x0 + step / 2)
            vs.append(fn(v[m]))
    out = np.interp(x.ravel(), cs, vs).reshape(x.shape).astype(np.float32)
    out[(x < lo) | (x > hi)] = np.nan
    return out


def disc(px, py, cx, cy, r0, r1):
    return 1.0 - sstep(r0, r1, np.hypot(px - cx, py - cy))


def lint(mask_ok, starts, px_mm, rng, size):
    """Ворсинки (синтетика — рисунок кодом): изогнутые нити 3–8 мм толщиной ~0,05 мм от точек starts (пиксели);
    нить обрывается, где кончается разрешённая область (своя деталь, карман)."""
    img = Image.new("L", (size * 2, size * 2), 0)
    dr = ImageDraw.Draw(img)
    for (r, c) in starts:
        n = int(rng.uniform(3.0, 8.0) * px_mm / 2.0)
        ang = rng.uniform(0, 2 * math.pi)
        curl = rng.uniform(-0.12, 0.12)
        pts = [(c * 2.0, r * 2.0)]
        y, x = float(r), float(c)
        for _ in range(n):
            ang += curl + rng.normal(0, 0.10)
            x += 2.0 * math.cos(ang)
            y += 2.0 * math.sin(ang)
            yi, xi = int(round(y)), int(round(x))
            if not (0 <= yi < size and 0 <= xi < size) or not mask_ok[yi, xi]:
                break
            pts.append((x * 2.0, y * 2.0))
        if len(pts) > 3:
            dr.line(pts, fill=255, width=2)
    img = img.filter(ImageFilter.GaussianBlur(0.8)).resize((size, size), Image.LANCZOS)
    return np.asarray(img).astype(np.float32) / 255.0


def lower_zones(folder):
    pos, nrm, ids, names = load("lower", folder)
    size = ids.shape[0]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    nx, ny, nz = nrm[..., 0], nrm[..., 1], nrm[..., 2]
    body = ids == names.index("Lower_receiver")
    # наружная обшивка борта: нормаль от центра и сама поверхность снаружи (|y| > 11 — у кармана УСМ борт 12,2) —
    # иначе кольца и пятна по XZ ложились и на стенки внутри кармана УСМ и на внутренние грани ушей (проба 30.10)
    side = body & (ny * np.sign(y) > 0.6) & (np.abs(y) > 11.0)
    Z = {}

    # низ раструба шахты и верхняя кромка правого борта — по полосам X
    zbot = by_x(body & (np.abs(ny) > 0.5), x, z, WELL_X[0], WELL_X[1] + 2, 2.0, lambda a: np.percentile(a, 0.5))
    ztop_r = by_x(body & (ny < -0.6), x, z, PORT_X[0] - 4, PORT_X[1] + 4, 2.0, lambda a: np.percentile(a, 99.5))
    in_well = body & (x > WELL_X[0]) & (x < WELL_X[1])
    above_bot = np.nan_to_num(z - zbot, nan=99.0)

    # 1. шахта — хват левой рукой: наружные бока и перёд от низа раструба до середины высоты (внутренние стенки шахты
    # тоже смотрят вбок — только нормаль от центра; перёд — только передняя наружная грань, не задняя стенка внутри)
    out_side = sstep(0.4, 0.8, ny * np.sign(y))
    out_front = sstep(0.3, 0.7, nx) * (x > 0)
    Z["hold"] = in_well * window(above_bot, 2.0, 5.0, 30.0, 40.0) * np.maximum(out_side * 0.9, out_front)
    # 2. раструб: низ шахты (кромка и внутренняя губа) — вставка магазина
    Z["flare"] = in_well * (1.0 - sstep(3.0, 6.0, above_bot))
    # 3. скоба: низ и передний изгиб, внутренняя кромка — баррикада, указательный, перчатка
    g = body & (x > GUARD_X[0]) & (x < GUARD_X[1]) & (z < -64.0)
    Z["guard"] = g * np.maximum(np.maximum(sstep(0.3, 0.7, -nz), 0.6 * sstep(0.3, 0.7, nz)), 0.4 * sstep(0.5, 0.9, np.abs(ny)))
    # 4. правый борт под окном — удар открывающейся крышки (полоса у верхней кромки)
    below_top = np.nan_to_num(ztop_r - z, nan=99.0)
    hit = body & (ny < -0.6)
    Z["cover_hit"] = hit * window(x, PORT_X[0], PORT_X[0] + 12, PORT_X[1] - 12, PORT_X[1]) * (1.0 - sstep(3.0, 7.0, below_top))
    # 5. верх башни сзади — трение рукоятки заряжания
    Z["ch_rub"] = body * sstep(0.5, 0.8, nz) * (1.0 - sstep(-174.0, -170.0, x)) * (1.0 - sstep(5.0, 8.0, np.abs(y))) * (z > 8)
    # 6. дуга под флажком переводчика (ход рычага: вперёд ↔ вверх), с обеих сторон; правый рычаг короче
    ang = np.degrees(np.arctan2(z - SELECTOR[1], x - SELECTOR[0]))
    r = np.hypot(x - SELECTOR[0], z - SELECTOR[1])
    arc_l = (y > 10) * window(r, 9.5, 11.0, 16.0, 17.5)
    arc_r = (y < -10) * window(r, 6.5, 7.5, 11.0, 12.5)
    Z["sel_arc"] = side * np.maximum(arc_l, arc_r) * window(ang, -20.0, -5.0, 95.0, 110.0)
    # 7. кольца у осей разборки и сборки — выбивают носиком патрона
    ring = np.zeros_like(x)
    for cx, cz, rp in (TAKEDOWN, PIVOT):
        rr = np.hypot(x - cx, z - cz)
        ring = np.maximum(ring, window(rr, rp + 0.2, rp + 0.8, rp + 2.5, rp + 4.0))
    Z["pin_rings"] = side * ring
    # 8. острые рёбра со стороны тела и ремня — нижняя половина, правый борт сильнее (прижат к телу на ремне)
    Z["edges"] = body * (1.0 - sstep(-24.0, -16.0, z)) * np.where(y < 0, 1.0, 0.55)
    # 9. масло у осей курка, спуска и переводчика — венчики на бортах
    oil = np.zeros_like(x)
    for cx, cz in (TRIGGER_PIN, HAMMER_PIN, SELECTOR):
        oil = np.maximum(oil, disc(x, z, cx, cz, 2.5, 5.5))
    Z["oil"] = side * oil
    # 10. карманы — пыль и ворс: ниша задержки, у кнопок магазина, вокруг оси переводчика, внутри скобы
    pk = np.zeros_like(x)
    outer = np.abs(y) > 8.0
    pk = np.maximum(pk, (y > 8) * window(x, -63, -60, -41, -38) * window(z, -29, -27, -3, -1))     # ниша задержки
    pk = np.maximum(pk, (y < -8) * disc(x, z, *MAG_BUTTON, 5.0, 7.0))                          # кнопка магазина
    pk = np.maximum(pk, (y > 14) * window(x, -44, -41, -6, -3) * window(z, -36, -34, -18, -16))     # левая кнопка
    pk = np.maximum(pk, outer * (ny * np.sign(y) > 0.3) * disc(x, z, *SELECTOR, 6.0, 9.0))     # ось переводчика
    pk = np.maximum(pk, window(x, -110, -106, -68, -64) * window(z, -72, -70, -58, -54) * (np.abs(y) < 11))  # внутри скобы
    Z["pockets"] = body * pk

    # точки сквозь (чёрное анодирование): острый угол раструба спереди внизу с обеих сторон, середина удара крышки
    thr = np.zeros_like(x)
    pts = []
    for s in (1, -1):
        m = in_well & (s * y > 9) & (above_bot < 2.5) & (x > WELL_X[1] - 12)
        if m.any():
            i = np.argmax(np.where(m, x, -1e9))
            pts.append(pos.reshape(-1, 3)[i])
    m = hit & (below_top < 3.0) & (np.abs(x - (PORT_X[0] + PORT_X[1]) / 2) < 4)
    if m.any():
        i = np.argmin(np.where(m, below_top, 1e9))
        pts.append(pos.reshape(-1, 3)[i])
    for p in pts:
        d = np.sqrt(((pos - p) ** 2).sum(-1))
        thr = np.maximum(thr, body * (1.0 - sstep(1.0, 2.2, d)))
    Z["through"] = thr

    # кромки под заглаживание (в Painter — × кривизна × разрыв): раструб и скоба целиком, прочие рёбра низа — слабее
    Z["edgewear"] = np.maximum(np.maximum(Z["flare"], Z["guard"]), 0.6 * Z["edges"])

    # органы управления (фосфат): то, чего касается палец
    def obj(n):
        return ids == names.index(n)
    ctl = np.zeros_like(x)
    ra = np.hypot(x - SELECTOR[0], z - SELECTOR[1])
    ctl = np.maximum(ctl, obj("Selector_lever_L") * sstep(0.5, 0.8, ny) * (0.5 + 0.5 * sstep(6.0, 10.0, ra)))
    ctl = np.maximum(ctl, obj("Selector_lever_R") * sstep(0.5, 0.8, -ny) * 0.8)
    ctl = np.maximum(ctl, obj("Bolt_catch") * sstep(0.5, 0.8, ny) * (0.3 + 0.7 * (1.0 - sstep(-14.0, -10.0, z))))
    ctl = np.maximum(ctl, obj("Mag_button") * sstep(0.5, 0.8, -ny))
    ctl = np.maximum(ctl, obj("Mag_release_L") * sstep(0.5, 0.8, ny) * 0.8)
    for n in ("Takedown_pin", "Pivot_pin"):
        ctl = np.maximum(ctl, obj(n) * sstep(0.7, 0.9, np.abs(ny)) * 0.7)
    Z["controls"] = ctl

    # ворсинки: от точек в карманах (зерно постоянное — тот же рисунок при пересборке)
    rng = np.random.default_rng(SEED)
    px_mm = 17.5
    starts = []
    for tx, tz, ty, k in ((-50.0, -8.0, 15.0, 2), (-62.0, -21.0, -15.0, 1), (-88.0, -60.0, 0.0, 1), (-129.0, -19.0, 14.0, 1)):
        d = np.sqrt((x - tx) ** 2 + (z - tz) ** 2 + (y - ty) ** 2)
        d = np.where(body & (pk > 0.3), d, 1e9)
        for _ in range(k):
            i = np.argsort(d.ravel())[rng.integers(0, 400)]
            starts.append(divmod(int(i), size))
    allowed = body & (Z["pockets"] > 0.05)
    allowed = np.asarray(Image.fromarray((allowed * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    Z["lint"] = lint(allowed & body, starts, px_mm, rng, size) * body
    print("ворсинок:", len(starts), "пикселей нитей > 0,2:", int((Z["lint"] > 0.2).sum()))
    return Z, pos, ids, names


def internals_zones(folder):
    pos, nrm, ids, names = load("internals", folder)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    nx, ny = nrm[..., 0], nrm[..., 1]
    Z = {}
    # лицо спускового крючка под пальцем (ниже верха скобы, передняя сторона)
    tr = ids == names.index("Trigger")
    Z["trigger_face"] = tr * (1.0 - sstep(-50.0, -44.0, z)) * sstep(0.1, 0.5, nx)
    # торцы осей курка, спуска (видны на бортах) — промаслены
    pins = np.zeros_like(x)
    for n in ("Trigger_pin", "Hammer_pin"):
        pins = np.maximum(pins, (ids == names.index(n)) * sstep(0.6, 0.9, np.abs(ny)))
    Z["pin_ends"] = pins
    return Z


def save(Z, prefix, folder):
    for k, a in Z.items():
        Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)).save(os.path.join(folder, f"{prefix}_zone_{k}_L.png"))
        print(prefix, k, "доля пикселей > 0,5:", round(float((a > 0.5).mean()), 4))


def preview(Z, folder):
    base = np.asarray(Image.open(os.path.join(BASE, "lower_baseColor.png")).convert("RGB")).astype(np.float32) / 255.0
    if base.shape[0] != Z["hold"].shape[0]:
        base = np.asarray(Image.fromarray((base * 255).astype(np.uint8)).resize(Z["hold"].shape[::-1])).astype(np.float32) / 255.0
    img = base * 0.55
    cols = {"hold": (0.2, 0.5, 1.0), "flare": (1.0, 0.5, 0.0), "guard": (0.8, 0.2, 0.9), "cover_hit": (1.0, 1.0, 0.0),
            "ch_rub": (0.0, 1.0, 1.0), "sel_arc": (0.3, 1.0, 0.3), "pin_rings": (1.0, 0.3, 0.6), "oil": (0.1, 0.1, 0.1),
            "pockets": (0.6, 0.4, 0.2), "controls": (0.2, 1.0, 0.6), "lint": (1.0, 1.0, 1.0), "through": (1.0, 0.0, 0.0)}
    for k, c in cols.items():
        a = np.clip(Z[k], 0, 1)[..., None] * 0.85
        img = img * (1 - a) + np.array(c) * a
    Image.fromarray((img * 255).astype(np.uint8)).resize((2048, 2048), Image.LANCZOS).save(os.path.join(folder, "lower_zones_preview.png"))


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else WEAR
    Z, pos, ids, names = lower_zones(folder)
    save(Z, "lower", folder)
    save(internals_zones(folder), "internals", folder)
    preview(Z, folder)


if __name__ == "__main__":
    main()
