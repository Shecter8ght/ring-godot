"""Где солнце на HDR-панорамах неба (assets/sky/*.hdr): доля ширины (sun_u) и высота над горизонтом.

python tools/sky_info.py → assets/sky/sky_info.json
RaidAtmosphere берёт отсюда sun_u, чтобы повернуть панораму солнцем туда, откуда светит игровое солнце.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKY = ROOT / "assets/sky"


def read_hdr(path: Path) -> np.ndarray:
    raw = path.read_bytes()
    i = raw.index(b"\n\n") + 2
    le = raw.index(b"\n", i)
    d = raw[i:le].split()
    h, w = int(d[1]), int(d[3])
    p = le + 1
    img = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        p += 4
        for c in range(4):
            x = 0
            while x < w:
                n = raw[p]
                p += 1
                if n > 128:
                    n -= 128
                    img[y, x:x + n, c] = raw[p]
                    p += 1
                else:
                    img[y, x:x + n, c] = np.frombuffer(raw[p:p + n], np.uint8)
                    p += n
                x += n
    e = img[..., 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0)
    return img[..., :3] * f[..., None]


def main() -> None:
    info = {}
    for hdr in sorted(SKY.glob("*.hdr")):
        rgb = read_hdr(hdr)
        h, w = rgb.shape[:2]
        lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
        up = lum[: h // 2].astype(np.float32)
        small = np.asarray(Image.fromarray(up, "F").resize((512, 128), Image.BILINEAR))
        y, x = np.unravel_index(np.argmax(small), small.shape)
        elev = 90.0 - (y + 0.5) / 128 * 90.0
        info[hdr.stem] = dict(sun_u=round((x + 0.5) / 512, 4), sun_elev=round(float(elev), 1),
                              sky_mean=round(float(up.mean()), 3), peak=round(float(small.max()), 2))
        print(hdr.stem, info[hdr.stem])
    (SKY / "sky_info.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
