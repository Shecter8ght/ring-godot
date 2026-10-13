"""Portable final native/PBR review package on the explicitly approved v05 geometry."""
import hashlib
import json
import re
import shutil
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex'
STAGE=OUT/'texture_delivery_v06'
TARGET=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v06')
MASTER='Grenade_MkII_UCUPaint_Codex_v06.blend'
PREVIEW='Grenade_MkII_PBR_Preview_v06.blend'
STUDIO='Grenade_MkII_Studio_v06.blend'
STUDIO_VIEWS=[('01_hero','Студийный портрет'),('02_landscape','Общий студийный вид'),
              ('03_head_and_mark','Металл головки и рычага'),('04_cast_detail','Литьё и износ краски'),
              ('05_sun_slnshk','Солнышко и СЛНШК'),('06_reverse_portrait','Обратная сторона'),
              ('07_low_angle','Низкий ракурс'),('08_split_pin_detail','Отверстие и раздельные концы'),
              ('09_visual_motion','Визуальная демонстрация движения'),('10_opposite_profile','Боковой портрет')]
VIEWS=[('01_textured_overall','Общий вид'),('02_textured_other_side','Обратная сторона'),
       ('03_cast_and_wear','Литьё и местами протёртая краска'),('04_head_ring_marking','Головка, кольцо и маркировка'),
       ('05_lever_surface','Обработка и износ рычага'),('06_pin_separate_lever_held','Чека отдельно'),
       ('07_lever_outward','Рычаг отведён'),('08_bottom','Дно и пробка'),
       ('09_sun_slnshk_top','Солнышко + СЛНШК'),('10_real_hole_and_split_tips','Отверстие и раздвоенные концы'),
       ('11_size_front','Размер'),('12_baked_comparison','Запечённые PBR карты'),
       ('13_baked_head_comparison','Запечённая головка крупно')]


def copy_file(source,relative):
    dest=STAGE/relative
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def write_manifest(folder):
    rows=[{'file':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
          for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json']
    (folder/'delivery_manifest.json').write_text(json.dumps({'version':'v06','files':rows},indent=2),encoding='utf8')


def validate(folder):
    manifest=json.loads((folder/'delivery_manifest.json').read_text(encoding='utf8'))
    for row in manifest['files']:
        path=folder/row['file']
        assert path.is_file() and path.stat().st_size==row['bytes'],row['file']
        assert sha(path)==row['sha256'],row['file']
    html=(folder/'gallery.html').read_text(encoding='utf8')
    for name in re.findall(r'(?:src|href)="([^"]+)"',html):
        if not name.startswith(('https://','http://','#','data:')):
            assert (folder/name).is_file(),name
    print('PACKAGE_V06_VALIDATED',str(folder),len(manifest['files']),flush=True)


def package():
    audit=json.loads((OUT/'checks/fresh_reopen_audit_v06.json').read_text(encoding='utf8'))
    maps=json.loads((OUT/'textures/pbr_v06/manifest.json').read_text(encoding='utf8'))
    assert audit['pass'] and audit['approved_geometry']=='v05' and len(maps)==16
    assert sum(len(m['layers']) for m in audit['materials'])==64
    STAGE.mkdir(parents=True,exist_ok=True)
    for name in [MASTER,PREVIEW,STUDIO]:
        copy_file(OUT/name,name)
    # Only actually used source maps are required beside the self-contained blend.
    for row in audit['images']:
        relative=Path(row['path'][2:].replace('\\','/'))
        assert relative.is_relative_to('textures'),relative
        copy_file(OUT/relative,relative)
    copy_file(OUT/'textures/pbr_v06/manifest.json','textures/pbr_v06/manifest.json')
    for row in maps:
        with (STAGE/'textures/pbr_v06'/row['file']).open('rb') as stream:
            data=stream.read(26)
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and data[24]==16,row['file']
        assert list(struct.unpack('>II',data[16:24]))==row['size'],row['file']
    for path in [OUT/'textures/cc0_sources/manifest.json',OUT/'textures/cc0_sources/ambientCG_license.html']:
        copy_file(path,Path('licenses')/path.name)
    for asset in ['Metal049C','Metal009','Metal063']:
        for name in ['metadata.json','provenance.json']:
            copy_file(OUT/'textures/cc0_sources'/asset/name,Path('licenses')/asset/name)
    for name in ['manifest.json','pitting_manifest_v06.json','marking_manifest_v06.json']:
        path=OUT/'textures/authoring'/name
        if path.exists(): copy_file(path,Path('textures/authoring')/name)
    copy_file(OUT/'textures/sources/LICENSE.md','licenses/Fingerprints003/LICENSE.md')
    copy_file(OUT/'textures/sources/Fingerprints003_4K-PNG_Opacity.png',
              'textures/sources/Fingerprints003_4K-PNG_Opacity.png')
    for name in ['geometry_approved_v05.json','geometry_delivery_audit_v05.json',
                 'fresh_reopen_audit_v06.json','preview_reopen_audit_v06.json',
                 'measurements_and_topology_v06.json','pbr_png_encoding_v06.json',
                 'size_annotation_points_v06.json','native_baked_comparison_v06.json','video_validation_v06.json',
                 'studio_setup_v06.json','studio_reopen_audit_v06.json','studio_renders_v06.json',
                 'map_space_repair_v06.json','investor_screens_v06.json']:
        copy_file(OUT/'checks'/name,Path('checks')/name)
    for folder in ['owner','owner_latest']:
        for p in (OUT/'references'/folder).glob('*'):
            if p.is_file():copy_file(p,Path('references')/folder/p.name)
    for name,title in VIEWS:
        copy_file(OUT/'previews'/(name+'.png'),Path('previews')/(name+'.png'))
    for name,title in STUDIO_VIEWS:
        copy_file(OUT/'previews/studio'/(name+'.png'),Path('previews/studio')/(name+'.png'))
    for path in (OUT/'Investor_Shots').glob('*'):
        if path.is_file():copy_file(path,Path('Investor_Shots')/path.name)
    copy_file(OUT/'Grenade_Investor_10_Shots_v06.zip','Grenade_Investor_10_Shots_v06.zip')
    copy_file(OUT/'Investor_Contact_Sheet_v06.jpg','Investor_Contact_Sheet_v06.jpg')
    copy_file(OUT/'previews/pin_lever_demo_v06.mp4','previews/pin_lever_demo_v06.mp4')
    for script in ['texture_grenade_codex.py','bake_grenade_codex.py','review_grenade_codex.py',
                   'studio_grenade_codex.py','check_grenade_codex_outputs.py',
                   'fix_grenade_codex_map_spaces.py','package_grenade_codex_v06.py',
                   'package_grenade_codex_investor.py','open_grenade_codex.py',
                   'fetch_grenade_codex_materials.py','grenade_codex_masks.py',
                   'grenade_codex_marking.py','grenade_codex_pitting_masks.py',
                   'grenade_codex_blender.py','texture_flare_pistol_codex.py']:
        copy_file(ROOT/'tools'/script,Path('scripts')/script)
    helper=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts/ucupaint_helpers.py')
    copy_file(helper,'scripts/ucupaint_helpers.py')
    for name in ['bake_resume_v06.log','final_technical_renders_v06.log','animation_v06.log',
                 'studio_final_build_v06.log','investor_final_renders_v06.log']:
        copy_file(OUT/name,Path('logs')/name)
    points=json.loads((OUT/'checks/size_annotation_points_v06.json').read_text(encoding='utf8'))
    x,bottom=points['height_bottom'];_,top=points['height_top'];left,baseline=points['body_left'];right,_=points['body_right']
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="2200"><image href="11_size_front.png" width="1800" height="2200"/><g stroke="#ffda8b" stroke-width="3" fill="none"><path d="M{x-20} {top}h45 M{x-20} {bottom}h45 M{x} {top}V{bottom}"/><path d="M{left} {baseline-20}v40 M{right} {baseline-20}v40 M{left} {baseline}H{right}"/></g><g fill="#ffda8b" font-family="Arial" font-size="36"><text x="{x+25}" y="{(top+bottom)/2}">114,51 мм</text><text x="{(left+right)/2}" y="{baseline+63}" text-anchor="middle">Корпус Ø63,40 мм</text></g></svg>'''
    (STAGE/'previews/size_annotated.svg').write_text(svg,encoding='utf8')
    readme=f'''# Граната — текстуры v06 на принятой геометрии v05

Откройте {STUDIO} для готовой сцены с пятью источниками света,
графитовым фоном и тёмной подставкой. F12 — финальный рендер портрета.
Investor_Shots — 10 JPEG высокого качества для презентации; ZIP рядом.
previews/studio — 10 исходных PNG 16 bit до 4000 пикселей; все без шумоподавления
и размытия глубины резкости, чтобы сохранить мелкую фактуру.

Откройте {MASTER} для редактирования 64 настоящих слоёв UCUPaint 2.4.9.
{PREVIEW} использует запечённые PBR карты для быстрого просмотра.
gallery.html — общие виды, крупные планы, размеры и видео движения.

Корпус Ø63,40 мм; общая высота 114,51 мм. 1 единица = 1 метр, отображение в мм.
Принятая геометрия, исходная UVMap корпуса, модификаторы и shape keys сохранены.

16 PNG 16 bit: корпус, головка и рычаг 8K; проволочные детали 4K.
BaseColor — sRGB, Metallic/Roughness/NormalGL — Non-Color. Уникальная развёртка PBRUV.
Все {len(audit['images'])} изображения встроены в три blend; внешние копии лежат рядом.
Головка имеет чёткое зерно и раковины; корпус — округлённые выемки, протёртую краску,
жёлтую полосу и красную линию. На рычаге тёмное солнышко и точная кириллица СЛНШК.

CTRL_Grenade: pin_pull и lever_open, 0–1. Для ползунков отвяжите Action от корня.
Таймлайн 1–96 при 24 fps: чека и кольцо отдельно, рычаг отведён и возвращён.
Два кончика чеки сжимаются в начале тяги и расходятся снаружи. Отверстие настоящее.

Материалы: ambientCG Metal049C/Metal009/Metal063/Fingerprints003, CC0 1.0.
Референсы владельца не проектировались в текстуры. Свои маски и маркировка оригинальны.
licenses и checks содержат происхождение и проверки. Оригинальный Grenade.blend сохранён.
scripts и logs сохраняют рецепт работы; пути скриптов рассчитаны на исходный проект RING.
'''
    (STAGE/'00_НАЧНИ_ЗДЕСЬ.md').write_text(readme,encoding='utf8')
    state={'geometry':'v05 explicitly approved by owner','textures':'v06 prepared for owner review',
        'approval_reply':'Да, v05 принята — делай текстуры','units':'metres, display mm',
        'dimensions_mm':[66.7994879186,63.4011887014,114.5109032514],
        'source_sha256':audit['source_sha256'],'approved_geometry_sha256':audit['approved_file_sha256'],
        'native_stacks':4,'native_layers':64,'packed_images':len(audit['images']),
        'pbr_maps':16,'game_export':False,'version':'v06','studio_file':STUDIO,
        'studio_lights':5,'studio_shots':10,'texture_approval':'prepared for owner review'}
    (STAGE/'asset-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
    cards=''.join(f'<figure><a href="previews/{n}.png"><img loading="lazy" src="previews/{n}.png"></a><figcaption>{title}</figcaption></figure>' for n,title in VIEWS)
    studio_cards=''.join(f'<figure><a href="previews/studio/{n}.png"><img loading="lazy" src="Investor_Shots/{n}.jpg"></a><figcaption>{title}</figcaption></figure>' for n,title in STUDIO_VIEWS)
    html=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Граната · текстуры v06</title><style>body{{margin:0;background:#151b20;color:#e6e8ec;font:17px/1.55 Arial}}main{{max-width:1400px;margin:auto;padding:30px}}h1{{font-size:34px}}a{{color:#efd59b}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:24px}}figure{{margin:0;background:#212830;border-radius:10px;overflow:hidden}}img{{width:100%;display:block}}figcaption{{padding:12px}}video{{width:100%;max-width:900px}}.note{{color:#b6bfc7}}</style><main><h1>Граната · текстуры v06</h1><p>Принятая геометрия v05 · корпус Ø63,40 мм · высота 114,51 мм</p><p>64 редактируемых слоя UCUPaint. Карты корпуса, головки и рычага 8K, проволочных деталей 4K, PNG 16 bit. Крупные виды без шумоподавления.</p><p><a href="{MASTER}">Мастер UCUPaint</a> · <a href="{PREVIEW}">Быстрое PBR превью</a> · <a href="00_НАЧНИ_ЗДЕСЬ.md">Памятка</a> · <a href="asset-state.json">Состояние</a> · <a href="previews/size_annotated.svg">Размеры на изображении</a></p><video controls preload="metadata" poster="previews/01_textured_overall.png" src="previews/pin_lever_demo_v06.mp4"></video><p class="note">Внешняя визуальная анимация; кадры 1–96, 24 fps. Нажмите изображение для полного разрешения.</p><div class="grid">{cards}</div><p>CC0 материалы: <a href="https://ambientcg.com/view?id=Metal049C">Metal049C</a>, <a href="https://ambientcg.com/view?id=Metal009">Metal009</a>, <a href="https://ambientcg.com/view?id=Metal063">Metal063</a>. Исходная модель и принятая v05 сохранены отдельно.</p></main></html>'''
    html=html.replace(f'<a href="{MASTER}">Мастер UCUPaint</a>',f'<a href="{STUDIO}">Готовая студийная сцена</a> · <a href="{MASTER}">Мастер UCUPaint</a>')
    html=html.replace('<video controls',f'<div class="grid">{studio_cards}</div><h2>Проверка деталей и движения</h2><video controls')
    html=html.replace('<h2>Проверка деталей и движения</h2>', '<p><a href="Grenade_Investor_10_Shots_v06.zip">Скачать 10 кадров для инвесторов</a> · <a href="Investor_Contact_Sheet_v06.jpg">Все ракурсы на одном листе</a></p><h2>Проверка деталей и движения</h2>')
    (STAGE/'gallery.html').write_text(html,encoding='utf8')
    (STAGE/'asset-state.md').write_text(readme,encoding='utf8')
    write_manifest(STAGE)
    validate(STAGE)


def seal():
    """Добавление отчётов новых процессов Blender, открывших доставленные файлы."""
    for name in ['delivered_native_reopen_v06.json','delivered_preview_reopen_v06.json',
                 'delivered_studio_reopen_v06.json']:
        report=json.loads((OUT/'checks'/name).read_text(encoding='utf8'))
        assert report['pass'],name
        assert Path(report['candidate']).parent.resolve()==TARGET.resolve(),name
        for folder in [STAGE,TARGET]:
            shutil.copy2(OUT/'checks'/name,folder/'checks'/name)
    for folder in [STAGE,TARGET]:
        write_manifest(folder)
        validate(folder)


if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'package'
    if mode=='package':package()
    elif mode=='copy':
        validate(STAGE)
        TARGET.mkdir(parents=True,exist_ok=True)
        shutil.copytree(STAGE,TARGET,dirs_exist_ok=True)
        validate(TARGET)
    elif mode=='validate':validate(TARGET)
    elif mode=='seal':seal()
    else:raise ValueError(mode)
