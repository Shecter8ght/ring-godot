# -*- coding: utf-8 -*-
"""Свет территории ТЦ по принятому профилю Проспекта (владелец, 2026-11-03).

Меняет только окружение и настройки света рейдовой карты. Расчётное небо, панорамы и
движение солнца остаются у ТЦ; геометрия и Пригород не затрагиваются.
Запуск: python -X utf8 tools/mall_map_light.py
"""
import json
import re
from pathlib import Path

import prospekt_light as source

ROOT = Path(__file__).resolve().parents[1]
ENV = "res://scenes/levels/mall/mall_environment.tres"


def main():
    env_path = ROOT / ENV.removeprefix("res://")
    env_path.write_text(source.ENV_TRES, encoding="utf-8", newline="\n")
    path = ROOT / "data/sectors/mall_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_comment"] = data["_comment"].replace(
        "Свет и небо — как у Пригорода.",
        "Свет — профиль Проспекта (tools/mall_map_light.py); своё расчётное небо и смена суток сохранены.")
    data["light"] = {k: v for k, v in source.LIGHT_KEYS.items() if k != "procedural_weather"}
    data["look"] = source.LOOK.copy()
    data["depth_fog"] = source.DEPTH_FOG.copy()
    # Сплошные тучи: то же отсутствие прямого луча, что в пасмурном Проспекте.
    for key in ("day_overcast", "dusk_overcast"):
        data["sky_hdri"][key]["sun_k"] = 0.0
    data["sky_hdri"]["day"]["sun_k"] = 1.0
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    scene_path = ROOT / "scenes/levels/mall_map.tscn"
    scene = scene_path.read_text(encoding="utf-8")
    scene = scene.replace("res://scenes/levels/zone01/zone01_environment.tres", ENV)
    match = re.search(r'(\[node name="Sun"[^\n]*\]\n)(.*?)(?=\n\[node)', scene, re.S)
    if match is None:
        raise RuntimeError("Не найдено солнце рейдовой карты")
    body = match[2]
    for key, value in {"light_color": "Color(1, 0.9, 0.76, 1)", "light_energy": "2.0",
                       "light_angular_distance": "0.53", "shadow_blur": "1.0",
                       "metadata/authored_shadow": "true"}.items():
        line = f"{key} = {value}"
        body = re.sub(r"^" + re.escape(key) + r" = .*", line, body, flags=re.M) if re.search(
            r"^" + re.escape(key) + r" = ", body, re.M) else body.rstrip() + "\n" + line + "\n"
    scene = scene[:match.start(2)] + body + scene[match.end(2):]
    scene_path.write_text(scene, encoding="utf-8", newline="\n")
    print("Территория ТЦ: окружение, свет, тени, дымка и привыкание глаза — профиль Проспекта")


if __name__ == "__main__":
    main()
