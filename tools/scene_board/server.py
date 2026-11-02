# «Доска сцен» RING (задача владельца 2026-11-02): все сцены, стенды и уровни проекта на одной странице —
# что это, откуда запускают, кто на них ссылается; кнопки «Запустить», «Убрать» (в карантин вне проекта, с отчётом)
# и «Вернуть». Из git файлы уходят только отдельной кнопкой владельца «Убрать из git» (коммит и отправка).
#   python -X utf8 tools/scene_board/server.py [--port 8767] [--repo <папка>] [--quarantine-root E:/] [--no-push] [--lan]
#   → http://localhost:8767/   (запускалка — SCENE_BOARD.cmd в корне проекта)
# Насовсем ничего не удаляется: «Убрать» переносит файлы в E:/RING_карантин_<дата>/Доска_сцен/<запись>/, там же
# запись.json (что откуда куда, какие строки AGENTS.md и меню сняты) и общий отчёт.md за день.
# --lan — страницу видно с телефона в домашней сети, но с чужого адреса можно только смотреть.
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inventory  # noqa: E402


def arg(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


REPO = os.path.abspath(arg("--repo", os.path.join(HERE, "..", "..")))
PORT = int(arg("--port", "8767"))
QROOT = os.path.abspath(arg("--quarantine-root", "E:/"))
NO_PUSH = "--no-push" in sys.argv
LAN = "--lan" in sys.argv
QDIR_NAME = "Доска_сцен"
WORK = os.path.join(tempfile.gettempdir(), "ring_scene_board")
THUMBS = os.path.join(WORK, "thumbs")
LOGS = os.path.join(WORK, "logs")
os.makedirs(THUMBS, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)
NO_WINDOW = 0x08000000

LOCK = threading.Lock()
STATE = {"inv": None, "building": False, "error": ""}
RUNS = {}


# ---------------------------------------------------------------- git и файлы

def git(*args, env=None, check=True, timeout=120, input_bytes=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=REPO, capture_output=True, env=full_env,
                       timeout=timeout, input=input_bytes)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args[:3]), r.stderr.decode("utf-8", "replace").strip()[:600]))
    return r.stdout.decode("utf-8", "replace")


def git_bytes(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def write_bytes(path, data):
    for attempt in range(6):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(1)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def rebuild():
    STATE["building"] = True
    try:
        STATE["inv"] = inventory.build(REPO)
        STATE["error"] = ""
    except Exception as e:  # noqa: BLE001 — показать владельцу, а не уронить сервер
        STATE["error"] = "Не удалось собрать список: %s" % e
    finally:
        STATE["building"] = False
    return STATE["inv"]


def item_by_id(item_id):
    inv = STATE["inv"] or rebuild()
    for it in inv["items"]:
        if it["id"] == item_id:
            return it
    return None


# ---------------------------------------------------------------- правки строк (AGENTS.md, меню)

def split_lines(data):
    text = data.decode("utf-8")
    crlf = "\r\n" in text
    return text.replace("\r\n", "\n").split("\n"), crlf


def join_lines(lines, crlf):
    text = "\n".join(lines)
    return (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")


def remove_lines(data, edit):
    """Снять строки правки: ищем тот же текст около прежнего номера строки."""
    lines, crlf = split_lines(data)
    texts = [x["text"] for x in edit["lines"]]
    n0 = edit["lines"][0]["n"] - 1
    best = None
    for start in range(len(lines) - len(texts) + 1):
        if lines[start:start + len(texts)] == texts:
            if best is None or abs(start - n0) < abs(best - n0):
                best = start
    if best is None:
        return None
    del lines[best:best + len(texts)]
    return join_lines(lines, crlf)


def insert_lines(data, edit):
    """Вернуть строки на место: после той же строки-соседа, иначе по прежнему номеру."""
    lines, crlf = split_lines(data)
    texts = [x["text"] for x in edit["lines"]]
    for start in range(len(lines) - len(texts) + 1):
        if lines[start:start + len(texts)] == texts:
            return join_lines(lines, crlf)  # уже на месте
    n0 = edit["lines"][0]["n"] - 1
    pos = None
    if edit.get("before") is not None:
        cands = [i for i, l in enumerate(lines) if l == edit["before"]]
        if cands:
            pos = min(cands, key=lambda i: abs(i + 1 - n0)) + 1
    if pos is None:
        pos = min(max(n0, 0), len(lines))
    lines[pos:pos] = texts
    return join_lines(lines, crlf)


def plan_edits(it):
    """Какие строки AGENTS.md и главного меню снимаются вместе с пунктом."""
    edits, manual = [], []
    texts = {"AGENTS.md": read_bytes(os.path.join(REPO, "AGENTS.md")).decode("utf-8", "replace")}

    class _R:
        pass
    shim = _R()
    shim.texts = texts
    entries = inventory.parse_agents(shim)
    lines = texts["AGENTS.md"].replace("\r\n", "\n").split("\n")
    name = os.path.basename(it["id"])
    for en in entries:
        mentions = it["id"] in en["scenes"] or name in en["names"]
        if it["type"] == "cmd":
            mentions = any(it["id"] in l or os.path.basename(it["id"]) in l for l in en["text"])
        if not mentions:
            continue
        only_this = all(s == it["id"] for s in en["scenes"]) and all(n == name for n in en["names"])
        if it["type"] == "cmd":
            only_this = False
        if only_this and not en["hash"]:
            first = en["lines"][0]
            edits.append({"file": "AGENTS.md", "lines": [{"n": j + 1, "text": lines[j]} for j in en["lines"]],
                          "before": lines[first - 1] if first > 0 else None})
        else:
            manual.append("AGENTS.md, строка %d — упоминание вместе с другими, поправить вручную" % (en["start"] + 1))
    if it.get("menu_lines"):
        mtext = read_bytes(os.path.join(REPO, "src/ui/main_menu.gd")).decode("utf-8").replace("\r\n", "\n").split("\n")
        for n in it["menu_lines"]:
            edits.append({"file": "src/ui/main_menu.gd", "lines": [{"n": n, "text": mtext[n - 1]}],
                          "before": mtext[n - 2] if n > 1 else None})
    return edits, manual


# ---------------------------------------------------------------- карантин

def qbase(date=None):
    return os.path.join(QROOT, "RING_карантин_%s" % (date or time.strftime("%Y-%m-%d")), QDIR_NAME)


def all_records():
    out = []
    try:
        names = os.listdir(QROOT)
    except OSError:
        return out
    for d in sorted(names):
        if not d.startswith("RING_карантин_"):
            continue
        base = os.path.join(QROOT, d, QDIR_NAME)
        if not os.path.isdir(base):
            continue
        for rec in sorted(os.listdir(base)):
            p = os.path.join(base, rec, "запись.json")
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        r = json.load(f)
                    r["_path"] = p
                    out.append(r)
                except (OSError, ValueError):
                    pass
    out.sort(key=lambda r: r.get("time", ""), reverse=True)
    return out


def save_record(rec):
    path = rec["_path"]
    data = {k: v for k, v in rec.items() if k != "_path"}
    write_bytes(path, json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
    write_report(os.path.dirname(os.path.dirname(path)))


def write_report(base):
    """Отчёт за день: что убрано, откуда и куда, что с git — для людей."""
    recs = []
    for rec in sorted(os.listdir(base)):
        p = os.path.join(base, rec, "запись.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                recs.append(json.load(f))
    out = ["# Доска сцен — что убрано в карантин", "",
           "Каждая запись — папка рядом: `files/` (файлы по прежним путям), `запись.json`. Вернуть — кнопкой «Вернуть»",
           "на доске (SCENE_BOARD.cmd) или переносом файлов из `files/` обратно в проект.", ""]
    for r in recs:
        state = {"quarantine": "в карантине", "returned": "возвращено"}.get(r["state"], r["state"])
        out.append("## %s — %s" % (r["title"], state))
        out.append("")
        out.append("- Сцена: `%s`; убрано %s" % (r["item"], r["time"]))
        if r.get("git", {}).get("commit"):
            out.append("- Из git: коммит `%s` (%s)%s" % (r["git"]["commit"][:9], r["git"].get("time", ""),
                                                      "" if r["git"].get("pushed") else ", не отправлен"))
        if r.get("returned"):
            out.append("- Возвращено %s%s" % (r["returned"], (", коммит `%s`" % r["return_commit"][:9]) if r.get("return_commit") else ""))
        for e in r.get("edits", []):
            out.append("- Снято из `%s`: строки %s" % (e["file"], ", ".join(str(x["n"]) for x in e["lines"])))
        for m in r.get("manual", []):
            out.append("- Вручную: %s" % m)
        out.append("")
        out.append("| Было в проекте | Лежит в карантине | Размер | В git |")
        out.append("|---|---|---|---|")
        for f in r["files"]:
            out.append("| `%s` | `%s` | %s | %s |" % (f["rel"], f["to"], inventory.human_size(f.get("size", 0)),
                                                     "да" if f.get("tracked") else "нет"))
        out.append("")
    write_bytes(os.path.join(base, "отчёт.md"), "\n".join(out).encode("utf-8"))


def remove_empty_dirs(rel):
    d = os.path.dirname(os.path.join(REPO, rel))
    while os.path.abspath(d) != REPO and d.startswith(REPO):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)


def do_remove(item_id, with_assets, with_snaps, consent):
    it = item_by_id(item_id)
    if not it:
        return {"ok": False, "msg": "Такого пункта уже нет в списке — обновите страницу."}
    if it.get("keep"):
        return {"ok": False, "msg": "Этот пункт помечен «не убирать»."}
    files = [o for o in it["own"] if o["core"] or with_assets]
    if with_snaps:
        files += [{"file": s["file"], "size": s["size"], "tracked": True, "changed": False, "core": False} for s in it["snapshots"]]
    risky = it["blocking"] > 0 or any(o.get("changed") for o in files) or any(not o.get("tracked", True) for o in files)
    if risky and not consent:
        return {"ok": False, "msg": "На пункт ссылается живое или в файлах чужие правки — нужно отдельное согласие."}
    edits, manual = plan_edits(it)
    stamp = time.strftime("%H%M%S")
    stem = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(item_id))[0])
    base = qbase()
    rec_dir = os.path.join(base, "%s_%s" % (stamp, stem))
    n = 1
    while os.path.exists(rec_dir):
        n += 1
        rec_dir = os.path.join(base, "%s_%s_%d" % (stamp, stem, n))
    tracked = set(git("ls-files", "-z").split("\0"))
    rec = {"item": item_id, "title": it["title"], "time": time.strftime("%Y-%m-%d %H:%M:%S"), "repo": REPO,
           "state": "quarantine", "files": [], "edits": [], "manual": manual, "git": {},
           "consent": bool(consent), "_path": os.path.join(rec_dir, "запись.json")}
    os.makedirs(os.path.join(rec_dir, "files"), exist_ok=True)
    # сначала правки строк (их легко вернуть), потом файлы
    for e in edits:
        p = os.path.join(REPO, e["file"])
        new = remove_lines(read_bytes(p), e)
        if new is None:
            rec["manual"].append("%s: строки не нашлись на месте, не сняты" % e["file"])
            continue
        write_bytes(p, new)
        rec["edits"].append(e)
    seen = set()
    for o in files:
        rel = o["file"]
        if rel in seen or not os.path.isfile(os.path.join(REPO, rel)):
            continue
        seen.add(rel)
        dst = os.path.join(rec_dir, "files", rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(REPO, rel), dst)
        remove_empty_dirs(rel)
        rec["files"].append({"rel": rel, "to": dst, "size": o.get("size", 0), "tracked": rel in tracked})
        save_record(rec)
    save_record(rec)
    return {"ok": True, "msg": "Убрано в карантин: %d файлов → %s" % (len(rec["files"]), rec_dir)}


def do_restore(rec_path):
    rec = next((r for r in all_records() if r["_path"] == rec_path), None)
    if not rec or rec["state"] != "quarantine":
        return {"ok": False, "msg": "Запись не найдена или уже возвращена."}
    clash = [f["rel"] for f in rec["files"] if os.path.exists(os.path.join(REPO, f["rel"]))]
    if clash:
        return {"ok": False, "msg": "В проекте уже есть файлы с теми же именами: %s" % ", ".join(clash[:5])}
    for f in rec["files"]:
        dst = os.path.join(REPO, f["rel"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(f["to"], dst)
    for e in rec.get("edits", []):
        p = os.path.join(REPO, e["file"])
        write_bytes(p, insert_lines(read_bytes(p), e))
    # пустые папки, оставшиеся в карантине после возврата
    for d, _sub, names in sorted(os.walk(os.path.join(os.path.dirname(rec["_path"]), "files")), key=lambda x: -len(x[0])):
        if not names:
            try:
                os.rmdir(d)
            except OSError:
                pass
    rec["state"] = "returned"
    rec["returned"] = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = "Возвращено: %d файлов на прежние места." % len(rec["files"])
    if rec.get("git", {}).get("commit"):
        try:
            res = commit_change(rec, restore=True)
            rec["return_commit"] = res["commit"]
            rec["return_pushed"] = res["pushed"]
            msg += " В git возвращено коммитом %s%s." % (res["commit"][:9], "" if res["pushed"] else " (не отправлен: %s)" % res["push_msg"])
        except Exception as e:  # noqa: BLE001
            msg += " В git вернуть не получилось: %s — файлы на месте, попросите агента закоммитить." % e
    save_record(rec)
    return {"ok": True, "msg": msg}


# ---------------------------------------------------------------- git: коммит только своих путей

def head_branch():
    r = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=REPO, capture_output=True)
    return r.stdout.decode().strip() or "HEAD"


def sync_with_origin():
    """Перед коммитом: подтянуть origin, если он ушёл вперёд (только перемоткой, чужие правки не трогаются)."""
    if NO_PUSH:
        return
    git("fetch", "-q", "origin", timeout=120)
    head = git("rev-parse", "HEAD").strip()
    branch = head_branch().replace("refs/heads/", "")
    up = git("rev-parse", "origin/%s" % branch, check=False).strip()
    if not up or up == head:
        return
    behind = subprocess.run(["git", "merge-base", "--is-ancestor", head, up], cwd=REPO).returncode == 0
    if behind:
        r = subprocess.run(["git", "merge", "--ff-only", "-q", up], cwd=REPO, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError("копия проекта отстала, а обновить её мешают незакоммиченные правки — попросите агента "
                               "сделать git pull, потом нажмите ещё раз")
        return
    ahead = subprocess.run(["git", "merge-base", "--is-ancestor", up, head], cwd=REPO).returncode == 0
    if not ahead:
        raise RuntimeError("ветка разошлась с origin — попросите агента разобраться, потом нажмите ещё раз")


def entry_of(rev, path):
    """(режим, блоб) файла в коммите или (None, None)."""
    out = git("ls-tree", rev, "--", path, check=False).split()
    return (out[0], out[2]) if len(out) >= 3 else (None, None)


def commit_change(rec, restore=False):
    """Коммит только путей записи: файлы убраны (или возвращены), строки AGENTS.md / меню сняты (или вставлены),
    отчёт docs/scene_inventory.md обновлён. Чужие незакоммиченные правки в рабочей копии в коммит не попадают."""
    sync_with_origin()
    paths = [f["rel"] for f in rec["files"] if f.get("tracked")]
    for attempt in range(3):
        old = git("rev-parse", "HEAD").strip()
        idx = os.path.join(WORK, "index_%d" % os.getpid())
        env = {"GIT_INDEX_FILE": idx}
        if os.path.exists(idx):
            os.remove(idx)
        git("read-tree", old, env=env)
        if restore:
            git("add", "--", *paths, env=env)
        else:
            git("rm", "--cached", "-q", "--ignore-unmatch", "--", *paths, env=env)
        edit_files = sorted(set(e["file"] for e in rec.get("edits", [])))
        for ef in edit_files:
            data = git_bytes("show", "%s:%s" % (old, ef))
            if data is None:
                continue
            for e in rec["edits"]:
                if e["file"] != ef:
                    continue
                new = insert_lines(data, e) if restore else remove_lines(data, e)
                if new is not None:
                    data = new
            blob = git("hash-object", "-w", "--stdin", "--no-filters", input_bytes=data).strip()
            mode = entry_of(old, ef)[0] or "100644"
            git("update-index", "--cacheinfo", "%s,%s,%s" % (mode, blob, ef), env=env)
        inv_md = "docs/scene_inventory.md"
        try:
            inventory.write_md(rebuild(), os.path.join(REPO, inv_md))
            git("add", "--", inv_md, env=env)
        except Exception:  # noqa: BLE001 — отчёт не главное
            pass
        tree = git("write-tree", env=env).strip()
        what = "вернуть" if restore else "убрать"
        msg = ("сцены: %s %s (доска сцен, выбор владельца)\n\n%s\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
               % (what, rec["item"], "\n".join("- " + p for p in paths[:40])))
        commit = git("commit-tree", tree, "-p", old, input_bytes=msg.encode("utf-8")).strip()
        r = subprocess.run(["git", "update-ref", head_branch(), commit, old], cwd=REPO, capture_output=True)
        os.remove(idx)
        if r.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("другие сессии одновременно коммитят — нажмите ещё раз")
    # настоящий индекс: где он совпадал со старым HEAD, ставим новое состояние; чужое добавленное не трогаем
    touched = paths + edit_files + ["docs/scene_inventory.md"]
    for p in touched:
        cur = git("ls-files", "-s", "--", p).split()
        cur_blob = cur[1] if len(cur) > 1 else None
        if cur_blob != entry_of(old, p)[1]:
            continue
        mode, nb = entry_of(commit, p)
        if nb:
            git("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, nb, p))
        else:
            git("update-index", "--force-remove", "--", p)
    pushed, push_msg = push()
    return {"commit": commit, "pushed": pushed, "push_msg": push_msg}


def push():
    if NO_PUSH:
        return False, "отправка выключена (--no-push)"
    branch = head_branch().replace("refs/heads/", "")
    try:
        r = subprocess.run(["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential",
                            "push", "-q", "origin", branch], cwd=REPO, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "сервер не ответил за 3 минуты"
    if r.returncode != 0:
        return False, r.stderr.decode("utf-8", "replace").strip()[-300:]
    return True, ""


def do_git_remove(rec_path):
    rec = next((r for r in all_records() if r["_path"] == rec_path), None)
    if not rec or rec["state"] != "quarantine":
        return {"ok": False, "msg": "Запись не найдена или уже возвращена."}
    if rec.get("git", {}).get("commit"):
        if rec["git"].get("pushed"):
            return {"ok": False, "msg": "Уже убрано из git."}
        pushed, pm = push()
        rec["git"]["pushed"] = pushed
        save_record(rec)
        return {"ok": pushed, "msg": "Отправлено." if pushed else "Не отправилось: %s" % pm}
    if not any(f.get("tracked") for f in rec["files"]) and not rec.get("edits"):
        return {"ok": False, "msg": "Эти файлы и не были в git — убирать из git нечего."}
    res = commit_change(rec)
    rec["git"] = {"commit": res["commit"], "pushed": res["pushed"], "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_record(rec)
    msg = "Убрано из git коммитом %s." % res["commit"][:9]
    msg += " Отправлено." if res["pushed"] else " Не отправлено: %s" % res["push_msg"]
    return {"ok": True, "msg": msg}


# ---------------------------------------------------------------- запуск

def do_launch(item_id, index):
    it = item_by_id(item_id)
    if not it or index >= len(it["launches"]):
        return {"ok": False, "msg": "Нет такого варианта запуска."}
    lo = it["launches"][index]
    env = dict(os.environ)
    if lo.get("cmd"):
        cmdline = ["cmd", "/c", lo["cmd"].replace("/", "\\")]
    else:
        cmdline = ["cmd", "/c", "tools\\godot.cmd", *lo["args"]]
        env.update(lo.get("env", {}))
    rid = "%d" % (int(time.time() * 1000))
    log = os.path.join(LOGS, "%s.log" % rid)
    fh = open(log, "wb")
    proc = subprocess.Popen(cmdline, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT, env=env, creationflags=NO_WINDOW)
    RUNS[rid] = {"id": rid, "item": item_id, "title": it["title"], "label": lo["label"], "proc": proc, "log": log,
                 "fh": fh, "started": time.strftime("%H:%M:%S"), "headless": bool(lo.get("headless"))}
    return {"ok": True, "msg": "Запущено: %s — %s" % (it["title"], lo["label"]), "run": rid}


def runs_state():
    out = []
    for rid, r in sorted(RUNS.items(), reverse=True)[:12]:
        code = r["proc"].poll()
        try:
            with open(r["log"], "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 6000))
                tail = f.read().decode("utf-8", "replace").splitlines()[-30:]
        except OSError:
            tail = []
        out.append({"id": rid, "item": r["item"], "title": r["title"], "label": r["label"], "started": r["started"],
                    "running": code is None, "code": code, "tail": tail})
    return out


def do_stop(rid):
    r = RUNS.get(rid)
    if not r:
        return {"ok": False, "msg": "Нет такого запуска."}
    subprocess.run(["taskkill", "/PID", str(r["proc"].pid), "/T", "/F"], capture_output=True)
    return {"ok": True, "msg": "Остановлено."}


# ---------------------------------------------------------------- миниатюры

def thumb(rel, wide):
    src = os.path.join(REPO, rel)
    if not (rel.startswith("docs/screens/") or rel.startswith("assets/maps/")) or ".." in rel or not os.path.isfile(src):
        return None, None
    if wide:
        ext = os.path.splitext(rel)[1].lower()
        return read_bytes(src), {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    key = hashlib.sha1(("%s|%d" % (rel, os.path.getmtime(src))).encode()).hexdigest()
    dst = os.path.join(THUMBS, key + ".jpg")
    if not os.path.isfile(dst):
        try:
            from PIL import Image
            im = Image.open(src).convert("RGB")
            im.thumbnail((480, 270))
            im.save(dst, "JPEG", quality=80)
        except Exception:  # noqa: BLE001 — без PIL отдаём оригинал
            return read_bytes(src), "image/png"
    return read_bytes(dst), "image/jpeg"


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self._send(200, read_bytes(os.path.join(HERE, "page.html")), "text/html; charset=utf-8")
        if u.path == "/api/inventory":
            if q.get("refresh") or STATE["inv"] is None:
                with LOCK:
                    rebuild()
            inv = STATE["inv"] or {}
            return self._send(200, {"inv": inv, "error": STATE["error"], "local": self._local(), "no_push": NO_PUSH,
                                    "quarantine_root": QROOT, "quarantine_today": qbase()})
        if u.path == "/api/quarantine":
            recs = [dict(r) for r in all_records()]
            return self._send(200, {"records": recs})
        if u.path == "/api/runs":
            return self._send(200, {"runs": runs_state()})
        if u.path == "/img":
            data, ctype = thumb(q.get("f", [""])[0], bool(q.get("full")))
            if data is None:
                return self._send(404, b"not found", "text/plain")
            return self._send(200, data, ctype)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._local():
            return self._send(403, {"ok": False, "msg": "С другого устройства можно только смотреть."})
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        p = urlparse(self.path).path
        try:
            if p == "/api/launch":
                return self._send(200, do_launch(data["id"], int(data.get("index", 0))))
            if p == "/api/stop":
                return self._send(200, do_stop(data["run"]))
            with LOCK:
                if p == "/api/remove":
                    res = do_remove(data["id"], bool(data.get("assets")), bool(data.get("snaps")), bool(data.get("consent")))
                elif p == "/api/restore":
                    res = do_restore(data["record"])
                elif p == "/api/git_remove":
                    res = do_git_remove(data["record"])
                else:
                    return self._send(404, {"ok": False, "msg": "нет такого действия"})
                rebuild()
                return self._send(200, res)
        except Exception as e:  # noqa: BLE001
            return self._send(200, {"ok": False, "msg": "Ошибка: %s" % e})


def main():
    import socket
    probe = socket.socket()
    busy_port = probe.connect_ex(("127.0.0.1", PORT)) == 0
    probe.close()
    if busy_port:
        print("Доска уже запущена — открываю страницу.")
        if "--open" in sys.argv:
            import webbrowser
            webbrowser.open("http://localhost:%d/" % PORT)
        return
    print("Доска сцен: собираю список…")
    rebuild()
    host = "0.0.0.0" if LAN else "127.0.0.1"
    try:
        srv = ThreadingHTTPServer((host, PORT), Handler)
    except OSError:
        print("Доска уже запущена — открываю страницу.")
        if "--open" in sys.argv:
            import webbrowser
            webbrowser.open("http://localhost:%d/" % PORT)
        return
    print("Готово: http://localhost:%d/   (проект %s, карантин %s%s)" % (PORT, REPO, QROOT, ", без отправки" if NO_PUSH else ""))
    if LAN:
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
            print("С телефона (только смотреть): http://%s:%d/" % (ip, PORT))
        except OSError:
            pass
    print("Окно не закрывать, пока пользуетесь доской.")
    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open("http://localhost:%d/" % PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
