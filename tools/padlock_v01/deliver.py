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
    parser.add_argument('--revision',choices=['v02','v03','v04','v05'],default='v02')
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
    if args.revision in {'v03','v04','v05'}:
        paths.extend(Path(s) for s in (
            'models/padlock_v03_textured.blend','painter/padlock_v03_textured.spp',
            'checks/contacts_v03.json','checks/v03_baseline.json','checks/refinement_v03.json',
            'checks/painter_reopen_v03.json','checks/texture_verification_v03.json',
            'textures/sources/contact_edge.png'))
        paths.extend(p.relative_to(WORK) for p in (WORK/'textures'/'export_v03').glob('*.png'))
        paths.extend(p.relative_to(WORK) for p in (WORK/'textures'/'contact_v03').glob('*.png'))
        paths.append(Path('textures/contact_v03/sources.json'))
        if (WORK/'models'/'padlock_v03_studio.blend').exists():
            paths.extend((Path('models/padlock_v03_studio.blend'),Path('checks/studio_v03.json')))
        baseline=json.loads((WORK/'checks'/'v03_baseline.json').read_text(encoding='utf-8'))
        for rel,checksum in baseline.items():
            assert digest(WORK/rel).lower()==checksum
            if (LIBRARY/rel).exists():assert digest(LIBRARY/rel).lower()==checksum,'Previous library version changed: '+rel
    if args.revision in {'v04','v05'}:
        paths.extend(Path(s) for s in (
            'models/padlock_v04_textured.blend','models/padlock_v04_studio.blend',
            'painter/padlock_v04_textured.spp','checks/contacts_v04.json',
            'checks/v04_baseline.json','checks/refinement_v04.json','checks/painter_v04_channels.json',
            'checks/painter_reopen_v04.json','checks/texture_verification_v04.json',
            'checks/studio_v04.json','textures/contact_v04/sources.json'))
        for folder in ('export_v04','contact_v04'):
            paths.extend(p.relative_to(WORK) for p in (WORK/'textures'/folder).glob('*.png'))
        baseline=json.loads((WORK/'checks'/'v04_baseline.json').read_text(encoding='utf-8'))
        for rel,checksum in baseline.items():
            assert digest(WORK/rel).lower()==checksum,'Previous work version changed: '+rel
            if (LIBRARY/rel).exists():assert digest(LIBRARY/rel).lower()==checksum,'Previous library version changed: '+rel
    if args.revision=='v05':
        paths.extend(Path(s) for s in (
            'models/padlock_v05_textured.blend','models/padlock_v05_studio.blend','painter/padlock_v05_textured.spp',
            'checks/v05_baseline.json','checks/v05_fields.json','checks/v05_native_layers.json',
            'checks/painter_reopen_v05.json','checks/painter_v05_channels.json','checks/texture_verification_v05.json',
            'checks/studio_v05.json','checks/studio_eevee_v05_074.png','checks/review_v05/report.txt','checks/review_v05/maps/maps.json',
            'checks/review_v05/maps/maps.txt','checks/review_v05/render/render.json',
            'checks/review_v05/render/render.txt','textures/authored_v05/layout.json','textures/authored_v05/sources.json'))
        for folder in ('export_v05','authored_v05','fields_v05'):
            paths.extend(p.relative_to(WORK) for p in (WORK/'textures'/folder).glob('*.png'))
        paths.extend(p.relative_to(WORK) for p in (WORK/'textures'/'authored_v05').glob('*.svg'))
        for folder in ('maps','render'):
            paths.extend(p.relative_to(WORK) for p in (WORK/'checks'/'review_v05'/folder).glob('*.png'))
        baseline=json.loads((WORK/'checks'/'v05_baseline.json').read_text(encoding='utf-8'))
        for rel,checksum in baseline.items():
            assert digest(WORK/rel).lower()==checksum,'Previous work version changed: '+rel
            if (LIBRARY/rel).exists():assert digest(LIBRARY/rel).lower()==checksum,'Previous library version changed: '+rel
    for folder,pattern in (('references','*.png'),('previews','*.png'),('textures/export','*.png'),
                           ('textures/sources','*.png'),('textures/sources','*.json')):
        paths.extend(p.relative_to(WORK) for p in (WORK/folder).glob(pattern) if '_probe' not in p.stem)
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
            'accepted_geometry_unchanged':True,'native_painter_layers':{'v02':18,'v03':25,'v04':37,'v05':61}[args.revision],
            'review_status':'Texture candidate; shape already accepted; game preparation separate'}
    if args.revision=='v05':
        report['native_painter_counts']={'fills':60,'paint':1,'groups':3,'hierarchical_nodes':64,
                                         'root_entries':38,'anchors':4,'references':11}
    if not args.verify_only:
        data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        manifest='delivery_manifest.json' if args.revision=='v02' else 'delivery_manifest_'+args.revision+'.json'
        (WORK/'checks'/manifest).write_text(data,encoding='utf-8')
        (LIBRARY/'checks'/manifest).write_text(data,encoding='utf-8')
    print('PADLOCK_DELIVERY_VERIFIED',len(rows),'files;',round(sum(r['bytes'] for r in rows)/1024**2,1),'MiB;',LIBRARY)

if __name__=='__main__':main()
