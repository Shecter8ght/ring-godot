# Разбор кадров review.py render: фон студии под прозрачный рендер, экспозиция по предмету,
# «издали» — разнообразие тона и блеска на снимках каналов (сбоку и с камеры игры), где видна вся модель целиком.
import json
import math
import os

import cv2
import numpy as np

from kit_maps import LIMITS, imread

BG = 0.25                       # фон студии, sRGB: тёмно-серый — видны и чёрная сталь, и светлые детали
EXPOSURE = {"clip_warn": 0.02, "crush_warn": 0.35, "median_lo": 0.08, "median_hi": 0.75}


def rgba(path):
    data = np.fromfile(path, dtype=np.uint8)
    im = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if im is None or im.ndim < 3 or im.shape[2] < 4:
        return None
    im = im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)  # dtype до приведения
    return im[..., [2, 1, 0]], im[..., 3]


def save_rgb(path, rgb):
    cv2.imencode(".png", (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)[..., ::-1])[1].tofile(path)


def blur_masked(img, m, sigma):
    num = cv2.GaussianBlur(img * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    return num / np.maximum(den, 1e-4)


def far_variety(color, rough, mask, px_cm):
    """Пятна ~4 см на снимке: полоса между σ и 2σ, локальное отклонение — как в картах, но по всей видимой модели."""
    lam = LIMITS["scales_cm"]["far"] * px_cm
    s1 = max(1.0, lam / 4)
    m = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(s1 / 2))).astype(np.float32)
    if m.sum() < 500:
        return None
    lab = cv2.cvtColor(np.ascontiguousarray(color), cv2.COLOR_RGB2Lab)
    r100 = rough * 100.0
    res = {"lambda_px": round(lam, 1)}
    bands = []
    for img in (lab[..., 0], lab[..., 1], lab[..., 2], r100):
        b = blur_masked(img, m, s1) - blur_masked(img, m, 2 * s1)
        bands.append(b)
    eC = bands[0] ** 2 + bands[1] ** 2 + bands[2] ** 2
    eR = bands[3] ** 2
    rC = np.sqrt(blur_masked(eC, m, lam / 2))
    rR = np.sqrt(blur_masked(eR, m, lam / 2))
    ok = m > 0.5
    flat = ok & (rC < LIMITS["flat_color_de"]["far"]) & (rR < LIMITS["flat_rough"]["far"])
    lowL = blur_masked(lab[..., 0], m, s1)
    lowR = blur_masked(r100, m, s1)
    res.update({"flat": round(float(flat.sum() / ok.sum()), 3),
                "flat_color": round(float((ok & (rC < LIMITS["flat_color_de"]["far"])).sum() / ok.sum()), 3),
                "flat_rough": round(float((ok & (rR < LIMITS["flat_rough"]["far"])).sum() / ok.sum()), 3),
                "tone_spread_L": round(float(np.percentile(lowL[ok], 95) - np.percentile(lowL[ok], 5)), 2),
                "gloss_spread": round(float(np.percentile(lowR[ok], 95) - np.percentile(lowR[ok], 5)), 2)})
    return res, flat, ok


def finish(out):
    with open(os.path.join(out, "views.json"), encoding="utf-8") as f:
        meta = json.load(f)
    rep = {"views": {}, "far": {}, "findings": []}
    for n, v in meta["views"].items():
        p = os.path.join(out, n + ".png")
        got = rgba(p) if os.path.exists(p) else None
        if got is None:
            continue
        rgb, a = got
        comp = rgb * a[..., None] + BG * (1 - a[..., None])
        save_rgb(p, comp)
        obj = a > 0.99
        st = {"object_share": round(float(obj.mean()), 3), "px_per_cm": v["px_per_cm_at_target"]}
        if obj.sum() > 100:
            lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
            lo = lum[obj]
            st.update({"lum_p2_p50_p98": [round(float(np.percentile(lo, q)), 3) for q in (2, 50, 98)],
                       "clipped": round(float((rgb[obj].max(axis=1) > 0.98).mean()), 4),
                       "crushed": round(float((lo < 0.03).mean()), 3)})
            if not v.get("rake"):
                if st["clipped"] > EXPOSURE["clip_warn"]:
                    rep["findings"].append({"set": "render:" + n, "level": "warn", "code": "exposure_clip",
                                            "text": f"пересвет на {st['clipped']:.0%} предмета — блики выбиты в белое", "value": st["clipped"]})
                if st["crushed"] > EXPOSURE["crush_warn"]:
                    rep["findings"].append({"set": "render:" + n, "level": "warn", "code": "exposure_crush",
                                            "text": f"провал в чёрное на {st['crushed']:.0%} предмета — не видно ни тона, ни блеска", "value": st["crushed"]})
        rep["views"][n] = st
        if "color" in v.get("channels", []) and "rough" in v.get("channels", []):
            c = rgba(os.path.join(out, f"{n}__color.png"))
            r = rgba(os.path.join(out, f"{n}__rough.png"))
            if c is None or r is None:
                continue
            fv = far_variety(c[0], r[0][..., 0], c[1] > 0.99, v["px_per_cm_at_target"])
            for ch in v["channels"]:
                pp = os.path.join(out, f"{n}__{ch}.png")
                g = rgba(pp)
                if g is not None:
                    save_rgb(pp, g[0] * g[1][..., None] + BG * (1 - g[1][..., None]))
            if fv is None:
                continue
            res, flat, ok = fv
            rep["far"][n] = res
            vis = cv2.cvtColor(np.ascontiguousarray(c[0]), cv2.COLOR_RGB2GRAY)
            vis = np.repeat(vis[..., None], 3, axis=2) * 0.6
            vis[flat] = vis[flat] * 0.4 + np.array([1.0, 0.2, 0.1]) * 0.6
            vis[~ok] *= 0.3
            save_rgb(os.path.join(out, f"{n}__far_flat.png"), vis)
            if res["flat"] > LIMITS["render_far_fail"]:
                rep["findings"].append({"set": "render:" + n, "level": "fail", "code": "flat_far",
                                        "text": f"издали (~4 см): однотонно {res['flat']:.0%} видимой модели — нужны крупные пятна тона и блеска (Soft Light, парой в шероховатости)",
                                        "value": res["flat"]})
            elif res["flat"] > LIMITS["render_far_warn"]:
                rep["findings"].append({"set": "render:" + n, "level": "warn", "code": "flat_far",
                                        "text": f"издали (~4 см): однотонно {res['flat']:.0%} видимой модели", "value": res["flat"]})
    with open(os.path.join(out, "render.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return rep


def text_report(rep):
    lines = ["Рендер:"]
    for f in rep["findings"]:
        lines.append(f"  [{f['level']}] {f['set']}: {f['text']}")
    for n, r in rep["far"].items():
        lines.append(f"  издали {n}: однотонно {r['flat']:.0%} (тон {r['flat_color']:.0%}, блеск {r['flat_rough']:.0%}), "
                     f"разброс тона L* {r['tone_spread_L']}, блеска {r['gloss_spread']} сотых")
    for n, v in rep["views"].items():
        if "lum_p2_p50_p98" in v:
            lines.append(f"  {n}: яркость {v['lum_p2_p50_p98']}, пересвет {v['clipped']:.1%}, в чёрном {v['crushed']:.0%}, "
                         f"{v['px_per_cm']} пикс/см")
    return "\n".join(lines) + "\n"
