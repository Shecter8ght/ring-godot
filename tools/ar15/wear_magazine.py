# AR-15 «ГРАНЬ-15», этап 2 (износ): места износа магазина (полимер чёрный гладкий, подаватель — серый) — попиксельно
# по геометрическим картам набора magazine (tools/ar15/wear_maps.py). План — asset-state.md модели, «Этап 2 — карта
# износа по деталям», п. 2; суть по образцам владельца 30.10: трётся то, что выступает (светлее и глаже), в углублениях —
# темно и пыль; на магазине — светлые продольные полосы по ходу в шахте.
#   python -X utf8 tools/ar15/wear_magazine.py [папка]       (папка по умолчанию — _asset_src/ar15/tex/wear)
# Пишет magazine_zone_<зона>_L.png (ч/б 8 бит) и magazine_zones_preview.png.
# На полимере металла нет: потёртость — светлее и матовее основы, заглаженность — темнее и с блеском.
# Координаты, мм: X — к дулу, Y — влево, Z — вверх; магазин вставлен: в шахте — от губок (z −6) до её низа (−56…−70).
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wear_lower import WEAR, disc, lint, load, sstep, window  # noqa: E402

BASE = "E:/Models Blender/WEAPONS/AR-15 — модель/Текстуры_этап1_v6_песок"
SEED = 2207
PX_MM = 17.5
WELL_Z = -62.0                          # ниже — под шахтой (видимая часть); выше — в шахте
LIP_Z = -14.0                           # губки и верх корпуса
CATCH = (-42.0, -26.0)                  # окно защёлки на левой стенке (lib.MAG_CATCH_SLOT)
BODY_HW = 12.3                          # полуширина корпуса ниже шахты (part_magazine)


def strokes(pos, nrm, ids, allowed, starts, dir_fn, rng, count, length_mm, deep_frac=0.0, width=(1, 2)):
    """Штрихи (царапины, полосы) в развёртке: направление из 3D (dir_fn(p, n)) переводится в пиксели по местному
    якобиану карты положения; штрих обрывается, где кончается разрешённая область или своя деталь. → (мелкие, глубокие)."""
    size = ids.shape[0]
    cand = np.argwhere(starts)
    light = Image.new("L", (size * 2, size * 2), 0)
    deep = Image.new("L", (size * 2, size * 2), 0)
    dl, dd = ImageDraw.Draw(light), ImageDraw.Draw(deep)
    for k in rng.choice(len(cand), size=min(count, len(cand)), replace=False):
        r0, c0 = cand[k]
        if not (2 <= r0 < size - 2 and 2 <= c0 < size - 2):
            continue
        if not (ids[r0 - 1:r0 + 2, c0 - 1:c0 + 2] == ids[r0, c0]).all():
            continue
        p0, n0 = pos[r0, c0], nrm[r0, c0]
        d = np.asarray(dir_fn(p0, n0), dtype=np.float64)
        d -= n0 * np.dot(n0, d)
        if np.linalg.norm(d) < 1e-6:
            continue
        J = np.stack([(pos[r0, c0 + 1] - pos[r0, c0 - 1]) / 2.0, (pos[r0 + 1, c0] - pos[r0 - 1, c0]) / 2.0], 1)
        uv = np.linalg.lstsq(J, d / np.linalg.norm(d), rcond=None)[0]
        if not np.isfinite(uv).all() or np.linalg.norm(uv) < 1e-6:
            continue
        uv /= np.linalg.norm(uv)
        n = rng.uniform(*length_mm) * PX_MM
        bend = rng.normal(0.0, 0.0015)
        pts, cx, cy = [], float(c0), float(r0)
        for i in range(int(n)):
            ang = math.atan2(uv[1], uv[0]) + bend * i
            cx += math.cos(ang); cy += math.sin(ang)
            yi, xi = int(round(cy)), int(round(cx))
            if not (0 <= yi < size and 0 <= xi < size) or not allowed[yi, xi] or ids[yi, xi] != ids[r0, c0]:
                break
            pts.append((cx * 2.0, cy * 2.0))
        if len(pts) < 6:
            continue
        is_deep = rng.random() < deep_frac
        (dd if is_deep else dl).line(pts, fill=int(rng.uniform(140, 255)), width=width[1] if is_deep else width[0])
    out = []
    for img in (light, deep):
        img = img.filter(ImageFilter.GaussianBlur(0.7)).resize((size, size), Image.LANCZOS)
        out.append(np.asarray(img).astype(np.float32) / 255.0)
    return out


def magazine_zones(folder):
    pos, nrm, ids, names = load("magazine", folder)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    nx, ny, nz = nrm[..., 0], nrm[..., 1], nrm[..., 2]
    body = ids == names.index("Magazine_body")
    plate = ids == names.index("Magazine_floorplate")
    follower = ids == names.index("Magazine_follower")
    rng = np.random.default_rng(SEED)
    Z = {}
    in_well = body & (z > WELL_Z)
    below = body & (z <= WELL_Z)
    outer_side = np.abs(y) > BODY_HW - 0.15                                   # наружная плоскость борта и вершины выступов
    out_n = np.maximum(sstep(0.5, 0.8, ny * np.sign(y)), np.maximum(sstep(0.5, 0.8, np.abs(nx)), 0.0))

    # 1. губки и верх корпуса — патроны и проход затвора: кромки губок светлее (в Painter × кривизна)
    Z["lips"] = body * sstep(LIP_Z - 3.0, LIP_Z, z)
    # 2. ход в шахте: наружные перёд, зад, бока — заглажено полосой, светлые продольные полосы вдоль корпуса
    slide = in_well & (z < LIP_Z) & (out_n > 0.5)
    Z["slide"] = slide * window(z, WELL_Z, WELL_Z + 6.0, LIP_Z - 4.0, LIP_Z)
    allowed = (Z["slide"] > 0.2) | (Z["lips"] > 0.2)
    well_streaks, wide = strokes(pos, nrm, ids, allowed, Z["slide"] > 0.5, lambda p, n: (0.0, 0.0, -1.0), rng,
                                 count=300, length_mm=(6.0, 26.0), deep_frac=0.4, width=(1, 2))
    # 3. под шахтой: выступы и наружная плоскость (вершины рёбер, плитки) — светлее и глаже по краям (Painter × кривизна);
    # углубления — пыль (карман)
    vis = below & ~plate
    Z["raised"] = vis * outer_side * (np.abs(ny) > 0.6)
    Z["recess"] = vis * (np.abs(ny) > 0.6) * (1.0 - outer_side)
    # 3а. полосы вдоль всей видимой части — подсумок и руки (образец владельца 30.10: светлые продольные полосы по рёбрам
    # по всей длине); направление — по оси магазина с его изгибом (середина корпуса по высоте → касательная)
    zc = np.arange(-195.0, -5.0, 4.0)
    xc = []
    for z0 in zc:
        sel = body & (np.abs(z - z0) < 2.0) & (np.abs(y) > BODY_HW - 1.0)
        xc.append(np.median(x[sel]) if sel.sum() > 50 else np.nan)
    xc = np.array(xc)
    ok_c = np.isfinite(xc)
    zc, xc = zc[ok_c], xc[ok_c]
    dxdz = np.gradient(xc, zc)

    def along(p, n):
        k = float(np.interp(p[2], zc, dxdz))
        return (-k, 0.0, -1.0)
    vis_out = vis & ((Z["raised"] > 0.5) | (sstep(0.5, 0.8, np.abs(nx)) > 0.5))
    pouch, pouch_w = strokes(pos, nrm, ids, vis_out | (Z["raised"] > 0.2), vis_out, along, rng,
                             count=220, length_mm=(10.0, 40.0), deep_frac=0.35, width=(1, 2))
    Z["streaks"] = np.maximum(np.maximum(well_streaks, wide), 0.7 * np.maximum(pouch, pouch_w))
    # 4. хват при перезарядке: бока и перёд средней части под шахтой
    Z["grip"] = below * window(z, -132.0, -120.0, -76.0, WELL_Z) * np.maximum(sstep(0.5, 0.8, np.abs(ny)), sstep(0.4, 0.7, nx))
    # 5. донце: низ и кромки — земля, подсумок: разнонаправленные царапины, потёртые кромки и углы
    bottom = plate & (nz < -0.5)
    Z["plate"] = plate * 1.0
    Z["plate_scr"], Z["plate_scr_deep"] = strokes(pos, nrm, ids, plate, bottom, lambda p, n: (
        math.cos(rng.uniform(0, math.tau)), math.sin(rng.uniform(0, math.tau)), 0.0), rng, count=90,
        length_mm=(2.0, 9.0), deep_frac=0.3)
    # 6. окно защёлки на левой стенке — слабая выработка кромки (кольцо вокруг окна)
    Z["catch"] = body * (y > 0) * disc(x, z, *CATCH, 4.0, 7.0) * (1.0 - disc(x, z, *CATCH, 2.0, 3.2))
    # 7. подаватель — верх, где лежит патрон: чуть заглажен
    Z["follower_top"] = follower * sstep(0.5, 0.8, nz)
    # 8. ворсинки — в углублениях под шахтой и у донца
    pk = (Z["recess"] > 0.5) | (plate & (nz > -0.2) & (z > -192))
    starts = []
    for tx, ty, tz in ((10.0, 12.0, -140.0), (25.0, -12.0, -165.0), (40.0, 6.0, -186.0)):
        d = np.where(pk, np.sqrt((x - tx) ** 2 + (y - ty) ** 2 + (z - tz) ** 2), 1e9)
        i = np.argsort(d.ravel())[rng.integers(0, 300)]
        starts.append(divmod(int(i), ids.shape[0]))
    ok = np.asarray(Image.fromarray((pk * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    Z["lint"] = lint(ok & (body | plate), starts, PX_MM, rng, ids.shape[0]) * (body | plate)
    print("магазин: ворсинок", len(starts), "пикселей нитей > 0,2:", int((Z["lint"] > 0.2).sum()),
          "| полос хода:", int((Z["streaks"] > 0.2).sum()), "| царапин донца:", int((Z["plate_scr"] > 0.2).sum()),
          "+", int((Z["plate_scr_deep"] > 0.2).sum()))
    return Z


def save(Z, prefix, folder):
    for k, a in Z.items():
        Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)).save(os.path.join(folder, f"{prefix}_zone_{k}_L.png"))
        print(prefix, k, "доля пикселей > 0,5:", round(float((a > 0.5).mean()), 4))


def preview(Z, folder):
    base = np.asarray(Image.open(os.path.join(BASE, "magazine_baseColor.png")).convert("RGB")).astype(np.float32) / 255.0
    n = Z["lips"].shape[0]
    if base.shape[0] != n:
        base = np.asarray(Image.fromarray((base * 255).astype(np.uint8)).resize((n, n))).astype(np.float32) / 255.0
    img = 0.25 + base * 0.6
    cols = {"lips": (1.0, 0.5, 0.0), "slide": (0.2, 0.5, 1.0), "raised": (0.3, 1.0, 0.3), "recess": (0.6, 0.4, 0.2),
            "grip": (0.9, 0.2, 0.9), "plate": (1.0, 1.0, 0.0), "catch": (0.0, 1.0, 1.0), "follower_top": (1.0, 0.6, 0.6),
            "streaks": (1.0, 1.0, 1.0), "plate_scr": (1.0, 1.0, 1.0), "plate_scr_deep": (1.0, 0.0, 0.0), "lint": (1.0, 1.0, 1.0)}
    for k, c in cols.items():
        a = np.clip(Z[k], 0, 1)[..., None] * 0.8
        img = img * (1 - a) + np.array(c) * a
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((2048, 2048), Image.LANCZOS).save(
        os.path.join(folder, "magazine_zones_preview.png"))


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else WEAR
    Z = magazine_zones(folder)
    save(Z, "magazine", folder)
    preview(Z, folder)


if __name__ == "__main__":
    main()
