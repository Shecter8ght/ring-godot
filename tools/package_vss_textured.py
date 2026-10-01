"""Архив финальных моделей, слоёв Krita и карт без временных материалов."""
from pathlib import Path
import hashlib,json,zipfile
from import_vss_textured import IDS,RAW

def main():
    files=[RAW/name for name in ('README.md','asset-state.md','license.txt','VSS_Textured_Kit.blend',
        'krita-progress.json','godot_check.json','godot_materials.png',
        'kit_all.png','kit_rifle.png','kit_optics.png','kit_mag_ammo.png')]
    if (RAW/'other-assets-unchanged.json').exists():
        unchanged=json.loads((RAW/'other-assets-unchanged.json').read_text(encoding='utf8'))
        if unchanged['status']!='PASS':raise ValueError('Other assets changed')
        files.append(RAW/'other-assets-unchanged.json')
    for identifier in IDS:
        folder=RAW/identifier
        report=json.loads((folder/'texturing-report.json').read_text(encoding='utf8'))
        if report['status']!='PASS':raise ValueError('Unverified asset: '+identifier)
        glb=folder/(identifier+'.glb')
        if hashlib.sha256(glb.read_bytes()).hexdigest()!=report['glb_sha256']:raise ValueError('Stale report: '+identifier)
        files.extend((glb,folder/(identifier+'_Textured.blend'),folder/'texturing-report.json'))
        for atlas in report['atlas_objects']:
            atlas_folder=folder/atlas
            krita=json.loads((atlas_folder/'krita-report.json').read_text(encoding='utf8'))
            if krita['status']!='PASS':raise ValueError('Unverified Krita source')
            kra=atlas_folder/'Textures.kra'
            with zipfile.ZipFile(kra) as source:
                if source.read('mimetype').strip()!=b'application/x-krita':raise ValueError('Invalid KRA')
            files.extend(atlas_folder/name for name in ('Textures.kra','basecolor.png','orm.png','normal.png','krita-report.json'))
    rifle=RAW/'VSS_Vintorez_Picatinny'
    files.extend(rifle/name for name in ('VSS_Vintorez_Picatinny_Textured_Editable.blend',
        'parts-transfer.json','editable-reopen-check.json','editable_reopened_beauty.png','editable_reopened_receiver.png'))
    if (rifle/'shoulder-audit.json').exists():
        audit=json.loads((rifle/'shoulder-audit.json').read_text(encoding='utf8'))
        native=json.loads((rifle/'texturing-report.json').read_text(encoding='utf8'))
        if audit['status']!='PASS' or audit['source_sha256']!=native['source_sha256']:raise ValueError('Stale shoulder audit')
        files.extend(rifle/name for name in ('shoulder-audit.json','geometry-change.json',
            'editable_reopened_shoulder_profile.png','editable_reopened_shoulder_rear.png','editable_reopened_shoulder_fit.png'))
    if (rifle/'current-export-map-check.json').exists():
        maps=json.loads((rifle/'current-export-map-check.json').read_text(encoding='utf8'))
        if maps['status']!='PASS' or maps['glb_sha256']!=hashlib.sha256((rifle/'VSS_Vintorez_Picatinny.glb').read_bytes()).hexdigest():raise ValueError('Stale map verification')
        for item in maps['maps']:
            path=rifle/item['atlas']/(item['map']+'.png')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['current_png_sha256']:raise ValueError('Changed Krita map')
        files.append(rifle/'current-export-map-check.json')
    paths=sorted(set(files))
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(RAW.resolve()):raise ValueError('Invalid source: '+str(path))
    manifest={'files':[{'path':path.relative_to(RAW).as_posix(),'bytes':path.stat().st_size,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]}
    manifest_path=RAW/'delivery-manifest.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    paths.append(manifest_path)
    pending=RAW/'VSS_Textured_Kit.pending.zip'; destination=RAW/'VSS_Textured_Kit.zip'
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for path in paths:
            compression=zipfile.ZIP_STORED if path.suffix.lower() in {'.png','.kra','.glb'} else zipfile.ZIP_DEFLATED
            archive.write(path,path.relative_to(RAW).as_posix(),compress_type=compression)
    with zipfile.ZipFile(pending) as archive:
        bad=archive.testzip()
        if bad:raise ValueError('Archive CRC mismatch: '+bad)
    pending.replace(destination)
    print(json.dumps({'status':'PASS','files':len(paths),'archive':str(destination),'bytes':destination.stat().st_size},ensure_ascii=False))

if __name__=='__main__':main()
