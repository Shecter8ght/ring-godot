"""Copy only this prop's reviewed source artifacts, checking every delivered byte."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
LIBRARY=Path('E:/Models Blender/PROPS/Padlock_01')
EXPECTED='5BE1E2579133AAC5C8B20ADA9228DD2D31875781B51928EE4CDAC2F1E335CA1C'

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest().upper()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    assert LIBRARY.resolve().parent==Path('E:/Models Blender/PROPS').resolve()
    master=Path('models/padlock_v01_geometry.blend')
    assert digest(WORK/master)==EXPECTED
    if (LIBRARY/master).exists():assert digest(LIBRARY/master)==EXPECTED,'Accepted library master has changed; do not overwrite'
    paths=[Path(s) for s in (
        'asset-state.md','license.txt',
        'models/padlock_v01_geometry.blend','models/padlock_v02_texture_source.blend','models/padlock_v02_textured.blend',
        'painter/padlock_highpoly_uv.fbx','painter/padlock_v02_textured.spp',
        'textures/padlock_paint_mask.png','textures/padlock_stamp_mask.png',
        'checks/audit-config.json','checks/audit-notes.md','checks/audit-report.json',
        'checks/delivery-audit-report.json','checks/skill-audit-unscaled.json','checks/geometry_audit.json',
        'checks/painter_channels.json','checks/painter_reopen.json','checks/texture_verification.json',
        'checks/uv_stats.json','checks/uv_layout.png')]
    for folder,pattern in (('references','*.png'),('previews','*.png'),('textures/export','*.png'),
                           ('textures/sources','*.png'),('textures/sources','*.json')):
        paths.extend(p.relative_to(WORK) for p in (WORK/folder).glob(pattern))
    paths=sorted(set(paths))
    rows=[]
    for rel in paths:
        source=WORK/rel;target=LIBRARY/rel
        assert source.is_file(),str(source)
        assert target.resolve().is_relative_to(LIBRARY.resolve())
        source_hash=digest(source)
        if not args.verify_only:
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or digest(target)!=source_hash:shutil.copy2(source,target)
        assert target.is_file() and digest(target)==source_hash,str(target)
        rows.append({'path':rel.as_posix(),'bytes':target.stat().st_size,'sha256':source_hash})
    report={'status':'PASS','library':str(LIBRARY),'files':rows,
            'accepted_geometry_unchanged':True,'native_painter_layers':18,
            'review_status':'Texture candidate; shape already accepted; game preparation separate'}
    if not args.verify_only:
        data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        (WORK/'checks'/'delivery_manifest.json').write_text(data,encoding='utf-8')
        (LIBRARY/'checks'/'delivery_manifest.json').write_text(data,encoding='utf-8')
    print('PADLOCK_DELIVERY_VERIFIED',len(rows),'files;',round(sum(r['bytes'] for r in rows)/1024**2,1),'MiB;',LIBRARY)

if __name__=='__main__':main()
