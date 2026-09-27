"""Список всех звуков игры для чтения: data/sound_catalog.json → docs/sound_catalog.md.

Использование: python tools/sound_catalog_md.py
Слушать и отбирать — на стенде: tools/godot.cmd res://tools/sound_bench.tscn
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "data" / "sound_catalog.json"
OUT = ROOT / "docs" / "sound_catalog.md"
AUDIO = ROOT / "assets" / "audio"
ACTIVE = ROOT / "data" / "sound_active.json"
TYPES = {"one": "разовый", "loop": "луп", "layer": "слой"}
PRIO = {1: "база", 2: "важно", 3: "детали"}

active_data = json.loads(ACTIVE.read_text(encoding="utf-8")) if ACTIVE.exists() else {"disabled": []}
DISABLED = {str(path).replace("\\", "/") for path in active_data.get("disabled", [])}


def recorded(prefix: str) -> int:
    group, head = prefix.split("/")
    d = AUDIO / group
    if not d.is_dir():
        return 0
    pat = re.compile(re.escape(head) + r"\d+$")
    return sum(1 for f in d.iterdir() if f.suffix.lower() in (".ogg", ".wav", ".mp3")
               and pat.match(f.stem) and f"{group}/{f.name}" not in DISABLED)


def main() -> None:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    sounds = data["sounds"]
    lines = [
        "# Звуки игры — полный список",
        "",
        "Собрано из `data/sound_catalog.json` (`python tools/sound_catalog_md.py`). Слушать, сравнивать",
        "варианты и отбирать новые — стенд `tools/godot.cmd res://tools/sound_bench.tscn` (папка `_sound_try/`).",
        "Рабочий путь в стенде: положить ogg/wav/mp3 или целую папку генератора во входящие → выбрать звук",
        "в каталоге → назначить (стенд рекурсивно найдёт файлы и сохранит их исходный путь до назначения),",
        "прослушать и одобрить кандидат → указать источник с CC0/CC-BY (или «собственный звук») → добавить в",
        "проект. Стенд отдельно показывает, подключён ли выбранный звук к игровому событию: запись без такого",
        "вызова сохранится в библиотеке, но сама по себе в геймплее не появится.",
        "Варианты сгруппированы по исходным подпапкам: всю папку можно назначить выбранному звуку разом, а",
        "одинаковый источник и лицензию — заполнить сразу у всех ещё пустых карточек.",
        "У каждой уже добавленной записи есть переключатель «Использовать в игре»: снятая галочка исключает",
        "её из случайного выбора без удаления файла; решение хранится в `data/sound_active.json`.",
        "У моделей оружия могут быть отдельные наборы с общим запасным: первая своя запись заменяет общий",
        "набор только у выбранной модели.",
        "",
        "Файл — префикс в `assets/audio`: записи «префикс + номер» (`guns/carbine_04.ogg`), игра берёт",
        "случайную, подряд одна не повторяется. «Вид» — каким звуком игра это играет сейчас (`Audio.play`);",
        "пусто — код его ещё не зовёт. Важность: база — без этого игра звучит бедно; важно — заметно",
        "добавляет; детали — полировка.",
        "",
    ]
    total = len(sounds)
    rec = sum(1 for s in sounds if recorded(s["file"]) > 0)
    wired = sum(1 for s in sounds if s["kind"])
    lines.append(f"Всего **{total}** звуков: с записями {rec}, код зовёт {wired}, "
                 + ", ".join(f"{PRIO[p]} — {sum(1 for s in sounds if s['prio'] == p)}" for p in (1, 2, 3)) + ".")
    absent = [x for x in sounds if not x["kind"] and recorded(x["file"]) == 0]
    lines += [f"В игре нет — **{len(absent)}** (своей записи нет и код их не зовёт; где-то пока звучит замена —"
              " см. «Сейчас» в таблицах):", ""]
    for cat in data["cats"]:
        names = [x["name"] for x in absent if x["cat"] == cat]
        if names:
            lines.append(f"- **{cat}** ({len(names)}): " + "; ".join(names) + ".")
    lines.append("")
    for cat in data["cats"]:
        rows = [s for s in sounds if s["cat"] == cat]
        lines += [f"## {cat}", "", "| Звук | Когда | Файл | Вид | Тип | Вар. | Важн. | Записей | Сейчас |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s in rows:
            lines.append(f"| {s['name']} | {s['when']} | `{s['file']}` | {s['kind'] or '—'} | {TYPES[s['type']]} "
                         f"| {s['variants']} | {PRIO[s['prio']]} | {recorded(s['file'])} | {s['now']} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {total} звуков")


if __name__ == "__main__":
    main()
