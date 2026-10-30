"""Страница каталога заводских отделок с выбором: карточки «как в интернет-магазине», кнопка «Выбрать» пишет файл
спецификации отделки (finish-spec.json рядом с моделью), «Прислать образец» кладёт картинку владельца в папку
«Образцы владельца» каталога. Только стандартная библиотека Python — запускают и Claude, и Codex.

    python -X utf8 tools/asset_kit/finish/catalog_server.py [--spec "<папка модели>/finish-spec.json"] [--port 8765]
    python -X utf8 tools/asset_kit/finish/catalog_server.py --new-spec "<файл>" --asset "<имя>" --slot id:Название ...

Без --spec выбор идёт в «<каталог>/выбор.json» (избранное). Страница — http://localhost:<порт>/.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CATALOG = Path(os.environ.get("FINISH_CATALOG", r"E:/Models Blender/Каталог отделок"))
SAMPLES = "Образцы владельца"
SCHEMA = "ring-finish-spec/1"
LOCK = threading.Lock()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_spec(asset: str = "", slots: list | None = None) -> dict:
    return {"schema": SCHEMA, "asset": asset, "model": "", "stage": "factory",
            "catalog": "tools/asset_kit/finish/finishes.json",
            "about": "Заводская отделка (этап 1): слот — группа деталей, finish — код каталога, overrides — правки чисел "
                     "поверх карточки. Пишет страница каталога (catalog_server.py) и агент; читают Claude и Codex.",
            "slots": slots or [], "favorites": [], "requests": [], "history": [], "accepted": False}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def safe_name(s: str, limit: int = 60) -> str:
    s = re.sub(r"[^\w\-. ]+", "_", s, flags=re.UNICODE).strip(" ._")
    return s[:limit] or "образец"


class Handler(SimpleHTTPRequestHandler):
    spec_path: Path = CATALOG / "выбор.json"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(CATALOG), **kw)

    def log_message(self, fmt, *args):  # тише: только API
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _spec(self) -> dict:
        return read_json(self.spec_path, None) or new_spec()

    def do_GET(self):
        if self.path.startswith("/api/spec"):
            spec = self._spec()
            spec["_path"] = str(self.spec_path)
            return self._send(spec)
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n > 40 * 1024 * 1024:
            return self._send({"error": "слишком большой файл (больше 40 МБ)"}, 413)
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send({"error": "не JSON"}, 400)
        with LOCK:
            if self.path == "/api/choose":
                return self._send(self.choose(req))
            if self.path == "/api/favorite":
                return self._send(self.favorite(req))
            if self.path == "/api/sample":
                return self._send(self.sample(req))
        return self._send({"error": "нет такого действия"}, 404)

    def choose(self, req) -> dict:
        """Выбор отделки для слота (группы деталей) модели; пустой код — снять выбор."""
        spec = self._spec()
        slot = next((s for s in spec["slots"] if s["id"] == req.get("slot")), None)
        if slot is None:
            return {"error": "нет слота " + str(req.get("slot"))}
        slot["finish"] = req.get("code") or None
        if req.get("note") is not None:
            slot["note"] = req["note"]
        spec["accepted"] = False
        spec["history"].append({"time": now(), "slot": slot["id"], "finish": slot["finish"], "by": "страница каталога"})
        write_json(self.spec_path, spec)
        return spec

    def favorite(self, req) -> dict:
        spec = self._spec()
        code = req.get("code")
        favs = spec.setdefault("favorites", [])
        if code in favs:
            favs.remove(code)
        elif code:
            favs.append(code)
        spec["history"].append({"time": now(), "favorite": code, "on": code in favs, "by": "страница каталога"})
        write_json(self.spec_path, spec)
        return spec

    def sample(self, req) -> dict:
        """Образец владельца: картинка (data URL) и/или комментарий к карточке или к новой отделке."""
        folder = CATALOG / SAMPLES
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        code = safe_name(req.get("code") or "новая", 20)
        saved = []
        for i, item in enumerate(req.get("images") or []):
            m = re.match(r"data:image/(\w+);base64,(.*)", item.get("data", ""), re.S)
            if not m:
                continue
            ext = {"jpeg": "jpg"}.get(m.group(1).lower(), m.group(1).lower())
            stem = safe_name(Path(item.get("name") or f"образец_{i + 1}").stem)
            path = folder / f"{stamp}_{code}_{stem}.{ext}"
            path.write_bytes(base64.b64decode(m.group(2)))
            saved.append(path.name)
        rec = {"time": now(), "code": req.get("code") or None, "comment": req.get("comment", ""), "files": saved}
        log = read_json(folder / "образцы.json", [])
        log.append(rec)
        write_json(folder / "образцы.json", log)
        spec = self._spec()
        spec.setdefault("requests", []).append(rec)
        write_json(self.spec_path, spec)
        return {"ok": True, "saved": saved, "spec": spec}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", type=Path)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--new-spec", type=Path, help="создать файл спецификации и выйти")
    p.add_argument("--asset", default="")
    p.add_argument("--model", default="")
    p.add_argument("--slot", action="append", default=[], help="id:Название[:деталь,деталь]")
    a = p.parse_args()
    if a.new_spec:
        slots = []
        for s in a.slot:
            sid, title, *rest = s.split(":")
            slots.append({"id": sid, "title": title, "parts": rest[0].split(",") if rest and rest[0] else [],
                          "finish": None, "overrides": {}, "note": ""})
        spec = read_json(a.new_spec, None) or new_spec(a.asset, slots)
        spec["asset"] = a.asset or spec.get("asset", "")
        spec["model"] = a.model or spec.get("model", "")
        have = {s["id"] for s in spec["slots"]}
        spec["slots"] += [s for s in slots if s["id"] not in have]
        write_json(a.new_spec, spec)
        print("SPEC", a.new_spec, len(spec["slots"]), "слотов")
        return
    Handler.spec_path = (a.spec or CATALOG / "выбор.json").resolve()
    if not Handler.spec_path.exists():
        write_json(Handler.spec_path, new_spec())
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"CATALOG http://localhost:{a.port}/  spec={Handler.spec_path}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
