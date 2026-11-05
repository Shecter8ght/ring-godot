# «Осока» (ПЗРК по образцу 9К333): снимки моделей Sketchfab через Viewer API — только образец формы, сетки не скачиваются.
# python -X utf8 tools/osoka/sketchfab_capture_server.py <порт> <папка> ; GET /?uid=<id> — просмотрщик; POST /save?name=<имя> — тело = data URL → <папка>/<имя>.png
import base64
import http.server
import json
import os
import re
import sys
import urllib.parse

OUT = sys.argv[2] if len(sys.argv) > 2 else "."
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8771
HERE = os.path.dirname(os.path.abspath(__file__))


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "sketchfab_capture.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        else:
            self._send(404, b"no")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_POST(self) -> None:
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n)
        if u.path == "/save":
            name = q.get("name", ["shot"])[0]
            if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", name):
                self._send(400, b"bad name")
                return
            s = data.decode("ascii", "ignore")
            m = re.match(r"data:image/(png|jpeg);base64,(.*)", s, re.S)
            if not m:
                self._send(400, b"bad data")
                return
            ext = "png" if m.group(1) == "png" else "jpg"
            path = os.path.join(OUT, f"{name}.{ext}")
            with open(path, "wb") as f:
                f.write(base64.b64decode(m.group(2)))
            self._send(200, json.dumps({"saved": path}).encode())
        elif u.path == "/json":
            name = q.get("name", ["meta"])[0]
            if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", name):
                self._send(400, b"bad name")
                return
            path = os.path.join(OUT, f"{name}.json")
            with open(path, "wb") as f:
                f.write(data)
            self._send(200, json.dumps({"saved": path}).encode())
        else:
            self._send(404, b"no")

    def log_message(self, *a) -> None:
        pass


os.makedirs(OUT, exist_ok=True)
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
