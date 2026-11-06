# ИЗЛОМ-45 (wpn_smg_03): магазины v2 (Glock 21 на 13 и на 30 с удлинителем, геометрия v07) — свой проект Painter, отдельно
# от корпуса: атласы Mag13 / Mag30 переделаны (новая игровая сетка tools/smg03/game_lp_mags.py), остальные наборы и их
# принятый износ v3 не трогаются. Те же функции, что у проекта корпуса (sp_smg03), с папкой _asset_src/smg03/tex_mags
# (вход — game_tex.py с SMG03_TEX_LP / SMG03_TEX_SRC / SMG03_TEX_OUT). Отделка этапа 1 — та же принятая карточка
# PL-BLK-SMO (finish-spec.json, слот magazine), патроны — BR-CAS / CU-PRM. Износ — sp_smg03_mags_wear.py.
#
#   FINISH_SP_JOBS=_asset_src/smg03/tex_mags/sp_jobs python -X utf8 tools/asset_kit/finish/sp_run.py start
#   … sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/smg03'); import sp_smg03_mags as M; print(M.create())"
#   … print(M.bake())  → _bake_done.txt;  print(M.normals());  print(M.stack()) → _stack_done.txt;  print(M.export(<папка>))
import json

import sp_smg03 as S

ROOT = S.ROOT
TEX = ROOT + "/_asset_src/smg03/tex_mags"
PROJECT = TEX + "/sp/SMG03_mags_v2.spp"
PARTS_JSON = ROOT + "/_asset_src/smg03/game/lp/parts_mags_v2.json"


def _px_mm():
    with open(PARTS_JSON, encoding="utf-8") as f:
        a = json.load(f)["atlases"]
    return {k: v["report"]["px_mm"] for k, v in a.items()}


def use():
    """Перевести функции sp_smg03 на папку магазинов (модуль общий в процессе Painter — вызывать перед каждым шагом)."""
    S.TEX = TEX
    S.PROJECT = PROJECT
    S.LOW = TEX + "/SMG03_low.fbx"
    S.HIGH = TEX + "/SMG03_high.fbx"
    S._px_mm = _px_mm
    S.RED_SETS = ()


def create():
    use()
    return S.create()


def bake(only=None):
    use()
    return S.bake(only)


def normals(only=None):
    """Нормали — из Blender (tex_mags/normals/<набор>_normal.png): рифление и окна с high-poly v07, V-канавки 45°."""
    use()
    return S.use_blender_normals(only)


def stack(only=None):
    use()
    return S.stack(only)


def export(out_dir, only=None):
    use()
    return S.export(out_dir, only)


def open_project():
    use()
    return S.open_project()
