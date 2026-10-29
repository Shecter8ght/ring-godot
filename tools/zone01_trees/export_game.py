"""Клёны и тополя зоны 1 — игровая версия (bpy) тем же конвейером, что растения «Проспекта» (tools/prospekt_plants/game.py):

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/zone01_trees/export_game.py -- [maple negundo poplar] [atlas] [meshes] [preview] [compare]

  atlas  — модули веточек из PBR-файла вида (pbr.py) рендерятся в атлас 2048²: цвет с альфой и нормаль в осях карточки;
           у веточек с плоской «мозаикой» листьев клёна — вид сверху, у висячих кистей и голых прутьев — ещё и сбоку.
  meshes — экземпляры тем же генератором (те же ветви и точки модулей): LOD0 (ветви от 1 см), LOD1 (от 3 см, половина
           карточек крупнее), дальний — две скрещённые плоскости с видом дерева → assets/zone01/trees/<ключ>_{lod0,lod1,far}.glb.
           Цвет вершин: r — затенение в кроне, g — гибкость, b — фаза ветра (шейдеры spruce_foliage / spruce_bark).
Отчёт — _asset_src/zone01_trees/game.json (для материалов Godot: tools/zone01_trees/godot_assets.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prospekt_plants"))
import game as G  # noqa: E402  (игровой конвейер растений «Проспекта»)
import plib  # noqa: E402
import species_z1 as S  # noqa: E402
import forms as F  # noqa: E402
import pbr as P  # noqa: E402

ROOT = HERE.parents[1]
# имена материалов: Plant<вид>… (дальний вид конвейер «Проспекта» называет Plant<вид>Far); тополь зоны 1 — свой, не как на «Проспекте»
MAT = {"maple": "Maple", "negundo": "Negundo", "poplar": "Z1Poplar"}

# конвейер «Проспекта» — на виды, пути и файлы зоны 1
G.S = S
G.BF = SimpleNamespace(ORDER=P.ORDER, LIB=F.LIB, camera=F.PBF.camera, render=F.PBF.render)
G.BP = SimpleNamespace(VERSION=P.VERSION, BARK_TEX=P.BARK_TEX, image=P.BPP.image)
G.OUT = ROOT / "assets/zone01/trees"
G.TEX = ROOT / "_asset_src/zone01_trees/textures"
G.WORK = ROOT / "_asset_src/zone01_trees"
# крестом (сверху и сбоку): у клёна — веточка с крылатками и голая; у ясенелистного — с кистями; у тополя — все
G.CROSS.update({"maple": {"03", "05"}, "negundo": {"03", "04"}, "poplar": {"01", "02", "03", "04", "05"}})
G.LOD0_KIND.update({k: dict(min_r=0.0105, side_div=2.0, seg=0.55) for k in ("negundo", "poplar")})
# клён остролистный ветвится густо (у дворового — 167 тыс. треуг. ветвей в форме): в LOD0 ветви от 1,4 см и реже
G.LOD0_KIND["maple"] = dict(min_r=0.014, side_div=2.4, seg=0.7)
G.CARD_GROW.update({"maple": 1.15, "negundo": 1.1, "poplar": 1.08})
G.FLEX.update({"maple": 0.8, "negundo": 0.95, "poplar": 0.8})
G.MAT.update(MAT)


def game_materials(kind: str, key: str) -> dict:
    """Имена слотов = имена материалов Godot (assets/zone01/trees/materials/<имя>.tres); у тополя кора своя на экземпляр
    (высота старой бороздчатой коры)."""
    m = MAT[kind]
    names = {"bark": f"Plant{m}Bark", "branch": f"Plant{m}Branch", "dead": f"Plant{m}Dead", "leaves": f"Plant{m}Leaves",
             "far": f"Plant{m}Far"}
    if kind == "poplar":
        names["bark"] = f"Plant{m}Bark_{key[-1]}"
    return {k: (bpy.data.materials.get(v) or bpy.data.materials.new(v)) for k, v in names.items()}


def wood_object(kind: str, pl, lod: dict, col, mats: dict) -> tuple:
    plib.LOD = dict(lod, col=col)
    m, tw, env = S.BUILDERS[kind](pl)
    plib.LOD = None
    slot = {"bark": mats["bark"], "branch": mats["branch"], "twig": mats["branch"], "seed": mats["branch"], "dead": mats["dead"]}
    ob = m.build(pl.key + "_wood", slot) if m.parts else None
    return ob, tw, env


G.game_materials = game_materials
G.wood_object = wood_object


def main() -> None:
    S.LEAF_MODE = "alpha"
    G.main()


if __name__ == "__main__":
    main()
