# Мост для управления Substance 3D Painter скриптами: плагин читает задания *.py из папки SP_BRIDGE_DIR
# и выполняет их в главном потоке Painter; вывод и ошибки — в одноимённый *.out, задание переименовывается в *.done.
# Подключается без правки настроек пользователя: SUBSTANCE_PAINTER_PLUGINS_PATH=<папка sp_bridge> при запуске.
import contextlib
import io
import os
import time
import traceback

from PySide6 import QtCore

_TIMER = None
_GLOBALS = {}


def _jobs_dir():
    return os.environ.get("SP_BRIDGE_DIR", "")


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


_STARTED = time.time()


def _poll():
    if time.time() - _STARTED < 120.0:            # только стартовые окна: перебор окон во время работы проекта рискован
        _dismiss_popups()
    d = _jobs_dir()
    if not d or not os.path.isdir(d):
        return
    for name in sorted(os.listdir(d)):
        if not name.endswith(".py"):
            continue
        job = os.path.join(d, name)
        try:
            # файл может ещё дописываться (перенаправление вывода в оболочке) — берём только «остывшие»
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
        break                              # одно задание за тик: Painter успевает обработать события


_POPUPS = ("Home screen", "What's new")


def _dismiss_popups():
    """Стартовые окна Painter («Home screen» после перезагрузки, «What's new») модальные — с ними задания не идут
    (2026-10-26 цепочка встала на создании проекта); закрываем их сами."""
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        try:
            if w.isVisible() and w.windowTitle() in _POPUPS:
                w.close()
        except RuntimeError:
            continue


def start_plugin():
    global _TIMER
    _GLOBALS.clear()
    _GLOBALS["__name__"] = "claude_bridge_job"
    _TIMER = QtCore.QTimer()
    _TIMER.setInterval(500)
    _TIMER.timeout.connect(_poll)
    _TIMER.start()
    d = _jobs_dir()
    if d and os.path.isdir(d):
        _write(os.path.join(d, "_bridge_ready.txt"), time.strftime("%Y-%m-%d %H:%M:%S"))


def close_plugin():
    global _TIMER
    if _TIMER is not None:
        _TIMER.stop()
        _TIMER = None
