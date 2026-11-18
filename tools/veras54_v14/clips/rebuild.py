"""ВЕРАС-54, клипы рук: то, что делает rebuild.cmd / regenerate.cmd над файлом клипов.

blender -b <клипы.blend> --python-exit-code 1 --python tools/veras54_v14/clips/rebuild.py -- <клипы.blend> [--regenerate]

Файл уже с клипами владельца (в нём есть снимок поз VERAS54_Poses_applied) — делается только то же, что кнопка панели
«Хваты из поз → во все клипы»: позы переносятся в клипы, версии собираются заново, движение и ручные ключи остаются, текст
панели обновляется. Флаг --regenerate — клипы собираются заново из таблиц build_clips.py (ручные правки клипов стираются,
позы остаются).
"""
import runpy
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clip_tools  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
say = lambda *a: print("VERAS_CLIPS", *a, flush=True)  # noqa: E731

if "--regenerate" in args or clip_tools.APPLIED not in bpy.data.actions:
    say("клипы собираются заново из таблиц build_clips.py (позы — из файла)")
    sys.argv = sys.argv[:sys.argv.index("--") + 1] + [out]
    runpy.run_path(str(HERE / "build_clips.py"), run_name="__main__")
else:
    res = clip_tools.sync(bpy.context, say)
    if res is None:
        raise SystemExit(1)
    say(f"позы перенесены в клипы: поправлено ключей {res[0]}, клипов {res[1]}; движение и ручные ключи не тронуты")
    panel = bpy.data.texts.get(clip_tools.PANEL_TEXT) or bpy.data.texts.new(clip_tools.PANEL_TEXT)
    panel.from_string((HERE / "clip_tools.py").read_text(encoding="utf-8"))
    panel.use_module = True
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    say("сохранено", out)
