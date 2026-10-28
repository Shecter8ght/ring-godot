"""Byte-preserving revision-5 lighting archive and frozen-geometry guard."""
from pathlib import Path
import hashlib,json,shutil,copy,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/screens/dorm'
def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def frozen(plan):
    p=copy.deepcopy(plan)
    for key in ['version','environment','lights','probes']:p.pop(key,None)
    for section in p['sections'].values():
        section.pop('lights',None);section.pop('probes',None)
    for room in p['spaces']:room.pop('lighting_state',None)
    return p
if '--verify' in sys.argv:
    baseline=json.loads((OUT/'light5_archive.json').read_text(encoding='utf-8'))
    plan=json.loads((ROOT/'data/blockouts/dorm.json').read_text(encoding='utf-8'))
    current=hashlib.sha256(json.dumps(frozen(plan),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    assert current==baseline['frozen_plan_sha256'],'Geometry, scale, cameras or base colours changed'
    for row in baseline['files']:assert digest(OUT/row['before'])==row['sha256'],row['before']
    print('FROZEN_PLAN_AND_ARCHIVE_PASS',len(baseline['files']))
else:
    if (OUT/'light5_archive.json').exists():raise RuntimeError('Archive already exists; use --verify')
    rows=[]
    for src in sorted(OUT.glob('light_*')):
        if src.suffix.lower() not in ['.png','.json']:continue
        assert not src.read_bytes().startswith(b'version https://git-lfs.github.com/spec/v1'),'Run git lfs checkout before archiving: '+str(src)
        dst=src.with_name(src.name.replace('light_','light5_',1))
        if dst.exists() and digest(src)!=digest(dst):raise RuntimeError('Existing different archive '+str(dst))
        shutil.copy2(src,dst);assert digest(src)==digest(dst)
        rows.append({'source':src.name,'before':dst.name,'sha256':digest(src),'bytes':src.stat().st_size})
    p=json.loads((ROOT/'data/blockouts/dorm.json').read_text(encoding='utf-8'))
    data={'base_commit':'c374f0dc','files':rows,'frozen_plan_sha256':hashlib.sha256(json.dumps(frozen(p),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
          'shots':p['shots'],'scale':p['scale'],'finish':p['finish']}
    (OUT/'light5_archive.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BYTE_ARCHIVE_CREATED',len(rows),'files')
