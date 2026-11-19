"""ВЕРАС-54 v14, износ на проектах Painter по очереди (по образцу tools/pkp/wear_all.py): копия принятого проекта
VERAS_<проект>_v1.spp → VERAS_<проект>_wear_v1.spp (если копии ещё нет; принятый файл только читается), открыть копию,
рабочее разрешение наборов 2K (в 4K стек износа у «Частокола» выедал видеопамять — выгрузка выходила ровной),
собрать группу «Этап 2 — износ» (sp_veras_wear.build с силой k), выгрузить карты в разрешении набора.
Painter уже запущен своим экземпляром:
    set FINISH_SP_JOBS=E:/Games/RING-godot/_asset_src/veras54_v14/tex/sp_jobs, TEMP=TMP=E:\\RING_tmp_painter,
    VK_LOADER_LAYERS_DISABLE=~implicit~, DISABLE_RTSS_LAYER=1;  python -X utf8 tools/asset_kit/finish/sp_run.py start

    python -X utf8 tools/veras54_v14/tex/wear_all.py <папка карт> body,front,rear [k=1.0] [kg=rust:0.5,edge:1.2] [fresh]
      fresh — копию заново с принятого проекта (иначе берётся существующая копия: в ней может быть кисть владельца)
      factory=<папка> — сначала заводская группа заново по finish-spec.json (W.restack_factory) и её карты в <папку>
      (износ и группа кисти при этом стираются и собираются заново)
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


PRE = ("import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/veras54_v14/tex')\n"
       "import importlib, sp_veras, sp_veras_wear as W; importlib.reload(sp_veras); importlib.reload(W)\n")


def main():
    out = sys.argv[1]
    projs = sys.argv[2].split(",")
    k, kg, fresh, factory = 1.0, {}, False, None
    for a in sys.argv[3:]:
        if a.startswith("k="):
            k = float(a[2:])
        elif a.startswith("kg="):
            kg = {x.split(":")[0]: float(x.split(":")[1]) for x in a[3:].split(",") if x}
        elif a.startswith("factory="):
            factory = a[8:]
        elif a == "fresh":
            fresh = True
    for proj in projs:
        print("==", proj, flush=True)
        src, dst = f"{SP}/VERAS_{proj}_v1.spp", f"{SP}/VERAS_{proj}_wear_v1.spp"
        if fresh or not os.path.exists(dst):
            shutil.copyfile(src, dst)
            print("копия", dst, flush=True)
        rm("_project_ready.txt")
        print(run(PRE + f"print(W.open_wear('{proj}'))", 300), flush=True)
        print(wait("_project_ready.txt", 900), flush=True)
        print(run("import substance_painter.textureset as TS\n"
                  "for t in TS.all_texture_sets():\n"
                  "    if t.get_resolution().width > 2048: t.set_resolution(TS.Resolution(2048, 2048))\n"
                  "print([(t.name(), t.get_resolution().width) for t in TS.all_texture_sets()])", 900), flush=True)
        if factory:
            rm("_stack_done.txt")
            print(run(PRE + "print(W.restack_factory())", 1800), flush=True)
            print(wait("_stack_done.txt", 3600), flush=True)
            export_checked(factory, proj)
        rm("_wear_done.txt")
        print(run(PRE + f"print(W.build(k={k}, kg={kg!r}))", 1800), flush=True)
        print(wait("_wear_done.txt", 3600), flush=True)
        export_checked(out, proj)
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


def export_checked(out, proj, tries=3):
    """Выгрузка проекта, затем однотонные наборы — заново по одному."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tex_sets as T
    rm("_export_done.txt")
    print(run(PRE + f"print(W.export(r'{out}'))", 120), flush=True)
    print(wait("_export_done.txt", 3600), flush=True)
    for _ in range(tries):
        bad = [s for s in T.PROJECTS[proj] if flat(out, s)]
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
