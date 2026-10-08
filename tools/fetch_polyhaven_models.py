"""Скачивает модели Poly Haven (CC0) в _asset_src/<папка>/<id>/: glTF + текстуры + license.txt.

python tools/fetch_polyhaven_models.py <папка> <id> [id ...] [--res 2k]
Пример: python tools/fetch_polyhaven_models.py pine_forest fir_tree_01 pine_roots
Сырые сканы тяжёлые (миллионы треугольников) — в игру их переводит отдельный Blender-скрипт
(для зоны 1 — tools/build_zone01_forest.py), сюда — только исходники.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)"}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        return json.load(r)


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        data = r.read()
    dest.write_bytes(data)
    return len(data)


def fetch(folder: str, asset_id: str, res: str, info: dict) -> None:
    out = ROOT / "_asset_src" / folder / asset_id
    files = get_json(f"https://api.polyhaven.com/files/{asset_id}")
    gltf = files["gltf"][res]["gltf"]
    total = download(gltf["url"], out / f"{asset_id}.gltf")
    for rel, inc in gltf.get("include", {}).items():
        total += download(inc["url"], out / rel)
    # карточки растений: в glTF цвет — JPEG без альфы; альфа и «сухой» цвет — отдельными картами.
    # Склеиваем в <id>_rgba.png (сухой цвет, если есть, — для осени)
    if "Alpha" in files:
        from PIL import Image
        tex = out / "textures"
        alpha = tex / f"{asset_id}_alpha_{res}.jpg"
        total += download(files["Alpha"][res]["jpg"]["url"], alpha)
        diff_key = "dry_diff" if "dry_diff" in files else "Diffuse"
        diff = tex / f"{asset_id}_{diff_key.lower()}_{res}.jpg"
        total += download(files[diff_key][res]["jpg"]["url"], diff)
        rgba = Image.open(diff).convert("RGB")
        rgba.putalpha(Image.open(alpha).convert("L").resize(rgba.size))
        rgba.save(tex / f"{asset_id}_rgba.png")
    authors = ", ".join(info.get("authors", {}).keys()) or "Poly Haven"
    (out / "license.txt").write_text(
        f"title: {info.get('name', asset_id)}\nauthor: {authors}\nlicense: CC0 1.0\n"
        f"source: https://polyhaven.com/a/{asset_id}\nformat: glTF {res}\n", encoding="utf-8")
    print(f"{asset_id}: {total // 1024} КБ")


def main() -> None:
    args = sys.argv[1:]
    res = "2k"
    if "--res" in args:
        i = args.index("--res")
        res = args[i + 1]
        del args[i:i + 2]
    folder, ids = args[0], args[1:]
    catalog = get_json("https://api.polyhaven.com/assets?t=models")
    for asset_id in ids:
        fetch(folder, asset_id, res, catalog.get(asset_id, {}))


if __name__ == "__main__":
    main()
