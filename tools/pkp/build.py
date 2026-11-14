# ПКП: расчёт деталей (обычный Python, см. sdf.py).
#   python -X utf8 tools/pkp/build.py <папка вывода> [деталь | модуль …] [--k 2.0] [--jobs 8]
# --k — множитель вокселя (2 — черновик в восемь раз быстрее). Деталь-поле считается кусками вдоль X параллельно:
# каждый работник сам собирает список операций детали и считает свой кусок. Пишет <деталь>__NN.npz (поля),
# <деталь>.npz (готовые сетки) и manifest.json для assemble.py. Без имён — все детали. Если названы только модули
# (receiver, box …), читаются только они; записи остальных деталей в manifest.json сохраняются.
import importlib
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MODULES = ("part_receiver", "part_cover", "part_feed", "part_barrel", "part_stock", "part_grip", "part_trigger",
           "part_sights", "part_bolt", "part_bipod", "part_box", "part_ammo")


def catalog(only=None):
    """Каталог деталей. only — имена модулей: тогда читаются только они (чужой недописанный модуль не мешает);
    иначе все модули, а тот, что не читается, пропускается с предупреждением."""
    out = []
    for m in MODULES:
        if only and m not in only:
            continue
        if not os.path.exists(os.path.join(HERE, m + ".py")):
            continue
        try:
            mod = importlib.import_module(m)
            plist = mod.parts()
        except Exception as e:  # noqa: BLE001
            if only:
                raise
            print(f"SKIP_MODULE {m}: {type(e).__name__}: {e}", flush=True)
            continue
        for p in plist:
            p["module"] = m
            out.append(p)
    return out


_cache = {}


def _built(module, name, k):
    key = (module, name, k)
    if key not in _cache:
        mod = importlib.import_module(module)
        p = next(q for q in mod.parts() if q["name"] == name)
        _cache.clear()
        _cache[key] = p["build"](p.get("h", 0.15) * k)
    return _cache[key]


def run(job):
    kind, module, name, out_dir, k, idx, c0, c1 = job
    t = time.time()
    res = _built(module, name, k)
    if kind == "mesh":
        import numpy as np
        path = os.path.join(out_dir, name + ".npz")
        mod = importlib.import_module(module)
        unit = next(q for q in mod.parts() if q["name"] == name).get("unit", 1.0)
        if unit != 1.0:
            res = (res[0] * unit,) + tuple(res[1:])
        if len(res) > 2:
            np.savez_compressed(path, v=res[0], f=res[1], m=res[2])
        else:
            np.savez_compressed(path, v=res[0], f=res[1])
        return name, "mesh", len(res[1]), time.time() - t
    vol = res.save_chunk(os.path.join(out_dir, f"{name}__{idx:02d}.npz"), c0, c1)
    return name, "chunk", vol, time.time() - t


def main():
    args = sys.argv[1:]
    out_dir = os.path.abspath(args[0])
    k = 1.0; jobs = 8; names = []
    i = 1
    while i < len(args):
        if args[i] == "--k":
            k = float(args[i + 1]); i += 2
        elif args[i] == "--jobs":
            jobs = int(args[i + 1]); i += 2
        else:
            names.append(args[i]); i += 1
    os.makedirs(out_dir, exist_ok=True)
    mods = ["part_" + n for n in names if os.path.exists(os.path.join(HERE, "part_" + n + ".py"))]
    cat = catalog(mods if names and len(mods) == len(names) else None)
    todo = [p for p in cat if not names or p["name"] in names or p["module"].replace("part_", "") in names]
    t = time.time()
    work = []; nchunks = {}
    for p in todo:
        res = p["build"](p.get("h", 0.15) * k)
        if isinstance(res, tuple):
            work.append(("mesh", p["module"], p["name"], out_dir, k, 0, 0, 0))
            continue
        # прежние куски детали убрать: число кусков могло измениться
        for f in os.listdir(out_dir):
            if f.startswith(p["name"] + "__") and f.endswith(".npz"):
                os.remove(os.path.join(out_dir, f))
        ch = res.chunks()
        nchunks[p["name"]] = (len(ch), tuple(int(v) for v in res.n), res.h)
        for idx, (c0, c1) in enumerate(ch):
            work.append(("chunk", p["module"], p["name"], out_dir, k, idx, c0, c1))
    vols = {}; secs = {}
    if jobs > 1 and len(work) > 1:
        with Pool(min(jobs, len(work))) as pool:
            for name, kind, val, dt in pool.imap_unordered(run, work):
                vols[name] = vols.get(name, 0.0) + (val if kind == "chunk" else 0.0)
                secs[name] = secs.get(name, 0.0) + dt
    else:
        for j in work:
            name, kind, val, dt = run(j)
            vols[name] = vols.get(name, 0.0) + (val if kind == "chunk" else 0.0)
            secs[name] = secs.get(name, 0.0) + dt
    for p in todo:
        n = p["name"]
        if n in nchunks:
            print(f"FIELD {n}: {nchunks[n][1]} вокселей по {nchunks[n][2]:g} мм, кусков {nchunks[n][0]}, "
                  f"объём {vols.get(n, 0) / 1000:.2f} см3, {secs.get(n, 0):.1f} с работы", flush=True)
        else:
            print(f"MESH {n}: {secs.get(n, 0):.1f} с", flush=True)
    # манифест: прежние записи о числе кусков сохраняются, пересчитанные обновляются
    mpath = os.path.join(out_dir, "manifest.json")
    old = {}
    if os.path.exists(mpath):
        old = {q["name"]: q for q in json.load(open(mpath, encoding="utf-8"))}
    # записи деталей из модулей, которые в этот раз не читались, остаются как были
    man = dict(old)
    for p in cat:
        q = {kk: vv for kk, vv in p.items() if kk not in ("build",)}
        if p["name"] in nchunks:
            q["chunks"] = nchunks[p["name"]][0]
        elif p["name"] in old and "chunks" in old[p["name"]]:
            q["chunks"] = old[p["name"]]["chunks"]
        man[p["name"]] = q
    man = list(man.values())
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"BUILD {len(todo)} деталей, {len(work)} заданий, {time.time() - t:.1f} с")


if __name__ == "__main__":
    main()
