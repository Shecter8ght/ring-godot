"""Map missed interior bake rays to LP pieces; verify outward mesh orientation."""
import bpy,bmesh,pathlib,json,sys,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
bpy.ops.wm.open_mainfile(filepath=str(WORK/'dozor_lp.blend'))
report={}
def pixels(path):
    im=bpy.data.images.load(str(path));im.colorspace_settings.name='Non-Color'
    a=np.empty(im.size[0]*im.size[1]*4,np.float32);im.pixels.foreach_get(a);return a.reshape(im.size[1],im.size[0],4)[...,0]
for key in ('F1','P'):
    u=pixels(WORK/('uv_coverage_'+key+'.png'))>.5;hit=pixels(WORK/('hit_coverage_'+key+'.png'))>.5
    for k in range(2):u=u&np.roll(u,1,0)&np.roll(u,-1,0)&np.roll(u,1,1)&np.roll(u,-1,1)
    bad=u&~hit;size=SIZES[key]
    for o in bpy.data.objects:
        if o.type!='MESH' or not o.name.startswith('LP__'+key+'.'):continue
        bm=bmesh.new();bm.from_mesh(o.data);volume=bm.calc_volume(signed=True);bm.free()
        me=o.data;me.calc_loop_triangles();uv=me.uv_layers['GameUV'];n=0
        for tri in me.loop_triangles:
            t=np.array([tuple(uv.data[i].uv) for i in tri.loops])*size-.5
            x0=max(0,int(np.ceil(t[:,0].min())));x1=min(size-1,int(np.floor(t[:,0].max())))
            y0=max(0,int(np.ceil(t[:,1].min())));y1=min(size-1,int(np.floor(t[:,1].max())))
            if x1<x0 or y1<y0:continue
            yy,xx=np.nonzero(bad[y0:y1+1,x0:x1+1]);yy+=y0;xx+=x0
            if not len(xx):continue
            d=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(d)<1e-12:continue
            a=((t[1,1]-t[2,1])*(xx-t[2,0])+(t[2,0]-t[1,0])*(yy-t[2,1]))/d
            b=((t[2,1]-t[0,1])*(xx-t[2,0])+(t[0,0]-t[2,0])*(yy-t[2,1]))/d
            n+=int(((a>=0)&(b>=0)&(a+b<=1)).sum())
        report[o.name]={'missed_interior_pixels':n,'signed_volume_m3':volume}
(WORK/'projection-by-piece.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('MISS / INWARD',[(k,v) for k,v in report.items() if v['missed_interior_pixels'] or v['signed_volume_m3']<0],flush=True)
