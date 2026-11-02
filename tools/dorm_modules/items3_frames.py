"""Вещи общежития, партия 3: оси каждой книги и тетради в наборах — для печати обложек и корешков (items3_prints.py).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Items_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/items3_frames.py -- <папка geo>

На кусок переплёта (обложки) — центр, оси длины, ширины и толщины (единичные, в осях набора) и размеры по ним. Ширина
смотрит от корешка к обрезу (у корешка дуга — вершины гуще), толщина — к лицевой крышке: у лежащей книги — вверх,
у стоящей в ряду — к +X (лицом к соседке справа). Обложка тетради — три полосы: собираются в тетрадь по сгибу.
Выход: <папка>/<набор>_frames.json.
"""
import json
import os
import sys

import bmesh
import bpy
import numpy as np

SETS = ("it_book", "it_book_stack", "it_book_row", "it_notebook", "it_notebook_stack", "it_notebook48")
COVERS = ("Переплёт", "Обложка_тетради")


def components(bm):
    seen, out = set(), []
    for start in bm.verts:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            v = stack.pop()
            comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        out.append(comp)
    return out


def frame(pts: np.ndarray) -> dict:
    c = (pts.min(0) + pts.max(0)) / 2
    w, v = np.linalg.eigh(np.cov((pts - pts.mean(0)).T))
    axes = [v[:, i] for i in np.argsort(w)[::-1]]      # длина, ширина, толщина
    ext = []
    for a in axes:
        d = (pts - c) @ a
        ext.append(float(d.max() - d.min()))
    # центр — по габариту в своих осях
    c = c + sum(a * float(((pts - c) @ a).max() + ((pts - c) @ a).min()) / 2 for a in axes)
    length, width, thick = axes
    # ширина — от корешка к обрезу: средняя вершина смещена к корешку (дуга гуще вершинами) — он у −width
    if float(((pts - c) @ width).mean()) > 0:
        width = -width
    up = np.array([0.0, 0.0, 1.0])
    ref = up if abs(float(thick @ up)) > 0.7 else np.array([1.0, 0.0, 0.0])
    if float(thick @ ref) < 0:
        thick = -thick
    # голова книги: правая тройка (ширина, длина, толщина) — смотрим на лицевую крышку, корешок слева, голова сверху
    length = np.cross(thick, width)
    return {"center": c.tolist(), "length": length.tolist(), "width": width.tolist(), "thick": thick.tolist(),
            "size": ext}


def notebooks(parts: list) -> list:
    """Обложка тетради — три полосы (верх, низ, сгиб): тетрадь — две крышки у своего сгиба; ширина — от сгиба,
    толщина — между крышками, лицевая — верхняя."""
    folds = [f for f in parts if f["size"][1] < 0.01]
    plates = [f for f in parts if f["size"][1] >= 0.01]
    out = []
    for s in folds:
        sc = np.array(s["center"])
        # свои крышки — те, у которых длинный край лежит у сгиба (в стопке тетради сдвинуты и повёрнуты, середины
        # чужих крышек бывают так же близко)

        def edge_gap(f):
            fc, fw = np.array(f["center"]), np.array(f["width"])
            return min(float(np.linalg.norm(fc + k * fw * f["size"][1] / 2 - sc)) for k in (-1, 1))
        near = sorted(plates, key=edge_gap)[:2]
        if len(near) < 2:
            continue
        top, bot = sorted(near, key=lambda f: f["center"][2], reverse=True)
        c = (np.array(top["center"]) + np.array(bot["center"])) / 2
        width = np.array(top["width"])
        if float((c - sc) @ width) < 0:
            width = -width
        thick = np.array([0.0, 0.0, 1.0])
        length = np.cross(thick, width)
        gap = float(top["center"][2] - bot["center"][2])
        out.append({"center": c.tolist(), "length": length.tolist(), "width": width.tolist(), "thick": thick.tolist(),
                    "size": [top["size"][0], top["size"][1], gap + 0.001]})
    return out


def main() -> None:
    out = sys.argv[sys.argv.index("--") + 1]
    for game in SETS:
        coll = bpy.data.collections.get(game)
        if coll is None:
            continue
        frames = []
        for ob in coll.objects:
            if ob.name.split(".")[0].split("__")[0] not in COVERS:
                continue
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            for comp in components(bm):
                pts = np.array([tuple(v.co) for v in comp])
                frames.append(frame(pts))
            bm.free()
        if game.startswith("it_notebook"):
            frames = notebooks(frames)
        # порядок: лежащие — снизу вверх (стопка), стоящие — слева направо (ряд)
        frames.sort(key=lambda f: f["center"][2] if abs(f["thick"][2]) > 0.7 else f["center"][0])
        with open(os.path.join(out, f"{game}_frames.json"), "w", encoding="utf-8") as fh:
            json.dump(frames, fh, ensure_ascii=False, indent=1)
        print("FRAMES", game, len(frames), flush=True)


if __name__ == "__main__":
    main()
