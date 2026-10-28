# Мост для управления Substance 3D Designer скриптами (близнец моста Painter tools/vss_m_v8/sp_bridge):
# плагин читает задания *.py из папки SD_BRIDGE_DIR и выполняет их в главном потоке Designer; вывод и ошибки —
# в одноимённый *.out, задание переименовывается в *.done. Подключается без правки настроек пользователя:
# SBS_DESIGNER_PYTHON_PATH=<папка tools/sd_bridge> при запуске (Designer ищет там папки плагинов).
# В задании уже есть sd, ctx (SDContext), app (SDApplication), pkg_mgr (SDPackageMgr).
import contextlib
import io
import os
import time
import traceback

import sd
from PySide6 import QtCore

_TIMER = None
_GLOBALS = {}
_STARTED = time.time()
_POPUPS = ("Home Screen", "Home screen", "What's new", "What's New", "Welcome")


def _jobs_dir():
    return os.environ.get("SD_BRIDGE_DIR", "")


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _dismiss_popups():
    """Стартовые модальные окна держат главный поток — с ними задания не идут (так было у Painter)."""
    from PySide6 import QtWidgets
    qt_app = QtWidgets.QApplication.instance()
    if qt_app is None:
        return
    for w in qt_app.topLevelWidgets():
        try:
            if w.isVisible() and w.isModal() and w.windowTitle() in _POPUPS:
                w.close()
        except RuntimeError:
            continue


def _poll():
    if time.time() - _STARTED < 120.0:
        _dismiss_popups()
    d = _jobs_dir()
    if not d or not os.path.isdir(d):
        return
    for name in sorted(os.listdir(d)):
        if not name.endswith(".py"):
            continue
        job = os.path.join(d, name)
        try:
            # файл может ещё дописываться — берём только «остывшие»
            if time.time() - os.path.getmtime(job) < 1.0:
                continue
            with open(job, encoding="utf-8") as f:
                code = f.read()
        except OSError:
            continue
        os.replace(job, job + ".done")
        buf = io.StringIO()
        t0 = time.time()
        status = "OK"
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(compile(code, job, "exec"), _GLOBALS)
        except Exception:
            status = "ERROR"
            buf.write(traceback.format_exc())
        _write(job[:-3] + ".out", f"{status} {time.time() - t0:.2f}s\n" + buf.getvalue())
        break                              # одно задание за тик: Designer успевает обработать события


def initializeSDPlugin():
    global _TIMER
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    _GLOBALS.clear()
    _GLOBALS.update({"__name__": "claude_sd_bridge_job", "sd": sd, "ctx": ctx, "app": app,
                     "pkg_mgr": app.getPackageMgr()})
    _TIMER = QtCore.QTimer()
    _TIMER.setInterval(500)
    _TIMER.timeout.connect(_poll)
    _TIMER.start()
    d = _jobs_dir()
    if d and os.path.isdir(d):
        _write(os.path.join(d, "_bridge_ready.txt"), time.strftime("%Y-%m-%d %H:%M:%S"))


def uninitializeSDPlugin():
    global _TIMER
    if _TIMER is not None:
        _TIMER.stop()
        _TIMER = None
