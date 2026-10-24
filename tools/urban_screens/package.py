"""Проверка полноты выдачи и копирование только этой партии в библиотеку на E."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import statistics
from PIL import Image, ImageStat
from catalog import ROOT, PROJECT, DELIVERY, assets


def verify():
    expected=assets()
    reports=[]
    issues=[]
    boundary_notes=[]
    image_count=0
    for a in expected:
        folder=ROOT/'assets'/f"{a['id']}_{a['key']}"
        report=json.loads((folder/'checks/geometry.json').read_text(encoding='utf-8'))
        blend=folder/'model'/f"{a['id']}_{a['key']}_geometry_v01.blend"
        if hashlib.sha256(blend.read_bytes()).hexdigest()!=report['blend_sha256']:
            issues.append(a['id']+': SHA-256 does not match reviewed candidate')
        if report['zero_area_faces'] or report['nonmanifold_edges'] or report['loose_vertices']:
            issues.append(a['id']+': topology defect')
        if abs(report['bounds_min_m'][2])>1e-5:
            issues.append(a['id']+': ground contact')
        if min(report['dimensions_m'])<=0 or report['triangles']<=0:
            issues.append(a['id']+': empty / collapsed model')
        if report['production_uv'] or report['production_textures']:
            issues.append(a['id']+': unapproved production stage')
        if not report['saved_file_reopened']:
            issues.append(a['id']+': file not reopened')
        for view in ('front34','rear34','front','right'):
            image=folder/'previews'/f'{view}.png'
            with Image.open(image) as im:
                im.load()
                if im.size!=(1000,850) or max(ImageStat.Stat(im.convert('RGB')).stddev)<2:
                    issues.append(a['id']+': blank or wrong size view '+view)
            image_count+=1
        state=(folder/'asset-state.md').read_text(encoding='utf-8')
        if report['blend_sha256'] not in state:
            issues.append(a['id']+': state points at a different file')
        if report['boundary_edges']:
            boundary_notes.append(dict(id=a['id'],kind='FONT curve tessellation, editable raised reference lettering',
                                       boundary_edges=report['boundary_edges']))
        reports.append(dict(id=a['id'],key=a['key'],name=a['name'],screenshot=a['screenshot'],
            file=str(blend.relative_to(ROOT)),**report))
    counts=Counter(a['screenshot'] for a in expected)
    if len(reports)!=95 or any(counts[i]!=5 for i in range(1,20)):
        issues.append('Not exactly 5 assets per screenshot')
    if len({d['geometry_sha256'] for d in reports})!=95:
        issues.append('Duplicate geometry')
    if len(list((ROOT/'assets').glob('*/model/*.blend')))!=95:
        issues.append('Unexpected model file count')
    source_files=list((ROOT/'references').glob('screen_*.png'))
    if len(source_files)!=19: issues.append('Missing screenshot references')
    tri=[r['triangles'] for r in reports]
    summary=dict(stage='geometry_candidate_v01_pending_owner_review',
        geometry_approved=False,production_textures=False,game_ready=False,
        models=95,models_per_screenshot=dict(sorted(counts.items())),
        distinct_geometry=95,neutral_views=image_count,
        saved_candidates_reopened=95,zero_area_faces=sum(r['zero_area_faces'] for r in reports),
        overfull_edges=sum(r['nonmanifold_edges'] for r in reports),
        loose_vertices=sum(r['loose_vertices'] for r in reports),
        total_triangles=sum(tri),min_triangles=min(tri),max_triangles=max(tri),
        median_triangles=statistics.median(tri),intentional_boundary_notes=boundary_notes,
        source_references=19,issues=issues,
        dimension_basis='Estimated artistic reconstruction from screenshots; not measured original objects',
        visual_review_scope='Representative complex assets inspected individually; four views available for all 95',
        limitations=['Owner has not accepted geometry',
          'Not pixel-exact replicas; hidden sides are author reconstruction',
          'Neutral geometry slots only; requested surface textures still pending',
          'No production UV, game mesh, LOD, collisions or engine integration',
          'Editable font curves are separate geometry-review markings; final markings are planned in texture layers'])
    checks=ROOT/'checks'; checks.mkdir(exist_ok=True)
    (checks/'bundle_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (checks/'review_manifest.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Геометрия 95 ассетов — кандидат v01', '',
      '19 кадров × 5 разных предметов. Все .blend можно открыть по отдельности в Blender 5.2.', '',
      '**Текущая стадия:** геометрия для просмотра. Форма ещё не принята владельцем. '
      'Производственные UV и PBR не начаты; игровые LOD/коллизии и экспорт не выполнены.', '',
      'Структура: `assets/Uxx_yy_name/model/` — редактируемый .blend; '
      '`previews/` — четыре нейтральных вида; `checks/geometry.json` — измерения и аудит; '
      '`asset-state.md` — состояние конкретного ассета. Номер Uxx соответствует кадру из запроса. '
      '`references/screen_xx.png` — исходный визуальный референс.', '',
      'Модель — коллекция `MODEL | editable components`. Камера находится отдельно в `STUDIO`. '
      'Низ геометрии Z=0, масштаб в метрах. Размеры оценены по изображению; скрытая конструкция '
      'реконструирована. Крупные сборки — самостоятельные детали с собственными материалами SLOT_*.', '',
      'Проверено: 95 файлов сохранены и повторно открыты, 380 изображений читаются и не пустые, '
      '95 различных геометрических подписей, пять моделей на каждый из 19 кадров, ноль свободных '
      'вершин, нулевых граней и рёбер с более чем двумя гранями. У редактируемого текста есть '
      'открытые границы при вычислении: они перечислены в отчёте и не относятся к основным сеткам.', '',
      'Нейтральные изображения показывают форму. Визуально проверены характерные сложные предметы; '
      'автоматические проверки не подтверждают сходство всех деталей с оригиналом или качество '
      'финальных игровых моделей. Авторская реконструкция и оценки требуют просмотра владельца.', '',
      'Текущая партия занимает около 0,3 ГБ; переход на D не потребовался. Матрица — `asset_matrix.md`. '
      'Скриншоты используются только как визуальные референсы, не как игровые текстуры. '
      'Бренды и интерфейс не перенесены; геометрия создана заново.', '',
      'Следующий этап по blender-asset-workflow: принятие показанной геометрии владельцем, '
      'затем UV и UCUPaint/PBR по фактурам кадров. После принятия отделки — отдельная игровая подготовка.', '',
      'Воспроизводимые исходники генераторов: `source_tools/`. Запуск из репозитория: '
      '`Blender --background --factory-startup --python-exit-code 1 --python tools/urban_screens/generate.py -- --ids all`. '
      'Для одного предмета: `--ids U13_03` или `--ids wheelchair`.', '',
      'Ниже — перечень файлов; это технический указатель, не презентация.', '',
      '| ID | Предмет | Файл |', '|---|---|---|']
    for a in expected:
        rel=f"assets/{a['id']}_{a['key']}/model/{a['id']}_{a['key']}_geometry_v01.blend"
        lines.append(f"| {a['id']} | {a['name']} | [{Path(rel).name}]({rel}) |")
    (ROOT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    shutil.copy2(PROJECT/'docs/assets/urban_screens_95_matrix.md',ROOT/'asset_matrix.md')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('intentional_boundary_notes','limitations','models_per_screenshot')},ensure_ascii=False,indent=2))
    if issues: raise SystemExit('Bundle validation failed')
    return summary


def deliver():
    # Пишем только в отдельную папку этой партии, не затрагивая библиотеку вокруг.
    if DELIVERY.exists() and not (DELIVERY/'README.md').exists():
        raise SystemExit('Destination exists without this bundle marker; refusing overwrite')
    DELIVERY.mkdir(parents=True,exist_ok=True)
    for folder in ('assets','references'):
        shutil.copytree(ROOT/folder,DELIVERY/folder,dirs_exist_ok=True)
    (DELIVERY/'checks').mkdir(exist_ok=True)
    for file in ('bundle_summary.json','review_manifest.json'):
        shutil.copy2(ROOT/'checks'/file,DELIVERY/'checks'/file)
    for file in ('README.md','asset_matrix.md','manifest.json','license.txt'):
        shutil.copy2(ROOT/file,DELIVERY/file)
    sources=DELIVERY/'source_tools'; sources.mkdir(exist_ok=True)
    for file in Path(__file__).parent.glob('*.py'): shutil.copy2(file,sources/file.name)
    for src in (ROOT/'assets').glob('*/model/*.blend'):
        dst=DELIVERY/src.relative_to(ROOT)
        if hashlib.sha256(src.read_bytes()).digest()!=hashlib.sha256(dst.read_bytes()).digest():
            raise SystemExit('Delivery checksum mismatch: '+str(dst))
    print('DELIVERY_OK',DELIVERY,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--deliver',action='store_true')
    opts=parser.parse_args()
    verify()
    if opts.deliver: deliver()
