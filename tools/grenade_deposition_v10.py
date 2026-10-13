"""Task 2 only: add causal deposition and handling masks to accepted v09.

All existing layers, masks, image pixels, manufacturing settings, geometry,
UVs, markings and rig remain. New POINT attributes describe real proximity
and orientation; they neither displace nor edit the accepted mesh.
"""
import argparse
import importlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v09_Task1_На_проверку')
SOURCE = BASE / 'Grenade_MkII_Studio_v09_Task1.blend'
OUT = ROOT / '_asset_src/grenade_codex/materials_v10_stage2'
FILE = OUT / 'Grenade_MkII_Studio_v10_Task2.blend'
PREFIX = 'V10 • '
ATTRS = ['V10_DepositRetention', 'V10_UpwardShelteredDust',
         'V10_MovingContact', 'V10_HandlingAccess']


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = load_module('grenade_surface_v09_helpers', ROOT/'tools/grenade_surface_v09.py')


def smooth(a, b, x):
    q = np.clip((x-a)/(b-a), 0, 1)
    return q*q*(3-2*q)


def tree_for(obj):
    mat = obj.active_material
    group = next(n for n in mat.node_tree.nodes if n.type == 'GROUP'
                 and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node)
    return group.node_tree


def near_surface(points, normals, other, bvh, limit):
    """Triangle proximity and facing in world metres, not normal-only noise."""
    matrix = np.asarray(other.matrix_world, dtype=np.float64)
    inverse = np.linalg.inv(matrix)
    local = points@inverse[:3,:3].T+inverse[:3,3]
    other_co = H.array(other.data.vertices,'co',3)
    lo, hi = other_co.min(0)-limit, other_co.max(0)+limit
    selected = np.nonzero(np.all((local>=lo)&(local<=hi),axis=1))[0]
    proximity = np.zeros(len(points), np.float32)
    facing = np.zeros(len(points), np.float32)
    min_distance = float('inf')
    for index in selected:
        location, normal, face, distance = bvh.find_nearest(Vector(local[index]), limit)
        if location is None:
            continue
        world = np.asarray(location)@matrix[:3,:3].T+matrix[:3,3]
        vector = world-points[index]
        world_distance = float(np.linalg.norm(vector))
        min_distance = min(min_distance,world_distance)
        proximity[index] = float(1-smooth(limit*.12,limit,world_distance))
        if world_distance > 1e-9:
            facing[index] = float(smooth(-.12,.45,np.dot(vector/world_distance,normals[index])))
    return proximity, facing, {'object':other.name,'query_vertices':len(selected),
                                'limit_mm':limit*1000,'nearest_distance_mm':min_distance*1000
                                if np.isfinite(min_distance) else None,
                                'nonzero_fraction':float(np.mean(proximity>0))}


def old_attribute(mesh,name):
    attr=mesh.color_attributes[name]
    values=H.array(attr.data,'color',4)[:,0]
    if attr.domain=='POINT':
        return values
    indices=H.array(mesh.loops,'vertex_index',1,np.int32).ravel()
    sums=np.bincount(indices,weights=values,minlength=len(mesh.vertices))
    counts=np.bincount(indices,minlength=len(mesh.vertices))
    return (sums/np.maximum(counts,1)).astype(np.float32)


def add_attribute(mesh,name,values):
    attr=mesh.color_attributes.get(name) or mesh.color_attributes.new(name=name,type='FLOAT_COLOR',domain='POINT')
    rgba=np.ones((len(mesh.vertices),4),np.float32)
    rgba[:,:3]=np.clip(values,0,1)[:,None]
    attr.data.foreach_set('color',rgba.ravel())


def geometry_masks():
    depsgraph=bpy.context.evaluated_depsgraph_get()
    objects={n:bpy.data.objects[n] for n in H.ASSETS}
    bvhs={n:BVHTree.FromObject(o,depsgraph,deform=True,cage=False) for n,o in objects.items()}
    records={}
    for name,obj in objects.items():
        mesh=obj.data
        active_color=mesh.color_attributes.active_color_name
        render_color=mesh.color_attributes.render_color_index
        matrix=np.asarray(obj.matrix_world,dtype=np.float64)
        points=H.array(mesh.vertices,'co',3).astype(np.float64)@matrix[:3,:3].T+matrix[:3,3]
        normals=H.array(mesh.vertices,'normal',3).astype(np.float64)@np.linalg.inv(matrix[:3,:3])
        normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-9)
        up=smooth(.1,.85,normals[:,2])
        recess=old_attribute(mesh,'Wear_Recess')
        contact=old_attribute(mesh,'Wear_Contact')
        queries=[]
        if name=='GrenadeBody':
            close,facing,record=near_surface(points,normals,objects['SafetyLever'],bvhs['SafetyLever'],.0030)
            queries.append(record)
            shelter=np.maximum(recess,close*facing*.65)
            moving=np.zeros(len(points),np.float32)
            handling=np.clip(contact,0,1)
            # Existing cast grooves and accessible convex grip are authoritative.
            retention=(.35+.65*shelter)*(1-.62*handling)
            dust=(.45+.55*shelter)*(1-.72*handling)*(.25+.75*up)
        elif name in {'FuzeCasting','BottomPlug'}:
            lever,facing,record=near_surface(points,normals,objects['SafetyLever'],bvhs['SafetyLever'],.0020)
            queries.append(record)
            pin,pinface,record=near_surface(points,normals,objects['SafetyPin'],bvhs['SafetyPin'],.00075)
            queries.append(record)
            body,bodyface,record=near_surface(points,normals,objects['GrenadeBody'],bvhs['GrenadeBody'],.0015)
            queries.append(record)
            shelter=np.maximum.reduce([lever*facing,body*bodyface,pin*.65])
            moving=pin*pinface
            handling=np.clip(.22+.55*(1-shelter)+.4*moving,0,1)
            retention=(.12+.88*shelter)*(1-.60*moving)
            dust=(.15+.85*shelter)*(.18+.82*up)*(1-.65*moving)
        elif name=='SafetyLever':
            body,bodyface,record=near_surface(points,normals,objects['GrenadeBody'],bvhs['GrenadeBody'],.0025)
            queries.append(record)
            head,headface,record=near_surface(points,normals,objects['FuzeCasting'],bvhs['FuzeCasting'],.0018)
            queries.append(record)
            shelter=np.maximum(body*bodyface,head*headface)
            moving=np.maximum(body*bodyface*.65,head*headface)
            # Fine dust on upper cover; inner bends retain soil, outer hold rubs.
            handling=np.clip(.12+.7*(1-shelter),0,1)
            retention=(.10+.90*shelter)*(1-.4*handling)
            dust=(.15+.85*np.maximum(shelter,up*.35))*(.18+.82*up)*(1-.5*handling)
        else:
            pairs={'PullRing':['PinEyelet'], 'PinEyelet':['PullRing','SafetyPin'],
                   'SafetyPin':['FuzeCasting','PinEyelet']}[name]
            signals=[]
            for other in pairs:
                close,facing,record=near_surface(points,normals,objects[other],bvhs[other],.00075)
                queries.append(record)
                signals.append(close*np.maximum(facing,.35))
            moving=np.maximum.reduce(signals)
            shelter=np.clip(moving,0,1)
            # Accessible upper/outward ring is handled; eyelet contact is rubbed.
            handling=np.clip(.18+.34*(1-shelter)+.65*moving,0,1)
            retention=.20+.80*shelter*(1-.45*moving)
            dust=(.1+.9*shelter)*up
        data={ATTRS[0]:retention,ATTRS[1]:dust,ATTRS[2]:np.clip(.08+.92*moving,0,1),ATTRS[3]:handling}
        used=set(ATTRS[:2]) if name=='GrenadeBody' else set(ATTRS) if name in {
            'FuzeCasting','BottomPlug','SafetyLever'} else {ATTRS[0],ATTRS[2],ATTRS[3]}
        for attr,values in data.items():
            if attr in used:
                add_attribute(mesh,attr,values)
        mesh.color_attributes.active_color_name=active_color
        mesh.color_attributes.render_color_index=render_color
        mesh.update()
        records[name]={'queries':queries,'attributes':{a:{'min':float(v.min()),'max':float(v.max()),
                                                        'mean':float(v.mean())} for a,v in data.items()}}
        print('SPATIAL_MASKS',name,records[name]['attributes'],flush=True)
    H.write_json(OUT/'checks/spatial_masks.json',records)


def vcol_mask(U,layer,attribute,label):
    return U.Mask.add_new_mask(layer,PREFIX+label,'VCOL','Object','UVMap',vcol_name=attribute)


def valley_mask(U,layer,family,height_layer,floor):
    path=OUT/'textures/deposition'/f'{family}_local_valley_retention_16.png'
    image=bpy.data.images.load(str(path),check_existing=True)
    image.colorspace_settings.name='Non-Color'
    image.pack()
    mask=U.Mask.add_new_mask(layer,PREFIX+'Local microvalleys from accepted Height','IMAGE',
                             height_layer.texcoord_type,height_layer.uv_name,image=image)
    mask.scale=height_layer.scale
    mask.translation=height_layer.translation
    mask.rotation=height_layer.rotation
    src=U.common.get_mask_source(mask)
    height_src=U.common.get_layer_source(height_layer)
    src.projection=height_src.projection
    src.projection_blend=height_src.projection_blend
    src.interpolation='Linear'
    modifier=importlib.import_module(U.__name__+'.MaskModifier')
    modifier.add_new_mask_modifier(mask,'RAMP')
    ramp=U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp].color_ramp
    ramp.elements[0].position=0
    ramp.elements[0].color=(floor,floor,floor,1)
    ramp.elements[1].position=1
    ramp.elements[1].color=(1,1,1,1)
    ramp.interpolation='LINEAR'
    return mask


def baseline(U):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    record={'source':str(SOURCE),'sha256':H.sha(SOURCE),'geometry':H.geometry_snapshot(),
            'paint':H.paint_snapshot(U),'studio':H.studio_snapshot(),'rig':H.rig_snapshot()}
    H.write_json(OUT/'checks/baseline_v09.json',record)
    print('BASELINE_V09_OK',record['sha256'],flush=True)


def patch(U):
    record=json.loads((OUT/'checks/baseline_v09.json').read_text(encoding='utf8'))
    assert H.sha(SOURCE)==record['sha256'], 'Accepted task 1 file changed'
    if FILE.exists():
        raise RuntimeError('Do not compound the same new masks by reapplying a patch')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    geometry_masks()
    added=[]
    for family,obj_name in [('body','GrenadeBody'),('head','FuzeCasting'),('lever','SafetyLever'),('wire','PullRing')]:
        obj=bpy.data.objects[obj_name]
        bpy.context.view_layer.objects.active=obj
        tree=tree_for(obj)
        if family!='wire':
            height=next(l for l in tree.yp.layers if l.name.startswith('03 • Casting')) if family=='body' else next(
                l for l in tree.yp.layers if l.name==H.FACTORY_PREFIXES[1])
            for layer in tree.yp.layers:
                number=layer.name[:2]
                if number not in {'70','72','74','76'}:
                    continue
                attr=ATTRS[1] if number in {'72','76'} else ATTRS[0]
                vcol_mask(U,layer,attr,'Shelter, orientation and cleaning' if attr==ATTRS[1] else 'Actual recess retention, reduced at rub')
                if number!='74' or family=='body':
                    valley_mask(U,layer,family,height,.32 if number=='70' else .48 if number=='72' else .42)
                added.append([tree.name,layer.name])
        if family!='body':
            for number,attr,label in [('12',ATTRS[0],'Oxide remains in sheltered contact pockets'),
                                      ('20',ATTRS[2],'Real pin and interlocking wire contact'),
                                      ('22',ATTRS[3],'Accessible handling surfaces')]:
                layer=next(l for l in tree.yp.layers if l.name.startswith(number+' •'))
                vcol_mask(U,layer,attr,label)
                added.append([tree.name,layer.name])
        H.reconnect(U,tree)
        tree['task2_deposition']='Existing layer/mask data retained; appended Height-correlated and geometry-derived constraints'
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:continue
        absolute=Path(bpy.path.abspath(image.filepath)).resolve()
        if absolute.is_relative_to(BASE.resolve()):
            destination=OUT/absolute.relative_to(BASE.resolve())
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():shutil.copy2(absolute,destination)
        elif absolute.is_relative_to(OUT.resolve()):
            destination=absolute
        else:raise RuntimeError(('Unexpected source',absolute))
        image.filepath='//'+destination.relative_to(OUT).as_posix()
        for packed in image.packed_files:packed.filepath=image.filepath
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False,compress=True)
    H.write_json(OUT/'checks/added_masks.json',added)
    print('TASK2_SAVED',FILE,flush=True)


def finish():
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    # Remove only five unused fields created by this task's first working pass.
    # No existing v09 attribute or material/mask is removed.
    for name in H.ASSETS:
        mesh=bpy.data.objects[name].data
        used=set(ATTRS[:2]) if name=='GrenadeBody' else set(ATTRS) if name in {
            'FuzeCasting','BottomPlug','SafetyLever'} else {ATTRS[0],ATTRS[2],ATTRS[3]}
        for attr_name in set(ATTRS)-used:
            attr=mesh.color_attributes.get(attr_name)
            if attr:mesh.color_attributes.remove(attr)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False,compress=True)
    print('TASK2_READY',FILE,flush=True)


def strip_ui(data):
    if isinstance(data,dict):
        return {k:strip_ui(v) for k,v in data.items() if not k.startswith('expand_')
                and k not in {'active_edit','active_edit_1','prev_active_edit_idx'}}
    if isinstance(data,list):return [strip_ui(v) for v in data]
    return data


def verify(U,path=FILE):
    base=json.loads((OUT/'checks/baseline_v09.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    geometry=H.geometry_snapshot()
    new_attributes={}
    for name,original in base['geometry'].items():
        current=geometry[name]
        extra={k:v for k,v in current['colors'].items() if k not in original['colors']}
        used=set(ATTRS[:2]) if name=='GrenadeBody' else set(ATTRS) if name in {
            'FuzeCasting','BottomPlug','SafetyLever'} else {ATTRS[0],ATTRS[2],ATTRS[3]}
        if set(extra)!=used:raise RuntimeError(('Unexpected new attribute set',name,sorted(extra)))
        new_attributes[name]=extra
        for attr in extra:del current['colors'][attr]
    geometry_diff=H.differences(base['geometry'],geometry)
    paint=H.paint_snapshot(U)
    material_diff=[];appended=[];old_masks=0
    for material,original in base['paint'].items():
        current=paint[material]
        for field in ['tree','root_channels','principled','root_links']:
            material_diff+=H.differences(strip_ui(original[field]),strip_ui(current[field]),material+'/'+field)
        if list(original['layers'])!=list(current['layers']):raise RuntimeError('Native layer order changed')
        for layer_name,old_layer in original['layers'].items():
            new_layer=current['layers'][layer_name]
            a,b=strip_ui(old_layer['props']),strip_ui(new_layer['props'])
            old=a.pop('masks');new=b.pop('masks');old_masks+=len(old)
            new_old=[m for m in new if not m['name'].startswith(PREFIX)]
            added=[m for m in new if m['name'].startswith(PREFIX)]
            material_diff+=H.differences(old,new_old,material+'/'+layer_name+'/old_masks')
            material_diff+=H.differences(a,b,material+'/'+layer_name+'/layer_settings')
            material_diff+=H.differences(old_layer['source'],new_layer['source'],material+'/'+layer_name+'/source')
            # Original masks remain at their original indices; all additions append.
            material_diff+=H.differences(old_layer['mask_sources'],new_layer['mask_sources'][:len(old)],
                                         material+'/'+layer_name+'/old_mask_sources')
            for mask in added:
                if mask['blend_type']!='MULTIPLY' or not mask['enable']:
                    raise RuntimeError(('Invalid new constraint',mask['name']))
                appended.append({'material':material,'layer':layer_name,'name':mask['name'],'type':mask['type']})
    rig_diff=H.differences(base['rig'],H.rig_snapshot())
    studio_diff=H.differences(base['studio'],H.studio_snapshot())
    images=[]
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:continue
        file=Path(bpy.path.abspath(image.filepath))
        if not image.packed_file or not file.is_file():raise RuntimeError(('Missing image',image.name))
        digest=__import__('hashlib').sha256(bytes(image.packed_file.data)).hexdigest()
        if digest!=H.sha(file):raise RuntimeError(('Packed/external mismatch',image.name))
        if 'local_valley' in image.name and image.colorspace_settings.name!='Non-Color':raise RuntimeError('Wrong color space')
        images.append({'name':image.name,'file':image.filepath,'sha256':digest,'color_space':image.colorspace_settings.name})
    result={'file':str(path),'sha256':H.sha(path),'geometry_differences':geometry_diff,
            'protected_material_differences':material_diff,'rig_differences':rig_diff,'studio_differences':studio_diff,
            'new_attributes':new_attributes,'appended_masks':appended,'retained_masks':old_masks,
            'native_stacks':len(paint),'native_layers':sum(len(v['layers']) for v in paint.values()),
            'images':images,'pass':not geometry_diff and not material_diff and not rig_diff and not studio_diff}
    H.write_json(OUT/'checks/verify_task2.json',result)
    print('TASK2_VERIFY',result['pass'],'geometry',len(geometry_diff),'materials',len(material_diff),
          'old_masks',old_masks,'new_masks',len(appended),'images',len(images),flush=True)
    for difference in (geometry_diff+material_diff+rig_diff+studio_diff)[:12]:print('DIFFERENCE',difference,flush=True)
    if not result['pass']:raise RuntimeError('Protected v09 data differs')


def render(U,version,shot,samples,pilot):
    H.OUT=OUT;H.STUDIO=SOURCE;H.CANDIDATE=FILE
    H.SHOTS['body']=((.10,-.17,.089),(.002,-.005,.043),105,1920,1920)
    H.render(U,version,shot,samples,pilot)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['baseline','patch','finish','verify','render','compare'])
    parser.add_argument('--version',choices=['before','after'],default='after')
    parser.add_argument('--shot',choices=['body','head','lever','wire'],default='head')
    parser.add_argument('--samples',type=int,default=256)
    parser.add_argument('--pilot',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    OUT.mkdir(parents=True,exist_ok=True)
    U=H.native()
    if args.mode=='baseline':baseline(U)
    elif args.mode=='patch':patch(U)
    elif args.mode=='finish':finish()
    elif args.mode=='verify':verify(U)
    elif args.mode=='render':render(U,args.version,args.shot,args.samples,args.pilot)
    elif args.mode=='compare':
        for shot in ['body','head','wire']:
            for version in ['before','after']:render(U,version,shot,args.samples,args.pilot)


if __name__=='__main__':main()
