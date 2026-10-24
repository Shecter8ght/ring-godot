"""Финальная сверка каталога без изменения проверенных Blender-файлов."""
from pathlib import Path
import json
import re
import shutil
from PIL import Image

from plan import ROOT, DELIVERY, sha
from delivery import prepare_package, read, write


def main():
    manifest=prepare_package()
    summary=read(DELIVERY/'checks/delivery_summary.json')
    assert summary['all_101_passed'] and summary['all_reopened_from_delivery']
    proof={a['id']:a for a in summary['results']}
    for a in manifest['assets']:
        assert proof[a['id']]['sha256']==a['blend_sha256']==sha(DELIVERY/a['model']),a['id']
        assert sha(a['source_blend'])==a['source_sha256'],a['id']
        for view in a['previews']:
            with Image.open(DELIVERY/view) as image:
                image.verify()
        assert (DELIVERY/a['reference']).is_file()
        for name in ('asset-state.md',):
            shutil.copy2(ROOT/'assets'/a['folder']/name,DELIVERY/'assets'/a['folder']/name)
    sources=read(ROOT/'sources.json')
    next(s for s in sources if s['id']=='original_graphics')['operation']='Code-authored fictional LCD/poster/sign typography and technical glass perimeter mask; no copied brand graphics'
    for root in (ROOT,DELIVERY):
        write(root/'sources.json',sources)
    write(ROOT/'checks/delivery_summary.json',summary)
    review=read(ROOT/'checks/visual_review.json')
    assert set(review['reviewed_front_views'])==set(proof)
    for a in manifest['assets']:
        r=read(DELIVERY/'assets'/a['folder']/'checks/delivery_validation.json')
        r['front_view_reviewed']=True
        if a['id'] in ('U13_02','U15_02'):
            r['preserved_geometry_note']=next(x['note'] for x in review['preserved_source_geometry_notes'] if x['id']==a['id'])
        write(DELIVERY/'assets'/a['folder']/'checks/delivery_validation.json',r)
    manifest['verification']={k:v for k,v in summary.items() if k!='results'}
    manifest['visual_review']='checks/visual_review.json'
    for root in (ROOT,DELIVERY):
        write(root/'manifest.json',manifest)
    shutil.copy2(ROOT/'checks/visual_review.json',DELIVERY/'checks/visual_review.json')
    text=(ROOT/'README.md').read_text(encoding='utf-8')
    text+='\n## Проверенный комплект\n\n'
    text+=f'{summary["models"]} файлов повторно открыты из этой папки: {summary["native_materials"]} материалов, '
    text+=f'{summary["native_layers"]} слоёв UCUPaint; {summary["geometry_objects_checked"]} объектов сверено с исходниками. '
    text+='Все встроенные изображения и внешние копии проверены по хешам. [Визуальная проверка](checks/visual_review.json).\n\n'
    text+='Старые формы U13_02 (медицинская ширма, разнесённые ролики) и U15_02 (светофор, отдельный верхний блок) '
    text+='сохранены как в исходниках; их доработка относится к геометрии. Версии R01–R05 предпочтительны для пяти переделанных предметов.\n'
    for root in (ROOT,DELIVERY):
        (root/'README.md').write_text(text,encoding='utf-8')
    for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',text):
        assert (DELIVERY/target).is_file(),(label,target)
    scripts=DELIVERY/'source'
    for path in Path(__file__).parent.glob('*.py'):
        shutil.copy2(path,scripts/path.name)
    stats=dict(models=101,native_materials=summary['native_materials'],native_layers=summary['native_layers'],
        packed_image_datablocks=summary['packed_image_datablocks'],
        files=sum(1 for f in DELIVERY.rglob('*') if f.is_file()),
        bytes=sum(f.stat().st_size for f in DELIVERY.rglob('*') if f.is_file()),
        png_views=len(list((DELIVERY/'assets').glob('*/previews/*.png'))),
        models_hash_verified=True,original_geometry_sources_unchanged=True,catalog_links_verified=True,
        visual_review_count=len(review['reviewed_front_views']),game_export=False,texture_approved=False)
    write(DELIVERY/'checks/package.json',stats)
    write(ROOT/'checks/package.json',stats)
    print('URBAN_PBR_FINALIZED',json.dumps(stats),flush=True)


if __name__=='__main__':
    main()
