"""Attach current working stills/checks and seal a bounded 20% review package."""
from pathlib import Path
import json,shutil,hashlib
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v02';OUT=REV/'delivery'
check=json.loads((REV/'checks/delivery_validation.json').read_text(encoding='utf-8'))
assert check['pass_checks'] and not check['geometry_changes'] and not check['modifier_driver_action_shape_key_changes']
shutil.copy2(REV/'checks/delivery_validation.json',OUT/'04_Проверки/delivery_validation.json')
for key in ('left','right','index','metal'):
    name=f'PM_20_v02_review_{key}_neutral.png';dst=OUT/'04_Проверки'/name;shutil.copy2(REV/'images'/name,dst)
for key,lighting in [('grip','neutral'),('grip','right'),('trigger','right'),('hammer','neutral')]:
    name=f'PM_20_v02_oil_{key}_{lighting}.png';shutil.copy2(REV/'images'/name,OUT/'04_Проверки'/name)
for path in (OUT/'asset-state.json',REV/'texture_state.json'):
    state=json.loads(path.read_text(encoding='utf-8'))
    state['previous_texture_source']=str(ROOT/'candidate/20/PM_Textures_20_v01.blend')
    state['candidate']=str(REV/'candidate/PM_Textures_20_v02.blend')
    path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('package_pm_20_pbr.py','finalize_pm_20_delivery.py','publish_pm_20_pbr.ps1'):
    shutil.copy2(PROJECT/'tools'/name,OUT/'05_Скрипты'/name)
records=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or p.name=='package_manifest.json' or p.suffix in ('.blend1','.blend2'):continue
    records.append(dict(file=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(OUT/'package_manifest.json').write_text(json.dumps(dict(revision='20-v02',conditions=[20],owner_accepted=False,geometry_source_sha256=check['source_sha256'],files=records),ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_20_REVIEW_PACKAGE_SEALED',len(records),'files',sum(r['bytes'] for r in records),'bytes')
