"""Собственные слои PBR для Krita, привязанные к поверхности и масштабу предмета.

Подготовка масок не меняет модель. Композит и .kra создаёт движок Krita.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[1]/'_asset_src'/'vss_textured'

def noise(p,scale,offset=0):
    q=p*scale+offset; i=np.floor(q); f=q-i; f=f*f*(3-2*f)
    result=np.zeros(q.shape[:-1],dtype=np.float32)
    for x in (0,1):
        for y in (0,1):
            for z in (0,1):
                v=np.sin((i[...,0]+x)*127.1+(i[...,1]+y)*311.7+(i[...,2]+z)*74.7)*43758.5453
                v=v-np.floor(v)
                result+=v*(f[...,0] if x else 1-f[...,0])*(f[...,1] if y else 1-f[...,1])*(f[...,2] if z else 1-f[...,2])
    return result

def srgb(linear):
    return np.where(linear<=.0031308,linear*12.92,1.055*np.power(np.maximum(linear,0),1/2.4)-.055)

def byte(v): return np.uint8(np.clip(v*255+.5,0,255))

def dilate(image,radius=10):
    # Соседние острова разделены margin: цвет не берётся из чёрного фона.
    rgba=image.convert('RGBA'); arr=np.array(rgba); mask=arr[...,3]>0
    for _ in range(radius):
        add=np.zeros(mask.shape,bool); value=np.zeros_like(arr)
        for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
            nearby=np.roll(mask,(dy,dx),(0,1)); target=~mask & nearby & ~add
            if dy==1:target[0]=False
            if dy==-1:target[-1]=False
            if dx==1:target[:,0]=False
            if dx==-1:target[:,-1]=False
            value[target]=np.roll(arr,(dy,dx),(0,1))[target]; add|=target
        arr[add]=value[add]; mask|=add
    return Image.fromarray(arr)

def edge_flags(positions,indices):
    normal=np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0])
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-15)
    lookup={}; result=np.zeros((len(indices),3),bool)
    for f,ids in enumerate(indices):
        for e in range(3):
            a,b=int(ids[(e+1)%3]),int(ids[(e+2)%3]); key=tuple(sorted((a,b)))
            if key in lookup:
                other,oe=lookup[key]
                angle=np.arccos(np.clip(np.dot(normal[f],normal[other]),-1,1))
                convex=np.dot(normal[other],positions[f,e]-positions[other,oe])<1e-9
                # Грани гладкого цилиндра не считаются острыми кромками износа.
                if convex and .50<angle<2.65: result[f,e]=True; result[other,oe]=True
            else:lookup[key]=(f,e)
    return result

def classify(material):
    text=material.lower()
    if 'walnut' in text:return 'wood'
    if 'rubber' in text or 'eyecup' in text:return 'rubber'
    if 'polymer' in text:return 'polymer'
    if 'seal' in text or ('red' in text and 'lacquer' in text):return 'seal'
    if 'copper' in text or 'projectile' in text:return 'copper'
    if 'case' in text or 'brass' in text or 'primer' in text:return 'case'
    if 'index' in text or 'mark' in text or 'engraving' in text:return 'mark'
    if 'recess' in text:return 'recess'
    return 'metal'

def raster(folder,atlas):
    meta=json.loads((folder/(atlas+'_surfaces.json')).read_text(encoding='utf-8'))
    geo=np.load(folder/meta['geometry']); points=geo['positions']; uv=geo['uv']; ids=geo['ids']; flags=edge_flags(points,geo['indices'])
    n=meta['resolution']; out=folder/atlas; out.mkdir(exist_ok=True)
    base=np.zeros((n,n,4),np.uint8); grain=np.zeros_like(base); wear=np.zeros_like(base); dirt=np.zeros_like(base)
    orm=np.zeros_like(base); orm[:,:,:3]=[255,128,0]
    guide=Image.new('RGBA',(n,n)); draw=ImageDraw.Draw(guide)
    matid=np.zeros_like(base); usage=np.zeros((n,n),bool)
    surfaces=meta['surfaces']; classes=[classify(m['material']) for m in surfaces]
    for f,(poly,tex,sid) in enumerate(zip(points,uv,ids)):
        xy=np.column_stack((tex[:,0]*n,(1-tex[:,1])*n))
        lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),0); hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),n-1)
        if np.any(hi<lo):continue
        xs=np.arange(lo[0],hi[0]+1,dtype=np.float32)+.5; ys=np.arange(lo[1],hi[1]+1,dtype=np.float32)+.5
        xx,yy=np.meshgrid(xs,ys); den=(xy[1,1]-xy[2,1])*(xy[0,0]-xy[2,0])+(xy[2,0]-xy[1,0])*(xy[0,1]-xy[2,1])
        if abs(den)<1e-8:continue
        a=((xy[1,1]-xy[2,1])*(xx-xy[2,0])+(xy[2,0]-xy[1,0])*(yy-xy[2,1]))/den
        b=((xy[2,1]-xy[0,1])*(xx-xy[2,0])+(xy[0,0]-xy[2,0])*(yy-xy[2,1]))/den
        c=1-a-b; inside=(a>=-1e-5)&(b>=-1e-5)&(c>=-1e-5)
        if not inside.any():continue
        iy,ix=np.nonzero(inside); rows=iy+lo[1]; cols=ix+lo[0]
        bary=np.stack((a[inside],b[inside],c[inside]),axis=-1)
        p=bary@poly; p=p[:,[1,0,2]]*[-1,1,1]; surface=surfaces[int(sid)]; kind=classes[int(sid)]
        medium=noise(p,190,3.73); fine=noise(p,2600,2.13); tiny=noise(p,11000,.07)
        rough=surface['roughness']+.06*(medium-.5)+.05*(fine-.5)
        metal=np.full(len(p),surface['metallic'],np.float32)
        color=np.tile(np.array(surface['color'],np.float32),(len(p),1))
        variation=1+.14*(medium-.5)+.065*(fine-.5)
        distances=[]
        for e in range(3):
            if flags[f,e]:
                v1,v2=poly[(e+1)%3],poly[(e+2)%3]
                altitude=np.linalg.norm(np.cross(poly[e]-v1,v2-v1))/max(np.linalg.norm(v2-v1),1e-12)
                distances.append(bary[:,e]*altitude)
        distance=np.min(np.stack(distances),axis=0) if distances else np.full(len(p),1)
        edge=np.exp(-distance/.00012)
        patch=np.clip((noise(p,1450,33.1)-.54)*4.4,0,1)
        contact=np.ones(len(p))*.55
        name=surface['object'].lower()
        if any(s in name for s in ('floor','lip','clamp','lever','handle','rail','mount','screw')):contact[:]=1
        if kind=='wood':
            # Продольный рисунок и поры непрерывны в пространстве по обеим сторонам приклада.
            wp=p*np.array([1,25,17]); elongated=noise(wp,160,1.71)
            ring=.5+.5*np.sin(p[:,2]*4100+noise(p,65,9)*13+p[:,1]*1050)
            tone=np.clip(.64*elongated+.22*ring+.14*medium,0,1)
            dark=np.array([.095,.020,.0045]); light=np.array([.42,.155,.030])
            color=dark+tone[:,None]*(light-dark)
            pores=np.power(np.clip((noise(wp,1100,7)-.60)*2.5,0,1),2)
            color*=1-pores[:,None]*.28; rough=.30+.13*pores+.09*(medium-.5)
            rubbed=edge*patch*.55; worn=np.array([.29,.105,.035]); rough-=rubbed*.08
        elif kind=='metal':
            color*=variation[:,None]; rough=np.clip(rough,.25,.55)
            rubbed=edge*patch*contact*.45; worn=np.array([.15,.17,.185]); rough-=rubbed*.10; metal+=rubbed*.12
        elif kind=='polymer':
            color*=variation[:,None]; rough=.52+.12*(medium-.5)+.085*(fine-.5)
            rubbed=edge*patch*contact*.42; worn=np.array([.055,.047,.039]); rough-=rubbed*.19; metal[:]=0
        elif kind=='rubber':
            color*=variation[:,None]; rough=.73+.07*(fine-.5); rubbed=edge*patch*.10; worn=np.array([.028,.030,.031]); metal[:]=0
        elif kind in ('copper','case'):
            color*=variation[:,None]; rough=.32+.10*(medium-.5)+.06*(fine-.5)
            # Плавные следы вытяжки гильзы и касания подачи, без вымышленной коррозии.
            lines=.5+.5*np.sin(p[:,0]*49000+noise(p,800,4)*6)
            rough+=lines*.035; rubbed=edge*patch*.13
            worn=np.array([.36,.26,.085]) if kind=='case' else np.array([.50,.25,.09])
        else:
            color*=variation[:,None]; rubbed=edge*patch*.02; worn=np.array([.025,.023,.020])
        oil=np.clip((noise(p,430,17)-.58)*3,0,1)*contact*.15
        dust=np.clip((noise(p,320,23)-.60)*2.5,0,1)*.09
        if kind in ('case','copper','seal','mark'):dust*=.12;oil*=.2
        rough+=dust*.18-oil*.13
        base[rows,cols,:3]=byte(srgb(color));base[rows,cols,3]=255
        grain[rows,cols,:3]=byte(srgb(color*(.94+.09*tiny[:,None])));grain[rows,cols,3]=65
        wear[rows,cols,:3]=byte(srgb(worn));wear[rows,cols,3]=byte(rubbed)
        dirt[rows,cols,:3]=byte(srgb(np.array([.034,.028,.020])));dirt[rows,cols,3]=byte(dust)
        orm[rows,cols,0]=255;orm[rows,cols,1]=byte(rough);orm[rows,cols,2]=byte(metal);orm[rows,cols,3]=255
        matid[rows,cols,:3]=[int((int(sid)*73+61)%230)+25,int((int(sid)*127+19)%230)+25,int((int(sid)*47+109)%230)+25];matid[rows,cols,3]=255
        usage[rows,cols]=True
        if f%5000==0:print(folder.name,atlas,f,'/',len(points),flush=True)
        draw.line([tuple(x) for x in xy]+[tuple(xy[0])],fill=(70,170,230,125),width=1)
    normal=Image.open(folder/(atlas+'_normal_before.png')).convert('RGBA')
    if normal.size!=(n,n):normal=normal.resize((n,n))
    normal_arr=np.array(normal);normal_arr[...,3]=np.uint8(usage)*255
    layers=[]
    for label,value,group,visible,pad in [
        ('01 Coating and wood grain',base,'Base Color',True,True),('02 Surface microvariation',grain,'Base Color',True,False),
        ('03 Contact and edge wear',wear,'Base Color',True,False),('04 Settled grime',dirt,'Base Color',True,False),
        ('ORM - AO roughness metallic',orm,'ORM',False,True),('OpenGL tangent normal',normal_arr,'Normal',False,True),
        ('Material IDs',matid,'Guides',False,False)]:
        path=out/(label.replace(' ','_')+'.png');img=Image.fromarray(value)
        if pad:img=dilate(img,12 if n==4096 else 8)
        img.save(path);layers.append({'name':label,'file':path.name,'group':group,'visible':visible})
    guide.save(out/'UV_Guide.png');layers.append({'name':'UV Guide','file':'UV_Guide.png','group':'Guides','visible':False})
    (out/'layers.json').write_text(json.dumps({'name':folder.name+' / '+atlas,'size':n,'layers':layers,
        'authoring':'Original geometry-aware layers; final compositing and KRA via installed Krita',
        'normal_convention':'OpenGL +Y','orm':'R=1, G=roughness, B=metallic; no baked AO'},indent=2),encoding='utf-8')
    print('TEXTURE_LAYERS_READY',folder.name,atlas,flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--id');args=parser.parse_args()
    folders=[ROOT/args.id] if args.id else sorted(p for p in ROOT.iterdir() if (p/'prepare.json').exists())
    for folder in folders:
        data=json.loads((folder/'prepare.json').read_text())
        for atlas in data['atlas_objects']:raster(folder,atlas)
if __name__=='__main__':main()
