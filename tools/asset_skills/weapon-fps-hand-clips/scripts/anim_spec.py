"""Памятка видов анимаций и файл ответов владельца anim-spec.json (навык weapon-fps-hand-clips).

  python -X utf8 anim_spec.py catalog [вид]                 памятка для владельца (markdown); вид — pistol, rifle, smg, bolt,
                                                            shotgun, lmg, launcher (без него — все пункты)
  python -X utf8 anim_spec.py new <anim-spec.json> <id ствола> <название> <вид>
                                                            заготовка: все пункты памятки этого вида, need "?" и черновые фазы
  python -X utf8 anim_spec.py check <anim-spec.json>        проверка и выжимка для asset-state.md (markdown)

Обычный Python, без Blender. Файл пишется в UTF-8 с LF.
"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = json.loads((HERE.parent / "references/animation-catalog.json").read_text(encoding="utf-8"))
NEED_RU = {"yes": "нужно", "no": "не нужно", "later": "позже", "?": "не спрошено"}


def fits(item, kind):
    return kind is None or item["applies"] == "all" or kind in item["applies"]


def catalog(kind=None):
    out = [f"# Виды анимаций рук — памятка ({CATALOG['kinds'].get(kind, 'все виды оружия')})", ""]
    n = 0
    for g, g_ru in CATALOG["groups"].items():
        items = [it for it in CATALOG["items"] if it["group"] == g and fits(it, kind)]
        if not items:
            continue
        out += [f"## {g_ru}", ""]
        for it in items:
            n += 1
            line = f"{n}. **{it['title']}**"
            if it.get("game") and it["game"] != "—":
                line += f" — в игре: {it['game']}"
            out.append(line)
        out.append("")
    out.append("По каждому пункту: нужно / не нужно / позже. Чего нет в списке — допишите своё.")
    return "\n".join(out)


def new(path, weapon, name, kind):
    p = Path(path)
    if p.exists():
        sys.exit(f"{p} уже есть — правьте его, заготовка не перезаписывает")
    spec = {
        "weapon": weapon, "name": name, "kind": kind, "created": date.today().isoformat(), "status": "interview",
        "style": {"reference": "", "words": "", "tempo": ""},
        "interview": [],
        "clips": [{"id": it["id"], "title": it["title"], "group": it["group"], "need": "?",
                   "phases": [dict(ph, owner=False) for ph in it["phases"]],
                   "blender": it.get("blender", ""), "game": it.get("game", ""), "notes": ""}
                  for it in CATALOG["items"] if fits(it, kind)],
        "game_questions": [],
        "accepted": False,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("создан", p, "пунктов", len(spec["clips"]))


def check(path):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    errs, out = [], [f"### Анимации рук: ответы владельца ({spec.get('name', '?')}, {spec.get('weapon', '?')})", ""]
    st = spec.get("style", {})
    if not st.get("words"):
        errs.append("не записан характер движения (style.words)")
    out.append(f"Характер: {st.get('words') or '—'}; образец: {st.get('reference') or '—'}; темп: {st.get('tempo') or '—'}")
    out.append("")
    counts = {}
    for c in spec.get("clips", []):
        need = c.get("need", "?")
        counts[need] = counts.get(need, 0) + 1
        if need not in NEED_RU:
            errs.append(f"{c['id']}: need = {need!r} (ждём yes / no / later)")
        if need == "?":
            errs.append(f"{c['id']}: владельца не спросили")
        if need != "yes":
            continue
        marks = [ph.get("mark", "") for ph in c.get("phases", [])]
        if len(set(marks)) != len(marks):
            errs.append(f"{c['id']}: имена фаз повторяются")
        if c.get("group") in ("owner", "ideas") and not any(q.get("clip") == c["id"] for q in spec.get("game_questions", [])):
            errs.append(f"{c['id']}: «живая» анимация без вопроса к игре (когда и как часто срабатывает)")
        out.append(f"- **{c['title']}** (`{c['id']}`)")
        for i, ph in enumerate(c.get("phases", []), 1):
            out.append(f"  {i}. {ph.get('text', '')} — `{ph.get('mark', '')}`" + (" (владелец)" if ph.get("owner") else ""))
        for key, ru in (("blender", "Blender"), ("game", "игра"), ("notes", "заметки")):
            if c.get(key):
                out.append(f"  {ru}: {c[key]}")
    later = [c["title"] for c in spec.get("clips", []) if c.get("need") == "later"]
    if later:
        out += ["", "Позже: " + "; ".join(later)]
    qs = spec.get("game_questions", [])
    if qs:
        out += ["", "Вопросы к коду игры (не к Blender):"] + [f"- {q.get('clip', '')}: {q.get('q', '')} — {q.get('a') or 'ответа нет'}" for q in qs]
    out += ["", "Счёт: " + ", ".join(f"{NEED_RU.get(k, k)} {v}" for k, v in counts.items())]
    print("\n".join(out))
    if errs:
        print("\nНЕ ГОТОВО:\n" + "\n".join("- " + e for e in errs))
        sys.exit(1)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "catalog":
        print(catalog(a[1] if len(a) > 1 else None))
    elif len(a) == 5 and a[0] == "new":
        new(*a[1:])
    elif len(a) == 2 and a[0] == "check":
        check(a[1])
    else:
        print(__doc__)
        sys.exit(2)
