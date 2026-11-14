"""«Частокол», износ: подбор порога (Histogram Scan, Position) умной маски под долю поверхности — белый «маркер» по
маске на наборе, выгрузка 2K, замер доли закрытого, деление пополам. Painter с открытым проектом набора, мост
FINISH_SP_JOBS=_asset_src/pkp/tex/sp_jobs.

    python -X utf8 tools/pkp/wear_calib.py <набор> "<маска>:<доля>[:edge|cavity]" [...]  → wear_calib.json (набор, маска → Position)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

ROOT = "E:/Games/RING-godot"
J = ROOT + "/_asset_src/pkp/tex/sp_jobs"
OUT = ROOT + "/_asset_src/pkp/tex/calib"
STAGE1 = "E:/Models Blender/WEAPONS/Печенег — модель/текстуры_этап1_v02"
RES = ROOT + "/_asset_src/pkp/tex/wear_calib.json"
ENV = dict(os.environ, FINISH_SP_JOBS=J)
Image.MAX_IMAGE_PIXELS = None


def run(code, t=600):
    r = subprocess.run(["python", "-X", "utf8", "tools/asset_kit/finish/sp_run.py", "-c", code, str(t)], env=ENV,
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    return r.stdout.strip()


def coverage(setname, mask, pos, where=None):
    p = os.path.join(J, "_export_done.txt")
    if os.path.exists(p):
        os.remove(p)
    d = f"{OUT}/{setname}"
    tri = "1"
    code = f"""import importlib, sp_pkp, sp_pkp_wear as W, sp_lib, substance_painter.layerstack as L
importlib.reload(sp_pkp); importlib.reload(W)
g = W._group('{setname}')
lay = sp_lib.fill('маркер', L.InsertPosition.inside_node(g, L.NodeStack.Substack), color=(1.0, 1.0, 1.0), rough=1.0, metal=0.0)
lay.add_mask(L.MaskBackground.Black)
L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), W.smart_mask('{mask}'))
W.to_triplanar(lay, sp_pkp._scene())
{'W.place(lay, ' + repr(where) + ', ' + repr(setname) + ')' if where else ''}
{'W.scan(lay, ' + repr(pos) + ')' if pos is not None else ''}
print(sp_pkp.export(r'{d}', ['{setname}'], 2048))
"""
    out = run(code)
    if not out.startswith("OK"):
        raise SystemExit(out)
    t0 = time.time()
    while not os.path.exists(p):
        time.sleep(1)
        if time.time() - t0 > 900:
            raise SystemExit("нет выгрузки")
    time.sleep(1)
    bc = np.asarray(Image.open(f"{d}/{setname}_baseColor.png").convert("L"), np.float32) / 255.0
    base = np.asarray(Image.open(f"{STAGE1}/{setname}_baseColor.png").convert("L").resize(bc.shape[::-1]), np.float32) / 255.0
    # только наружное: затенение этапа 1 светлое (внутренности листовой коробки — половина площади набора — в тени,
    # пыль там уместна и долю не мерит)
    ao = np.asarray(Image.open(f"{STAGE1}/{setname}_occlusionRoughnessMetallic.png").convert("RGB").resize(bc.shape[::-1]),
                    np.float32)[..., 0] / 255.0
    used = islands(setname, bc.shape[0]) & (ao > 0.8)
    return float(((bc > 0.6) & used).sum() / used.sum())


_ISL = {}


def islands(setname, n):
    """Пиксели островов развёртки (поля между островами — заливка отступов, их не мерить)."""
    key = (setname, n)
    if key not in _ISL:
        from PIL import ImageDraw
        z = np.load(f"{ROOT}/_asset_src/pkp/tex/uv/{setname}_tris.npz")
        im = Image.new("L", (n, n), 0)
        dr = ImageDraw.Draw(im)
        for tri in z["tri"]:
            dr.polygon([(float(u) * n, (1.0 - float(v)) * n) for u, v in tri], fill=255)
        _ISL[key] = np.asarray(im) > 127
    return _ISL[key]


def find(setname, mask, target, where=None):
    lo, hi = 0.0, 1.0
    best = None
    for _ in range(6):
        mid = (lo + hi) / 2
        c = coverage(setname, mask, mid, where)
        print(f"  {mask} Position {mid:.3f} → {c:.4f}", flush=True)
        if best is None or abs(c - target) < abs(best[1] - target):
            best = (mid, c)
        if abs(c - target) < 0.15 * target:
            break
        if c < target:
            lo = mid
        else:
            hi = mid
    return best


def main():
    setname = sys.argv[1]
    res = json.load(open(RES, encoding="utf-8")) if os.path.exists(RES) else {}
    for item in sys.argv[2:]:
        parts = item.split(":")
        mask, target, where = parts[0], float(parts[1]), (parts[2] if len(parts) > 2 else None)
        pos, c = find(setname, mask, target, where)
        res.setdefault(setname, {})[mask + (":" + where if where else "")] = {
            "position": round(pos, 4), "coverage": round(c, 4), "target": target}
        print("CALIB", setname, mask, pos, c, flush=True)
        with open(RES, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    run("import importlib, sp_pkp_wear as W, sp_lib, substance_painter.layerstack as L\n"
        f"[L.delete_node(n) for n in L.get_root_layer_nodes(sp_lib.stack_by_name('{setname}')) if n.get_name() == W.GROUP]\nprint('clean')")


if __name__ == "__main__":
    main()
