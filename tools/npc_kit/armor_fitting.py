"""NPC: «примерочная» — мародёр с текстурами и все три брони в одном файле, переключаются в Outliner.

Берёт npc_scav_<версия>_tex.blend и дописывает коллекции брони из armor_<уровень>_tex.blend (у каждой брони свои
материалы Poor_* / Mid_* / Top_*). Одинаковые картинки (плетение, маски) сводятся к одной. Видна одна броня
(по умолчанию — средняя); остальные включаются галочкой коллекции 06_Armor_* в Outliner.
Снимок: мародёр в каждой броне 3/4 спереди — три кадра рядом (previews/armor_fitting.jpg).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_fitting.py -- [shots] [deliver=<папка>]
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

ARMOR = kc.WORK / "armor"
TIERS = (("poor", "06_Armor_Poor", "бомжовская"), ("mid", "06_Armor_Mid", "средняя"), ("top", "06_Armor_Top", "крутая"))


def append_armor(tier: str, col_name: str) -> bpy.types.Collection:
    path = ARMOR / f"armor_{tier}_tex.blend"
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == col_name]
    col = next(c for c in dst.collections if c is not None)
    bpy.context.scene.collection.children.link(col)
    return col


def dedupe_images() -> int:
    """Одна картинка на файл: копии (имя.001) от разных броней → оригинал."""
    by_path: dict[str, bpy.types.Image] = {}
    n = 0
    for im in list(bpy.data.images):
        if im.source != "FILE" or not im.filepath:
            continue
        key = bpy.path.abspath(im.filepath).lower()
        if key in by_path and by_path[key] != im:
            im.user_remap(by_path[key])
            bpy.data.images.remove(im)
            n += 1
        else:
            by_path[key] = im
    return n


def show_only(col_name: str) -> None:
    for _, name, _ in TIERS:
        lc = bpy.context.view_layer.layer_collection.children.get(name)
        if lc is not None:
            lc.hide_viewport = name != col_name
        c = bpy.data.collections.get(name)
        if c is not None:
            c.hide_render = name != col_name


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.npc_file()))
    for tier, col_name, _ in TIERS:
        append_armor(tier, col_name)
    kc.log("  картинок-копий сведено:", dedupe_images())
    if "shots" in args:
        shots()
    show_only("06_Armor_Mid")
    out = kc.WORK / f"armor_fitting_{kc.VERSION}.blend"
    kc.save(out)
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        show_only("06_Armor_Mid")
        am.deliver(Path(dest), "Примерка_брони_на_мародёре_v03.blend", (
            "Примерочная: мародёр v03 с текстурами и все три брони (текстуры приняты).\n"
            "Переключение — галочки (глаз) коллекций в Outliner: 06_Armor_Poor — бомжовская, 06_Armor_Mid — средняя,\n"
            "06_Armor_Top — крутая. Включать по одной: брони надеты на одно тело и проходят друг сквозь друга.\n"
            "Для рендера по F12 — ещё и значок фотоаппарата у коллекции. Смотреть в Rendered (Cycles).\n"
            "Скрипт: tools/npc_kit/armor_fitting.py.\n"), focus_z=1.15)


def shots() -> None:
    kc.studio()
    kc.gpu_cycles(128)
    scene = bpy.context.scene
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    out = kc.WORK / "previews"
    cam = kc.camera("Cam_Fitting", (1.55, -2.35, 1.30), (0.0, 0.0, 1.02), 50)
    paths = []
    for tier, col_name, _ in TIERS:
        show_only(col_name)
        p = out / f"armor_fitting_{tier}.png"
        kc.render(cam, p, (900, 1300), 128)
        paths.append(p)
    # три кадра рядом — в одно изображение (через картинки Blender: в его Python нет PIL)
    import numpy as np
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    strip = np.zeros((h, w * 3, 4), np.float32)
    for i, im in enumerate(imgs):
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        strip[:, i * w:(i + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("armor_fitting", w * 3, h, alpha=False)
    res.pixels.foreach_set(strip.ravel())
    settings = scene.render.image_settings
    settings.file_format = "JPEG"
    settings.quality = 90
    settings.color_mode = "RGB"
    res.save_render(str(out / "armor_fitting.jpg"))
    kc.log("FITTING", out / "armor_fitting.jpg")


if __name__ == "__main__":
    main()
