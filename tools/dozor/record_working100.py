"""Record the reviewed candidate without accepting it or changing factory acceptance."""
import pathlib,json,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/dozor/wear'
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))
assert spec['accepted'] and (OUT/'checks/working100-native-reopen.json').exists()
assert (OUT/'checks/working100-reopen.json').exists()
assert (OUT/'checks/working100-preservation.json').exists()
review=json.loads((WORK/'review_maps/maps.json').read_text(encoding='utf-8'))
assert not any(f['level']=='fail' for f in review['findings'])
assert (WORK/'review_render/render.txt').exists()
model=OUT/'models/DOZOR_Working100_Painter_v01.blend'
project=OUT/'painter/DOZOR_working100_v01.spp'
candidate={'state':'working100','accepted':False,'date':'2026-11-02',
    'model':str(model),'model_sha256':sha(model),'painter_project':str(project),'painter_sha256':sha(project),
    'factory_preserved':True,'geometry_preserved':True,'native_group':'Этап 2 — износ',
    'effects':['partial fingerprints','grip and seating polish','sparse superficial scratches','trace recess dust'],
    'excluded':['coating loss','chips','rust','heavy dirt','geometric damage'],
    'contact_basis':{'handheld':'Generic geometric grip/button zones; pistol hand pose is not available; no rig-derived contact claimed',
                     'mount':'Actual ring inner seat, liner and Picatinny jaw/recoil contacts'},
    'history':'No faction, environment or extended service history invented',
    'interview_basis':'Owner said continue after proposed light working100 stage; factory accepted separately',
    'sources':json.loads((WORK/'sources.json').read_text(encoding='utf-8')),
    'limitations':['High-poly authoring UV fill 24%; game atlas separate',
                   'Five roughness texels differ by <=3/255 after recomputation; also reproduced from immutable factory SPP']}
spec['wear']=candidate
spec['about']='Заводская отделка принята 2026-11-02; рабочее состояние 100% сохранено отдельным кандидатом для просмотра.'
(OUT/'finish-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'checks/working100-candidate.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
maskfolder=OUT/'painter/working100_masks';maskfolder.mkdir(exist_ok=True)
for p in WORK.glob('*.png'):shutil.copyfile(p,maskfolder/p.name)
for name in ('license.txt','sources.json','masks.json','parts.json'):shutil.copyfile(WORK/name,maskfolder/name)
(maskfolder/'originals').mkdir(exist_ok=True)
for p in (WORK/'sources').glob('*.png'):shutil.copyfile(p,maskfolder/'originals'/p.name)
renders=OUT/'renders/working100';renders.mkdir(exist_ok=True)
for p in (WORK/'preview/renders').glob('*.png'):shutil.copyfile(p,renders/p.name)
screens=ROOT/'docs/screens/dozor';screens.mkdir(exist_ok=True)
for src,dest in [('01_flashlight_34.png','working100_flashlight.png'),('06_assembly.png','working100_assembly.png'),
                 ('13_grip_contact.png','working100_grip.png'),('07_ring_open.png','working100_mount_open.png')]:
    shutil.copyfile(renders/src,screens/dest)
for name,folder in [('maps',WORK/'review_maps'),('render',WORK/'review_render')]:
    for ext in ('json','txt'):
        p=folder/(name+'.'+ext)
        if p.exists():shutil.copyfile(p,OUT/'checks'/('working100-review-'+p.name))
state=OUT/'asset-state.md'
note='''

2026-11-02 — рабочее состояние 100%, отдельный кандидат на просмотр.
Актуальный просмотр: models/DOZOR_Working100_Painter_v01.blend.
Нативный авторинг: painter/DOZOR_working100_v01.spp, группа «Этап 2 — износ» отключается целиком.
Принятые заводские .blend/.spp сохранены побайтно; finish-spec.accepted=true относится к ним.
finish-spec.wear.accepted=false: рабочее состояние ещё не принято владельцем.

| Узел | След | Каналы / маска |
|---|---|---|
| Наружная насечка корпуса | Частичные отпечатки 12–17 мм | BaseColor ×, Roughness −; три локальных штампа × зона хвата |
| Вершины насечки и кнопки | Лёгкая полировка | BaseColor ×, Roughness −; геометрические выступы/центры нажатия |
| Корпус/клипса | Редкие поверхностные риски | BaseColor ×, Roughness +; ограниченные наружные зоны |
| Углубления насечки, кнопочной площадки, шарнира | Следы пыли | BaseColor, Roughness +, слабое Metallic −; углубления × CC0 рисунок |
| Кольцо, вкладыш, губки Picatinny и упор | Контактная полировка | BaseColor ×, Roughness −; реальные посадочные поверхности |

Ручной контакт задан по геометрии, не по несуществующему клипу пистолетного хвата.
История фракции/среды не придумывалась. Сколов, ржавчины, утраты покрытия и тяжёлой грязи нет.
Линза/внутренности оптики без следов. Height и Normal от износа не меняются; буквы по-прежнему только цвет.
Рисунок: ambientCG Fingerprints002, Scratches002, SurfaceImperfections007, CC0 1.0.
Библиотечные узоры не заявляются как фотосканы; копии оригиналов, лицензия и маски — painter/working100_masks.
Проверки повторного открытия: нативные редактируемые слои/заводское дерево, 15 packed map nodes и HDRI,
геометрия/модификаторы/трансформы неизменны. Контроль OFF: цвет/Normal/крепёж совпадают точно;
5 текселей Roughness корпуса отличаются не более чем на 3/255 при пересчёте (воспроизведено и из исходной заводской SPP).
review.py maps/render: обязательных исправлений нет; прежнее предупреждение о заполнении авторского UV 24%.
Снимки: renders/working100. Игровая сетка, _coat, LOD, экспорт, руки и механика L ещё не выполнялись.
'''
text=state.read_text(encoding='utf-8')
if '— рабочее состояние 100%, отдельный кандидат на просмотр.' not in text:state.write_text(text+note,encoding='utf-8')
print('Candidate recorded; factory acceptance preserved; wear awaits owner review')
print('Blender SHA-256',candidate['model_sha256'])
print('Painter SHA-256',candidate['painter_sha256'])
