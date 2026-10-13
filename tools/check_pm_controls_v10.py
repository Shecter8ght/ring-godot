"""Fresh saved geometry evidence for the four v10 control corrections."""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def tree(o):
    eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
    t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return t

def bounds(o):
    eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();v=[eo.matrix_world@p.co for p in me.vertices];eo.to_mesh_clear()
    return [min(p[i] for p in v)*1000 for i in range(3)],[max(p[i] for p in v)*1000 for i in range(3)]

def inspect_controls(details):
    rig=bpy.data.objects['PM_CONTROLS • select me'];S=bpy.context.scene
    def pose(**values):
        for k,v in values.items():rig[k]=float(v)
        rig.update_tag();S.frame_set(S.frame_current);bpy.context.view_layer.update()
    pose(MagCatch=0,Magazine=0,Safety=0,SlideStop=0)
    shoe=bpy.data.objects[details['rail']['main_shoe']];st=tree(shoe)
    collision=[]
    for o in bpy.data.objects:
        if o.name.startswith('Mount | chamfered rail tooth'):
            n=len(st.overlap(tree(o)));collision.append(dict(tooth=o.name,surface_intersections=n))
    rail=dict(collision=collision,internal_prongs=[o.name for o in bpy.data.objects if o.name.startswith('Reflex | K1 internal rail fitting pad')],width_mm=details['rail']['width_mm'])
    rail['pass']=not rail['internal_prongs'] and not any(r['surface_intersections'] for r in collision) and 18<rail['width_mm']<22
    thumb=bpy.data.objects[details['magcatch']['thumb']];floor=bpy.data.objects[details['magcatch']['floorplate']];lip=bpy.data.objects[details['magcatch']['lip']]
    tl,th=bounds(thumb);fl,fh=bounds(floor);ll,lh=bounds(lip);closed_center=thumb.matrix_world@Vector(thumb.bound_box[0])
    catch=dict(protrusion_below_floorplate_mm=fl[2]-tl[2],lip_under_floorplate_gap_mm=fl[2]-lh[2],lip_overlap_x_mm=fh[0]-ll[0])
    pose(MagCatch=1);rl,rh=bounds(lip);released_center=thumb.matrix_world@Vector(thumb.bound_box[0]);catch['release_delta_mm']=[(released_center-closed_center)[i]*1000 for i in range(3)]
    catch['released_lip_clearance_x_mm']=rl[0]-fh[0]
    catch['pass']=3<catch['protrusion_below_floorplate_mm']<4 and .01<catch['lip_under_floorplate_gap_mm']<.25 and catch['lip_overlap_x_mm']>1 and catch['released_lip_clearance_x_mm']>.25 and catch['release_delta_mm'][0]>2
    pose(MagCatch=0)
    # Recessed flute bottoms are measured against the original curved envelope.
    t=tree(thumb);grooves=[];cx,_,cz=details['magcatch']['arc_center_mm'];R=details['magcatch']['radius_mm']
    for a in details['magcatch']['groove_centers']:
        n=Vector((math.cos(a),0,math.sin(a)));p=Vector(((cx+R*n.x)/1000,0,(cz+R*n.z)/1000));hit,_,_,_=t.ray_cast(p+n*.001,-n,.003)
        d=(p-hit).dot(n)*1000 if hit else None;grooves.append(d)
    catch['groove_depths_mm']=grooves;catch['pass']=catch['pass'] and all(d is not None and .30<d<.50 for d in grooves)
    leaf=bpy.data.objects[details['slidestop']['leaf']];t=tree(leaf);cut_depth=[]
    for row in details['slidestop']['groove_samples']:
        n=Vector(row['normal']);p=Vector(row['point_mm'])/1000;hit,_,_,_=t.ray_cast(p+n*.001,-n,.003)
        d=(p-hit).dot(n)*1000 if hit else None;cut_depth.append(dict(slot=row['slot'],depth_mm=d,pass_depth=d is not None and .12<d<.24))
    tip=Vector(leaf.bound_box[0]);a=leaf.matrix_world@tip;pose(SlideStop=1);b=leaf.matrix_world@tip;pose(SlideStop=0)
    stop=dict(grooves=cut_depth,tip_delta_z_mm=(b.z-a.z)*1000)
    stop['pass']=len({r['slot'] for r in cut_depth})==5 and all(r['pass_depth'] for r in cut_depth) and stop['tip_delta_z_mm']<-.5
    # Rays at interior points of the real shell pocket establish its depth.
    t=tree(bpy.data.objects['Slide | continuous crown, rounded muzzle & rear']);samples=[]
    rows=details['safety']['floor_samples'];N=len(details['safety']['pocket'])
    for j in range(1,len(rows)-N,max(1,N//7)):
        row=rows[j];p=Vector(row['point_mm'])/1000;hit,_,_,_=t.ray_cast(p+Vector((0,-.003,0)),Vector((0,1,0)),.010)
        depth=(hit.y-p.y)*1000 if hit else None;samples.append(dict(depth_mm=depth,target_mm=row['depth_mm'],pass_depth=depth is not None and .3*row['depth_mm']<depth<max(.85,row['depth_mm']*1.5)))
    collisions=[]
    shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear'];pad=bpy.data.objects[details['safety']['pad']];flag=bpy.data.objects[details['safety']['flag']]
    for i in range(11):
        value=i/10;pose(Safety=value);body=tree(shell)
        collisions.append(dict(value=value,pad_intersections=len(body.overlap(tree(pad))),flag_intersections=len(body.overlap(tree(flag)))))
    pose(Safety=0)
    safety=dict(samples=samples,full_stroke=collisions);safety['pass']=bool(samples) and all(r['pass_depth'] for r in samples) and not any(r['pad_intersections'] or r['flag_intersections'] for r in collisions)
    return dict(rail=rail,magcatch=catch,slidestop=stop,safety=safety,pass_controls=rail['pass'] and catch['pass'] and stop['pass'] and safety['pass'])
