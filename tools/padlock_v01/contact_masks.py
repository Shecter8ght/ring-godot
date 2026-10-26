"""Rasterize contact wear in millimetres onto the existing, unchanged UV atlas.

Run in Blender; conversion of the resulting arrays to PNG uses the bundled
NumPy/Pillow Python (contact_masks_png.py). No high-poly/UV rebuild or bake.
"""
import importlib.util
import json
import math
from pathlib import Path

import bpy
import numpy as np

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
SIZE=4096
OUT=WORK/'textures'/'contact_v03';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v02_texture_source.blend'))
spec=importlib.util.spec_from_file_location('padlock_profile',Path(__file__).with_name('build.py'))
profile_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile_module)
outline=np.asarray(profile_module.body_profile(),dtype=np.float32)
key_outline=np.asarray(profile_module.key_profile(),dtype=np.float32)
angle=np.arctan2(outline[:,1]-35,outline[:,0]);order=np.argsort(angle)
radius=np.sqrt(outline[:,0]**2+(outline[:,1]-35)**2)
arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(np.vstack([outline,outline[0]]),axis=0),axis=1))][:-1]
perimeter=float(arc[-1]+np.linalg.norm(outline[0]-outline[-1]))

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1)
    return t*t*(3-2*t)

def image_array(name):
    image=bpy.data.images.load(str(WORK/'textures'/'sources'/name),check_existing=True)
    image.colorspace_settings.name='Non-Color'
    values=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(values)
    result=values.reshape(image.size[1],image.size[0],4)[:,:,0].copy()
    bpy.data.images.remove(image)
    return result

# Owner alpha is sampled along the actual curved edge, not projected across its face.
edge=image_array('contact_edge.png')
def sample_alpha(u,v):
    h,w=edge.shape
    xx=np.clip(u*(w-1),0,w-1);yy=np.clip(v*(h-1),0,h-1)
    xi=xx.astype(np.int32);yi=yy.astype(np.int32)
    xf=xx-xi;yf=yy-yi
    xj=np.minimum(xi+1,w-1);yj=np.minimum(yi+1,h-1)
    return ((1-xf)*(1-yf)*edge[yi,xi]+xf*(1-yf)*edge[yi,xj]
            +(1-xf)*yf*edge[yj,xi]+xf*yf*edge[yj,xj])

def segment_distance(points,start,end):
    delta=end-start;length=float(np.dot(delta,delta))
    t=np.clip(((points-start)@delta)/max(length,1e-12),0,1)
    return np.linalg.norm(points-start-t[:,None]*delta,axis=1)

def edge_coordinates(x,z):
    a=np.arctan2(z-35,x)
    r=np.sqrt(x*x+(z-35)**2)
    boundary=np.interp(a,angle[order],radius[order],period=2*math.pi)
    # Radial separation is sufficient inside the narrow outer bevel mask.
    dist=np.maximum(0,boundary-r)
    # Angular coordinate stays continuous through the stencil's periodic repeats.
    along=(a+math.pi)/(2*math.pi)*perimeter
    return dist,along

FRONT_SCRATCHES=[((-39,35),(-34.4,37.1),.14),((35.0,22),(31.0,25),.13),
                 ((36.4,66),(33.1,64.1),.18),((-29,9),(-25.6,12.5),.10)]
BACK_SCRATCHES=[((-38,48),(-34.6,47),.13),((30,13),(27.7,17),.12)]
KEY_SCRATCHES=[((-4.6,22),(-7.2,23.2),.13),((5.0,20.3),(8.0,18.0),.15),
               ((-1.7,11),(-3.7,8.2),.11),((2.7,14.0),(4.6,12.1),.10)]

def fields(name,points):
    x,y,z=points.T
    zeros=np.zeros(len(points),np.float32)
    values=np.zeros((len(points),3),np.float32)
    if name.startswith('Shackle'):
        left=x<0;cx=np.where(left,-25.,25.)
        phi=np.arctan2(y,x-cx)
        top=np.where(left,74.4,76.9)+.65*np.sin(phi*3.0)+.22*np.sin(phi*8.0+1.7)
        base=smooth(67.9,69.7,z)*(1-smooth(top-.8,top+.3,z))
        # Broken axial tails, rather than perfectly machined silver collars.
        tails=zeros.copy()
        for centre,width in ((-2.61,.023),(-.71,.035),(-.23,.018),(.56,.028),(2.14,.020)):
            delta=np.mod(phi-centre+math.pi,2*math.pi)-math.pi
            tails=np.maximum(tails,np.exp(-(delta/width)**2))
        tail_height=np.where(left,76.6,79.3)+.18*np.sin(phi*5.)
        tails*=smooth(70.5,72.,z)*(1-smooth(tail_height-.7,tail_height,z))
        values[:,0]=np.maximum(base,tails*.82)
    elif name.startswith(('Front_cheek','Rear_cheek')):
        front=name.startswith('Front')
        facing=smooth(9.4,10.9,-y if front else y)
        d,along=edge_coordinates(x,z)
        exposure=np.clip(.20+.60*(np.abs(x)/40)**3+.40*np.exp(-((z-6)/8)**2)
                         +.30*np.exp(-((z-68)/5)**2),0,1)
        u=.08+.84*np.mod(along/32.+(0 if front else .39),1)
        stencil=sample_alpha(u,.510+d/28.)
        edge_mask=stencil*exposure*(1-smooth(.6,1.0,d))
        xz=np.column_stack((x,z))
        for desired in ((-37,30),(35,64),(27,8),(-30,15)):
            idx=int(np.argmin(np.sum((outline-np.array(desired))**2,axis=1)))
            anchor=outline[idx];tangent=outline[(idx+1)%len(outline)]-outline[(idx-1)%len(outline)]
            tangent=tangent/max(float(np.linalg.norm(tangent)),1e-7)
            along_chip=(xz-anchor)@tangent
            chip_u=.10+.80*np.clip(along_chip/4.+.5,0,1)
            chip=sample_alpha(chip_u,.510+d/70.)*(1-smooth(1.6,2.2,np.abs(along_chip)))
            edge_mask=np.maximum(edge_mask,chip*(1-smooth(.65,1.15,d)))
        for start,end,width in (FRONT_SCRATCHES if front else BACK_SCRATCHES):
            dist=segment_distance(xz,np.array(start),np.array(end))
            edge_mask=np.maximum(edge_mask,1-smooth(width*.3,width,dist))
        values[:,2]=edge_mask*facing
        if front:
            selected=(x>-8)&(x<10)&(z>5)&(z<28.5)&(y<-9.7)
            dist=np.full(len(x),100.,np.float32)
            if selected.any():
                local=xz[selected];best=np.full(len(local),100.,np.float32)
                for i,start in enumerate(key_outline):
                    best=np.minimum(best,segment_distance(local,start,key_outline[(i+1)%len(key_outline)]))
                dist[selected]=best
            ragged=.65+.17*np.sin(x*5.3+z*2.4)+.12*np.sin(z*13.4)
            key_mask=1-smooth(.14,ragged,dist)
            for start,end,width in KEY_SCRATCHES:
                gap=segment_distance(xz,np.array(start),np.array(end))
                key_mask=np.maximum(key_mask,1-smooth(width*.3,width,gap))
            values[:,1]=key_mask*facing
    elif name=='Visible_key_guide_post':
        r=np.sqrt((x-.8)**2+(z-21.1)**2)
        values[:,1]=(1-smooth(-8.4,-7.8,y))*smooth(1.3,1.8,r)*.8
    return np.clip(values,0,1)

masks=np.zeros((3,SIZE,SIZE),np.float32)
parts=[o for o in bpy.data.objects if o.get('stage')=='accepted_shape_highpoly_texture_copy'
       and o.name.startswith(('Front_cheek','Rear_cheek','Shackle','Visible_key'))]
for obj in parts:
    mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data
    world=np.asarray([tuple(obj.matrix_world@v.co) for v in mesh.vertices],dtype=np.float32)*1000
    for triangle in mesh.loop_triangles:
        tex=np.asarray([tuple(uv[i].uv) for i in triangle.loops],dtype=np.float64)
        tex[:,0]*=SIZE;tex[:,1]=(1-tex[:,1])*SIZE
        a,b,c=tex;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-7:continue
        low=np.maximum(0,np.floor(tex.min(axis=0)).astype(int));high=np.minimum(SIZE-1,np.ceil(tex.max(axis=0)).astype(int))
        if np.any(high<low):continue
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]
        px=xx.ravel()+.5;py=yy.ravel()+.5
        w0=((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/den
        w1=((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/den
        w2=1-w0-w1;inside=(w0>=-1e-6)&(w1>=-1e-6)&(w2>=-1e-6)
        if not inside.any():continue
        bary=np.column_stack((w0[inside],w1[inside],w2[inside]))
        points=bary@world[list(triangle.vertices)]
        vals=fields(obj.name,points)
        rows=yy.ravel()[inside];cols=xx.ravel()[inside]
        for channel in range(3):
            masks[channel,rows,cols]=np.maximum(masks[channel,rows,cols],vals[:,channel])
    print('CONTACT_UV_RASTERIZED',obj.name,flush=True)

for i,name in enumerate(('shackle','keyhole','body_edges')):
    np.save(OUT/(name+'.npy'),masks[i])
    print('CONTACT_PIXELS',name,int(np.count_nonzero(masks[i]>.05)),flush=True)
(WORK/'checks'/'contacts_v03.json').write_text(json.dumps({
    'resolution':SIZE,'method':'Existing UV triangles, barycentric world coordinates in millimetres',
    'geometry_changed':False,'shackle_wear_upper_mm':{'left':74.4,'right':76.9},
    'keyhole_wear_rim_mm':'.14 to approximately .65, plus directional key scratches',
    'body_wear':'Owner interrupted edge alpha follows the outer profile; six localized scratches',
    'baseline':'v02 retained; no global rust color or height changes',
},ensure_ascii=False,indent=2),encoding='utf-8')
