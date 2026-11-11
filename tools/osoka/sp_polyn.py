# «Осока», тепловизор ПН-36Т «ПОЛЫНЬ», текстуры этап 1 — заводская отделка в Substance Painter прямо на игровой сетке
# тем же кодом, что у «Осоки» (tools/osoka/sp_osoka.py: проект, запекание, нормали из Blender, стек по finish-spec.json;
# здесь — только пути, набор «Polyn» и маркировка белой краской). Через мост (tools/asset_kit/finish/sp_run.py, своя папка
# заданий FINISH_SP_JOBS=_asset_src/osoka_polyn/tex/sp_jobs):
#   python -X utf8 tools/asset_kit/finish/sp_run.py start
#   python -X utf8 tools/asset_kit/finish/sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/osoka'); import sp_polyn; print(sp_polyn.create())"
#   … sp_polyn.bake() → _bake_done.txt; … sp_polyn.use_blender_normals(); … sp_polyn.stack() → _stack_done.txt;
#   … sp_polyn.export(<папка>) → _export_done.txt
# Вход — tools/osoka/sight_tex.py (Polyn_low.fbx / Polyn_high.fbx, meshes.json, normals/) и tools/osoka/sight_masks.py
# (маркировка). Отделки — карточки каталога по finish-spec.json папки «Тепловизор».
import os

import sp_finish
import sp_osoka as S

ROOT = "E:/Games/RING-godot"
S.TEX = ROOT + "/_asset_src/osoka_polyn/tex"
S.SPEC = "E:/Models Blender/WEAPONS/Верба — модель/Тепловизор/finish-spec.json"
S.PROJECT = S.TEX + "/sp/Polyn_finish_v1.spp"
S.LOW = S.TEX + "/Polyn_low.fbx"
S.HIGH = S.TEX + "/Polyn_high.fbx"
S.RES = {"Polyn": 4096}
# луч запекания — доля габарита сцены (прицел ~0.27 м): 0.008 ≈ 2.1 мм — отклонение игровой сетки до 0.85 мм
S.RAY_REL = 0.008
# маркировка — белая краска, полумат (как «1ПН97» на снимке)
S.STENCIL = {"color": (0.84, 0.84, 0.81), "rough": 0.55, "metal": 0.0}
SET = "Polyn"

create = S.create
use_blender_normals = S.use_blender_normals


def bake(only=None, match=1, ray=None, sub=1):
    return S.bake(only, match, S.RAY_REL if ray is None else ray, sub)


def stack(only=None):
    """Стек этапа 1 набора «Polyn» и маркировка белой краской поверх (маска Polyn_stencil.png); итог — _stack_done.txt."""
    import substance_painter.project as P
    import substance_painter.textureset as TS
    import sp_lib
    sp_finish.WORLD_GRAIN = True
    sp_finish.FINE_EDGES = True
    px = S._json("px_mm.json")
    scene = S._json("scene.json")["size_mm"]
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        parts = S.parts_of(name)
        if not parts:
            continue
        log.append(sp_finish.build_set(name, parts, px.get(name, 9.0), scene))
        if os.path.exists(f"{S.TEX}/masks/{name}_stencil.png"):
            S.stencil(name)
            log.append(name + ": маркировка")

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_stack_done.txt")


export = S.export            # карты glTF (baseColor, ORM, normal) в папку; итог — _export_done.txt
open_project = S.open_project
