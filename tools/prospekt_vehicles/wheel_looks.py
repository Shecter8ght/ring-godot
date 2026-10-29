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


def look(style: str, key: str | None = None) -> dict:
    """Вариант стиля по ключу (нет ключа — основной)."""
    items = LOOKS[style]
    return next((x for x in items if x["key"] == key), items[0])


def rounds() -> list[dict]:
    """Проходы выгрузки карт: в k-м проходе у каждого набора свой k-й вариант (короче — повторяет последний)."""
    n = max(len(v) for v in LOOKS.values())
    return [{ts: LOOKS[st][min(k, len(LOOKS[st]) - 1)]["key"] for ts, st in SET_STYLE.items()} for k in range(n)]


if __name__ == "__main__":                        # для цепочки: строки «Набор=вариант,…» по проходам
    for r in rounds():
        print(",".join(f"{ts}={k}" for ts, k in r.items()))
