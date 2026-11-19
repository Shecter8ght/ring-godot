# ВЕРАС-54 v14, износ (этап 2): крупные планы мест эксплуатации при скользящем свете с двух направлений — на файле
# просмотра износа (tex_review.py apply). Студийные источники на время кадра выключаются, ставятся два узких источника
# почти вдоль поверхности (слева и справа от взгляда); файл не сохраняется.
#   blender -b "<ВЕРАС-54_износ_v14_01.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/wear_review.py -- <папка> [samples] [вид,вид]
#   python -X utf8 tools/veras54_v14/tex/wear_review.py sheets <папка кадров износа> <папка кадров заводской>   — листы «заводская | износ»
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# имя: (точка взгляда, м; направление к камере; расстояние, м; нормаль поверхности для скользящего света; позы рига)
CLOSE = {
    "c01_дуга_переводчика": ((0.150, -0.017, -0.012), (0.0, -1.0, 0.1), 0.15, (0, -1, 0), {"selector": 0.6}),
    "c02_окно_и_рама": ((0.205, -0.016, 0.020), (0.15, -1.0, 0.45), 0.17, (0, -1, 0), {}),
    "c03_рукоятка_взведения": ((0.235, -0.030, 0.010), (0.5, -0.8, 0.5), 0.09, (0, -1, 0), {}),
    "c04_шахта_и_магазин": ((0.200, -0.015, -0.045), (0.2, -1.0, -0.25), 0.17, (0, -1, 0), {}),
    "c05_пятка_магазина": ((0.240, -0.010, -0.195), (0.4, -1.0, -0.3), 0.14, (0, -1, 0), {}),
    "c06_рукоятка": ((0.030, -0.016, -0.095), (-0.2, -1.0, 0.0), 0.16, (0, -1, 0), {}),
    "c07_цевьё_снизу": ((0.345, -0.010, -0.020), (0.1, -0.8, -0.6), 0.25, (0, 0, -1), {}),
    "c08_планка_крышки": ((0.177, 0.0, 0.043), (-0.3, -0.5, 1.0), 0.17, (0, 0, 1), {}),
    "c09_боковая_планка": ((0.400, -0.020, 0.028), (0.1, -1.0, 0.3), 0.11, (0, -1, 0), {}),
    "c10_приклад_щека": ((-0.150, 0.010, -0.030), (0.1, 0.8, 0.6), 0.32, (0, 0, 1), {}),
    "c11_затыльник_и_труба": ((-0.150, -0.016, -0.050), (-0.6, -1.0, 0.2), 0.30, (0, -1, 0), {}),
    "c12_дульное": ((0.670, 0.0, 0.0), (0.5, -1.0, 0.3), 0.15, (0, -1, 0), {}),
    "c13_крышка_сзади": ((0.020, 0.0, 0.030), (-0.6, -0.6, 0.8), 0.14, (0, 0, 1), {}),
    "c14_зуб_планки": ((0.190, -0.006, 0.043), (0.15, -0.65, 0.75), 0.055, (0, 0, 1), {}),   # ракурс снимка владельца
}


def _graze(at, nrm, view, side):
    """Источник почти вдоль поверхности: направление ⟂ взгляду в плоскости поверхности, чуть над ней."""
    from mathutils import Vector
    n = Vector(nrm).normalized()
    v = Vector(view).normalized()
    t = n.cross(v)
    if t.length < 1e-3:
        t = n.orthogonal()
    t.normalize()
    d = (t * side + n * 0.18).normalized()
    return Vector(at) + d * 0.6


def shots(folder, samples=64, only=None):
    import bpy
    from mathutils import Vector
    import tex_review as R
    R._gpu()
    S = bpy.context.scene
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    cam = S.camera
    S.cycles.samples = samples
    S.render.resolution_x, S.render.resolution_y = 1600, 1000
    cam.data.sensor_fit = "AUTO"
    cam.data.lens = 50
    studio = [o for o in bpy.data.objects if o.type == "LIGHT"]
    ctl = bpy.data.objects.get("VERAS54_Controls")
    keep = {k: float(ctl[k]) for k in ctl.keys() if isinstance(ctl[k], (int, float))} if ctl else {}
    ld = bpy.data.lights.new("скользящий", "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = 0.02, 0.25
    ld.energy = 40.0
    lo = bpy.data.objects.new("скользящий", ld)
    S.collection.objects.link(lo)
    for o in studio:
        o.hide_render = True
    world = S.world
    bg = [n for n in world.node_tree.nodes if n.type == "BACKGROUND" and n.label.startswith("Отражения")]
    old_bg = bg[0].inputs["Strength"].default_value if bg else None
    if bg:
        bg[0].inputs["Strength"].default_value = 0.35
    try:
        for name, (at, view, dist, nrm, pose) in CLOSE.items():
            if only and name not in only and name.split("_")[0] not in only:
                continue
            R._pose({**keep, **pose})
            cam.location = Vector(at) + Vector(view).normalized() * dist
            cam.rotation_euler = (Vector(at) - cam.location).to_track_quat("-Z", "Y").to_euler()
            for side, tag in ((1, "a"), (-1, "b")):
                lo.location = _graze(at, nrm, view, side)
                lo.rotation_euler = (Vector(at) - lo.location).to_track_quat("-Z", "Y").to_euler()
                S.render.filepath = os.path.join(folder, f"{name}_{tag}.png")
                bpy.ops.render.render(write_still=True)
                print("SHOT", name, tag, flush=True)
    finally:
        for o in studio:
            o.hide_render = False
        if bg:
            bg[0].inputs["Strength"].default_value = old_bg
        bpy.data.objects.remove(lo)
        R._pose(keep)


def sheets(wear, factory):
    """Пары «заводская | износ» по одинаковым именам кадров (PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    out = os.path.join(wear, "pairs")
    os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(wear)):
        if not f.endswith(".png") or not os.path.exists(os.path.join(factory, f)):
            continue
        a = Image.open(os.path.join(factory, f)).convert("RGB")
        b = Image.open(os.path.join(wear, f)).convert("RGB").resize(a.size)
        sh = Image.new("RGB", (a.width * 2 + 8, a.height + 30), (30, 30, 30))
        sh.paste(a, (0, 30))
        sh.paste(b, (a.width + 8, 30))
        d = ImageDraw.Draw(sh)
        d.text((8, 5), "заводская отделка", fill=(230, 230, 230), font=font)
        d.text((a.width + 16, 5), "износ v01 (этап 2)", fill=(230, 230, 230), font=font)
        sh.save(os.path.join(out, f.replace(".png", ".jpg")), quality=90)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if a[0] == "sheets":
        sheets(a[1], a[2])
    else:
        shots(a[0], int(a[1]) if len(a) > 1 else 64, a[2].split(",") if len(a) > 2 else None)
