"""Отдельная сессия и очередь Painter для замка; чужие проекты не переключаются."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
JOBS=ROOT/"_asset_src"/"padlock_v01"/"sp_jobs"
EXE=Path("D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/Adobe Substance 3D Painter.exe")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--timeout",type=float,default=45)
    parser.add_argument("--revision",choices=['v02','v03','v04'],default='v02')
    parser.add_argument("--wait-for",default=None)
    args=parser.parse_args()
    JOBS.mkdir(parents=True,exist_ok=True)
    if args.command=="launch":
        target=JOBS/"_bridge_ready.txt"
        target.unlink(missing_ok=True)
        env=dict(os.environ)
        env["SUBSTANCE_PAINTER_PLUGINS_PATH"]=str(ROOT/"tools"/"vss_m_v8"/"sp_bridge")
        env["SP_BRIDGE_DIR"]=str(JOBS)
        env["OCIO"]=str(EXE.parent/"resources"/"ocio"/"substance"/"config.ocio")
        # Keep this task's disposable cache off the almost-full system disk.
        cache=JOBS.parent/"tmp"
        cache.mkdir(exist_ok=True)
        env["TEMP"]=str(cache)
        env["TMP"]=str(cache)
        startup=subprocess.STARTUPINFO()
        startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow=0
        proc=subprocess.Popen([str(EXE)],env=env,startupinfo=startup)
        (JOBS/"session.json").write_text(json.dumps({"pid":proc.pid,"executable":str(EXE),"started":time.time()},indent=2),encoding="utf-8")
        print("PAINTER_STARTED",proc.pid,flush=True)
    else:
        source=Path(args.command)
        stamp=str(time.time_ns())+"_"+source.stem
        temporary=JOBS/(stamp+".tmp")
        header="import sys\nPADLOCK_REVISION="+repr(args.revision)+"\n_p=r'E:/Games/RING-godot/tools/vss_m_v8'\nif _p not in sys.path: sys.path.insert(0,_p)\n"
        temporary.write_text(header+source.read_text(encoding="utf-8"),encoding="utf-8")
        temporary.rename(JOBS/(stamp+".py"))
        target=JOBS/(stamp+".out")
    deadline=time.monotonic()+args.timeout
    while not target.exists():
        if time.monotonic()>deadline:raise SystemExit("NO_RESPONSE "+str(target))
        time.sleep(.3)
    result=target.read_text(encoding="utf-8")
    print(result)
    if result.startswith("ERROR"):raise SystemExit(1)
    if args.wait_for:
        if Path(args.wait_for).name!=args.wait_for:raise ValueError('Marker must be a task-local filename')
        marker=JOBS/args.wait_for
        while not marker.exists():
            if time.monotonic()>deadline:raise SystemExit('COMPLETION_PENDING '+str(marker))
            time.sleep(.3)
        result=marker.read_text(encoding='utf-8');print(result)
        if result.startswith('ERROR'):raise SystemExit(1)


if __name__=="__main__":main()
