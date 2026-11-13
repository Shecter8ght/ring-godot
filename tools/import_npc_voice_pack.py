import argparse
import json
import shutil
from pathlib import Path

SOURCE = Path(r"C:/Users/Schecter_8ght/Desktop/РЕПЛИКИ/RING_генерация")
PROJECT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT / "data/audio_events.json"
VOICE_MAP = PROJECT / "data/npc_voice_map.json"

LABELS = {
    "SCAV": "Мародёр",
    "VETERAN": "Бывалый",
    "PMC": "ЧВК",
    "RESIDENT": "Жилец",
    "RIVAL_RADIO": "Рация чужих отрядов",
    "MIKHALYCH": "Михалыч",
    "ILYA": "Илья",
    "KIRILL": "Кирилл",
    "NINA": "Нина",
    "PLAYER": "Игрок",
    "SERGEY": "Сергей",
    "ANTON": "Антон",
}

SPEAKERS = {
    "player": "PLAYER",
    "Михалыч": "MIKHALYCH",
    "Сергей": "SERGEY",
    "Антон": "ANTON",
    "ilya": "ILYA",
    "kirill": "KIRILL",
    "perevalka": "NINA",
}

EXISTING = {
    "Контакт!": "ai_spot",
    "Ушёл… Ищем.": "ai_search",
    "Проверю тут…": "ai_investigate",
    "Перезаряжаюсь!": "ai_reload",
    "Граната!": "ai_nade",
    "Меня зацепило!": "ai_hurt",
    "Пошли вон отсюда!": "resident",
    "Стой! Назад за линию!": "ai_cordon_warning",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def speaker_index():
    result = {}
    for path in (PROJECT / "data/quests").glob("*.json"):
        data = read_json(path)
        def walk(value):
            if isinstance(value, dict):
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                if len(value) >= 2 and isinstance(value[0], str) and isinstance(value[1], str) and value[0] in SPEAKERS:
                    voice = SPEAKERS[value[0]]
                    result[(voice, value[1])] = value[0]
                else:
                    for child in value:
                        walk(child)
        walk(data)
    return result


def event_name(entry):
    label = LABELS[entry["voice"]]
    text = entry["text"]
    suffix = f"{label} — {text}"
    return suffix if len(suffix) <= 160 else suffix[:159].rstrip() + "…"


def event_group(entry):
    voice = entry["voice"]
    output = entry["output"]
    if "/combat/" in output:
        return {
            "SCAV": "Мародёры — бой и поиск",
            "VETERAN": "Чужие отряды — ведущий",
            "PMC": "ЧВК — кордон",
            "RESIDENT": "Жильцы",
        }.get(voice, LABELS[voice])
    if "/radio_" in output:
        return "Чужие отряды — рация"
    quest = output.split("/")[1] if "/" in output else "Прочее"
    return f"{LABELS[voice]} — {quest}"


def build():
    manifest = read_json(SOURCE / "manifest.json")
    registry = read_json(REGISTRY)
    existing = {event["id"]: event for event in registry["events"]}
    speakers = speaker_index()
    copied = []
    map_rows = []
    changes = []
    for entry in manifest["entries"]:
        if entry.get("deferred", False):
            continue
        source = SOURCE / "mp3" / entry["output"]
        if not source.exists() or source.stat().st_size == 0:
            raise RuntimeError(f"Нет исходника: {source}")
        line_number = entry["id"].split("_")[-1]
        event_id = EXISTING.get(entry["text"], f"voice_{entry['voice'].lower()}_{line_number}")
        relative = f"voice/{event_id}.mp3"
        target = PROJECT / "assets/audio" / relative
        copied.append((source, target))
        old = existing.get(event_id)
        if old:
            event = dict(old)
            event["files"] = [relative]
            event["enabled"] = True
        else:
            event = {
                "id": event_id,
                "name": event_name(entry),
                "category": "Голоса ИИ и персонажей",
                "group": event_group(entry),
                "binding": {"type": "action", "hook": event_id},
                "type": "one",
                "profile": "world",
                "custom": True,
                "files": [relative],
                "enabled": True,
            }
        if old and old.get("files") != [relative]:
            changes.append(event_id)
        if not old:
            changes.append(event_id)
        existing[event_id] = event
        speaker = speakers.get((entry["voice"], entry["text"]), "*")
        map_rows.append({"speaker": speaker, "text": entry["text"], "event": event_id})
    registry["events"] = list(existing.values())
    voice_map = {"schemaVersion": 1, "lines": map_rows}
    return registry, voice_map, copied, changes


def validate(registry, voice_map, copied):
    ids = set()
    hooks = set()
    for event in registry["events"]:
        if event["id"] in ids:
            raise RuntimeError(f"Повторный id: {event['id']}")
        ids.add(event["id"])
        binding = event.get("binding", {})
        if binding.get("type") == "action":
            hook = binding.get("hook", "")
            if hook in hooks:
                raise RuntimeError(f"Повторная привязка: {hook}")
            hooks.add(hook)
    if len(ids) > 5000:
        raise RuntimeError("Слишком много событий")
    for source, target in copied:
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Файл уже изменён другим источником: {target}")
    seen = set()
    for row in voice_map["lines"]:
        key = (row["speaker"], row["text"])
        if key in seen:
            continue
        seen.add(key)
        if row["event"] not in ids:
            raise RuntimeError(f"Нет события для {row['text']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    registry, voice_map, copied, changes = build()
    validate(registry, voice_map, copied)
    print(f"Голосовых событий к обновлению: {len(changes)}")
    print(f"Файлов MP3: {len(copied)}")
    print(f"Строк в карте: {len(voice_map['lines'])}")
    if args.check:
        print("Только проверка; файлы не записаны")
        return
    for source, target in copied:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VOICE_MAP.write_text(json.dumps(voice_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Записано: {REGISTRY}")
    print(f"Записано: {VOICE_MAP}")


if __name__ == "__main__":
    main()
