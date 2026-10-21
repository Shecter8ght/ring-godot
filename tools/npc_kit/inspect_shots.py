"""Крупные проверочные снимки открытого .blend: -- <файл> <вид:x:y:z:tx:ty:tz[:hide=Obj,Obj]> ... → папка out=..."""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402


def main() -> None:
    args = kc.args_after_dashes()
    out = Path(next(a[4:] for a in args if a.startswith("out=")))
    for spec in args:
        if spec.startswith("out=") or ":" not in spec:
            continue
        parts = spec.split(":")
        name = parts[0]
        x, y, z, tx, ty, tz = (float(v) for v in parts[1:7])
        hidden = []
        for extra in parts[7:]:
            if extra.startswith("hide="):
                for oname in extra[5:].split(","):
                    o = bpy.data.objects.get(oname)
                    if o:
                        o.hide_render = True
                        hidden.append(o)
        cam = kc.camera("Cam_Inspect", (x, y, z), (tx, ty, tz), 60)
        kc.render(cam, out / f"{name}.png", (800, 800), 32)
        for o in hidden:
            o.hide_render = False


if __name__ == "__main__":
    main()
