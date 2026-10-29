# AR-15 «ГРАНЬ-15»: развёртка в RizomUV (встроенный Python RizomUV, объект App). Запуск:
#   rizomuv.exe -cfi E:/Games/RING-godot/tools/ar15/rz_unwrap.py
# Задание — <WORK>/rz/job.json: {"sets": [...], "res": {набор: разрешение}, "seams": {...}}; на каждый набор
# <набор>_in.obj (tex_uv.py export) → швы → развёртка → выпрямление → упаковка в квадрат 0–1 → <набор>_out.obj.
# Итог и замеры — <WORK>/rz/rz_log.txt. RizomUV не открывает пути с кириллицей — рабочая папка латиницей.
# RizomUV перезапускает этот файл при каждом его изменении — поэтому в конце App.Quit.
import json
import time
import traceback

RZ = "E:/Games/RING-godot/_asset_src/ar15/tex/rz"
LOG = open(RZ + "/rz_log.txt", "a", encoding="utf-8")


def log(*a):
    LOG.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    LOG.flush()


def check(name, r):
    log("  ok", name)
    if isinstance(r, dict) and "Error" in r:
        raise RuntimeError(f"{name}: {r['Error']}")
    return r


def unwrap(s, res, cfg):
    t0 = time.time()
    check("Load", App.Load({"File": {"Path": f"{RZ}/{s}_in.obj", "XYZ": True, "AutoWeld": False}, "NormalizeUVW": True}))
    # швы: «мозаика» (плоские и цилиндрические участки — по своему острову), сквозные отверстия и ручки — разрезать,
    # растяжение — ограничить (добавляет разрезы, где остров не развернуть ровно)
    auto = {"QuasiDevelopable": {"Developability": cfg.get("dev", 0.5), "IslandPolyNBMin": cfg.get("polymin", 6),
                                 "AreaMinRatio": cfg.get("areamin", 0.03), "FitCones": True, "Straighten": True},
            "HandleCutter": True, "PipesCutter": True,
            "StretchLimiter": True, "Quality": cfg.get("quality", 0.4), "FlatteningMode": 0,
            "FlatteningUnfoldParams": {"BorderIntersections": True, "TriangleFlips": True}}
    if cfg.get("sharp"):
        auto["SharpEdges"] = {"AngleMin": cfg["sharp"]}
    if cfg.get("reweld"):
        # мелкие острова мозаики приварить обратно к соседям, если наложений не будет (длина — в мм модели)
        auto["ReWeld"] = {"Threshold": cfg.get("reweld_thr", 0.2), "PolyMax": cfg.get("reweld_poly", 2000),
                          "LenghtMax": cfg.get("reweld_len", 40.0)}
    check("Select", App.Select({"PrimType": "Edge", "Select": True, "ResetBefore": True, "WorkingSet": "Visible",
                                "Auto": auto}))
    # диагонали внутри многоугольников исходной сетки не режем: обратно UV ложатся на целую грань
    diag = json.load(open(f"{RZ}/{s}_in_map.json", encoding="utf-8"))["diag"]
    if diag:
        check("Deselect diag", App.Select({"PrimType": "Edge", "DeSelect": True, "List": True,
                                           "EdgesAsPolyEdgeIDs": True, "IDs": diag}))
    check("Cut", App.Cut({"PrimType": "Edge", "WorkingSet": "Visible"}))
    u = check("Unfold", App.Unfold({"PrimType": "Edge", "WorkingSet": "Visible", "MinAngle": 1e-5, "Mix": 1,
                                    "Iterations": 1, "RoomSpace": 0, "BorderIntersections": True,
                                    "TriangleFlips": True}))
    if isinstance(u, dict) and u.get("BijectionFailedIslandIDs"):
        log(f"  {s}: не развернулись без наложений острова {len(u['BijectionFailedIslandIDs'])}")
    # Optimize падал (RizomUV 2024.1 закрывался молча) на острове, не развернувшемся без наложений, — по заданию
    if cfg.get("optimize"):
        check("Optimize", App.Optimize({"PrimType": "Edge", "WorkingSet": "Visible", "MinAngle": 1e-5, "Mix": 1,
                                        "AngleDistanceMix": 1, "Iterations": 1, "RoomSpace": 0,
                                        "BorderIntersections": True, "TriangleFlips": True,
                                        "ProcessAllIfNoneSelected": True}))
    n_isl = len(App.ItemNames("Lib.Mesh.Islands"))
    pad = cfg.get("padding_px", 12) / res
    mar = cfg.get("margin_px", 8) / res
    r = check("Pack", App.Pack({"ProcessTileSelection": False, "RecursionDepth": 1, "RootGroup": "RootGroup",
                                "Scaling": {"Mode": 2}, "Rotate": {"Step": 90}, "Translate": True,
                                "LayoutScalingMode": 2, "PaddingSize": pad, "MarginSize": mar,
                                "Resolution": cfg.get("pack_res", 1000), "MaxMutations": cfg.get("mutations", 2)}))
    cov = r.get("Coverages") if isinstance(r, dict) else r
    check("Save", App.Save({"File": {"Path": f"{RZ}/{s}_out.obj", "UVWProps": False}}))
    log(f"SET {s} res {res} islands {n_isl} coverage {cov} time {time.time() - t0:.0f}s")


try:
    job = json.load(open(RZ + "/job.json", encoding="utf-8"))
    log("JOB", job.get("sets"))
    for s in job["sets"]:
        try:
            unwrap(s, job["res"][s], dict(job.get("seams", {}), **job.get("per_set", {}).get(s, {})))
        except Exception:
            log("ERROR", s, traceback.format_exc())
    log("END")
except Exception:
    log("FATAL", traceback.format_exc())
LOG.close()
App.Quit({})
