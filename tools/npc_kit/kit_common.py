"""Общее для сборки модульного NPC (tools/npc_kit): пути, студия, рендер, MPFB.

Запускается внутри Blender 5.2 (--background --factory-startup). Каждый этап — отдельный
скрипт, который читает .blend прошлого этапа и пишет свой в _asset_src/npc_kit.
"""
from __future__ import annotations

import importlib
import math
import sys
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src" / "npc_kit"
MPFB = "bl_ext.blender_org.mpfb"


def log(*parts: object) -> None:
    """Печать сразу в поток: при выводе в файл Blender копит его до выхода."""
    print(*parts)
    sys.stdout.flush()


def args_after_dashes() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def enable_mpfb() -> dict:
    if MPFB not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module = MPFB
    addon_utils.enable(MPFB, default_set=False, persistent=False)
    services = {}
    for module, name in [
        ("humanservice", "HumanService"),
        ("targetservice", "TargetService"),
        ("rigservice", "RigService"),
        ("locationservice", "LocationService"),
    ]:
        services[name] = getattr(importlib.import_module(MPFB + ".services." + module), name)
    return services


def gpu_cycles(samples: int = 64) -> None:
    """Cycles на видеокарте: в фоне настройки пустые, устройство включаем сами."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                break
        except TypeError:
            continue
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True


def wipe_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    holder = parent or bpy.context.scene.collection
    if col.name not in holder.children:
        holder.children.link(col)
    return col


def move_to(obj: bpy.types.Object, col: bpy.types.Collection) -> None:
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)


def make_active(obj: bpy.types.Object) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def clay(name: str, color: tuple[float, float, float], roughness: float = 0.7) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def studio(dark: bool = False) -> bpy.types.Collection:
    """Студия для проверки: мягкий ключ, заполнение, контровой, серый фон и пол."""
    col = collection("99_Studio")
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    g = 0.05 if dark else 0.30
    bg.inputs[0].default_value = (g, g, g * 1.04, 1.0)
    bg.inputs[1].default_value = 1.0
    floor_mat = clay("Studio_Floor", (0.32, 0.32, 0.33) if not dark else (0.06, 0.06, 0.065), 0.85)
    if "Studio_Floor" not in bpy.data.objects:
        mesh = bpy.data.meshes.new("Studio_Floor")
        mesh.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
        floor = bpy.data.objects.new("Studio_Floor", mesh)
        col.objects.link(floor)
        floor.data.materials.append(floor_mat)
    for name, pos, power, size in [
        ("Key", (-2.2, -2.8, 3.2), 420.0, 2.2),
        ("Fill", (2.6, -2.0, 1.6), 140.0, 2.6),
        ("Rim", (1.2, 2.6, 3.0), 300.0, 1.6),
        ("Back_Fill", (-1.8, 2.4, 1.2), 90.0, 2.0),
    ]:
        if name in bpy.data.objects:
            continue
        light = bpy.data.lights.new(name, "AREA")
        light.energy = power
        light.shape = "DISK"
        light.size = size
        obj = bpy.data.objects.new(name, light)
        col.objects.link(obj)
        obj.location = pos
        look_at(obj, (0, 0, 1.1))
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    return col


def camera(name: str, pos: tuple[float, float, float], target: tuple[float, float, float],
           lens: float = 85.0, ortho: float | None = None) -> bpy.types.Object:
    col = collection("99_Studio")
    data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, data)
    if obj.name not in col.objects:
        col.objects.link(obj)
    obj.location = pos
    look_at(obj, target)
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    else:
        data.type = "PERSP"
        data.lens = lens
    data.clip_end = 100
    return obj


def render(cam: bpy.types.Object, path: Path, size: tuple[int, int] = (1200, 1600), samples: int = 64) -> None:
    scene = bpy.context.scene
    gpu_cycles(samples)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def view_cameras(height: float = 1.8) -> dict[str, bpy.types.Object]:
    """Стандартные ракурсы проверки персонажа: лицо смотрит в -Y."""
    mid = height * 0.52
    return {
        "front": camera("Cam_Front", (0, -5.2, mid), (0, 0, mid), 70),
        "back": camera("Cam_Back", (0, 5.2, mid), (0, 0, mid), 70),
        "side": camera("Cam_Side", (5.2, 0, mid), (0, 0, mid), 70),
        "three_quarter": camera("Cam_34", (3.4, -4.0, mid + 0.2), (0, 0, mid), 70),
        "head": camera("Cam_Head", (0.55, -1.25, height * 0.94), (0, 0, height * 0.925), 85),
        "hands": camera("Cam_Hands", (0.9, -1.2, 0.95), (0.33, -0.05, 0.85), 85),
    }


def save(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False, compress=True)


def deg(a: float) -> float:
    return math.radians(a)
