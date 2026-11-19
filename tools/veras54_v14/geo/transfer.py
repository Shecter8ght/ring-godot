# ВЕРАС-54 v14: что переходит из принятой v13 без изменений (assemble.py --base <v13.blend>): затвор с выбрасывателем,
# шток с поршнем, возвратная пружина, патроны в магазине.
# (начало имени объекта v13, коллекция v14, материал v14)
GROUPS = [
    # С 19.11 по слову владельца перед оружия и целик строятся по образцу (part_gas, part_muzzle, part_sights):
    # ствол, газовый узел с мушкой, дульное устройство и целик v13 больше не переносятся.
    # затвор и выбрасыватель v13 тоже не переносятся: новый затвор с досылателем и пазом отражателя — part_bolt
    ("Bolt carrier • gas piston", "Затворная группа", "Steel_bare"),
    # направляющая пружины v13 не переносится: её упор торчал сквозь задний скос крышки — она строится заново (part_bolt)
    ("Recoil spring • coil", "Затворная группа", "Spring_steel"),
    ("Magazine • loaded case", "Патроны", "Case_lacquer"),
    ("Magazine • loaded projectile", "Патроны", "Bullet_jacket"),
]
# родитель перенесённой детали в v14 (начало имени объекта v13 → имя объекта v14): подвижное едет за своим узлом
PARENT_OF = {
    "Bolt carrier • gas piston": "Bolt_Carrier",
    "Magazine • loaded": "Magazine_Body",
}


# точное имя → родитель (смотрится раньше, чем начало имени): пуля верхнего патрона едет за его гильзой
PARENT_EXACT = {"Magazine • loaded projectile 1": "Magazine • loaded case 1"}


class _Parents(dict):
    def get(self, name, default=None):
        if name in PARENT_EXACT:
            return PARENT_EXACT[name]
        for prefix, parent in PARENT_OF.items():
            if name.startswith(prefix):
                return parent
        return default


PARENTS = _Parents()
# Стопка патронов v13 сидела слишком низко для досылания: вся стопка поворачивается вокруг оси Y через центр дуги
# магазина (начало имени → (X центра, Z центра, угол в градусах; плюс опускает то, что впереди центра)). Числа — отчёт
# исполнителя магазина; None — не поворачивать.
ROT_Y = {"Magazine • loaded": (524.18, 9.24, 1.939)}
# начало координат перенесённой детали (мм), ТОЧНОЕ имя: у пружины — задний конец (к нему она сжимается приводом рига),
# у верхнего патрона — центр дна гильзы после поворота стопки (вокруг него патрон доворачивается при досылании)
TOP_ROUND_BASE = (151.66, 4.15, -16.29)
ORIGIN = {"Recoil spring • coil": (17.3, 0.0, 15.5)}
if TOP_ROUND_BASE:
    ORIGIN["Magazine • loaded case 1"] = TOP_ROUND_BASE
    ORIGIN["Magazine • loaded projectile 1"] = TOP_ROUND_BASE
# сдвиг группы по X, мм (начало имени объекта v13 → сдвиг)
SHIFT_X = {}


def group_of(name):
    for prefix, coll, mat in GROUPS:
        if name.startswith(prefix):
            return coll, mat, None
    return None
