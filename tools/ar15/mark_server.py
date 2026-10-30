# AR-15 «ГРАНЬ-15», этап 2 (износ): сервис разметки мест износа владельцем — страница с рендерами
# (tools/ar15/mark_views.py), кистью отмечается место, из выпадающего списка — тип повреждения и сила; «Сохранить»
# пишет маски меток и marks.json в папку разметки, оттуда tools/ar15/mark_apply.py переносит их в развёртку, а
# sp_ar15_wear.build_marks() кладёт слои в Substance Painter (владелец 30.10: «отмечал курсором места, выпадающий
# список с типом повреждения, и в рамках отмеченного места — износ в Substance Painter»).
#   python -X utf8 tools/ar15/mark_server.py [папка разметки] [порт 8766]   → http://localhost:8766/
# Только этот компьютер (127.0.0.1). Страница — tools/ar15/mark_page.html.
import base64
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else "E:/Models Blender/WEAPONS/AR-15 — модель/Разметка_износа"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8766
MARKS = os.path.join(ROOT, "marks")
SAFE = re.compile(r"^[A-Za-z0-9_\-]+$")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        if not os.path.isfile(path):
            return self._send(404, b"not found", "text/plain")
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._file(os.path.join(HERE, "mark_page.html"), "text/html; charset=utf-8")
        if p == "/views.json":
            return self._file(os.path.join(ROOT, "views.json"), "application/json; charset=utf-8")
        if p == "/marks.json":
            path = os.path.join(MARKS, "marks.json")
            if not os.path.isfile(path):
                return self._send(200, b'{"marks": []}', "application/json")
            return self._file(path, "application/json; charset=utf-8")
        m = re.match(r"^/(views|marks)/([A-Za-z0-9_\-]+)\.png$", p)
        if m:
            folder = os.path.join(ROOT, "views") if m.group(1) == "views" else MARKS
            return self._file(os.path.join(folder, m.group(2) + ".png"), "image/png")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/save":
            return self._send(404, b"not found", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n).decode("utf-8"))
        os.makedirs(MARKS, exist_ok=True)
        keep, out = set(), []
        for mk in data.get("marks", []):
            mid = mk.get("id", "")
            if not SAFE.match(mid) or not SAFE.match(mk.get("view", "")):
                continue
            keep.add(mid)
            mask = mk.pop("mask", None)
            if mask:
                raw = base64.b64decode(mask.split(",", 1)[1])
                with open(os.path.join(MARKS, mid + ".png"), "wb") as f:
                    f.write(raw)
            mk["file"] = mid + ".png"
            out.append(mk)
        # маски удалённых на странице меток — тоже прочь (это файлы самого сервиса)
        for fn in os.listdir(MARKS):
            if fn.endswith(".png") and fn[:-4] not in keep:
                os.remove(os.path.join(MARKS, fn))
        with open(os.path.join(MARKS, "marks.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"marks": out}, f, ensure_ascii=False, indent=1)
        print("сохранено меток:", len(out))
        self._send(200, json.dumps({"ok": True, "count": len(out)}).encode(), "application/json")

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"Разметка износа: http://localhost:{PORT}/  (папка {ROOT})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
