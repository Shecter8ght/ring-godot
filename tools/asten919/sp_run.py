"""АСТЕН-919: задания для Substance Painter через мост каталога отделок (tools/asset_kit/finish/sp_run.py) — свой
экземпляр и своя папка заданий _asset_src/asten919/tex/sp_jobs. Painter стартует без неявных слоёв Vulkan (RivaTuner,
оверлеи Steam): с ними 12.1 падал на первом кадре и при запекании (tools/handguard_dolinskyi/sp_run.py, 2026-11-01).

    python -X utf8 tools/asten919/sp_run.py start
    python -X utf8 tools/asten919/sp_run.py -c "print(sp_asten.create())" [секунд]     # sp_asten уже импортирован
    python -X utf8 tools/asten919/sp_run.py wait <метка> [секунд]
    python -X utf8 tools/asten919/sp_run.py quit
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ["FINISH_SP_JOBS"] = str(ROOT / "_asset_src" / "asten919" / "tex" / "sp_jobs")
os.environ.update({"VK_LOADER_LAYERS_DISABLE": "~implicit~", "DISABLE_RTSS_LAYER": "1",
                   "DISABLE_VK_LAYER_VALVE_steam_overlay_1": "1", "DISABLE_VK_LAYER_VALVE_steam_fossilize_1": "1"})
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
import sp_run as base  # noqa: E402

base.HEADER += (f"sys.path.insert(0, r'{HERE.as_posix()}') if r'{HERE.as_posix()}' not in sys.path else None\n"
                "import tex_sets, sp_asten\nimportlib.reload(tex_sets); importlib.reload(sp_asten)\n")

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "clear":            # убрать метку перед длинным действием
        p = base.SP_JOBS / a[1]
        if p.exists():
            p.unlink()
    else:
        base.main()
