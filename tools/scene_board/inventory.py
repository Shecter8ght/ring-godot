# Инвентаризация сцен, стендов и уровней RING (задача владельца 2026-11-02): что это, откуда запускают,
# кто на неё ссылается, какие файлы принадлежат только ей, когда правили и сколько весит. Данные для
# «Доски сцен» (tools/scene_board/server.py) и отчёт docs/scene_inventory.md.
#   python -X utf8 tools/scene_board/inventory.py [--repo <папка>] [--md]   → печатает сводку; --md — пишет отчёт
# Ничего не удаляет и не меняет в проекте (кроме отчёта по --md).
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

TEXT_EXT = {".tscn", ".tres", ".gd", ".gdshader", ".gdshaderinc", ".json", ".cmd", ".py", ".sh", ".md",
            ".txt", ".godot", ".cfg"}
# откуда ссылка «живая»: сцены, код, данные игры; документы и скрипты сборки — только для сведения
LIVE_EXT = {".tscn", ".tres", ".gd", ".gdshader", ".gdshaderinc", ".godot", ".cfg"}
DOC_EXT = {".md", ".txt"}
MAX_SCAN = 40 * 1024 * 1024

RES_RE = re.compile(r'res://([^"\'\s\)\]\}<>,;|`*]+)')
UID_RE = re.compile(r'uid://[a-z0-9]+')
REL_RE = re.compile(r'((?:tools|scenes|levels|src|data|assets|docs)/[^\s"\'`<>|,;*()\[\]]+)')
TSCN_NAME_RE = re.compile(r'([\w.\-]+\.tscn)')
CLASS_RE = re.compile(r'^class_name\s+(\w+)', re.M)
IDENT_RE = re.compile(r'\b[A-Z]\w+\b')
QUOTED_RE = re.compile(r'"([A-Za-z0-9_]+)"')
DYN_RE = re.compile(r'"res://([^"%]*?)(?:%[sd0-9]|"\s*\+)')
EXT_RES_RE = re.compile(r'\[ext_resource ([^\]]*)\]')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


NAME_CH = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")


def tscn_names(t):
    """Имена «x.tscn» в тексте (регулярка без якоря на длинных строках из букв и цифр квадратична)."""
    out = set()
    i = t.find(".tscn")
    while i >= 0:
        j = i
        while j > 0 and i - j < 120 and t[j - 1] in NAME_CH:
            j -= 1
        if j < i and (j == 0 or t[j - 1] not in "/\\:"):
            out.add(t[j:i + 5].lstrip(".-"))
        i = t.find(".tscn", i + 5)
    return out


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8", "replace")


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_SCAN:
            return ""
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def is_doc(path):
    return path.startswith("docs/") or ext_of(path) in DOC_EXT or path == "AGENTS.md"


def ref_kind(path):
    """Как читать ссылку из файла path: что сломается, если её цель убрать."""
    e = ext_of(path)
    if path == "AGENTS.md":
        return "agents"
    if path == "src/ui/main_menu.gd":
        return "menu"
    if is_doc(path):
        return "doc"
    if e in (".tscn", ".tres"):
        return "scene"
    if e in (".gd", ".gdshader", ".gdshaderinc"):
        return "code"
    if e in (".godot", ".cfg", ".json"):
        return "data"
    if e == ".cmd":
        return "cmd"
    if e in (".py", ".sh"):
        return "build"
    return "other"


BLOCKING = {"scene", "code", "data", "cmd", "menu"}


class Repo:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.files = []          # все файлы рабочей копии (в git и новые, не игнорируемые)
        self.tracked = set()
        self.changed = set()     # есть незакоммиченные правки (кто-то работает)
        self.deleted = set()     # в git есть, в рабочей копии удалены
        self.untracked = set()
        self.sizes = {}
        self.last_commit = {}
        self.uid_to_path = {}
        self.class_to_path = {}
        self.refs_to = defaultdict(set)     # цель → кто ссылается (по пути / uid / имени класса)
        self.refs_from = defaultdict(set)   # файл → на что ссылается
        self.name_refs = defaultdict(set)   # имя сцены «x.tscn» → где упоминается
        self.quoted_in = defaultdict(set)   # строка в кавычках → файлы кода и данных
        self.dynamic = []                   # (префикс пути, файл кода) — загрузка по имени
        self.texts = {}

    def p(self, rel):
        return os.path.join(self.root, rel)

    def scan(self):
        out = git(self.root, "ls-files", "-z")
        self.tracked = set(x for x in out.split("\0") if x)
        out = git(self.root, "ls-files", "-z", "--others", "--exclude-standard")
        self.untracked = set(x for x in out.split("\0") if x)
        st = git(self.root, "status", "--porcelain", "-z", "--untracked-files=no")
        for rec in st.split("\0"):
            if len(rec) < 4:
                continue
            code, path = rec[:2], rec[3:]
            if "D" in code:
                self.deleted.add(path)
            else:
                self.changed.add(path)
        allf = sorted((self.tracked | self.untracked))
        self.files = [f for f in allf if os.path.isfile(self.p(f))]
        self.fileset = set(self.files)
        for f in self.files:
            try:
                self.sizes[f] = os.path.getsize(self.p(f))
            except OSError:
                self.sizes[f] = 0
        # дата последнего коммита — одним проходом истории
        log = git(self.root, "log", "--format=@@%cs", "--name-only")
        date = ""
        for line in log.splitlines():
            if line.startswith("@@"):
                date = line[2:]
            elif line and line not in self.last_commit:
                self.last_commit[line] = date
        # uid → путь
        for f in self.files:
            e = ext_of(f)
            if e == ".uid":
                m = UID_RE.search(read_text(self.p(f)))
                if m:
                    self.uid_to_path[m.group(0)] = f[:-4]
            elif e == ".import":
                txt = read_text(self.p(f))
                m = re.search(r'uid="(uid://[a-z0-9]+)"', txt)
                if m:
                    self.uid_to_path[m.group(1)] = f[:-7]
            elif e in (".tscn", ".tres"):
                with open(self.p(f), "rb") as fh:
                    head = fh.read(400).decode("utf-8", "replace")
                m = re.search(r'uid="(uid://[a-z0-9]+)"', head.split("\n", 1)[0])
                if m:
                    self.uid_to_path[m.group(1)] = f
        # тексты и классы
        for f in self.files:
            if ext_of(f) in TEXT_EXT:
                self.texts[f] = read_text(self.p(f))
        for f, t in self.texts.items():
            if ext_of(f) == ".gd":
                m = CLASS_RE.search(t)
                if m:
                    self.class_to_path[m.group(1)] = f
        for f, t in self.texts.items():
            # сама доска упоминает все сцены (пометки, отчёт) — это не ссылка
            if f.startswith("tools/scene_board/") or f == "docs/scene_inventory.md":
                continue
            self._index(f, t)

    def _resolve(self, raw):
        raw = raw.rstrip(".:'\"")
        if "%" in raw or "{" in raw or "$" in raw:
            return None
        raw = raw.split("::")[0]
        if raw in self.fileset:
            return raw
        return None

    def _add(self, src, dst):
        if dst and dst != src:
            self.refs_to[dst].add(src)
            self.refs_from[src].add(dst)

    def _index(self, f, t):
        e = ext_of(f)
        for m in RES_RE.finditer(t):
            self._add(f, self._resolve(m.group(1)))
        for m in UID_RE.finditer(t):
            self._add(f, self.uid_to_path.get(m.group(0)))
        if e in (".cmd", ".py", ".sh", ".md", ".txt", ".json", ".cfg"):
            norm = t.replace("\\", "/")
            for m in REL_RE.finditer(norm):
                self._add(f, self._resolve(m.group(1)))
        for name in tscn_names(t):
            self.name_refs[name].add(f)
        if e == ".gd":
            for name in set(IDENT_RE.findall(t)):
                dst = self.class_to_path.get(name)
                if dst:
                    self._add(f, dst)
            for m in DYN_RE.finditer(t):
                self.dynamic.append((m.group(1), f))
        if e in (".gd", ".json"):
            for q in set(QUOTED_RE.findall(t)):
                self.quoted_in[q].add(f)

    def referrers(self, target):
        """Кто ссылается на файл: по пути, uid, имени класса; для сцен — ещё по имени файла."""
        out = set(self.refs_to.get(target, ()))
        if target.endswith(".tscn"):
            out |= self.name_refs.get(os.path.basename(target), set())
        out.discard(target)
        return out

    def dynamic_users(self, target):
        """Код, который грузит файлы из папки по имени («…/%s.tscn»), и сам упоминает имя этого файла."""
        stem = os.path.splitext(os.path.basename(target))[0]
        users = set()
        loaders = set(f for prefix, f in self.dynamic if prefix and len(prefix) > 6 and target.startswith(prefix))
        if loaders:
            # имя в кавычках — в самом загрузчике или в данных, по которым он грузит (манифесты, списки)
            for f in self.quoted_in.get(stem, set()):
                if f in loaders or ext_of(f) == ".json":
                    users.add(f)
            if users:
                users |= loaders
        return users

    def under_dynamic(self, target):
        return any(prefix and len(prefix) > 6 and target.startswith(prefix) for prefix, _ in self.dynamic)


# ---------------------------------------------------------------- AGENTS.md: строки запуска

def parse_agents(repo):
    """Записи раздела «Запуск и проверка»: строка команды и её строки-продолжения (комментарии)."""
    text = repo.texts.get("AGENTS.md", "")
    lines = text.split("\n")
    entries = []
    in_block = False
    section = False
    cur = None
    for i, raw in enumerate(lines):
        line = raw.rstrip("\r")
        if line.startswith("## "):
            section = line.startswith("## Запуск и проверка")
        if not section:
            continue
        if line.startswith("```"):
            in_block = not in_block
            cur = None
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if not stripped:
            cur = None
            continue
        is_cont = line.startswith(" ") and stripped.startswith("#")
        is_hash_block = line.startswith("#")
        if is_cont and cur is not None:
            cur["lines"].append(i)
            cur["comment"] += " " + stripped.lstrip("#").strip()
            continue
        if is_hash_block and cur is not None and cur.get("hash") and line.startswith("#  "):
            cur["lines"].append(i)
            cur["comment"] += " " + stripped.lstrip("#").strip()
            continue
        cmd, comment = line, ""
        if is_hash_block:
            cmd, comment = "", stripped.lstrip("#").strip()
        else:
            m = re.search(r"\s#\s", line)
            if m:
                cmd, comment = line[:m.start()].strip(), line[m.end():].strip()
        cur = {"start": i, "lines": [i], "cmd": cmd.strip(), "comment": comment, "hash": is_hash_block}
        entries.append(cur)
    for en in entries:
        body = "\n".join(lines[j] for j in en["lines"])
        en["scenes"] = sorted(set(m.group(1) for m in RES_RE.finditer(body) if m.group(1).endswith(".tscn")))
        en["names"] = sorted(tscn_names(body))
        en["text"] = [lines[j].rstrip("\r") for j in en["lines"]]
    return entries


ARG_WORDS = {
    "verify": "проверка", "shots": "снимки", "bake": "запечь свет", "check": "проверка", "v3shots": "снимки материалов",
    "host": "хост", "client": "гость", "c1": "гость 1", "c2": "гость 2", "gear": "со снаряжением", "off": "для сравнения (выключено)",
    "lod": "дальности LOD", "lodcmp": "сравнение LOD",
}


def launch_from_cmd(cmd):
    """Строка команды AGENTS.md → вариант запуска (аргументы godot.cmd) или None."""
    if not cmd or "godot.cmd" not in cmd:
        return None
    cmd = re.sub(r"\[[^\]]*\]", " ", cmd)
    cmd = re.sub(r"<[^>]*>", " ", cmd)
    toks = cmd.split()
    env = {}
    while toks and re.match(r"^[A-Z_][A-Z0-9_]*=", toks[0]):
        k, v = toks.pop(0).split("=", 1)
        env[k] = v.strip('"')
    if not toks or not toks[0].endswith("godot.cmd"):
        return None
    args = [t for t in toks[1:] if t not in ("…", "...")]
    if "-s" in args or "--script" in args:
        return None
    scene = next((a for a in args if a.startswith("res://") and a.endswith(".tscn")), None)
    if not scene:
        return None
    tail = args[args.index("--") + 1:] if "--" in args else []
    if any('"' in t or t.endswith("=") or t == "id" for t in tail):
        return None
    tail = [os.path.basename(t[6:]) if t.startswith("res://") else t for t in tail]
    headless = "--headless" in args
    words = [ARG_WORDS.get(t, t) for t in tail]
    if words:
        label = ", ".join(words).capitalize()
    else:
        label = "Проверка без окна" if headless else "Открыть"
    if headless and words:
        label += " (без окна)"
    return {"label": label, "args": args, "env": env, "headless": headless, "scene": scene[6:],
            "needs_pair": any(t in ("host", "client", "c1", "c2") for t in tail)}


# ---------------------------------------------------------------- снимки docs/screens

SNAP_RE = [
    re.compile(r"docs/screens/([\w/\-]+?)_?\*"),
    re.compile(r"снимк\w*\s+(?:в\s+)?(?:docs/screens/)?([a-z0-9][\w/\-]*?)_?\*"),
    re.compile(r"→\s*docs/screens/([\w/\-]+?)(?:_?\*|/|\s|$)"),
    re.compile(r"docs/screens/([\w\-]+/)"),
]


def snapshot_prefixes(entry_texts):
    out = set()
    for t in entry_texts:
        for rx in SNAP_RE:
            for m in rx.finditer(t):
                p = m.group(1)
                if not p or p.startswith("<"):
                    continue
                if p.endswith("/"):
                    out.add(p)
                else:
                    out.add(p + "_" if not p.endswith("_") else p)
    return out


# ---------------------------------------------------------------- классификация

GROUPS = [
    ("raid", "Карты рейда"),
    ("hideout", "Убежище"),
    ("game", "Меню и экраны игры"),
    ("stand", "Стенды владельца"),
    ("walk", "Прогулки по черновикам карт"),
    ("test", "Автоматические проверки"),
    ("shots", "Снимки для просмотра"),
    ("perf", "Замеры скорости"),
    ("service", "Сборка и служебное"),
    ("part", "Детали карт, предметов и персонажа"),
    ("shelter_part", "Детали убежища"),
    ("launcher", "Запускалки без своей сцены"),
]
GROUP_TITLE = dict(GROUPS)


def classify(path, floors_scenes):
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    if path in floors_scenes:
        return "raid"
    if path == "scenes/levels/hideout.tscn" or re.match(r"levels/shelter/[^/]+\.tscn$", path):
        return "hideout"
    if path.startswith("levels/shelter/"):
        return "shelter_part"
    if path.startswith("scenes/ui/") and stem in ("main_menu", "loading_screen") or path == "scenes/net/lobby.tscn":
        return "game"
    if path.startswith("scenes/debug/"):
        return "stand" if stem != "development_lab_base" else "part"
    if path.startswith("scenes/"):
        if path.startswith("scenes/levels/") and path.count("/") == 2:
            return "walk"
        return "part"
    if not path.startswith("tools/"):
        return "part"
    if re.search(r"(_perf|perf_test|cpu_probe|mesh_census|performance_audit|ai_work_benchmark)$", stem):
        return "perf"
    if re.search(r"(_shots|_tour|trailer_capture|_capture)$", stem):
        return "shots"
    if re.search(r"^(author_|bake_|export_)|(icon_bake|raid_map_bake|sticker_icons|sector_stats|hand_fit_dump|smoke)$", stem):
        return "service"
    if re.search(r"(_study|_play|_stand|_gallery|^gallery|_bench|_playtest|_lab|scale_probe|parking_probe|ssr_probe|normal_probe|sight_inventory|hideout_move_probe)$", stem):
        return "stand"
    return "test"


# ---------------------------------------------------------------- сборка инвентаризации

def own_closure(repo, start, protected):
    """Файлы, которые принадлежат только этой сцене: всё, на что она ссылается и на что больше ничто живое не ссылается."""
    own = set(start)
    changed = True
    while changed:
        changed = False
        for f in list(own):
            for d in repo.refs_from.get(f, ()):
                if d in own or d in protected or d not in repo.fileset:
                    continue
                if d.endswith(".uid") or d.endswith(".import"):
                    continue
                if repo.under_dynamic(d):
                    continue
                others = [r for r in repo.referrers(d) if r not in own and ref_kind(r) not in ("doc", "agents", "build", "other")]
                if not others:
                    own.add(d)
                    changed = True
    for f in list(own):
        for side in (f + ".uid", f + ".import"):
            if side in repo.fileset:
                own.add(side)
    return own


def is_core_file(f, scene):
    """Файл стенда (уходит вместе со сценой) — сама сцена, её запускалка и всё из tools/; остальное — файлы игры."""
    base = f[:-4] if f.endswith(".uid") else f[:-7] if f.endswith(".import") else f
    if base == scene or base.endswith(".cmd"):
        return True
    return base.startswith("tools/") or base.startswith("scenes/debug/")


def root_script(repo, scene):
    t = repo.texts.get(scene, "")
    ext = {}
    for m in EXT_RES_RE.finditer(t):
        a = dict(ATTR_RE.findall(m.group(1)))
        ext[a.get("id", "")] = a.get("path", "")[6:] if a.get("path", "").startswith("res://") else a.get("path", "")
    m = re.search(r'\[node name="[^"]*"(?: type="[^"]*")?(?: [^\]]*)?\]\n((?:[^\[\n].*\n)*)', t)
    if not m or "parent=" in t[m.start():m.start() + 200].split("\n")[0]:
        return None, ext
    sm = re.search(r'script = ExtResource\("([^"]+)"\)', m.group(1))
    return (ext.get(sm.group(1)) if sm else None), ext


def labs_menu_lines(repo, scene):
    """Строки списка «Отладочные стенды» главного меню с этой сценой — их доска убирает и возвращает сама."""
    t = repo.texts.get("src/ui/main_menu.gd", "")
    stem = os.path.splitext(os.path.basename(scene))[0]
    if not scene.startswith("scenes/debug/") or ("res://" + scene) in t:
        return []
    lines = t.split("\n")
    out, inside = [], False
    for i, line in enumerate(lines):
        if line.startswith("func "):
            inside = line.startswith("func _show_labs")
        if inside and ('"%s"' % stem) in line:
            out.append(i + 1)
    return out


def missing_refs(repo, scene, ext):
    out = []
    for p in ext.values():
        if p and not p.startswith("uid://") and p not in repo.fileset:
            out.append(p)
    return sorted(set(out))


def script_doc(repo, script):
    """Первый комментарий-описание скрипта (строки ## или # в начале файла)."""
    t = repo.texts.get(script or "", "")
    out = []
    for line in t.split("\n")[:40]:
        s = line.strip()
        if s.startswith("#"):
            s = s.lstrip("#").strip()
            if s and not s.startswith("@"):
                out.append(s)
            continue
        if not s or s.startswith("@tool") or s.startswith("extends") or s.startswith("class_name"):
            if out and not s:
                break
            continue
        break
    return " ".join(out)


def short_title(text, fallback):
    t = text.strip()
    if not t:
        return fallback
    for sep in (":", " — ", ";", ". "):
        k = t.find(sep)
        if 3 < k <= 70:
            t = t[:k]
            break
    if len(t) > 70:
        t = t[:67].rsplit(" ", 1)[0] + "…"
    return t[0].upper() + t[1:]


def human_size(n):
    if n >= 1024 * 1024:
        return "%.1f МБ" % (n / 1024 / 1024)
    if n >= 1024:
        return "%d КБ" % (n // 1024)
    return "%d Б" % n


def build(root):
    t0 = time.time()
    repo = Repo(root)
    repo.scan()
    notes = {}
    npath = os.path.join(HERE, "notes.json")
    if os.path.isfile(npath):
        with open(npath, encoding="utf-8") as f:
            notes = json.load(f).get("items", {})

    floors = json.loads(repo.texts.get("data/floors.json", "{}") or "{}").get("floors", [])
    floors_scenes = {fl["scene"][6:]: fl for fl in floors if fl.get("scene", "").startswith("res://")}
    project = repo.texts.get("project.godot", "")
    main_scene = (re.search(r'run/main_scene="res://([^"]+)"', project) or [None, ""])[1]
    protected = set(re.findall(r'"\*?res://([^"]+)"', project))
    protected.add("project.godot")
    protected.add("AGENTS.md")
    agents = parse_agents(repo)

    scenes = sorted(f for f in repo.files if f.endswith(".tscn"))
    cmds = sorted(f for f in repo.files if f.endswith(".cmd") and (f.count("/") == 0 or f.startswith("tools/") and f.count("/") == 1))

    # какие .cmd запускают какие сцены
    cmd_scenes = {}
    for c in cmds:
        targets = [d for d in repo.refs_from.get(c, ()) if d.endswith(".tscn")]
        cmd_scenes[c] = sorted(targets)

    # снимки: префиксы из строк AGENTS.md и имени сцены, снимок — самому длинному префиксу
    prefixes = {}
    for s in scenes:
        if not s.startswith("tools/") and not s.startswith("scenes/debug/") and not s.startswith("scenes/levels/"):
            continue
        texts = []
        for en in agents:
            if s in en["scenes"] or os.path.basename(s) in en["names"]:
                texts.extend(en["text"])
        pre = snapshot_prefixes(texts)
        stem = os.path.splitext(os.path.basename(s))[0]
        base = re.sub(r"_(shots|test|check|tour|probe|perf|study|stand|gallery|lab|play)$", "", stem)
        if base != stem or s.startswith("scenes/debug/"):
            pre.add(base + "_")
        prefixes[s] = pre
    screens = [f for f in repo.files if f.startswith("docs/screens/") and ext_of(f) in (".png", ".jpg", ".jpeg", ".webp")]
    snap_owner = {}
    for img in screens:
        rel = img[len("docs/screens/"):]
        best, best_len = set(), 0
        for s, pre in prefixes.items():
            for p in pre:
                if rel.startswith(p) and len(p) > best_len:
                    best, best_len = {s}, len(p)
                elif rel.startswith(p) and len(p) == best_len:
                    best.add(s)
        # у снимка один хозяин; спорный (одинаковое начало имени у двух стендов) — ничей
        if len(best) == 1:
            snap_owner.setdefault(best.pop(), []).append(img)

    items = []
    claimed_cmds = set()
    for s in scenes:
        kind = classify(s, floors_scenes)
        script, ext = root_script(repo, s)
        stem = os.path.splitext(os.path.basename(s))[0]
        ents = [en for en in agents if s in en["scenes"] or os.path.basename(s) in en["names"]]
        own_entries = [en for en in ents if s in en["scenes"]]
        # запускалки .cmd, которые открывают только эту сцену, уходят вместе с ней
        own_cmds = [c for c, t in cmd_scenes.items() if t == [s] and c not in ("RING.cmd", "EDITOR.cmd")]
        claimed_cmds.update(own_cmds)
        own = own_closure(repo, {s} | set(own_cmds), protected)
        for c in own_cmds:
            own.add(c)
        refs = repo.referrers(s) | repo.dynamic_users(s)
        refs -= own
        launches, seen = [], set()
        for c in own_cmds:
            launches.append({"label": "Как обычно (%s)" % os.path.basename(c), "cmd": c})
        for en in own_entries:
            lo = launch_from_cmd(en["cmd"])
            if lo and lo["scene"] == s:
                key = " ".join(lo["args"]) + json.dumps(lo["env"], sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    launches.append(lo)
        if not launches and kind not in ("part", "shelter_part"):
            hl = kind == "test"
            args = (["--headless"] if hl else ["--windowed", "--resolution", "1600x900"]) + ["res://" + s]
            launches.append({"label": "Проверка без окна" if hl else "Открыть", "args": args, "env": {}, "headless": hl,
                             "scene": s, "guess": True, "needs_pair": False})
        for lo in launches:
            if lo.get("label") == "Проверка без окна" and kind != "test":
                lo["label"] = "Запустить без окна"
        sources = []
        for c in cmds:
            if s in cmd_scenes.get(c, []):
                sources.append({"kind": "cmd", "text": "Запускалка %s" % c, "file": c})
        if s in floors_scenes:
            sources.append({"kind": "floors", "text": "Маршрут рейда «%s» (data/floors.json)" % floors_scenes[s]["name"]})
        if s == main_scene:
            sources.append({"kind": "main", "text": "Стартовая сцена игры (project.godot)"})
        if "src/ui/main_menu.gd" in refs:
            sources.append({"kind": "menu", "text": "Главное меню игры"})
        if "src/core/balance.gd" in refs:
            sources.append({"kind": "game", "text": "Игра открывает её сама (src/core/balance.gd)"})
        if kind in ("hideout", "part", "shelter_part", "walk"):
            hosts = sorted(r for r in refs if r.endswith(".tscn") and not r.startswith("tools/"))
            if hosts:
                more = " и ещё %d" % (len(hosts) - 3) if len(hosts) > 3 else ""
                sources.append({"kind": "scene", "text": "Входит в " + ", ".join(hosts[:3]) + more})
        for en in ents:
            sources.append({"kind": "agents", "text": "AGENTS.md, строка %d" % (en["start"] + 1), "line": en["start"] + 1})
        ref_list = []
        for r in sorted(refs):
            k = ref_kind(r)
            if k == "agents":
                continue
            ref_list.append({"file": r, "kind": k})
        menu_lines = labs_menu_lines(repo, s) if "src/ui/main_menu.gd" in refs else []
        for x in ref_list:
            if x["kind"] == "menu" and not menu_lines:
                x["kind"] = "code"
        blocking = [x for x in ref_list if x["kind"] in BLOCKING and x["kind"] != "menu"]
        game_used = any(not x["file"].startswith("tools/") for x in blocking)
        own_sorted = sorted(own)
        core = set(f for f in own_sorted if is_core_file(f, s))
        snaps = sorted(snap_owner.get(s, []))
        thumb = None
        if snaps:
            imgs = [x for x in snaps if ext_of(x) in (".png", ".jpg", ".jpeg")]
            if imgs:
                thumb = max(imgs, key=lambda x: os.path.getmtime(repo.p(x)))
        # у карт рейда — план сверху из «Плана рейда» (tools/raid_map_bake.tscn)
        if s in floors_scenes and ("assets/maps/%s.webp" % floors_scenes[s]["id"]) in repo.fileset:
            thumb = "assets/maps/%s.webp" % floors_scenes[s]["id"]
        dates = [repo.last_commit.get(f, "") for f in own_sorted if f in repo.tracked]
        desc_agents = " ".join(en["comment"] for en in own_entries if en["comment"] and not en["hash"]).strip()
        desc_script = script_doc(repo, script)
        note = notes.get(s, {})
        desc = note.get("desc") or desc_agents or desc_script
        head = desc_agents if desc_agents and not desc_agents.startswith("+") else desc_script
        title = note.get("title") or short_title(head or desc_agents, stem.replace("_", " "))
        flags = list(note.get("flags", []))
        if s in repo.untracked:
            flags.append("new")
        if any(f in repo.changed for f in own_sorted):
            flags.append("changed")
        if not ents and kind in ("stand", "test", "shots", "perf", "service", "walk"):
            flags.append("no_agents")
        miss = missing_refs(repo, s, ext)
        if miss:
            flags.append("broken")
        if kind in ("part", "shelter_part") and not ref_list:
            flags.append("unused")
        items.append({
            "id": s, "type": "scene", "kind": kind, "group": GROUP_TITLE[kind], "title": title, "desc": desc,
            "note": note.get("note", ""), "keep": bool(note.get("keep")), "script": script,
            "flags": flags, "sources": sources, "refs": ref_list, "blocking": len(blocking), "game_used": game_used,
            "menu_lines": menu_lines,
            "own": [{"file": f, "size": repo.sizes.get(f, 0), "tracked": f in repo.tracked, "changed": f in repo.changed,
                     "core": f in core} for f in own_sorted],
            "own_size": sum(repo.sizes.get(f, 0) for f in own_sorted),
            "snapshots": [{"file": f, "size": repo.sizes.get(f, 0)} for f in snaps],
            "snap_size": sum(repo.sizes.get(f, 0) for f in snaps),
            "thumb": thumb, "launches": launches, "missing": miss,
            "last_commit": max(dates) if dates else "", "agents_lines": [en["start"] + 1 for en in ents],
            "agents_own": [en["start"] + 1 for en in own_entries if all(x == s for x in en["scenes"])
                           and all(n == os.path.basename(s) for n in en["names"])],
        })

    # запускалки без своей сцены (или на несколько сцен)
    for c in cmds:
        if c in claimed_cmds:
            continue
        note = notes.get(c, {})
        txt = repo.texts.get(c, "")
        rem = " ".join(l.strip()[4:].strip() for l in txt.splitlines() if l.strip().lower().startswith("rem "))
        refs = [{"file": r, "kind": ref_kind(r)} for r in sorted(repo.referrers(c)) if ref_kind(r) != "agents"]
        items.append({
            "id": c, "type": "cmd", "kind": "launcher", "group": GROUP_TITLE["launcher"],
            "title": note.get("title") or os.path.basename(c), "desc": note.get("desc") or rem[:400],
            "note": note.get("note", ""), "keep": bool(note.get("keep")), "script": None, "flags": list(note.get("flags", [])),
            "sources": [{"kind": "scene", "text": "Открывает %s" % t} for t in cmd_scenes.get(c, [])],
            "refs": refs, "blocking": len([x for x in refs if x["kind"] in BLOCKING]), "game_used": False, "menu_lines": [],
            "own": [{"file": c, "size": repo.sizes.get(c, 0), "tracked": c in repo.tracked, "changed": c in repo.changed,
                     "core": True}],
            "own_size": repo.sizes.get(c, 0), "snapshots": [], "snap_size": 0, "thumb": None,
            "launches": [{"label": "Запустить", "cmd": c}] if c not in ("tools/godot.cmd", "tools/smoke.cmd") else [],
            "missing": [], "last_commit": repo.last_commit.get(c, ""), "agents_lines": [], "agents_own": [],
        })

    # удалённые в рабочей копии, но не из git (кто-то убрал руками и не закоммитил)
    gone = sorted(f for f in repo.deleted if f.endswith(".tscn"))

    # данные карт: кто пользуется
    data_files = sorted(f for f in repo.files if (f.startswith("data/blockouts/") or f.startswith("data/sectors/")))
    owner_of = {}
    for it in items:
        for o in it["own"]:
            owner_of[o["file"]] = it["id"]
    data = []
    for f in data_files:
        users = sorted(r for r in repo.referrers(f) if ref_kind(r) not in ("doc", "agents"))
        data.append({"file": f, "size": repo.sizes.get(f, 0), "owner": owner_of.get(f), "users": users,
                     "last_commit": repo.last_commit.get(f, "")})

    order = {k: i for i, (k, _) in enumerate(GROUPS)}
    items.sort(key=lambda x: (order[x["kind"]], x["id"]))
    return {
        "generated": time.strftime("%Y-%m-%d %H:%M"), "repo": repo.root, "seconds": round(time.time() - t0, 1),
        "groups": [{"kind": k, "title": t} for k, t in GROUPS], "items": items, "gone": gone, "data": data,
        "main_scene": main_scene,
    }


# ---------------------------------------------------------------- отчёт для людей и агентов

FLAG_TEXT = {
    "old": "устарело", "new": "не в git", "changed": "есть несохранённые правки", "no_agents": "нет в AGENTS.md",
    "broken": "ссылается на отсутствующие файлы", "unused": "никем не используется", "active": "в работе",
    "dup": "дубль",
}
KIND_TEXT = {"scene": "сцена", "code": "код", "data": "данные", "cmd": "запускалка", "menu": "главное меню",
             "build": "скрипт сборки", "doc": "документ", "other": "прочее"}


def write_md(inv, path):
    out = ["# Сцены, стенды и уровни RING — инвентаризация", "",
           "Собрано `tools/scene_board/inventory.py` %s. Смотреть и убирать — «Доска сцен» (`SCENE_BOARD.cmd`)." % inv["generated"],
           "Колонки: что это, откуда запускают, кто ссылается (живые ссылки — сцены, код, данные, запускалки; "
           "документы не считаются), сколько файлов принадлежат только ей, последняя правка.", ""]
    by = defaultdict(list)
    for it in inv["items"]:
        by[it["kind"]].append(it)
    for g in inv["groups"]:
        lst = by.get(g["kind"], [])
        if not lst:
            continue
        out.append("## %s (%d)" % (g["title"], len(lst)))
        out.append("")
        if g["kind"] == "shelter_part":
            unused = [it for it in lst if "unused" in it["flags"]]
            out.append("Вставляются в сцены убежища. Всего %d, никем не используются — %d:" % (len(lst), len(unused)))
            out.append("")
            for it in unused:
                out.append("- `%s` — %s" % (it["id"], human_size(it["own_size"])))
            out.append("")
            continue
        out.append("| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |")
        out.append("|---|---|---|---|---|---|---|")
        for it in lst:
            src = "; ".join(s["text"] for s in it["sources"]) or "—"
            live = [r for r in it["refs"] if r["kind"] in BLOCKING]
            refs = ", ".join("`%s`" % r["file"] for r in live[:4]) + (" и ещё %d" % (len(live) - 4) if len(live) > 4 else "")
            flags = ", ".join(FLAG_TEXT.get(f, f) for f in it["flags"])
            if it["keep"]:
                flags = ("не убирать" + (", " + flags if flags else ""))
            desc = (it["title"] + (" — " + it["note"] if it["note"] else "")).replace("|", "/")
            out.append("| `%s` | %s | %s | %s | %d, %s | %s | %s |" % (
                it["id"], desc, src.replace("|", "/"), refs or "—", len(it["own"]), human_size(it["own_size"]),
                it["last_commit"] or "—", flags or ""))
        out.append("")
    if inv["gone"]:
        out.append("## Удалены в рабочей копии, но не из git")
        out.append("")
        for g in inv["gone"]:
            out.append("- `%s`" % g)
        out.append("")
    out.append("## Данные карт (data/blockouts, data/sectors)")
    out.append("")
    out.append("| Файл | Чей | Кто читает | Размер | Правка |")
    out.append("|---|---|---|---|---|")
    for d in inv["data"]:
        out.append("| `%s` | %s | %s | %s | %s |" % (d["file"], ("`%s`" % d["owner"]) if d["owner"] else "общий",
                                                 ", ".join("`%s`" % u for u in d["users"][:4]) or "—",
                                                 human_size(d["size"]), d["last_commit"] or "—"))
    out.append("")
    data = ("\n".join(out)).encode("utf-8")
    for attempt in range(5):
        try:
            with open(path, "wb") as f:
                f.write(data)
            return
        except OSError:
            time.sleep(1)


def main():
    repo = os.path.abspath(os.path.join(HERE, "..", ".."))
    if "--repo" in sys.argv:
        repo = sys.argv[sys.argv.index("--repo") + 1]
    inv = build(repo)
    cnt = defaultdict(int)
    for it in inv["items"]:
        cnt[it["group"]] += 1
    print("собрано за %.1f с" % inv["seconds"])
    for g, n in cnt.items():
        print("  %-40s %d" % (g, n))
    if "--md" in sys.argv:
        write_md(inv, os.path.join(repo, "docs", "scene_inventory.md"))
        print("отчёт: docs/scene_inventory.md")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(inv, f, ensure_ascii=False, indent=1)
        print("json:", out)


if __name__ == "__main__":
    main()
