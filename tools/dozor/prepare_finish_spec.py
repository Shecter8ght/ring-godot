"""Prepare exact mesh slots for the finish catalogue, without choosing materials."""
import bpy
import json
import pathlib

root=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
path=root/'finish-spec.json'
assert pathlib.Path(bpy.data.filepath).name=='DOZOR_Family_form_v02.blend'
definitions=[('body','Корпуса трёх фонарей'),('bezel','Ободок и наконечники'),
             ('clip','Клипсы'),('mount','Корпус крепления ДОЗОР-П'),
             ('fasteners','Стальные винты и оси'),('rubber','Кнопки и уплотнения'),
             ('glass','Стекло'),('reflector','Отражатели'),('emitter','Светодиоды и центраторы')]
slots={key:{'id':key,'title':title,'parts':[],'finish':None,'overrides':{},'note':''} for key,title in definitions}
for colname in ['01 • ДОЗОР Ф-1 • master shape','02 • ДОЗОР Ф-1М • shared housing',
                '03 • ДОЗОР Ф-1С • shared housing','04 • ДОЗОР-П • independent Picatinny mount']:
    for ob in bpy.data.collections[colname].all_objects:
        if ob.type!='MESH':continue
        n=ob.name
        if '.Optics.solid_glass' in n:key='glass'
        elif '.Optics.parabolic_reflector' in n:key='reflector'
        elif '.Optics.LED_' in n or '.Optics.emitter_centering_ring' in n:key='emitter'
        elif '.Button.' in n or '.Liner.' in n or '.lens_gasket' in n or '.recessed_switch_plate' in n:key='rubber'
        elif '.Bezel.' in n:key='bezel'
        elif '.Clip.' in n:key='clip'
        elif n in ['P.Hinge.pin','P.Lock.threaded_shank','P.Lock.hex_socket_head','P.Clamp.cross_pin','P.Clamp.recoil_key']:key='fasteners'
        elif n.startswith('P.'):key='mount'
        else:key='body'
        slots[key]['parts'].append(n)
if path.exists():
    spec=json.loads(path.read_text(encoding='utf-8'))
    for slot in spec['slots']:
        if slot['id'] in slots:slot['parts']=slots[slot['id']]['parts']
else:
    spec={'schema':'ring-finish-spec/1','asset':'ДОЗОР Ф-1 / Ф-1М / Ф-1С и ДОЗОР-П',
          'model':str(root/'models/DOZOR_Family_form_v02.blend'),'stage':'factory',
          'catalog':'tools/asset_kit/finish/finishes.json','slots':list(slots.values()),
          'interview':[],'favorites':[],'requests':[],'history':[],'accepted':False,
          'about':'Подготовлены группы реальных деталей; отделки ещё не выбраны. Ответы интервью ожидаются.'}
path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('SPEC',path,'slots',len(slots),'meshes',sum(len(s['parts']) for s in slots.values()),flush=True)
