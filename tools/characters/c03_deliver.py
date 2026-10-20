"""Упаковать C03: общая примерка, четыре самостоятельных ассета и реальные снимки."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,bpy,json,math,shutil,hashlib,zipfile
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_balaclavas as B
import wardrobe_deliver as WD
import c03_geometry as C
import c03_polish as P
import c03_refine as R
import c03_verify as V

ROOT=Path(__file__).resolve().parents[2]
MODEL_ROOT=Path('E:/Models Blender/RING_NPC_2026-10-20_v01')
MASTER='RING_C03_M02_Art_v01.blend'


def purge():
    for group in [bpy.data.materials,bpy.data.images,bpy.data.meshes,bpy.data.node_groups,bpy.data.armatures,bpy.data.curves]:
        for block in group:block.use_fake_user=False
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)


def hood_and_hem(col,body,rig):
    mats={key:bpy.data.materials['C03 | '+key] for key in ['nylon_olive','combat_knit','thread_dark']}
    for ob in list(col.objects):
        if any(word in ob.name for word in ['collapsed hood','hood sewn lip','hood panel stitch','gathered elastic hem','hem fine topstitch']):bpy.data.objects.remove(ob,do_unlink=True)
    verts=[];faces=[];n=112;rows=40
    for j in range(rows+1):
        t=j/rows;r=math.cos(t*math.pi/2)
        for i in range(n):
            a=2*math.pi*i/n
            x=.108*r*math.sin(a);y=.075+.037*math.sin(math.pi*t)+.037*r*math.cos(a)
            y+=.004*math.sin(3*a+1.3)*math.sin(math.pi*t)**2
            y+=.004*math.sin(2*a-.6)*math.exp(-((t-.34-.08*math.sin(a))/.10)**2)
            z=1.539-.135*math.sin(t*math.pi/2)+.014*math.cos(a)*(1-t)+.003*math.cos(2*a-.7)*math.sin(math.pi*t)
            verts.append(Vector((x,y,z)))
    for j in range(rows):
        for i in range(n):k=(i+1)%n;faces.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    hood=C.mesh('T03 | rounded collapsed cloth hood',verts,faces,col,mats['nylon_olive'],1,.0007)
    hood.data.materials.append(mats['combat_knit']);next(m for m in hood.modifiers if m.type=='SOLIDIFY').material_offset=1
    objects=[hood,G.line_mesh('T03 | hood soft sewn lip',[verts[:n]],.0012,col,mats['nylon_olive'],True)]
    for angle in [14,n-14]:
        line=[verts[j*n+angle]+Vector((0,.001,0)) for j in range(rows-2)]
        objects.append(G.stitches('T03 | hood panel sewing',[line],col,mats['thread_dark'],radius=.00012))
    top=next(ob for ob in col.objects if 'sewn main surface' in ob.name)
    # Убрать искусственный горизонтальный переход раннего раскроя.
    key=top.data.shape_keys.key_blocks[-1];adj=[[] for _ in top.data.vertices]
    for edge in top.data.edges:
        a,b=edge.vertices;adj[a].append(b);adj[b].append(a)
    for _ in range(10):
        values={}
        for i,p in enumerate(key.data):
            if 1.105<p.co.z<1.18 and abs(p.co.x)<.225:
                weight=G.smooth(1.105,1.128,p.co.z)*(1-G.smooth(1.155,1.18,p.co.z))*.50
                values[i]=G.mix(p.co.y,sum(key.data[j].co.y for j in adj[i])/len(adj[i]),weight)
        for i,value in values.items():key.data[i].co.y=value
    top.data.update();bpy.context.view_layer.update();surface=W.outer_surface(top)
    boundary=min(B.boundary_paths(top),key=lambda path:sum(p.z for p in path)/len(path));n=len(boundary);vv=[];ff=[]
    for j in range(6):
        t=j/5
        for p in boundary:
            target=p+Vector((0,0,.021*t));q,normal,_,_=surface.nearest(target)
            radial=Vector((target.x,target.y+.012,0)).normalized()
            if q is None:q=target;normal=radial
            if normal.dot(radial)<0:normal=-normal
            vv.append(q+normal*(.0012+.00035*math.sin(71*math.atan2(p.x,p.y+.012))))
    for j in range(5):
        for i in range(n):k=(i+1)%n;ff.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    objects.append(C.mesh('T03 | surface fitted elastic hem',vv,ff,col,mats['nylon_olive'],1,.00065))
    line=[vv[4*n+i]+Vector((0,0,.0004)) for i in range(n)]
    objects.append(G.stitches('T03 | fitted hem topstitch',[line+[line[0]]],col,mats['thread_dark'],radius=.00012))
    G.bind([ob for ob in objects if ob],body,rig)
    control=bpy.data.objects['RING | Wardrobe Controls']
    for ob in objects:
        if not ob:continue
        ob['wardrobe_id']='T03';W.metric_uv(ob);M.attributes(ob,'T03');P.wear(ob,'T03')
        for prop in ['hide_render','hide_viewport']:
            d=ob.driver_add(prop).driver;d.type='SCRIPTED';var=d.variables.new();var.name='enabled';var.targets[0].id=control;var.targets[0].data_path='["Ветровка"]';d.expression='not enabled'


def prepare(source,out):
    assert out.parent.resolve()==MODEL_ROOT.resolve(),out
    assert not out.exists(),'Папка выдачи уже существует: '+str(out)
    out.mkdir();(out/'Previews').mkdir();(out/'Separate_Assets').mkdir();(out/'construction_scripts').mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.filepaths.save_version=0
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    flags=[(m,m.show_viewport,m.show_render) for m in body.modifiers if m.type=='MASK']
    # Отключить только видимость модификаторов для переноса весов, сохранив драйверы.
    for m,_,_ in flags:
        for prop in ['show_viewport','show_render']:
            f=body.animation_data.drivers.find(m.path_from_id(prop)) if body.animation_data else None
            if f:f.mute=True
        m.show_viewport=False;m.show_render=False
    bpy.context.view_layer.update()
    col=next(c for c in bpy.data.collections if c.get('wardrobe_id')=='T03')
    # Вернуть гарантированный запас ткани над головой до неудачной сферической правки.
    name=next(ob.name for ob in bpy.data.objects if 'B03 | tailored cotton hood shell'==ob.name)
    good=R.WORK/'probe_v04/C03_Refinement_M02.blend'
    with bpy.data.libraries.load(str(good),link=False) as (_,dst):dst.objects=[name]
    ref=dst.objects[0];current=bpy.data.objects[name];assert len(ref.data.vertices)==len(current.data.vertices)
    for a,b in zip(current.data.vertices,ref.data.vertices):a.co=b.co
    current.data.update();bpy.data.objects.remove(ref,do_unlink=True)
    hood_and_hem(col,body,rig)
    for ob in col.objects:
        if 'grey jersey under the open neck' in ob.name:
            for v in ob.data.vertices:v.co.z=min(v.co.z,1.505)
            ob.data.update()
    for m,view,ren in flags:
        m.show_viewport=view;m.show_render=ren
        for prop in ['show_viewport','show_render']:
            f=body.animation_data.drivers.find(m.path_from_id(prop)) if body.animation_data else None
            if f:f.mute=False
    # Расширить кадр спины, чтобы кисти не обрезались.
    bpy.data.objects['C03_Back'].data.ortho_scale=2.19
    bpy.data.objects['C03_Front'].data.ortho_scale=2.19
    purge();bpy.ops.file.pack_all();images=WD.pack(out)
    D.frame((0,0,.94),2.55);bpy.context.scene.camera=bpy.data.objects['C03_ThreeQuarter']
    file=out/MASTER;bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=False)
    (out/'images.json').write_text(json.dumps(images,ensure_ascii=False,indent=2),encoding='utf-8')
    print('C03_DELIVERY_PREPARED '+str(file),flush=True)


def parts(out,render):
    master=out/MASTER
    records=[]
    for code,z,scale in [('T03',1.27,1.80),('P01',.59,1.18),('F01',.095,.53),('B03',1.64,.39)]:
        bpy.ops.wm.open_mainfile(filepath=str(master));bpy.context.preferences.filepaths.save_version=0
        col=next(c for c in bpy.data.collections if c.get('wardrobe_id')==code and c.asset_data)
        rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls'];studio=bpy.data.collections['06_Review_Studio']
        keep=set(col.objects)|{rig,control}|set(studio.objects)
        for ob in list(bpy.data.objects):
            if ob not in keep:bpy.data.objects.remove(ob,do_unlink=True)
        for ob in [rig,control]:
            if ob.name not in col.objects:col.objects.link(ob)
        if col.name not in bpy.context.scene.collection.children:bpy.context.scene.collection.children.link(col)
        for collection in list(bpy.data.collections):
            if collection not in [col,studio]:bpy.data.collections.remove(collection)
        purge()
        for im in bpy.data.images:
            path=im.filepath.replace('\\','/')
            if im.packed_file and path.startswith('//textures/'):im.filepath='//../textures/'+path.rsplit('/',1)[-1]
        scene=bpy.context.scene;cam=bpy.data.objects['C03_ThreeQuarter'];target=Vector((0,-.025,z));cam.location=target+Vector((2.1,-4,.70));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.camera=cam
        scene.render.resolution_x=1500 if code=='T03' else 1200;scene.render.resolution_y=1000 if code in ['T03','F01'] else 1400
        scene.cycles.samples=40;scene.render.filepath=str(out/'Previews'/(code+'_asset.png'));R.use_render_device(scene)
        D.frame(tuple(target),scale*1.35);rig.hide_set(True);control.hide_set(True)
        file=out/'Separate_Assets'/(code+'_M02_Art_v01.blend');bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=False)
        if render:bpy.ops.render.render(write_still=True)
        records.append({'id':code,'collection':col.name,'file':str(file.relative_to(out)).replace('\\','/'),'meshes':sum(o.type=='MESH' for o in col.objects)})
        print('C03_SEPARATE_ASSET '+code,flush=True)
    (out/'separate_assets.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')


def finish(out):
    records=json.loads((out/'separate_assets.json').read_text(encoding='utf-8'));results=[]
    for rec in records:
        bpy.ops.wm.open_mainfile(filepath=str(out/rec['file']));col=bpy.data.collections[rec['collection']]
        assert col.asset_data and 'M02_Body_Head' not in bpy.data.objects
        rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls'];assert rig.parent==control
        for ob in col.objects:
            if ob.type!='MESH':continue
            assert not ob.hide_render and ob.parent==rig and ob.data.uv_layers.get('UV_Fabric_Metres'),ob.name
            assert any(m.type=='ARMATURE' and m.object==rig for m in ob.modifiers),ob.name
            for slot in ob.material_slots:
                if slot.material:assert len(P.native(slot.material).yp.layers)>=6,slot.material.name
        for im in bpy.data.images:
            if im.filepath:assert im.packed_file and Path(bpy.path.abspath(im.filepath)).is_file(),im.filepath
        rec['meshes']=sum(ob.type=='MESH' for ob in col.objects)
        results.append({'id':rec['id'],'self_contained_native_asset':'PASS'})
    (out/'separate_assets.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    V.main(out/MASTER)
    report=json.loads((out/'verification/c03_verification.json').read_text(encoding='utf-8'));report['standalone_assets_reopened']=results
    (out/'c03_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    prior=MODEL_ROOT/'NPC_Wardrobe_Concepts_v01'
    shutil.copy2(prior/'phototexture_sources.json',out/'phototexture_sources.json')
    for directory in ['Licenses','licenses']:
        if (prior/directory).exists():shutil.copytree(prior/directory,out/'licenses',dirs_exist_ok=True)
    references=[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'role':'Owner supplied finish reference only; no image projection, geometry or texture extraction.'} for p in sorted((R.WORK/'references').glob('owner_finish_*.png'))]
    scripts=[*sorted((ROOT/'tools/characters').glob('c03_*.py'))]
    scripts+=[ROOT/'tools/characters'/name for name in ['m02_custom_clothes.py','m02_custom_clothes_deliver.py','m02_custom_clothes_verify.py','wardrobe_geometry.py','wardrobe_materials.py','wardrobe_balaclavas.py','wardrobe_deliver.py','wardrobe_verify.py','npc_wardrobe.py']]
    for file in scripts:shutil.copy2(file,out/'construction_scripts'/file.name)
    manifest={'master':MASTER,'source_wardrobe':str(prior/'RING_NPC_Wardrobe_M02_v01.blend'),'source_wardrobe_sha256':hashlib.sha256((prior/'RING_NPC_Wardrobe_M02_v01.blend').read_bytes()).hexdigest(),
        'source_body':report['source_body'],'source_body_sha256':report['source_sha256'],'items':records,'owner_references':references,
        'original_concept':str(MODEL_ROOT/'Clothing_Concepts_v01/C03_scavenger_windbreaker_sheet_v01.png'),
        'scope':'Editable art review version, M02 fitting. No game mesh, LOD, bake or import. Other wardrobe presets preserved in previous library.'}
    (out/'c03_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'00_НАЧНИ_ЗДЕСЬ.txt').write_text('C03 — художественная редакция одежды М02\n\nОткрыть '+MASTER+' в Blender 5.2.2.\nОсновной файл — вся примерка в T-позе. Separate_Assets — четыре независимых коллекции Asset со своими ригами.\nRING | Wardrobe Controls: Ветровка, Джинсы, Обувь, Балаклава. Выключатели возвращают соответствующую анатомию; снятая балаклава возвращает волосы и щетину.\nМатериалы — нативный UCUPaint 2.4.9. Все изображения упакованы и продублированы в textures. Для просмотра и обычного рендера дополнение не обязательно; для редактирования слоёв его нужно включить.\nPreviews — реальные снимки сохранённых моделей, ZIP — их архив. Исходное тело, все его формы и UV сохранены без изменений.\n\nЭто редактируемый художественный кандидат на оценку, не готовый игровой персонаж. Другие размеры тел, полная доводка деформаций в анимациях и игровой экспорт выполняются отдельно.\nПредыдущая библиотека NPC_Wardrobe_Concepts_v01 сохранена.\n',encoding='utf-8')
    (out/'asset-state.md').write_text('# C03: художественная редакция v01\n\nРедактируемый исходник на М02, передан владельцу на художественную оценку. Ветровка, джинсы, низкая треккинговая обувь и хлопковая балаклава.\n\nПроверены исходная анатомия и UV, все формы тела, веса, нативные слои, выключатели, конечность координат в трёх статичных позах, повторное открытие отдельных ассетов.\n\nПолная анимационная коррекция и подготовка к игре не выполнялись. Художественная оценка владельца ещё не получена.\n',encoding='utf-8')
    pngs=sorted((out/'Previews').glob('*.png'));assert len(pngs)==12,len(pngs)
    archive=out/'C03_Photos_v01.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for png in pngs:z.write(png,'Previews/'+png.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and len(z.namelist())==12
    checks={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='SHA256.json'}
    (out/'SHA256.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('C03_DELIVERY_PASS '+json.dumps({'folder':str(out),'assets':4,'photos':len(pngs),'verification':'PASS'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','renders','parts','finish']);p.add_argument('output',type=Path);p.add_argument('--source',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);D.enable_layers();out=args.output.resolve()
    if args.mode=='prepare':prepare(args.source.resolve(),out)
    elif args.mode=='renders':
        bpy.ops.wm.open_mainfile(filepath=str(out/MASTER));R.render(out/'Previews','ThreeQuarter,Jacket,Shoes,Back,Jeans,Mask,Front,Side',48)
    elif args.mode=='parts':parts(out,True)
    else:finish(out)
