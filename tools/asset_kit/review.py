# Самопроверка отделки ассета до показа владельцу: метрики карт PBR и рендер в постоянной студии.
# Кадры и отчёт — для самого агента (владельцу листы показа не нужны). Описание и пороги —
# tools/asset_skills/weapon-asset-texturing/references/validation-and-delivery.md, «Самопроверка».
#
#   python -X utf8 tools/asset_kit/review.py maps <папка карт|файлы…> [--mesh модель.gltf|.glb|.fbx|.blend …] [--out папка]
#   python -X utf8 tools/asset_kit/review.py render <модель.blend|.gltf|.glb|.fbx> [--out папка] [--views r34,fps,…] [--samples 64]
#   python -X utf8 tools/asset_kit/review.py preset <имя> [--no-render] [--no-maps] — наборы из presets.json (veras54, pm, vss_m_v8)
#
# Внутри Blender (запускает сам review.py): blender --background --factory-startup --python review.py -- render|uvdump …
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BLENDER = os.environ.get("BLENDER", r"D:\ПРОГРАММЫ\Blender 5\blender.exe")
sys.path.insert(0, HERE)

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


def blender(args, log):
    cmd = [BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.join(HERE, "review.py"), "--"] + args
    t = time.time()
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        with open(log, encoding="utf-8", errors="replace") as f:
            tail = f.read()[-3000:]
        raise RuntimeError(f"Blender упал ({r.returncode}), журнал {log}:\n{tail}")
    print(f"Blender: {time.time() - t:.0f} с, журнал {log}", flush=True)


def uv_sources(meshes, out_dir, skip):
    """glTF читается здесь; .fbx/.blend/.obj — выгрузкой развёртки через Blender."""
    res = []
    for i, p in enumerate(meshes or []):
        ext = os.path.splitext(p)[1].lower()
        if ext in (".gltf", ".glb", ".json"):
            res.append(p)
            continue
        dump = os.path.join(out_dir, "uv", f"uv_{i}_{os.path.splitext(os.path.basename(p))[0]}.json")
        os.makedirs(os.path.dirname(dump), exist_ok=True)
        if not (os.path.exists(dump) and os.path.getmtime(dump) > os.path.getmtime(p)):   # сетка не менялась — прежняя выгрузка
            blender(["uvdump", p, dump, "--skip", skip], os.path.join(out_dir, "uv", f"uvdump_{i}.log"))
        res.append(dump)
    return res


def run_maps(inputs, meshes, out_dir, only=None, px_cm=None, skip=None, title=""):
    import kit_maps
    import kit_mesh
    skip = kit_mesh.LOD_SKIP if skip is None else skip
    os.makedirs(out_dir, exist_ok=True)
    t = time.time()
    rep = kit_maps.check_asset(inputs, uv_sources(meshes, out_dir, skip), out_dir, only, px_cm, skip)
    rep["limits"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in kit_maps.LIMITS.items()}
    with open(os.path.join(out_dir, "maps.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    txt = kit_maps.text_report(rep, title)
    with open(os.path.join(out_dir, "maps.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)
    print(f"карты: {time.time() - t:.0f} с → {out_dir}", flush=True)
    return rep


def run_render(asset, out_dir, views=None, samples=64, channels=False, hide="", preset=None):
    import kit_shots
    os.makedirs(out_dir, exist_ok=True)
    args = ["render", asset, out_dir, "--samples", str(samples)]
    if views:
        args += ["--views", views]
    if channels:
        args += ["--channels"]
    if hide:
        args += ["--hide", hide]
    if preset:
        args += ["--frame", json.dumps(preset, ensure_ascii=False)]
    blender(args, os.path.join(out_dir, "render.log"))
    rep = kit_shots.finish(out_dir)
    txt = kit_shots.text_report(rep)
    with open(os.path.join(out_dir, "render.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)
    return rep


def main_cli():
    ap = argparse.ArgumentParser(description="Самопроверка отделки: карты PBR и рендер в студии")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("maps")
    m.add_argument("inputs", nargs="+")
    m.add_argument("--mesh", nargs="*", default=[])
    m.add_argument("--out", default=None)
    m.add_argument("--only", default="")
    m.add_argument("--px-cm", type=float, default=None)
    m.add_argument("--skip", default=None, help="регулярка имён сеток, которые не брать (по умолчанию LOD1+)")
    r = sub.add_parser("render")
    r.add_argument("asset")
    r.add_argument("--out", default=None)
    r.add_argument("--views", default="")
    r.add_argument("--samples", type=int, default=64)
    r.add_argument("--channels", action="store_true", help="ещё цвет / шероховатость / металличность излучением")
    r.add_argument("--hide", default="", help="регулярка имён объектов, которые не рендерить")
    p = sub.add_parser("preset")
    p.add_argument("name")
    p.add_argument("--out", default=None)
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--no-maps", action="store_true")
    p.add_argument("--views", default="")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--channels", action="store_true")
    p.add_argument("--only", default="")
    a = ap.parse_args()
    scratch = os.environ.get("REVIEW_OUT") or os.path.join(ROOT, "_asset_src", "_review")   # не в git
    if a.cmd == "maps":
        out = a.out or os.path.join(scratch, "maps_" + time.strftime("%H%M%S"))
        run_maps(a.inputs, a.mesh, out, [s for s in a.only.split(",") if s], a.px_cm, a.skip)
    elif a.cmd == "render":
        out = a.out or os.path.join(scratch, "render_" + time.strftime("%H%M%S"))
        run_render(a.asset, out, a.views, a.samples, a.channels, a.hide)
    else:
        with open(os.path.join(HERE, "presets.json"), encoding="utf-8") as f:
            pr = json.load(f)[a.name]
        out = a.out or os.path.join(scratch, a.name)
        absp = lambda x: x if os.path.isabs(x) else os.path.join(ROOT, x)  # noqa: E731
        texts, findings = [], []
        if not a.no_maps and pr.get("maps"):
            rm = run_maps([absp(x) for x in pr["maps"]], [absp(x) for x in pr.get("mesh", [])], os.path.join(out, "maps"),
                          [s for s in a.only.split(",") if s], pr.get("px_cm"), pr.get("skip"), title=a.name)
            findings += rm["findings"]
            with open(os.path.join(out, "maps", "maps.txt"), encoding="utf-8") as f:
                texts.append(f.read())
        if not a.no_render and pr.get("asset"):
            rr = run_render(absp(pr["asset"]), os.path.join(out, "render"), a.views or pr.get("views", ""), a.samples,
                            a.channels, pr.get("hide", ""), pr.get("frame"))
            findings += rr["findings"]
            with open(os.path.join(out, "render", "render.txt"), encoding="utf-8") as f:
                texts.append(f.read())
        verdict = "исправить" if any(x["level"] == "fail" for x in findings) else (
            "посмотреть" if any(x["level"] == "warn" for x in findings) else "чисто")
        with open(os.path.join(out, "report.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{a.name}: {verdict}\n\n" + "\n".join(texts))
        print(f"{a.name}: {verdict} → {os.path.join(out, 'report.txt')}")


if __name__ == "__main__":
    if IN_BLENDER:
        import kit_blender
        kit_blender.main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        main_cli()
