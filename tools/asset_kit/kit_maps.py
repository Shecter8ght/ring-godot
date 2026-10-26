# Метрики карт PBR для самопроверки отделки до показа владельцу (review.py maps).
# Нормы — навык weapon-asset-texturing: painter-workflow.md (порядок слоёв, связь каналов, резкость),
# wood-and-paint-layers.md (три расстояния «издали / средне / вблизи», блеск против матовости),
# realism-review.md (признаки ошибки: мыло, одинаковые Color/Roughness у всех частей).
# Пороги подобраны на принятых владельцем ВЕРАС-54 и ПМ (проходят без «исправить») и на копиях их карт,
# испорченных так, как владелец ругал ВСС-М («мыльные пятна», «каток», серое однообразие) — см. validation-and-delivery.md.
import glob
import json
import math
import os

import cv2
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

import kit_mesh as km

# Все пороги — здесь. Цвет — в единицах L* (CIELAB, 0–100) и ΔE76, шероховатость — в сотых (0–100).
LIMITS = {
    # границы PBR: неметалл — альбедо 30–240 sRGB (яркость), металл — не темнее покрытия тёмной стали
    # учебная граница неметалла 30–240 sRGB; принятые ПМ и ВЕРАС темнее (грязь и нагар на стали 15–23, бакелит 31–48),
    # поэтому «исправить» — только ниже 14 (лак цевья ВСС-М 26.10 — 13: чёрная дыра без тона)
    "dielectric_norm_srgb": (30, 240),
    "dielectric_dark_srgb": 14,
    "dielectric_bright_srgb": 240,
    "dielectric_dark_fail": 0.25,      # доля площади неметалла темнее порога → исправить
    "dielectric_dark_warn": 0.08,
    "dielectric_bright_fail": 0.05,
    "metal_threshold": 0.5,            # металличность ≥ — металл
    "metal_dark_srgb": 12,             # тёмная сталь: ПМ 15–21, ВЕРАС 23–26, совет навыка 38–56; ниже 12 — краска
    "metal_dark_fail": 0.30,
    "metal_dark_warn": 0.10,
    "worn_dL": 15.0,                   # светлее основы металла на 15 L* — «вытерто до металла»
    "worn_warn": 0.14,                 # доля металла: ПМ 0.04–0.05, ВЕРАС 0.09, ВСС-М 26.10 — 0.19–0.20
    "worn_fail": 0.30,
    "metal_grey_lo": 0.15,             # «серая» металличность: ни металл, ни покрытие (ПМ — до 12 % у глушителя)
    "metal_grey_hi": 0.50,
    "metal_grey_fail": 0.25,
    "metal_grey_warn": 0.15,
    # разнообразие: локальное отклонение на своём масштабе ниже порога — «однотонно»
    "scales_cm": {"near": 0.1, "mid": 0.8, "far": 4.0},   # длина волны: зерно ~1 мм, потёртости ~8 мм, пятна ~4 см
    "flat_color_de": {"near": 0.6, "mid": 0.8, "far": 1.0},
    "flat_rough": {"near": 0.6, "mid": 0.8, "far": 1.0},
    "flat_normal": {"near": 1.5, "mid": 1.5, "far": 1.5},   # наклон нормали, сотые
    "coat_gloss": 30.0,                # жировая плёнка 0–1 → перепад блеска в сотых
    # доля однотонной площади: принятые — вблизи до 0.56 (патроны 0.9–0.95), средне до 0.36, издали до 0.07;
    # серая заливка поверх тех же нормалей — 0.71 / 0.64 / 1.0
    "flat_fail": {"near": 0.97, "mid": 0.55, "far": 0.60},
    "flat_warn": {"near": 0.65, "mid": 0.42, "far": 0.35},
    # издали по рендеру (каналы излучением сбоку и с камеры игры): ВЕРАС 0.38–0.56, ПМ 0–0.09, ВСС-М 0.05–0.14,
    # ВЕРАС с серой заливкой стали — 0.86–0.92
    "render_far_fail": 0.75,
    "render_far_warn": 0.62,
    "min_valid": 0.10,                 # масштаб оценивается по карте, если кусков развёртки такого размера ≥ 10 % площади
    # мыло: пятна без резкого края — у соседней мелкой октавы энергия падает как у гладкой функции
    "soap_active_rough": 1.5,          # пятно блеска заметно (сотые)
    "soap_active_color": 1.5,          # пятно тона заметно (ΔE)
    "soap_ratio": 0.33,                # мелкая октава / своя: гладкое пятно ≈ 0.25, рваный край ≈ 0.6–1
    "soap_fail": 0.45,                 # доля мыльных среди заметных пятен
    "soap_warn": 0.30,
    # каток: длинные царапины по всей поверхности
    "scratch_sigma_cm": 0.025,         # ширина царапины ~0.5 мм
    "scratch_contrast": 0.05,          # перепад шероховатости у царапины
    "scratch_long_cm": 0.5,            # кусок длиннее — царапина (швы развёртки режут длинные на куски)
    "scratch_density_fail": 25.0,      # см царапин на 100 см² поверхности: принятые 0–4, «каток» — 62
    "scratch_density_warn": 12.0,
    "scratch_tilt_skip": 0.35,         # где нормаль наклонена сильнее — геометрия (кромка, канавка), не царапина
    # связь каналов: у пятна в цвете — пара в шероховатости
    "link_spot_de": 1.5,
    "link_corr": 0.35,                 # |локальная корреляция| полос тона и блеска у пятна — «есть пара»
    "link_min_cm2": 15.0,              # меньше пятен по площади (патроны) — не судим
    "link_min_share": 0.08,            # и если пятна меньше 8 % поверхности (цифры на магазине ВЕРАС — 5 %)
    "link_fail": 0.25,                 # доля пятен цвета с парой: принятые 0.53–0.97, пятна только в цвете — 0.18
    "link_warn": 0.40,
    # нормали
    "normal_z_fail": 0.75,             # среднее z ниже — «кора» (у «коры» ВСС-М было 0.44; накатка ПМ — 0.86)
    "normal_z_warn": 0.82,
    "normal_y_ratio": 1.15,            # во сколько раз ротор хуже у неверного соглашения о зелёном
    # развёртка
    "density_ideal": (50, 70),         # пикс/см, оружие от первого лица (ролик «AAA Weapon»)
    "density_warn": 30,
    "density_fail": 18,
    "density_rel_warn": 0.5,           # набор ниже половины плотности ассета («мыльные прицелы» ВСС-М: 33 против 156)
    "fill_ideal": 0.80,
    "fill_warn": 0.25,                 # принятые атласы ВЕРАС — 30–46 %, не переделываются
    # одинаковые части
    "same_parts_de": 1.5,
    "same_parts_rough": 2.0,
}

DIAG_RES = 1024


# ---------- чтение ----------

def imread(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)            # cv2.imread не открывает кириллические пути
    im = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise RuntimeError("не читается " + path)
    mx = 65535.0 if im.dtype == np.uint16 else 255.0
    im = im.astype(np.float32) / mx
    if im.ndim == 2:
        return im[..., None]
    if im.shape[2] == 4:
        im = im[..., :3]
    return im[..., ::-1].copy()


def find_sets(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for ext in ("png", "jpg", "jpeg", "tga", "webp", "tif", "tiff"):
                files += glob.glob(os.path.join(p, "*." + ext))
        else:
            files.append(p)
    sets = {}
    for f in sorted(files):
        ch = km.channel_of(f)
        if ch in ("color", "orm", "rough", "metal", "normal", "coat"):
            sets.setdefault(km.set_key(f), {})[ch] = f
    return {k: v for k, v in sets.items() if "color" in v and ("orm" in v or "rough" in v)}


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def fit(img, w, h):
    if img.shape[1] == w and img.shape[0] == h:
        return img
    r = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if img.shape[1] > w else cv2.INTER_LINEAR)
    return r[..., None] if r.ndim == 2 else r


# ---------- пирамида с маской ----------

def masked_pyramid(img, mask, levels):
    """Нормированная свёртка: уровень k — среднее только по текселям развёртки (img H×W×C, mask H×W)."""
    m = mask.astype(np.float32)
    num = img * m[..., None]
    G, M = [], []
    for k in range(levels + 1):
        G.append(num / np.maximum(m, 1e-4)[..., None])
        M.append(m)
        if k < levels:
            num = cv2.pyrDown(num)
            if num.ndim == 2:
                num = num[..., None]
            m = cv2.pyrDown(m)
    return G, M


def band(G, M, k):
    """Полоса k пирамиды Лапласа и где она честная (внутри островов)."""
    h, w = G[k].shape[:2]
    up = cv2.pyrUp(G[k + 1], dstsize=(w, h))
    if up.ndim == 2:
        up = up[..., None]
    mu = cv2.pyrUp(M[k + 1], dstsize=(w, h))
    # не «только внутри острова»: у игровых атласов острова мелкие, и крупный масштаб пропадал целиком;
    # нормированная свёртка и так усредняет только тексели развёртки
    return G[k] - up, (M[k] > 0.6) & (mu > 0.6)


def local_rms(e, valid, sigma=2.0):
    """Локальное отклонение: корень из сглаженной энергии полосы по честным текселям."""
    v = valid.astype(np.float32)
    num = cv2.GaussianBlur(e * v, (0, 0), sigma)
    den = cv2.GaussianBlur(v, (0, 0), sigma)
    return np.sqrt(num / np.maximum(den, 1e-4)), den > 0.5


def local_corr(a, b, valid, sigma):
    v = valid.astype(np.float32)
    den = np.maximum(cv2.GaussianBlur(v, (0, 0), sigma), 1e-4)
    m = lambda x: cv2.GaussianBlur(x * v, (0, 0), sigma) / den  # noqa: E731
    ma, mb = m(a), m(b)
    cov = m(a * b) - ma * mb
    va = np.maximum(m(a * a) - ma * ma, 0)
    vb = np.maximum(m(b * b) - mb * mb, 0)
    return cov / np.sqrt(np.maximum(va * vb, 1e-8))


def level_for(lam_cm, dens, levels):
    k = int(round(math.log2(max(lam_cm * dens, 1e-6)) - 1.5))
    return max(0, min(levels - 1, k))


def up_to(img, w, h, interp=cv2.INTER_LINEAR):
    return cv2.resize(img.astype(np.float32), (w, h), interpolation=interp)


# ---------- проверка одного набора ----------

def check_set(key, files, mesh, dens_override=None, diag_dir=None):
    color = imread(files["color"])
    h, w = color.shape[:2]
    scale = 1.0
    if max(w, h) > 4096:                                  # 8K считаем на 4K: метрики в физических единицах
        scale = 4096 / max(w, h)
        w, h = int(w * scale), int(h * scale)
        color = fit(color, w, h)
    if "orm" in files:
        orm = fit(imread(files["orm"]), w, h)
        rough, metal = orm[..., 1], orm[..., 2]          # R — запечённое затенение, не нужно
    else:
        rough = fit(imread(files["rough"]), w, h)[..., 0]
        metal = fit(imread(files["metal"]), w, h)[..., 0] if "metal" in files else np.zeros_like(rough)
    normal = fit(imread(files["normal"]), w, h) if "normal" in files else None
    coat = fit(imread(files["coat"]), w, h)[..., 0] if "coat" in files else None   # жировая плёнка ВЕРАС/ПМ — тоже блеск

    rep = {"files": dict(files), "size": [int(w / scale), int(h / scale)]}
    find = []

    # --- развёртка и плотность ---
    if mesh is not None:
        mask = km.rasterize(mesh["uv"], w, h)
        d, a, o, uv_px = km.density(mesh, w / scale, h / scale)
        fill = float(mask.mean())
        uv_sum = float(uv_px.sum()) / (w / scale * h / scale)
        dens = km.wpercentile(d, a, 50) * scale
        objs = []
        for oi, name in enumerate(mesh["objects"]):
            sel = o == oi
            if sel.any():
                objs.append({"name": name, "area_cm2": round(float(a[sel].sum()), 1),
                             "px_cm": round(km.wpercentile(d[sel], a[sel], 50), 1)})
        rep["uv"] = {"fill": round(fill, 3), "overlap": round(max(0.0, 1 - fill / max(uv_sum, 1e-6)), 3),
                     "area_cm2": round(float(a.sum()), 1),
                     "px_cm": {"p10": round(km.wpercentile(d, a, 10), 1), "p50": round(km.wpercentile(d, a, 50), 1),
                               "p90": round(km.wpercentile(d, a, 90), 1)},
                     "objects": sorted(objs, key=lambda x: x["px_cm"])}
        if fill < LIMITS["fill_warn"]:
            find.append(("warn", "uv_fill", f"заполнение развёртки {fill:.0%} (норма ≥ {LIMITS['fill_ideal']:.0%})", fill))
        big = [x for x in objs if x["area_cm2"] > 0.1 * float(a.sum()) and x["px_cm"] < 0.5 * rep["uv"]["px_cm"]["p50"]]
        for x in big:
            find.append(("warn", "uv_part_low", f"деталь {x['name']}: {x['px_cm']} пикс/см — вдвое ниже набора", x["px_cm"]))
        dens_src = "развёртка"
    else:
        mask = np.ones((h, w), np.uint8)
        dens = 40.0 * max(w, h) / 4096
        dens_src = "принята (развёртки нет)"
        rep["uv"] = None
    if dens_override:
        dens, dens_src = dens_override * scale, "задана"
    rep["px_cm_used"] = round(dens / scale, 1)
    rep["px_cm_source"] = dens_src
    px_cm_full = dens / scale
    if mesh is not None and not dens_override:
        lo, hi = LIMITS["density_ideal"]
        if px_cm_full < LIMITS["density_fail"]:
            find.append(("fail", "density", f"плотность {px_cm_full:.0f} пикс/см — вблизи мыло (норма {lo}–{hi})", px_cm_full))
        elif px_cm_full < LIMITS["density_warn"]:
            find.append(("warn", "density", f"плотность {px_cm_full:.0f} пикс/см ниже {LIMITS['density_warn']} (норма {lo}–{hi})", px_cm_full))

    inner = cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0
    if inner.sum() < 100:
        inner = mask > 0
    sel = inner

    # --- границы PBR ---
    lab = cv2.cvtColor(np.ascontiguousarray(color), cv2.COLOR_RGB2Lab)
    lin = srgb_to_lin(color)
    Y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    Ys = lin_to_srgb(Y) * 255
    is_metal = metal >= LIMITS["metal_threshold"]
    die = sel & ~is_metal
    met = sel & is_metal
    pbr = {"metal_share": round(float(met.sum() / max(sel.sum(), 1)), 3)}
    bad_dark = die & (Ys < LIMITS["dielectric_dark_srgb"])
    bad_bright = die & ((Ys > LIMITS["dielectric_bright_srgb"]) | (color.max(axis=2) * 255 > 250))
    bad_metal = met & (Ys < LIMITS["metal_dark_srgb"])
    grey = sel & (metal > LIMITS["metal_grey_lo"]) & (metal < LIMITS["metal_grey_hi"])
    if die.sum():
        dd = float(bad_dark.sum() / die.sum())
        db = float(bad_bright.sum() / die.sum())
        pbr["dielectric"] = {"albedo_srgb_p5_p50_p95": [round(float(np.percentile(Ys[die], q)), 1) for q in (5, 50, 95)],
                             "too_dark": round(dd, 3), "too_bright": round(db, 3),
                             "rough_p5_p50_p95": [round(float(np.percentile(rough[die], q)), 3) for q in (5, 50, 95)]}
        if dd > LIMITS["dielectric_dark_fail"]:
            find.append(("fail", "pbr_dark", f"неметалл темнее {LIMITS['dielectric_dark_srgb']} sRGB на {dd:.0%} площади — чёрная дыра, поднять тон", dd))
        elif dd > LIMITS["dielectric_dark_warn"]:
            find.append(("warn", "pbr_dark", f"неметалл темнее {LIMITS['dielectric_dark_srgb']} sRGB на {dd:.0%} площади", dd))
        if db > LIMITS["dielectric_bright_fail"]:
            find.append(("fail", "pbr_bright", f"неметалл светлее {LIMITS['dielectric_bright_srgb']} sRGB на {db:.0%} площади", db))
    if met.sum():
        dm = float(bad_metal.sum() / met.sum())
        pbr["metal"] = {"albedo_srgb_p5_p50_p95": [round(float(np.percentile(Ys[met], q)), 1) for q in (5, 50, 95)],
                        "too_dark": round(dm, 3),
                        "metallic_p5_p50_p95": [round(float(np.percentile(metal[met], q)), 3) for q in (5, 50, 95)],
                        "rough_p5_p50_p95": [round(float(np.percentile(rough[met], q)), 3) for q in (5, 50, 95)]}
        if dm > LIMITS["metal_dark_fail"]:
            find.append(("fail", "pbr_metal_dark", f"металл темнее {LIMITS['metal_dark_srgb']} sRGB на {dm:.0%} — читается краской (тёмная сталь ПМ 15–21, ВЕРАС 23–26)", dm))
        elif dm > LIMITS["metal_dark_warn"]:
            find.append(("warn", "pbr_metal_dark", f"металл темнее {LIMITS['metal_dark_srgb']} sRGB на {dm:.0%} площади", dm))
    if met.sum() > 1000:
        # «камуфляж»: светлые пятна вытертого на большой доле металла (замечание владельца по ВСС-М — «на пол-крышки»)
        Lm = lab[..., 0]
        base_L = float(np.median(Lm[met]))
        worn = float((Lm[met] > base_L + LIMITS["worn_dL"]).mean())
        pbr["metal"]["worn_bright_share"] = round(worn, 3)
        if worn > LIMITS["worn_fail"]:
            find.append(("fail", "camo", f"светлого вытертого металла {worn:.0%} — «камуфляж», вытирать только кромки и места хвата", worn))
        elif worn > LIMITS["worn_warn"]:
            find.append(("warn", "camo", f"светлого вытертого металла {worn:.0%} (у ПМ и ВЕРАС 4–9 %) — не «на пол-крышки»", worn))
    gs = float(grey.sum() / max(sel.sum(), 1))
    pbr["metallic_grey"] = round(gs, 3)
    if gs > LIMITS["metal_grey_fail"]:
        find.append(("fail", "pbr_metal_grey", f"металличность {LIMITS['metal_grey_lo']}–{LIMITS['metal_grey_hi']} на {gs:.0%} площади — ни металл, ни покрытие", gs))
    elif gs > LIMITS["metal_grey_warn"]:
        find.append(("warn", "pbr_metal_grey", f"металличность {LIMITS['metal_grey_lo']}–{LIMITS['metal_grey_hi']} на {gs:.0%} площади", gs))
    rep["pbr"] = pbr

    # --- полосы: цвет в CIELAB, шероховатость в сотых ---
    levels = max(1, int(math.log2(min(w, h))) - 3)
    GL, ML = masked_pyramid(lab, mask, levels)
    # блеск — шероховатость за вычетом жировой плёнки (у ВЕРАС и ПМ отпечатки блестят плёнкой, а не картой шероховатости)
    gloss = rough * 100.0 - (coat * LIMITS["coat_gloss"] if coat is not None else 0.0)
    GR, _ = masked_pyramid(gloss[..., None], mask, levels)
    # вид меняет и рельеф (зерно, шагрень): место с ним — не «ровное»
    GN = masked_pyramid((normal[..., :2] * 2 - 1) * 100.0, mask, levels)[0] if normal is not None else None
    GD = None
    if normal is not None:
        nn = normal[..., :2] * 2 - 1                 # дивергенция наклонов ≈ кривизна высоты: бугор, вмятина, цифра
        div = cv2.Sobel(nn[..., 0], cv2.CV_32F, 1, 0, ksize=3) - cv2.Sobel(nn[..., 1], cv2.CV_32F, 0, 1, ksize=3)
        GD = masked_pyramid(div[..., None] * 100.0, mask, levels)[0]
    spectrum = []
    for k in range(levels):
        bl, v = band(GL, ML, k)
        br, _ = band(GR, ML, k)
        if v.sum() < 50:
            continue
        spectrum.append({"lambda_cm": round(2 ** (k + 1.5) / dens, 3),
                         "color_de": round(float(np.sqrt((bl[v] ** 2).sum(axis=1).mean())), 3),
                         "rough": round(float(np.sqrt((br[v, 0] ** 2).mean())), 3)})
    rep["spectrum"] = spectrum

    variety = {}
    flat_diag = {}
    soap = {}
    link = {}
    total_sel = float(sel.sum())
    for s, lam in LIMITS["scales_cm"].items():
        k = level_for(lam, dens, levels)
        bl, v = band(GL, ML, k)
        br, _ = band(GR, ML, k)
        eC = (bl ** 2).sum(axis=2)
        eR = br[..., 0] ** 2
        rC, okC = local_rms(eC, v)
        rR, _ = local_rms(eR, v)
        ok = okC & (ML[k] > 0.6)
        share = float(ok.sum() * 4 ** k / max(total_sel, 1))
        flat = ok & (rC < LIMITS["flat_color_de"][s]) & (rR < LIMITS["flat_rough"][s])
        fN = None
        if GN is not None:
            rN, _ = local_rms((band(GN, ML, k)[0] ** 2).sum(axis=2), v)
            fN = float((ok & (rN < LIMITS["flat_normal"][s])).sum() / max(ok.sum(), 1))
            flat &= rN < LIMITS["flat_normal"][s]
        fC = float((ok & (rC < LIMITS["flat_color_de"][s])).sum() / max(ok.sum(), 1))
        fR = float((ok & (rR < LIMITS["flat_rough"][s])).sum() / max(ok.sum(), 1))
        ff = float(flat.sum() / max(ok.sum(), 1))
        variety[s] = {"level": k, "lambda_cm": round(2 ** (k + 1.5) / dens, 2), "valid_share": round(min(share, 1.0), 3),
                      "color_de_p50": round(float(np.median(rC[ok])), 2) if ok.any() else None,
                      "rough_p50": round(float(np.median(rR[ok])), 2) if ok.any() else None,
                      "flat": round(ff, 3), "flat_color": round(fC, 3), "flat_rough": round(fR, 3),
                      "flat_normal": round(fN, 3) if fN is not None else None}
        flat_diag[s] = (flat, ok)
        enough = ok.sum() >= 64 and share >= LIMITS["min_valid"]
        variety[s]["judged"] = bool(enough)
        name = {"near": "вблизи (~1 мм)", "mid": "средне (~1 см)", "far": "издали (~4 см)"}[s]
        if enough:
            if ff > LIMITS["flat_fail"][s]:
                what = "тон и блеск" if fC > 0.5 and fR > 0.5 else ("блеск" if fR > fC else "тон")
                find.append(("fail", f"flat_{s}", f"{name}: однотонно {ff:.0%} площади ({what}) — нужна вариация этого размера", ff))
            elif ff > LIMITS["flat_warn"][s]:
                find.append(("warn", f"flat_{s}", f"{name}: однотонно {ff:.0%} площади", ff))
        # мыло: у заметных пятен соседняя мелкая октава почти пустая
        if s in ("mid", "far") and k >= 1:
            bl1, v1 = band(GL, ML, k - 1)
            br1, _ = band(GR, ML, k - 1)
            rC1, _ = local_rms((bl1 ** 2).sum(axis=2), v1, 4.0)
            rR1, _ = local_rms(br1[..., 0] ** 2, v1, 4.0)
            rC1 = cv2.resize(rC1, (rC.shape[1], rC.shape[0]), interpolation=cv2.INTER_AREA)
            rR1 = cv2.resize(rR1, (rR.shape[1], rR.shape[0]), interpolation=cv2.INTER_AREA)
            actR = ok & (rR > LIMITS["soap_active_rough"])
            actC = ok & (rC > LIMITS["soap_active_color"])
            soapR = actR & (rR1 < LIMITS["soap_ratio"] * rR)
            soapC = actC & (rC1 < LIMITS["soap_ratio"] * rC)
            act = actR | actC
            sp = soapR | soapC
            soap[s] = {"active": round(float(act.sum() / max(ok.sum(), 1)), 3),
                       "soap": round(float(sp.sum() / max(act.sum(), 1)), 3) if act.sum() >= 32 else None,
                       "ratio_rough_p50": round(float(np.median(rR1[actR] / rR[actR])), 3) if actR.sum() else None,
                       "ratio_color_p50": round(float(np.median(rC1[actC] / rC[actC])), 3) if actC.sum() else None,
                       "_map": (sp, act)}
            # связь каналов
            spot = ok & (rC > LIMITS["link_spot_de"])
            # корреляция локальная: у грязи (темнее и матовее) и у отпечатка (темнее и глянцевее) знак разный
            pairR = spot & (np.abs(local_corr(bl[..., 0], br[..., 0], v, 3.0)) > LIMITS["link_corr"])
            pair = pairR
            if GD is not None:
                # маркировка и литые цифры объяснены рельефом: пара в кривизне высоты тоже считается
                bd = band(GD, ML, k)[0][..., 0]
                pair = pair | (spot & (np.abs(local_corr(bl[..., 0], bd, v, 3.0)) > LIMITS["link_corr"]))
            corr = None
            if v.sum() > 100:
                a1, a2 = bl[v, 0], br[v, 0]
                if a1.std() > 1e-6 and a2.std() > 1e-6:
                    corr = float(np.corrcoef(a1, a2)[0, 1])
            link[s] = {"spots": round(float(spot.sum() / max(ok.sum(), 1)), 3),
                       "paired": round(float(pair.sum() / max(spot.sum(), 1)), 3) if spot.sum() >= 32 else None,
                       "paired_rough": round(float(pairR.sum() / max(spot.sum(), 1)), 3) if spot.sum() >= 32 else None,
                       "spot_cm2": round(float(spot.sum()) * 4 ** k / (dens * dens), 1),
                       "corr_L_rough": round(corr, 3) if corr is not None else None, "_map": (spot, pair)}
    rep["variety"] = variety
    for s in ("mid", "far"):
        sv = soap.get(s)
        if sv and sv["soap"] is not None and sv["active"] > 0.05 and variety[s]["judged"]:
            nm = "средние" if s == "mid" else "крупные"
            if sv["soap"] > LIMITS["soap_fail"]:
                find.append(("fail", f"soap_{s}", f"{nm} пятна мыльные: {sv['soap']:.0%} без резкого края (маски — фото/grunge + Warp/Histogram Scan, не мягкий шум)", sv["soap"]))
            elif sv["soap"] > LIMITS["soap_warn"]:
                find.append(("warn", f"soap_{s}", f"{nm} пятна мягкие: {sv['soap']:.0%} без резкого края", sv["soap"]))
    rep["soap"] = {s: {k2: v2 for k2, v2 in sv.items() if not k2.startswith("_")} for s, sv in soap.items()}
    pairs = [link[s]["paired"] for s in link if link[s]["paired"] is not None and link[s]["spots"] >= LIMITS["link_min_share"]
             and link[s]["spot_cm2"] >= LIMITS["link_min_cm2"]]
    if pairs:
        pm = min(pairs)
        if pm < LIMITS["link_fail"]:
            find.append(("fail", "link", f"пятна цвета без пары в шероховатости: с парой только {pm:.0%}", pm))
        elif pm < LIMITS["link_warn"]:
            find.append(("warn", "link", f"пятна цвета с парой в шероховатости: {pm:.0%}", pm))
    rep["link"] = {s: {k2: v2 for k2, v2 in lv.items() if not k2.startswith("_")} for s, lv in link.items()}

    # --- нормали ---
    tilt = None
    if normal is not None:
        n = normal * 2 - 1
        nz = n[..., 2]
        tilt = np.sqrt(n[..., 0] ** 2 + n[..., 1] ** 2)
        mz = float(nz[sel].mean())
        nrep = {"mean_z": round(mz, 3), "tilt_gt_0_5": round(float((tilt[sel] > 0.5).mean()), 3)}
        # соглашение о зелёном: поле наклонов должно быть безвихревым только при верном знаке
        zz = np.maximum(nz, 0.2)
        hx = cv2.GaussianBlur(-n[..., 0] / zz, (0, 0), 1.0)
        hy = cv2.GaussianBlur(n[..., 1] / zz, (0, 0), 1.0)
        dhx_dy = cv2.Sobel(hx, cv2.CV_32F, 0, 1, ksize=3)
        dhy_dx = cv2.Sobel(hy, cv2.CV_32F, 1, 0, ksize=3)
        sel2 = cv2.erode(mask, np.ones((7, 7), np.uint8)) > 0
        if sel2.sum() > 1000:
            c_gl = float(np.abs(dhx_dy - dhy_dx)[sel2].mean())
            c_dx = float(np.abs(dhx_dy + dhy_dx)[sel2].mean())
            r = c_dx / max(c_gl, 1e-9)
            nrep["curl_dx_over_gl"] = round(r, 3)
            nrep["convention"] = "OpenGL" if r > LIMITS["normal_y_ratio"] else ("DirectX" if r < 1 / LIMITS["normal_y_ratio"] else "неясно")
            if nrep["convention"] == "DirectX":
                find.append(("fail", "normal_dx", "карта нормалей в соглашении DirectX — Godot и Blender ждут OpenGL (перевернуть зелёный)", r))
        if mz < LIMITS["normal_z_fail"]:
            find.append(("fail", "normal_bark", f"нормали: среднее z {mz:.2f} — рельеф «корой» (высота сложилась, а не уровень)", mz))
        elif mz < LIMITS["normal_z_warn"]:
            find.append(("warn", "normal_bark", f"нормали: среднее z {mz:.2f} — рельеф сильный", mz))
        rep["normal"] = nrep

    # --- длинные царапины («каток») ---
    sig = max(1.0, LIMITS["scratch_sigma_cm"] * dens)
    rs = cv2.GaussianBlur(rough, (0, 0), sig)
    # Собель 3×3: вторая производная ×4, первая ×8 — приводим к настоящим
    rxx = cv2.Sobel(rs, cv2.CV_32F, 2, 0, ksize=3) / 4
    ryy = cv2.Sobel(rs, cv2.CV_32F, 0, 2, ksize=3) / 4
    rxy = cv2.Sobel(rs, cv2.CV_32F, 1, 1, ksize=3) / 4
    gx = cv2.Sobel(rs, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(rs, cv2.CV_32F, 0, 1, ksize=3) / 8
    tr = (rxx + ryy) / 2
    dt = np.sqrt(((rxx - ryy) / 2) ** 2 + rxy ** 2)
    l1, l2 = np.abs(tr + dt), np.abs(tr - dt)
    big, small = np.maximum(l1, l2), np.minimum(l1, l2)
    line = (big - small) * sig * sig
    thr = LIMITS["scratch_contrast"] * 0.35
    # у ступеньки (край зоны износа) рядом с пиком второй производной большой наклон, у тонкой линии — нет
    step = np.sqrt(gx * gx + gy * gy) * sig > 0.5 * line
    # у края острова размытие видит ступеньку в отступе между соседними островами — это не царапина
    edge = cv2.distanceTransform(mask, cv2.DIST_L2, 3) <= 3 * sig + 1
    # и на границе двух материалов (металл рядом с неметаллом) — тоже
    mg = cv2.GaussianBlur(metal, (0, 0), 1.0)
    mgrad = np.sqrt(cv2.Sobel(mg, cv2.CV_32F, 1, 0, ksize=3) ** 2 + cv2.Sobel(mg, cv2.CV_32F, 0, 1, ksize=3) ** 2) / 8
    k_ = int(2 * (3 * sig + 1)) | 1
    edge |= cv2.dilate((mgrad > 0.05).astype(np.uint8), np.ones((k_, k_), np.uint8)) > 0
    lines = (line > thr) & (big > 2.5 * small) & ~step & sel & ~edge
    if tilt is not None:
        geo = cv2.dilate((tilt > LIMITS["scratch_tilt_skip"]).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        lines &= ~geo
    lines = ndimage.binary_opening(lines, structure=np.ones((2, 2))) if sig > 1.5 else lines
    sk = skeletonize(lines)
    lab_sk, nlab = ndimage.label(sk, structure=np.ones((3, 3)))
    long_len = 0.0
    n_long = 0
    angles = []
    long_mask = np.zeros_like(sk)
    if nlab:
        sizes = ndimage.sum(sk, lab_sk, index=np.arange(1, nlab + 1))
        min_px = LIMITS["scratch_long_cm"] * dens
        objs = ndimage.find_objects(lab_sk)
        for i, (sz, sl) in enumerate(zip(sizes, objs)):
            if sz < min_px:
                continue
            ys, xs = np.nonzero(lab_sk[sl] == i + 1)
            ext = math.hypot(xs.max() - xs.min(), ys.max() - ys.min())
            if ext < 0.6 * min_px or ext < 0.6 * sz:     # клубок, кольцо вокруг отверстия, дуга — не царапина
                continue
            n_long += 1
            long_len += sz * 1.12 / dens
            cov = np.cov(np.stack([xs, ys]).astype(np.float64)) if len(xs) > 2 else np.eye(2)
            ev, evec = np.linalg.eigh(cov)
            angles.append((math.atan2(evec[1, 1], evec[0, 1]) % math.pi, sz))
            long_mask[sl] |= lab_sk[sl] == i + 1
    area_cm2 = float(sel.sum()) / (dens * dens)
    dens_scr = long_len / max(area_cm2, 1e-6) * 100.0
    ent = None
    if angles:
        hist = np.zeros(12)
        for a_, wgt in angles:
            hist[int(a_ / math.pi * 12) % 12] += wgt
        p = hist / hist.sum()
        ent = float(-(p[p > 0] * np.log(p[p > 0])).sum() / math.log(12))
    rep["scratches"] = {"long_count": n_long, "long_cm": round(long_len, 1), "cm_per_100cm2": round(dens_scr, 1),
                        "direction_spread": round(ent, 2) if ent is not None else None, "surface_cm2": round(area_cm2, 1)}
    if dens_scr > LIMITS["scratch_density_fail"] and (ent is None or ent > 0.6):
        find.append(("fail", "rink", f"«каток»: длинных царапин {dens_scr:.0f} см на 100 см² во все стороны — оставить редкие, по направлению движения", dens_scr))
    elif dens_scr > LIMITS["scratch_density_warn"] and (ent is None or ent > 0.6):
        find.append(("warn", "rink", f"длинных царапин {dens_scr:.0f} см на 100 см²", dens_scr))

    rep["findings"] = [{"set": key, "level": lv, "code": c, "text": t, "value": round(float(v), 3)} for lv, c, t, v in find]

    if diag_dir:
        os.makedirs(diag_dir, exist_ok=True)
        write_diag(os.path.join(diag_dir, key + ".png"), color, rough, mask, bad_dark | bad_bright, bad_metal, grey,
                   flat_diag, soap, link, long_mask, w, h)
        rep["diag"] = os.path.join(diag_dir, key + ".png")
    rep["_per_object"] = object_tones(mesh, lab, rough, w, h) if mesh is not None else None
    return rep


def object_tones(mesh, lab, rough, w, h):
    """Средний тон и блеск каждой детали набора — «все детали одной заливкой»."""
    ids = np.zeros((h, w), np.int32)
    pts = np.round(np.stack([mesh["uv"][..., 0] * w, mesh["uv"][..., 1] * h], axis=-1) * 16).astype(np.int32)
    for t, oi in zip(pts, mesh["obj"]):
        cv2.fillConvexPoly(ids, t, int(oi) + 1, cv2.LINE_8, 4)
    res = []
    for oi, name in enumerate(mesh["objects"]):
        s = ids == oi + 1
        if s.sum() < 400:
            continue
        res.append({"name": name, "L": float(np.median(lab[..., 0][s])), "a": float(np.median(lab[..., 1][s])),
                    "b": float(np.median(lab[..., 2][s])), "rough": float(np.median(rough[s])) * 100, "px": int(s.sum())})
    return res


def write_diag(path, color, rough, mask, pbr_bad, metal_bad, grey, flat, soap, link, long_mask, w, h):
    """Четыре панели в развёртке: PBR | однотонность (R — издали, G — средне, B — вблизи) | мыло и царапины | связь."""
    R = DIAG_RES
    m = up_to(mask, R, R, cv2.INTER_NEAREST) > 0
    dim = lambda img: np.where(m[..., None], img, img * 0.25)  # noqa: E731
    c = up_to(color, R, R)
    p1 = c.copy()
    for msk, col in ((pbr_bad, (1, 0, 0)), (metal_bad, (0, 1, 1)), (grey, (1, 1, 0))):
        mm = up_to(msk.astype(np.float32), R, R) > 0.3
        p1[mm] = p1[mm] * 0.3 + np.array(col) * 0.7
    p1 = dim(p1)
    p2 = np.zeros((R, R, 3), np.float32)
    for i, s in enumerate(("far", "mid", "near")):
        f, ok = flat[s]
        p2[..., i] = up_to(f.astype(np.float32), R, R, cv2.INTER_NEAREST)
        p2[..., i] = np.where(up_to(ok.astype(np.float32), R, R, cv2.INTER_NEAREST) > 0, p2[..., i], 0.15)
    p2 = dim(p2)
    rr = up_to(rough, R, R)
    p3 = np.repeat(rr[..., None], 3, axis=2) * 0.8
    for s in ("far", "mid"):
        if s in soap:
            sp, act = soap[s]["_map"]
            mm = up_to(sp.astype(np.float32), R, R) > 0.5
            p3[mm] = p3[mm] * 0.4 + np.array([0.1, 0.3, 1.0]) * 0.6
    lm = cv2.dilate(up_to(long_mask.astype(np.float32), R, R), np.ones((3, 3), np.uint8)) > 0.2
    p3[lm] = (1, 0.1, 0.1)
    p3 = dim(p3)
    p4 = c * 0.35
    for s in ("far", "mid"):
        if s in link:
            spot, pair = link[s]["_map"]
            ms = up_to(spot.astype(np.float32), R, R) > 0.5
            mp = up_to(pair.astype(np.float32), R, R) > 0.5
            p4[ms & ~mp] = (0.9, 0.15, 0.1)
            p4[mp] = (0.1, 0.85, 0.2)
    p4 = dim(p4)
    top = np.concatenate([p1, p2], axis=1)
    bot = np.concatenate([p3, p4], axis=1)
    img = (np.clip(np.concatenate([top, bot], axis=0), 0, 1) * 255).astype(np.uint8)
    for (x, y), t in (((8, 24), "PBR: red dielectric out, cyan metal dark, yellow grey metal"),
                      ((R + 8, 24), "flat: R far  G mid  B near (white = flat everywhere)"),
                      ((8, R + 24), "roughness: blue soap, red long scratches"),
                      ((R + 8, R + 24), "color spots: green paired in roughness, red unpaired")):
        cv2.putText(img, t, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, t, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", img[..., ::-1])
    buf.tofile(path)


# ---------- ассет целиком ----------

def check_asset(inputs, meshes, out_dir, only=None, dens_override=None, skip=km.LOD_SKIP):
    sets = find_sets(inputs)
    if only:
        sets = {k: v for k, v in sets.items() if k in only}
    mats = []
    for p in meshes or []:
        ext = os.path.splitext(p)[1].lower()
        if ext in (".gltf", ".glb"):
            mats += km.read_gltf(p, skip)
        elif ext == ".json":
            mats += km.read_dump(p)
        else:
            raise RuntimeError("развёртка из " + ext + " — сначала review.py uvdump (Blender)")
    matched = km.match_sets(mats, list(sets)) if mats else {}
    rep = {"sets": {}, "findings": []}
    diag = os.path.join(out_dir, "diag")
    for key in sorted(sets):
        mesh = km.merge(matched[key]) if key in matched else None
        print("набор", key, "развёртка:", (mesh["name"] if mesh else "нет"), flush=True)
        r = check_set(key, sets[key], mesh, dens_override, diag)
        rep["sets"][key] = r
        rep["findings"] += r["findings"]
    asset_checks(rep)
    for r in rep["sets"].values():
        r.pop("_per_object", None)
    order = {"fail": 0, "warn": 1, "info": 2}
    rep["findings"].sort(key=lambda f: (order[f["level"]], f["set"]))
    rep["verdict"] = "исправить" if any(f["level"] == "fail" for f in rep["findings"]) else (
        "посмотреть" if any(f["level"] == "warn" for f in rep["findings"]) else "чисто")
    return rep


def asset_checks(rep):
    sets = rep["sets"]
    dens = [(k, r["uv"]["px_cm"]["p50"], r["uv"]["area_cm2"]) for k, r in sets.items() if r.get("uv")]
    if len(dens) > 1:
        v = np.array([d[1] for d in dens])
        a = np.array([d[2] for d in dens])
        med = km.wpercentile(v, a, 50)
        rep["asset_px_cm_p50"] = round(med, 1)
        for k, d, ar in dens:
            if d < LIMITS["density_rel_warn"] * med and ar > 20:
                rep["findings"].append({"set": k, "level": "warn", "code": "density_rel",
                                        "text": f"плотность {d:.0f} пикс/см против {med:.0f} у ассета — рядом с соседями будет мыльнее, процедуры крупнее",
                                        "value": round(d, 1)})
    for k, r in sets.items():
        po = r.get("_per_object") or []
        big = [p for p in po if p["px"] > 2000]
        if len(big) >= 3:
            L = np.array([p["L"] for p in big])
            ab = np.array([[p["a"], p["b"]] for p in big])
            ro = np.array([p["rough"] for p in big])
            de = np.sqrt((L - L.mean()) ** 2 + ((ab - ab.mean(axis=0)) ** 2).sum(axis=1))
            if de.max() < LIMITS["same_parts_de"] and (ro.max() - ro.min()) < LIMITS["same_parts_rough"]:
                rep["findings"].append({"set": k, "level": "warn", "code": "same_parts",
                                        "text": f"{len(big)} деталей одной заливкой (ΔE ≤ {de.max():.1f}, блеск ± {(ro.max() - ro.min()) / 2:.1f}) — развести оттенком и блеском",
                                        "value": round(float(de.max()), 2)})


def text_report(rep, title=""):
    lines = []
    if title:
        lines.append(title)
    lines.append(f"Итог: {rep['verdict']}")
    fails = [f for f in rep["findings"] if f["level"] == "fail"]
    warns = [f for f in rep["findings"] if f["level"] == "warn"]
    if fails:
        lines.append("")
        lines.append("Исправить до показа:")
        lines += [f"  [{f['set']}] {f['text']}" for f in fails]
    if warns:
        lines.append("")
        lines.append("Посмотреть:")
        lines += [f"  [{f['set']}] {f['text']}" for f in warns]
    lines.append("")
    lines.append("Наборы (пикс/см · заполнение · однотонно издали/средне/вблизи · мыло · пары цвет→блеск · царапины см/100см²):")
    for k, r in rep["sets"].items():
        uv = r.get("uv")
        v = r["variety"]
        fl = "/".join((f"{v[s]['flat']:.0%}" if v[s]["judged"] else "—") for s in ("far", "mid", "near"))
        so = r["soap"]
        sp = max([x["soap"] for x in so.values() if x.get("soap") is not None] or [0])
        lk = [x["paired"] for x in r["link"].values() if x.get("paired") is not None]
        lines.append(f"  {k}: {r['px_cm_used']:.0f} · {(uv['fill'] if uv else float('nan')):.0%} · {fl} · {sp:.0%} · "
                     f"{(min(lk) if lk else float('nan')):.0%} · {r['scratches']['cm_per_100cm2']:.0f}")
    return "\n".join(lines) + "\n"
