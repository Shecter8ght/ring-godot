"""Review packet for task 2; preserve accepted v09 and its exact backup."""
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'_asset_src/grenade_codex/materials_v10_stage2'
BASE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v09_Task1_На_проверку')
DEST=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10_Task2_На_проверку')
NAME='Grenade_MkII_Studio_v10_Task2.blend'
spec=importlib.util.spec_from_file_location('grenade_matched_comparison',ROOT/'tools/package_grenade_surface_v09.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
P.WORK=WORK
P.TITLES={'body':'Корпус — осадок во впадинах и очищаемые выступы',
          'head':'Головка и скоба — защищённые места и локальная пыль',
          'wire':'Кольцо — износ возле реальных контактов'}
P.CROPS={'body':(600,630,1330,1360),'head':(470,480,1300,1290),'wire':(940,270,1620,1170)}
P.LABEL_BEFORE='ДО · принятая v09'
P.LABEL_AFTER='ПОСЛЕ · загрязнения v10'


def seal():
    record=json.loads((WORK/'checks/verify_task2.json').read_text(encoding='utf8'))
    if not record['pass'] or P.sha(DEST/NAME)!=record['sha256']:
        raise RuntimeError('Task 2 verification/model hash mismatch')
    for name in ['grenade_deposit_maps_v10.py','grenade_deposition_v10.py','package_grenade_deposition_v10.py',
                 'grenade_surface_v09.py','package_grenade_surface_v09.py']:
        shutil.copy2(ROOT/'tools'/name,DEST/'source'/name)
    shutil.copy2(WORK/'checks/verify_task2.json',DEST/'checks/verify_task2.json')
    records=[{'file':p.relative_to(DEST).as_posix(),'bytes':p.stat().st_size,'sha256':P.sha(p)}
             for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='file_manifest.json']
    (DEST/'file_manifest.json').write_text(json.dumps({'status':'pending_owner_visual_review','scope':'task_2_only',
                                            'files':records},ensure_ascii=False,indent=2),encoding='utf8')
    backup=json.loads((WORK/'backup_v09/manifest.json').read_text(encoding='utf-8-sig'))
    for key in ['source','backup']:
        if P.sha(Path(backup[key])).lower()!=backup['sha256'].lower():
            raise RuntimeError(('Accepted v09 or backup changed',backup[key]))
    print('TASK2_SEALED',len(records),'V09_UNCHANGED',record['sha256'],flush=True)


def deliver():
    verified=json.loads((WORK/'checks/verify_task2.json').read_text(encoding='utf8'))
    compared=json.loads((WORK/'checks/comparisons_verified.json').read_text(encoding='utf8'))
    if not verified['pass'] or set(compared)!=set(P.TITLES):raise RuntimeError('Verification incomplete')
    if DEST.exists():raise RuntimeError('Refuse to overwrite existing review folder')
    DEST.mkdir(parents=True)
    shutil.copy2(WORK/NAME,DEST/NAME)
    for name in ['textures','comparisons','checks']:
        shutil.copytree(WORK/name,DEST/name)
    shutil.copytree(BASE/'resources',DEST/'resources')
    (DEST/'source').mkdir()
    shutil.copy2(WORK/'asset-state.md',DEST/'asset-state.md')
    shutil.copy2(WORK/'backup_v09/manifest.json',DEST/'checks/backup_manifest.json')
    (DEST/'00_НАЧНИ_ЗДЕСЬ.txt').write_text(
        'v10 на проверку — только задача 2: загрязнения и износ.\n'
        'Открой Grenade_MkII_Studio_v10_Task2.blend в Blender.\n'
        'High Poly и 56 нативных слоёв UCUPaint; принятая фактура v09 сохранена.\n'
        'comparisons: три одинаково освещённые пары v09/v10, PNG16 и JPEG сравнения.\n'
        'Геометрия, риг, маркировка и PBR-значения не редактировались.\n'
        'Задача 3 — только после визуального подтверждения владельца.\n',encoding='utf8')
    seal()


def accept_task1():
    path=BASE/'asset-state.md'
    state=path.read_text(encoding='utf8')
    state=state.replace('Статус: **ожидает визуального подтверждения владельца**. Задачи 2–4 не начаты.',
                        'Статус: **задача 1 принята владельцем** после просмотра сравнений.\n'
                        'Переход к задаче 2 явно разрешён; она выполняется в отдельной v10. Задачи 3–4 ожидают своего этапа.')
    path.write_text(state,encoding='utf8')
    manifest_path=BASE/'file_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    manifest['status']='task_1_accepted_by_owner'
    item=next(x for x in manifest['files'] if x['file']=='asset-state.md')
    item.update(bytes=path.stat().st_size,sha256=P.sha(path))
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print('TASK1_ACCEPTANCE_RECORDED_MODEL_UNCHANGED',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['compare','deliver','seal','accept-task1'])
    parser.add_argument('--shot',choices=list(P.TITLES))
    args=parser.parse_args()
    if args.mode=='compare':P.compare([args.shot] if args.shot else list(P.TITLES))
    elif args.mode=='deliver':deliver()
    elif args.mode=='seal':seal()
    elif args.mode=='accept-task1':accept_task1()


if __name__=='__main__':main()
