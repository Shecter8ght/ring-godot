"""ВЕРАС-54 v14: спецификация заводской отделки (finish-spec.json) — слоты деталей и выбранные карточки каталога.

    python -X utf8 tools/veras54_v14/tex/tex_spec.py            # создать / обновить «Карты v14/finish-spec.json»

Интервью 2026-11-19: владелец — «Всё по образцу» (Sketchfab «Kalashnikov AK-12», RaduCarstean; снимки образца под его
светом — _asset_src/veras54_v14/refs_finish). Слоты и детали — по описи формы (tex_dump.py). Файл пишется заново из
этой таблицы, кроме полей, которые ведёт страница каталога и приёмка (favorites, requests, history, accepted).
"""
from __future__ import annotations

import json
from pathlib import Path

LIB = Path(r"E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54")
SPEC = LIB / "Карты v14" / "finish-spec.json"
MODEL = LIB / "Карты v14" / "ВЕРАС-54_развёртка_v14_01.blend"

# Поправки чисел карточек под модель (первый проход отделки, 2026-11-19): пятна тона на автомате длиной 940 мм —
# действующий размер hue_mm / scale = 150 мм (70 мм карточки давали «камуфляж»); крупные градиенты мельче карточки
# (scale 1,7) и лёгкая неровность покрытия двумя размерами — иначе самопроверка: «однотонно на 1 и 4 см»;
# hue — сила тёплых и холодных пятен (владелец: «и холодные, и тёплые оттенки должны быть»)
_MOTTLE_STEEL = [{"type": "mottle", "mm": 80.0, "color": 0.012, "rough": 0.06},
                 {"type": "mottle", "mm": 40.0, "color": 0.006, "rough": 0.03}]
_POLY_LAYERS = [{"type": "stipple", "dots_mm": 0.1, "rough": 0.25, "height": 0.003}, {"type": "flow", "rough": -0.05},
                {"type": "mottle", "mm": 150.0, "color": 0.015, "rough": 0.05},
                {"type": "mottle", "mm": 40.0, "color": 0.0, "rough": 0.03}]


def _steel(hue):
    return {"gradients": {"color": 0.04, "rough": 0.05, "scale": 1.7, "hue_mm": 255.0, "hue": hue}, "layers": _MOTTLE_STEEL}


_SMALL = {"gradients": {"hue_mm": 150.0}}

# слот: (название, карточка, детали, правки чисел, примечание)
SLOTS = {
    "corpus": ("Корпус — сталь под чёрной оружейной краской, атлас", "GP-BLK-SAT",
               ["Receiver", "Dust_Cover", "Top_Rail", "Cover_Rear_Block", "Front_Block", "Gas_Block", "Gas_Tube",
                "Rear_Sight_Base", "Rear_Sight_Yoke", "Rear_Sight_Leaf", "Rear_Sight_Slider", "Trigger_Guard",
                "Selector_Lever", "Hinge_Base", "Stock_Knuckle", "Mag_Catch", "Hinge_Latch"], _steel(0.35), ""),
    "dark": ("Ствол, дульное устройство и мелкая сталь — чёрный фосфат, мат", "PH-BLK-MAT",
             ["Barrel", "Barrel_Breech", "Barrel_Collar", "Muzzle_Body", "Muzzle_Collar", "Muzzle_Tip",
              "Front_Sight_Post", "Rear_Sight_Button_L", "Rear_Sight_Button_R", "Rear_Sight_Drum", "Rear_Sight_Knob",
              "Cover_Button", "Handguard_Latch", "Side_Rail_Screws", "Sling_Stud", "Stock_Screws", "Trigger",
              "Gas_Block_Pins", "Gas_Tube_Pins", "Hinge_Pin", "Mag_Catch_Axle", "Rear_Sight_Axle", "Ejector"], _steel(0.25), ""),
    "carrier": ("Затворная рама с рукояткой — чёрное оксидирование, мат", "OX-BLK-MAT",
                ["Bolt_Carrier", "Charging_Handle"], _steel(0.25),
                "Владелец: рама чёрная, как корпус. Краска на трущейся детали не держится — оксид того же тона."),
    "bolt": ("Затвор, выбрасыватель, направляющий стержень — светлая сталь", "ST-WHT-SAT",
             ["Bolt", "Bolt_Extractor", "Recoil_Guide_Rod"], _SMALL, ""),
    "piston": ("Шток с поршнем — твёрдый хром", "CR-SAT", ["Bolt carrier • gas piston"], _SMALL, ""),
    "spring": ("Пружины — голая пружинная сталь", "ST-WHT-SAT",
               ["Recoil spring • coil", "Bolt_Extractor_Spring", "Hinge_Spring", "Magazine_Spring"],
               {"base": {"color": [0.42, 0.42, 0.43], "rough": 0.42}, "layers": [], "gradients": {"hue_mm": 150.0}},
               "Пружинная проволока темнее и матовее шлифованной стали затвора, без рисок шлифовки."),
    "polymer_go": ("Приклад, рукоятка, магазин — серо-оливковый полимер, зерно литья", "PL-GOL-TEX",
                   ["Stock_Body", "Stock_Latch", "Pistol_Grip", "Grip_Cap", "Grip_Button_L", "Grip_Button_R",
                    "Magazine_Body", "Magazine_Floorplate", "Magazine_Follower"],
                   {"base": {"color": [0.18, 0.18, 0.158]}, "gradients": {"scale": 1.7, "hue_mm": 255.0, "hue": 0.3},
                    "layers": _POLY_LAYERS},
                   "Цвет темнее карточки PL-GOL-TEX: в первом проходе полимер вышел заметно светлее образца."),
    "polymer_blk": ("Цевьё — чёрный полимер, зерно литья", "PL-BLK-TEX", ["Handguard_Lower", "Handguard_Upper"],
                    {"gradients": {"scale": 1.7, "hue_mm": 255.0, "hue": 0.35}, "layers": _POLY_LAYERS}, ""),
    "alu": ("Труба приклада и боковые планки — чёрное анодирование", "AN-BLK-SAT",
            ["Stock_Tube", "Side_Rail_L", "Side_Rail_R"], _steel(0.35), ""),
    "rubber": ("Затыльник — чёрная резина", "RB-BLK-MAT", ["Butt_Pad"], _SMALL, ""),
    "case": ("Гильзы — сталь под зелёным лаком", "ST-LAC-GRN",
             ["Chambered_Case"] + [f"Magazine • loaded case {i}" for i in range(1, 31)], _SMALL, ""),
    "bullet": ("Пули — томпак", "CU-TMP",
               ["Chambered_Bullet"] + [f"Magazine • loaded projectile {i}" for i in range(1, 31)], _SMALL, ""),
    "primer": ("Капсюль — медь (маской на донце гильзы)", "CU-PRM", [], _SMALL, "Зона внутри сетки гильзы — маска."),
    "sealant": ("Красный лак у капсюля и дульца (маской)", "LQ-RED-GLS", [], _SMALL, "Зона внутри сетки гильзы — маска."),
}

INTERVIEW = [
    ("Образец готовой отделки", "Модель Sketchfab «Kalashnikov AK-12» (RaduCarstean) — «полный референс и по форме, и по "
     "текстурированию» (владелец, 2026-11-18); снимки под светом образца — _asset_src/veras54_v14/refs_finish"),
    ("Цвет полимера", "Как у образца: приклад, рукоятка и магазин серо-оливковые, цевьё чёрное («Всё по образцу», 2026-11-19)"),
    ("Блеск чёрной стали корпуса", "Как у образца: атлас — заводская краска со сдержанным блеском"),
    ("Затворная рама", "Чёрная, как корпус; затвор — светлая сталь, шток с поршнем — хром"),
    ("Маркировка", "Гравировка без заливки краской (вымышленная: «ВЕРАС-54», «5,45×39», «АВ / 2 / ОД», «0547», цифры магазина)"),
    ("Прочее без вопросов (владелец не возразил)", "Ствол, дульное устройство, мелкая сталь — чёрный матовый фосфат; пружины — "
     "голая сталь; затыльник — чёрная резина; гильзы — сталь под зелёным лаком, пули — томпак; полимер матовый с зерном литья"),
    ("Износ", "Потёртости, царапины и ржавчина образца — следующим этапом (weapon-asset-wear), не в заводской отделке"),
]


def main() -> None:
    old = json.loads(SPEC.read_text(encoding="utf-8")) if SPEC.exists() else {}
    spec = {
        "schema": "ring-finish-spec/1", "asset": "ВЕРАС-54 v14", "model": str(MODEL), "stage": "factory",
        "slots": [{"id": k, "title": t, "parts": parts, "finish": code, "overrides": ov, "note": note}
                  for k, (t, code, parts, ov, note) in SLOTS.items()],
        "interview": [{"q": q, "a": a} for q, a in INTERVIEW],
        "favorites": old.get("favorites", []), "requests": old.get("requests", []),
        "history": old.get("history", []), "accepted": old.get("accepted", False),
    }
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("SPEC", SPEC, len(spec["slots"]), "слотов,", sum(len(s["parts"]) for s in spec["slots"]), "деталей")


if __name__ == "__main__":
    main()
