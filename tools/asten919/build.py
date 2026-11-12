# АСТЕН-919: сборка сеток деталей (обычный Python, см. sdf.py).
#   python -X utf8 tools/asten919/build.py <папка вывода> [деталь …] [--k 2.0] [--jobs 6]
# --k — множитель вокселя (2 — черновик вчетверо быстрее). Пишет <деталь>.npz и manifest.json для assemble.py.
import importlib
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MODULES = ("part_slide", "part_barrel", "part_frame", "part_controls", "part_small", "part_magazine")


def catalog():
    out = []
    for m in MODULES:
        if not os.path.exists(os.path.join(HERE, m + ".py")):
            continue
        mod = importlib.import_module(m)
        for p in mod.parts():
            p["module"] = m
            out.append(p)
    return out


def run(job):
    name, module, out_dir, k = job
    t = time.time()
    mod = importlib.import_module(module)
    p = next(q for q in mod.parts() if q["name"] == name)
    res = p["build"](p.get("h", 0.1) * k)
    path = os.path.join(out_dir, name + ".npz")
    if isinstance(res, tuple):
        import numpy as np
        if len(res) > 2:
            np.savez_compressed(path, v=res[0], f=res[1], m=res[2])
        else:
            np.savez_compressed(path, v=res[0], f=res[1])
        print(f"MESH {name}: {len(res[0])} вершин, {len(res[1])} граней, {time.time() - t:.1f} с", flush=True)
    else:
        res.save(path)
    return name


def main():
    args = sys.argv[1:]
    out_dir = os.path.abspath(args[0])
    k = 1.0; jobs = 6; names = []
    i = 1
    while i < len(args):
        if args[i] == "--k":
            k = float(args[i + 1]); i += 2
        elif args[i] == "--jobs":
            jobs = int(args[i + 1]); i += 2
        else:
            names.append(args[i]); i += 1
    os.makedirs(out_dir, exist_ok=True)
    cat = catalog()
    todo = [p for p in cat if not names or p["name"] in names or p["module"].replace("part_", "") in names]
    t = time.time()
    work = [(p["name"], p["module"], out_dir, k) for p in todo]
    # тяжёлые — первыми
    work.sort(key=lambda j: -next(p.get("weight", 1) for p in todo if p["name"] == j[0]))
    if jobs > 1 and len(work) > 1:
        with Pool(min(jobs, len(work))) as pool:
            for _ in pool.imap_unordered(run, work):
                pass
    else:
        for j in work:
            run(j)
    man = []
    for p in cat:
        q = {kk: vv for kk, vv in p.items() if kk not in ("build",)}
        q["file"] = p["name"] + ".npz"
        man.append(q)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"BUILD {len(work)} деталей, {time.time() - t:.1f} с")


if __name__ == "__main__":
    main()
