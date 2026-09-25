"""Download pinned Three.js browser modules for offline local preview."""
from pathlib import Path
import re
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent / "viewer" / "vendor"
BASE = "https://cdn.jsdelivr.net/npm/three@0.180.0/"
PENDING = ["LICENSE", "build/three.module.js", "examples/jsm/loaders/FBXLoader.js"]
SEEN = set()
while PENDING:
    rel = PENDING.pop()
    if rel in SEEN:
        continue
    SEEN.add(rel)
    source = urlopen(BASE + rel, timeout=30).read()
    target = OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    for dependency in re.findall(r"\bfrom\s+['\"](\.[^'\"]+)['\"]", source.decode("utf-8")):
        import posixpath
        PENDING.append(posixpath.normpath(posixpath.join(posixpath.dirname(rel), dependency)))
    print(rel, len(source))
