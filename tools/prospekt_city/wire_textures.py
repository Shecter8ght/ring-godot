"""«Проспект», ограждения и город: плиточные карты проволоки для игровых лент (без Painter).

    python -X utf8 tools/prospekt_city/wire_textures.py <папка> [Razor Barbed Rebar]

Razor_* — лента АКЛ поперёк полосы 48 мм: сама лента 22 мм с обжатым сердечником Ø 2,5 мм посередине, по каждой
кромке две пары лезвий на плитку 74 мм (шаг 37 мм, как у подробной формы). Barbed_* — нить колючки поперёк 40 мм: две
проволоки Ø 2 мм в скрутку (шаг 70 мм, два шага на плитку 140 мм) и одна четырёхточечная колючка с обмоткой.
Карты: baseColor (RGBA, A — маска; в игре alpha scissor 0,5), occlusionRoughnessMetallic (R — AO, G — шероховатость,
B — металл), normal (OpenGL, Y вверх) — из карты высот рисунка. Плитка повторяется по U, по V — на всю ширину ленты.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 4                                   # сглаживание: рисуем крупнее и уменьшаем


def _canvas(w: int, h: int) -> tuple:
    a = Image.new("L", (w * SS, h * SS), 0)
    z = Image.new("L", (w * SS, h * SS), 0)
    return a, z, ImageDraw.Draw(a), ImageDraw.Draw(z)


def _normal(height: np.ndarray, strength: float) -> np.ndarray:
    gy, gx = np.gradient(height)
    n = np.dstack([-gx * strength, gy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def _finish(alpha: Image.Image, height: Image.Image, w: int, h: int, base_rgb, rough: float, metal: float,
            name: str, out: Path, dirt_seed: int) -> None:
    a = np.asarray(alpha.resize((w, h), Image.LANCZOS), dtype=np.float32) / 255
    z = np.asarray(height.filter(ImageFilter.GaussianBlur(SS * 0.8)).resize((w, h), Image.LANCZOS), dtype=np.float32) / 255
    rng = np.random.default_rng(dirt_seed)
    # пятна налёта и ржавчины по длине (плитка повторяется — мелкие, без крупного рисунка)
    noise = np.asarray(Image.fromarray((rng.random((h // 16, w // 16)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                       dtype=np.float32) / 255
    rust = np.clip((noise - 0.78) * 2.5, 0, 1) * 0.6     # редкие рыжие точки, не «леопард»
    base = np.asarray(base_rgb, dtype=np.float32)
    col = base[None, None, :] * (0.85 + 0.25 * z[..., None])
    col = col * (1 - rust[..., None] * 0.8) + np.array([0.36, 0.18, 0.08])[None, None, :] * rust[..., None] * 0.8
    rgba = np.dstack([np.clip(col, 0, 1) * 255, a * 255]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(out / f"{name}_baseColor.png")
    ao = 0.75 + 0.25 * z
    orm = np.dstack([ao, np.clip(rough + rust * 0.35, 0, 1), np.clip(metal - rust * 0.6, 0, 1)])
    Image.fromarray((orm * 255).astype(np.uint8), "RGB").save(out / f"{name}_occlusionRoughnessMetallic.png")
    Image.fromarray(_normal(z, 6.0), "RGB").save(out / f"{name}_normal.png")


def razor(out: Path) -> None:
    w, h = 512, 332                       # 74 мм × 48 мм — пикселей поровну на мм
    mm = w / 74.0
    a, z, da, dz = _canvas(w, h)
    S = SS * mm
    cy = 24.0                             # середина полосы, мм
    # лента 22 мм
    for d, val in ((da, 255), (dz, 150)):
        d.rectangle([0, (cy - 11) * S, w * SS, (cy + 11) * S], fill=val)
    # обжатый сердечник по оси ленты и кромки обжима
    dz.rectangle([0, (cy - 1.6) * S, w * SS, (cy + 1.6) * S], fill=255)
    for e in (-4.5, 4.5):
        dz.rectangle([0, (cy + e - 0.4) * S, w * SS, (cy + e + 0.4) * S], fill=200)
    # лезвия: у каждой пары (шаг 37 мм) на каждой кромке — вперёд-наружу и назад-наружу, длина ~12 мм
    for x0 in (8.0, 45.0):
        for side in (-1, 1):
            edge = cy + side * 11
            for dirn in (-1, 1):            # узкое лезвие: основание 6 мм на кромке, остриё на 11 мм наружу и 9 вдоль
                pts = [(x0 + 1.0 * dirn, edge - side * 1.0), (x0 + 7.0 * dirn, edge - side * 0.3), (x0 + 10.0 * dirn, edge + side * 11.5)]
                poly = [(px * S, py * S) for px, py in pts]
                da.polygon(poly, fill=255)
                dz.polygon(poly, fill=120)
            # просечка между лезвиями
            dz.ellipse([(x0 - 1.2) * S, (edge - side * 4 - 1.2) * S, (x0 + 1.2) * S, (edge - side * 4 + 1.2) * S], fill=60)
    _finish(a, z, w, h, (0.70, 0.72, 0.72), 0.30, 0.95, "Razor", out, 11)


def barbed(out: Path) -> None:
    w, h = 512, 146                       # 140 мм × 40 мм
    mm = w / 140.0
    a, z, da, dz = _canvas(w, h)
    S = SS * mm
    cy = 20.0
    r = 1.0                               # проволока Ø 2 мм
    for ph in (0.0, math.pi):
        pts = []
        for k in range(281):
            x = k * 0.5
            y = cy + 1.3 * math.sin(x / 70.0 * 2 * math.pi + ph)
            pts.append((x * S, y * S))
        da.line(pts, fill=255, width=int(2 * r * S) + 1)
        for i in range(len(pts) - 1):
            front = math.cos(pts[i][0] / S / 70.0 * 2 * math.pi + ph) > 0
            dz.line([pts[i], pts[i + 1]], fill=230 if front else 150, width=int(2 * r * S) + 1)
    # колючка: обмотка 8 мм и четыре острия ~14 мм, косо срезанные
    xb = 70.0
    for d, val in ((da, 255), (dz, 255)):
        d.rectangle([(xb - 4) * S, (cy - 2.4) * S, (xb + 4) * S, (cy + 2.4) * S], fill=val)
    for ang in (-62, -118, 58, 122):
        rad = math.radians(ang)
        x1, y1 = xb + 14 * math.cos(rad), cy + 14 * math.sin(rad)
        for d, val in ((da, 255), (dz, 200)):
            d.line([(xb * S, cy * S), (x1 * S, y1 * S)], fill=val, width=int(1.8 * S))
    _finish(a, z, w, h, (0.50, 0.50, 0.48), 0.45, 0.9, "Barbed", out, 12)


def _tile_noise(h: int, w: int, rng: np.random.Generator, octaves: int = 24, fmax: int = 9) -> np.ndarray:
    """Бесшовный шум: сумма синусоид с целыми частотами по обеим осям (плитка повторяется без шва)."""
    yy, xx = np.mgrid[0:h, 0:w]
    n = np.zeros((h, w))
    for _ in range(octaves):
        kx, ky = rng.integers(1, fmax + 1), rng.integers(0, fmax + 1)
        n += np.sin(2 * np.pi * (kx * xx / w + ky * yy / h) + rng.uniform(0, 2 * np.pi)) / (kx + ky)
    return (n - n.min()) / (n.max() - n.min())


def rebar(out: Path) -> None:
    """Пруток периодического профиля Ø 8–12 мм (петли плит, арматура пролома): ржавый. Плитка по U — 80 мм вдоль
    прутка, по V — окружность. Два продольных ребра, косые поперечные «серпом» через 8 мм, ржавчина пятнами с тёмной
    окалиной. Без прозрачности."""
    w, h = 512, 128
    rng = np.random.default_rng(13)
    yy, xx = np.mgrid[0:h, 0:w]
    v = yy / h
    u = xx / w * 80.0
    z = 0.45 + 0.3 * np.exp(-((v - 0.25) / 0.035) ** 2) + 0.3 * np.exp(-((v - 0.75) / 0.035) ** 2)
    phase = (u + 3.0 * np.sin(v * 4 * np.pi)) % 8.0
    z += 0.35 * np.exp(-((phase - 4.0) / 0.9) ** 2) * (np.abs(np.sin(v * 2 * np.pi)) > 0.12)
    big = _tile_noise(h, w, rng, 24, 6)
    fine = _tile_noise(h, w, rng, 40, 24)
    rust = np.array([0.36, 0.18, 0.09])
    oxide = np.array([0.13, 0.10, 0.08])
    t = np.clip((big - 0.55) * 3.0, 0, 1)[..., None]
    col = rust[None, None, :] * (0.8 + 0.4 * fine[..., None]) * (1 - t) + oxide[None, None, :] * t
    col *= (0.85 + 0.25 * z)[..., None]
    rgba = np.dstack([np.clip(col, 0, 1) * 255, np.full((h, w), 255.0)]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(out / "Rebar_baseColor.png")
    orm = np.dstack([0.7 + 0.3 * z, np.clip(0.82 - 0.15 * t[..., 0] + 0.08 * fine, 0, 1), 0.25 + 0.4 * t[..., 0]])
    Image.fromarray((np.clip(orm, 0, 1) * 255).astype(np.uint8), "RGB").save(out / "Rebar_occlusionRoughnessMetallic.png")
    Image.fromarray(_normal(z + 0.15 * fine, 5.0), "RGB").save(out / "Rebar_normal.png")


def main() -> None:
    """<папка> [набор …] — только названные наборы (Razor, Barbed, Rebar); без списка — все три."""
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    want = set(sys.argv[2:]) or {"Razor", "Barbed", "Rebar"}
    for name, draw in (("Razor", razor), ("Barbed", barbed), ("Rebar", rebar)):
        if name in want:
            draw(out)
    print("карты проволоки и прутка:", out, sorted(want))


if __name__ == "__main__":
    main()
