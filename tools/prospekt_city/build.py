"""«Проспект», ограждения и город: собрать форму одного ассета в .blend (фоновый Blender).

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/prospekt_city/build.py -- <ключ> <выход.blend> [вариант,вариант …]

Ключ — модуль генератора (po2_fence, garages, containers, poles, catenary, bus_stop, ktp); варианты — его VARIANTS.
Каждый вариант — своя коллекция с корнем «ID | вариант», варианты стоят рядом вдоль X.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clib as C  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
key, out = argv[0], argv[1]
mod = importlib.import_module(key)
keys = argv[2].split(",") if len(argv) > 2 and argv[2] else list(mod.VARIANTS)
C.reset()
made = mod.build(keys)
C.save(out)
print("собрано:", out, made)
