"""Магазины 45 / 60 во вьюмодели ВЕРАС-54 (tools/export_veras54.py подключает этот модуль, его остальное не меняется).

Наборы клипов «<клип>[_<рукоятка>]_<mag45|drum60>» — из «Клипы v13» (tools/veras54_mags/mags_clips.sh, от файлов хватов
владельца); есть файл — набор идёт во вьюмодель. Сами модели магазинов (assets/models/weapons/veras54_mags, свои карты,
патроны Round_NN, подаватель) во вьюмодель не запекаются: игра ставит их на метки MagAsset (кость Magazine — магазин в
оружии и в руке) и SpareMagAsset (кость SpareMag — старый магазин быстрой перезарядки). Оси меток — оси модели магазина:
поворот +90° вокруг Z от пустышки Magazine (модель магазина экспортирована с поворотом −90°, tools/veras54_mags/mags_game_export.py).
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix

MAG_SETS = ("mag45", "drum60")
# роль в игре: (суффикс действий build_clips.py, последний кадр, файл)
ROLES = (("reload_tactical", "Tactical", 79, "Reload_Tactical"), ("reload_full", "Full", 114, "Reload_Full"),
         ("reload_fast", "Fast", 58, "Reload_Fast"), ("reload_fast_full", "Fastfull", 92, "Reload_FastFull"),
         ("mag_check", "Check", 60, "Mag_Check"))


def clips(src: Path, grips: tuple) -> dict:
    """{клип в игре: (суффикс действий, последний кадр, файл)} — наборы магазинов, у которых есть файлы клипов."""
    out = {}
    for m in MAG_SETS:
        for g in ("",) + tuple(grips):
            gs = "_" + g if g else ""
            for role, tag, last, file in ROLES:
                path = src / f"VERAS54_{file}{gs}_{m}_v13.blend"
                if path.exists():
                    out[f"{role}{gs}_{m}"] = (f"{tag}{gs}_{m}", last, path)
    return out


def add_marks(wr, magob) -> list:
    """Метки MagAsset (кость Magazine) и SpareMagAsset (кость SpareMag) — в месте корня штатного магазина."""
    bpy.context.view_layer.update()
    world = magob.matrix_world @ Matrix.Rotation(math.radians(90), 4, "Z")
    made = []
    for name, bone in (("MagAsset", "Magazine"), ("SpareMagAsset", "SpareMag")):
        if bone not in wr.data.bones:
            continue
        e = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(e)
        e.empty_display_size = 0.02
        e.parent = wr
        e.parent_type = "BONE"
        e.parent_bone = bone
        e.matrix_world = world
        made.append(name)
    return made
