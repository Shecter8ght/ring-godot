"""Project authored millimetre layouts onto the unchanged high-poly UV surface."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np

SCRIPT=Path(__file__).resolve().parent;sys.path.insert(0,str(SCRIPT))
from uv_mask_raster import rasterize
WORK=SCRIPT.parents[1]/'_asset_src'/'padlock_v01'
SOURCE=WORK/'textures'/'authored_v05';OUT=WORK/'textures'/'fields_v05';OUT.mkdir(exist_ok=True)
layout=json.loads((SOURCE/'layout.json').read_text(encoding='utf-8'));domains=layout['domains_mm']
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v02_texture_source.blend'))
spec=importlib.util.spec_from_file_location('padlock_shape_v05',SCRIPT/'build.py')
shape=importlib.util.module_from_spec(spec);spec.loader.exec_module(shape)
outline=np.asarray(shape.body_profile());angles=np.arctan2(outline[:,1]-35,outline[:,0]);order=np.argsort(angles)
radii=np.linalg.norm(outline-np.array([0,35]),axis=1)
cache={}

def load(name):
    if name not in cache:
        im=bpy.data.images.load(str(SOURCE/(name+'.png')));im.colorspace_settings.name='Non-Color'
        buf=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(buf)
        cache[name]=buf.reshape(im.size[1],im.size[0],4)[:,:,0].copy();bpy.data.images.remove(im)
    return cache[name]
for domain in ('front','rear','band'):
    for suffix in ('enamel','oxide_tone','varnish_wear'):load(domain+'_'+suffix)
for name in ('front_key_steel','front_key_pits','front_key_scratches','shackle_steel','shackle_enamel','shackle_variation'):load(name)

def sample(name,x,z,domain):
    image=load(name);x0,x1,z0,z1=domains[domain];h,w=image.shape
    xx=np.clip((x-x0)/(x1-x0)*(w-1),0,w-1);yy=np.clip((z-z0)/(z1-z0)*(h-1),0,h-1)
    i=xx.astype(np.int32);j=yy.astype(np.int32);fx=xx-i;fy=yy-j
    ii=np.minimum(i+1,w-1);jj=np.minimum(j+1,h-1)
    return image[j,i]*(1-fx)*(1-fy)+image[j,ii]*fx*(1-fy)+image[jj,i]*(1-fx)*fy+image[jj,ii]*fx*fy
def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def edge_data(x,z):
    a=np.arctan2(z-35,x);r=np.sqrt(x*x+(z-35)**2)
    boundary=np.interp(a,angles[order],radii[order],period=2*math.pi)
    return np.maximum(0,boundary-r),a

NAMES=['enamel_coverage','oxide_tone','varnish_wear','contact_steel','key_pits','key_scratches',
       'corner_grime','corner_dust','enamel_brush_height','shackle_enamel_coverage']
pins=[(-29.3,60.8,3.1),(-10.1,59.,3.2),(29.4,64.8,3.1),(-21.2,10.4,2.65),(22.1,11.2,2.65)]
edge_contacts=[(-38,46,4.8,.8),(-36,65,3.,.7),(-30,11,3.2,.9),(-8,1.1,3.,.65),
               (24,7.5,3.8,.7),(38,31,4.,.9),(38,58,3.4,.7),(35,69,2.8,.6)]

def fields(name,p,normals):
    x,y,z=p.T;v=np.zeros((len(p),len(NAMES)),np.float32);v[:,1:3]=.5;v[:,8]=.5
    if name.startswith(('Front_cheek','Rear_cheek','Body_perimeter')):
        front=name.startswith('Front');back=name.startswith('Rear');band=name.startswith('Body')
        d,a=edge_data(x,z)
        if band:
            s=(a+math.pi)/(2*math.pi)*240.
            for i,suffix in ((0,'enamel'),(1,'oxide_tone'),(2,'varnish_wear')):v[:,i]=sample('band_'+suffix,s,y,'band')
            facing=np.ones(len(x))
        else:
            domain='front' if front else 'rear';facing=smooth(9.4,10.8,-y if front else y)
            for i,suffix in ((0,'enamel'),(1,'oxide_tone'),(2,'varnish_wear')):v[:,i]=sample(domain+'_'+suffix,x,z,domain)
            v[:,0]*=facing
        # Individually chosen contacts, clipped to actual outside boundary.
        wear=np.zeros(len(x))
        for cx,cz,span,width in edge_contacts:
            near=np.exp(-(((x-cx)**2+(z-cz)**2)/(span*span))**2)
            strip=1-smooth(width*.35,width,d)
            wear=np.maximum(wear,near*strip)
        if band:wear*=smooth(7.4,9.3,np.abs(y))
        else:wear*=facing
        v[:,3]=wear
        seam=np.exp(-((np.abs(y)-9.15)/.48)**2)*(1-smooth(.5,2.,d))
        pockets=np.zeros(len(x))
        if not band:
            for px,pz,r in pins+([] if front else [(16,33.6,2.4),(-1.2,17.3,2.7)]):
                ring=np.exp(-((np.hypot(x-px,z-pz)-r)/.55)**2)
                pockets=np.maximum(pockets,ring*facing)
        notch=np.exp(-(x/10.)**4-((z-62.0)/1.15)**2)*np.exp(-(y/8.5)**8)
        sockets=np.maximum(np.exp(-((np.hypot(x-25,y)-6.6)/.55)**2),
                           np.exp(-((np.hypot(x+25,y)-6.6)/.55)**2))*np.exp(-((z-69.4)/1.2)**2)
        protected=np.maximum.reduce((seam,pockets,notch,sockets))
        v[:,6]=protected*(1-wear*.85)
        v[:,7]=protected*(.15+.85*smooth(0.,.65,normals[:,2]))*(1-wear)
        # Very shallow, deliberately broad finish undulation, not sinusoidal ridges.
        v[:,8]=.5+.0014*(v[:,2]-.5)
        if front:
            keygate=(x>-11)&(x<12)&(z>3)&(z<30)
            v[:,3]=np.maximum(v[:,3],sample('front_key_steel',x,z,'front')*facing*keygate)
            v[:,4]=sample('front_key_pits',x,z,'front')*facing*keygate
            v[:,5]=sample('front_key_scratches',x,z,'front')*facing*keygate
    elif name.startswith('Shackle'):
        left=x<0;cx=np.where(left,-25.,25.)
        s=(np.arctan2(y,x-cx)+math.pi)/(2*math.pi)*39.
        s=np.where(left,np.mod(39.-s+3.7,39.),s)
        gate=smooth(67.6,69.0,z)*(1-smooth(np.where(left,75.2,77.7),np.where(left,76.4,79.),z))
        v[:,3]=sample('shackle_steel',s,z,'shackle')*gate
        v[:,0]=sample('shackle_enamel',s,z,'shackle')*gate*(1-v[:,3])
        v[:,9]=v[:,0]
        v[:,1]=sample('shackle_variation',s,z,'shackle')
        v[:,2]=v[:,1]
        v[:,6]=np.exp(-((z-69.2)/.40)**2)*(1-v[:,3])*.65
    elif name=='Visible_key_guide_post':
        r=np.hypot(x-.8,z-21.1)
        v[:,3]=(1-smooth(-8.3,-7.8,y))*(.45+.55*smooth(.8,2.,r))
    else:
        v[:,1]=.42
        v[:,6]=.10;v[:,7]=.05*smooth(0,.7,normals[:,2])
    return np.clip(v,0,1)

parts=[o for o in bpy.data.objects if o.get('stage')=='accepted_shape_highpoly_texture_copy' and not o.name.endswith(('_shaft','_seat'))]
rasterize(parts,fields,NAMES,OUT)
(WORK/'checks'/'v05_fields.json').write_text(json.dumps({'fields':NAMES,'geometry_changed':False,
    'source_layout':'textures/authored_v05/layout.json','edge_contacts_mm':edge_contacts,
    'method':'Authored contours/stencils projected by barycentric world positions onto existing UVs; no periodic noise'},indent=2),encoding='utf-8')
