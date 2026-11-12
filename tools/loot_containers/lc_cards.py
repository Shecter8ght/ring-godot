"""Контейнеры для лута, партия 1: новые карточки каталога отделок (tools/asset_kit/finish/finishes.json), которых для
этой партии не хватало. Повторный запуск не дублирует записи. Числа — по ближайшим карточкам (порошок — CK-GRY-MAT /
PW-WHT-MAT, пластик — PL-BLK-TEX, ткань — FB-OXF-RED, войлок — CP-WOL-RED), цвета — по серийным изделиям (см.
asset-state.md, образцы).

  python -X utf8 tools/loot_containers/lc_cards.py
"""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "asset_kit" / "finish" / "finishes.json"
ORIGIN = ("Контейнеры для лута, партия 1 (tools/loot_containers), 2026-11-13: интервью — «гражданское заводское» (порошковая "
          "краска с лёгкой шагренью, атлас), сейфы графит и серый, оружейный шкаф серо-зелёный, картотека светло-серая, "
          "касса серо-бежевый пластик, сумка красная со светоотражающими полосами; выбор по слотам сделан исполнителем")


def powder(code, title, color, rough=0.42, mm=0.7, use=""):
    return {"code": code, "group": "enamel", "title": title, "step": "атлас", "kind": "coating",
            "base": {"color": color, "rough": rough, "metal": 0.0},
            "grain": {"mm": mm, "rough": 0.2, "color": 0.03, "height": 0.003}, "layers": [{"type": "mottle", "mm": 22.0, "color": 0.035, "rough": 0.06}], "use": use, "origin": ORIGIN,
            "godot": "StandardMaterial3D по картам"}


def abs_plastic(code, title, color, rough=0.46, use="", stipple=True):
    f = {"code": code, "group": "polymer", "title": title, "step": "мат" if rough >= 0.5 else "атлас", "kind": "coating",
         "base": {"color": color, "rough": rough, "metal": 0.0},
         "grain": {"mm": 0.25, "rough": 0.2, "color": 0.05, "height": 0.003}, "use": use, "origin": ORIGIN,
         "godot": "StandardMaterial3D по картам"}
    if stipple:
        f["layers"] = [{"type": "stipple", "dots_mm": 0.12, "rough": 0.2, "height": 0.002}, {"type": "flow", "rough": -0.04}]
    return f


NEW = [
    powder("PW-GRA-SAT", "Порошок графит, шагрень, атлас", [0.15, 0.155, 0.16], 0.40, 1.6, "Напольные сейфы, корпуса"),
    powder("PW-GRY-SAT", "Порошок серый, шагрень, атлас", [0.40, 0.41, 0.42], 0.42, 1.6, "Сейфы-ячейки"),
    powder("PW-LGR-SAT", "Порошок светло-серый, шагрень, атлас", [0.62, 0.63, 0.62], 0.42, 1.6, "Картотека, нутро сейфа"),
    powder("PW-SGN-SAT", "Порошок серо-зелёный, шагрень, атлас", [0.29, 0.34, 0.29], 0.42, 1.6, "Оружейные шкафы"),
    {"code": "PW-WHT-SMO", "group": "enamel", "title": "Эмаль порошковая белая, гладкая, полуглянец", "step": "атлас",
     "kind": "coating", "base": {"color": [0.84, 0.84, 0.82], "rough": 0.32, "metal": 0.0},
     "grain": {"mm": 1.2, "rough": 0.08, "color": 0.02, "height": 0.002}, "layers": [{"type": "mottle", "mm": 22.0, "color": 0.03, "rough": 0.05}], "use": "Настенные аптечки",
     "origin": ORIGIN, "godot": "StandardMaterial3D по картам"},
    abs_plastic("PL-BGE-TEX", "АБС серо-бежевый, мелкая фактура литья", [0.62, 0.59, 0.52], 0.46, "Корпуса касс и принтеров"),
    abs_plastic("PL-DGR-TEX", "АБС тёмно-серый, фактура литья (клавиши)", [0.15, 0.155, 0.16], 0.5, "Клавиши касс"),
    abs_plastic("PL-LGR-TEX", "АБС светло-серый, фактура литья (цифровой блок)", [0.48, 0.48, 0.47], 0.5, "Цифровой блок касс"),
    abs_plastic("PL-RED-TEX", "АБС красный, фактура литья", [0.55, 0.07, 0.06], 0.46, "Цветные клавиши, ярлычки"),
    abs_plastic("PL-GRN-TEX", "АБС зелёный, фактура литья", [0.12, 0.40, 0.18], 0.46, "Цветные клавиши, ярлычки"),
    abs_plastic("PL-BLU-TEX", "АБС синий, фактура литья", [0.08, 0.20, 0.50], 0.46, "Цветные клавиши, ярлычки"),
    {"code": "FT-BLK-MAT", "group": "fabric", "title": "Войлок чёрный, ложементы", "step": "мат", "kind": "coating",
     "base": {"color": [0.045, 0.045, 0.047], "rough": 0.95, "metal": 0.0}, "grain": None,
     "material": {"res": "fabric_felt/fabric_felt", "mm": 30.0,
                  "params": {"fabric_color": [0.05, 0.05, 0.052], "fabric_roughness": 0.95}},
     "use": "Ложементы оружейных шкафов", "origin": ORIGIN,
     "godot": "StandardMaterial3D по картам; блеск ворса — rim (Sheen в Blender)"},
    {"code": "FM-DGR-MAT", "group": "fabric", "title": "Пенополиэтилен тёмно-серый (вкладыши)", "step": "мат", "kind": "coating",
     "base": {"color": [0.10, 0.10, 0.11], "rough": 0.93, "metal": 0.0},
     "grain": {"mm": 0.6, "rough": 0.04, "color": 0.05, "height": 0.004}, "use": "Вкладыши укладок", "origin": ORIGIN,
     "godot": "StandardMaterial3D по картам"},
    {"code": "RF-SLV-TAP", "group": "fabric", "title": "Светоотражающая лента серебристо-серая (микропризма)",
     "step": "атлас", "kind": "coating", "base": {"color": [0.62, 0.64, 0.62], "rough": 0.36, "metal": 0.0},
     "grain": {"mm": 0.3, "rough": 0.12, "color": 0.03, "height": 0.0006}, "use": "Ленты на сумках скорой помощи",
     "origin": ORIGIN, "godot": "StandardMaterial3D по картам; блик под светом — в игре отдельным слоем не делается"},
]


def main() -> None:
    """Записи — по одной строке, как в файле: вставка перед закрывающей скобкой списка, остальное не трогаем."""
    text = CATALOG.read_text(encoding="utf-8")
    have = set(f["code"] for f in json.loads(text)["finishes"])
    add = [f for f in NEW if f["code"] not in have]
    lines_in = text.split("\n")
    for f in NEW:
        if f["code"] in have:     # запись уже есть — заменить строку (правка чисел карточки)
            key = '{"code": "%s"' % f["code"]
            for i, ln in enumerate(lines_in):
                if ln.lstrip().startswith(key):
                    tail_comma = "," if ln.rstrip().endswith(",") else ""
                    lines_in[i] = "    " + json.dumps(f, ensure_ascii=False) + tail_comma
    text = "\n".join(lines_in)
    if add:
        tail = "\n  ]\n}"
        i = text.rstrip().rfind(tail)
        lines = ",\n".join("    " + json.dumps(f, ensure_ascii=False) for f in add)
        text = text[:i] + ",\n" + lines + text[i:]
    CATALOG.write_text(text, encoding="utf-8", newline="\n")
    print("добавлено карточек:", len(add))


if __name__ == "__main__":
    main()
