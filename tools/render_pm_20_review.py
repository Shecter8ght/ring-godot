"""Unsaved neutral and opposite-grazing stills of the PM 20% revision."""
from pathlib import Path
import sys,argparse,os,json
import bpy,addon_utils
from mathutils import Vector
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v02'
ap=argparse.ArgumentParser();ap.add_argument('--file',required=True);ap.add_argument('--views',default='metal,grip');ap.add_argument('--lights',default='neutral,left,right');ap.add_argument('--prefix',default='study');ap.add_argument('--samples',type=int,default=48);ap.add_argument('--fingerprint-diagnostic',action='store_true')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
for sub in ('work/optix_cache','work/cuda_cache'):(ROOT/sub).mkdir(parents=True,exist_ok=True)
os.environ['OPTIX_CACHE_PATH']=str(ROOT/'work/optix_cache');os.environ['CUDA_CACHE_PATH']=str(ROOT/'work/cuda_cache')
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=args.file)
sys.path.insert(0,str(PROJECT/'tools'));from pm_engraving_geometry import cache_engraving_preview
cache_engraving_preview()
S=bpy.context.scene;S.frame_set(1);S.render.engine='CYCLES';S.cycles.samples=args.samples;S.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type!='CPU'
S.cycles.device='GPU';S.cycles.max_bounces=16;S.cycles.transmission_bounces=12
S.render.resolution_x=1400;S.render.resolution_y=1000;S.render.resolution_percentage=100
S.render.image_settings.file_format='PNG';S.render.film_transparent=False;S.view_settings.exposure=-.5
for o in bpy.data.objects:
    if o.type=='LIGHT' or o.name.startswith(('Reference','Animation |','Studio |')):o.hide_render=True
# A simple neutral studio lets material variation carry the appearance.
w=bpy.data.worlds.new('QA neutral environment');w.use_nodes=True
bg=next(n for n in w.node_tree.nodes if n.type=='BACKGROUND');bg.inputs['Color'].default_value=(.15,.15,.15,1);bg.inputs['Strength'].default_value=.65;S.world=w
if args.fingerprint_diagnostic:
    # Actual native Roughness output, isolated and amplified only in this
    # unsaved QA process. This is not a render of a hand-painted diagnostic mask.
    for mat in bpy.data.materials:
        if not mat.use_nodes:continue
        groups=[n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node]
        if not groups:continue
        node=groups[0];tree=node.node_tree
        for l in tree.yp.layers:l.enable=l.name.startswith('00 •') or any(k in l.name for k in ('Масляные отпечатки','Широкие следы ладони','Следы вытянутого указательного'))
        base=next((l for l in tree.yp.layers if l.name.startswith('00 •')),None)
        if base is None:continue
        idx=next(i for i,c in enumerate(tree.yp.channels) if c.name=='Roughness')
        baseline=base.channels[idx].override_value
        subtract=mat.node_tree.nodes.new('ShaderNodeMath');subtract.operation='SUBTRACT';subtract.inputs[0].default_value=baseline
        amplify=mat.node_tree.nodes.new('ShaderNodeMath');amplify.operation='MULTIPLY';amplify.inputs[1].default_value=7.
        emit=mat.node_tree.nodes.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=1.
        output=next(n for n in mat.node_tree.nodes if n.type=='OUTPUT_MATERIAL')
        mat.node_tree.links.new(node.outputs['Roughness'],subtract.inputs[1]);mat.node_tree.links.new(subtract.outputs[0],amplify.inputs[0]);mat.node_tree.links.new(amplify.outputs[0],emit.inputs['Color']);mat.node_tree.links.new(emit.outputs[0],output.inputs['Surface'])
cam=bpy.data.objects['CHECK 01 | Complete PM and separate sight'];cam.data.type='ORTHO';cam.data.clip_start=.0001;cam.data.clip_end=10;S.camera=cam
def area(name,loc,energy,size,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);S.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
views={
 'metal':((-.105,-.20,.157),(-.023,-.008,.108),.135),
 'ejection':((-.07,.19,.164),(-.018,.005,.107),.137),
 'grip':((.079,-.20,.081),(.052,-.008,.047),.127),
 'hammer':((.120,-.090,.156),(.067,-.008,.111),.057),
 'trigger':((-.068,.086,.098),(-.012,0,.081),.053),
 'index':((-.079,.135,.126),(-.016,.009,.094),.103),
 'frame':((-.02,-.20,.116),(.023,-.006,.088),.129),
 'left':((-.18,-.42,.224),(-.002,0,.084),.258),
 'right':((-.19,.42,.224),(-.002,0,.084),.258),
 'top':((-.18,-.05,.35),(-.002,0,.117),.232),
}
out=REV/'images';out.mkdir(parents=True,exist_ok=True)
for v in args.views.split(','):
    eye,target,scale=views[v];cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    for lighting in args.lights.split(','):
        active=[]
        if lighting=='neutral':
            active.append(area('QA soft key',(-.06,-.21,.30),8,.18,target))
            active.append(area('QA soft fill',(.10,.16,.23),4,.18,target))
            active.append(area('QA reflected front card',(-.14,-.13,.10),1.4,.10,target))
        else:
            sign=-1 if lighting=='left' else 1
            active.append(area('QA grazing strip',(-.13,sign*.075,.155),5,.045,target))
            active.append(area('QA weak fill',(.13,-sign*.17,.22),1.2,.19,target))
        path=out/f'PM_20_v02_{args.prefix}_{v}_{lighting}.png';S.render.filepath=str(path)
        bpy.ops.render.render(write_still=True);print('PM_REVIEW_STILL',path,flush=True)
        for o in active:o.hide_render=True
print('PM_20_REVIEW_DONE',flush=True)
