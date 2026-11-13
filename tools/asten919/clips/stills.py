"""АСТЕН-919, клипы рук: кадры для собственной проверки хвата и клипов (Workbench, без видеокарты почти не грузит).

blender -b <файл.blend> --python tools/asten919/clips/stills.py -- <папка> [кадр,кадр…] [вид,вид…] [приставка]
Виды: eye (камера игры), right, left, top, bottom, front, back, r34 (справа-сзади-сверху), l34 — ортокамеры вокруг рукояти.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT = Path(A[0])
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools  # noqa: E402


def frame_of(x):
    """«51» — кадр открытого действия; «Reload_Full:25» — кадр 25 клипа, «poses:41» — кадр позы."""
    if ":" in x:
        clip, f = x.split(":")
        return (clip_tools.POSES if clip == "poses" else clip_tools.PREFIX + clip, int(f))
    return (None, int(x))


FRAMES = [frame_of(x) for x in A[1].split(",")] if len(A) > 1 and A[1] else [(None, bpy.context.scene.frame_current)]
VIEWS = A[2].split(",") if len(A) > 2 and A[2] else ["eye", "right", "left", "bottom", "back", "top"]
TAG = A[3] if len(A) > 3 else ""
S = bpy.context.scene
root = bpy.data.objects["ASTEN919"]
S.render.engine = "BLENDER_WORKBENCH"
sh = S.display.shading
sh.light = "STUDIO"
sh.color_type = "TEXTURE"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.show_shadows = False
sh.show_object_outline = True
S.render.resolution_x, S.render.resolution_y = 1100, 800
S.render.film_transparent = False
S.world = S.world or bpy.data.worlds.new("w")
S.display.shading.background_type = "VIEWPORT"
S.display.shading.background_color = (0.32, 0.34, 0.36)
S.render.image_settings.file_format = "PNG"
eye = bpy.data.objects["FPS • Camera"]
# направления «откуда смотрим» в осях исходника пистолета (+X дуло, +Y влево, +Z вверх) и «верх» кадра
DIRS = {"right": ((0, -1, 0), (0, 0, 1)), "left": ((0, 1, 0), (0, 0, 1)), "top": ((0, 0, 1), (1, 0, 0)),
        "bottom": ((0, 0, -1), (1, 0, 0)), "front": ((1, 0, 0), (0, 0, 1)), "back": ((-1, 0, 0), (0, 0, 1)),
        "r34": ((-0.55, -0.7, 0.45), (0, 0, 1)), "l34": ((-0.55, 0.7, 0.45), (0, 0, 1)),
        "rlow": ((0.3, -0.75, -0.6), (0, 0, 1)), "llow": ((0.3, 0.75, -0.6), (0, 0, 1))}
cam_data = bpy.data.cameras.new("check")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 0.30
cam_data.clip_start, cam_data.clip_end = 0.01, 5.0
cam = bpy.data.objects.new("check", cam_data)
S.collection.objects.link(cam)
OUT.mkdir(parents=True, exist_ok=True)
for act_name, f in FRAMES:
    if act_name:
        assert clip_tools.open_action(bpy.context, act_name), act_name
    S.frame_set(f)
    bpy.context.view_layer.update()
    TW = root.matrix_world.copy()
    c = TW @ Vector((-0.035, 0.0, -0.05))
    for v in VIEWS:
        if v == "eye":
            S.camera = eye
        else:
            d, up = DIRS[v]
            d = (TW.to_3x3() @ Vector(d)).normalized()
            up = (TW.to_3x3() @ Vector(up)).normalized()
            z = d
            x = up.cross(z).normalized()
            y = z.cross(x)
            m = Matrix((x, y, z)).transposed().to_4x4()
            m.translation = c + d * 1.0
            cam.matrix_world = m
            S.camera = cam
        clip = (act_name or "").replace(clip_tools.PREFIX, "")
        S.render.filepath = str(OUT / f"{TAG}{v}_{clip + '_' if clip else ''}{f:03d}.png")
        bpy.ops.render.render(write_still=True)
print("STILLS", OUT)
