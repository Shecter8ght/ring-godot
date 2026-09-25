"""Local shortlist viewer. Serves only audit files and shortlisted FBX."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIEWER = HERE / "viewer"
PORT = 8765


def allowed_paths() -> set[str]:
    data = json.loads((HERE / "shortlist.json").read_text(encoding="utf-8"))
    return {item["path"] for family in data.values() for state in family.values() for item in state["candidates"]}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER), **kwargs)

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/asset/"):
            rel = path[len("/asset/"):]
            if rel not in allowed_paths():
                self.send_error(403, "Not shortlisted")
                return
            source = (ROOT / rel).resolve()
            if not source.is_file() or not source.is_relative_to(ROOT / "assets" / "animations"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(source.stat().st_size))
            self.end_headers()
            with source.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    self.wfile.write(chunk)
            return
        if path.startswith("/vendor/"):
            candidate = (VIEWER / path.lstrip("/")).resolve()
            if candidate.is_file() and candidate.is_relative_to(VIEWER / "vendor"):
                return super().do_GET()
            self.send_error(404)
            return
        if path == "/" or path in {"/index.html", "/styles.css", "/app.js", "/shortlist.json"}:
            self.path = "/index.html" if path == "/" else path
            return super().do_GET()
        self.send_error(404)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/selection":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 1024 * 1024:
                raise ValueError("Invalid size")
            payload = json.loads(self.rfile.read(size))
            valid = allowed_paths()
            decisions = payload["decisions"]
            if not isinstance(decisions, dict) or any(path not in valid or status not in {"SELECT", "MAYBE", "REJECT"} for path, status in decisions.items()):
                raise ValueError("Invalid decision")
            selection = {"decisions": decisions, "selected": sorted(path for path, status in decisions.items() if status == "SELECT")}
            (HERE / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            lines = ["# Animation selection", "", "Visual review decisions exported from the shortlist viewer.", ""]
            for status in ("SELECT", "MAYBE", "REJECT"):
                lines.extend([f"## {status}", ""])
                lines.extend(f"- `{path}`" for path, value in sorted(decisions.items()) if value == status)
                lines.append("")
            (HERE / "SELECTION.md").write_text("\n".join(lines), encoding="utf-8")
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))


if __name__ == "__main__":
    print(f"Open http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
