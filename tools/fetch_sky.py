"""Ночное небо: HDRI с Poly Haven (CC0) и карта Луны NASA (общественное достояние) в
_asset_src/sky/<id>/ (+ license.txt), затем — в assets/sky/<id>.<ext> и раздел «Небо» в
assets/CREDITS.md.

Использование: python tools/fetch_sky.py
Игра обязана работать без assets/sky: шейдер неба (src/world/night_sky.gdshader) без HDRI рисует
процедурные звёзды, без карты Луны — ровный серый диск.
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src" / "sky"
OUT = ROOT / "assets" / "sky"
CREDITS = ROOT / "assets" / "CREDITS.md"
UA = {"User-Agent": "RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)"}

SKY = {
    "qwantani_night_puresky": {
        "title": "Qwantani Night (Pure Sky)", "author": "Greg Zaal, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/qwantani_night_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/qwantani_night_puresky_4k.hdr",
        "file": "qwantani_night_puresky.hdr", "role": "ночное небо со звёздами (фон)",
    },
    "nqweba_dawn": {
        "title": "Nqweba Dawn", "author": "Dario Barresi", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/nqweba_dawn",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/nqweba_dawn_4k.hdr",
        "file": "nqweba_dawn.hdr", "role": "небо рассвета и заката зоны 1 (HdriSky)",
    },
    "kloppenheim_06_puresky": {
        "title": "Kloppenheim 06 (Pure Sky)", "author": "Greg Zaal, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/kloppenheim_06_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/kloppenheim_06_puresky_4k.hdr",
        "file": "kloppenheim_06_puresky.hdr", "role": "закат: кандидат — мягкий, облачный",
    },
    "belfast_sunset_puresky": {
        "title": "Belfast Sunset (Pure Sky)", "author": "Greg Zaal, Dimitrios Savva, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/belfast_sunset_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/belfast_sunset_puresky_4k.hdr",
        "file": "belfast_sunset_puresky.hdr", "role": "закат: кандидат — солнце у горизонта",
    },
    "qwantani_dusk_2_puresky": {
        "title": "Qwantani Dusk 2 (Pure Sky)", "author": "Greg Zaal, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/qwantani_dusk_2_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/qwantani_dusk_2_puresky_4k.hdr",
        "file": "qwantani_dusk_2_puresky.hdr", "role": "закат: кандидат — тёплый, чистый",
    },
    "kloppenheim_01_puresky": {
        "title": "Kloppenheim 01 (Pure Sky)", "author": "Greg Zaal, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/kloppenheim_01_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/kloppenheim_01_puresky_4k.hdr",
        "file": "kloppenheim_01_puresky.hdr", "role": "закат в дождь и туман",
    },
    "kloppenheim_03_puresky": {
        "title": "Kloppenheim 03 (Pure Sky)", "author": "Greg Zaal, Jarod Guest", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/kloppenheim_03_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/kloppenheim_03_puresky_4k.hdr",
        "file": "kloppenheim_03_puresky.hdr", "role": "день ясный, переменная облачность",
    },
    "kloofendal_overcast_puresky": {
        "title": "Kloofendal Overcast (Pure Sky)", "author": "Greg Zaal", "license": "CC0 1.0",
        "source": "https://polyhaven.com/a/kloofendal_overcast_puresky",
        "url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/kloofendal_overcast_puresky_4k.hdr",
        "file": "kloofendal_overcast_puresky.hdr", "role": "день в дождь и туман",
    },
    "moon_lroc_color": {
        "title": "CGI Moon Kit — Lunar Surface in Color (LRO LROC)", "author": "NASA's Scientific Visualization Studio",
        "license": "Public Domain (NASA)", "source": "https://svs.gsfc.nasa.gov/4720",
        "url": "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_1k.jpg",
        "file": "moon_lroc_color.jpg", "role": "диск Луны в шейдере неба",
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["## Небо (assets/sky)", ""]
    for sid, s in SKY.items():
        src = SRC / sid
        src.mkdir(parents=True, exist_ok=True)
        raw = src / s["file"]
        if not raw.exists():
            with urllib.request.urlopen(urllib.request.Request(s["url"], headers=UA)) as r, open(raw, "wb") as f:
                f.write(r.read())
            print(f"{sid}: скачано {raw.stat().st_size // 1024} КБ")
        (src / "license.txt").write_text(
            f"title: {s['title']}\nauthor: {s['author']}\nlicense: {s['license']}\nsource: {s['source']}\nrole: {s['role']}\n",
            encoding="utf-8")
        shutil.copy2(raw, OUT / s["file"])
        lines.append(f"- `assets/sky/{s['file']}` — {s['title']}, {s['author']}, {s['license']}, {s['source']} — {s['role']}")
    lines.append("")
    old = CREDITS.read_text(encoding="utf-8") if CREDITS.exists() else ""
    if "\n## Небо" in old:
        start = old.index("\n## Небо")
        rest = old[start + 1:]
        nxt = rest.find("\n## ", 1)
        old = old[:start] + ("\n" + rest[nxt + 1:] if nxt >= 0 else "\n")
    CREDITS.write_text(old.rstrip("\n") + "\n\n" + "\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
