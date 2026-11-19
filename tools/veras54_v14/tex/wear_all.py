"""ВЕРАС-54 v14, износ на проектах Painter по очереди (по образцу tools/pkp/wear_all.py): копия принятого проекта
VERAS_<проект>_v1.spp → VERAS_<проект>_wear_v<ver>.spp (если копии ещё нет; принятый файл только читается), открыть
копию, собрать группу «Этап 2 — износ» (sp_veras_wear.build с силой k), выгрузить карты в разрешении набора — по одному
набору (однотонная выгрузка — не хватило видеопамяти — повторяется).
Рабочее разрешение — родное разрешение набора (tex_sets.SETS, до 4K). Износ v01 работал в 2K и выгружался растянутым до
4K — главная причина «мыла» (диагноз 2026-11-19, второй проход); work=2048 — прежний режим, только если 4K не помещается
в видеопамять.
Painter уже запущен своим экземпляром:
    set FINISH_SP_JOBS=E:/Games/RING-godot/_asset_src/veras54_v14/tex/sp_jobs, TEMP=TMP=E:\\RING_tmp_painter,
    VK_LOADER_LAYERS_DISABLE=~implicit~, DISABLE_RTSS_LAYER=1;  python -X utf8 tools/asset_kit/finish/sp_run.py start

    python -X utf8 tools/veras54_v14/tex/wear_all.py <папка карт> body,front,rear [k=1.0] [kg=rust:0.5,edge:1.2] [fresh]
                                                     [ver=2] [work=2048] [only=cover,receiver] [factory=<папка>]
      fresh — копию заново с принятого проекта (иначе берётся существующая копия: в ней может быть кисть владельца)
      factory=<папка> — сначала заводская группа заново по finish-spec.json (W.restack_factory) и её карты в <папку>
      (износ и группа кисти при этом стираются и собираются заново)
      only — только эти наборы (пробы)
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = "E:/Games/RING-godot"
J = ROOT + "/_asset_src/veras54_v14/tex/sp_jobs"
SP = ROOT + "/_asset_src/veras54_v14/tex/sp"
ENV = dict(os.environ, FINISH_SP_JOBS=J)
PRE = ""


def pre(ver):
    return ("import os, sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/veras54_v14/tex')\n"
            f"os.environ['VERAS_WEAR_VER'] = '{ver}'\n"
            "import importlib, sp_veras, sp_veras_wear as W; importlib.reload(sp_veras); importlib.reload(W)\n")


def run(code, t=120):
    r = subprocess.run(["python", "-X", "utf8", "tools/asset_kit/finish/sp_run.py", "-c", code, str(t)], env=ENV,
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    out = (r.stdout + r.stderr).strip()
    if "ERROR" in out[:20] or "Traceback" in out:
        raise SystemExit(out)
    return out


def wait(marker, t=1800):
    p = os.path.join(J, marker)
    t0 = time.time()
    while not os.path.exists(p):
        time.sleep(3)
        if time.time() - t0 > t:
            raise SystemExit("нет метки " + marker)
    time.sleep(2)
    s = open(p, encoding="utf-8").read()
    if s.startswith("ERROR"):
        raise SystemExit(s)
    return s


def rm(m):
    p = os.path.join(J, m)
    if os.path.exists(p):
        os.remove(p)


def main():
    global PRE
    out = os.path.abspath(sys.argv[1]).replace("\\", "/")     # Painter относительный путь выгрузки теряет
    projs = sys.argv[2].split(",")
    k, kg, fresh, factory, ver, work, only = 1.0, {}, False, None, 2, None, None
    for a in sys.argv[3:]:
        if a.startswith("k="):
            k = float(a[2:])
        elif a.startswith("kg="):
            kg = {x.split(":")[0]: float(x.split(":")[1]) for x in a[3:].split(",") if x}
        elif a.startswith("factory="):
            factory = os.path.abspath(a[8:]).replace("\\", "/")
        elif a == "fresh":
            fresh = True
        elif a.startswith("ver="):
            ver = int(a[4:])
        elif a.startswith("work="):
            work = int(a[5:])
        elif a.startswith("only="):
            only = a[5:].split(",")
    PRE = pre(ver)
    for proj in projs:
        print("==", proj, flush=True)
        src, dst = f"{SP}/VERAS_{proj}_v1.spp", f"{SP}/VERAS_{proj}_wear_v{ver}.spp"
        if fresh or not os.path.exists(dst):
            shutil.copyfile(src, dst)
            print("копия", dst, flush=True)
        rm("_project_ready.txt")
        print(run(PRE + f"print(W.open_wear('{proj}'))", 300), flush=True)
        print(wait("_project_ready.txt", 900), flush=True)
        # рабочее разрешение: родное разрешение набора (или work=… — не больше)
        print(run("import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/veras54_v14/tex')\n"
                  "import substance_painter.textureset as TS, tex_sets as T\n"
                  "for t in TS.all_texture_sets():\n"
                  f"    r = min(T.SETS[t.name()][0], T.WORK_RES, {work or 1 << 20})\n"
                  "    if t.get_resolution().width != r: t.set_resolution(TS.Resolution(r, r))\n"
                  "print([(t.name(), t.get_resolution().width) for t in TS.all_texture_sets()])", 900), flush=True)
        if factory:
            rm("_stack_done.txt")
            print(run(PRE + "print(W.restack_factory())", 1800), flush=True)
            print(wait("_stack_done.txt", 3600), flush=True)
            export_checked(factory, proj, only=only)
        rm("_wear_done.txt")
        print(run(PRE + f"print(W.build(only={only!r}, k={k}, kg={kg!r}))", 1800), flush=True)
        print(wait("_wear_done.txt", 3600), flush=True)
        export_checked(out, proj, only=only)
    print("ALL DONE", flush=True)


def flat(out, s):
    """Выгрузка набора однотонная (у «Частокола» и здесь 19.11 — при нехватке видеопамяти Painter выгружал ровный цвет)."""
    import numpy as np
    from PIL import Image
    p = f"{out}/{s}_baseColor.png"
    if not os.path.exists(p):
        return True
    a = np.asarray(Image.open(p).convert("RGB").reduce(8), np.float32)
    return float(a.reshape(-1, 3).std(0).max()) < 2.0


def export_checked(out, proj, tries=3, only=None):
    """Выгрузка по одному набору (меньше видеопамяти за раз), затем однотонные наборы — заново по одному."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tex_sets as T
    sets = [s for s in T.PROJECTS[proj] if not only or s in only]
    for s in sets:
        rm("_export_done.txt")
        print(run(PRE + f"print(W.export(r'{out}', only=['{s}']))", 120), flush=True)
        print(wait("_export_done.txt", 3600), flush=True)
    bad = []
    for _ in range(tries):
        bad = [s for s in sets if flat(out, s)]
        if not bad:
            return
        for s in bad:
            print("однотонная выгрузка — заново:", s, flush=True)
            rm("_export_done.txt")
            print(run(PRE + f"print(W.export(r'{out}', only=['{s}']))", 120), flush=True)
            print(wait("_export_done.txt", 3600), flush=True)
    raise SystemExit("однотонная выгрузка: " + ", ".join(bad))


if __name__ == "__main__":
    main()
