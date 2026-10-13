"""Add owner's recessed KORS-9 frame markings with local native paint fill.

Only the new engraving floors receive UCUPaint. Full pistol surfacing remains
pending geometry acceptance. Run on the v09 optical engraving candidate.
"""
from pathlib import Path
import hashlib,importlib,json,math,sys
import bpy,bmesh,addon_utils
from mathutils import Vector,Matrix,Color
from mathutils.bvhtree import BVHTree

PROJECT=Path(__file__).resolve().parents[1];OUT=PROJECT/'_asset_src/pm_refinement/review_v09'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pm_engraving_geometry import solid_from_cap,stroke_cap,engraving_report,paint_fill_report
sys.path.insert(0,'C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts')
import ucupaint_helpers as H
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=H.load_ucupaint();assert U.common.get_current_version_str()=='2.4.9'
if '--repair-frame' in sys.argv:bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
rig=bpy.data.objects['PM_CONTROLS • select me'];host=bpy.data.objects['Frame | traced flowing silhouette']
source=Path(bpy.data.filepath)
records=json.loads((OUT/'Проверки/engraving.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'Проверки/revision_manifest.json').read_text(encoding='utf-8'))
if '--repair-frame' in sys.argv:
    for mod in host.modifiers:
        if mod.name.startswith('ENGRAVE | Frame'):mod.solver='MANIFOLD'
    bpy.context.view_layer.update();eo=host.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=eo.to_mesh()
    bm=bmesh.new();bm.from_mesh(mesh)
    topology=dict(boundary=sum(e.is_boundary for e in bm.edges),overfull=sum(len(e.link_faces)>2 for e in bm.edges),wire=sum(e.is_wire for e in bm.edges),zero_area=sum(f.calc_area()<1e-14 for f in bm.faces))
    paint_faces=sum(p.material_index==list(host.data.materials).index(bpy.data.materials['КОРС-9 • светлая краска в клеймах']) for p in mesh.polygons)
    bm.free();eo.to_mesh_clear();fresh=engraving_report(records);paint=paint_fill_report()
    check=dict(topology=topology,engraving=fresh,paint_fill=paint,paint_floor_faces=paint_faces)
    (OUT/'Проверки/frame_engraving_finish.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not any(topology.values()) and fresh['pass_engraving'] and paint['pass_paint'] and paint_faces>0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v09.blend'))
    print('PM_KORS9_FINISHED',topology,paint_faces,flush=True);sys.exit(0)
if any(m.name.startswith('ENGRAVE | Frame') for m in host.modifiers):raise RuntimeError('Frame already engraved; restart from optical candidate')
dg=bpy.context.evaluated_depsgraph_get();eo=host.evaluated_get(dg);me=eo.to_mesh()
base=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear()
collection=bpy.data.collections.new('01a • КОРС-9 engraving sources — hidden');S.collection.children.link(collection)
font=bpy.data.objects['Reflex | Marking brand -1'].data.font

# A light enamel in the engraving, separate from neutral inspection steel.
mat=bpy.data.materials.new('КОРС-9 • светлая краска в клеймах');mat.use_nodes=True
bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
bsdf.inputs['Base Color'].default_value=(.045,.051,.059,1);bsdf.inputs['Metallic'].default_value=.9;bsdf.inputs['Roughness'].default_value=.34
host.data.materials.append(mat);host.active_material_index=len(host.data.materials)-1
bpy.ops.object.select_all(action='DESELECT');host.hide_set(False);host.select_set(True);bpy.context.view_layer.objects.active=host
bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='КОРС-9 • заполнение утопленных клейм',color=True,metallic=True,roughness=True,normal=True,ao=False,switch_to_material_view=False,target_bsdf_name=bsdf.name)
group=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
tree=group.node_tree

def paint_layer(name,color,metal,rough):
    tree.yp.halt_update=True
    layer=U.Layer.add_new_layer(tree,name,'COLOR',-1,'MIX','OVERLAY','BUMP_MAP','Object','',use_designated_idx=True,designated_index=0)
    tree.yp.halt_update=False
    values={'Color':Color(color),'Metallic':metal,'Roughness':rough,'Normal':None}
    for root,ch in zip(tree.yp.channels,layer.channels):
        value=values[root.name];ch.enable=value is not None
        if value is None:continue
        ch.override=True;ch.override_type='DEFAULT';H.sync_property(U,ch,'override_color' if root.type=='RGB' else 'override_value',value)
    H.sync_property(U,layer,'intensity_value',1.0);return layer

paint_layer('01 • тёмное металлическое дно выемок',(.045,.051,.059),.90,.34)
paint=paint_layer('02 • светлая эмаль — местами облупилась',(.59,.56,.49),0.0,.57)
mask=U.Mask.add_new_mask(paint,'Локальные сколы эмали 0,08–0,25 мм','NOISE','Object','')
noise=U.common.get_mask_tree(mask).nodes[mask.source];noise.inputs['Scale'].default_value=680
noise.inputs['Detail'].default_value=2.4;noise.inputs['Roughness'].default_value=.66
H.local_noise_ramp(U,mask,.33,.40);H.reconnect(U,tree)
mat['Scope']='Only floors of actual recessed frame markings; owner specifically requested pale chipped fill'
mat['Native UCUPaint']='2.4.9';mat['Paint chip size mm']='0.08–0.25';mat['Coverage']='mostly intact with sparse irregular chips'
steel=host.data.materials[0];inverse=rig.matrix_world.inverted();sources=[]

def lettering(name,text,x,z,size,side=-1):
    data=bpy.data.curves.new('КОРС-9 source | '+name,'FONT');data.body=text;data.font=font;data.size=size
    data.align_x='CENTER';data.align_y='CENTER';data.resolution_u=24
    o=bpy.data.objects.new('Frame | Marking '+name,data);collection.objects.link(o)
    o.location=(x,side*.011,z);o.rotation_euler=(math.pi/2,0,math.pi if side>0 else 0)
    bpy.context.view_layer.update();world=o.matrix_world.copy();o.parent=rig;o.matrix_world=world;sources.append((o,Vector((0,side,0))))

lettering('brand','КОРС-9',.056,.0940,.00235)
lettering('serial','№ КР061284',.057,.0912,.00110)
lettering('calibre','9×18',.056,.0940,.00215,1)
lettering('production','КР · 06/24',.056,.0912,.0011,1)
lettering('quality','ОТК',.043,.0912,.0009)

def symbol(name,points):
    data=bpy.data.curves.new('КОРС-9 source | '+name,'CURVE');data.dimensions='3D';data.bevel_depth=.000065;data.bevel_resolution=5;data.use_fill_caps=True
    spline=data.splines.new('POLY');spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):p.co=(*co,1)
    o=bpy.data.objects.new('Frame | Marking '+name,data);collection.objects.link(o)
    bpy.context.view_layer.update();world=o.matrix_world.copy();o.parent=rig;o.matrix_world=world;sources.append((o,Vector((0,-1,0))))

symbol('proof ring',[(.043+.00088*math.cos(j*2*math.pi/96),-.011,.0940+.00088*math.sin(j*2*math.pi/96)) for j in range(97)])
symbol('proof triangle',[(.043,-.011,.09453),(.04253,-.011,.09369),(.04347,-.011,.09369),(.043,-.011,.09453)])

for source_obj,normal in sources:
    name=source_obj.name.removeprefix('Frame | Marking ');depth=.00012 if name=='brand' else .000080
    p=source_obj.matrix_world.translation.copy() if source_obj.type=='FONT' else Vector((.043,-.011,.0940))
    hit,hn,_,_=base.ray_cast(p+normal*.006,-normal,.020)
    if hit is None or hn.dot(normal)<.99:raise RuntimeError('No planar frame surface for '+name)
    plane=hit.dot(normal)
    if source_obj.type=='FONT':
        eo=source_obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
        vertices=[eo.matrix_world@v.co for v in me.vertices];faces=[tuple(p.vertices) for p in me.polygons];eo.to_mesh_clear()
        vertices=[p+normal*(plane-depth-p.dot(normal)) for p in vertices]
    else:vertices,faces=stroke_cap(source_obj,normal,plane,depth)
    vertices,faces=solid_from_cap(vertices,faces,normal,depth)
    data=bpy.data.meshes.new('КОРС-9 cutter | '+name);data.from_pydata([inverse@p for p in vertices],[],faces);data.update()
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0
    bm.to_mesh(data);bm.free();data.materials.append(steel);data.materials.append(mat)
    cutter=bpy.data.objects.new('Engraving | cutter Frame '+name,data);collection.objects.link(cutter)
    cutter.parent=rig;cutter.matrix_parent_inverse=Matrix.Identity(4);cutter.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update();local_normal=(cutter.matrix_world.to_3x3().inverted()@normal).normalized()
    for face in data.polygons:face.material_index=1 if face.normal.dot(local_normal)<-.99 else 0
    mod=host.modifiers.new('ENGRAVE | Frame '+name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='MANIFOLD';mod.object=cutter
    while host.modifiers.find(mod.name)>0 and host.modifiers[host.modifiers.find(mod.name)-1].type=='WEIGHTED_NORMAL':bpy.ops.object.modifier_move_up(modifier=mod.name)
    for ob,role in ((source_obj,'Editable lettering master' if source_obj.type=='FONT' else 'Editable symbol master'),(cutter,'Boolean operand')):
        ob['PM engraving helper']=True;ob['Engraving role']=role;ob.hide_render=True;ob.hide_set(True)
    data.calc_loop_triangles();candidates=[]
    for tri in data.loop_triangles:
        pts=[cutter.matrix_world@data.vertices[i].co for i in tri.vertices];cross=(pts[1]-pts[0]).cross(pts[2]-pts[0])
        if cross.length>2e-12 and cross.normalized().dot(normal)>.99:candidates.append((cross.length,sum(pts,Vector())/3))
    candidates.sort(key=lambda x:x[0],reverse=True);samples=[]
    for _,point in candidates:
        if all((point-q).length>.00012 for q in samples):samples.append(point)
        if len(samples)==8:break
    assert len(samples)>=2
    records['markings'].append(dict(source=source_obj.name,cutter=cutter.name,host=host.name,text=source_obj.data.body if source_obj.type=='FONT' else name,
        depth_mm=depth*1000,reference_root=rig.name,normal_local=list((inverse.to_3x3()@normal).normalized()),
        plane_point_local=list(inverse@(normal*plane)),samples_local=[list(inverse@p) for p in samples],paint_fill=True))
    print('PM_FRAME_ENGRAVING',name,depth*1000,flush=True)

records['expected_markings']=25;bpy.context.view_layer.update();fresh=engraving_report(records)
eo=host.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=eo.to_mesh();bm=bmesh.new();bm.from_mesh(mesh)
topology=dict(boundary=sum(e.is_boundary for e in bm.edges),overfull=sum(len(e.link_faces)>2 for e in bm.edges),wire=sum(e.is_wire for e in bm.edges),zero_area=sum(f.calc_area()<1e-14 for f in bm.faces))
bm.free();eo.to_mesh_clear();fresh['frame_topology']=topology;fresh['paint_fill']=paint_fill_report()
(OUT/'Проверки/frame_engraving_build.json').write_text(json.dumps(fresh,ensure_ascii=False,indent=2),encoding='utf-8')
assert fresh['pass_engraving'] and not any(topology.values()) and fresh['paint_fill']['pass_paint'],'Frame/optic actual cuts or paint failed'
records['pass_engraving']=True;records['frame_marking_count']=7;records['optic_marking_count']=18
(OUT/'Проверки/engraving.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
manifest['changes'].append('На рамке реальные утопленные КОРС-9, № КР061284, 9×18, КР · 06/24 и условные ОТК/кольцо/треугольник; светлая слегка облупившаяся эмаль на дне — отдельный нативный UCUPaint')
manifest['non_optic_geometry_unchanged']=False;manifest['base_meshes_unchanged']=True
manifest['localized_paint_authorized']='Owner explicitly requested pale chipped paint inside the new recessed frame markings'
manifest['full_surface_texturing_approval']=False
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
note=bpy.data.texts.new('КОРС-9 • клейма рамки')
note.write('Имя КОРС-9 задано владельцем. Технические клейма художественные: калибр, серийный номер, партия, условный контроль.\nБренд утоплен на 0,12 мм; мелкие клейма на 0,08 мм. Светлая эмаль/облупившиеся пятна — отдельные настоящие UCUPaint-слои на дне выемок.\nОстальной ПМ/прицел показываются в нейтральных проверочных материалах. Полный текстурный этап ещё ждёт принятия формы.\n')
S.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v09.blend'))
assert hashlib.sha256(Path(manifest['parent_geometry']).read_bytes()).hexdigest()==manifest['parent_sha256']
print('PM_KORS9_SAVED',fresh['pass_engraving'],U.common.get_current_version_str(),flush=True)
