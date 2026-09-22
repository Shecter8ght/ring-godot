"""Звуки в assets/audio из звуковой библиотеки прежнего RING (Three.js).

Сырьё (CC0-паки и записи владельца из ElevenLabs) лежит в E:\\Games\\RING\\_audio_src и уже
прогнано через E:\\Games\\RING\\tools\\build_audio.py: выстрелы нарезаны по транзиентам,
пики нормализованы, хвосты обрезаны, всё в моно ogg 44.1 кГц. Здесь берём готовое по списку
групп и пишем раздел «Звук» в assets/CREDITS.md. Путь к прежнему проекту — RING_OLD.

Использование: python tools/import_audio.py
Игра обязана звучать и без assets/audio — src/audio/audio_system.gd синтезирует запасной звук.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = Path(os.environ.get("RING_OLD", r"E:\Games\RING")) / "public" / "audio"
OUT = ROOT / "assets" / "audio"
CREDITS = ROOT / "assets" / "CREDITS.md"

# группа в библиотеке -> префиксы файлов, которые берём
GROUPS: dict[str, list[str]] = {
    "guns": ["pistol_", "pistol_far_", "carbine_", "carbine_far_", "shotgun_", "shotgun_far_",
             "marksman_", "marksman_far_", "reload_pistol_", "reload_rifle_", "reload_shotgun_"],
    "hits": ["concrete_", "hard_", "glass_", "metal_", "wood_"],
    "steps": ["stone_", "stone_run_", "dirt_", "dirt_run_", "snow_", "snow_run_"],
    "body": ["hit_", "fall_"],
    "voice": ["rattle_groan_", "rattle_gurgle_"],
    "world": ["door_", "debris_"],
    "ambient": ["building_wind_drips"],
}

AUDIO_CREDITS = """
## Звук (assets/audio — `tools/import_audio.py`, обработка — `tools/build_audio.py` прежнего RING)

| Источник | Автор | Лицензия | Где |
|---|---|---|---|
| The Free Firearm Sound Library | Ben Jaszczak, Brian Nelson, Kevin Heras, Matthew Nanney | CC0 | guns/shotgun, guns/marksman, *_far |
| 100 CC0 SFX #2 | rubberduck (OpenGameArt) | CC0 | world/door, world/debris, hits/hard, body/hit |
| Gun reload sounds | zer0_sol, SpringySpringo | CC0 | guns/reload_* |
| Loopable Dungeon Ambience / Wind whoosh loop / Dripping water | JaggedStone, SketchMan3, qubodup | CC0 | ambient/building_wind_drips |
| Пистолет и автомат (одиночный) | Shecter8ght — сгенерировано в ElevenLabs | права автора проекта; ElevenLabs — https://elevenlabs.io | guns/pistol, guns/carbine |
| Шаги и бег по камню, грунту, снегу; попадания в стекло, металл, дерево; предсмертные хрипы | Shecter8ght — сгенерировано в ElevenLabs | права автора проекта; ElevenLabs — https://elevenlabs.io | steps/*, hits/glass|metal|wood, voice/rattle_* |
"""


def main() -> None:
    if not OLD.exists():
        raise SystemExit(f"нет библиотеки {OLD} — задай RING_OLD")
    total = 0
    for group, prefixes in GROUPS.items():
        dst = OUT / group
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for f in sorted((OLD / group).glob("*.ogg")):
            stem = f.stem
            # префикс без номера: "pistol_" не должен ловить "pistol_far_01"
            base = stem.rsplit("_", 1)[0] + "_" if stem[-2:].isdigit() else stem
            if base in prefixes or stem in prefixes:
                shutil.copy2(f, dst / f.name)
                total += 1
        print(f"{group}: {len(list(dst.glob('*.ogg')))}")
    text = CREDITS.read_text(encoding="utf-8") if CREDITS.exists() else "# Источники ассетов\n"
    marker = "\n## Звук"
    if marker in text:
        text = text[: text.index(marker)]
    CREDITS.write_text(text.rstrip() + "\n" + AUDIO_CREDITS, encoding="utf-8")
    print(f"всего файлов: {total}")


if __name__ == "__main__":
    main()
