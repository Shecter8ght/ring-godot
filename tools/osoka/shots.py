# «Осока»: снимки модели — сверка с заводским снимком КБМ (вид слева в его масштабе, наложение 50 %) и виды для
# владельца. "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/osoka/shots.py -- <папка> [виды через запятую]
# виды: kbm (наложение), left, right, top, bottom, front, rear, q_front, q_rear, close_launcher, close_bell, missile
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import lib  # noqa: E402

KBM = r"E:/Models Blender/WEAPONS/Верба — модель/refs/web/kbm_ru/kbm_verba_left_IFF_2631x822.png"
KBM_W, KBM_H = 2631, 822


def setup_render(w, h, samples=1):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_cavity = True
    sc.display.shading.cavity_type = "WORLD"
    sc.display.shading.show_object_outline = False
    sc.display.shading.show_specular_highlight = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.display.render_aa = "16"
    sc.view_settings.view_transform = "Standard"
    w_ = sc.world or bpy.data.worlds.new("W")
    sc.world = w_
    w_.color = (0.92, 0.92, 0.92)


def camera(name, loc, look, ortho=None, lens=85.0):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
    cam.data.clip_start = 0.01
    cam.data.clip_end = 100.0
    bpy.context.scene.camera = cam
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("SHOT", path)


def kbm_overlay(out):
    """Вид слева ортографически в масштабе снимка КБМ; снимок срезан по наклону оси (0.25°) — ось горизонтальна."""
    setup_render(KBM_W, KBM_H)
    S = lib.S_PX
    cx = lib.px_x(KBM_W / 2)
    cz = (lib.AXIS_Y0 - KBM_H / 2) * S
    camera("Cam_kbm", (cx * lib.MM, 3.0, cz * lib.MM), (cx * lib.MM, 0.0, cz * lib.MM), ortho=KBM_W * S * lib.MM)
    model = os.path.join(out, "kbm_model.png")
    render(model)
    # наложение — системным Python с PIL (у Blender его нет): печатаем команду
    print("OVERLAY_CMD", f'python -X utf8 "{os.path.join(HERE, "overlay.py")}" "{KBM}" "{model}" "{os.path.join(out, "compare_kbm.png")}"')


VIEWS = {
    # имя: (положение камеры, точка взгляда, орто-масштаб или None — перспектива, объектив)
    "left": ((850, 3000, 0), (850, 0, 0), 1900, 0),
    "right": ((850, -3000, 0), (850, 0, 0), 1900, 0),
    "top": ((850, 0.01, 3000), (850, 0, 0), 1900, 0),
    "bottom": ((850, 0.01, -3000), (850, 0, 0), 1900, 0),
    "front": ((3000, 0, -20), (0, 0, -20), 330, 0),
    "rear": ((-3000, 0, -20), (0, 0, -20), 330, 0),
    "q_front": ((2600, 1500, 900), (900, 0, -30), None, 55),
    "q_rear": ((-900, 1500, 800), (800, 0, -30), None, 55),
    "close_launcher": ((1330, 1100, 260), (1300, 0, -50), None, 85),
    "close_launcher_r": ((1330, -1100, 220), (1300, 0, -50), None, 85),
    "close_bell": ((1900, 600, 250), (1560, 0, 0), None, 85),
    "missile": ((2600, 2600, 700), (2600, 0, 0), None, 50),
    "missile_tail": ((1700, 420, 260), (1840, 0, 0), None, 70),
    "missile_nose": ((3500, 380, 200), (3330, 0, 0), None, 70),
    "open": ((2400, 1700, 600), (850, 0, -40), None, 45),
}


# состояния управления для видов (остальное — по умолчанию)
STATES = {
    "missile": {"missile_out": 1.0, "fins": 1.0},
    "missile_tail": {"missile_out": 1.0, "fins": 1.0},
    "missile_nose": {"missile_out": 1.0, "fins": 1.0},
    "open": {"front_cap": 1.0, "rear_cap": 1.0, "launcher_detach": 1.0, "power_out": 1.0, "lever": 1.0,
             "dust_cover": 1.0, "front_sight": 0.0, "rear_sight": 0.0},
}


def set_state(name):
    ctrl = bpy.data.objects.get("OSOKA_Controls")
    if ctrl is None:
        return
    base = {"front_sight": 1.0, "rear_sight": 1.0}
    for k in list(ctrl.keys()):
        if not k.startswith("_"):
            ctrl[k] = base.get(k, 0.0)
    for k, val in STATES.get(name, {}).items():
        ctrl[k] = val
    ctrl.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def view(out, name, w=1800, h=900):
    set_state(name)
    loc, look, ortho, lens = VIEWS[name]
    if name in ("front", "rear"):
        w, h = 900, 900
    setup_render(w, h)
    camera("Cam_" + name, [c * lib.MM for c in loc], [c * lib.MM for c in look], ortho=ortho * lib.MM if ortho else None,
           lens=lens or 85.0)
    render(os.path.join(out, name + ".png"))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    names = argv[1].split(",") if len(argv) > 1 else ["kbm"] + list(VIEWS)
    for n in names:
        if n == "kbm":
            kbm_overlay(out)
        else:
            view(out, n)


main()
