"""Record the owner's choices; append phone recipes without rewriting the catalogue."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/quest_phone'
SOURCE_HASH = '13e406a76661eefa9f73d0d8ad80749009dd5704cef9601e0a93c40073388bdb'

RECIPES = [
    dict(code='MT-GPH-SAT', group='bright', title='Металл графитовый, атлас смартфона',
         step='атлас', kind='metal', base=dict(color=[.23,.24,.25], rough=.33, metal=1.),
         grain=dict(mm=.035, rough=.035, color=0., height=0.),
         use='Рамка, кнопки и ободы камер смартфона QuestPhone'),
    dict(code='GL-GPH-FRST', group='glass', title='Стекло графитовое, матовое на подложке',
         step='мат', kind='glass', base=dict(color=[.145,.15,.16], rough=.58, metal=0.),
         grain=dict(mm=.025, rough=.025, color=0., height=0.),
         render=dict(ior=1.52),
         use='Задняя панель и площадка камер; стекло с непрозрачной тёмной подложкой, единый составной материал'),
    dict(code='GL-PHONE-OFF', group='glass', title='Чёрное стекло выключенного дисплея',
         step='глянец', kind='glass', base=dict(color=[.09,.092,.096], rough=.055, metal=0.),
         grain=None, render=dict(ior=1.52),
         use='Переднее стекло с чёрной подложкой и выключенный OLED; составной непрозрачный материал')
]

def setup():
    p = ROOT / 'tools/asset_kit/finish/finishes.json'
    original = p.read_text(encoding='utf-8')
    data = json.loads(original)
    existing = {f['code']:f for f in data['finishes']}
    added = []
    for f in RECIPES:
        f.update(edges=None, cavity=None, gradients=None,
                 origin='QuestPhone: выбор владельца 2026-11-04; художественная отделка, не химическая спецификация Apple',
                 godot='Игровой материал готовится отдельно после принятия отделки')
        if f['code'] not in existing:
            added.append(f)
        else:
            assert existing[f['code']] == f, f['code']
    if added:
        # Retain the catalogue's hand-formatted entries and all concurrent additions.
        end = original.rfind(']')
        text = ',\n' + ',\n'.join('    '+json.dumps(f,ensure_ascii=False) for f in added)+'\n  '
        p.write_text(original[:end].rstrip()+text+original[end:],encoding='utf-8')
    slots = [
        ('frame','Рамка, кнопки, ободы камер','MT-GPH-SAT',['Рамка']),
        ('back','Заднее матовое стекло и площадка камер','GL-GPH-FRST',['Задняя панель']),
        ('front','Переднее стекло и выключенный экран','GL-PHONE-OFF',['Стекло','Экран']),
        ('optics','Прозрачные стёкла объективов','GL-AR',['Оптика']),
        ('camera_cover','Защитные стёкла трёх камер','GL-CLR',['Защитное стекло камер']),
        ('seals','Уплотнения и чёрные внутренние детали','RB-BLK-MAT',['Внутри']),
        ('polymer','Антенные вставки и USB-C','PL-BLK-SMO',['Полимер']),
        ('contacts','Контакты разъёма','NI-PLT-SAT',['Контакты']),
        ('flash','Рассеиватель вспышки','TL-MLK-FRO',['Вспышка'])
    ]
    spec = dict(schema='ring-finish-spec/1',asset='QuestPhone',stage='factory',
        model='models/QuestPhone_factory_v01.blend',
        source=dict(model='models/QuestPhone_v02.blend',sha256=SOURCE_HASH,accepted=True,
                    acceptance='2026-11-04: владелец — «принимаю»'),
        catalog='tools/asset_kit/finish/finishes.json',
        interview=[dict(question='Заводская отделка телефона',answer='Графит: тёмная рамка и матовое тёмное стекло'),
                   dict(question='Металлические ободы трёх задних камер',answer='В цвет металлической рамки')],
        slots=[dict(id=i,title=t,finish=f,parts=parts,overrides={},note='') for i,t,f,parts in slots],
        favorites=[],requests=[],history=[dict(time='2026-11-04',by='Явные ответы владельца в чате',
            note='Выбор палитры записан; численные рецепты и законченная отделка ещё предъявляются владельцу.')],
        accepted=False)
    for s in spec['slots']:
        if s['id'] in ['seals','polymer','contacts','flash']:
            s['overrides']=dict(grain=None,edges=None,cavity=None,gradients=None,layers=None)
            s['note']='Малые гладкие детали смартфона: только основа, без разводов литья и оружейных кромок.'
    p = WORK / 'finish-spec.json'
    if not p.exists():
        p.write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PHONE FINISH SPEC',p)

if __name__ == '__main__':
    setup()
