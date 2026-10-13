"""Independent saved-mesh evidence for the v11 repairs."""
import math,bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from check_pm_controls_v10 import inspect_controls

def tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return t
def inside(p,poly):
 yes=False
 for i,a in enumerate(poly):
  b=poly[(i+1)%len(poly)]
  if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:yes=not yes
 return yes
def distance(p,poly):
 p=Vector(p);best=1e6
 for i,aa in enumerate(poly):
  a=Vector(aa);b=Vector(poly[(i+1)%len(poly)]);d=b-a;t=max(0,min(1,(p-a).dot(d)/d.length_squared));best=min(best,(p-a-t*d).length)
 return best
def inspect_repairs(details,control_details):
 rig=bpy.data.objects['PM_CONTROLS • select me'];S=bpy.context.scene
 for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop'):rig[key]=0.
 rig.update_tag();S.frame_set(S.frame_current);bpy.context.view_layer.update()
 frame=bpy.data.objects['Frame | traced flowing silhouette'];eo=frame.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();normal_matrix=eo.matrix_world.to_3x3().inverted().transposed();samples=[]
 for p in me.polygons:
  if abs(p.normal.y)<.99999 or not all(abs(abs(me.vertices[j].co.y)-.134)<3e-6 for j in p.vertices):continue
  target=Vector((0,1 if p.normal.y>0 else -1,0))
  angles=[math.degrees(math.acos(max(-1,min(1,(normal_matrix@me.corner_normals[j].vector).normalized().dot(target))))) for j in p.loop_indices]
  samples.append(max(angles))
 eo.to_mesh_clear();flat=dict(cap_faces=len(samples),maximum_shading_angle_deg=max(samples) if samples else None);flat['pass']=bool(samples) and max(samples)<.2
 rail=bpy.data.objects[details['rail']['rail']];shoe=bpy.data.objects[control_details['rail']['main_shoe']]
 rail_row=dict(objects_with_old_tooth_sheets=[o.name for o in bpy.data.objects if o.name.startswith('Mount | chamfered rail tooth')],shoe_intersections=len(tree(rail).overlap(tree(shoe))),merged_teeth=details['rail']['merged_teeth'])
 rail_row['pass']=not rail_row['objects_with_old_tooth_sheets'] and rail_row['shoe_intersections']==0 and rail_row['merged_teeth']==7
 pad=tree(bpy.data.objects[details['safety_pad']['pad']]);poly=[(50.85,107.65),(52.1,107.30),(57.1,110.50),(57.6,111.55),(56.5,112.10),(51.05,109.1)];bands=[]
 for i,row in enumerate(details['safety_pad']['bands']):
  measurements=[];z=row['z_mm']
  for j in range(23):
   x=50.9+j*.28
   if not inside((x,z),poly) or distance((x,z),poly)<.23:continue
   y=-(15.45+max(0,min(1,(57.2-x)/6.3))*1.9);p=Vector((x,y,z))/1000;h=pad.ray_cast(p+Vector((0,-.001,0)),Vector((0,1,0)),.004)[0]
   depth=(h.y-p.y)*1000 if h else None;measurements.append(depth)
  bands.append(dict(index=i,depths_mm=measurements,pass_band=bool(measurements) and all(d is not None and .30<d<.46 for d in measurements)))
 hammer=tree(bpy.data.objects['Hammer | rounded spur with broad side chamfers']);cx,cz=details['hammer']['center_xz_mm'];slots=[]
 for i,row in enumerate(details['hammer']['grooves']):
  a=math.radians(row['angle_deg']);d=Vector((math.cos(a),0,math.sin(a)));values=[]
  for y in (-1.4,0,1.4):
   c=Vector((cx,y,cz))/1000;h=hammer.ray_cast(c+d*((row['radius_mm']+.5)/1000),-d,.012)[0]
   depth=row['radius_mm']-(h-c).dot(d)*1000 if h else None;values.append(depth)
  slots.append(dict(index=i,angle_deg=row['angle_deg'],depths_mm=values,pass_slot=all(d is not None and 1.22<d<1.45 for d in values)))
 screws=[]
 for row in details['drives']:
  o=bpy.data.objects[row['object']];n=Vector(row['normal']);c=Vector(row['center_mm'])/1000;start=c+n*(row['front_mm']/1000-c.dot(n)+.001)
  h=tree(o).ray_cast(start,-n,.006)[0];depth=row['front_mm']-h.dot(n)*1000 if h else None
  screws.append(dict(object=o.name,old_depth_mm=row['old_depth_mm'],new_depth_mm=depth,target_mm=row['new_depth_mm'],pass_screw=depth is not None and abs(depth-row['new_depth_mm'])<.035 and depth>row['old_depth_mm']+.09))
 inherited=inspect_controls(control_details)
 checks=dict(frame_normals=flat,rail=rail_row,horizontal_safety_bands=bands,radial_hammer_slots=slots,screw_drives=screws,inherited_controls=inherited,pocket_beveled_edges=details['safety_pocket']['beveled_edges'])
 checks['pass_repairs']=flat['pass'] and rail_row['pass'] and all(r['pass_band'] for r in bands) and len(slots)==5 and all(r['pass_slot'] for r in slots) and len(screws)==13 and all(r['pass_screw'] for r in screws) and inherited['pass_controls'] and details['safety_pocket']['beveled_edges']>0
 return checks
