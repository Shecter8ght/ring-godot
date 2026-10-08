"""Библиотека скачанных моделей Sketchfab: раскладка по статусу и общий список.

python tools/sketchfab_library.py

Корень: _asset_src/Zone01/Sketchfab/ (не в git). Владелец кладёт скачанное в 0_новые/<категория>/<модель>/
(архивы как скачались). Инструмент для каждой модели:
  1) читает лицензию из license.txt внутри glTF-архива и сверяет с API Sketchfab (автор, лицензия,
     треугольники) — пишет _модель.json рядом;
  2) распаковывает glTF-архив в gltf/;
  3) переносит папку модели в папку статуса, сохраняя категорию:
       1_в_игре/                 — встроена (есть в assets/zone01/models/sketchfab.json)
       2_можно_не_использовано/  — лицензия подходит (CC0, CC-BY), пока не встроена; причина — в списке
       3_нельзя/                 — лицензия не подходит (Free Standard, NC, ND, SA) — в игру не пойдёт
  4) пишет _СПИСОК.md в корне библиотеки и docs/assets_sketchfab.md (в git) — таблица по всем моделям.
Повторный запуск безопасен: уже разобранное просто перепроверяется и переносится, если статус сменился.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "_asset_src/Zone01/Sketchfab"
STATUS = {"new": "0_новые", "used": "1_в_игре", "ok": "2_можно_не_использовано", "bad": "3_нельзя"}
USED = ROOT / "assets/zone01/models/sketchfab.json"
DOC = ROOT / "docs/assets_sketchfab.md"
ALLOWED = ("CC0", "CC Attribution", "Public Domain")
FORBIDDEN_MARKS = ("NonCommercial", "NoDerivs", "ShareAlike", "Standard", "Editorial")

# понятные имена и заметки по uid (почему не встроено и куда пойдёт)
NAMES = {
    "cedba0fb26e34497910044f11a23e686": "ВАЗ 2104 скан",
    "5cdf33c5d3754f658e740f5360e3eeca": "Сгоревшая машина",
    "3836ff67877248c2a820e6a969984aac": "Мусорный бак зелёный",
    "c25e5fc2bfa54d24a165a8a207c0a6d7": "Сухое дерево",
    "4ae7a186ccb54b9abdd535ff564a57b9": "Камень",
    "d6e22786fbfd4b239c54eced37de7a84": "Деревянный брусок",
    "4ca6068160cc43feb305f5547eb9f87e": "Гаражи кирпичные",
    "cb7064bec48845fea62a830b2c692fb1": "Панельная 12 этажей",
    "deb2133873534b8ebec4c97e5c7f6c3b": "Панельная 5 этажей",
    "cc649800861341a58dbf5307dfa8dc9f": "Квартал девятиэтажек",
    "ece69535f7584e099488f65f2072264e": "Сосновый лес (сцена)",
    "61f8c7817fe6457fb26e4814cfc48a3f": "Лес с дорогой (сцена)",
    "c1cee56e73ed47438015a646ad82dfa5": "Активные наушники",
    "82adf376164f4d99a4e0b2949930e2ad": "Шлем с наушниками",
    "844f276a2b464389bf3bbd75a6a7bbc4": "Подсумки",
    "abe8e567ae72431384ee7535845b6f45": "Плитник",
    "342501b0c84843a3a418319c31ea26fa": "Тактический персонаж",
    "850593a8c7114c188395ba1849a66eb9": "Солдат в полном снаряжении",
    "29846501dcc84fa79709f8db5cfd033c": "Забор ПО-2",
    "a60e52bd903843a49e9364ce43be8e2a": "Будка ремонта обуви",
    "6622502050b548ef85796886f319dc99": "ВАЗ 2110",
}
NOTES = {
    "4ae7a186ccb54b9abdd535ff564a57b9": "глыба склеена с куском земли в один объект — отдельно не вырезать",
    "cc649800861341a58dbf5307dfa8dc9f": "дома склеены с землёй в один меш — для фона карты пробовать позже",
    "ece69535f7584e099488f65f2072264e": "это сфера неба с пятачком, отдельных деревьев нет",
    "61f8c7817fe6457fb26e4814cfc48a3f": "деревья — вырезанные фотографии на плоскостях, слабое качество",
    "c1cee56e73ed47438015a646ad82dfa5": "снаряжение — не для карты; пойдёт в убежище/персонажей",
    "82adf376164f4d99a4e0b2949930e2ad": "снаряжение — не для карты; пойдёт в убежище/персонажей",
    "844f276a2b464389bf3bbd75a6a7bbc4": "снаряжение — не для карты; 269 тыс. треугольников, нужен ретопо",
    "abe8e567ae72431384ee7535845b6f45": "снаряжение — не для карты; пойдёт в убежище/персонажей",
    "342501b0c84843a3a418319c31ea26fa": "персонаж — для мародёров, отдельная задача (риг под анимации)",
    "850593a8c7114c188395ba1849a66eb9": "персонаж — для ЧВК, отдельная задача (риг под анимации)",
}


def read_text(raw: bytes) -> str:
    for enc in ("utf-8", "cp1251", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def gltf_zip(folder: Path) -> Path | None:
    for z in sorted(folder.glob("*.zip")):
        try:
            if any(n.endswith("scene.gltf") for n in zipfile.ZipFile(z).namelist()):
                return z
        except zipfile.BadZipFile:
            continue
    return None


def model_folders() -> list[Path]:
    """Папка модели — та, где лежит glTF-архив или уже есть _модель.json."""
    out = []
    for p in LIB.rglob("*"):
        if p.is_dir() and p.name != "gltf" and ((p / "_модель.json").exists() or gltf_zip(p)):
            out.append(p)
    return sorted(set(out))


def inspect(folder: Path) -> dict:
    meta_path = folder / "_модель.json"
    info = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    z = gltf_zip(folder)
    if z and not info.get("uid"):
        zf = zipfile.ZipFile(z)
        txt = next((n for n in zf.namelist() if n.lower().endswith(".txt")), None)
        text = read_text(zf.read(txt)) if txt else ""
        m = re.search(r"([0-9a-f]{32})", text)
        info["uid"] = m.group(1) if m else ""
        lic = re.search(r"license type:\s*(.+)", text, re.I)
        info["license_txt"] = lic.group(1).strip() if lic else ""
    if info.get("uid") and not info.get("api"):
        try:
            req = urllib.request.Request(f"https://api.sketchfab.com/v3/models/{info['uid']}", headers={"User-Agent": "RING-asset-tool/1.0"})
            api = json.load(urllib.request.urlopen(req, timeout=20))
            info["api"] = True
            info["title"] = api.get("name")
            info["author"] = (api.get("user") or {}).get("displayName")
            lic = api.get("license")
            info["license"] = lic.get("label") if isinstance(lic, dict) else str(lic)
            info["triangles"] = api.get("faceCount")
            info["url"] = api.get("viewerUrl") or f"https://sketchfab.com/3d-models/{info['uid']}"
        except Exception as e:  # сеть недоступна — лицензия только из файла
            info.setdefault("license", info.get("license_txt", ""))
            print("  API недоступен:", folder.name, e)
    info["name"] = NAMES.get(info.get("uid", ""), info.get("name") or info.get("title") or folder.name)
    if z and not (folder / "gltf/scene.gltf").exists():
        zf = zipfile.ZipFile(z)
        for n in zf.namelist():
            if n.startswith("/") or ".." in n:
                continue
            zf.extract(n, folder / "gltf")
    meta_path.write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return info


def license_ok(lic: str) -> bool:
    if any(m.lower() in lic.lower() for m in FORBIDDEN_MARKS):
        return False
    return any(a.lower() in lic.lower() for a in ALLOWED)


def relative_category(folder: Path) -> Path:
    rel = folder.relative_to(LIB)
    if rel.parts and rel.parts[0] in STATUS.values():
        rel = Path(*rel.parts[1:])
    return rel


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for s in STATUS.values():
        (LIB / s).mkdir(parents=True, exist_ok=True)
    used = json.loads(USED.read_text(encoding="utf-8")) if USED.exists() else {}
    used_by_lib: dict[str, list[str]] = {}
    for key, v in used.items():
        used_by_lib.setdefault(v.get("library", ""), []).append(key)
    rows = []
    for folder in model_folders():
        info = inspect(folder)
        lic = info.get("license") or info.get("license_txt", "")
        if not license_ok(lic):
            status = "bad"
        elif info["name"] in used_by_lib:
            status = "used"
        else:
            status = "ok"
        target = LIB / STATUS[status] / relative_category(folder)
        if target != folder:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                print("  уже есть:", target)
            else:
                shutil.move(str(folder), str(target))
                print(f"{STATUS[status]:<26} {relative_category(folder)}")
        note = NOTES.get(info.get("uid", ""), "")
        if status == "bad":
            note = f"лицензия «{lic}» — в игру нельзя (правило проекта: только CC0 / CC-BY)"
        if status == "used":
            note = "в игре: " + ", ".join(f"`{k}.glb`" for k in used_by_lib[info["name"]])
        rows.append((STATUS[status], str(relative_category(folder)).replace("\\", "/"), info["name"], info.get("author", ""), lic,
                     info.get("triangles", ""), info.get("url", ""), note))
    # пустые папки после переноса
    for p in sorted(LIB.rglob("*"), key=lambda q: -len(q.parts)):
        if p.is_dir() and p.name not in STATUS.values() and not any(p.iterdir()):
            p.rmdir()
    rows.sort()
    lines = ["# Библиотека Sketchfab (зона 1)", "",
             "Генерирует `python tools/sketchfab_library.py`. Новое скачанное класть в `_asset_src/Zone01/Sketchfab/0_новые/<категория>/<модель>/`.",
             "Статусы: **1_в_игре** — встроено; **2_можно_не_использовано** — лицензия подходит, не встроено (причина в заметке);",
             "**3_нельзя** — лицензия не подходит (только CC0 / CC-BY).", "",
             "| Статус | Папка | Модель | Автор | Лицензия | Треугольников | Заметка |", "|---|---|---|---|---|---|---|"]
    for status, rel, name, author, lic, tri, url, note in rows:
        lines.append(f"| {status} | {rel} | [{name}]({url}) | {author} | {lic} | {tri} | {note} |")
    text = "\n".join(lines) + "\n"
    (LIB / "_СПИСОК.md").write_text(text, encoding="utf-8")
    DOC.write_text(text, encoding="utf-8")
    print(f"моделей {len(rows)}: в игре {sum(r[0] == STATUS['used'] for r in rows)}, можно {sum(r[0] == STATUS['ok'] for r in rows)}, нельзя {sum(r[0] == STATUS['bad'] for r in rows)}")


if __name__ == "__main__":
    main()
