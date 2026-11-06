# «Осока», тепловизионный прицел: снимки формы на приёмку (Workbench, нейтральный материал).
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/osoka/sight_shots.py -- <папка> [виды через запятую]
# Виды прицела — по габариту объектов THERMAL; в сборке (есть «Осока») — ещё виды на трубе: asm_*.
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import shots  # noqa: E402


def thermal_bbox():
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in bpy.data.objects:
        if o.type != "MESH" or not any(c.name.startswith(("THERMAL", "Thermal_")) for c in o.users_collection):
            continue
        for p in o.bound_box:
            w = o.matrix_world @ Vector(p)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def view_dir(az, el):
    """Направление ОТ центра к камере: az — от +X (вперёд) к +Y (влево), el — вверх, градусы."""
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    want = argv[1].split(",") if len(argv) > 1 else None
    # третий аргумент — положения: «cap=1,mode=0.5» (свойства THERMAL_Controls)
    tc = bpy.data.objects.get("THERMAL_Controls")
    if len(argv) > 2 and tc is not None:
        for kv in argv[2].split(","):
            k, val = kv.split("=")
            tc[k] = float(val)
    for o in bpy.data.objects:
        if o.name.endswith("_Controls"):
            o.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    # чёрное на снимках формы не читается — только для снимков светлее (в файл не пишется)
    for m in bpy.data.materials:
        c = m.diffuse_color
        if max(c[0], c[1], c[2]) < 0.06:
            g = 0.30 if "Rubber" in m.name else (0.36 if "metal" in m.name or "Alu" in m.name or "Steel" in m.name else 0.42)
            if m.name == "Germanium":
                g = 0.16
            if m.name == "Lens":
                g = 0.12
            m.diffuse_color = (g, g, g * 1.02, 1.0)
    lo, hi = thermal_bbox()
    c = (lo + hi) / 2
    size = (hi - lo).length
    asm = bpy.data.objects.get("OSOKA_Controls") is not None
    views = {
        # имя: (азимут, высота, орто-масштаб в долях габарита или 0 — перспектива, ширина, высота кадра)
        "left": (90, 0, 1.15, 1600, 1100), "right": (-90, 0, 1.15, 1600, 1100), "front": (0, 0, 0.9, 1200, 1100),
        "rear": (180, 0, 0.9, 1200, 1100), "top": (90.01, 89.9, 1.15, 1600, 1100), "bottom": (90.01, -89.9, 1.15, 1600, 1100),
        "q_fl": (35, 22, 0, 1600, 1100), "q_rl": (145, 22, 0, 1600, 1100), "q_rr": (-145, 25, 0, 1600, 1100),
        "q_fr": (-35, 20, 0, 1600, 1100), "q_under": (60, -30, 0, 1600, 1100),
    }
    for name, (az, el, orth, w, h) in views.items():
        if want and name not in want:
            continue
        shots.setup_render(w, h)
        d = view_dir(az, el)
        if orth:
            shots.camera("Cam_" + name, c + d * 2.0, c, ortho=size * orth)
        else:
            shots.camera("Cam_" + name, c + d * size * 2.6, c, lens=70)
        shots.render(os.path.join(out, f"{name}.png"))
    if not asm:
        return
    M = 0.001
    # сборка: крупно область пускового механизма и прицела, вся «Осока» сбоку, глазами стрелка
    big = {
        "asm_left": ((1150, 1400, 120), (1150, 0, 60), 0.62, 1800, 1100),
        "asm_right": ((1150, -1400, 120), (1150, 0, 60), 0.62, 1800, 1100),
        "asm_full_left": ((850, 3000, 0), (850, 0, 0), 1.9, 2000, 700),
        "asm_top": ((1200, 40, 1500), (1200, 40, 0), 0.62, 1800, 1100),
        "asm_q_fl": ((1750, 650, 520), (1230, 30, 90), 0, 1800, 1100),
        "asm_q_rl": ((700, 600, 420), (1230, 20, 90), 0, 1800, 1100),
        "asm_front": ((2600, 0, 60), (1230, 20, 60), 0.42, 1400, 1100),
        "asm_rear": ((-300, 0, 60), (1230, 20, 60), 0.42, 1400, 1100),
        "asm_foot_r": ((1330, -230, 120), (1214, -4, 52), 0, 1800, 1100),
        "asm_foot_l": ((1300, 260, 150), (1210, 8, 58), 0, 1800, 1100),
        "asm_foot_rear": ((1060, -60, 110), (1214, 0, 52), 0, 1800, 1100),
        "asm_cap": ((1560, 330, 330), (1300, 48, 160), 0, 1800, 1100),
    }
    for name, (loc, look, orth, w, h) in big.items():
        if want and name not in want:
            continue
        shots.setup_render(w, h)
        if orth:
            shots.camera("Cam_" + name, tuple(x * M for x in loc), tuple(x * M for x in look), ortho=orth)
        else:
            shots.camera("Cam_" + name, tuple(x * M for x in loc), tuple(x * M for x in look), lens=50)
        shots.render(os.path.join(out, f"{name}.png"))


main()
