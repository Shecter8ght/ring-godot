"""Two matched body comparisons and portable task-2 correction candidate.

No galleries, video, asset export, deletions or replacement of v10/v09 files.
"""
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_asset_src/grenade_codex/materials_v10b_stage2_recess'
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10_Task2_На_проверку')
DEST = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10b_Task2_На_проверку')
NAME = 'Grenade_MkII_Studio_v10b_Task2.blend'
spec = importlib.util.spec_from_file_location('grenade_recess_matched_comparison',ROOT/'tools/package_grenade_surface_v09.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
P.WORK = WORK
P.TITLES = {'body':'Корпус — накопление осадка в горизонтальных и вертикальных желобах',
            'macro':'Макро — пылевая плёнка, уплотнённые участки и отдельные частицы'}
P.CROPS = {'body':(600,630,1330,1360),'macro':(450,600,1350,1450)}
P.LABEL_BEFORE = 'ДО · v10, слабый осадок'
P.LABEL_AFTER = 'ПОСЛЕ · исправленная v10b'
SCRIPTS = ['grenade_recess_grains_v10b.py','grenade_recess_deposits_v10b.py',
           'package_grenade_recess_v10b.py','grenade_deposition_v10.py',
           'grenade_surface_v09.py','package_grenade_surface_v09.py']


def seal():
    checked = json.loads((WORK/'checks/verify_task2_correction.json').read_text(encoding='utf8'))
    assert checked['pass'] and P.sha(DEST/NAME)==checked['sha256']
    assert Path(checked['file']).resolve()==(DEST/NAME).resolve(), 'Reopen delivered copy before sealing'
    for name in SCRIPTS:
        shutil.copy2(ROOT/'tools'/name,DEST/'source'/name)
    shutil.copy2(WORK/'checks/verify_task2_correction.json',DEST/'checks/verify_task2_correction.json')
    backup = json.loads((WORK/'backup_v10/manifest.json').read_text(encoding='utf-8-sig'))
    for key in ['source','backup']:
        assert P.sha(Path(backup[key])).lower()==backup['sha256'].lower(), 'Original v10 or exact backup changed'
    # Original v09 task 1 remains the accepted factory surface source.
    accepted = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v09_Task1_На_проверку/Grenade_MkII_Studio_v09_Task1.blend')
    assert P.sha(accepted)=='8d214db0f8dcf13e167e5d8c61fda797910b2cae1870305e9b9a5dc3c7723aad'
    rows = [{'file':p.relative_to(DEST).as_posix(),'bytes':p.stat().st_size,'sha256':P.sha(p)}
            for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='file_manifest.json']
    (DEST/'file_manifest.json').write_text(json.dumps({'status':'pending_owner_visual_review',
        'scope':'task_2_recess_deposition_correction_only','files':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print('RECESS_CORRECTION_SEALED',len(rows),checked['sha256'],flush=True)


def deliver():
    checked = json.loads((WORK/'checks/verify_task2_correction.json').read_text(encoding='utf8'))
    compared = json.loads((WORK/'checks/comparisons_verified.json').read_text(encoding='utf8'))
    assert checked['pass'] and P.sha(WORK/NAME)==checked['sha256']
    assert set(compared)==set(P.TITLES)
    if DEST.exists():
        raise RuntimeError('Refuse to overwrite an existing review folder')
    DEST.mkdir(parents=True)
    shutil.copy2(WORK/NAME,DEST/NAME)
    for folder in ['textures','comparisons','checks']:
        shutil.copytree(WORK/folder,DEST/folder)
    shutil.copytree(BASE/'resources',DEST/'resources')
    shutil.copy2(WORK/'asset-state.md',DEST/'asset-state.md')
    shutil.copy2(WORK/'backup_v10/manifest.json',DEST/'checks/backup_manifest.json')
    (DEST/'source').mkdir()
    for name in SCRIPTS:
        shutil.copy2(ROOT/'tools'/name,DEST/'source'/name)
    shutil.copy2('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts/ucupaint_helpers.py',
                 DEST/'source/ucupaint_helpers.py')
    (DEST/'00_НАЧНИ_ЗДЕСЬ.txt').write_text(
        'v10b — исправление задачи 2, ожидает визуальной проверки владельца.\n'
        'Открой Grenade_MkII_Studio_v10b_Task2.blend в Blender 5.2.2 + UCUPaint 2.4.9.\n'
        'В углублениях корпуса добавлены отдельные слои сухого осадка, уплотнённой грязи и частиц.\n'
        'Прежние 56 слоёв и 97 масок сохранены; новые слои сверху можно отключить для сравнения.\n'
        'comparisons: две пары до/после, PNG16 и подписанные JPEG, одинаковые камера/свет/экспозиция.\n'
        'Рецепты в source — копии рабочих tools проекта RING, не отдельная универсальная библиотека.\n'
        'Задача 3 не выполнялась и требует отдельного визуального подтверждения.\n',encoding='utf8')
    print('RECESS_CORRECTION_DELIVERED',DEST,flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['compare','deliver','seal'])
    args = parser.parse_args()
    if args.mode=='compare':P.compare(list(P.TITLES))
    elif args.mode=='deliver':deliver()
    elif args.mode=='seal':seal()


if __name__=='__main__':
    main()
