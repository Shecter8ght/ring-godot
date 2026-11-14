"""«Частокол», текстуры этап 1: файл спецификации отделки finish-spec.json рядом с моделью — слоты (детали принятой
формы v03), предложение агента (recommended) по интервью, ответы интервью. Выбор делает владелец на странице каталога
(tools/asset_kit/finish/catalog_server.py --spec …); повторный запуск не трогает выбранное (finish) и историю.

    python -X utf8 tools/pkp/tex_spec.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MODEL_DIR = Path(r"E:/Models Blender/WEAPONS/Печенег — модель")
SPEC = MODEL_DIR / "finish-spec.json"

# слот: id, название, отделка-предложение, детали (имена объектов формы v03; Box200_* и Strip_* — те же отделки)
SLOTS = [
    ("receiver", "Ствольная коробка, крышка, лоток, спуск, затыльник и плечевой упор", "OX-BLK-LAC",
     ["Receiver", "Breech_Insert", "Barrel_Lock", "Top_Cover", "Feed_Flap", "Exit_Flap", "Port_Cover", "Cover_Base_F",
      "Cover_Base_R", "Cover_Latch", "Cover_Catch", "Side_Rail", "Sling_Bar", "Box_Bracket", "Feed_Tray", "Cover_Guide",
      "Cover_Lever", "Cover_Lever_Bracket", "Feed_Lever", "Feed_Lever_Guard", "Feed_Pawl_Arm", "Retainer_Pawl",
      "Cartridge_Stop", "Trigger_Housing", "Trigger", "Safety_Lever", "Rest_Hinge", "Shoulder_Rest", "Buttplate",
      "Ejector"]),
    ("barrel", "Ствол, кожух, газовый узел, ручка для переноски, мушка", "OX-BLK-LAC",
     ["Barrel", "Flash_Hider", "Gas_Block", "Gas_Housing", "Gas_Tube", "Front_Sight_Base", "Front_Sight_Post",
      "Shroud", "Shroud_Scoop", "Carry_Handle"]),
    ("sight", "Прицел (основание, планка с цифрами, хомутик, маховичок)", "OX-BLK-LAC",
     ["Rear_Sight_Base", "Rear_Sight_Leaf", "Rear_Sight_Slider", "Rear_Sight_Notch", "Rear_Sight_Knob",
      "Rear_Sight_Button"]),
    ("bipod", "Сошки", "OX-BLK-LAC",
     ["Bipod_Yoke", "Bipod_Leg_L", "Bipod_Leg_R", "Bipod_Foot_L", "Bipod_Foot_R"]),
    ("bolt", "Затворная группа — светлая сталь: рама, затвор, поршень, рукоятка", "ST-WHT-SAT",
     ["Bolt_Carrier", "Bolt", "Bolt_Extractor", "Gas_Piston", "Charging_Handle", "Cartridge_Gripper", "Gripper_Pin",
      "Piston_Pin"]),
    ("small", "Мелкая сталь: оси, пружины, винты, вертушки и зубья коробок", "OX-BLK-MAT",
     ["Cover_Hinge_Pin", "Cover_Latch_Pin", "Cover_Lever_Pin", "Cover_Lever_Spring", "Feed_Lever_Pin",
      "Feed_Pawl_Shaft", "Retainer_Shaft", "Retainer_Spring", "Recoil_Guide", "Recoil_Spring",
      "Rear_Sight_Pin", "Rear_Sight_Spring", "Bipod_Hinge_Pin_L", "Bipod_Hinge_Pin_R", "Bipod_Pin", "Bipod_Spring",
      "Butt_Screw_L", "Butt_Screw_R", "Box100_Latch_Spring", "Box200_Latch_Spring", "Box100_Turnbutton",
      "Box200_Turnbutton", "Box100_Mount_Tooth", "Box200_Mount_Tooth", "Box100_Flap_Pin", "Box100_Hinge_Pin",
      "Box100_Latch_Pin", "Box200_Flap_Pin", "Box200_Hinge_Pin", "Box200_Latch_Pin"]),
    ("stock", "Приклад — чёрный пластик, полумат", "PL-BLK-SMO", ["Stock"]),
    ("grip", "Пистолетная рукоятка — чёрный пластик, глянец (насечка матовее)", "PL-BLK-GLS", ["Pistol_Grip"]),
    ("box", "Коробки для ленты на 100 и 200 — оливковая эмаль снаружи и внутри", "EN-OLV-SAT",
     ["Box100_Body", "Box100_Lid", "Box100_Flap", "Box100_Latch", "Box100_Mount",
      "Box200_Body", "Box200_Lid", "Box200_Flap", "Box200_Latch", "Box200_Mount"]),
    ("strap", "Ручка коробки — брезент хаки", "FB-CNV-KHK", ["Box100_Handle", "Box200_Handle"]),
    ("links", "Лента: звенья, спирали, наконечник", "PH-BLK-MAT",
     ["Belt_Link_src", "Belt_Spiral_src", "Belt_Tip", "Strip_Tip"]),
    # патрон и гильза — одна сетка с тремя материалами формы; в Painter — кусками «<объект>:<материал>»
    ("case", "Гильза — сталь под зелёным лаком (клеймо «ЧК» / «27» на донце)", "ST-LAC-GRN",
     ["Belt_Round_00:Case_lacquer", "Cartridge:Case_lacquer", "Case_Spent:Case_lacquer"]),
    ("bullet", "Пуля — томпак", "CU-TMP", ["Belt_Round_00:Bullet_jacket", "Cartridge:Bullet_jacket"]),
    ("primer", "Капсюль — медь", "CU-PRM", ["Belt_Round_00:Primer", "Cartridge:Primer", "Case_Spent:Primer"]),
    # красный лак — слой по маске поверх гильзы и капсюля (кольцо вокруг капсюля, полоска у дульца)
    ("sealant", "Красный лак: кольцо вокруг капсюля и у дульца", "LQ-RED-GLS",
     ["Belt_Round_00:Case_lacquer", "Belt_Round_00:Primer", "Cartridge:Case_lacquer", "Cartridge:Primer",
      "Case_Spent:Case_lacquer", "Case_Spent:Primer"]),
    ("rail", "Обвес: планка на крышку и цевьё — алюминий", "AN-BLK-MAT", ["Rail_Cover", "Rail_Forend"]),
    ("rail_screws", "Обвес: стяжные винты и болты", "PH-BLK-MAT",
     ["Rail_Cover_Screw_F", "Rail_Cover_Screw_R", "Forend_Bolt_A", "Forend_Bolt_B"]),
]

INTERVIEW = [
    {"q": "Образец готовой отделки", "a": "Рендеры владельца refs/owner/01–06 («материалы и текстурирование нужно "
                                          "сделать как на первых 6 скринах»); на них износ — это цель этапа 2"},
    {"q": "Сталь коробки, крышки, кожуха, ствола и сошек", "a": "Оксид под лаком, полуглянец (тёмно-серая, бликует пучками)"},
    {"q": "Затворная группа", "a": "Светлая сталь — рама, затвор, рукоятка перезаряжания"},
    {"q": "Коробки для ленты (100 и 200)", "a": "Олива, полуглянец; грунт под ней — на этапе износа"},
    {"q": "Ручка коробки", "a": "Брезент хаки, как на образце 03"},
    {"q": "Приклад и рукоятка", "a": "Рукоятка глянцевая, приклад полумат"},
    {"q": "Патроны", "a": "Гильза — сталь под зелёным лаком; пуля — томпак; капсюль медный, красный лак у капсюля и дульца"},
    {"q": "Кронштейны с планками (докупаемый обвес)", "a": "Чёрное анодирование, мат"},
    {"q": "Клеймо на донце гильз (вымышленное)", "a": "«ЧК» и «27»"},
    {"q": "Маркировка", "a": "Решено при приёмке формы: «ЧАСТОКОЛ» на крышке, «7,62×54» и «ЧК 2714» слева, «ОГОНЬ» "
                             "у флажка, цифры прицела — штамп в сетке; «ОГОНЬ» и цифры прицела залиты белой краской "
                             "(образцы 02, 05), остальное без заливки"},
    {"q": "Маски износа (этап 2)", "a": "Только из E:/Models Blender/Маски_АЛЬФА/smart masks (владелец, 2026-11-14)"},
]


def main() -> None:
    spec = {}
    if SPEC.exists():
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
    old = {s["id"]: s for s in spec.get("slots", [])}
    slots = []
    for sid, title, rec, parts in SLOTS:
        s = old.get(sid, {})
        slots.append({"id": sid, "title": title, "parts": parts, "finish": s.get("finish"), "recommended": rec,
                      "overrides": s.get("overrides", {}), "note": s.get("note", "")})
    spec.update({
        "schema": "ring-finish-spec/1", "asset": "Пулемёт «Частокол» (по мотивам ПКП «Печенег»)",
        "model": "Частокол_геометрия_v03.blend", "stage": "factory", "catalog": "tools/asset_kit/finish/finishes.json",
        "about": "Заводская отделка (этап 1): слот — группа деталей, finish — код каталога (выбор владельца), "
                 "recommended — предложение агента по интервью, overrides — правки чисел поверх карточки. Пишет "
                 "страница каталога (catalog_server.py) и агент; читают Claude и Codex.",
        "slots": slots, "interview": INTERVIEW})
    for k, v in (("favorites", []), ("requests", []), ("history", []), ("accepted", False)):
        spec.setdefault(k, v)
    tmp = SPEC.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, SPEC)
    print("SPEC", SPEC, len(slots), "слотов")


if __name__ == "__main__":
    main()
