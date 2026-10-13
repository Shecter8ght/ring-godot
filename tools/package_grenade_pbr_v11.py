"""Matched review delivery for grenade task 3; retain accepted v10b.

Includes editable native stacks, unchanged external/packed images and recipes.
No material library, Substance migration, gaming bake/export or asset cleanup.
"""
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'_asset_src/grenade_codex/materials_v11_stage3'
BASE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10b_Task2_На_проверку')
DEST=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v11_Task3_На_проверку')
NAME='Grenade_MkII_Studio_v11_Task3.blend'
spec=importlib.util.spec_from_file_location('grenade_pbr_comparison',ROOT/'tools/package_grenade_surface_v09.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
P.WORK=WORK
P.TITLES={'head':'Головка — неметаллический слой окислов над металлическим основанием',
          'lower_lever':'Нижняя часть скобы — потемневший открытый металл',
          'wire':'Кольцо — открытый металл и локальные неметаллические окислы'}
P.CROPS={'head':(470,480,1300,1290),'lower_lever':(700,400,1450,1450),'wire':(940,270,1620,1170)}
P.LABEL_BEFORE='ДО · принятая v10b'
P.LABEL_AFTER='ПОСЛЕ · PBR v11'
SCRIPTS=['grenade_pbr_v11.py','grenade_pbr_metrics_v11.py','package_grenade_pbr_v11.py',
         'grenade_surface_v09.py','grenade_deposition_v10.py','package_grenade_surface_v09.py']


def accept_task2():
    path=BASE/'asset-state.md'
    state=path.read_text(encoding='utf8')
    state=state.replace('Статус: **ожидает визуальной проверки владельца**. Принятые фактуры v09\n'
                        'сохранены; v10 не принята из-за слабой читаемости грязи в углублениях.\n'
                        'Задачи 3–4, библиотека и игровые этапы не начаты.',
                        'Статус: **владелец разрешил переход к задаче 3 после просмотра v10b**.\n'
                        'Плотность грязи пока сохранена; замечание «кажется, что грязи мало» записано.\n'
                        'Принятые фактуры v09 сохранены; PBR-задача 3 выполняется в отдельной v11.\n'
                        'Задача 4, библиотека и игровые этапы не начаты.')
    state=state.replace('Следующий шаг — визуальная проверка читаемости осадка владельцем.\n'
                        'До её подтверждения общая PBR-коррекция задачи 3 не выполняется.',
                        'Следующий этап — отдельно разрешённая PBR-коррекция задачи 3 в v11.\n'
                        'Текущая плотность осадка сохранена; дальнейший объём дефектов требует своего этапа.')
    path.write_text(state,encoding='utf8')
    manifest_path=BASE/'file_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    manifest['status']='task_2_owner_authorized_proceed_to_task_3'
    manifest['owner_note']='Current dirt density retained; owner unsure about quantity but said to continue'
    row=next(x for x in manifest['files'] if x['file']=='asset-state.md')
    row.update(bytes=path.stat().st_size,sha256=P.sha(path))
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print('TASK2_PROCEED_RECORDED_MODEL_UNCHANGED',flush=True)


def deliver():
    checked=json.loads((WORK/'checks/verify_task3.json').read_text(encoding='utf8'))
    compared=json.loads((WORK/'checks/comparisons_verified.json').read_text(encoding='utf8'))
    assert checked['pass'] and P.sha(WORK/NAME)==checked['sha256']
    assert len(checked['verified_changes'])==7 and set(compared)==set(P.TITLES)
    if DEST.exists():raise RuntimeError('Refuse to overwrite an existing review delivery')
    DEST.mkdir(parents=True)
    shutil.copy2(WORK/NAME,DEST/NAME)
    for folder in ['textures','comparisons','checks']:
        shutil.copytree(WORK/folder,DEST/folder)
    shutil.copytree(BASE/'resources',DEST/'resources')
    (DEST/'source').mkdir()
    for name in SCRIPTS:shutil.copy2(ROOT/'tools'/name,DEST/'source'/name)
    shutil.copy2(WORK/'asset-state.md',DEST/'asset-state.md')
    shutil.copy2(WORK/'backup_v10b/manifest.json',DEST/'checks/backup_manifest.json')
    (DEST/'00_НАЧНИ_ЗДЕСЬ.txt').write_text(
        'v11 на проверку — только задача 3, корректировка PBR.\n'
        'Открой Grenade_MkII_Studio_v11_Task3.blend в Blender 5.2.2 + UCUPaint 2.4.9.\n'
        'Семь исправлений Metallic: неметаллические окислы 0, потемневшая открытая скоба 1.\n'
        'Форма, маркировки, 59 слоёв/105 масок, плотность грязи, Roughness и Bump сохранены.\n'
        'comparisons: три пары до/после, PNG16 и подписанные JPEG; одинаковые камера/свет.\n'
        'Исходная v10b и точная резервная копия сохранены.\n'
        'Задача 4 — только после визуального подтверждения владельца.\n',encoding='utf8')
    print('PBR_DELIVERED',DEST,flush=True)


def seal():
    checked=json.loads((WORK/'checks/verify_task3.json').read_text(encoding='utf8'))
    assert checked['pass'] and P.sha(DEST/NAME)==checked['sha256']
    assert Path(checked['file']).resolve()==(DEST/NAME).resolve(), 'Reopen delivered copy first'
    for name in SCRIPTS:shutil.copy2(ROOT/'tools'/name,DEST/'source'/name)
    shutil.copy2(WORK/'checks/verify_task3.json',DEST/'checks/verify_task3.json')
    backup=json.loads((WORK/'backup_v10b/manifest.json').read_text(encoding='utf-8-sig'))
    for key in ['source','backup']:
        assert P.sha(Path(backup[key])).lower()==backup['sha256'].lower()
    rows=[{'file':p.relative_to(DEST).as_posix(),'bytes':p.stat().st_size,'sha256':P.sha(p)}
          for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='file_manifest.json']
    (DEST/'file_manifest.json').write_text(json.dumps({'status':'pending_owner_visual_review',
        'scope':'task_3_pbr_only','files':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print('PBR_SEALED',len(rows),checked['sha256'],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['accept-task2','compare','deliver','seal'])
    args=parser.parse_args()
    if args.mode=='accept-task2':accept_task2()
    elif args.mode=='compare':P.compare(list(P.TITLES))
    elif args.mode=='deliver':deliver()
    elif args.mode=='seal':seal()


if __name__=='__main__':main()
