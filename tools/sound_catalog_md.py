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
WEAPONS = ROOT / "data" / "weapons.json"
WEAPON_SLOTS = ROOT / "data" / "weapon_sound_slots.json"
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


def slot_applies(slot: dict, weapon: dict) -> bool:
    condition = slot.get("condition", "all")
    internal = "internal_mag" in weapon
    action = weapon.get("action", "")
    if condition == "suppressible":
        return bool(weapon.get("integral", {}).get("suppressed")) or "muzzle" in weapon.get("mounts", {})
    if condition == "detachable_mag":
        return not internal
    if condition == "internal_mag":
        return internal
    if condition == "manual_cycle":
        return bool(weapon.get("cycle_sound"))
    if condition == "break_action":
        return action == "break"
    if condition == "not_break_action":
        return action != "break"
    if condition == "automatic":
        return bool(weapon.get("stats", {}).get("auto"))
    return True


CLASS_ORDER = ["PISTOL", "SMG", "PDW", "ASSAULT_RIFLE", "CARBINE", "BATTLE_RIFLE", "DMR", "SNIPER", "SPECIAL", "LMG", "SHOTGUN"]
CLASS_NAMES = {"PISTOL": "Пистолеты", "SMG": "Пистолеты-пулемёты", "PDW": "PDW", "SHOTGUN": "Ружья",
               "ASSAULT_RIFLE": "Автоматы", "CARBINE": "Карабины", "BATTLE_RIFLE": "Боевые винтовки",
               "DMR": "Марксманские", "SNIPER": "Снайперские", "SPECIAL": "Специальные", "LMG": "Пулемёты"}


def weapon_fallback(weapon: dict, fallback: str) -> str:
    """Тот же запасной набор, что WeaponDb._weapon_sound_fallback."""
    shot = weapon.get("sound", "")
    if fallback == "$shot":
        return shot
    if fallback == "$shot_far":
        if shot.startswith("shot_hg_") or shot == "shot_pistol":
            return "shot_pistol@far"
        for k in ("shot_smg", "shot_ak762", "shot_shotgun", "shot_bolt"):
            if shot == k:
                return k + "@far"
        return "shot_rifle@far"
    if fallback == "$suppressed":
        if weapon.get("caliber") == "9x39":
            return "shot_sup939"
        if weapon.get("class") in ("PISTOL", "SMG", "PDW"):
            return "shot_pistol_sup"
        if weapon.get("class") == "SHOTGUN":
            return weapon.get("sound", "shot_shotgun")
        return "shot_rifle_sup"
    if fallback == "$mechanism":
        return "mech_pistol" if weapon.get("class") == "PISTOL" else "mech_rifle"
    if fallback == "$reload":
        return weapon.get("reload_sound", "reload_rifle")
    if fallback == "$cycle":
        return weapon.get("cycle_sound", "bolt")
    return fallback


def borrowed(sounds: list[dict], ref: str) -> tuple[str, int]:
    """Чем звучит слот без своих записей: идём по цепочке fallback каталога до набора с записями."""
    by_id = {s["id"]: s for s in sounds}
    by_kind: dict[str, dict] = {}
    for s in sounds:
        by_kind.setdefault(s["kind"], s)
    cur = by_id.get(ref) or by_kind.get(ref)
    for _ in range(8):
        if not cur:
            return ("", 0)
        n = recorded(cur["file"])
        if n:
            return (cur["name"].split(" — ")[0], n)
        nxt = cur.get("fallback", "")
        cur = by_id.get(nxt) or by_kind.get(nxt)
    return ("", 0)


def weapon_matrix(sounds: list[dict], weapons: dict, slots: list[dict], families: dict) -> list[str]:
    own_slots = [s for s in slots if not s.get("shared") and s.get("wired")]
    shared = [s for s in slots if s.get("shared") and not s.get("family")]
    fam_slots = [s for s in slots if s.get("family")]
    out = ["## Оружие по моделям — чего нет", "",
           "Своя запись модели лежит в `assets/audio/guns/<модель>_<слот>_NN` (модель — id без `wpn_`) и заменяет",
           "общий набор только у неё. В клетке: **N** — своих записей; «как …» — пока звучит чужим набором",
           "(сколько в нём записей); **тишина** — игра зовёт, а звучать нечему; «—» — у конструкции такого нет.", ""]
    head = "| Ствол | Калибр | " + " | ".join(s["name"] for s in own_slots) + " |"
    out += [head, "|" + "---|" * (len(own_slots) + 2)]
    silent: dict[str, list[str]] = {}
    wrong: dict[str, list[str]] = {}
    by_class: dict[str, list[str]] = {}
    for wid, item in weapons.items():
        by_class.setdefault(item["weapon"].get("class", ""), []).append(wid)
    order = [c for c in CLASS_ORDER if c in by_class] + [c for c in by_class if c not in CLASS_ORDER]
    for cls in order:
        out.append(f"| **{CLASS_NAMES.get(cls, cls)}** |" + " |" * (len(own_slots) + 1))
        for wid in by_class[cls]:
            item = weapons[wid]
            w = item["weapon"]
            stem = wid.removeprefix("wpn_")
            cells = []
            for slot in own_slots:
                if not slot_applies(slot, w):
                    cells.append("—")
                    continue
                n = recorded(f"guns/{stem}_{slot['file']}_")
                if n:
                    cells.append(f"**{n}**")
                    continue
                name, m = borrowed(sounds, weapon_fallback(w, slot.get("fallback", "")))
                if m:
                    cells.append(f"как {name} ({m})")
                    if slot["id"] == "shot":
                        wrong.setdefault(name, []).append(item["name"])
                else:
                    cells.append("**тишина**")
                    silent.setdefault(slot["name"], []).append(item["name"])
            out.append(f"| {item['name']} | {w.get('caliber', '')} | " + " | ".join(cells) + " |")
    out += ["", "### Магазин, затвор, спуск — по семействам механики", "",
            "Запись семейства — `assets/audio/guns/fam_<семейство>_<действие>_NN`; звучит у каждого ствола семейства,",
            "пока у ствола нет своей (`guns/<модель>_<действие>_NN`). Без записей семейства — общий звук действия.",
            "В клетке: **N** — записей семейства; «общий» — пока звучит общим; «—» — в семействе такого действия нет.", ""]
    fam_ids = list(families)
    out += ["| Действие | " + " | ".join(families[f]["name"] for f in fam_ids) + " |", "|" + "---|" * (len(fam_ids) + 1)]
    for slot in fam_slots:
        cells = []
        for f in fam_ids:
            members = [weapons[w]["weapon"] for w in families[f]["weapons"] if w in weapons]
            if not any(slot_applies(slot, w) for w in members):
                cells.append("—")
                continue
            n = recorded(f"guns/fam_{f}_{slot['file']}_")
            cells.append(f"**{n}**" if n else "общий")
        out.append(f"| {slot['name']} | " + " | ".join(cells) + " |")
    out += ["", "Состав: " + "; ".join(f"{families[f]['name']} — " + ", ".join(weapons[w]["name"] for w in families[f]["weapons"] if w in weapons) for f in fam_ids) + "."]
    out += ["", "### Общие для всех стволов действия", "",
            "Один звук на всё оружие (и запасной для семейств) — раздел «Обращение с оружием — общее» на стенде.", "",
            "| Действие | Когда | Сейчас звучит | В игре |", "|---|---|---|---|"]
    for slot in shared:
        name, m = borrowed(sounds, slot.get("fallback", ""))
        now = f"как {name} ({m})" if m else ("синтез" if slot.get("fallback") else "тишина")
        out.append(f"| {slot['name']} | {slot['when']} | {now} | {'да' if slot.get('wired') else 'механики ещё нет'} |")
    out += ["", "### Что записывать в первую очередь", ""]
    for name, guns in sorted(wrong.items(), key=lambda kv: -len(kv[1])):
        out.append(f"- Выстрел «как {name}» у {len(guns)}: " + ", ".join(guns) + ".")
    for name, guns in silent.items():
        out.append(f"- **Тишина** — «{name}» у {len(guns)} стволов.")
    out.append("")
    return out


def main() -> None:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    sounds = data["sounds"]
    weapons = json.loads(WEAPONS.read_text(encoding="utf-8"))["weapons"]
    slot_data = json.loads(WEAPON_SLOTS.read_text(encoding="utf-8"))
    slots = slot_data["slots"]
    families = slot_data.get("families", {})
    weapon_slot_count = sum(1 for item in weapons.values() for slot in slots
                            if slot_applies(slot, item["weapon"]))
    lines = [
        "# Звуки игры — полный список",
        "",
        "Собрано из `data/sound_catalog.json` (`python tools/sound_catalog_md.py`). Слушать, сравнивать",
        "варианты и отбирать новые — стенд `tools/godot.cmd res://tools/sound_bench.tscn` (папка `_sound_try/`).",
        "Рабочий путь в стенде: положить ogg/wav/mp3 или целую папку генератора во входящие → выбрать звук",
        "в каталоге → назначить (назначение хранится отдельно и никогда не меняет исходные папки и имена),",
        "прослушать и одобрить кандидат → указать источник с CC0/CC-BY (или «собственный звук») → добавить в",
        "проект. Стенд отдельно показывает, подключён ли выбранный звук к игровому событию: запись без такого",
        "вызова сохранится в библиотеке, но сама по себе в геймплее не появится.",
        "Во вкладке входящих слева показано точное дерево исходных подпапок; справа — только выбранная папка",
        "или файл. У каждого файла есть индикатор назначения/одобрения. Всю выбранную папку можно",
        "назначить игровому звуку разом, а",
        "одинаковый источник и лицензию — заполнить сразу у всех ещё пустых карточек.",
        "У каждой уже добавленной записи есть переключатель «Использовать в игре»: снятая галочка исключает",
        "её из случайного выбора без удаления файла; решение хранится в `data/sound_active.json`.",
        "Если вариант точно не нужен, кнопка «Удалить навсегда» после подтверждения удаляет входящий и/или",
        "готовый аудиофайл, `.import`, данные отбора и соответствующую строку `assets/CREDITS.md`.",
        "Если генератор сложил несколько вариантов в один файл, «Разрезать по паузам» находит отдельные",
        "участки и создаёт из них самостоятельные WAV с тем же назначением, источником и лицензией.",
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
    lines.append(f"Отдельно автоматически собрано **{weapon_slot_count} помодельных слотов** для "
                 f"{len(weapons)} единиц оружия; их источники — `data/weapons.json` и "
                 "`data/weapon_sound_slots.json`. Своя запись заменяет общий запасной набор только у одной модели.")
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
        lines += [f"## {cat}", ""]
        group = None
        for s in rows:
            # подгруппы раздела — в порядке каталога (поле group)
            if s.get("group", "") != group:
                group = s.get("group", "")
                lines += ["", f"### {group}", "", "| Звук | Когда | Файл | Вид | Тип | Вар. | Важн. | Записей | Сейчас |",
                          "|---|---|---|---|---|---|---|---|---|"]
            lines.append(f"| {s['name']} | {s['when']} | `{s['file']}` | {s['kind'] or '—'} | {TYPES[s['type']]} "
                         f"| {s['variants']} | {PRIO[s['prio']]} | {recorded(s['file'])} | {s['now']} |")
        lines.append("")
    lines += weapon_matrix(sounds, weapons, slots, families)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {total} звуков")


if __name__ == "__main__":
    main()
