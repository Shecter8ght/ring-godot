"""Купе Ильи, радиатор: развёртка под текстуры на рабочей копии принятой формы.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/radiator_uv.py -- <принятый.blend> models/items/Radiator_Ilya_v01_uv.blend

Сетку не трогает (форма v01 принята 2026-10-18). Сердцевина (трубки и ламели) — свой материал rad_core
и проекция спереди: лист ламели идёт вглубь, поэтому к v добавлен малый сдвиг по глубине (иначе грань
вырождается в линию), а глубина — атрибут CoreDepth (0 спереди → 1 сзади: мошки и пыль у передней кромки).
Бирка и надпись — проекция на плоскость бирки; остальные детали — общий атлас на материал (Smart UV
Project по всем объектам материала разом), чтобы детали одного материала не наслаивались в текстуре.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import radiator as rad  # noqa: E402

TEX_PX = {          # разрешение текстур материала — для проверки плотности
    "rad_alu": 2048, "rad_core": 4096, "rad_plastic": 4096, "rad_hose": 2048, "rad_clamp": 1024,
    "rad_wire": 512, "rad_tag": 1024, "rad_tag_ring": 512, "rad_ink": 1024,
}


def planar_uv(ob: bpy.types.Object, origin, ax_u, ax_v, size: float, ax_w=None, k_w: float = 0.0) -> None:
    """Прямая проекция: uv = 0.5 + (p − origin)·ax / size (одинаковый масштаб по обеим осям);
    ax_w, k_w — малая добавка глубины к v, чтобы грани вдоль луча проекции не вырождались."""
    me = ob.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    co = np.array([v.co[:] for v in me.vertices])
    idx = np.array([lp.vertex_index for lp in me.loops])
    p = co[idx] - np.asarray(origin, float)
    u = 0.5 + p @ np.asarray(ax_u, float) / size
    v = 0.5 + p @ np.asarray(ax_v, float) / size
    if ax_w is not None:
        v += p @ np.asarray(ax_w, float) * k_w
    uv.data.foreach_set("uv", np.c_[u, v].ravel())


def depth_attr(ob: bpy.types.Object, y0: float, y1: float) -> None:
    """Атрибут CoreDepth на вершинах: 0 у передней кромки сердцевины, 1 у задней."""
    me = ob.data
    a = me.color_attributes.get("CoreDepth") or me.color_attributes.new("CoreDepth", "FLOAT_COLOR", "POINT")
    y = np.array([v.co.y for v in me.vertices])
    d = np.clip((y - y0) / (y1 - y0), 0, 1)
    a.data.foreach_set("color", np.c_[d, d, d, np.ones_like(d)].ravel())


def smart_uv(obs: list[bpy.types.Object]) -> None:
    """Общий атлас для объектов одного материала."""
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def texel_report(groups: dict[str, list]) -> None:
    """Плотность: пикселей на миллиметр по площади UV и площади поверхности."""
    for mat, obs in groups.items():
        a3 = auv = 0.0
        for o in obs:
            me = o.data
            uv = me.uv_layers["UVMap"].data
            for p in me.polygons:
                a3 += p.area
                pts = [uv[i].uv for i in p.loop_indices]
                s = 0.0
                for k in range(1, len(pts) - 1):
                    s += abs((pts[k].x - pts[0].x) * (pts[k + 1].y - pts[0].y)
                             - (pts[k + 1].x - pts[0].x) * (pts[k].y - pts[0].y)) / 2
                auv += s
        px = TEX_PX.get(mat, 1024)
        dens = math.sqrt(auv / max(a3, 1e-12)) * px / 1000.0
        print(f"  {mat}: объектов {len(obs)}, площадь {a3:.4f} м², UV {auv:.3f}, {px} пкс → {dens:.2f} пкс/мм")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, out = Path(argv[0]), Path(argv[1])
    bpy.ops.wm.open_mainfile(filepath=str(src))
    m = bpy.data.materials["rad_alu"].copy()
    m.name = "rad_core"
    y0, y1 = -rad.CORE_D / 2, rad.CORE_D / 2          # оси предмета: Y_C → 0
    for name in ("Radiator_Core_Fins", "Radiator_Core_Tubes"):
        ob = bpy.data.objects[name]
        ob.data.materials[0] = m
        # вид спереди, ширина сердцевины на всю текстуру; глубина 27 мм → ~1 пкс по v
        planar_uv(ob, (0.0, 0.0, (rad.CORE_Z0 + rad.CORE_Z1) / 2 - rad.CAR_POS[2]), (1, 0, 0), (0, 0, 1),
                  2 * rad.CORE_X + 0.006, (0, 1, 0), 0.01)
        depth_attr(ob, y0, y1)
    # бирка и надпись: плоскость бирки, квадратный тексель
    f = rad.tag_frame()
    c = f["center"] - rad.CAR_POS
    for name in ("Tag_Card", "Tag_Text"):
        planar_uv(bpy.data.objects[name], c, f["u"], f["up"], rad.TAG_H + 0.004)
    # надпись — плоская краска на обеих сторонах: каждая грань лицом наружу от картона
    import bmesh
    me = bpy.data.objects["Tag_Text"].data
    bm = bmesh.new()
    bm.from_mesh(me)
    nn = Vector(f["n"].tolist())
    cc = Vector(c.tolist())
    flip = [fc for fc in bm.faces if fc.normal.dot(nn) * (fc.calc_center_median() - cc).dot(nn) < 0]
    bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(me)
    bm.free()
    print("  надпись: развёрнуто граней", len(flip))
    groups: dict[str, list] = defaultdict(list)
    for o in bpy.data.objects:
        if o.type == "MESH":
            groups[o.active_material.name].append(o)
    for mat, obs in groups.items():
        if mat in ("rad_core", "rad_tag", "rad_ink"):
            continue
        smart_uv(obs)
    texel_report(groups)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("сохранено:", out)


main()
