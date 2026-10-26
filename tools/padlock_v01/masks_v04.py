"""Interrupted contact steel, key impacts, larger chips and protected dirt in millimetres."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np

SCRIPT=Path(__file__).resolve().parent;sys.path.insert(0,str(SCRIPT))
from uv_mask_raster import rasterize
WORK=SCRIPT.parents[1]/'_asset_src'/'padlock_v01';OUT=WORK/'textures'/'contact_v04'
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v02_texture_source.blend'))
spec=importlib.util.spec_from_file_location('shape_profile',SCRIPT/'build.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
outline=np.asarray(profile.body_profile(),np.float32);key=np.asarray(profile.key_profile(),np.float32)
angles=np.arctan2(outline[:,1]-35,outline[:,0]);order=np.argsort(angles)
radii=np.linalg.norm(outline-np.array([0,35]),axis=1)
perimeter=float(np.linalg.norm(np.roll(outline,-1,axis=0)-outline,axis=1).sum())

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)

def noise(x,z):
    return np.clip(.5+.21*np.sin(x*.73+z*.37)+.17*np.sin(x*1.87-z*.69+.8)+.12*np.cos(x*4.31+z*2.71),0,1)

def load(name):
    image=bpy.data.images.load(str(OUT/name));image.colorspace_settings.name='Non-Color'
    data=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(data)
    result=data.reshape(image.size[1],image.size[0],4)[:,:,0].copy();bpy.data.images.remove(image);return result

chips=load('edge_chips.png');paint=load('grain_chips.png')

def sample(image,u,v,wrap=False):
    if wrap:u=np.mod(u,1);v=np.mod(v,1)
    h,w=image.shape;xx=np.clip(u*(w-1),0,w-1);yy=np.clip(v*(h-1),0,h-1)
    i=xx.astype(np.int32);j=yy.astype(np.int32);fx=xx-i;fy=yy-j
    ii=np.minimum(i+1,w-1);jj=np.minimum(j+1,h-1)
    return image[j,i]*(1-fx)*(1-fy)+image[j,ii]*fx*(1-fy)+image[jj,i]*(1-fx)*fy+image[jj,ii]*fx*fy

def segment(points,start,end):
    a=np.asarray(start);d=np.asarray(end)-a;t=np.clip(((points-a)@d)/max(float(np.dot(d,d)),1e-12),0,1)
    return np.linalg.norm(points-a-t[:,None]*d,axis=1)

def edge_data(x,z,scale=1):
    a=np.arctan2(z-35,x);r=np.sqrt(x*x+(z-35)**2)
    boundary=np.interp(a,angles[order],radii[order],period=2*math.pi)*scale
    return np.maximum(0,boundary-r),(a+math.pi)/(2*math.pi)*perimeter

rng=np.random.default_rng(7404)
impacts=[]
for i in range(34):
    impacts.append((rng.uniform(-7.0,8.2),rng.uniform(6.5,28),rng.uniform(.18,.45) if i<24 else rng.uniform(.45,.85),rng.uniform(0,6.28)))
scratches=[((-5.1,22),(-9.,24.5),.15),((4.8,22),(10.5,20),.16),((-2.,12),(-5.,7.7),.12),
           ((2.6,14),(6.5,10),.13),((-4.2,24),(-7.4,28.0),.14),((4.5,18),(8.8,15),.16),
           ((-3.4,17),(-6.9,15),.11),((2.2,8.4),(4.8,6.1),.12),((-5.4,20),(-8.5,18.3),.09)]
pins=[(-29.3,60.8,3.1),(-10.1,59,3.2),(29.4,64.8,3.1),(-21.2,10.4,2.65),(22.1,11.2,2.65)]
NAMES=['shackle_steel','shackle_paint','body_edges','key_steel','key_dents','key_lips','key_scratches','corner_grime','corner_dust',
       'contact_roughness','steel_microheight']

def fields(name,p,normals):
    x,y,z=p.T;result=np.zeros((len(p),len(NAMES)),np.float32);xz=np.column_stack((x,z));grain=noise(x,z)
    result[:,9]=.17+.16*noise(x*3.1+7,z*2.3-2)
    result[:,10]=.5002+.0006*(noise(x*4.7,z*3.2)-.5)
    if name.startswith('Shackle'):
        left=x<0;cx=np.where(left,-25.,25.);phi=np.arctan2(y,x-cx);s=phi*6.2
        top=np.where(left,76.0,79.0)+.7*np.sin(phi*2.0+1.3)
        zone=smooth(67.4,69.,z)*(1-smooth(top-.8,top+.7,z))
        photo=sample(paint,s/21.+.31,(z-63.)/17.,True)
        paint_mask=zone*smooth(.47,.65,photo*.8+noise(s,z)*.2)
        steel=np.zeros(len(x),np.float32)
        for index,(centre,width) in enumerate(((-2.62,.055),(-2.11,.14),(-1.74,.045),(-1.24,.10),(-.63,.06),(.08,.15),(.87,.05),(1.43,.11),(2.32,.065))):
            da=np.mod(phi-centre+.025*np.sin(z*.9+index)+math.pi,2*math.pi)-math.pi
            strip=np.exp(-(da/width)**4)
            lo=67.8+(index%3)*.65;hi=np.where(left,74.8,78.0)+(index%4)*.45
            strip*=smooth(lo,lo+.45,z)*(1-smooth(hi-.5,hi+.4,z))
            strip*=smooth(.24,.46,noise(s*1.4+index,z*.9))
            steel=np.maximum(steel,strip)
        steel=np.maximum(steel,zone*smooth(.66,.81,photo)*smooth(.44,.72,noise(s*1.9,z*.8)))
        result[:,0]=steel*(1-paint_mask*.70)
        result[:,1]=paint_mask*(1-steel*.8)
        # Subtle axial scoring survives inside bare patches; they are not perfect mirrors.
        directional=.5+.30*np.sin(s*19.+.3*np.sin(z*.23))+.16*np.sin(s*37.-z*.12)
        result[:,9]=.18+.12*noise(s*3.2,z*2.7)+.045*directional
        result[:,10]=.5002+.0012*(directional-.5)+.00035*(noise(s*11,z*13)-.5)
        # Dust stays in the socket's sheltered bottom, not over sliding strips.
        result[:,7]=np.exp(-((z-69.5)/.45)**2)*(1-steel)*(.35+.65*noise(s,z))*.6
    elif name.startswith(('Front_cheek','Rear_cheek','Body_perimeter')):
        front=name.startswith('Front');back=name.startswith('Rear');band=name.startswith('Body')
        facing=np.ones(len(x)) if band else smooth(9.5,10.9,-y if front else y)
        d,along=edge_data(x,z,.961 if band else 1.)
        if band:
            d=np.abs(np.abs(y)-9.2)
            outer,_=edge_data(x,z,.961);facing*=1-smooth(.6,1.4,outer)
        width=.8+.6*noise(along*.4,z*.3)
        stencil=sample(chips,.08+.84*np.mod(along/27.+(.23 if back else 0),1),.510+d/85.)
        edge_mask=np.clip(stencil*1.6,0,1)*(1-smooth(width,width+.5,d))
        for target in ((-38,43),(-37,60),(-29,11),(-6,1),(22,6),(37,31),(38,55),(36,68)):
            idx=int(np.argmin(np.sum((outline-np.asarray(target))**2,axis=1)))
            a=outline[idx];t=outline[(idx+1)%len(outline)]-outline[(idx-1)%len(outline)];t=t/np.linalg.norm(t)
            q=(xz-a)@t;shape=(1-smooth(2.0,4.1,np.abs(q)))*(1-smooth(.6,1.8,d))
            fragment=sample(paint,q/7.+.5,d/5.+.37)
            edge_mask=np.maximum(edge_mask,shape*smooth(.18,.42,fragment+grain*.18))
        result[:,2]=edge_mask*facing
        # Protected plate joints, not a generic all-over dirt layer.
        seam=np.exp(-((np.abs(y)-9.15)/.60)**2)*(1-smooth(1.0,2.6,d))
        corner=np.zeros(len(x),np.float32)
        chosen=pins+([] if front else [(16,33.6,2.4),(-1.2,17.3,2.7)])
        if not band:
            for px,pz,rr in chosen:
                rr=rr*(.84 if back and (px,pz,rr) in pins else 1.)
                ring=np.exp(-((np.sqrt((x-px)**2+(z-pz)**2)-rr)/.65)**2)
                corner=np.maximum(corner,ring*facing)
        notch=np.exp(-(x/10)**4-((z-62.2)/1.3)**2)*np.exp(-(y/8.8)**8)
        sockets=np.maximum(np.exp(-((np.sqrt((x-25)**2+y*y)-6.7)/.8)**2),
                           np.exp(-((np.sqrt((x+25)**2+y*y)-6.7)/.8)**2))*np.exp(-((z-69.4)/1.5)**2)
        protected=np.maximum.reduce((seam,corner,notch,sockets))
        result[:,7]=protected*(.35+.65*grain)*(1-result[:,2]*.8)
        orient=.25+.75*smooth(-.1,.6,normals[:,2])
        result[:,8]=protected*orient*(.4+.6*noise(x*.8+4,z*.9-6))*(1-result[:,2])
        if front:
            in_key=(x>-10)&(x<12)&(z>4)&(z<31)&(y<-9.8)
            distance=np.full(len(x),100.,np.float32)
            if in_key.any():
                loc=xz[in_key];best=np.full(len(loc),100.,np.float32)
                for i,a in enumerate(key):best=np.minimum(best,segment(loc,a,key[(i+1)%len(key)]))
                distance[in_key]=best
            halo=(1-smooth(.3,3.4+.8*grain,distance))*facing
            pattern=sample(paint,(x+10)/18,(z-4)/27)
            result[:,3]=halo*smooth(.22,.54,pattern*.65+grain*.35)
            for px,pz,rr,phase in impacts:
                dx=x-px;dz=z-pz;angle=np.arctan2(dz,dx)
                radius=rr*(.82+.12*np.sin(angle*3+phase)+.10*np.sin(angle*7-phase))
                r=np.sqrt((dx*1.12)**2+(dz*.89)**2)/radius
                dent=1-smooth(.15,1.,r)
                lip=np.exp(-((r-1.06)/.16)**2)*smooth(.16,.72,noise(dx*6+px,dz*7+pz))
                result[:,4]=np.maximum(result[:,4],dent*in_key*facing)
                result[:,5]=np.maximum(result[:,5],lip*in_key*facing)
            for a,b,w in scratches:
                scratch=1-smooth(w*.35,w,segment(xz,a,b))
                result[:,6]=np.maximum(result[:,6],scratch*in_key*facing)
            # Deep side of the entrance collects dark grime; the mouth stays abraded.
            result[:,7]=np.maximum(result[:,7],np.exp(-((distance-.1)/.32)**2)*(1-facing)*.6)
    elif name=='Visible_key_guide_post':
        r=np.sqrt((x-.8)**2+(z-21.1)**2)
        result[:,3]=(1-smooth(-8.3,-7.8,y))*smooth(1.0,1.8,r)*(.5+.5*grain)
    elif 'pressed' in name or 'peened' in name or name.endswith('_head'):
        # Small oxide/dust pockets near existing rivet seats; generators refine them.
        result[:,7]=.18*grain
        result[:,8]=.12*grain*smooth(0,.65,normals[:,2])
    return np.clip(result,0,1)

parts=[o for o in bpy.data.objects if o.get('stage')=='accepted_shape_highpoly_texture_copy' and not o.name.endswith(('_shaft','_seat'))]
rasterize(parts,fields,NAMES,OUT)
(WORK/'checks'/'contacts_v04.json').write_text(json.dumps({'resolution':4096,'fields':NAMES,
    'key_impacts_mm':impacts,'key_scratches_mm':scratches,'geometry_changed':False,
    'method':'Barycentric physical UV raster; irregular axial steel/paint; actual plate/rivet/socket corners'},indent=2),encoding='utf-8')
