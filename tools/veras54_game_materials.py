"""Матовая отделка игровых GLB ВЕРАС-54 после экспорта из Blender.

python tools/veras54_game_materials.py [путь.glb ...]
Меняет только упакованные карты Roughness/Metallic оружия и шероховатость
маркировки. Исходные бинарные данные сеток, рук, скелетов и клипов сохраняются.
Повторный запуск для той же версии отделки ничего не меняет.

v2 (владелец, 2026-10-10): по автомату не должны скользить блики ламп и солнца —
всё матовое, блеск остаётся только у затворной рамы и трубки приклада. Их места на
развёртке — tools/veras54_gloss.mask (PNG; пишет tools/export_veras54.py из GameUV).

python tools/veras54_game_materials.py --states
Карты состояний 60 % и 20 % (износ из библиотеки модели) с той же матовой отделкой:
assets/models/weapons/veras54/states/veras54_<поверхность>_<состояние>_{albedo,normal,orm}.png.
В GLB зашито состояние 100 %; игра подменяет карты по ресурсу ствола (WeaponCondition).
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

VERSION = 2
GLOSS_MASK = Path(__file__).resolve().parent / "veras54_gloss.mask"
# Матовое покрытие: бликов нет, цвет меняется только от освещённости.
MATTE_ROUGHNESS = 0.94
# Открытая сталь вне затвора и трубки (оси, винты): матовая, но остаётся металлом.
MATTE_STEEL = {"roughness": 0.86, "metallic": 0.6}
STATE_SOURCE = Path("E:/Models Blender/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Риг v01/Текстуры")
STATE_PX = 2048
MARKER = "ring_veras54_material_finish"
ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [ROOT / "assets/models/weapons/veras54" / name
            for name in ("veras54.glb", "veras54_viewmodel.glb", "veras54_detail.glb")]


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


def gloss_mask(size: tuple[int, int]) -> np.ndarray:
    """Где на развёртке металла блеск остаётся исходным (затворная рама, трубка приклада)."""
    with Image.open(GLOSS_MASK) as mask:
        return np.array(mask.convert("L").resize(size, Image.NEAREST)) > 127


def matte_channels(roughness: np.ndarray, metallic: np.ndarray, surface: str) -> None:
    """Матовая отделка на месте: каналы 0..1, размер — как у карты."""
    steel = metallic >= 0.8
    if surface == "WeaponMetal":
        # Карта разделяет чёрную отделку и открытую сталь (~1); блеск — только по маске.
        matte = ~gloss_mask((roughness.shape[1], roughness.shape[0]))
    elif surface in ("Furniture", "Magazine"):
        matte = np.ones(roughness.shape, dtype=bool)
    else:
        raise ValueError(f"Неизвестная поверхность: {surface}")
    roughness[matte & ~steel] = MATTE_ROUGHNESS
    metallic[matte & ~steel] = 0.0
    roughness[matte & steel] = MATTE_STEEL["roughness"]
    metallic[matte & steel] = MATTE_STEEL["metallic"]


def matte_orm(png: bytes, surface: str) -> bytes:
    source = Image.open(BytesIO(png))
    pixels = np.array(source.convert("RGB"), dtype=np.uint8)
    roughness = pixels[:, :, 1].astype(np.float32) / 255.0
    metallic = pixels[:, :, 2].astype(np.float32) / 255.0
    matte_channels(roughness, metallic, surface)
    pixels[:, :, 1] = np.rint(roughness * 255).astype(np.uint8)
    pixels[:, :, 2] = np.rint(metallic * 255).astype(np.uint8)
    output = BytesIO()
    Image.fromarray(pixels).save(output, format="PNG")
    return output.getvalue()


def write_states() -> None:
    """Карты изношенных состояний из библиотеки модели → assets/…/veras54/states (2048, ORM упакован)."""
    out = ROOT / "assets/models/weapons/veras54/states"
    out.mkdir(parents=True, exist_ok=True)
    size = (STATE_PX, STATE_PX)
    for state in (60, 20):
        folder = STATE_SOURCE / f"{state:03d}"
        for surface in ("WeaponMetal", "Furniture", "Magazine"):
            stem = folder / f"VERAS54_{surface}_{state:03d}_"
            Image.open(str(stem) + "BaseColor.png").convert("RGB").resize(size, Image.LANCZOS).save(
                out / f"veras54_{surface}_{state}_albedo.png")
            Image.open(str(stem) + "Normal.png").convert("RGB").resize(size, Image.LANCZOS).save(
                out / f"veras54_{surface}_{state}_normal.png")
            roughness = np.array(Image.open(str(stem) + "Roughness.png").convert("L").resize(size, Image.LANCZOS),
                                 dtype=np.float32) / 255.0
            metallic = np.array(Image.open(str(stem) + "Metallic.png").convert("L").resize(size, Image.LANCZOS),
                                dtype=np.float32) / 255.0
            matte_channels(roughness, metallic, surface)
            orm = np.full((STATE_PX, STATE_PX, 3), 255, dtype=np.uint8)
            orm[:, :, 1] = np.rint(roughness * 255).astype(np.uint8)
            orm[:, :, 2] = np.rint(metallic * 255).astype(np.uint8)
            Image.fromarray(orm).save(out / f"veras54_{surface}_{state}_orm.png")
        Image.open(folder / f"VERAS54_Markings_{state:03d}_BaseColorAlpha.png").convert("RGBA").resize(
            size, Image.LANCZOS).save(out / f"veras54_Markings_{state}_albedo.png")
        print(f"состояние {state}: карты записаны в {out}")


def fix_glb(path: Path) -> bool:
    document, original_binary = read_glb(path)
    extras = document.get("asset", {}).get("extras", {})
    if extras.get(MARKER) == VERSION:
        print(f"{path.name}: матовая отделка v{VERSION} уже применена")
        return False
    # v1 оставила сталь (metallic >= 0.8) исходной, а покрытие v2 задаёт заново — поверх v1 можно.
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
            pbr["roughnessFactor"] = MATTE_ROUGHNESS
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
    parser.add_argument("--states", action="store_true", help="записать карты состояний 60 и 20")
    args = parser.parse_args()
    if args.states:
        write_states()
    else:
        for path in args.paths or DEFAULTS:
            fix_glb(path)
