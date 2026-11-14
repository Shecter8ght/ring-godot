"""«Частокол», износ на проектах Painter по очереди: открыть проект, рабочее разрешение наборов 2K (в 4K стек износа
выедал видеопамять — выгрузка выходила ровной), собрать группу «Этап 2 — износ» (sp_pkp_wear.build), выгрузить карты.
Painter уже запущен (sp_run.py start; TEMP / TMP — на E:, на C: мало места).

    python -X utf8 tools/pkp/wear_all.py <папка карт> body,front,box
"""
import os, subprocess, sys, time
ROOT = "E:/Games/RING-godot"
J = ROOT + "/_asset_src/pkp/tex/sp_jobs"
ENV = dict(os.environ, FINISH_SP_JOBS=J)
OUT = sys.argv[1]
PROJ = sys.argv[2].split(",")

def run(code, t=120):
    r = subprocess.run(["python", "-X", "utf8", "tools/asset_kit/finish/sp_run.py", "-c", code, str(t)], env=ENV,
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    return (r.stdout + r.stderr).strip()

def wait(marker, t=1800):
    p = os.path.join(J, marker)
    t0 = time.time()
    while not os.path.exists(p):
        time.sleep(3)
        if time.time() - t0 > t:
            raise SystemExit("нет метки " + marker)
    time.sleep(2)
    return open(p, encoding="utf-8").read()

def rm(m):
    p = os.path.join(J, m)
    if os.path.exists(p):
        os.remove(p)

PRE = "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/pkp'); import importlib, sp_pkp, sp_pkp_wear as W; importlib.reload(sp_pkp); importlib.reload(W)\n"
for proj in PROJ:
    print("==", proj, flush=True)
    rm("_project_ready.txt")
    print(run(PRE + f"print(sp_pkp.open_project('{proj}'))"), flush=True)
    wait("_project_ready.txt", 900)
    print(run("import substance_painter.textureset as TS\n"
              "for t in TS.all_texture_sets():\n"
              "    if t.get_resolution().width != 2048: t.set_resolution(TS.Resolution(2048, 2048))\n"
              "print([(t.name(), t.get_resolution().width) for t in TS.all_texture_sets()])", 600), flush=True)
    rm("_wear_done.txt")
    print(run(PRE + "print(W.build())", 900), flush=True)
    print(wait("_wear_done.txt"), flush=True)
    rm("_export_done.txt")
    print(run(PRE + f"print(sp_pkp.export(r'{OUT}'))", 60), flush=True)
    print(wait("_export_done.txt", 3600), flush=True)
print("ALL DONE", flush=True)
