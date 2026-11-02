"""Replace hovering text with a native editable surface-colour layer.

Regular Python: --asset <folder> --prepare-masks (Pillow typography only).
Blender with accepted v01 open: --asset <folder>. Saves a new v02, preserves v01.
No body mesh changes, UV unwrap, finish selection, bump, or displacement.
"""
import argparse
import hashlib
import json
import pathlib
import sys

argp=argparse.ArgumentParser()
argp.add_argument('--asset',required=True)
argp.add_argument('--prepare-masks',action='store_true')
cli=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
args=argp.parse_args(cli)
ASSET=pathlib.Path(args.asset)
TEX=ASSET/'textures'/'markings'
TEX.mkdir(parents=True,exist_ok=True)
VERSIONS={'F1':'Ф-1','F1M':'Ф-1М','F1S':'Ф-1С'}

if args.prepare_masks:
    from PIL import Image,ImageDraw,ImageFont
    big=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',132)
    small=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',90)
    for key,label in VERSIONS.items():
        im=Image.new('L',(1024,256),0);d=ImageDraw.Draw(im)
        d.text((355,128),'ДОЗОР',font=big,fill=255,anchor='mm')
        d.text((850,128),label,font=small,fill=255,anchor='mm')
        im.save(TEX/(key+'.png'))
    im=Image.new('L',(1024,256),0);d=ImageDraw.Draw(im)
    d.text((512,128),'ДОЗОР-П',font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',126),fill=255,anchor='mm')
    im.save(TEX/'P.png')
    print('Created 4 monochrome marking masks; no product finish generated.')
    raise SystemExit(0)

import bpy

SOURCE=ASSET/'models'/'DOZOR_Family_form_v01.blend'
EXPECTED='d9b21b0b41a6e23ee089aa936481b8f27c503f5e05264a72a83616492c3cd30c'
assert pathlib.Path(bpy.data.filepath).resolve()==SOURCE.resolve(),'Unexpected open file'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED,'Accepted candidate changed'

def mesh_hash():
    # Unique mesh datablocks, vertex positions, polygon indices and local transforms.
    digest=hashlib.sha256()
    for ob in sorted([o for o in bpy.data.objects if o.type=='MESH'],key=lambda o:o.name):
        digest.update(ob.name.encode())
        for v in ob.data.vertices:digest.update(repr(tuple(v.co)).encode())
        for f in ob.data.polygons:digest.update(repr(tuple(f.vertices)).encode())
        digest.update(repr(tuple(tuple(row) for row in ob.matrix_local)).encode())
    return digest.hexdigest()

before=mesh_hash()
layer_records=[]

def layer(ob,key,zmin,zmax,yextent):
    original=ob.material_slots[0].material
    material=original.copy()
    material.name='ДОЗОР • '+key+' • корпус + маркировка'
    # Linked geometry retains per-instance material overrides for the three versions.
    ob.material_slots[0].link='OBJECT'
    ob.material_slots[0].material=material
    nodes=material.node_tree.nodes;links=material.node_tree.links
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    substrate=tuple(bsdf.inputs['Base Color'].default_value)
    group=bpy.data.node_groups.new('Маркировка • ДОЗОР '+key,'ShaderNodeTree')
    group.interface.new_socket(name='Координаты детали',in_out='INPUT',socket_type='NodeSocketVector')
    base=group.interface.new_socket(name='Цвет корпуса',in_out='INPUT',socket_type='NodeSocketColor')
    base.default_value=substrate
    ink=group.interface.new_socket(name='Цвет надписи',in_out='INPUT',socket_type='NodeSocketColor')
    ink.default_value=(.70,.72,.74,1)
    group.interface.new_socket(name='Цвет поверхности',in_out='OUTPUT',socket_type='NodeSocketColor')
    gn=group.nodes;gl=group.links
    inp=gn.new('NodeGroupInput');inp.location=(-900,0)
    output=gn.new('NodeGroupOutput');output.location=(600,100)
    separate=gn.new('ShaderNodeSeparateXYZ');separate.location=(-710,120)
    gl.new(inp.outputs['Координаты детали'],separate.inputs[0])
    def normalized(socket,low,span,x,y):
        sub=gn.new('ShaderNodeMath');sub.operation='SUBTRACT';sub.inputs[1].default_value=low;sub.location=(x,y)
        div=gn.new('ShaderNodeMath');div.operation='DIVIDE';div.inputs[1].default_value=span;div.location=(x+160,y)
        gl.new(socket,sub.inputs[0]);gl.new(sub.outputs[0],div.inputs[0])
        return div.outputs[0]
    u=normalized(separate.outputs['Z'],zmin,zmax-zmin,-500,240)
    v=normalized(separate.outputs['Y'],-yextent,2*yextent,-500,50)
    combine=gn.new('ShaderNodeCombineXYZ');combine.location=(-140,240)
    gl.new(u,combine.inputs['X']);gl.new(v,combine.inputs['Y'])
    image=bpy.data.images.load(str(TEX/(key+'.png')),check_existing=False)
    image.name='Маска маркировки • '+key
    image.colorspace_settings.name='Non-Color';image.pack()
    tex=gn.new('ShaderNodeTexImage');tex.name='Редактируемая маска надписи';tex.label=tex.name
    tex.image=image;tex.extension='CLIP';tex.interpolation='Linear';tex.location=(40,240)
    gl.new(combine.outputs[0],tex.inputs['Vector'])
    gate=gn.new('ShaderNodeMath');gate.operation='LESS_THAN';gate.inputs[1].default_value=-.015
    gate.location=(-140,-120);gl.new(separate.outputs['X'],gate.inputs[0])
    mask=gn.new('ShaderNodeMath');mask.operation='MULTIPLY';mask.location=(250,0)
    gl.new(gate.outputs[0],mask.inputs[0]);gl.new(tex.outputs['Color'],mask.inputs[1])
    mix=gn.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.location=(420,150)
    gl.new(mask.outputs[0],mix.inputs[0]);gl.new(inp.outputs['Цвет корпуса'],mix.inputs[1])
    gl.new(inp.outputs['Цвет надписи'],mix.inputs[2]);gl.new(mix.outputs[0],output.inputs[0])
    coord=nodes.new('ShaderNodeTexCoord');coord.location=(-650,100)
    inst=nodes.new('ShaderNodeGroup');inst.node_tree=group;inst.name='Маркировка • встроенный слой'
    inst.label='Маркировка • маска цвета, без рельефа';inst.location=(-350,100)
    links.new(coord.outputs['Object'],inst.inputs['Координаты детали'])
    links.new(inst.outputs['Цвет поверхности'],bsdf.inputs['Base Color'])
    layer_records.append({'object':ob.name,'material':material.name,'layer':group.name,'mask':image.name,
                          'geometry_offset_mm':0,'bump':False,'displacement':False})

for prefix in VERSIONS:
    layer(bpy.data.objects[prefix+'.Head.hollow_faceted_housing'],prefix,.008,.0295,.0027)
layer(bpy.data.objects['P.Ring.upper_cap'],'P',.068,.093,.0030)
removed=[]
for ob in list(bpy.data.objects):
    if ob.type=='FONT' and '.Mark' in ob.name:
        removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
assert len(removed)==7,(len(removed),removed)
assert before==mesh_hash(),'Body mesh or transform unexpectedly changed'
assert not any(o.type=='FONT' for o in bpy.data.objects),'Visible font geometry remains'

note=bpy.data.texts.new('ДОЗОР • маркировка')
note.write('Надписи нанесены маской цвета в родной группе материала.\n'
           'Для правки откройте Shader Editor → Маркировка • встроенный слой.\n'
           'Внутри — упакованная чёрно-белая маска; цвет корпуса и надписи задаются на входах группы.\n'
           'Геометрия корпуса, Height, Normal, Displacement и shadow visibility не менялись.\n')
bpy.ops.file.pack_all()
dest=ASSET/'models'/'DOZOR_Family_form_v02.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(dest))
report={'source':str(SOURCE),'source_sha256':EXPECTED,'source_shape_accepted':True,
        'candidate':str(dest),'candidate_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'mesh_hash_before':before,'mesh_hash_after':mesh_hash(),'geometry_unchanged':True,
        'removed_floating_text':removed,'native_marking_layers':layer_records,
        'marking_correction_reviewed':False}
(ASSET/'checks'/'marking-integration-v02.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
state=ASSET/'asset-state.md'
s=state.read_text(encoding='utf-8')
s=s.replace('2026-11-02. Стадия: геометрический кандидат v01, ожидает просмотра формы владельцем.',
            '2026-11-02. Форма корпуса и крепления v01 принята владельцем: «Хорошо, мне нравится».')
s=s.replace('Прототип: Fenix TK16 V2.0; имя и линейка приняты, форма кандидата ещё не принята.',
            'Прототип: Fenix TK16 V2.0; имя, линейка и основная форма приняты. Уточнение — интеграция маркировки.')
s=s.replace('Файл: models/DOZOR_Family_form_v01.blend. Blender 5.2.2 LTS.',
            'Актуальный файл: models/DOZOR_Family_form_v02.blend. Принятый источник v01 сохранён. Blender 5.2.2 LTS.')
s=s.replace('корпус общий (linked mesh), версия обозначается отдельным редактируемым текстом.',
            'корпус общий (linked mesh), версия обозначается отдельной редактируемой маской цвета в материале.')
s=s.replace('Следующий этап — просмотр кандидата владельцем. UV и текстурирование после принятия формы.',
            'Локальная правка v02: надписи встроены слоем цвета. Полная заводская отделка ещё не выбиралась.')
s+='\n2026-11-02, уточнение владельца: надпись должна быть частью сетки или текстурным слоем поверхности.\n'
s+='v02: удалены 7 FONT-объектов, добавлены 4 нативных слоя маркировки. Сетки и трансформы сохранены.\n'
s+='Слой влияет только на цвет поверхности; зазора, отдельной геометрии букв и её тени нет.\n'
s+='SHA-256 v02: '+report['candidate_sha256']+'\n'
state.write_text(s,encoding='utf-8')
print('SAVED',dest,flush=True)
print('Removed floating text:',removed,flush=True)
print('Geometry unchanged:',before==mesh_hash(),flush=True)
