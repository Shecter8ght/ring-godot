"""Именованная передача новой геометрии и визуального движения в библиотеку ВСС."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_motion_v5'
LIBRARY=Path('E:/Models Blender/ВСС Винторез — полный комплект')
REVIEW='09_На_согласование_затвор_v5'
REFERENCES=(
    'a83fdd1e-3bde-4d8a-bd0a-48dd9da157ce',
    '591bdb1b-a3d5-43e0-a4e2-8a149bc8a175',
    'f98c645e-59ca-41dc-97bd-a4c90ffde1bc',
    '2df29e08-9d0b-4ae2-89fb-b8290bccd612',
    '43e6ecbb-c92e-4b88-8926-a0b86c7e91ab',
    '279bfed9-aa71-4b41-ab4a-6ae0e5aff572',
    '324b00ee-3ea0-4812-825a-ccb8a6397490',
)


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    audit=json.loads((RAW/'motion-audit.json').read_text(encoding='utf8'))
    build=json.loads((RAW/'build-report.json').read_text(encoding='utf8'))
    video=json.loads((RAW/'video-check.json').read_text(encoding='utf8'))
    assert audit['status']=='PASS' and video['status']=='PASS'
    assert build['source_unchanged'] and digest(RAW/'Live_Source_v4.blend')==build['source_sha256']
    assert len(audit['files_reopened'])==4
    for row in audit['files_reopened']:assert digest(RAW/row['name'])==row['sha256']
    bounds=audit['closed_bounds'];dimensions=bounds['dimensions_mm']
    state=f'''# ВСС: крючок затворной рукоятки и визуальное движение, v5

Дата: 01.10.2026. Blender 5.2.2 LTS. Основа — сохранённая копия фактически
открытой v4; SHA256: {build['source_sha256']}. Предыдущие исходники сохранены.

Изменены наружная рукоятка (единая изогнутая лопатка-крючок), видимая крышка
рамы, окно выброса/продольная прорезь и передние отгибы предохранителя.
Крышка и крючок принадлежат Bolt_carrier и уходят назад вместе. Верх листа
повторяет внутренний радиус неподвижного кожуха. Ось предохранителя неподвижна.
Дерево, сопряжения, затыльник, магазин и ещё {build['unchanged_mesh_parts']} mesh-частей
сохранены по evaluated координатам, топологии и родителям.

Сборка с коротким магазином, верхней планкой и рукояткой, без оптики/студии:
{dimensions[0]:.3f} × {dimensions[1]:.3f} × {dimensions[2]:.3f} мм;
{bounds['mesh_objects']} mesh-часть, {bounds['evaluated_triangles']} треугольников.
Blender: +X к дульному торцу, -Y правая сторона, +Z вверх, единицы — метры.

VSS_Controls: safety_up 0..1 и bolt_pull 0..1. Нативные драйверы работают
после свежего открытия без Python handlers или пользовательского namespace.
Для ручных правок следует отвязать действие VSS_Demo у VSS_Controls,
иначе переход на другой кадр восстановит ключевые значения контролов.
Максимальный показанный ход — 74 мм; с поднятым предохранителем — около
55 мм. Это художественно поставленный наружный ход по фотографиям, а не
обмер механизма или его физическая симуляция. Внутренние исполнительные
узлы и самостоятельный экстрактор не создавались; показано окно выброса.

Проверены 45 сочетаний положения рычага и отвода, крайние/промежуточные
кадры, геометрический упор и 7 лучей через отверстие. Сдвиг ещё на 0.7 мм
за ограничитель вызывает пересечение крючка с рычагом, подтверждая место
упора. Проверенные исправленные объёмы замкнуты, без вырожденных граней.
Четыре сохранённых файла повторно открыты. Ролик — 180 свежих кадров,
6 секунд при 30 кадрах/с из того же финального .blend.

Новые текстуры/UV/baking/Krita, игровые экспорты и Godot в v5 не выполнялись.
Материалы простые для просмотра формы. Шесть отдельных магазинов 10/20/30
остаются в 08_На_согласование_геометрия_v4; оба прицела и патрон — в 01_Blender.
Фото служат только референсами формы, их пиксели не переносятся в материалы.
После осмотра владельцем можно продолжать следующую запрошенную правку.
'''
    (RAW/'asset-state.md').write_text(state,encoding='utf8')
    refs=RAW/'Референсы';refs.mkdir(exist_ok=True)
    for index,identifier in enumerate(REFERENCES,1):
        source=Path('C:/Users/SCHECT~1/AppData/Local/Temp')/f'codex-clipboard-{identifier}.png'
        target=refs/f'{index:02d}_Затвор_и_предохранитель.png'
        if not target.exists():shutil.copy2(source,target)
        assert digest(source)==digest(target)
    destination=LIBRARY/REVIEW;destination.mkdir(parents=True,exist_ok=True);entries=[]

    def copy(source,relative):
        target=destination/relative
        assert target.resolve().is_relative_to(destination.resolve())
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and digest(source)!=digest(target):
            raise RuntimeError('Different review file already exists: '+str(target))
        if not target.exists():shutil.copy2(source,target)
        assert digest(source)==digest(target)
        entries.append({'path':relative,'sha256':digest(target),'bytes':target.stat().st_size})

    copy(RAW/'VSS_Motion_v5.blend','00_ВСС_Затвор_v5.blend')
    for source,label in (('01_Closed','01_Закрыт'),('02_Full_Travel','02_Полный_ход'),
                         ('03_Safety_Stop','03_Предохранитель_упор')):
        copy(RAW/(source+'.blend'),'Положения/'+label+'.blend')
    for image in sorted(RAW.glob('v5_*.png')):copy(image,'Превью/'+image.name)
    copy(RAW/'v5_motion.mp4','Превью/Демонстрация_хода.mp4')
    for file in sorted(refs.iterdir()):copy(file,'Референсы/'+file.name)
    for name in ('asset-state.md','build-report.json','motion-audit.json','contact-samples.json','video-check.json'):
        copy(RAW/name,'Документы/'+name)
    readme='''ВСС — ЗАТВОРНАЯ РУКОЯТКА И ПРЕДОХРАНИТЕЛЬ v5
Дата: 01.10.2026

НАЧНИТЕ С 00_ВСС_Затвор_v5.blend
Откроется крупный план новой рукоятки-крючка и окна выброса.
Пробел над Timeline или 3D-вьюпортом — воспроизвести 6-секундную демонстрацию.
Кадры 1–80: предохранитель опущен, рукоятка проходит весь показанный ход.
Кадры 95–180: предохранитель поднят, рукоятка останавливается у его выступа.

ГОТОВЫЕ ПОЛОЖЕНИЯ — отдельные .blend в папке Положения
01_Закрыт — переднее положение, кадр 1.
02_Полный_ход — опущенный предохранитель, отвод назад, кадр 45.
03_Предохранитель_упор — поднятый предохранитель, упор, кадр 145.
Все три содержат полную винтовку и то же действие демонстрации.

Превью — общий вид, крупные планы, вид крючка сверху и MP4-демонстрация.
Референсы — семь последних изображений владельца.
Документы — описание текущего состояния и результаты реальных проверок.

РУЧНОЕ УПРАВЛЕНИЕ
В Outliner выберите VSS_Controls. В Action Editor отвяжите VSS_Demo кнопкой X.
В свойствах объекта / Пользовательские свойства:
safety_up: 0 — опущен, 1 — поднят;
bolt_pull: 0 — вперёд, 1 — запрос полного отвода.
Драйвер сам ограничивает фактический отвод при поднятом предохранителе.
Для возврата демонстрации повторно откройте файл либо назначьте VSS_Demo.
Numpad 0 — выйти из камеры; средняя кнопка мыши — повернуть обзор.
Camera_V5_Top показывает крючок сверху, Camera_V5_Side — профиль узла.

ОСТАЛЬНЫЕ АССЕТЫ
Шесть пустых/снаряжённых магазинов 10/20/30 — в соседнем разделе
08_На_согласование_геометрия_v4/Магазины. Оба прицела и СП-5 — в 01_Blender.
Ранее сделанные версии остаются в прежних пронумерованных папках.

Это этап согласования геометрии и визуального движения. Новый текстурный
этап и игровые экспорты не выполнялись. Ход оценён по внешним фото;
демонстрация не является физической симуляцией внутреннего устройства.
'''
    (destination/'НАЧНИ_ЗДЕСЬ.txt').write_text(readme,encoding='utf8')
    guide=LIBRARY/'00_НАЧНИ_ЗДЕСЬ.txt';marker='НОВОЕ: ЗАТВОР И ПРЕДОХРАНИТЕЛЬ — v5 (01.10.2026)'
    if guide.exists():
        previous=guide.read_text(encoding='utf-8-sig')
        if not previous.startswith(marker):
            (destination/'Документы/Предыдущая_памятка_v4.txt').write_text(previous,encoding='utf8')
            guide.write_text(marker+'\nОткройте '+REVIEW+'\\00_ВСС_Затвор_v5.blend\n'
                'Новая рукоятка-крючок, окно выброса и демонстрация ограничения хода.\n'
                'В '+REVIEW+' есть три положения, видео и понятная памятка.\n'
                'Отдельные магазины 10/20/30 по-прежнему находятся в разделе 08.\n\n'
                'ПРЕДЫДУЩИЕ ПОСТАВКИ:\n'+previous,encoding='utf8')
    report={'status':'PASS','destination':str(destination),'copied_files':len(entries),
            'blend_files':sum(row['path'].endswith('.blend') for row in entries),
            'bytes':sum(row['bytes'] for row in entries),'files':entries}
    (RAW/'library-copy-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (destination/'Документы/Список_файлов.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({key:report[key] for key in ('status','destination','copied_files','blend_files','bytes')},ensure_ascii=False))


if __name__=='__main__':main()
