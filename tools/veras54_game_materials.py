"""Матовая отделка игровых GLB ВЕРАС-54 после экспорта из Blender.

python tools/veras54_game_materials.py [путь.glb ...]
Меняет только упакованные карты Roughness/Metallic оружия и шероховатость
маркировки. Исходные бинарные данные сеток, рук, скелетов и клипов сохраняются.
Повторный запуск для той же версии отделки ничего не меняет.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

VERSION = 1
MARKER = "ring_veras54_material_finish"
ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [ROOT / "assets/models/weapons/veras54" / name
            for name in ("veras54.glb", "veras54_viewmodel.glb")]


def read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or total != len(raw):
        raise ValueError(f"{path}: неверный заголовок GLB")
    size, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError(f"{path}: нет JSON GLB")
    document = json.loads(raw[20:20 + size])
    offset = 20 + size
    bin_size, bin_kind = struct.unpack_from("<II", raw, offset)
    if bin_kind != 0x004E4942 or offset + 8 + bin_size != len(raw):
        raise ValueError(f"{path}: ожидается один бинарный блок GLB")
    if len(document.get("buffers", [])) != 1:
        raise ValueError(f"{path}: ожидается один встроенный буфер")
    return document, raw[offset + 8:]


def matte_orm(png: bytes, surface: str) -> bytes:
    source = Image.open(BytesIO(png))
    pixels = np.array(source.convert("RGB"), dtype=np.uint8)
    roughness = pixels[:, :, 1].astype(np.float32) / 255.0
    metallic = pixels[:, :, 2].astype(np.float32) / 255.0
    if surface == "WeaponMetal":
        # Карта разделяет чёрную отделку (~0.48) и открытую сталь (~1).
        # Микроструктура покрытия сохраняется; сталь не становится краской.
        coating = metallic < 0.8
        roughness[coating] = np.clip(roughness[coating] + 0.20, 0.62, 0.80)
        metallic[coating] *= 0.08
    elif surface in ("Furniture", "Magazine"):
        polymer = metallic < 0.2
        roughness[polymer] = np.clip(roughness[polymer] + 0.09, 0.70, 0.88)
        metallic[polymer] = 0.0
    else:
        raise ValueError(f"Неизвестная поверхность: {surface}")
    pixels[:, :, 1] = np.rint(roughness * 255).astype(np.uint8)
    pixels[:, :, 2] = np.rint(metallic * 255).astype(np.uint8)
    output = BytesIO()
    Image.fromarray(pixels).save(output, format="PNG")
    return output.getvalue()


def fix_glb(path: Path) -> bool:
    document, original_binary = read_glb(path)
    extras = document.get("asset", {}).get("extras", {})
    if extras.get(MARKER) == VERSION:
        print(f"{path.name}: матовая отделка v{VERSION} уже применена")
        return False
    if MARKER in extras:
        raise ValueError("Для новой версии отделки нужен свежий экспорт из Blender")
    binary = bytearray(original_binary)
    replaced: set[int] = set()
    surfaces: set[str] = set()
    for material in document.get("materials", []):
        name = material.get("name", "")
        if not name.startswith("GAME • "):
            continue
        surface = name.split(" • ")[1]
        pbr = material.get("pbrMetallicRoughness", {})
        if surface == "Markings":
            pbr["roughnessFactor"] = 0.70
            continue
        if surface not in ("WeaponMetal", "Furniture", "Magazine"):
            continue
        texture = document["textures"][pbr["metallicRoughnessTexture"]["index"]]
        image_index = texture["source"]
        image = document["images"][image_index]
        if not image.get("name", "").startswith("VERAS54_" + surface + "_100_Metallic"):
            raise ValueError(f"{path}: неожиданная карта {image}")
        surfaces.add(surface)
        if image_index in replaced:
            continue
        view = document["bufferViews"][image["bufferView"]]
        offset = view.get("byteOffset", 0)
        png = original_binary[offset:offset + view["byteLength"]]
        corrected = matte_orm(png, surface)
        binary.extend(b"\0" * (-len(binary) % 4))
        image["bufferView"] = len(document["bufferViews"])
        document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary),
                                      "byteLength": len(corrected)})
        binary.extend(corrected)
        replaced.add(image_index)
    if surfaces != {"WeaponMetal", "Furniture", "Magazine"}:
        raise ValueError(f"{path}: неполный комплект материалов {surfaces}")
    document["asset"].setdefault("extras", {})[MARKER] = VERSION
    document["buffers"][0]["byteLength"] = len(binary)
    binary.extend(b"\0" * (-len(binary) % 4))
    json_chunk = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * (-len(json_chunk) % 4)
    result = (struct.pack("<4sII", b"glTF", 2, 28 + len(json_chunk) + len(binary))
              + struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk
              + struct.pack("<II", len(binary), 0x004E4942) + binary)
    temporary = path.with_suffix(".glb.tmp")
    temporary.write_bytes(result)
    temporary.replace(path)
    print(f"{path.name}: исправлены {len(replaced)} карты ORM; исходный бинарный блок сохранён")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="*")
    args = parser.parse_args()
    for path in args.paths or DEFAULTS:
        fix_glb(path)
