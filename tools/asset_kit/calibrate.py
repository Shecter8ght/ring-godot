# Проверка порогов review.py maps: принятые карты ВЕРАС-54 и ПМ проходят без «исправить», а копии карт ВЕРАС,
# испорченные так, как владелец ругал ВСС-М 25–26.10, ловятся. Запускать после правки LIMITS в kit_maps.py.
#   python -X utf8 tools/asset_kit/calibrate.py [папка для копий]
import os
import shutil
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import kit_maps as KM  # noqa: E402
import kit_mesh as km  # noqa: E402

VERAS = os.path.join(ROOT, "assets/models/weapons/veras54")
PM = os.path.join(ROOT, "assets/models/weapons/pm")
rng = np.random.default_rng(7)


def rd(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)


def wr(p, im):
    cv2.imencode(".png", im)[1].tofile(p)


def smooth_noise(h, w, sigma_px):
    """Мягкие пятна: шум на грубой сетке, размытый и растянутый — как объёмный шум без резкого края."""
    k = max(1, int(sigma_px / 4))
    n = rng.standard_normal((h // k + 2, w // k + 2)).astype(np.float32)
    n = cv2.GaussianBlur(n, (0, 0), sigma_px / k)
    n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    return n / (n.std() + 1e-6)


def copy_set(src_dir, key, dst):
    os.makedirs(dst, exist_ok=True)
    files = {}
    for f in os.listdir(src_dir):
        if f.endswith(".png") and km.set_key(f) == key:
            shutil.copy(os.path.join(src_dir, f), os.path.join(dst, f))
            files[km.channel_of(f)] = os.path.join(dst, f)
    return files


def defect(kind, files, dens):
    col = rd(files["color"])
    orm = rd(files["orm"])
    h, w = col.shape[:2]
    if kind == "soap":           # «мыльные паттерны»: ровный мат с мягкими шумовыми пятнами
        blob = smooth_noise(h, w, 1.5 * dens)
        blob2 = smooth_noise(h, w, 0.8 * dens)
        r = np.clip(0.72 + 0.09 * blob + 0.04 * blob2, 0, 1)
        orm[..., 1] = (r * 255).astype(np.uint8)
        base = np.median(col.reshape(-1, 3), axis=0)
        col = np.clip(base[None, None, :] * (1 + 0.18 * blob[..., None] + 0.08 * blob2[..., None]), 0, 255).astype(np.uint8)
        os.remove(files.pop("coat"))
    elif kind == "rink":         # «каток, исцарапанный коньками»: длинные хаотичные царапины по всей поверхности
        layer = np.zeros((h, w), np.uint8)
        n = int(1.2 * w * h / (dens * dens) / 6)          # ~120 см на 100 см² развёртки
        for _ in range(n):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            a = rng.uniform(0, np.pi * 2)
            pts = []
            for _s in range(6):
                pts.append((x, y))
                step = rng.uniform(0.8, 1.4) * dens
                a += rng.normal(0, 0.12)
                x, y = x + np.cos(a) * step, y + np.sin(a) * step
            cv2.polylines(layer, [np.round(np.array(pts) * 16).astype(np.int32)], False, 255, 1, cv2.LINE_AA, 4)
        m = layer.astype(np.float32) / 255
        orm[..., 1] = np.clip(orm[..., 1] - 70 * m, 0, 255).astype(np.uint8)
        col = np.clip(col.astype(np.float32) + 25 * m[..., None], 0, 255).astype(np.uint8)
    elif kind == "grey":         # серое однообразие: заливка с едва заметным шумом, без пятен блеска и плёнки
        base = np.median(col.reshape(-1, 3), axis=0)
        col = np.clip(base[None, None, :] + rng.normal(0, 0.6, (h, w, 1)), 0, 255).astype(np.uint8)
        orm[..., 1] = np.clip(185 + rng.normal(0, 0.6, (h, w)), 0, 255).astype(np.uint8)
        os.remove(files.pop("coat"))
    elif kind == "unlinked":     # пятна только в цвете: шероховатость их не знает
        spots = (smooth_noise(h, w, 0.25 * dens) > 0.9).astype(np.float32)
        spots = cv2.GaussianBlur(spots, (0, 0), 1.5)
        col = np.clip(col.astype(np.float32) * (1 - 0.45 * spots[..., None]) + 30 * spots[..., None], 0, 255).astype(np.uint8)
    elif kind == "black":        # неметалл «чёрной дырой»
        col = (col.astype(np.float32) * 0.22).astype(np.uint8)
    elif kind == "directx":
        nm = rd(files["normal"])
        nm[..., 1] = 255 - nm[..., 1]                     # BGR: зелёный — тот же индекс
        wr(files["normal"], nm)
    elif kind == "bark":         # рельеф «корой»: высота сложилась
        nm = rd(files["normal"]).astype(np.float32) / 127.5 - 1
        bump = smooth_noise(h, w, 0.08 * dens)
        gx = cv2.Sobel(bump, cv2.CV_32F, 1, 0) * 1.6
        gy = cv2.Sobel(bump, cv2.CV_32F, 0, 1) * 1.6
        n = np.stack([np.ones_like(gx), -gy, -gx], axis=-1)    # BGR: z, y, x
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        wr(files["normal"], ((n + 1) * 127.5).astype(np.uint8))
    elif kind == "lowres":       # «мыльные прицелы»: та же развёртка в карте вчетверо меньше
        for ch, p in list(files.items()):
            im = rd(p)
            wr(p, cv2.resize(im, (im.shape[1] // 4, im.shape[0] // 4), interpolation=cv2.INTER_AREA))
        return
    wr(files["color"], col)
    wr(files["orm"], orm)


CASES = [  # (вид порчи, набор ВЕРАС, код, который должен выйти с «исправить»)
    ("soap", "veras54_Steel_100", "soap_"),
    ("rink", "veras54_Steel_100", "rink"),
    ("grey", "veras54_Steel_100", "flat_mid"),
    ("unlinked", "veras54_Steel_100", "link"),
    ("black", "veras54_Polymer_100", "pbr_dark"),
    ("directx", "veras54_Polymer_100", "normal_dx"),
    ("bark", "veras54_Steel_100", "normal_bark"),
    ("lowres", "veras54_Steel_100", "density"),
]


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="review_cal_")
    ok = True
    rows = []
    for name, folder, gltf in (("ВЕРАС-54", VERAS, "veras54.gltf"), ("ПМ", PM, "pm.gltf")):
        mats = km.read_gltf(os.path.join(folder, gltf))
        sets = KM.find_sets([folder])
        matched = km.match_sets(mats, list(sets))
        for key in sorted(sets):
            r = KM.check_set(key, sets[key], km.merge(matched[key]) if key in matched else None)
            fails = [f["code"] for f in r["findings"] if f["level"] == "fail"]
            warns = [f["code"] for f in r["findings"] if f["level"] == "warn"]
            good = not fails
            ok &= good
            rows.append(f"{'ок ' if good else 'НЕТ'} принят {name} {key}: исправить {fails or '—'}, посмотреть {warns or '—'}")
    mats = km.read_gltf(os.path.join(VERAS, "veras54.gltf"))
    for kind, key, code in CASES:
        dst = os.path.join(work, kind)
        shutil.rmtree(dst, ignore_errors=True)
        files = copy_set(VERAS, key, dst)
        mesh = km.merge(km.match_sets(mats, [key])[key])
        d, a, _, _ = km.density(mesh, *rd(files["color"]).shape[1::-1])
        defect(kind, files, km.wpercentile(d, a, 50))
        sets = KM.find_sets([dst])
        r = KM.check_set(key, sets[key], mesh)
        fails = [f["code"] for f in r["findings"] if f["level"] == "fail"]
        good = any(c.startswith(code) for c in fails)
        ok &= good
        rows.append(f"{'ок ' if good else 'НЕТ'} порча «{kind}» {key}: ждём {code}, исправить {fails or '—'}")
    print("\n".join(rows))
    print("ПОРОГИ В ПОРЯДКЕ" if ok else "ПОРОГИ НЕ СХОДЯТСЯ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
