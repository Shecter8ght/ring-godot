"""Independent ray evidence after reopening: walls, cut valleys, both shoulders."""
import bpy,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
 t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return t

def inspect_body(details):
 rig=bpy.data.objects['PM_CONTROLS • select me'];S=bpy.context.scene
 for key in ('Slide','Hammer','Safety','Magazine','MagCatch','SlideStop'):rig[key]=0.
 rig.update_tag();S.frame_set(S.frame_current);bpy.context.view_layer.update()
 mw=rig.matrix_world;grip=tree(bpy.data.objects['Bakelite | one-piece rounded grip']);walls=[]
 for row in details['grip']['wall_samples']:
  p=mw@Vector(row['point']);d=(mw.to_3x3()@Vector(row['direction'])).normalized()
  hit=grip.ray_cast(p,d,1)[0];inner=grip.ray_cast(hit+d*.000002,d,.02)[0] if hit else None
  original=(mw@Vector(row['inner'])-mw@Vector(row['outer'])).length
  thick=(inner-hit).length if inner else None;ratio=thick/original if thick else None
  walls.append(dict(point_mm=list(p*1000),original_mm=original*1000,new_mm=thick*1000 if thick else None,ratio=ratio,outer_delta_mm=(hit-mw@Vector(row['outer'])).length*1000 if hit else None,pass_wall=ratio is not None and .44<ratio<.57 and (hit-mw@Vector(row['outer'])).length<.000025))
 shell=tree(bpy.data.objects['Slide | continuous crown, rounded muzzle & rear']);bands=[]
 # Compare lands to adjacent cut bottoms at top, middle and lower opening.
 # The slanted cutter has the original -0.205 rad inclination.
 for sy in (-1,1):
  for z in (1.230,1.300,1.398):
   for i in (2,6,10):
    x=.175+i*.034-math.tan(.205)*(z-1.310)
    ys=[]
    for xx in (x,x+.015):
     p=mw@Vector((xx,sy*.4,z));d=(mw.to_3x3()@Vector((0,-sy,0))).normalized();h=shell.ray_cast(p,d,.10)[0]
     ys.append(abs(h.y)*1000 if h else None)
    depth=ys[1]-ys[0] if all(v is not None for v in ys) else None
    bands.append(dict(side=sy,height_mm=(mw@Vector((0,0,z))).z*1000,cut_depth_mm=depth,land_y_mm=ys[1],pass_band=depth is not None and .30<depth<1.5 and ys[1]>12.5))
 hammer=tree(bpy.data.objects['Hammer | rounded spur with broad side chamfers']);crest=[]
 for i in range(121):
  x=.887+i*.111/120;p=mw@Vector((x,0,1.7));d=Vector((0,0,-1));h=hammer.ray_cast(p,d,.06)[0]
  if h:crest.append([x,h.z*1000])
 # Five separated depressions must cross the thumb crown. Valleys are deeper
 # than the smooth crest, independently of the five stored design parameters.
 valleys=[]
 for i in range(1,len(crest)-1):
  if crest[i][1]<crest[i-1][1]-.00005 and crest[i][1]<=crest[i+1][1]:
   if not valleys or crest[i][0]-valleys[-1][0]>.005:valleys.append(crest[i])
 hrow=dict(measured_valleys=valleys,crest=crest,pass_hammer=len(valleys)==5)
 return dict(walls=walls,serration_bands=bands,hammer=hrow,pass_body=bool(walls) and all(r['pass_wall'] for r in walls) and all(r['pass_band'] for r in bands) and hrow['pass_hammer'])
