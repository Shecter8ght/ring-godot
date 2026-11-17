"""Ограниченный набор кандидатов для травы «Проспекта».

    python -X utf8 tools/prospekt_grass/fetch_assets.py [asset_id …]

Poly Haven: исходные 8K-карты покрытий и 8K Blender-модели с зависимостями.
ambientCG: исходный архив Grass001 8K-JPG и распакованные карты. Fab скачивается
отдельно через штатную страницу, без обхода входа или лицензионного диалога.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "prospekt_grass"
UA = {"User-Agent": "RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)"}
PH_TEXTURES = {"leafy_grass", "grass_ground"}
PH_MODELS = {"grass_bermuda_01", "weed_plant_02", "grass_medium_01"}
ROLES = {
    "leafy_grass": "основной кандидат: тёмная трава, листья и веточки",
    "grass_ground": "второй слой: почва, корни и проплешины",
    "Grass001": "альтернативная плотная тёмная основа",
    "grass_bermuda_01": "низкий плотный ковёр",
    "weed_plant_02": "низкие широколистные сорняки",
    "grass_medium_01": "отдельные куртины после упрощения",
}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as response:
        return response.read()


def get_json(url: str) -> dict:
    return json.loads(get(url))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path, expected_md5: str = "") -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        part = dest.with_name(dest.name + ".part")
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as response, part.open("wb") as stream:
            while chunk := response.read(4 * 1024 * 1024):
                stream.write(chunk)
        part.replace(dest)
    if expected_md5:
        actual = hashlib.md5(dest.read_bytes()).hexdigest()
        if actual != expected_md5:
            raise RuntimeError(f"MD5 не совпал: {dest}: {actual} != {expected_md5}")
    return {"file": str(dest.relative_to(OUT)), "bytes": dest.stat().st_size, "sha256": sha256(dest)}


def write_provenance(asset_id: str, info: dict, source: str, license_url: str, records: list[dict]) -> None:
    folder = OUT / asset_id
    authors = info.get("authors", {})
    if authors:
        author_text = ", ".join(f"{name} ({role})" for name, role in authors.items())
    else:
        author_text = "ambientCG / Lennart Demes"
    (folder / "source_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "license.txt").write_text(
        f"title: {info.get('name', info.get('displayName', asset_id))}\n"
        f"asset_id: {asset_id}\n"
        f"author: {author_text}\n"
        f"license: CC0 1.0 Universal\n"
        f"license_url: {license_url}\n"
        f"source: {source}\n"
        f"downloaded: {datetime.date.today().isoformat()}\n"
        f"role: {ROLES[asset_id]}\n"
        "modifications: исходники не изменены; игровые производные описаны в ../asset-state.md\n",
        encoding="utf-8", newline="\n",
    )
    (folder / "provenance.json").write_text(json.dumps({
        "asset_id": asset_id,
        "source": source,
        "license": "CC0 1.0 Universal",
        "license_url": license_url,
        "downloaded": datetime.date.today().isoformat(),
        "files": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_polyhaven(asset_id: str) -> None:
    folder = OUT / asset_id
    folder.mkdir(parents=True, exist_ok=True)
    info = get_json(f"https://api.polyhaven.com/info/{asset_id}")
    files = get_json(f"https://api.polyhaven.com/files/{asset_id}")
    (folder / "api_files.json").write_text(json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8")
    records: list[dict] = []
    if asset_id in PH_TEXTURES:
        for key, name in (("Diffuse", "albedo"), ("nor_gl", "normal"), ("arm", "arm"), ("Displacement", "height")):
            variant = files[key]["8k"].get("jpg") or files[key]["8k"].get("png")
            ext = "jpg" if files[key]["8k"].get("jpg") else "png"
            records.append(download(variant["url"], folder / f"{name}_8k.{ext}", variant["md5"]))
    else:
        entry = files["blend"]["8k"]["blend"]
        records.append(download(entry["url"], folder / f"{asset_id}_8k.blend", entry["md5"]))
        for relative, variant in entry.get("include", {}).items():
            records.append(download(variant["url"], folder / relative, variant["md5"]))
    write_provenance(asset_id, info, f"https://polyhaven.com/a/{asset_id}", "https://polyhaven.com/license", records)
    print(f"СКАЧАНО {asset_id}: {len(records)} файлов", flush=True)


def fetch_ambientcg(asset_id: str) -> None:
    folder = OUT / asset_id
    folder.mkdir(parents=True, exist_ok=True)
    info = get_json(f"https://ambientcg.com/api/v2/full_json?id={asset_id}")
    archive = folder / f"{asset_id}_8K-JPG.zip"
    records = [download(f"https://ambientcg.com/get?file={archive.name}", archive)]
    with zipfile.ZipFile(archive) as source_zip:
        if source_zip.testzip() is not None:
            raise RuntimeError(f"Повреждён архив {archive}")
        for entry in source_zip.infolist():
            target = (folder / entry.filename).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise RuntimeError(f"Небезопасный путь в архиве: {entry.filename}")
            if entry.is_dir():
                continue
            if not target.exists():
                target.write_bytes(source_zip.read(entry))
            records.append({"file": str(target.relative_to(OUT)), "bytes": target.stat().st_size, "sha256": sha256(target)})
    asset_info = info["foundAssets"][0]
    asset_info["name"] = asset_info.get("displayName", asset_id)
    write_provenance(asset_id, asset_info, f"https://ambientcg.com/a/{asset_id}", "https://docs.ambientcg.com/license/", records)
    print(f"СКАЧАНО {asset_id}: {len(records)} файлов", flush=True)


def main() -> None:
    ids = sys.argv[1:] or ["leafy_grass", "grass_ground", "Grass001", "grass_bermuda_01", "weed_plant_02", "grass_medium_01"]
    for asset_id in ids:
        if asset_id in PH_TEXTURES | PH_MODELS:
            fetch_polyhaven(asset_id)
        elif asset_id == "Grass001":
            fetch_ambientcg(asset_id)
        else:
            raise SystemExit(f"Неизвестный кандидат: {asset_id}")
    print("НАБОР КАНДИДАТОВ ГОТОВ", flush=True)


if __name__ == "__main__":
    main()
