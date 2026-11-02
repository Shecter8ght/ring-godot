"""Reopen a saved geometry candidate, set diagnostic lighting, render inspection views."""
import argparse
import math
import pathlib
import sys
import bpy
from mathutils import Vector

p=argparse.ArgumentParser()
p.add_argument('--out',required=True)
p.add_argument('--views',default='01,02,03,04,05,06,07,08,09,10')
p.add_argument('--save',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=pathlib.Path(a.out)
scene=bpy.context.scene
scene.cycles.samples=40
if scene.world.name=='Neutral inspection world':
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.25
base=bpy.data.collections['01 • ДОЗОР Ф-1 • master shape']
variants=[bpy.data.collections['02 • ДОЗОР Ф-1М • shared housing'],bpy.data.collections['03 • ДОЗОР Ф-1С • shared housing']]
mount=bpy.data.collections['04 • ДОЗОР-П • independent Picatinny mount']
mr=bpy.data.objects['DOZOR_P_ROOT'];cap=bpy.data.objects['P.CAP_HINGE']
cam=scene.camera
def aim(target):cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
views={
'01':('01_flashlight_34',(-.055,-.17,.175),(.071,0,.035),.183,[base.name],False,False),
'02':('02_side',(.071,-.24,.035),(.071,0,.035),.177,[base.name],False,False),
'03':('03_optics',(-.050,-.07,.075),(.014,0,.035),.060,[base.name],False,False),
'04':('04_tail',(.19,-.075,.105),(.132,0,.035),.054,[base.name],False,False),
'05':('05_mount',(.018,-.145,.110),(.0805,-.064,.030),.110,[mount.name],False,False),
'06':('06_assembly',(-.025,-.15,.145),(.073,0,.027),.182,[base.name,mount.name],True,False),
'07':('07_ring_open',(.020,-.14,.130),(.0805,-.064,.047),.155,[mount.name],False,True),
'08':('08_family',(-.045,-.23,.265),(.070,.058,.034),.240,[base.name,*[c.name for c in variants]],False,False),
'09':('09_front',(-.1,0,.035),(.010,0,.035),.075,[base.name],False,False),
'10':('10_picatinny',(.018,-.145,.110),(.0805,-.064,.030),.110,[mount.name],False,False),
'11':('11_marking_surface',(.019,0,.12),(.019,0,.051),.047,[base.name],False,False),
'12':('12_marking_raking',(.025,.095,.105),(.019,0,.050),.047,[base.name],False,False),
'13':('13_grip_contact',(.080,-.095,.125),(.080,0,.040),.066,[base.name],False,False),
}
if a.save:
    # Update the saved studio only; ensure all mesh variants remain visible in the file.
    for c in [base,*variants,mount]:c.hide_render=False
    mr.location.y=-.064;cap.rotation_euler.z=0
    cam.location=(-.10,-.22,.235);aim((.07,.03,.035));cam.data.ortho_scale=.27
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
for key in a.views.split(','):
    name,loc,target,scale,visible,assembly,opened=views[key]
    for c in [base,*variants,mount]:c.hide_render=c.name not in visible
    mr.location.y=0 if assembly else -.064
    for ob in base.objects:
        if ob.name.startswith('F1.Clip.'):ob.hide_render=assembly
    cap.rotation_euler.z=math.radians(-65) if opened else 0
    rail=bpy.data.objects.get('Review.Picatinny_coupon')
    if rail:
        rail.hide_render=key!='10'
    cam.location=loc;aim(target);cam.data.ortho_scale=scale
    scene.render.filepath=str(out/'renders'/(name+'.png'))
    bpy.context.view_layer.update()
    print('RENDER',name,flush=True)
    bpy.ops.render.render(write_still=True)
print('REVIEW COMPLETE',flush=True)
