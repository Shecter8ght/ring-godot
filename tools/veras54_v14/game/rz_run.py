# ВЕРАС-54 v14, игровая сетка: задание для RizomUV 2024.1 (встроенный Python, объект App). Запуск:
#   "D:/ПРОГРАММЫ/RizomUV 2024.1/rizomuv.exe" -cfi E:/Games/RING-godot/tools/veras54_v14/game/rz_run.py
# Задание — _asset_src/veras54_v14/game/rizom/job.json: {"tasks": [{"mode": "pack" | "unwrap", "in": ..., "out": ...,
# "size": 4096, "padding_px": 12}]}. Пути латиницей (кириллицу RizomUV не открывает).
#   pack   — только укладка: масштаб островов не меняется (Scaling OFF), повороты по 90°, без масштаба после укладки;
#            чтобы отступ в пикселях вышел точным, острова заранее приводятся к размеру квадрата, укладка повторяется
#            с поправкой масштаба (до 3 раз), берётся лучшая, у которой отступ после вписывания не меньше заданного.
#   unwrap — швы RizomUV (острые рёбра, трубы, ручки, ограничение растяжения), Unfold + Optimize, без укладки.
# Лог — rizom/rz_log.txt. RizomUV перезапускает этот файл при каждом его изменении — поэтому в конце App.Quit.
import json
import math
import time
import traceback

RZ = "E:/Games/RING-godot/_asset_src/veras54_v14/game/rizom"
LOG = open(RZ + "/rz_log.txt", "a", encoding="utf-8")


def log(*a):
    LOG.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    LOG.flush()


def check(name, r):
    log("    ok", name)
    if isinstance(r, dict) and "Error" in r:
        raise RuntimeError(f"{name}: {r['Error']}")
    return r


def read_vt(path):
    vt = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            if ln.startswith("vt "):
                p = ln.split()
                vt.append((float(p[1]), float(p[2])))
    return vt


def scaled_copy(src, dst, c):
    """Копия OBJ с UV × c (острова к размеру квадрата)."""
    with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8", newline="\n") as g:
        for ln in f:
            if ln.startswith("vt "):
                p = ln.split()
                g.write(f"vt {float(p[1]) * c:.9f} {float(p[2]) * c:.9f}\n")
            else:
                g.write(ln)


def island_area(path):
    """Сумма площадей граней в UV (острова не перекрываются — это их площадь)."""
    vt, area = [], 0.0
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.startswith("vt "):
                p = ln.split()
                vt.append((float(p[1]), float(p[2])))
            elif ln.startswith("f "):
                q = [vt[int(t.split("/")[1]) - 1] for t in ln.split()[1:]]
                for k in range(1, len(q) - 1):
                    area += abs((q[k][0] - q[0][0]) * (q[k + 1][1] - q[0][1]) - (q[k + 1][0] - q[0][0]) * (q[k][1] - q[0][1])) / 2
    return area


def pack_once(path_in, path_out, pad, size, mutations):
    check("Load", App.Load({"File": {"Path": path_in, "XYZUVW": True, "AutoWeld": False}, "NormalizeUVW": False}))
    n_isl = len(App.ItemNames("Lib.Mesh.Islands"))
    t0 = time.time()
    r = check("Pack", App.Pack({"ProcessTileSelection": False, "RecursionDepth": 1, "RootGroup": "RootGroup",
                                "Scaling": {"Mode": 0}, "Rotate": {"Step": 90}, "Translate": True,
                                "LayoutScalingMode": 2, "PaddingSize": pad, "MarginSize": 0.0,
                                "Resolution": size, "MaxMutations": mutations}))
    check("Save", App.Save({"File": {"Path": path_out, "UVWProps": False}}))
    vt = read_vt(path_out)
    us, vs = [p[0] for p in vt], [p[1] for p in vt]
    ext = max(max(us) - min(us), max(vs) - min(vs))
    return n_isl, ext, island_area(path_out), time.time() - t0


def task_pack(t):
    """Масштаб после укладки (Best fit) меняет и отступ: отступ на входе подбирается так, чтобы после вписывания
    в квадрат (как fit_square в rz_game.py) вышло не меньше padding_px."""
    size, px = t["size"], t.get("padding_px", 12)
    src, out = RZ + "/" + t["in"], RZ + "/" + t["out"]
    tmp = src.replace("_in.obj", "_scaled.obj")
    a0 = island_area(src)
    r1 = (px + 1) // 2 + 1
    inner = 1.0 - 2.0 * r1 / size
    c = math.sqrt(t.get("fill_guess", 0.62) / a0)
    scaled_copy(src, tmp, c)
    a_in = a0 * c * c
    pad = px / size
    best = None
    for it in range(t.get("iters", 3)):
        name = out.replace(".obj", f"_try{it}.obj")
        n, ext, a_out, sec = pack_once(tmp, name, pad, size, t.get("mutations", 3))
        s_tot = math.sqrt(a_out / a_in) * inner / ext
        pad_final = pad * s_tot * size
        fill = a_out * (inner / ext) ** 2
        log(f"  pack {t['in']} попытка {it}: островов {n}, отступ на входе {pad * size:.2f} px, масштаб {s_tot:.4f}, "
            f"отступ после вписывания {pad_final:.2f} px, заполнение {fill:.4f}, {sec:.0f} с")
        if pad_final >= px * 0.999 and (best is None or fill > best[0]):
            best = (fill, it)
        pad = pad * px / pad_final * 1.004
    if best is None:
        raise RuntimeError("ни одна укладка не дала нужного отступа")
    import shutil
    shutil.copyfile(out.replace(".obj", f"_try{best[1]}.obj"), out)
    log(f"PACK {t['in']} → {t['out']}: лучшая попытка {best[1]}, заполнение (по UV RizomUV) {best[0]:.4f}")


def task_unwrap(t):
    src, out = RZ + "/" + t["in"], RZ + "/" + t["out"]
    t0 = time.time()
    check("Load", App.Load({"File": {"Path": src, "XYZ": True, "AutoWeld": False}, "NormalizeUVW": True}))
    auto = {"SharpEdges": {"AngleMin": t.get("sharp", 60.0)}, "HandleCutter": True, "PipesCutter": True,
            "StretchLimiter": True, "Quality": t.get("quality", 0.5), "FlatteningMode": 0,
            "FlatteningUnfoldParams": {"BorderIntersections": True, "TriangleFlips": True}}
    if t.get("reweld", True):
        auto["ReWeld"] = {"Threshold": 0.2, "PolyMax": 4000, "LenghtMax": t.get("reweld_len", 30.0)}
    check("Select", App.Select({"PrimType": "Edge", "Select": True, "ResetBefore": True, "WorkingSet": "Visible",
                                "Auto": auto}))
    check("Cut", App.Cut({"PrimType": "Edge", "WorkingSet": "Visible"}))
    u = check("Unfold", App.Unfold({"PrimType": "Edge", "WorkingSet": "Visible", "MinAngle": 1e-5, "Mix": 1,
                                    "Iterations": 1, "RoomSpace": 0, "BorderIntersections": True, "TriangleFlips": True}))
    failed = u.get("BijectionFailedIslandIDs") if isinstance(u, dict) else None
    log(f"  unwrap {t['in']}: Unfold, островов {len(App.ItemNames('Lib.Mesh.Islands'))}, без наложений не вышло "
        f"{len(failed) if failed else 0}, {time.time() - t0:.0f} с")
    check("Save", App.Save({"File": {"Path": out.replace(".obj", "_unfold.obj"), "UVWProps": False}}))
    if t.get("optimize", True) and not failed:
        check("Optimize", App.Optimize({"PrimType": "Edge", "WorkingSet": "Visible", "MinAngle": 1e-5, "Mix": 1,
                                        "AngleDistanceMix": 1, "Iterations": 1, "RoomSpace": 0,
                                        "BorderIntersections": True, "TriangleFlips": True,
                                        "ProcessAllIfNoneSelected": True}))
    check("Save", App.Save({"File": {"Path": out, "UVWProps": False}}))
    log(f"UNWRAP {t['in']} → {t['out']}: островов {len(App.ItemNames('Lib.Mesh.Islands'))}, {time.time() - t0:.0f} с")


try:
    job = json.load(open(RZ + "/job.json", encoding="utf-8"))
    log("JOB", [t["in"] for t in job["tasks"]])
    for t in job["tasks"]:
        try:
            (task_pack if t["mode"] == "pack" else task_unwrap)(t)
        except Exception:
            log("ERROR", t["in"], traceback.format_exc())
    log("END")
except Exception:
    log("FATAL", traceback.format_exc())
LOG.close()
App.Quit({})
