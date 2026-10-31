"""Транспорт «Проспекта»: варианты отделки колёс v2 — цвет, глянец, износ (один источник для Painter и Blender).

Владелец 2026-10-29: «сделай вариации цветов, пусть будет ещё чёрный и какой-нибудь коричневый и разную степень
глянцевости, на литых можно и совсем новьё сделать блестящее; нужно разнообразие». Вариант — словарь: key (имя в файлах
карт), name (по-русски, в файле просмотра), color (sRGB), metal, rough (шероховатость основы), age (0 — новое: без
царапин, сколов, коррозии и пыли; 1 — брошенная машина), flakes (зерно металлика, 0 — краска без зерна).
Первый вариант стиля — основной (тот, что был в v01).
"""

LOOKS = {
    "cap": [
        dict(key="silver", name="Колпак — серебрянка, полуглянец", color=(0.66, 0.67, 0.68), metal=0.6, rough=0.30,
             age=1.0, flakes=0.35),
        dict(key="black", name="Колпак — чёрный пластик, мат", color=(0.035, 0.035, 0.037), metal=0.0, rough=0.62,
             age=0.9, flakes=0.0),
        dict(key="graphite", name="Колпак — графит, глянец", color=(0.34, 0.34, 0.36), metal=0.6, rough=0.20,
             age=0.6, flakes=0.3),
    ],
    "steel": [
        dict(key="silver", name="Штамповка — серебро, полуглянец", color=(0.60, 0.61, 0.62), metal=0.75, rough=0.36,
             age=1.0, flakes=0.35),
        dict(key="black", name="Штамповка — чёрная эмаль, глянец", color=(0.025, 0.025, 0.027), metal=0.0, rough=0.20,
             age=0.9, flakes=0.0),
        dict(key="brown", name="Штамповка — коричневая эмаль, мат", color=(0.25, 0.14, 0.08), metal=0.0, rough=0.56,
             age=1.1, flakes=0.0),
    ],
    "alloy": [
        dict(key="silver", name="Литой — серебро под лаком, б/у", color=(0.76, 0.77, 0.78), metal=1.0, rough=0.30,
             age=1.0, flakes=0.4),
        dict(key="new", name="Литой — серебро, новые, блестящие", color=(0.84, 0.85, 0.86), metal=1.0, rough=0.10,
             age=0.0, flakes=0.3),
        dict(key="black", name="Литой — чёрный глянец", color=(0.02, 0.02, 0.022), metal=0.0, rough=0.12,
             age=0.55, flakes=0.0),
        dict(key="bronze", name="Литой — бронза, мат", color=(0.30, 0.21, 0.13), metal=0.85, rough=0.48,
             age=0.8, flakes=0.3),
        dict(key="graphite", name="Литой — графит, полуглянец", color=(0.36, 0.36, 0.38), metal=0.9, rough=0.26,
             age=0.5, flakes=0.35),
    ],
}

SET_STYLE = {"WheelCap": "cap", "WheelSteel": "steel", "WheelAlloy": "alloy"}

# Какие колёса у машин (владелец 2026-10-29: «да, ставь на машины» — вперемешку): стиль и вариант на класс. Колесо у
# машины одно на все места, у битой спущено только переднее левое, а три других — колёса целой той же машины, поэтому у
# битой стиль и вариант — как у целой (иначе на одной машине два вида дисков); разнообразие — между классами.
# У сгоревшей — металл диска того же стиля (колпак сгорел — штамповка под ним). Коробчатые (автобусы, ГАЗели) —
# грузовая штамповка (vwheels.truck_disc) в краске варианта стиля steel.
CAR_WHEELS = {
    "sedan": {"clean": ("cap", "silver"), "burnt": ("steel", None)},
    "hatch": {"clean": ("alloy", "bronze")},
    "wagon": {"clean": ("steel", "brown")},
    "suv": {"clean": ("alloy", "new")},
    "taxi": {"clean": ("steel", "black")},
    "police": {"clean": ("cap", "graphite"), "burnt": ("steel", None)},
    "bus12": {"clean": ("truck", "silver")},
    "paz": {"clean": ("truck", "black")},
    "gazel": {"clean": ("truck", "silver")},
    "van": {"clean": ("truck", "black")},
    "ambulance": {"clean": ("truck", "silver")},
    "bus12_over": {"over": ("truck", "silver")},
}


def car_wheel(name: str, fam: str) -> tuple[str, str | None]:
    """(стиль, вариант) колеса класса name в семье fam; семьи нет в таблице — как у целой."""
    t = CAR_WHEELS[name]
    return t.get(fam) or t.get("clean") or next(iter(t.values()))


def stack_arg(name: str, fam: str) -> str:
    """Ключ задания Painter «wheel=стиль:вариант» (грузовая штамповка красится как steel)."""
    style, key = car_wheel(name, fam)
    return f"wheel={'steel' if style == 'truck' else style}:{key or ''}"


def look(style: str, key: str | None = None) -> dict:
    """Вариант стиля по ключу (нет ключа — основной)."""
    items = LOOKS[style]
    return next((x for x in items if x["key"] == key), items[0])


def rounds() -> list[dict]:
    """Проходы выгрузки карт: в k-м проходе у каждого набора свой k-й вариант (короче — повторяет последний)."""
    n = max(len(v) for v in LOOKS.values())
    return [{ts: LOOKS[st][min(k, len(LOOKS[st]) - 1)]["key"] for ts, st in SET_STYLE.items()} for k in range(n)]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3 and sys.argv[1] == "arg":   # wheels_cars.sh: ключ задания Painter класса и семьи
        print(stack_arg(sys.argv[2], sys.argv[3]))
    else:                                           # wheels_finish.sh: строки «Набор=вариант,…» по проходам
        for r in rounds():
            print(",".join(f"{ts}={k}" for ts, k in r.items()))
