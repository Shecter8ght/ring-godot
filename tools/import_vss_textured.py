"""Перенос проверенного текстурного комплекта Krita из сырья в assets."""
from pathlib import Path
import hashlib,json,shutil,struct
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_textured'
DEST=ROOT/'assets/models/weapons/vss_textured'
IDS=('VSS_Vintorez_Picatinny','PSO_VSS_4x24','Rail_4x32','Magazine_939_10_Empty','Magazine_939_10_Loaded','Cartridge_939_SP5')
CREDIT='''<!-- VSS_TEXTURES_START -->
## Текстурный комплект ВСС — Krita

- `assets/models/weapons/vss_textured/` — отдельная текстурная версия собственной ВСС с верхней планкой, двух прицелов, пустого/снаряжённого магазина и СП-5. Геометрия и происхождение — собственные модели, описанные выше; старые исходники сохранены.
- Собственные карты: продольный рисунок дерева, покрытие, микрофактура, контактный износ, загрязнения, шероховатость, металлические участки и локальный AO. UV-маски и baking подготовлены в Blender; финальные слоистые `.kra`, композит и PNG выполнены установленной Krita 5.3.4. Текстуры игр и пиксели чужих фотографий не копировались. Все карты созданы для владельца проекта и разрешены для использования вместе с моделями.
- Винтовка: два атласа basecolor/ORM/OpenGL normal 4096². Остальные предметы: по одному атласу 2048²; стекло прицелов отдельно. ORM: R — локальный AO, G — roughness, B — metallic. Исходники `.kra`/`.blend` и отчёты — `_asset_src/vss_textured/`; `tools/prepare_vss_texturing.py`, `paint_vss_texture_layers.py`, `bake_vss_texture_ao.py`, `merge_vss_texture_ao.py`, `finish_vss_in_krita.ps1`, `apply_vss_krita_textures.py`, `import_vss_textured.py`.
<!-- VSS_TEXTURES_END -->'''

def glb_json(path):
    data=path.read_bytes();magic,version,length=struct.unpack_from('<4sII',data)
    if magic!=b'glTF' or version!=2 or length!=len(data):raise ValueError('Invalid GLB')
    count,kind=struct.unpack_from('<II',data,12)
    if kind!=0x4e4f534a:raise ValueError('Missing GLB JSON')
    return json.loads(data[20:20+count])

def main():
    if not (RAW/'license.txt').is_file():raise ValueError('No license')
    manifest=[]
    for identifier in IDS:
        folder=RAW/identifier;report=json.loads((folder/'texturing-report.json').read_text());file=folder/(identifier+'.glb')
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if report['status']!='PASS' or report['glb_sha256']!=digest or not report['source_unchanged']:raise ValueError('Not verified: '+identifier)
        if hashlib.sha256(Path(report['source']).read_bytes()).hexdigest()!=report['source_sha256']:raise ValueError('Changed native model')
        doc=glb_json(file);triangles=sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives'])
        if triangles!=report['triangles']:raise ValueError('Changed triangle budget')
        expected=6 if identifier=='VSS_Vintorez_Picatinny' else 3
        if len(doc['images'])!=expected or any('bufferView' not in im for im in doc['images']):raise ValueError('Textures not embedded')
        for material in doc['materials']:
            if material.get('alphaMode')=='BLEND':continue
            if not all(name in material for name in ('normalTexture','occlusionTexture')):raise ValueError('Missing PBR data')
            if 'metallicRoughnessTexture' not in material['pbrMetallicRoughness']:raise ValueError('Missing ORM')
        if identifier.startswith(('PSO','Rail')) and not any(m.get('alphaMode')=='BLEND' for m in doc['materials']):raise ValueError('Lost lens alpha')
        for atlas in report['atlas_objects']:
            krita=json.loads((folder/atlas/'krita-report.json').read_text())
            if krita['status']!='PASS' or len(krita['groups'])<4 or not (folder/atlas/'Textures.kra').is_file():raise ValueError('No editable Krita source')
        manifest.append({'id':identifier,'sha256':digest,'triangles':triangles,
            'game_axes':'+Z forward, +Y up, -X right','dimensions_blender_game_mm':report['bounds']['dimensions_mm'],
            'surfaces':len(doc['materials']),'atlases':report['atlas_objects'],
            'resolution':4096 if identifier=='VSS_Vintorez_Picatinny' else 2048,
            'orm':'R local cavity AO, G roughness, B metallic','authoring':'Blender UV/baking; Krita 5.3.4 layered KRA/compositing/PNG'})
    DEST.mkdir(parents=True,exist_ok=True)
    for item in manifest:shutil.copy2(RAW/item['id']/(item['id']+'.glb'),DEST/(item['id']+'.glb'))
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    credits=ROOT/'assets/CREDITS.md';text=credits.read_text(encoding='utf-8')
    start,end='<!-- VSS_TEXTURES_START -->','<!-- VSS_TEXTURES_END -->'
    if start in text:
        before,rest=text.split(start,1);_,after=rest.split(end,1);text=before.rstrip()+'\n\n'+CREDIT+after
    else:text=text.rstrip()+'\n\n'+CREDIT+'\n'
    credits.write_text(text,encoding='utf-8')
    print(json.dumps({'status':'PASS','assets':len(manifest),'destination':str(DEST)}))
if __name__=='__main__':main()
