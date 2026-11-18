# ВЕРАС-54 v14: что переходит из принятой v13 без изменений (assemble.py --base <v13.blend>).
# Узлы, которых нет в списке замечаний владельца и чьи размеры у v13 заводские: ствол, газовый узел с мушкой,
# дульное устройство, затвор со штоком и пружиной, целик (принят с U-образной прорезью), патроны в магазине.
# (начало имени объекта v13, коллекция v14, материал v14)
GROUPS = [
    ("Barrel band", "Ствол и газовый узел", "Steel_blued"),
    ("Barrel •", "Ствол и газовый узел", "Steel_blued"),
    ("Front bayonet loop", "Ствол и газовый узел", "Steel_blued"),
    ("Front sight", "Ствол и газовый узел", "Steel_blued"),
    ("Gas block", "Ствол и газовый узел", "Steel_blued"),
    ("Gas tube", "Ствол и газовый узел", "Steel_blued"),
    ("Muzzle •", "Ствол и газовый узел", "Steel_blued"),      # дульная часть ствола и хомут перед дульным устройством
    ("Brake •", "Дульное устройство", "Steel_blued"),
    ("Muzzle brake", "Дульное устройство", "Steel_blued"),
    ("Bolt • extractor", "Затворная группа", "Steel_bare"),
    ("Bolt • rotating head", "Затворная группа", "Steel_bare"),
    ("Bolt carrier • gas piston", "Затворная группа", "Steel_bare"),
    # направляющая пружины v13 не переносится: её упор торчал сквозь задний скос крышки — она строится заново (part_bolt)
    ("Recoil spring • coil", "Затворная группа", "Spring_steel"),
    ("Rear sight", "Целик", "Steel_blued"),
    ("Magazine • loaded case", "Патроны", "Case_lacquer"),
    ("Magazine • loaded projectile", "Патроны", "Bullet_jacket"),
]
# родитель перенесённой детали в v14 (начало имени объекта v13 → имя объекта v14): подвижное едет за своим узлом
PARENT_OF = {
    "Bolt • extractor": "Bolt_Carrier",
    "Bolt • rotating head": "Bolt_Carrier",
    "Bolt carrier • gas piston": "Bolt_Carrier",
    "Magazine • loaded": "Magazine_Body",
    "Rear sight": "Dust_Cover",      # целик стоит на планке крышки и поднимается вместе с ней
}


class _Parents(dict):
    def get(self, name, default=None):
        for prefix, parent in PARENT_OF.items():
            if name.startswith(prefix):
                return parent
        return default


PARENTS = _Parents()
# начало координат перенесённой детали (мм): у пружины — задний конец, к нему она сжимается приводом рига
ORIGIN = {"Recoil spring • coil": (17.3, 0.0, 15.5)}
# сдвиг группы по X, мм (начало имени объекта v13 → сдвиг)
SHIFT_X = {"Rear sight": 21.0}


def group_of(name):
    for prefix, coll, mat in GROUPS:
        if name.startswith(prefix):
            return coll, mat, None
    return None
