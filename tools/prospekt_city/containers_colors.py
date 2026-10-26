"""Контейнеры «Проспекта»: цвета краски — синий, зелёный, бежевый к основному ржаво-красному.

    python -X utf8 tools/prospekt_city/containers_colors.py paint
        — под замком Painter (sp_lock.py), проект контейнеров открыт: стек с каждым цветом (sp/stack_containers.py,
          наборы C20, C40), выгрузка, карта цвета → <textures>/<набор>_<цвет>_baseColor.png; в конце стек снова красный.
    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/containers_colors.py -- \
        blend <игровой .blend (game_apply.py)> <папка textures>
        — у вариантов-цветов (GAME["extra"] containers.py: «c20_closed_blue» …) сетки становятся своими копиями
          (развёртка та же), материалы C20 / C40 — копиями «C20_blue» … с другой картой цвета; ORM и нормали общие.
Порядок: sp_family.sh / sp_cycle.sh (основной цвет) → paint → blend → game_previews.py → game_export.py.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
COLORS = ("blue", "green", "beige")
SETS = ("C20", "C40")
OUT = Path(r"E:\Models Blender\ENVIRONMENT\Проспект_город_партия1\Контейнеры\textures")


def sp(args: list, timeout: int = 900) -> str:
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "sp_run.py")] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout + 60)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)
    return r.stdout


def sharpen(path: Path) -> None:
    """Лёгкая резкость цветовой копии — как sharpen_maps.py у основного цвета (там пары с ORM, у копий её нет)."""
    from PIL import Image, ImageFilter
    im = Image.open(path)
    rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
    if im.mode == "RGBA":
        rgb.putalpha(im.getchannel("A"))
    rgb.save(path)


def paint() -> None:
    tmp = ROOT / "_asset_src" / "prospekt_city" / "Containers_ISO" / "colors"
    for color in COLORS:
        print(sp([str(HERE / "sp" / "stack_containers.py"), "900", "--", f"paint={color}", "sets=C20,C40"]).strip())
        d = tmp / color
        d.mkdir(parents=True, exist_ok=True)
        code = ("import sp_lib\n"
                f"for ts in {SETS!r}:\n"
                f"    print(ts, sp_lib.export(r'{d.as_posix()}', ts)[0])\n")
        print(sp(["-c", code, "900"]).strip())
        for ts in SETS:
            dst = OUT / f"{ts}_{color}_baseColor.png"
            shutil.copyfile(d / f"{ts}_baseColor.png", dst)
            sharpen(dst)
            print("цвет:", dst)
    print(sp([str(HERE / "sp" / "stack_containers.py"), "900", "--", "paint=red", "sets=C20,C40"]).strip())


def blend(path: str, textures: str) -> None:
    import bpy
    sys.path.insert(0, str(HERE))
    import containers as K
    bpy.ops.wm.open_mainfile(filepath=path)
    folder = Path(textures)
    made = {}

    def colored(m, color):
        key = (m.name, color)
        if key in made:
            return made[key]
        c = m.copy()
        c.name = f"{m.name}_{color}"
        for n in c.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.name.startswith(f"{m.name}_baseColor"):
                img = bpy.data.images.load(str(folder / f"{m.name}_{color}_baseColor.png"), check_existing=True)
                img.colorspace_settings.name = "sRGB"
                n.image = img
        made[key] = c
        return c
    for col in bpy.context.scene.collection.children:
        roots = [o for o in col.objects if o.type == "EMPTY" and o.get("variant") in K.GAME["extra"]]
        if not roots:
            continue
        color = roots[0]["variant"].rsplit("_", 1)[1]
        for o in col.objects:
            if o.type != "MESH":
                continue
            o.data = o.data.copy()
            for i, m in enumerate(o.data.materials):
                if m and m.name in SETS:
                    o.data.materials[i] = colored(m, color)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("цвета в", path, sorted(m.name for m in made.values()))


if __name__ == "__main__":
    if "--" in sys.argv:
        a = sys.argv[sys.argv.index("--") + 1:]
        blend(a[1], a[2])
    elif sys.argv[1] == "paint":
        paint()
