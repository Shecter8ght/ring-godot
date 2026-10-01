"""Копирование проверенного открытого канала ВСС в пользовательскую библиотеку."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_bore_v6'
LIBRARY=Path('E:/Models Blender/ВСС Винторез — полный комплект')
REVIEW='10_На_согласование_глушитель_v6'


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    audit=json.loads((RAW/'bore-audit.json').read_text(encoding='utf8'))
    build=json.loads((RAW/'build-report.json').read_text(encoding='utf8'))
    assert audit['status']=='PASS' and build['source_unchanged']
    assert digest(RAW/'Live_Source.blend')==build['source_sha256']
    for row in audit['files_reopened']:assert digest(RAW/row['name'])==row['sha256']
    bounds=audit['closed_assembly_bounds'];dimensions=bounds['dimensions_mm']
    state=f'''# ВСС: открытый канал глушителя, v6

Дата: 01.10.2026. Blender 5.2.2 LTS. Основа — сохранённая копия фактически
открытой v5; SHA256: {build['source_sha256']}. Прежние версии сохранены.

Вместо почти закрытого короткого дульного recess создана непрерывная
полая трубка Suppressor_barrel_through_tube. Вход и выход открыты.
Короткий канал в переднем стыке цевья исключает перекрытие входа торцом
соседней детали. Наружный кожух, насечки/кольца и прицельные детали не менялись.
{build['unchanged_mesh_parts']} прежних mesh-частей совпадают по evaluated геометрии и родителям.

Сборка с коротким магазином, верхней планкой и рукояткой, без оптики/студии,
переднее положение затвора: {dimensions[0]:.3f} × {dimensions[1]:.3f} ×
{dimensions[2]:.3f} мм; {bounds['mesh_objects']} mesh-часть,
{bounds['evaluated_triangles']} треугольников. Оси: +X к дульному торцу,
-Y правая сторона, +Z вверх; 1 единица Blender = 1 метр.
Внутренняя трубка художественная, её наружная стенка оценена для просмотра;
диаметр просвета следует уже существовавшему дульному отверстию модели.
Рабочие внутренние узлы не моделировались.

Глушитель доступен также самостоятельной native-сборкой с владельцем
Suppressor, сохранённой посадкой и обоими открытыми торцами. Камеры
Camera_V6_Front_Through и Camera_V6_Rear_Through соосны каналу.
Полная винтовка сохраняет VSS_Controls / VSS_Demo из v5:
Пробел — воспроизвести; кадр 45 — полный отвод, кадр 145 — упор.
Для ручных контролов отвязать действие VSS_Demo у VSS_Controls.

После нового открытия: 50 продольных лучей в собранном узле и 50 в
отдельном глушителе, по 25 точкам сечения с обоих торцов. Ещё 32 поперечных
луча подтверждают стенки по длине. Изменённые объёмы замкнуты, без нулевых
граней, overfull/wire/loose. Движение v5 проверено на восьми кадрах.
Свежие превью: оба торца, наклонный дульный торец, весь глушитель и винтовка.

Новые текстуры, UV/baking, Krita, игровые экспорты и Godot не выполнялись.
Магазины 10/20/30 остаются в разделе 08, прицелы и патрон — в 01_Blender.
Новая версия готова к дальнейшему осмотру владельцем.
'''
    (RAW/'asset-state.md').write_text(state,encoding='utf8')
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

    copy(RAW/'VSS_Bore_v6.blend','00_ВСС_Глушитель_v6.blend')
    copy(RAW/'Suppressor_Through_Bore.blend','01_Глушитель_отдельно.blend')
    for image in sorted(RAW.glob('v6_*.png')):copy(image,'Превью/'+image.name)
    for name in ('asset-state.md','build-report.json','bore-audit.json'):copy(RAW/name,'Документы/'+name)
    readme='''ВСС — ГЛУШИТЕЛЬ СО СКВОЗНЫМ КАНАЛОМ v6
Дата: 01.10.2026

00_ВСС_Глушитель_v6.blend — полная винтовка со всеми правками v4/v5.
При открытии показан крупный план дульного отверстия.
01_Глушитель_отдельно.blend — самостоятельный глушитель для осмотра канала;
прицельные детали принадлежат его сборке и сохранены.

Внутри вместо почти закрытого углубления проходит открытая с двух концов
полая трубка. Внешняя форма глушителя сохранена.
В отдельном файле Camera_V6_Front_Through / Camera_V6_Rear_Through дают
соосный взгляд с переднего / заднего торца. Numpad 0 — выход из камеры.
Свежие рендеры находятся в Превью; проверки и описание — в Документы.

Демонстрация затвора/предохранителя из v5 сохранена в полной винтовке.
Пробел над Timeline запускает действие; кадр 45 — полный отвод,
кадр 145 — ограничение хода поднятым предохранителем.
Для просмотра движения переключитесь на Camera_V5_Side.

Отдельные пустые/снаряжённые магазины 10/20/30 остаются в разделе 08.
Оба прицела и СП-5 находятся в прежней папке 01_Blender.
Новые текстуры и игровые экспорты на этом этапе не выполнялись.
Это художественная геометрия; внутренние стенки оценены для осмотра.
'''
    (destination/'НАЧНИ_ЗДЕСЬ.txt').write_text(readme,encoding='utf8')
    guide=LIBRARY/'00_НАЧНИ_ЗДЕСЬ.txt';marker='НОВОЕ: СКВОЗНОЙ КАНАЛ ГЛУШИТЕЛЯ — v6 (01.10.2026)'
    if guide.exists():
        previous=guide.read_text(encoding='utf-8-sig')
        if not previous.startswith(marker):
            (destination/'Документы/Предыдущая_памятка_v5.txt').write_text(previous,encoding='utf8')
            guide.write_text(marker+'\nОткройте '+REVIEW+'\\00_ВСС_Глушитель_v6.blend\n'
                'Полная ВСС сохраняет крючок и демонстрацию предохранителя из v5.\n'
                'Рядом — 01_Глушитель_отдельно.blend, оба торца и результаты проверок.\n\n'
                'ПРЕДЫДУЩИЕ ПОСТАВКИ:\n'+previous,encoding='utf8')
    report={'status':'PASS','destination':str(destination),'copied_files':len(entries),
            'blend_files':sum(row['path'].endswith('.blend') for row in entries),
            'bytes':sum(row['bytes'] for row in entries),'files':entries}
    (RAW/'library-copy-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (destination/'Документы/Список_файлов.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({key:report[key] for key in ('status','destination','copied_files','blend_files','bytes')},ensure_ascii=False))


if __name__=='__main__':main()
