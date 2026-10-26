"""«Проспект», ограждения и город: игровая сетка LOD0 и файлы для Substance Painter (фоновый Blender).

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/game.py -- \
        <модуль> <рабочая папка>

Собирает подробную форму (build() модуля — источник запекания) и игровые детали (game() модуля) рядом, в тех же
местах: вариант i стоит на X = i·step (META), игровые варианты сверх VARIANTS (GAME["extra"]) — дальше.
Наборы текстур развёртываются целиком (умная проекция, одна плотность, упаковка), детали триангулированы — та же
сетка уходит в Painter и в glTF. В рабочей папке:
  <name>_low.fbx  — игровая сетка: по набору и материалу детали одна сетка «<набор>__<материал>» (маски слоёв Painter);
  <name>_high.fbx — подробная форма вариантов GAME["bake"] без деталей GAME["skip_high"] (проволока и т. п.);
  <name>_lod0.blend — игровые детали по вариантам (коллекции «LOD0 | <вариант>») для карт и glTF.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clib as C  # noqa: E402
import game_lib as G  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
mod = importlib.import_module(argv[0])
work = Path(argv[1])
work.mkdir(parents=True, exist_ok=True)
meta, game = mod.META, mod.GAME
name = meta["name"]
C.reset()
keys = list(mod.VARIANTS)
mod.build(keys)
high_cols = {c.name: c for c in bpy.context.scene.collection.children}

order = keys + list(game.get("extra", {}))
ctx: dict = {}
lod = {}
for i, k in enumerate(order):
    title = mod.VARIANTS.get(k) or game["extra"][k]
    col = C.collection(f"LOD0 | {title}")
    r = C.root(f"{game['ids'][k]} | {title}", col, (i * meta["step"], 0.0, 0.0))
    r["variant"], r["model_id"] = k, game["ids"][k]
    mod.game(col, r, k, ctx)
    lod[k] = col
bpy.context.view_layer.update()

parts = [o for c in lod.values() for o in c.objects if o.type == "MESH"]
for o in G.unique_by_data(parts):
    G.triangulate(o)
painter = [o for o in G.unique_by_data(parts) if o["tex_set"] not in G.NO_PAINTER]
uv_report = {}
for ts in sorted({o["tex_set"] for o in painter}):
    r = str(game.get("res", {}).get(ts, 11))                 # «11» — квадрат 2048, «11x10» — 2048 × 1024
    size = (2 ** int(r.split("x")[0]), 2 ** int(r.split("x")[1])) if "x" in r else 2 ** int(r)
    st = G.unwrap([o for o in painter if o["tex_set"] == ts], size=size)
    uv_report[ts] = {"size": size, **st}
    print(f"UV {ts}: {size} пикс, заполнение {st['fill'] * 100:.0f} %, плотность {st['px_m']:.0f} пикс/м"
          + ("  UV_FILL_LOW" if st["low"] else ""))
(work / f"{name}_uv.json").write_text(__import__("json").dumps(uv_report, ensure_ascii=False, indent=1), encoding="utf-8")

# FBX для Painter: игровые детали по (набору, материалу) и подробная форма
tmp = C.collection("_fbx")
low = []
for ts in sorted({o["tex_set"] for o in painter}):
    for m in sorted({o["mat"] for o in painter if o["tex_set"] == ts}):
        low.append(G.merged_copy([o for o in painter if o["tex_set"] == ts and o["mat"] == m], f"{ts}__{m}", ts, tmp))
G.export_fbx(low, work / f"{name}_low.fbx")
skip = tuple(game.get("skip_high", ()))
high = []
for k in game["bake"]:
    col = high_cols[mod.VARIANTS[k]]
    high += [o for o in col.objects if o.type == "MESH" and not o.name.split(".")[0].startswith(skip)]
G.export_fbx(high, work / f"{name}_high.fbx")
for o in low:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.collections.remove(tmp)
# игровой .blend — без подробной формы
for c in high_cols.values():
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(c)
bpy.ops.outliner.orphans_purge(do_recursive=True)
C.save(work / f"{name}_lod0.blend")
for k, col in lod.items():
    t = sum(G.tris(o) for o in col.objects if o.type == "MESH")
    print(f"LOD0 {game['ids'][k]}: {t} треугольников, деталей {sum(1 for o in col.objects if o.type == 'MESH')}")
print("наборы:", sorted({o['tex_set'] for o in painter}), "→", work)
