"""Record the verified game derivative and preserve accepted artist sources."""
import pathlib,json,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[2];WORK=ROOT/'_asset_src/dozor/game'
OUT=ROOT/'assets/models/attachments/dozor';ASSET=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
spec=json.loads((ASSET/'finish-spec.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
checks=json.loads((WORK/'godot-checks.json').read_text(encoding='utf-8'))
assert checks['failed']==0 and checks['complete_assembly_triangles']<=5000
assert checks['renderer']=='forward_plus'
assert checks['imported_lod_entries']>0
assert hashlib.sha256(pathlib.Path(spec['wear']['model']).read_bytes()).hexdigest()==spec['wear']['model_sha256']
assert hashlib.sha256(pathlib.Path(spec['wear']['painter_project']).read_bytes()).hexdigest()==spec['wear']['painter_sha256']
pack=json.loads((WORK/'pack.json').read_text(encoding='utf-8'))
assert all(r['unresolved_interior_pixels']==0 for r in pack)
for folder in ('review_maps_f1','review_maps_p'):
    review=json.loads((WORK/folder/'maps.json').read_text(encoding='utf-8'))
    assert not any(f['level']=='fail' for f in review['findings'])
spec['game']={'prepared':True,'owner_visual_reviewed':False,'model':str(ASSET/'models/DOZOR_Game_v01.blend'),
    'asset_directory':str(OUT),'triangles':manifest['triangles'],'complete_assembly_triangles':checks['complete_assembly_triangles'],
    'triangle_limit':5000,'godot_checks_passed':checks['passed'],'renderer':'Forward+',
    'gameplay_integrated':False,'hands_changed':False,'source_accepted':True}
(ASSET/'finish-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['godot-checks.json','geometry-checks.json','nearest-report.json','pack.json']:
    shutil.copyfile(WORK/name,ASSET/'checks'/('game-'+name))
shutil.copyfile(OUT/'manifest.json',ASSET/'checks/game-manifest.json')
for folder in ('review_maps_f1','review_maps_p'):
    for extension in ('json','txt'):shutil.copyfile(WORK/folder/('maps.'+extension),ASSET/'checks'/(folder+'.'+extension))
renders=ASSET/'renders/game';renders.mkdir(exist_ok=True)
for p in (ROOT/'docs/screens/dozor').glob('game_*.png'):shutil.copyfile(p,renders/p.name)
state=ASSET/'asset-state.md';text=state.read_text(encoding='utf-8')
marker='2026-11-02 — игровая версия ДОЗОР, лимит 5000 треугольников.'
note=f'''\n\n{marker}
Рабочая отделка 100% принята владельцем; источники Blender/Painter сохранены побайтно.
Игровой просмотр: models/DOZOR_Game_v01.blend. В проекте: assets/models/attachments/dozor/dozor_f1.gltf,
dozor_f1m.gltf, dozor_f1s.gltf, dozor_p.gltf, внешние PNG8. Фонарь {manifest['triangles']['f1']} трис,
крепёж {manifest['triangles']['p']} трис; сборка со стеклом {checks['complete_assembly_triangles']} ≤ 5000.
Клипса, кнопки, хвостовая крышка и ободок, створка кольца, губка, винт и кнопки зажима отдельными узлами.
GameUV: 2K фонарь / 1K крепёж; UV заполнение {manifest['atlas']['F1']['fill']:.1%} / {manifest['atlas']['P']['fill']:.1%},
плотность {manifest['atlas']['F1']['px_mm']:.2f} / {manifest['atlas']['P']['px_mm']:.2f} пикс/мм; 12/6 px отступы.
80% не достигнуты: узкие профили, торцы и отступы множества мелких островов; проверены четыре схемы укладки.
Карты не увеличивались. Насечка, мелкие кольца и точки кнопок перенесены в normal map.
Запекание matched/exploded; жёсткие грани согласованы с экспортом. Краевые пропуски дополнены с ближайшей
реальной HP-поверхности (≤0.5 мм), с переводом normal HP tangent → world → LP tangent; внутри UV пропусков нет.
glTF содержит SHA-256 внешнего BIN: Godot держал старую UV-копию при прежнем JSON, теперь геометрия переимпортируется.
Линза GL-AR — слабый френелевский отлив; особенность тонкой плёнки заменена шейдером Godot.
AO из Painter отключён в игровом загрузчике, как в принятом Blender-материале; освещение использует SSAO.
Коллизия — простой convex из 68 точек для фонаря, box со смещением 18 мм для крепежа.
Godot 4.7.2 Forward+: {checks['passed']} проверок / 0 ошибок, размеры 143 × 34 мм, зазор вкладыша >0,
съём клипсы и вращение створки, импорт normal/ORM, mipmaps и {checks['imported_lod_entries']} записей автоматических LOD.
Просмотрены реальные кадры docs/screens/dozor/game_*.png; ближний вид и мировой ракурс с LOD.
Модели и импорт готовы; игровой вид предъявляется владельцу. Предметы/цены/монтаж/L и FPS-поза рук — следующий этап.
'''
if marker not in text:state.write_text(text+note,encoding='utf-8')
print('Game derivative recorded:',checks['complete_assembly_triangles'],'triangles;',checks['passed'],'checks')
