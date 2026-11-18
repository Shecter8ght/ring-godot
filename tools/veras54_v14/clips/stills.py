"""ВЕРАС-54, клипы рук: кадры для собственной проверки хвата и клипов (Workbench — почти не грузит видеокарту).

blender -b <файл.blend> --python tools/veras54_v14/clips/stills.py -- <папка> [кадр,кадр…] [вид,вид…] [приставка] [вариант]
Кадр: «51» — кадр открытого действия; «Reload_Full:25» — кадр 25 клипа; «poses:41» — кадр позы.
Виды: eye (камера игры), right, left, top, bottom, front, back, r34, l34, rlow, llow — ортокамеры вокруг автомата
(«_near» — крупнее, у магазина; «_muzzle» — у дула). Вариант: «grip=varn_v1,mag=45» — показать рукоятку и магазин.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT = Path(A[0])
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import clip_tools  # noqa: E402
except Exception:                                       # файл рига без панели
    clip_tools = None


def frame_of(x):
    if ":" in x:
        clip, f = x.split(":")
        return ("VERAS54_Poses" if clip == "poses" else "VERAS54_" + clip, int(f))
    return (None, int(x))


FRAMES = [frame_of(x) for x in A[1].split(",")] if len(A) > 1 and A[1] else [(None, bpy.context.scene.frame_current)]
VIEWS = A[2].split(",") if len(A) > 2 and A[2] else ["eye", "right", "left", "bottom", "top"]
TAG = A[3] if len(A) > 3 else ""
VAR = dict(kv.split("=") for kv in A[4].split(",")) if len(A) > 4 and A[4] else {}
S = bpy.context.scene
root = bpy.data.objects["VERAS54"]
S.render.engine = "BLENDER_WORKBENCH"
sh = S.display.shading
sh.light = "STUDIO"
sh.color_type = "TEXTURE"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.show_shadows = False
sh.show_object_outline = True
S.render.resolution_x, S.render.resolution_y = 1280, 720
S.render.film_transparent = False
S.display.shading.background_type = "VIEWPORT"
S.display.shading.background_color = (0.32, 0.34, 0.36)
S.render.image_settings.file_format = "PNG"
eye = bpy.data.objects["FPS • Camera"]
# откуда смотрим (оси автомата: +X дуло, +Y влево, +Z вверх) и «верх» кадра
DIRS = {"right": ((0, -1, 0), (0, 0, 1)), "left": ((0, 1, 0), (0, 0, 1)), "top": ((0, 0, 1), (1, 0, 0)),
        "bottom": ((0, 0, -1), (1, 0, 0)), "front": ((1, 0, 0), (0, 0, 1)), "back": ((-1, 0, 0), (0, 0, 1)),
        "r34": ((-0.55, -0.7, 0.45), (0, 0, 1)), "l34": ((-0.55, 0.7, 0.45), (0, 0, 1)),
        "rlow": ((0.3, -0.75, -0.6), (0, 0, 1)), "llow": ((0.3, 0.75, -0.6), (0, 0, 1))}
cam_data = bpy.data.cameras.new("check")
cam_data.type = "ORTHO"
cam_data.clip_start, cam_data.clip_end = 0.01, 5.0
cam = bpy.data.objects.new("check", cam_data)
S.collection.objects.link(cam)
OUT.mkdir(parents=True, exist_ok=True)
for act_name, f in FRAMES:
    if act_name and clip_tools is not None:
        assert clip_tools.open_action(bpy.context, act_name), act_name
    if clip_tools is not None and VAR:
        clip_tools.show_variant(VAR.get("grip", ""), VAR.get("mag", "30"), bool(VAR.get("light")))
    S.frame_set(f)
    bpy.context.view_layer.update()
    TW = root.matrix_world.copy()
    for v in VIEWS:
        near = v.endswith("_near")
        muzzle = v.endswith("_muzzle")
        base = v.split("_")[0]
        if base == "eye":
            S.camera = eye
        else:
            c = TW @ (Vector((0.20, 0.0, -0.06)) if near else Vector((0.68, 0.0, 0.0)) if muzzle else Vector((0.25, 0.0, -0.04)))
            cam_data.ortho_scale = 0.32 if near else 0.40 if muzzle else 0.95
            d, up = DIRS[base]
            d = (TW.to_3x3() @ Vector(d)).normalized()
            up = (TW.to_3x3() @ Vector(up)).normalized()
            x = up.cross(d).normalized()
            y = d.cross(x)
            m = Matrix((x, y, d)).transposed().to_4x4()
            m.translation = c + d * 1.5
            cam.matrix_world = m
            S.camera = cam
        clip = (act_name or "").replace("VERAS54_", "")
        S.render.filepath = str(OUT / f"{TAG}{v}_{clip + '_' if clip else ''}{f:03d}.png")
        bpy.ops.render.render(write_still=True)
print("STILLS", OUT)
