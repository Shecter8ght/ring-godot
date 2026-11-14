#!/usr/bin/env python
"""«Проспект»: лут по виду контейнера (docs/design/loot_matrix_v2.md §3, §5.1).

Каждому месту Loot_N сцены scenes/levels/prospekt.tscn назначается вид контейнера (weapon_crate, ammo_crate, …)
и таблица этого вида (таблица = вид). Назначение идёт по подписи места (поле note плана data/blockouts/prospekt.json →
loot), прежней таблице и виду (kind плана). Не меняются: схроны, тела, кассы, сейф ювелира, сейф директора, стойка
консьержа, склад «Яруса» с ключом, главарь банка — всё, что завязано на пролог, ключи и задания.

Результат:
  data/blockouts/prospekt_loot_kinds.json — таблица «узел → вид, таблица, почему» (правится руками и применяется снова);
  --apply — строки `kind = "…"` и `table = "…"` в узлах Loot_N сцены и поле "container" в записях loot плана.
Файл соответствия — источник: если узел в нём есть, правило не пересчитывается (--rules — пересчитать всё заново).

  python -X utf8 tools/prospekt_loot_kinds.py            # только пересчитать соответствие и вывести сводку
  python -X utf8 tools/prospekt_loot_kinds.py --apply    # и внести в сцену и план
  python -X utf8 tools/prospekt_loot_kinds.py --fit      # то же + поворот, высота пола и «не помещается» из prospekt_loot_fit.json
"""
import collections
import json
import os
import re
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENE = ROOT / "scenes/levels/prospekt.tscn"
PLAN = ROOT / "data/blockouts/prospekt.json"
MAP = ROOT / "data/blockouts/prospekt_loot_kinds.json"
FIT = ROOT / "data/blockouts/prospekt_loot_fit.json"  # подгонка моделей по физике: tools/prospekt_loot_fit.tscn

# таблицы, которые не трогаем (ключи, пролог, задания, особые места)
KEEP_TABLES = {"stash", "prospekt_body", "prospekt_concierge", "prospekt_director_safe", "prospekt_yarus_staff",
               "jewelry_safe", "bank_boss", "register", "server_rack"}


def h(name: str) -> int:
    """Устойчивое число из имени узла — для разбивки поровну, без случайности."""
    return zlib.crc32(name.encode("utf8"))


def kind_for(name: str, table: str, look: int, rec: dict) -> tuple[str, str]:
    """(вид или "" — не менять, причина)."""
    note = rec["note"].lower()
    k = rec["kind"]
    tier = rec["tier"]
    if table == "register":
        return "register", "касса"   # внешний вид — модель кассы; таблица, сетка и время обыска прежние
    if table in KEEP_TABLES:
        # серверная стойка «Жёсткие диски» — системный блок, «Серверная: стойка» остаётся
        if table == "server_rack" and "диск" in note:
            return "pc_block", "жёсткие диски"
        return "", "особое место"
    if look == 3 or k == "body":
        return "", "тело"
    # оружие и боевое
    if tier == "weapon" or table in ("security", "pmc"):
        if "патрон" in note:
            return "ammo_crate", "ящик с патронами"
        if any(w in note for w in ("шкаф", "оружейка", "залог", "хранилища", "сейф-шкаф")):
            return "weapon_locker", "оружейный шкаф"
        return "weapon_crate", "оружие: ящик / лёжка / машина"
    # сейфы и банк
    if k in ("safe", "cells") or table == "bank":
        return "safe", "сейф"
    # медицина
    if table == "pharmacy":
        if any(w in note for w in ("рецептур", "аптечный уголок", "госпиталь", "полки", "медпункт")):
            return "med_cabinet", "медицинский шкаф"
        return "medbag", "медицинская сумка"
    # электроника
    if table == "electronics":
        if "пачки денег" in note:
            return "safe", "пачки денег"
        if "архив" in note:
            return "pc_block", "архив"
        if any(w in note for w in ("телефон", "техно")):
            return "tech_shelf", "техника"
        return "locker", "посылки / груз"
    if table in ("tools", "workshop"):
        if "покрышк" in note:
            return "car_trunk", "покрышки"
        return "toolbox", "инструмент"
    if table in ("grocery", "kiosk"):
        return "ration_crate", "продукты, ларьки"
    # багажники и сумки (прежняя таблица home)
    if table == "home":
        if k == "car":
            if "инструмент" in note:
                return "toolbox", "инструмент в машине"
            if "сумки пассажиров" in note:
                return "duffel", "сумки пассажиров"
            if "автобус" in note and "багаж" in note:
                return "suitcase", "багаж автобуса"
            if "открытые двери" in note or "багажник" in note:
                # каждая четвёртая машина — сумка на заднем сиденье
                return ("duffel", "сумка в машине") if h(name) % 4 == 0 else ("car_trunk", "багажник")
            return "car_trunk", "машина"
        if k == "backpack":
            return ("locker", "камера хранения") if "камера хранения" in note else ("duffel", "рюкзак")
        if k == "suitcase":
            if "камера хранения" in note or "почтов" in note or "багажное" in note:
                return "locker", "камера хранения / почта"
            if any(w in note for w in ("сумк",)) or "автобус" in note:
                return ("suitcase", "багаж автобуса") if "автобус: багаж" in note else ("duffel", "сумка")
            return "suitcase", "чемодан"
    # склад, стеллажи, столы, шкафы
    if table == "storage":
        if any(w in note for w in ("гараж", "инструмент", "шиномонтаж", "техпомещения")):
            return "toolbox", "гараж / инструмент"
        if any(w in note for w in ("посылк", "груз из вагона", "гуманитар", "контейнер вскрыт", "багажное", "почты")):
            return "locker", "посылки / груз"
        if any(w in note for w in ("палатка лагеря", "ящики жильцов", "вещи эвакуированных", "колонна эвакуации")):
            return ("duffel" if "вещи" in note else "jacket"), "вещи"
        if any(w in note for w in ("контейнер", "ящики на разгрузке", "приёмка: ящики", "площадка", "фура")):
            return "ammo_crate", "ящик на разгрузке"
        if any(w in note for w in ("палатка лагеря", "ящики жильцов", "вещи эвакуированных", "колонна эвакуации")):
            return "duffel" if "вещи" in note else "jacket", "вещи"
        return "carton", "склад"
    if table == "shelf":
        if "подкоп" in note or "инструмент" in note:
            return "toolbox", "инструмент"
        if any(w in note for w in ("продукты", "полки", "буфет", "кофейный ларёк", "ларёк", "пекарня", "фуд", "рынок")):
            return "ration_crate", "продукты"
        if any(w in note for w in ("стеллаж", "корзина", "подсобка", "баков", "мусорн", "асфальте", "брошенное", "пролом", "химия")):
            return "carton", "стеллаж"
        return "filing", "стол / касса"
    if table == "office":
        if any(w in note for w in ("раздевалк", "шкафчик", "будка охраны", "бытовка прораба", "ресепшен", "пост",
                                    "вестибюль", "антресоль", "фитнес", "приём граждан")):
            return "jacket", "бытовое помещение"
        if "мастерская" in note:
            return "toolbox", "мастерская"
        if any(w in note for w in ("диспетчерская", "радиоузел")):
            return "pc_block", "диспетчерская"
        return "filing", "стол / шкаф конторы"
    return "", "не подошло"


def set_prop(body: str, key: str, value: str) -> str:
    """Свойство узла в тексте сцены: заменить строку `key = …` или дописать в конец блока."""
    line = "%s = %s" % (key, value)
    if re.search(r"^%s = .*$" % key, body, re.M):
        return re.sub(r"^%s = .*$" % key, line, body, count=1, flags=re.M)
    if body.endswith("\n"):
        return body + line + "\n"
    return body + "\n" + line


def has_model(kind: str) -> bool:
    cat = json.load(open(ROOT / "data/loot_containers.json", encoding="utf8"))
    return bool(cat["kinds"].get(kind, {}).get("model"))


def main() -> None:
    apply = "--apply" in sys.argv or "--fit" in sys.argv
    rules = "--rules" in sys.argv
    scene = open(SCENE, encoding="utf8", newline="").read()
    plan_text = open(PLAN, encoding="utf8", newline="").read()
    plan = json.loads(plan_text)
    loot = plan["loot"]
    pat = re.compile(r'(\[node name="(Loot_\d+)" parent="Gameplay/Loot" instance=ExtResource\("\d+"\)\]\n)((?:(?!\n\[|\n\n).*\n?)*)')
    blocks = list(pat.finditer(scene))
    assert len(blocks) == len(loot), (len(blocks), len(loot))
    old = json.load(open(MAP, encoding="utf8")) if MAP.exists() and not rules else {}
    # прежние таблица и вид места (до этого скрипта) — из сцены в git (RULES_REF, по умолчанию HEAD), если там их ещё нет в узле
    ref = os.environ.get("RULES_REF", "HEAD")
    try:
        orig_text = subprocess.check_output(["git", "show", "%s:scenes/levels/prospekt.tscn" % ref], cwd=ROOT).decode("utf8")
    except Exception:
        orig_text = ""
    orig = {}
    for om in pat.finditer(orig_text):
        if "kind =" not in om.group(3):
            ot = re.search(r'table = "(\w+)"', om.group(3))
            ol = re.search(r"look = (\d+)", om.group(3))
            orig[om.group(2)] = (ot.group(1), int(ol.group(1)) if ol else 0)
    result = collections.OrderedDict()
    for m, rec in zip(blocks, loot):
        name = m.group(2)
        body = m.group(3)
        x, y, z = (float(v) for v in re.search(r"position = Vector3\(([^)]*)\)", body).group(1).split(","))
        if abs(x - rec["at"][0]) > 0.06 or abs(z - rec["at"][2]) > 0.06:
            print("предупреждение: узел %s сдвинут руками относительно плана (%s) — соответствие по номеру" % (name, rec["note"]))
        table = re.search(r'table = "(\w+)"', body).group(1)
        look = int(re.search(r"look = (\d+)", body).group(1)) if "look =" in body else 0
        if name in orig:
            table, look = orig[name]
        if name in old:
            kind, why = old[name]["kind"], old[name]["why"]
            was = old[name].get("was", table)
        else:
            kind, why = kind_for(name, table, look, rec)
            was = table
            if "kind =" in body:
                # уже внесено прежним запуском: прежняя таблица неизвестна — берём из соответствия, если есть
                pass
        model = old.get(name, {}).get("model", "")
        if not model and kind == "weapon_crate" and any(w in rec["note"].lower() for w in ("чвк", "блокпост")):
            model = "it_trunk"  # у ЧВК — стальной сундук вместо дощатого ящика ЗИП
        entry = {"kind": kind, "table": kind if kind else table, "why": why, "was": was, "note": rec["note"]}
        if model:
            entry["model"] = model
        if old.get(name, {}).get("solid") is False:
            entry["solid"] = False
        result[name] = entry
    MAP.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf8", newline="\n")
    cnt = collections.Counter(v["kind"] or "(без изменений)" for v in result.values())
    print("мест:", len(result))
    for k, v in cnt.most_common():
        print("  %-18s %d" % (k, v))
    if not apply:
        return
    fit = json.load(open(FIT, encoding="utf8")) if FIT.exists() else {}
    # сцена: table, kind, model_id и (если снята подгонка по физике) model_yaw, floor_drop, model_off
    out = []
    pos = 0
    for m in blocks:
        out.append(scene[pos:m.start(3)])
        body = m.group(3)
        info = result[m.group(2)]
        body = re.sub(r"^body_solid = .*\n?", "", body, flags=re.M)
        fit_now = fit.get(m.group(2))
        # без коллизии: подгонка нашла ступени под местом или в таблице вида стоит "solid": false (контейнер на лестнице / в проходе ботов)
        if info["kind"] and (info.get("solid") is False or (fit_now is not None and fit_now.get("ok") and fit_now.get("solid") is False)):
            body = set_prop(body, "body_solid", "false")
        if info["kind"]:
            body = set_prop(body, "table", '"%s"' % info["table"])
            body = set_prop(body, "kind", '"%s"' % info["kind"])
            if info.get("model"):
                body = set_prop(body, "model_id", '"%s"' % info["model"])
            f = fit.get(m.group(2))
            if f is not None:
                # удачная подгонка заменяет прежнюю целиком: иначе «не помещается» от старого прогона остаётся при новой удачной
                # (у «не помещается» модели нет — прежние поворот и высота не действуют, их не трогаем)
                if f["ok"]:
                    body = re.sub(r"^(model_yaw|floor_drop|model_off|model_shift) = .*\n?", "", body, flags=re.M)
                body = set_prop(body, "model_yaw", "%g" % f["yaw"]) if f["ok"] and f["yaw"] else body
                body = set_prop(body, "floor_drop", "%g" % f["drop"]) if f["ok"] and f["drop"] else body
                body = set_prop(body, "model_off", "true") if not f["ok"] else body
                if f["ok"] and f.get("shift"):
                    body = set_prop(body, "model_shift", "Vector2(%g, %g)" % tuple(f["shift"]))
        out.append(body)
        pos = m.end(3)
    out.append(scene[pos:])
    open(SCENE, "w", encoding="utf8", newline="").write("".join(out))
    # план: поле container после kind
    new_plan = plan_text
    names = list(result)

    # вставка после "kind" внутри массива loot, по порядку записей
    start = new_plan.index('"loot": [')
    end = new_plan.index("\n ],", start)
    seg = new_plan[start:end]
    parts = re.split(r'(\n  \{\n)', seg)
    # parts: [заголовок, '\n  {\n', тело0, '\n  {\n', тело1, …]
    rebuilt = [parts[0]]
    n = 0
    for i in range(1, len(parts), 2):
        bodyj = parts[i + 1]
        info = result[names[n]]
        n += 1
        bodyj = re.sub(r'   "container": "\w+",\n|   "model_ok": true,\n', "", bodyj)
        if info["kind"]:
            extra = '   "container": "%s",\n' % info["kind"]
            fitted = fit.get(names[n - 1])
            if fitted is not None and fitted["ok"] and (info.get("model") or has_model(info["kind"])):
                extra += '   "model_ok": true,\n'  # настоящая модель стоит — маркер блокаута на этом месте не рисуется
            bodyj = re.sub(r'(   "kind": "\w+",\n)', lambda mm: mm.group(1) + extra, bodyj, count=1)
        rebuilt.append(parts[i])
        rebuilt.append(bodyj)
    new_plan = new_plan[:start] + "".join(rebuilt) + new_plan[end:]
    json.loads(new_plan)
    open(PLAN, "w", encoding="utf8", newline="").write(new_plan)
    print("внесено в сцену и план")


if __name__ == "__main__":
    main()
