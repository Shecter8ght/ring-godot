# -*- coding: utf-8 -*-
"""Санаторий — главный корпус v01: поэтажные планы, адресные данные помещений и дверей, проверка связей.

Решения владельца (mission_helicopter.md, пункты 28, 31–33, 38; sanatorium_map.md): 3 этажа; приёмная, администрация,
столовая с кухней, лечебные кабинеты, библиотека и помещения отдыха; спа с крытым и открытым бассейном; все этажи
доступны, часть комнат закрыта; парадная и служебные лестницы, разные маршруты; фасады — современное европейское
направление; проработка очень подробная. Всё остальное — предложение агента (docs/design/sanatorium_main_corps.md).

Координаты — те же, что на схеме участка (tools/sanatorium_map_plan.py): x — на восток, y — на север, метры игры
(правило масштаба E уже применено: ширины помещений и проходов × 1,3; мебель, ступени, люди — 1:1).

    python -X utf8 tools/sanatorium_main_corps_plan.py
        → docs/plans/sanatorium_main_corps_{1f,2f,3f,roof}_v01.png, docs/design/data/sanatorium_main_corps_v01.json
"""
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'docs/plans'
DATA = ROOT / 'docs/design/data/sanatorium_main_corps_v01.json'

FLOOR_TO_FLOOR = {1: 4.2, 2: 3.8, 3: 3.8}      # 1 этаж общественный — выше; 2–3 — потолок 3,4 м (2,95 × 1,15)
DOOR = 1.17          # проём 0,9 × 1,3
DOOR2 = 2.4          # двустворчатая / широкий проём
OPEN = 6.0           # открытый проём между общими зонами

# --------------------------------------------------------------------------- помещения
# (id, название, x0, y0, x1, y1, вид, признаки) ; вид: pub, med, admin, serv, wc, stair, lift, corr, void, tech, store
# признаки: loot — лут по смыслу места, lock — закрыто на ключ, dbl — второй свет (пол есть только на 1 этаже)
ST_M = ('ST-M', 'Парадная лестница', -44, 10, -35, 22, 'stair', '')
LF_M = ('LF-M', 'Лифты, 2 кабины', -35, 16, -29, 22, 'lift', '')
ST_N = ('ST-N', 'Служебная лестница и грузовой лифт', -32, 56, -26, 64, 'stair', '')
ST_S = ('ST-S', 'Служебная лестница', -20, -55.1, -12, -47, 'stair', '')
CORE = [ST_M, LF_M, ST_N, ST_S]
PATIO = (-38.0, -52.0, -26.0, -34.0)          # открытый дворик лечебного крыла, все этажи
VOID = (-41.0, -7.0, -25.0, 7.0)              # проём атриума на 2–3 этаже


def ring(f):
    """Кольцевой коридор вокруг дворика южного крыла: четыре отрезка."""
    return [(f'S{f}-cW', 'Коридор', -41.1, -55.1, -38, -30.9, 'corr', ''),
            (f'S{f}-cE', 'Коридор', -26, -55.1, -22.9, -30.9, 'corr', ''),
            (f'S{f}-cN', 'Коридор', -38, -34, -26, -30.9, 'corr', ''),
            (f'S{f}-cS', 'Коридор', -38, -55.1, -26, -52, 'corr', '')]


def central_core(f):
    return [(f'C{f}-ll', 'Лифтовый холл', -35, 10, -22, 16, 'pub', ''),
            (f'C{f}-st', 'Кладовая уборки', -29, 16, -22, 22, 'store', '')]


ROOMS = {
    1: CORE + central_core(1) + ring(1) + [
        ('C1-vest', 'Вестибюль', -22, -8, -10, 8, 'pub', ''),
        ('C1-rec', 'Приёмная, стойка, багажная', -22, 8, -10, 22, 'pub', 'loot'),
        ('C1-wc', 'Санузлы М / Ж', -22, -22, -10, -8, 'wc', ''),
        ('C1-atr', 'Атриум (3 света)', -44, -10, -22, 10, 'pub', ''),
        ('C1-lng', 'Лобби-гостиная', -44, -22, -22, -10, 'pub', ''),
        ('C1-gal', 'Галерея к террасе', -56, -22, -44, 22, 'pub', ''),
        ('N1-foy', 'Фойе столовой', -52, 22, -32, 28, 'pub', ''),
        ('N1-sc', 'Служебный коридор', -32, 22, -12, 28, 'corr', ''),
        ('N1-din', 'Столовая (2 света)', -52, 28, -32, 56, 'pub', ''),
        ('N1-bnq', 'Банкетный зал', -52, 56, -32, 64, 'pub', ''),
        ('N1-srv', 'Раздача', -32, 28, -26, 56, 'serv', ''),
        ('N1-wsh', 'Моечная', -26, 28, -18, 38, 'serv', ''),
        ('N1-stf', 'Бытовые кухни', -18, 28, -12, 38, 'serv', 'loot'),
        ('N1-hot', 'Горячий цех', -26, 38, -12, 50, 'serv', ''),
        ('N1-prp', 'Заготовочная', -26, 50, -12, 57, 'serv', ''),
        ('N1-dry', 'Сухой склад', -26, 57, -19, 64, 'store', 'loot'),
        ('N1-cld', 'Холодильная камера', -19, 57, -12, 64, 'store', 'loot'),
        ('N1-dck', 'Приёмка (рампа)', -12, 46, 4, 60, 'serv', ''),
        ('N1-grd', 'Пост охраны', -12, 40, 4, 46, 'serv', 'loot'),
        ('S1-hal', 'Холл спа и медпункта', -41.1, -30.9, -22.9, -22, 'pub', ''),
        ('S1-phm', 'Аптека', -52, -30.9, -41.1, -22, 'med', 'loot'),
        ('S1-med', 'Дежурный медпункт', -22.9, -30.9, -12, -22, 'med', 'loot'),
        ('S1-chM', 'Раздевалка М', -52, -43, -41.1, -30.9, 'wc', ''),
        ('S1-chF', 'Раздевалка Ж', -52, -55.1, -41.1, -43, 'wc', ''),
        ('S1-sau', 'Сауна, хаммам, души', -52, -64, -38, -55.1, 'wc', ''),
        ('S1-tch', 'Техника бассейна', -38, -64, -22.9, -55.1, 'tech', 'loot'),
        ('S1-ssc', 'Проход', -22.9, -55.1, -20, -47, 'corr', ''),
        ('S1-stf', 'Персонал спа', -22.9, -64, -12, -55.1, 'serv', 'loot'),
        ('S1-lin', 'Бельевая спа', -22.9, -47, -12, -30.9, 'store', 'loot'),
        ('S1-pool', 'Крытый бассейн 25 м', -88, -58, -52, -24, 'pub', ''),
    ],
    2: CORE + central_core(2) + ring(2) + [
        ('C2-gal', 'Галерея атриума', -44, -10, -22, 10, 'pub', ''),
        ('C2-wst', 'Зал отдыха с видом на озеро', -56, -22, -44, 22, 'pub', ''),
        ('C2-con1', 'Кабинет консультаций', -22, 8, -10, 22, 'med', ''),
        ('C2-wai', 'Ожидание', -22, -8, -10, 8, 'pub', ''),
        ('C2-wc', 'Санузлы М / Ж', -22, -22, -10, -8, 'wc', ''),
        ('C2-con2', 'Кабинет консультаций', -44, -22, -36, -10, 'med', ''),
        ('C2-sc', 'Переход в лечебное крыло', -36, -22, -30, -10, 'corr', ''),
        ('C2-con3', 'Кабинет консультаций', -30, -22, -22, -10, 'med', ''),
        ('N2-gal', 'Галерея над фойе', -52, 22, -32, 28, 'pub', ''),
        ('N2-cor', 'Коридор', -32, 22, -12, 28, 'corr', ''),
        ('N2-dinv', 'Второй свет столовой', -52, 28, -32, 56, 'void', 'dbl'),
        ('N2-yog', 'Малый зал (йога)', -52, 56, -32, 64, 'pub', ''),
        ('N2-lfk', 'Зал ЛФК', -32, 28, -12, 48, 'med', ''),
        ('N2-lch', 'Раздевалка ЛФК', -32, 48, -26, 56, 'wc', ''),
        ('N2-inv', 'Инвентарная', -26, 48, -12, 56, 'store', 'loot'),
        ('N2-lin', 'Чистая бельевая', -26, 56, -19, 64, 'store', 'loot'),
        ('N2-tch', 'Венткамера', -19, 56, -12, 64, 'tech', ''),
        ('S2-wai', 'Ожидание у кабинетов', -41.1, -30.9, -22.9, -22, 'pub', ''),
        ('S2-dc1', 'Кабинет терапевта', -52, -30.9, -41.1, -22, 'med', 'loot'),
        ('S2-dc2', 'Кабинет кардиолога', -22.9, -30.9, -12, -22, 'med', 'loot'),
        ('S2-dia', 'Диагностика', -52, -43, -41.1, -30.9, 'med', 'loot'),
        ('S2-phy', 'Физиотерапия', -52, -55.1, -41.1, -43, 'med', ''),
        ('S2-mas', 'Массажные кабинеты', -52, -64, -38, -55.1, 'med', ''),
        ('S2-prc', 'Процедурная', -38, -64, -22.9, -55.1, 'med', 'loot'),
        ('S2-ssc', 'Проход', -22.9, -55.1, -20, -47, 'corr', ''),
        ('S2-x', 'Грязное бельё', -22.9, -64, -12, -55.1, 'store', ''),
        ('S2-mst', 'Медицинский склад', -22.9, -47, -12, -39, 'store', 'loot lock'),
        ('S2-stf', 'Бытовые медперсонала', -22.9, -39, -12, -30.9, 'serv', 'loot'),
    ],
    3: CORE + central_core(3) + ring(3) + [
        ('C3-gal', 'Галерея атриума', -44, -10, -22, 10, 'pub', ''),
        ('C3-lib', 'Библиотека и читальный зал', -56, -22, -44, 22, 'pub', 'loot'),
        ('C3-qui', 'Тихая гостиная', -22, -8, -10, 22, 'pub', ''),
        ('C3-wc', 'Санузлы М / Ж', -22, -22, -10, -8, 'wc', ''),
        ('C3-bks', 'Книгохранилище', -44, -22, -36, -10, 'store', ''),
        ('C3-sc', 'Переход в административное крыло', -36, -22, -30, -10, 'corr', ''),
        ('C3-clb', 'Клубная комната', -30, -22, -22, -10, 'pub', 'loot'),
        ('N3-foy', 'Фойе зала', -52, 22, -32, 28, 'pub', ''),
        ('N3-cor', 'Коридор', -32, 22, -12, 28, 'corr', ''),
        ('N3-hal', 'Зал собраний и кино', -52, 28, -32, 56, 'pub', ''),
        ('N3-prj', 'Проекционная, кладовая зала', -52, 56, -32, 64, 'store', 'loot'),
        ('N3-bil', 'Бильярдная', -32, 28, -18, 40, 'pub', ''),
        ('N3-gam', 'Настольные игры', -18, 28, -12, 40, 'pub', ''),
        ('N3-clb', 'Комната отдыха', -32, 40, -12, 56, 'pub', 'loot'),
        ('N3-sto', 'Хозяйственная кладовая', -26, 56, -12, 64, 'store', 'loot'),
        ('S3-rec', 'Приёмная администрации', -41.1, -30.9, -22.9, -22, 'admin', ''),
        ('S3-acc', 'Бухгалтерия', -52, -30.9, -41.1, -22, 'admin', 'loot'),
        ('S3-dir', 'Кабинет главврача', -22.9, -30.9, -12, -22, 'admin', 'loot lock'),
        ('S3-ad1', 'Администрация', -52, -43, -41.1, -30.9, 'admin', 'loot'),
        ('S3-arc', 'Архив', -52, -55.1, -41.1, -43, 'store', 'loot lock'),
        ('S3-met', 'Переговорная', -52, -64, -38, -55.1, 'admin', ''),
        ('S3-csh', 'Касса с сейфом', -38, -64, -22.9, -55.1, 'admin', 'loot lock'),
        ('S3-ssc', 'Проход', -22.9, -55.1, -20, -47, 'corr', ''),
        ('S3-srv', 'Серверная', -22.9, -64, -12, -55.1, 'tech', 'loot'),
        ('S3-key', 'Хозчасть, ключница', -22.9, -47, -12, -39, 'admin', 'loot'),
        ('S3-ad2', 'Отдел кадров', -22.9, -39, -12, -30.9, 'admin', 'loot'),
    ],
}

# --------------------------------------------------------------------------- двери
# (a, b, t, ширина): b — помещение или 'out'; t — доля вдоль общей стены (для 'out' — сторона 'E'/'W'/'N'/'S' и доля)
DOORS = {
    1: [
        ('C1-vest', 'out', ('E', 0.5), 3.0), ('C1-vest', 'C1-atr', 0.5, OPEN), ('C1-vest', 'C1-rec', 0.5, DOOR2),
        ('C1-vest', 'C1-wc', 0.5, DOOR), ('C1-atr', 'C1-lng', 0.5, 10.0), ('C1-atr', 'C1-gal', 0.5, OPEN),
        ('C1-atr', 'C1-ll', 0.5, 8.0), ('C1-atr', 'ST-M', 0.5, 7.0), ('C1-ll', 'LF-M', 0.5, 4.0), ('C1-ll', 'C1-st', 0.5, DOOR),
        ('ST-M', 'C1-gal', 0.5, DOOR2), ('C1-lng', 'C1-gal', 0.5, OPEN), ('C1-lng', 'S1-hal', 0.5, OPEN),
        ('C1-gal', 'out', ('W', 0.5), 3.0), ('C1-gal', 'out', ('W', 0.15), DOOR2), ('C1-gal', 'out', ('W', 0.85), DOOR2),
        ('C1-gal', 'N1-foy', 0.5, OPEN), ('C1-rec', 'N1-sc', 0.5, DOOR),
        ('N1-foy', 'N1-din', 0.25, DOOR2), ('N1-foy', 'N1-din', 0.75, DOOR2), ('N1-foy', 'N1-sc', 0.5, DOOR),
        ('N1-din', 'N1-bnq', 0.5, DOOR2), ('N1-din', 'N1-srv', 0.5, DOOR2), ('N1-din', 'out', ('W', 0.5), DOOR2),
        ('N1-bnq', 'ST-N', 0.5, DOOR), ('N1-bnq', 'out', ('N', 0.5), DOOR2),
        ('N1-srv', 'N1-hot', 0.4, DOOR), ('N1-srv', 'N1-wsh', 0.5, DOOR), ('N1-srv', 'ST-N', 0.5, DOOR),
        ('N1-wsh', 'N1-sc', 0.5, DOOR), ('N1-stf', 'N1-sc', 0.5, DOOR), ('N1-hot', 'N1-wsh', 0.5, DOOR),
        ('N1-hot', 'N1-prp', 0.5, DOOR2), ('N1-prp', 'N1-dry', 0.5, DOOR), ('N1-prp', 'N1-cld', 0.5, DOOR),
        ('N1-prp', 'N1-dck', 0.5, DOOR2), ('N1-cld', 'N1-dck', 0.5, DOOR), ('N1-grd', 'N1-dck', 0.5, DOOR),
        ('N1-grd', 'out', ('E', 0.5), DOOR), ('N1-dck', 'out', ('E', 0.5), 3.5),
        ('S1-hal', 'S1-cN', 0.5, OPEN), ('S1-hal', 'S1-phm', 0.5, DOOR), ('S1-hal', 'S1-med', 0.5, DOOR),
        ('S1-med', 'out', ('E', 0.5), DOOR2),
        ('S1-cN', 'S1-cW', 0.5, 3.1), ('S1-cN', 'S1-cE', 0.5, 3.1), ('S1-cW', 'S1-cS', 0.5, 3.1), ('S1-cE', 'S1-cS', 0.5, 3.1),
        ('S1-cW', 'S1-chM', 0.5, DOOR), ('S1-cW', 'S1-chF', 0.5, DOOR), ('S1-chM', 'S1-pool', 0.5, DOOR),
        ('S1-chF', 'S1-pool', 0.5, DOOR), ('S1-chF', 'S1-sau', 0.5, DOOR), ('S1-sau', 'S1-pool', 0.5, DOOR),
        ('S1-cW', 'S1-sau', 0.5, DOOR), ('S1-cS', 'S1-tch', 0.5, DOOR), ('S1-tch', 'S1-stf', 0.5, DOOR),
        ('S1-cE', 'S1-ssc', 0.5, 3.1), ('S1-ssc', 'ST-S', 0.5, DOOR2), ('S1-stf', 'ST-S', 0.5, DOOR),
        ('ST-S', 'out', ('E', 0.5), DOOR), ('S1-cE', 'S1-lin', 0.5, DOOR),
        ('S1-pool', 'out', ('W', 0.35), 3.0), ('S1-pool', 'out', ('W', 0.75), 3.0),
    ],
    2: [
        ('C2-gal', 'ST-M', 0.5, 7.0), ('C2-gal', 'C2-ll', 0.5, 8.0), ('C2-ll', 'LF-M', 0.5, 4.0), ('C2-ll', 'C2-st', 0.5, DOOR),
        ('C2-gal', 'C2-wst', 0.5, OPEN), ('ST-M', 'C2-wst', 0.5, DOOR2), ('C2-gal', 'C2-wai', 0.5, OPEN),
        ('C2-wai', 'C2-con1', 0.5, DOOR), ('C2-wai', 'C2-wc', 0.5, DOOR), ('C2-gal', 'C2-sc', 0.5, 4.0),
        ('C2-sc', 'C2-con2', 0.5, DOOR), ('C2-sc', 'C2-con3', 0.5, DOOR), ('C2-sc', 'S2-wai', 0.5, 4.0),
        ('C2-wst', 'N2-gal', 0.5, OPEN), ('N2-gal', 'N2-cor', 0.5, 3.1), ('N2-cor', 'N2-lfk', 0.5, DOOR2),
        ('N2-lfk', 'N2-lch', 0.5, DOOR), ('N2-lfk', 'N2-inv', 0.5, DOOR2), ('N2-lch', 'ST-N', 0.5, DOOR),
        ('N2-inv', 'N2-lin', 0.5, DOOR), ('N2-inv', 'N2-tch', 0.5, DOOR), ('N2-yog', 'ST-N', 0.5, DOOR),
        ('S2-wai', 'S2-cN', 0.5, OPEN), ('S2-wai', 'S2-dc1', 0.5, DOOR), ('S2-wai', 'S2-dc2', 0.5, DOOR),
        ('S2-cN', 'S2-cW', 0.5, 3.1), ('S2-cN', 'S2-cE', 0.5, 3.1), ('S2-cW', 'S2-cS', 0.5, 3.1), ('S2-cE', 'S2-cS', 0.5, 3.1),
        ('S2-cW', 'S2-dia', 0.5, DOOR), ('S2-cW', 'S2-phy', 0.5, DOOR), ('S2-cW', 'S2-mas', 0.5, DOOR),
        ('S2-cS', 'S2-prc', 0.5, DOOR), ('S2-prc', 'S2-x', 0.5, DOOR), ('S2-cE', 'S2-ssc', 0.5, 3.1),
        ('S2-ssc', 'ST-S', 0.5, DOOR2), ('S2-x', 'ST-S', 0.5, DOOR), ('S2-cE', 'S2-mst', 0.5, DOOR),
        ('S2-cE', 'S2-stf', 0.5, DOOR),
    ],
    3: [
        ('C3-gal', 'ST-M', 0.5, 7.0), ('C3-gal', 'C3-ll', 0.5, 8.0), ('C3-ll', 'LF-M', 0.5, 4.0), ('C3-ll', 'C3-st', 0.5, DOOR),
        ('C3-gal', 'C3-lib', 0.5, OPEN), ('ST-M', 'C3-lib', 0.5, DOOR2), ('C3-gal', 'C3-qui', 0.5, OPEN),
        ('C3-qui', 'C3-wc', 0.5, DOOR), ('C3-gal', 'C3-sc', 0.5, 4.0), ('C3-sc', 'C3-bks', 0.5, DOOR),
        ('C3-sc', 'C3-clb', 0.5, DOOR), ('C3-sc', 'S3-rec', 0.5, 4.0), ('C3-bks', 'C3-lib', 0.5, DOOR),
        ('C3-lib', 'N3-foy', 0.5, OPEN), ('N3-foy', 'N3-cor', 0.5, 3.1), ('N3-foy', 'N3-hal', 0.25, DOOR2),
        ('N3-foy', 'N3-hal', 0.75, DOOR2), ('N3-hal', 'N3-prj', 0.5, DOOR), ('N3-prj', 'ST-N', 0.5, DOOR),
        ('N3-cor', 'N3-bil', 0.5, DOOR2), ('N3-cor', 'N3-gam', 0.5, DOOR), ('N3-bil', 'N3-clb', 0.5, DOOR2),
        ('N3-clb', 'ST-N', 0.5, DOOR), ('N3-clb', 'N3-sto', 0.5, DOOR),
        ('S3-rec', 'S3-cN', 0.5, OPEN), ('S3-rec', 'S3-acc', 0.5, DOOR), ('S3-rec', 'S3-dir', 0.5, DOOR),
        ('S3-cN', 'S3-cW', 0.5, 3.1), ('S3-cN', 'S3-cE', 0.5, 3.1), ('S3-cW', 'S3-cS', 0.5, 3.1), ('S3-cE', 'S3-cS', 0.5, 3.1),
        ('S3-cW', 'S3-ad1', 0.5, DOOR), ('S3-cW', 'S3-arc', 0.5, DOOR), ('S3-cW', 'S3-met', 0.5, DOOR),
        ('S3-cS', 'S3-csh', 0.5, DOOR), ('S3-csh', 'S3-srv', 0.5, DOOR), ('S3-cE', 'S3-ssc', 0.5, 3.1),
        ('S3-ssc', 'ST-S', 0.5, DOOR2), ('S3-srv', 'ST-S', 0.5, DOOR), ('S3-cE', 'S3-key', 0.5, DOOR),
        ('S3-cE', 'S3-ad2', 0.5, DOOR),
    ],
}
VERTICAL = ['ST-M', 'LF-M', 'ST-N', 'ST-S']          # одна над другой на всех этажах
LOCKED_DOORS = {('S2-cE', 'S2-mst'), ('S3-rec', 'S3-dir'), ('S3-cW', 'S3-arc'), ('S3-cS', 'S3-csh'), ('S3-csh', 'S3-srv')}

# --------------------------------------------------------------------------- геометрия и проверки
EPS = 0.05


def rect_of(r):
    return r[2], r[3], r[4], r[5]


def shared_edge(a, b):
    """Общий отрезок стены двух прямоугольников: ('v', x, y0, y1) или ('h', y, x0, x1); None — не соседи."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    for xa, xb in ((ax1, bx0), (ax0, bx1)):
        if abs(xa - xb) < EPS:
            lo, hi = max(ay0, by0), min(ay1, by1)
            if hi - lo > EPS:
                return ('v', xa, lo, hi)
    for ya, yb in ((ay1, by0), (ay0, by1)):
        if abs(ya - yb) < EPS:
            lo, hi = max(ax0, bx0), min(ax1, bx1)
            if hi - lo > EPS:
                return ('h', ya, lo, hi)
    return None


def door_geom(rooms, d):
    a, b, t, w = d
    ra = rect_of(rooms[a])
    if b == 'out':
        side, frac = t
        x0, y0, x1, y1 = ra
        if side in ('E', 'W'):
            x = x1 if side == 'E' else x0
            return ('v', x, y0 + (y1 - y0) * frac - w / 2, y0 + (y1 - y0) * frac + w / 2)
        y = y1 if side == 'N' else y0
        return ('h', y, x0 + (x1 - x0) * frac - w / 2, x0 + (x1 - x0) * frac + w / 2)
    e = shared_edge(ra, rect_of(rooms[b]))
    if e is None:
        raise SystemExit(f'дверь {a} — {b}: помещения не соседи')
    kind, c, lo, hi = e
    w = min(w, hi - lo - 0.3)
    mid = lo + (hi - lo) * t
    mid = min(max(mid, lo + w / 2 + 0.15), hi - w / 2 - 0.15)
    return (kind, c, mid - w / 2, mid + w / 2)


def overlaps(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > EPS and min(a[3], b[3]) - max(a[1], b[1]) > EPS


def area(r):
    x0, y0, x1, y1 = rect_of(r)
    a = (x1 - x0) * (y1 - y0)
    if r[0].endswith('-gal') and r[0][0] == 'C' and r[0][1] in '23':
        a -= (VOID[2] - VOID[0]) * (VOID[3] - VOID[1])
    return a


def check():
    problems = []
    rooms_by_floor = {f: {r[0]: r for r in ROOMS[f]} for f in ROOMS}
    for f, rs in ROOMS.items():
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if overlaps(rect_of(a), rect_of(b)):
                    problems.append(f'{f} эт.: {a[0]} и {b[0]} пересекаются')
            if overlaps(rect_of(a), PATIO):
                problems.append(f'{f} эт.: {a[0]} заходит во дворик')
        for d in DOORS[f]:
            for rid in (d[0], d[1]):
                if rid != 'out' and rid not in rooms_by_floor[f]:
                    problems.append(f'{f} эт.: дверь в несуществующее {rid}')
            door_geom(rooms_by_floor[f], d)
    for v in VERTICAL:
        rects = {rect_of(rooms_by_floor[f][v]) for f in ROOMS}
        if len(rects) != 1:
            problems.append(f'{v}: не одна над другой')
    # достижимость: от наружных дверей 1 этажа по дверям и вертикальным связям; запертые двери считаем открытыми
    # отдельно проверяем, что без запертых дверей доступно всё, кроме самих закрытых помещений
    def reach(skip_locked):
        adj = {}
        for f in ROOMS:
            for a, b, t, w in DOORS[f]:
                if b == 'out' or (skip_locked and ((a, b) in LOCKED_DOORS or (b, a) in LOCKED_DOORS)):
                    continue
                adj.setdefault((f, a), set()).add((f, b))
                adj.setdefault((f, b), set()).add((f, a))
        for v in VERTICAL:
            for f in (1, 2):
                adj.setdefault((f, v), set()).add((f + 1, v))
                adj.setdefault((f + 1, v), set()).add((f, v))
        start = {(1, a) for a, b, t, w in DOORS[1] if b == 'out'}
        seen, q = set(start), deque(start)
        while q:
            n = q.popleft()
            for m in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    q.append(m)
        return seen
    allr = {(f, r[0]) for f in ROOMS for r in ROOMS[f] if r[6] != 'void'}
    open_all = reach(False)
    for n in sorted(allr - open_all):
        problems.append(f'не дойти: {n[0]} эт. {n[1]}')
    locked_rooms = {(f, r[0]) for f in ROOMS for r in ROOMS[f] if 'lock' in r[7]}
    no_keys = reach(True)
    for n in sorted(allr - no_keys - locked_rooms):
        problems.append(f'без ключей не дойти: {n[0]} эт. {n[1]}')
    # у каждого этажа минимум два независимых пути на соседний: две лестницы, связанные этажом
    return problems, rooms_by_floor


PROBLEMS, BY_FLOOR = check()

# --------------------------------------------------------------------------- рисование
PAPER = (247, 245, 239)
INK = (40, 42, 46)
MUTED = (110, 112, 118)
FILL = {'pub': (246, 232, 206), 'med': (214, 234, 222), 'admin': (222, 222, 240), 'serv': (234, 226, 214),
        'wc': (214, 228, 238), 'stair': (200, 200, 196), 'lift': (184, 184, 180), 'corr': (240, 238, 232),
        'void': (232, 232, 232), 'tech': (210, 206, 200), 'store': (226, 220, 206)}
LOOT_C = (214, 140, 30)
LOCK_C = (200, 40, 40)
GLASS = (110, 160, 205)
XMIN, XMAX, YMIN, YMAX = -112.0, 8.0, -70.0, 70.0
SC = 6.2
PADX, PADY = 30, 90


def font(size, bold=False):
    return ImageFont.truetype(f'C:/Windows/Fonts/{"arialbd" if bold else "arial"}.ttf', size)


def make_canvas(w_extra=760, h=None):
    W = int((XMAX - XMIN) * SC) + PADX * 2 + w_extra
    H = h or int((YMAX - YMIN) * SC) + PADY + 70
    img = Image.new('RGB', (W, H), PAPER)
    return img, ImageDraw.Draw(img)


def P(x, y):
    return (PADX + (x - XMIN) * SC, PADY + (YMAX - y) * SC)


def inside_any(x, y, rects):
    return any(r[0] < x < r[2] and r[1] < y < r[3] for r in rects)


def site_context(d):
    """Окружение корпуса: терраса, подиум с открытым бассейном, площадь с кругом, рампа — для ориентира."""
    def rect(x0, y0, x1, y1, fill, outline=None):
        d.rectangle([*P(x0, y1), *P(x1, y0)], fill=fill, outline=outline)
    rect(XMIN, YMIN, XMAX, YMAX, (226, 230, 214))
    rect(-112, YMIN, -100, YMAX, (176, 190, 150))                      # бровка и склон
    d.text(P(-110, 66), 'склон к озеру ←', font=font(12), fill=MUTED)
    rect(-86, -16, -56, 16, (232, 228, 214), MUTED)                    # парадная терраса
    d.text(P(-71, -13), 'терраса', font=font(12), fill=MUTED, anchor='mm')
    d.ellipse([*P(-77, 5), *P(-67, -5)], fill=(150, 196, 220), outline=MUTED)
    d.polygon([P(-88, -60), P(-104, -60), P(-108, -22), P(-88, -22)], fill=(232, 228, 214), outline=MUTED)
    rect(-104, -50, -92, -30, (120, 196, 220), MUTED)                  # открытая чаша
    d.text(P(-98, -54), 'открытый\nбассейн', font=font(11), fill=MUTED, anchor='mm', align='center')
    d.ellipse([*P(-2, 12), *P(22, -12)], fill=(190, 190, 186))         # круг у входа
    d.ellipse([*P(4.5, 5.5), *P(15.5, -5.5)], fill=(150, 196, 220))
    rect(-10, -3.5, 8, 3.5, (190, 190, 186))
    rect(-80, 28, -52, 56, (232, 228, 214), MUTED)                     # веранда столовой
    d.text(P(-66, 42), 'веранда\nстоловой', font=font(11), fill=MUTED, anchor='mm', align='center')
    d.text(P(2, 66), 'С ↑', font=font(14, True), fill=INK)


def draw_floor(f, d, number):
    rooms = ROOMS[f]
    rects = [rect_of(r) for r in rooms]
    site_context(d)
    if f == 1:
        pass
    for r in rooms:
        x0, y0, x1, y1 = rect_of(r)
        d.rectangle([*P(x0, y1), *P(x1, y0)], fill=FILL[r[6]], outline=INK, width=1)
        if r[6] == 'void':
            for k in range(int((x1 - x0 + y1 - y0) / 2.5)):
                a = (x0 + k * 2.5, y0)
                b = (x0, y0 + k * 2.5)
                d.line([P(*a), P(*b)], fill=(200, 200, 200))
    # дворик и проём атриума
    d.rectangle([*P(PATIO[0], PATIO[3]), *P(PATIO[2], PATIO[1])], fill=(206, 222, 190), outline=INK, width=2)
    d.text(P((PATIO[0] + PATIO[2]) / 2, (PATIO[1] + PATIO[3]) / 2), 'дворик', font=font(12), fill=MUTED, anchor='mm')
    if f > 1:
        d.rectangle([*P(VOID[0], VOID[3]), *P(VOID[2], VOID[1])], fill=(236, 236, 236), outline=INK, width=2)
        d.text(P(-33, 0), 'проём атриума', font=font(12), fill=MUTED, anchor='mm')
    else:
        d.rectangle([*P(VOID[0], VOID[3]), *P(VOID[2], VOID[1])], outline=MUTED, width=1)
        d.text(P(-33, 3), 'атриум', font=font(12), fill=MUTED, anchor='mm')
        d.text(P(-33, -1), 'световой фонарь над', font=font(10), fill=MUTED, anchor='mm')
    # окна по наружным стенам (в т. ч. во дворик), кроме лестниц, техники, кладовых и санузлов
    for r in rooms:
        if r[6] in ('stair', 'lift', 'tech', 'store', 'wc', 'void', 'corr'):
            continue
        x0, y0, x1, y1 = rect_of(r)
        edges = [((x0, y0), (x1, y0), (0, -1)), ((x1, y0), (x1, y1), (1, 0)), ((x1, y1), (x0, y1), (0, 1)),
                 ((x0, y1), (x0, y0), (-1, 0))]
        for (ax, ay), (bx, by), (nx, ny) in edges:
            L = math.hypot(bx - ax, by - ay)
            n = int(L / 3.0)
            for k in range(n):
                t0, t1 = (k + 0.25) / n, (k + 0.75) / n
                mx, my = ax + (bx - ax) * (t0 + t1) / 2, ay + (by - ay) * (t0 + t1) / 2
                ox, oy = mx + nx * 0.4, my + ny * 0.4
                if inside_any(ox, oy, rects) and not (f > 1 and VOID[0] < ox < VOID[2] and VOID[1] < oy < VOID[3]):
                    continue
                if f > 1 and VOID[0] < ox < VOID[2] and VOID[1] < oy < VOID[3]:
                    continue
                d.line([P(ax + (bx - ax) * t0, ay + (by - ay) * t0), P(ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=GLASS, width=4)
    # двери: разрыв стены и метка
    for dd in DOORS[f]:
        kind, c, lo, hi = door_geom(BY_FLOOR[f], dd)
        locked = (dd[0], dd[1]) in LOCKED_DOORS
        col = LOCK_C if locked else (250, 250, 250)
        if kind == 'v':
            d.rectangle([*P(c - 0.35, hi), *P(c + 0.35, lo)], fill=col)
        else:
            d.rectangle([*P(lo, c + 0.35), *P(hi, c - 0.35)], fill=col)
        if dd[1] == 'out':
            cx, cy = (c, (lo + hi) / 2) if kind == 'v' else ((lo + hi) / 2, c)
            side = dd[2][0]
            dx, dy = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[side]
            tip = P(cx + dx * 2.6, cy + dy * 2.6)
            base1 = P(cx + dx * 0.8 - dy * 1.0, cy + dy * 0.8 + dx * 1.0)
            base2 = P(cx + dx * 0.8 + dy * 1.0, cy + dy * 0.8 - dx * 1.0)
            d.polygon([tip, base1, base2], fill=(40, 150, 70))
    # лестницы и лифты
    for r in rooms:
        x0, y0, x1, y1 = rect_of(r)
        if r[6] == 'stair':
            n = int((y1 - y0) / 0.6)
            for k in range(1, n):
                yy = y0 + k * (y1 - y0) / n
                d.line([P(x0 + 0.4, yy), P((x0 + x1) / 2 - 0.2, yy)], fill=MUTED)
                d.line([P((x0 + x1) / 2 + 0.2, yy), P(x1 - 0.4, yy)], fill=MUTED)
        if r[6] == 'lift':
            for k in range(2):
                ax = x0 + k * (x1 - x0) / 2
                d.rectangle([*P(ax + 0.3, y1 - 0.4), *P(ax + (x1 - x0) / 2 - 0.3, y0 + 0.6)], outline=INK)
                d.line([P(ax + 0.3, y1 - 0.4), P(ax + (x1 - x0) / 2 - 0.3, y0 + 0.6)], fill=INK)
                d.line([P(ax + 0.3, y0 + 0.6), P(ax + (x1 - x0) / 2 - 0.3, y1 - 0.4)], fill=INK)
    furniture(f, d)
    # номера помещений, лут и закрытые
    for r in rooms:
        if r[6] == 'void':
            continue
        x0, y0, x1, y1 = rect_of(r)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if r[0] in ('C2-gal', 'C3-gal'):
            cx, cy = -33, 8.5
        if r[0] == 'C1-atr':
            cx, cy = -33, -8.5
        label = number[r[0]]
        d.text(P(cx, cy), label, font=font(12, True), fill=INK, anchor='mm')
        if 'loot' in r[7]:
            px, py = P(cx, cy)
            d.ellipse([px + 14, py - 12, px + 22, py - 4], fill=LOOT_C)
        if 'lock' in r[7]:
            d.rectangle([*P(x0, y1), *P(x1, y0)], outline=LOCK_C, width=3)


def furniture(f, d):
    """Опорная мебель и оборудование — масштаб читается: столы, чаши, стеллажи, ряды кресел."""
    def rr(x0, y0, x1, y1, fill=(255, 255, 255), outline=MUTED):
        d.rectangle([*P(x0, y1), *P(x1, y0)], fill=fill, outline=outline)
    if f == 1:
        rr(-82.5, -47.5, -57.5, -35, (120, 196, 220), INK)        # чаша 25 × 12,5
        for k in range(1, 5):
            d.line([P(-82.5, -47.5 + k * 2.5), P(-57.5, -47.5 + k * 2.5)], fill=(90, 160, 190))
        for ix in range(4):                                      # столовая: столы на 4–6
            for iy in range(7):
                rr(-49.5 + ix * 4.4, 31 + iy * 3.6, -47.3 + ix * 4.4, 32.6 + iy * 3.6)
        for iy in range(3):
            rr(-48 + iy * 6, 58.5, -43.5 + iy * 6, 61)           # банкет
        rr(-21.5, 12, -20.5, 20, (210, 200, 180))                # стойка приёмной
        rr(-25.5, 41, -24.5, 49, (200, 200, 205))                # плиты горячего цеха
        rr(-15, 41, -13, 49, (200, 200, 205))
        rr(-31.5, 31, -30.5, 53, (210, 200, 180))                # линия раздачи
        for k in range(3):
            rr(-42 + k * 6, -19, -38 + k * 6, -15)               # кресла лобби
        rr(-10.5, 49, -0.5, 57, (230, 230, 230))                 # площадка приёмки
    if f == 2:
        for k in range(4):
            rr(-30 + k * 4.5, 32, -27 + k * 4.5, 44)             # маты ЛФК
        for k in range(3):
            rr(-50 + k * 4, -62, -48 + k * 4, -57.5)             # кушетки
    if f == 3:
        for k in range(8):                                       # ряды кресел зала
            d.line([P(-50, 33 + k * 2.2), P(-34, 33 + k * 2.2)], fill=MUTED, width=2)
        rr(-49, 52.5, -35, 55, (60, 60, 64))                     # экран
        rr(-27.5, 32, -22.5, 34.5, (70, 130, 80))                # бильярдный стол
        for k in range(8):                                       # стеллажи библиотеки
            rr(-55, -20 + k * 5, -50, -19.4 + k * 5)
        rr(-36.5, -62.5, -35, -61, (80, 80, 84))                 # сейф


def draw_schedule(d, f, number, x, y):
    d.text((x, y), f'Помещения {f} этажа', font=font(16, True), fill=INK)
    y += 26
    total = 0.0
    for r in ROOMS[f]:
        if r[6] == 'void':
            continue
        a = area(r)
        total += a
        flags = []
        if 'loot' in r[7]:
            flags.append('лут')
        if 'lock' in r[7]:
            flags.append('ключ')
        name = r[1] + (f'  [{", ".join(flags)}]' if flags else '')
        d.text((x, y), f'{number[r[0]]}', font=font(12, True), fill=INK)
        d.text((x + 44, y), name, font=font(12), fill=LOCK_C if 'lock' in r[7] else INK)
        d.text((x + 560, y), f'{a:.0f} м²', font=font(12), fill=MUTED)
        y += 16
    d.text((x, y + 4), f'Итого по полу ≈ {total:.0f} м²', font=font(12, True), fill=INK)
    return y + 26


def legend(d, x, y):
    items = [(FILL['pub'], 'общие зоны'), (FILL['med'], 'лечебные'), (FILL['admin'], 'администрация'),
             (FILL['serv'], 'хозяйственные, кухня'), (FILL['wc'], 'санузлы, раздевалки'), (FILL['stair'], 'лестницы, лифты'),
             (FILL['store'], 'кладовые, склады')]
    for c, s in items:
        d.rectangle([x, y + 2, x + 18, y + 16], fill=c, outline=INK)
        d.text((x + 26, y + 2), s, font=font(12), fill=INK)
        y += 20
    d.line([(x, y + 9), (x + 18, y + 9)], fill=GLASS, width=4)
    d.text((x + 26, y + 2), 'окна, витражи', font=font(12), fill=INK)
    y += 20
    d.polygon([(x + 2, y + 2), (x + 2, y + 16), (x + 16, y + 9)], fill=(40, 150, 70))
    d.text((x + 26, y + 2), 'наружный вход', font=font(12), fill=INK)
    y += 20
    d.ellipse([x + 4, y + 4, x + 14, y + 14], fill=LOOT_C)
    d.text((x + 26, y + 2), 'лут по смыслу места', font=font(12), fill=INK)
    y += 20
    d.rectangle([x, y + 2, x + 18, y + 16], outline=LOCK_C, width=3)
    d.text((x + 26, y + 2), 'закрыто на ключ (красная — запертая дверь)', font=font(12), fill=INK)
    return y + 24


TITLES = {1: '1 этаж — приём, питание, спа и медпункт', 2: '2 этаж — лечебный, ЛФК, отдых',
          3: '3 этаж — администрация, библиотека, зал, клуб'}
numbers = {}
for f in ROOMS:
    k = 0
    for r in ROOMS[f]:
        if r[6] == 'void':
            continue
        k += 1
        numbers.setdefault(f, {})[r[0]] = f'{f}.{k:02d}'

for f in ROOMS:
    img, d = make_canvas()
    d.text((PADX, 18), f'Санаторий · главный корпус v01 · {TITLES[f]}', font=font(22, True), fill=INK)
    d.text((PADX, 50), f'высота этажа {FLOOR_TO_FLOOR[f]:.1f} м'.replace('.', ',') +
           ' · координаты схемы участка, метры игры (правило E) · предложение агента на обсуждение',
           font=font(14), fill=MUTED)
    draw_floor(f, d, numbers[f])
    sx = PADX + int((XMAX - XMIN) * SC) + 30
    yy = draw_schedule(d, f, numbers[f], sx, PADY)
    legend(d, sx, yy + 6)
    # масштаб
    bx, by = P(-108, -66)
    d.line([(bx, by), (bx + 20 * SC, by)], fill=INK, width=3)
    d.text((bx + 10 * SC, by - 10), '20 м', font=font(12), fill=INK, anchor='mm')
    img.save(OUT_DIR / f'sanatorium_main_corps_{f}f_v01.png')

# --------------------------------------------------------------------------- кровля и разрез
img, d = make_canvas(w_extra=760)
d.text((PADX, 18), 'Санаторий · главный корпус v01 · кровля и разрез', font=font(22, True), fill=INK)
d.text((PADX, 50), 'солярий на кровле — предложение (выход парадной лестницей); техническая кровля — через служебную северную',
       font=font(14), fill=MUTED)
site_context(d)
for r in ROOMS[3]:
    x0, y0, x1, y1 = rect_of(r)
    d.rectangle([*P(x0, y1), *P(x1, y0)], fill=(196, 198, 200), outline=None)
d.rectangle([*P(-88, -24), *P(-52, -58)], fill=(212, 214, 216), outline=INK, width=2)   # кровля бассейна (1 этаж)
d.text(P(-70, -41), 'кровля бассейна, +8,4', font=font(12), fill=INK, anchor='mm')
d.rectangle([*P(-12, 60), *P(4, 40)], fill=(212, 214, 216), outline=INK, width=2)       # кровля рампы
d.rectangle([*P(-56, 22), *P(-10, -22)], outline=INK, width=2)
d.rectangle([*P(-52, 64), *P(-12, 22)], outline=INK, width=2)
d.rectangle([*P(-52, -22), *P(-12, -64)], outline=INK, width=2)
d.rectangle([*P(PATIO[0], PATIO[3]), *P(PATIO[2], PATIO[1])], fill=(206, 222, 190), outline=INK, width=2)
d.rectangle([*P(VOID[0], VOID[3]), *P(VOID[2], VOID[1])], fill=(190, 214, 232), outline=INK, width=2)
d.text(P(-33, 0), 'световой фонарь атриума', font=font(11), fill=INK, anchor='mm')
d.rectangle([*P(-56, 22), *P(-44, -22)], fill=(232, 214, 176), outline=LOCK_C, width=2)
for k in range(6):
    d.rectangle([*P(-54.5, -19 + k * 6.5), *P(-51.5, -21 + k * 6.5)], fill=(255, 255, 255), outline=MUTED)
d.text(P(-50, 20), 'солярий', font=font(12, True), fill=INK, anchor='mm')
for x0, y0, x1, y1, lab in ((-44, 10, -35, 22, 'выход'), (-32, 56, -26, 64, 'люк')):
    d.rectangle([*P(x0, y1), *P(x1, y0)], fill=(150, 150, 150), outline=INK, width=2)
    d.text(P((x0 + x1) / 2, (y0 + y1) / 2), lab, font=font(11), fill=(255, 255, 255), anchor='mm')
for x, y in ((-20, 50), (-16, 50), (-20, 34), (-48, -40), (-46, -60), (-16, -60)):      # вентиляция, кондиционеры
    d.rectangle([*P(x, y + 2), *P(x + 3, y)], fill=(120, 120, 124))
d.text(P(-32, 44), 'кровля +11,8, парапет 0,8', font=font(12), fill=INK, anchor='mm')
# разрез по оси y = 0
sx0 = PADX + int((XMAX - XMIN) * SC) + 30
d.text((sx0, PADY), 'Разрез по главной оси (y = 0): терраса — галерея — атриум — вестибюль — площадь', font=font(15, True), fill=INK)
d.text((sx0, PADY + 22), 'по вертикали × 2,5', font=font(12), fill=MUTED)
SS = 5.8
VZ = 2.5
base_y = PADY + 330


def S(x, z):
    return (sx0 + (x + 92) * SS, base_y - z * SS * VZ)


d.rectangle([S(-92, 0), S(14, -3)], fill=(214, 206, 186))
d.line([S(-92, 0), S(14, 0)], fill=INK, width=2)
zf = [0.0, 4.2, 8.0, 11.8]
for i in range(3):
    d.rectangle([S(-56, zf[i + 1]), S(-10, zf[i + 1] - 0.3)], fill=(170, 170, 168))
d.rectangle([S(-41, zf[3]), S(-25, zf[1] - 0.3)], fill=PAPER)                                   # проём атриума
d.rectangle([S(-41, zf[3] + 1.2), S(-25, zf[3])], fill=(190, 214, 232), outline=INK)            # фонарь
for x in (-56, -10):
    d.rectangle([S(x - 0.25, zf[3] + 0.8), S(x + 0.25, 0)], fill=(120, 120, 124))
d.rectangle([S(-56, zf[3] + 2.6), S(-44, zf[3] + 2.4)], fill=(150, 120, 90))                   # пергола солярия
for x in (-56, -50, -44):
    d.line([S(x, zf[3]), S(x, zf[3] + 2.6)], fill=(150, 120, 90), width=2)
for z, lab in ((0, '±0 терраса = плато +32'), (4.2, '+4,2'), (8.0, '+8,0'), (11.8, '+11,8 кровля'), (14.4, '+14,4 пергола солярия')):
    d.line([S(8, z), S(11, z)], fill=MUTED)
    d.text(S(11.5, z), lab, font=font(12), fill=MUTED, anchor='lm')
d.text(S(-73, 1.2), 'терраса', font=font(12), fill=INK, anchor='mm')
d.text(S(-50, 2), 'галерея', font=font(12), fill=INK, anchor='mm')
d.text(S(-33, 6), 'атриум в 3 света', font=font(12), fill=INK, anchor='mm')
d.text(S(-16, 2), 'вестибюль', font=font(12), fill=INK, anchor='mm')
d.text(S(2, 1.2), 'площадь', font=font(12), fill=INK, anchor='mm')
d.text(S(-50, zf[1] + 1.8), 'зал отдыха', font=font(11), fill=INK, anchor='mm')
d.text(S(-50, zf[2] + 1.8), 'библиотека', font=font(11), fill=INK, anchor='mm')
d.text(S(-16, zf[1] + 1.8), 'ожидание', font=font(11), fill=INK, anchor='mm')
d.text(S(-16, zf[2] + 1.8), 'тихая гостиная', font=font(11), fill=INK, anchor='mm')
# числа и проверка
ny = base_y + 50
summary = [f'Помещений: {sum(1 for f in ROOMS for r in ROOMS[f] if r[6] != "void")}, '
           f'дверей: {sum(len(DOORS[f]) for f in ROOMS)} (наружных — {sum(1 for d_ in DOORS[1] if d_[1] == "out")})',
           f'Площадь по полу: ' + ', '.join(f'{f} эт. ≈ {sum(area(r) for r in ROOMS[f] if r[6] != "void"):.0f} м²' for f in ROOMS),
           'Лестницы: парадная (атриум), северная служебная с грузовым лифтом, южная служебная; 2 пассажирских лифта',
           'Закрыто на ключ: медсклад, кабинет главврача, архив, касса с сейфом',
           'Проверка: ' + ('всё сходится — помещения не пересекаются, лестницы одна над другой,' if not PROBLEMS
                           else f'{len(PROBLEMS)} замечаний — см. вывод генератора'),
           ('  двери по общим стенам, каждое помещение достижимо от входов, без ключей — всё, кроме закрытых'
            if not PROBLEMS else '')]
for s in summary:
    d.text((sx0, ny), s, font=font(13), fill=INK)
    ny += 20
img.save(OUT_DIR / 'sanatorium_main_corps_roof_v01.png')

# --------------------------------------------------------------------------- данные
DATA.parent.mkdir(parents=True, exist_ok=True)
data = {'version': 'v01', 'note': 'предложение агента; координаты схемы участка, метры игры (правило E применено)',
        'floor_to_floor': FLOOR_TO_FLOOR, 'patio': PATIO, 'atrium_void': VOID, 'vertical': VERTICAL,
        'floors': {}}
for f in ROOMS:
    data['floors'][str(f)] = {
        'rooms': [{'id': r[0], 'no': numbers[f].get(r[0]), 'name': r[1], 'rect': [r[2], r[3], r[4], r[5]], 'kind': r[6],
                   'flags': r[7].split(), 'area': round(area(r), 1)} for r in ROOMS[f]],
        'doors': [{'a': dd[0], 'b': dd[1], 'width': dd[3], 'locked': (dd[0], dd[1]) in LOCKED_DOORS,
                   'wall': list(door_geom(BY_FLOOR[f], dd))} for dd in DOORS[f]],
    }
DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')

for p in PROBLEMS:
    print('ЗАМЕЧАНИЕ:', p)
print(f'главный корпус: помещений {sum(1 for f in ROOMS for r in ROOMS[f] if r[6] != "void")}, '
      f'дверей {sum(len(DOORS[f]) for f in ROOMS)}, замечаний {len(PROBLEMS)}')
