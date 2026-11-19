# ВЕРАС-54 v14, текстуры: наборы текстур (= материал в файле развёртки, набор в Painter) и детали в них — по образцу
# tools/pkp/tex_sets.py («Частокол»). Без bpy: модуль читают Blender (tex_uv.py, tex_uv_apply.py, sp_export.py,
# tex_check.py) и Painter. Слот отделки у детали — черновик по назначению детали; окончательные слоты утвердит
# владелец (finish-spec.json рядом с моделью — после выбора на карточках каталога отделок).

WORK = "E:/Games/RING-godot/_asset_src/veras54_v14/tex"     # рабочая папка
MODEL_DIR = "E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54"
SOURCE = MODEL_DIR + "/Геометрия v14/ВЕРАС-54_геометрия_v14_04.blend"   # принятая форма (четвёртая выдача 19.11)
UV_BLEND = MODEL_DIR + "/Карты v14/ВЕРАС-54_развёртка_v14_01.blend"     # та же форма с развёрткой под Painter
CONTROLS = "VERAS54_Controls"

# Площади по описи (dump.json, см²): коробка 531 + скоба 143; крышка 371 + планка 65 + колодка 48 + затыльник 32;
# основание целика 50, остальной целик ~51; цевьё 648 + боковые планки 57; ствол 281 + газовая трубка 240 + камера 110;
# дульное устройство 167; рукоятка 217 + крышка 39; приклад 650 + затыльник 196 + труба 137 + шарнир 69 + рычаг 87;
# магазин 729 + крышка 46 + подаватель 41 + пружина 25; затворная группа ~355; органы управления ~125; патрон 13.
# Плотность: при заполнении ~0,6 4K даёт 10–12 пикс/мм на 600–900 см² видимого; изнанка оболочек (стенки внутри
# коробки, цевья, магазина, приклада, рукоятки) и канал ствола — с меньшей стороной острова (INNER_K), видимое плотнее.
#
# набор: (разрешение атласа, ожидаемая плотность пикс/мм — по ней режутся длинные ленты, [детали])
SETS = {
    "receiver": (4096, 12.0, ["Receiver", "Trigger_Guard"]),
    "cover": (4096, 12.0, ["Dust_Cover", "Top_Rail", "Front_Block", "Cover_Rear_Block", "Rear_Sight_Base"]),
    "sight": (2048, 20.0, ["Rear_Sight_Leaf", "Rear_Sight_Slider", "Rear_Sight_Yoke", "Rear_Sight_Drum",
                           "Rear_Sight_Knob", "Rear_Sight_Button_L", "Rear_Sight_Button_R", "Rear_Sight_Axle"]),
    "controls": (2048, 13.0, ["Selector_Lever", "Trigger", "Mag_Catch", "Mag_Catch_Axle", "Cover_Button", "Ejector",
                              "Handguard_Latch", "Hinge_Base", "Hinge_Latch", "Hinge_Pin", "Hinge_Spring"]),
    "bolt": (4096, 15.0, ["Bolt_Carrier", "Bolt", "Bolt carrier • gas piston", "Charging_Handle", "Bolt_Extractor",
                          "Bolt_Extractor_Spring", "Recoil_Guide_Rod", "Recoil spring • coil"]),
    "barrel": (4096, 12.0, ["Barrel", "Barrel_Breech", "Barrel_Collar", "Gas_Block", "Gas_Block_Pins",
                            "Front_Sight_Post", "Gas_Tube", "Gas_Tube_Pins"]),
    "muzzle": (2048, 12.0, ["Muzzle_Body", "Muzzle_Collar", "Muzzle_Tip"]),
    "handguard": (4096, 12.0, ["Handguard_Upper", "Handguard_Lower", "Side_Rail_L", "Side_Rail_R",
                               "Side_Rail_Screws"]),
    "grip": (2048, 10.0, ["Pistol_Grip", "Grip_Cap", "Grip_Button_L", "Grip_Button_R"]),
    "stock": (4096, 10.0, ["Stock_Body", "Butt_Pad", "Stock_Latch", "Stock_Tube", "Stock_Knuckle", "Sling_Stud",
                           "Stock_Screws"]),
    "magazine": (4096, 11.0, ["Magazine_Body", "Magazine_Floorplate", "Magazine_Follower", "Magazine_Spring"]),
    # патроны: развёртка — у первого патрона магазина (гильза и пуля) и у патрона в патроннике (своя сетка формы);
    # остальные 29 патронов магазина — экземпляры той же развёртки (INSTANCES)
    "ammo": (1024, 15.0, ["Magazine • loaded case 1", "Magazine • loaded projectile 1", "Chambered_Case",
                          "Chambered_Bullet"]),
}

# экземпляры развёртки: деталь → чья развёртка (та же топология; проверяется при записи)
INSTANCES = {}
for _i in range(2, 31):
    INSTANCES[f"Magazine • loaded case {_i}"] = "Magazine • loaded case 1"
    INSTANCES[f"Magazine • loaded projectile {_i}"] = "Magazine • loaded projectile 1"

# слот отделки (черновик, по назначению детали): steel_coated — крашеная / фосфатированная сталь корпуса; steel_dark —
# ствол, дульное, мелкая сталь, оси, планки; bolt — рама, затвор, шток; spring — пружины; polymer; rubber; case; bullet
SLOTS = {
    "steel_coated": ["Receiver", "Trigger_Guard", "Dust_Cover", "Front_Block", "Cover_Rear_Block", "Rear_Sight_Base",
                     "Selector_Lever", "Mag_Catch", "Gas_Block", "Stock_Knuckle", "Stock_Tube", "Hinge_Base",
                     "Hinge_Latch"],
    "steel_dark": ["Barrel", "Barrel_Breech", "Barrel_Collar", "Gas_Tube", "Gas_Tube_Pins", "Gas_Block_Pins",
                   "Front_Sight_Post", "Muzzle_Body", "Muzzle_Collar", "Muzzle_Tip", "Top_Rail", "Rear_Sight_Leaf",
                   "Rear_Sight_Slider", "Rear_Sight_Yoke", "Rear_Sight_Drum", "Rear_Sight_Knob", "Rear_Sight_Button_L",
                   "Rear_Sight_Button_R", "Rear_Sight_Axle", "Trigger", "Mag_Catch_Axle", "Cover_Button", "Ejector",
                   "Handguard_Latch", "Hinge_Pin", "Side_Rail_L", "Side_Rail_R", "Side_Rail_Screws", "Sling_Stud",
                   "Stock_Screws", "Bolt_Extractor", "Recoil_Guide_Rod"],
    "bolt": ["Bolt_Carrier", "Bolt", "Bolt carrier • gas piston", "Charging_Handle"],
    "spring": ["Recoil spring • coil", "Bolt_Extractor_Spring", "Hinge_Spring", "Magazine_Spring"],
    "polymer": ["Handguard_Upper", "Handguard_Lower", "Pistol_Grip", "Grip_Cap", "Grip_Button_L", "Grip_Button_R",
                "Stock_Body", "Stock_Latch", "Magazine_Body", "Magazine_Floorplate", "Magazine_Follower"],
    "rubber": ["Butt_Pad"],
    "case": ["Magazine • loaded case 1", "Chambered_Case"],
    "bullet": ["Magazine • loaded projectile 1", "Chambered_Bullet"],
}
# вопрос владельцу: боковые планки цевья в форме — заглушка Alu_anodized (анодированный алюминий), в черновике —
# steel_dark; приклад и рычаг регулировки в форме — Polymer, затыльник — Rubber

# имена сеток в FBX для Painter (маска по сетке): у деталей с пробелами и «•» — понятные имена без них
SP_NAMES = {
    "Bolt carrier • gas piston": "Gas_Piston",
    "Recoil spring • coil": "Recoil_Spring",
    "Magazine • loaded case 1": "Round_Case",
    "Magazine • loaded projectile 1": "Round_Bullet",
}

# проекты Painter (~9 млн треугольников): три проекта по узлам — каждый до ~4 млн, открывается на 16 ГБ видеопамяти
PROJECTS = {
    "body": ["receiver", "cover", "sight", "controls", "bolt"],
    "front": ["barrel", "muzzle", "handguard"],
    "rear": ["grip", "stock", "magazine", "ammo"],
}
WORK_RES = 4096       # рабочее разрешение наборов в Painter не больше 4K (выгрузка — в разрешении набора SETS)

# отступы развёртки на 4K (между деталями / внутри группы одной детали); наборы 2K и 1K укладываются в своей сетке
# с отступами 8 / 4 и 6 / 3 пикс (tex_uv.PAD)
PADDING_PX = 12
GROUP_PX = 6

# изнанка оболочек (видна только вскрытой) и каналы: сторона острова против видимой
INNER_K = {"shell": 0.6, "bore": 0.25}
# правила изнанки по деталям: "shell" — стенки, смотрящие к средней плоскости XZ детали (|n_y| > 0,6) и лежащие
# глубже стенки снаружи; ("bore", r_мм) — грани ближе r к оси детали вдоль X, нормаль к оси (канал ствола, трубки)
INNER = {
    "Receiver": "shell", "Dust_Cover": "shell", "Handguard_Upper": "shell", "Handguard_Lower": "shell",
    "Magazine_Body": "shell", "Stock_Body": "shell", "Pistol_Grip": "shell",
    "Barrel": ("bore", 3.6), "Barrel_Breech": ("bore", 5.5), "Gas_Tube": ("bore", 7.0),
}

ANGLE = 60.0           # излом, по которому Smart UV делит острова
ANGLES = {"grip": 70.0, "barrel": 75.0}
RING_SPLIT = {"barrel", "muzzle"}   # кольца (рёбра трубки, дульного) — на четверти дуги


def project_of(set_name):
    for p, sets in PROJECTS.items():
        if set_name in sets:
            return p
    return None


def set_of(name):
    """Набор детали по имени объекта (экземпляры — по детали-источнику) или None."""
    name = INSTANCES.get(name, name)
    for s, (_res, _aim, names) in SETS.items():
        if name in names:
            return s
    return None


def slot_of(name):
    name = INSTANCES.get(name, name)
    for sl, names in SLOTS.items():
        if name in names:
            return sl
    return None


def sp_name(name):
    return SP_NAMES.get(name, name.replace(" ", "_").replace("•", ""))
