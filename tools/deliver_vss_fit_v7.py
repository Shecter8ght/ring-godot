"""Понятная библиотека ВСС с исправленной шахтой и новым направлением крючка."""
from pathlib import Path
import hashlib,json,shutil,sys

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_fit_v7'
LIBRARY=Path('E:/Models Blender/ВСС Винторез — полный комплект')
REVIEW='11_На_согласование_шахта_и_крючок_v7'


def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    audit=json.loads((RAW/'fit-audit.json').read_text(encoding='utf8'))
    build=json.loads((RAW/'build-report.json').read_text(encoding='utf8'))
    video=json.loads((RAW/'video-check.json').read_text(encoding='utf8'))
    assert audit['status']==video['status']=='PASS' and build['source_unchanged']
    assert digest(RAW/'Live_Source.blend')==build['source_sha256']
    for row in audit['files_reopened']:assert digest(Path(row['file']))==row['sha256']
    for row in build['magazines']:assert digest(Path(row['source']))==row['source_sha256']==digest(Path(row['file']))
    bounds=audit['closed_bounds'];size=bounds['dimensions_mm']
    limit=audit['manual_poses'][-1]['allowed_travel_mm']
    state=f'''# ВСС: посадка магазина и более пологий крючок, v7

Дата: 01.10.2026, Blender 5.2.2 LTS. Основа — копия открытой v6,
SHA256 {build['source_sha256']}. Предыдущие исходники сохранены.

Текущий файл: {LIBRARY/REVIEW/'01_ВСС_Шахта_и_крючок_v7.blend'}
Рабочий исходник: {RAW/'VSS_Fit_v7.blend'}

Передний торец шахты подогнан к существующему верхнему профилю магазина.
Внутри боковой накладки и нижней коробки создана настоящая посадочная
полость, передняя губка и боковые стенки сохранены. Исходная шахта была
сплошной и уже верхнего края магазина, что давало пересечение.
Верх/рёбра/плавная дуга/патроны и origin всех шести магазинов сохранены;
копии отдельных Empty/Loaded 10/20/30 побайтно совпадают с разделом 08.
Каждый вариант примерен в ту же шахту. Проверены все его mesh-части,
включая зацепы, губки, подаватель и два видимых патрона у Loaded.

Свободный конец Charging_handle_hook направлен вперёд (+X), в сторону,
противоположную v5/v6. Короткая открытая дуга заметно положе и похожа на
форму спускового крючка. Подвижный владелец Bolt_carrier сохранён.
Ограничение хода заново снято с evaluated поверхностей новой рукоятки
и поднятого предохранителя. Показанный полный ход 74 мм; остановка
при поднятом предохранителе около {limit:.2f} мм. Это постановочный
наружный ход, не обмер или физическая симуляция внутренних механизмов.

Остальные {build['unchanged_mesh_parts']} mesh-частей совпадают по evaluated геометрии/родителям,
включая сквозной канал глушителя из v6. В передней позе сборка с коротким
магазином/планкой/рукояткой, без оптики/студии: {size[0]:.3f} ×
{size[1]:.3f} × {size[2]:.3f} мм, {bounds['mesh_objects']} mesh-часть,
{bounds['evaluated_triangles']} треугольников. +X вперёд, -Y справа,
+Z вверх; 1 единица Blender = 1 метр.

После свежего открытия: посадка шести магазинов без пересечений с двумя
объёмами шахты, контроль полости/сохранённых боковых стенок, замкнутая
топология исправленных деталей без нулевых граней. Проверены направление
и более мелкий изгиб крючка, 45 сочетаний контролов, геометрический упор
и промежуточная анимация. Все восемь native-файлов повторно открыты.
Актуальные ракурсы показывают передний/задний стык, вид снизу, крючок
сверху/под углом, полный ход/упор и отдельные профили/верх магазинов.

VSS_Controls: safety_up 0..1, bolt_pull 0..1; Пробел запускает VSS_Demo.
Для ручных правок отвязать VSS_Demo в Action Editor у VSS_Controls.
Кадр 45 — полный отвод, кадр 145 — упор. Ролик v7 заново рассчитан из
финального файла: 180 кадров, 30 fps, 6 секунд, 1280×800.

Новые текстуры/UV/baking/Krita, игровые экспорты и Godot не выполнялись.
Оба прицела и патрон остаются в прежнем разделе 01_Blender;
самостоятельный глушитель — в разделе 10. Следующий этап — осмотр владельцем.
'''
    (RAW/'asset-state.md').write_text(state,encoding='utf8')
    references=RAW/'Референсы';references.mkdir(exist_ok=True)
    for identifier,label in (
        ('f63fecdc-6dce-4596-901f-4b45463affa0','01_Замечание_по_шахте'),
        ('994bf8a5-d781-494f-a224-7a5911755541','02_Замечание_по_крючку')):
        source=Path('C:/Users/SCHECT~1/AppData/Local/Temp')/f'codex-clipboard-{identifier}.png'
        target=references/(label+'.png');shutil.copy2(source,target);assert digest(source)==digest(target)
    destination=LIBRARY/REVIEW;destination.mkdir(parents=True,exist_ok=True);entries=[]

    def copy(source,relative):
        target=destination/relative
        assert target.resolve().is_relative_to(destination.resolve())
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and digest(source)!=digest(target):raise RuntimeError('Different review file: '+str(target))
        if not target.exists():shutil.copy2(source,target)
        assert digest(source)==digest(target)
        entries.append({'path':relative,'sha256':digest(target),'bytes':target.stat().st_size})

    copy(RAW/'VSS_and_Magazines_v7.blend','00_ВСС_и_магазины_10_20_30.blend')
    copy(RAW/'VSS_Fit_v7.blend','01_ВСС_Шахта_и_крючок_v7.blend')
    for capacity in (10,20,30):
        for state,label in (('Empty','Пустой'),('Loaded','Снаряжённый')):
            identifier=f'Magazine_939_{capacity}_{state}';folder=RAW/'Магазины'/identifier
            copy(folder/(identifier+'.blend'),f'Магазины/{capacity}_патронов/{label}.blend')
            for file in sorted(folder.glob('v7_*.png')):copy(file,f'Превью/Магазины/{capacity}_патронов/{label}/{file.name}')
    for file in sorted(RAW.glob('v7_*.png')):copy(file,'Превью/'+file.name)
    copy(RAW/'v7_motion.mp4','Превью/Демонстрация_крючка_v7.mp4')
    for file in sorted(references.iterdir()):copy(file,'Референсы/'+file.name)
    for name in ('asset-state.md','fit-audit.json','build-report.json','contact-samples.json','video-check.json'):
        copy(RAW/name,'Документы/'+name)
    readme='''ВСС — ПОСАДКА МАГАЗИНА И НАПРАВЛЕНИЕ КРЮЧКА v7
Дата: 01.10.2026

01_ВСС_Шахта_и_крючок_v7.blend — актуальная винтовка, крупный план узла.
00_ВСС_и_магазины_10_20_30.blend — общий просмотр: сверху винтовка,
средний ряд пустой, нижний снаряжённый; слева направо 10 / 20 / 30.
Магазины/10_патронов, 20_патронов, 30_патронов — шесть отдельных файлов.

Передняя губка и полость шахты подогнаны к исходному плавному магазину;
форма магазина и место посадки сохранены. Каждый вариант примерен.
Крючок направлен вперёд и сделан более пологим. Демонстрация упора
предохранителем пересчитана по новой форме рукоятки.

Камеры в основной винтовке:
Camera_V7_Mag_Front / Mag_Left / Mag_Bottom — посадка с обеих сторон и снизу.
Camera_V7_Hook_Top / Hook_Angle — крючок сверху и под углом.
Camera_V7_Review — одновременно оба исправленных участка.
Camera_V5_Side — профиль демонстрации затвора.
Numpad 0 — выйти из камеры; средняя кнопка мыши — вращать обзор.

Пробел над Timeline — воспроизвести VSS_Demo. Кадр 45 — полный отвод,
кадр 145 — остановка поднятым предохранителем. Для ручного управления
выбрать VSS_Controls и отвязать VSS_Demo кнопкой X в Action Editor;
safety_up: 0 — опущен / 1 — поднят, bolt_pull: 0 — вперёд / 1 — запрос отвода.
В Превью есть новый ролик, крупные планы и отдельные виды магазинов.
Референсы — два замечания владельца; Документы — описание и проверки.

Сквозной канал глушителя v6 и предыдущие правки приклада сохранены.
Оба прицела и СП-5 остаются в 01_Blender общей библиотеки;
отдельный глушитель — в разделе 10. Прежние версии не удалены.
Новые текстуры и игровые экспорты в этой версии не выполнялись.
'''
    (destination/'НАЧНИ_ЗДЕСЬ.txt').write_text(readme,encoding='utf8')
    guide=LIBRARY/'00_НАЧНИ_ЗДЕСЬ.txt';marker='НОВОЕ: ШАХТА И КРЮЧОК — v7 (01.10.2026)'
    previous=guide.read_text(encoding='utf-8-sig')
    if not previous.startswith(marker):
        (destination/'Документы/Предыдущая_памятка_v6.txt').write_text(previous,encoding='utf8')
        guide.write_text(marker+'\nОткройте '+REVIEW+'\\01_ВСС_Шахта_и_крючок_v7.blend\n'
            'Рядом есть общий просмотр с шестью отдельными магазинами и новый ролик.\n'
            'Шахта подогнана, крючок развёрнут и сделан положе; канал глушителя сохранён.\n\n'
            'ПРЕДЫДУЩИЕ ПОСТАВКИ:\n'+previous,encoding='utf8')
    report={'status':'PASS','destination':str(destination),'copied_files':len(entries),
            'blend_files':sum(row['path'].endswith('.blend') for row in entries),
            'bytes':sum(row['bytes'] for row in entries),'files':entries}
    (RAW/'library-copy-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (destination/'Документы/Список_файлов.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({key:report[key] for key in ('status','destination','copied_files','blend_files','bytes')},ensure_ascii=False))


def finalize():
    report=json.loads((RAW/'library-copy-report.json').read_text(encoding='utf8'))
    verified=json.loads((RAW/'library-blend-check.json').read_text(encoding='utf8'))
    destination=LIBRARY/REVIEW
    assert Path(report['destination'])==destination and verified['status']=='PASS'
    assert len(verified['files'])==8
    for row in verified['files']:assert digest(Path(row['file']))==row['sha256']
    state=RAW/'asset-state.md';body=state.read_text(encoding='utf8')
    if 'Текущий файл:' not in body:
        title,remainder=body.split('\n',1)
        body=title+'\n\nТекущий файл: '+str(destination/'01_ВСС_Шахта_и_крючок_v7.blend')+'\nРабочий исходник: '+str(RAW/'VSS_Fit_v7.blend')+'\n'+remainder
    for source,relative in ((state,'Документы/asset-state.md'),(RAW/'library-blend-check.json','Документы/library-blend-check.json')):
        target=destination/relative;assert target.resolve().is_relative_to(destination.resolve())
        previous=next((entry for entry in report['files'] if entry['path']==relative),None)
        if previous:assert digest(target)==previous['sha256']
        if source==state:state.write_text(body,encoding='utf8')
        shutil.copy2(source,target);assert digest(source)==digest(target)
        entry={'path':relative,'sha256':digest(target),'bytes':target.stat().st_size}
        if previous:previous.update(entry)
        else:report['files'].append(entry)
    report['copied_files']=len(report['files']);report['bytes']=sum(row['bytes'] for row in report['files'])
    for file in (RAW/'library-copy-report.json',destination/'Документы/Список_файлов.json'):
        file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V7_DELIVERY_FINALIZED',report['copied_files'],report['bytes'])


if __name__=='__main__':
    finalize() if '--finalize' in sys.argv else main()
