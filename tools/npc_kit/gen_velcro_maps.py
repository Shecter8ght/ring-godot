"""Карты липучки подсумков — свой рисунок по макрофото (владелец 2026-10-23: «на площадке, к которой крючки лепятся,
должна быть текстура липучки… как ворс, только жестковатый — за него цепляются маленькие крючки на ремешке»).

«Петля» (мягкая сторона): густой спутанный ворс из тонких кудрявых нейлоновых волокон — каждая ворсинка
скручивается кольцами 0,3–1 мм, лежат вразнобой слоями, между ними тёмные провалы до основы.
«Крючок» (жёсткая сторона): ряды литых крючков из лески — дуга ~0,7 мм, ряды вдоль ленты, соседние крючки
развёрнуты в разные стороны; под ними — рубчик тканой основы.

Рисунок: волокна — случайные кривые с плавно меняющейся кривизной, вдавлены по высоте (верхние перекрывают нижние),
бесшовно (координаты по модулю тайла). Высота — 16 бит; «тень» — глубина ворса (провалы темнее).
Там же — стропа язычка («ремешок… должен тоже иметь подходящую текстуру»): саржевое переплетение 2/1 нейлоновой
стропы — нити основы вдоль ленты, косой рубчик, волоски вдоль нитей.

python -X utf8 tools/npc_kit/gen_velcro_maps.py → _asset_src/npc_kit/tex_gen/velcro_{loop,hook}_{height,shade}.png,
webbing_twill_{height,shade}.png (петля — тайл 16 мм, крючок — 8 мм, стропа — 6 мм)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_npc_camo import OUT  # noqa: E402

LOOP_PX, LOOP_MM = 2048, 16.0
HOOK_PX, HOOK_MM = 1024, 8.0


def stamp(hmap: np.ndarray, xs: np.ndarray, ys: np.ndarray, hs: np.ndarray, rad: float) -> None:
    """Волокно сечением-цилиндром: по каждой точке кривой — диск радиуса rad (пикс.), высота — h + выпуклость сечения;
    берётся наибольшая (верхнее волокно закрывает нижнее)."""
    n = hmap.shape[0]
    r = int(np.ceil(rad))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d2 = (dx * dx + dy * dy) / (rad * rad)
            if d2 > 1.0:
                continue
            bulge = np.sqrt(1.0 - d2)
            ix = (np.rint(xs).astype(np.int64) + dx) % n
            iy = (np.rint(ys).astype(np.int64) + dy) % n
            np.maximum.at(hmap, (iy, ix), hs + bulge * rad * 0.6)


def curly(rng: np.random.Generator, count: int, steps: int, step_px: float, r_curl: tuple[float, float],
          n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """count кудрявых волокон: шаг вдоль, кривизна плавно меняется (кольца радиусом r_curl пикс.), иногда меняет знак;
    высота — своя у волокна, колеблется вдоль (волокно ныряет в ворс и выходит)."""
    x = rng.uniform(0, n, count)
    y = rng.uniform(0, n, count)
    a = rng.uniform(0, 2 * np.pi, count)
    k0 = 1.0 / rng.uniform(*r_curl, count) * rng.choice((-1.0, 1.0), count)
    h0 = rng.uniform(0.0, 1.0, count)
    ph = rng.uniform(0, 2 * np.pi, count)
    xs, ys, hs = [], [], []
    k = k0.copy()
    for s in range(steps):
        k += rng.normal(0.0, 0.25, count) * np.abs(k0)
        flip = rng.random(count) < 0.02
        k[flip] *= -1.0
        a += k * step_px
        x += np.cos(a) * step_px
        y += np.sin(a) * step_px
        xs.append(x.copy())
        ys.append(y.copy())
        hs.append(h0 + 0.18 * np.sin(ph + s * 0.21))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(hs)


def normalize(h: np.ndarray) -> np.ndarray:
    lo, hi = np.quantile(h[::4, ::4], 0.01), np.quantile(h[::4, ::4], 0.995)
    return np.clip((h - lo) / (hi - lo + 1e-9), 0.0, 1.0)


def save(h: np.ndarray, shade: np.ndarray, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((h * 65535).astype(np.uint16)).save(OUT / f"{name}_height.png")
    Image.fromarray((shade * 255).astype(np.uint8), "L").save(OUT / f"{name}_shade.png")
    print("VELCRO", OUT / f"{name}_height.png")


def loop_map() -> None:
    rng = np.random.default_rng(1957)
    n = LOOP_PX
    px_mm = n / LOOP_MM
    h = np.full((n, n), -6.0, np.float32)
    # основа — мелкое плетение под ворсом (видна в провалах)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    weave = 0.5 + 0.5 * np.sin(xx / px_mm * 2 * np.pi / 0.35) * np.sin(yy / px_mm * 2 * np.pi / 0.35)
    h = np.maximum(h, -5.0 + 0.4 * weave)
    # три слоя ворса: глубокий густой с тугими кольцами, средний, верхний реже и кольца крупнее
    for count, steps, (c0, c1), rad, lift in ((14000, 60, (0.10, 0.25), 2.2, -0.55), (10000, 70, (0.15, 0.40), 2.6, -0.15),
                                              (4000, 80, (0.25, 0.60), 2.8, 0.25)):
        x, y, z = curly(rng, count, steps, 1.6, (c0 * px_mm, c1 * px_mm), n)
        stamp(h, x, y, (lift + z * 0.4).astype(np.float32) * 6.0, rad)
    hn = normalize(h)
    shade = 0.35 + 0.65 * hn ** 0.7                      # провалы ворса темнее (свет туда не доходит)
    save(hn, shade, "velcro_loop")


def hook_map() -> None:
    rng = np.random.default_rng(1948)
    n = HOOK_PX
    px_mm = n / HOOK_MM
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    # основа — рубчик тканой ленты поперёк (шаг 0,25 мм)
    h = (-1.0 + 0.10 * (0.5 + 0.5 * np.sin(yy / px_mm * 2 * np.pi / 0.25))).astype(np.float32)
    # крючки рядами вдоль ленты (x): ряды через 0,5 мм, в ряду через 0,65 мм, соседние ряды сдвинуты на полшага.
    # Сверху крючок — короткая перекладина вдоль ряда: стебель от основы поднимается, загиб — самая высокая точка
    # и чуть толще (там блестит); в соседних рядах загиб смотрит в разные стороны.
    row_mm, col_mm = 0.5, 0.65
    rows, cols = int(round(HOOK_MM / row_mm)), int(round(HOOK_MM / col_mm))
    col_mm = HOOK_MM / cols                                  # ровно в тайл — без шва
    t = np.linspace(0.0, 1.0, 36)
    for thick, part in ((0.075, (0.0, 1.0)), (0.10, (0.62, 1.0))):
        xs, ys, hs = [], [], []
        for i in range(rows):
            d = 1.0 if i % 2 else -1.0
            for j in range(cols):
                cx = (j + 0.5 * (i % 2)) * col_mm * px_mm + rng.normal(0, 0.05 * px_mm)
                cy = i * row_mm * px_mm + rng.normal(0, 0.04 * px_mm)
                ang = rng.normal(0, 0.18)
                ln = rng.uniform(0.38, 0.48) * px_mm
                tt = part[0] + (part[1] - part[0]) * t
                lx = d * (tt - 0.5) * ln
                ly = 0.06 * px_mm * np.sin(np.pi * tt)
                xs.append(cx + lx * np.cos(ang) - ly * np.sin(ang))
                ys.append(cy + lx * np.sin(ang) + ly * np.cos(ang))
                hs.append(0.15 + 0.85 * np.sin(np.pi * 0.5 * np.clip(tt / 0.75, 0, 1)) - 0.25 * np.clip((tt - 0.75) / 0.25, 0, 1))
        stamp(h, np.concatenate(xs), np.concatenate(ys), (np.concatenate(hs) * 9.0).astype(np.float32), thick * px_mm)
    hn = normalize(h)
    shade = 0.30 + 0.70 * hn ** 0.8
    save(hn, shade, "velcro_hook")


def blur(h: np.ndarray, sigma: float) -> np.ndarray:
    """Бесшовное размытие (гаусс в частотной области), σ в пикселях."""
    f = np.fft.fftfreq(h.shape[0])
    g = np.exp(-2 * np.pi ** 2 * sigma ** 2 * (f[None, :] ** 2 + f[:, None] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(h) * g)).astype(np.float32)


def webbing_map() -> None:
    """Саржа 3/1 с лица основы (как у нейлоновой стропы): нить основы (вдоль ленты, x) идёт поверх трёх нитей утка
    и под одной, со сдвигом на нить — косой рубчик; уток виден только в узких провалах. Нить — валик с волосками
    вдоль, перекрытие выпуклое по длине."""
    rng = np.random.default_rng(1942)
    n, mm = 1024, 6.0
    yarn = 0.30                                              # шаг нитей основы и утка, мм
    cells = int(round(mm / yarn))
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) * (mm / n)
    i = np.floor(yy / yarn).astype(int) % cells             # нить основы (поперёк ленты — по y)
    j = np.floor(xx / yarn).astype(int) % cells             # нить утка (вдоль ленты — по x)
    fy, fx = (yy / yarn) % 1.0, (xx / yarn) % 1.0
    k = (i + j) % 4
    along = (np.maximum(k - 1, 0) + fx) / 3.0               # место на перекрытии в три утка
    h_warp = np.sin(np.pi * fy) ** 0.5 * (0.6 + 0.4 * np.sin(np.pi * along))
    h_weft = np.sin(np.pi * fx) ** 0.5 * 0.18
    h = np.where(k != 0, h_warp, h_weft)
    phase = rng.uniform(0, 6.28, (cells, cells))[i, j]
    h = h + 0.03 * np.sin(fy * np.pi * 9 + phase) * (k != 0) + rng.normal(0, 0.004, (n, n)).astype(np.float32)
    hn = normalize(blur(h, 1.5))
    save(hn, 0.6 + 0.4 * hn, "webbing_twill")


if __name__ == "__main__":
    loop_map()
    hook_map()
    webbing_map()
