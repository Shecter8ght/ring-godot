"""Authored stencil layouts in millimetres, based on the owner's padlock views.

The silhouettes and contact strokes below are individually placed. Seeded random
fields only break their borders and vary the finish; they do not choose the wear
locations. SVG layouts and the placement JSON remain editable source artifacts.
No reference photograph pixels are used in texture maps.
"""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import distance_transform_edt, map_coordinates

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
OUT=WORK/'textures'/'authored_v05';OUT.mkdir(exist_ok=True)
SIZE=2048
DOMAINS={'front':(-42.,42.,-1.,73.),'rear':(-42.,42.,-1.,73.),
         'shackle':(0.,39.,65.,83.),'band':(0.,240.,-11.,11.)}

# Deliberate broad islands, negative chips and short contact strokes. Coordinates
# are x/z for cheeks, arc-length/z for the shackle, perimeter/y for the band.
PAINT={
 'front':[
  [(-38,65),(-31,67),(-25,64),(-18,65),(-13,61),(-6,59),(-8,54),(-18,55),(-21,50),(-30,49),(-35,44),(-38,48)],
  [(-36,48),(-29,49),(-25,46),(-18,47),(-14,43),(-5,44),(1,39),(-4,35),(-12,34),(-17,29),(-27,31),(-33,35),(-36,32)],
  [(8,64),(17,66),(21,63),(30,66),(36,63),(35,55),(30,53),(26,58),(20,55),(15,59),(8,57)],
  [(-31,26),(-24,28),(-21,23),(-14,22),(-12,17),(-19,15),(-26,19),(-30,17)],
  [(27,43),(33,46),(37,42),(37,36),(31,35),(29,39)],
  [(18,29),(24,31),(28,28),(26,23),(20,24)],
  [(-17,8),(-10,10),(-5,7),(-6,3),(-12,3)],
  [(-6,51),(-2,52),(1,49),(-3,47)],[(7,45),(11,46),(14,43),(10,41)]],
 'rear':[
  [(-38,64),(-30,66),(-23,62),(-16,65),(-10,61),(-11,55),(-3,50),(7,53),(15,58),(25,61),(34,64),(38,56),
   (38,43),(35,29),(30,18),(22,11),(11,7),(1,3),(-12,6),(-23,13),(-32,24),(-36,35)],
  [(-35,22),(-29,24),(-26,18),(-19,16),(-20,10),(-26,13)],
  [(25,17),(31,21),(31,14),(23,9)]]}
HOLES={
 'front':[
  [(-30,61),(-25,62),(-23,58),(-25,55),(-29,56)],
  [(-20,43),(-16,44),(-13,40),(-17,38),(-21,40)],
  [(-31,37),(-28,39),(-25,36),(-27,33)],
  [(21,62),(25,62),(27,59),(23,58)]],
 'rear':[
  [(-19,62),(-12,58),(-9,51),(-3,48),(4,43),(7,35),(11,29),(10,22),(16,14),(10,10),(4,17),(1,25),
   (-5,29),(-7,37),(-13,43),(-16,51)],
  [(-31,45),(-25,49),(-18,46),(-17,39),(-23,34),(-29,36)],
  [(22,48),(28,51),(33,46),(30,39),(25,39)],
  [(-11,19),(-5,22),(-1,19),(-3,14),(-8,12)]]}
KEY_STEEL=[
 [(-5.4,25.0),(-3.8,24.0),(-2.4,24.5),(-2.0,22.2),(-4.8,20.7),(-6.3,21.6),(-6.0,23.0)],
 [(4.8,23.7),(6.4,22.7),(6.5,20.6),(4.8,18.4),(3.5,18.6),(3.5,21.4)],
 [(2.9,17.8),(4.0,17.3),(4.0,13.5),(3.0,11.4),(2.5,13.0)],
 [(-1.7,15.2),(-2.8,16.4),(-3.3,14.7),(-2.9,12.9),(-1.7,12.1)],
 [(-1.6,8.4),(-.7,6.3),(1.8,6.2),(3.1,7.6),(2.6,8.8),(.1,8.0)]]
KEY_PITS=[
 [(-6.4,24.8),(-5.9,25.4),(-5.1,25.0),(-5.4,24.6),(-5.0,24.1),(-5.8,24.0)],
 [(6.2,25.2),(6.6,25.7),(7.2,25.2),(7.0,24.6),(6.5,24.5)],
 [(-5.3,17.0),(-4.7,17.2),(-4.3,16.6),(-4.8,16.1),(-5.4,16.4)],
 [(4.7,12.9),(5.4,12.8),(5.8,12.2),(5.1,11.8),(4.6,12.3)],
 [(-2.9,8.0),(-3.2,8.5),(-3.9,8.2),(-3.9,7.5),(-3.4,7.1)],
 [(2.4,5.6),(2.9,6.0),(3.5,5.4),(3.1,4.9),(2.6,5.0)]]
KEY_SCRATCHES=[([(-5.6,23.2),(-7.2,24.0),(-8.1,24.0)],.11),
               ([(6.1,21.3),(7.2,20.9),(9.1,20.1)],.14),
               ([(-2.6,14.7),(-3.5,13.3),(-3.8,11.2)],.10),
               ([(3.4,9.8),(4.4,8.8),(5.1,7.5)],.12),
               ([(-5.4,22.5),(-6.9,21.9)],.065)]
SHACKLE_STROKES=[
 ([(2.7,69.7),(2.8,72.5),(2.95,75.8)],.26),
 ([(6.9,70.0),(7.1,71.8),(7.0,74.4),(7.2,75.5)],.65),
 ([(11.7,69.5),(11.5,72.4),(11.55,76.7)],.30),
 ([(14.1,70.2),(14.2,72.8),(14.4,74.1)],.95),
 ([(20.6,69.9),(20.4,72.3),(20.45,77.5)],.23),
 ([(23.7,69.8),(23.9,71.7),(23.85,73.5)],.55),
 ([(30.2,69.7),(30.1,72.6),(30.3,75.7)],.34),
 ([(35.8,69.9),(36.0,71.4),(35.9,74.6)],.40)]
SHACKLE_PAINT=[[(3.7,69.0),(5.8,69.3),(6.2,72.4),(5.2,73.3),(4.4,72.5)],
                [(12.4,69.2),(13.8,69.1),(13.5,72.6),(12.8,73.5),(12.1,71.7)],
                [(26.3,69.0),(28.1,69.4),(28.3,73.5),(27.0,74.4),(26.0,72.3)],
                [(36.9,69.0),(38.1,69.1),(38.5,71.7),(37.4,72.4)]]

def canvas():return Image.new('L',(SIZE,SIZE),0)
def px(point,domain):
    x0,x1,z0,z1=DOMAINS[domain];x,z=point
    return ((x-x0)/(x1-x0)*(SIZE-1),(z1-z)/(z1-z0)*(SIZE-1))
def polygon(image,points,domain,value=255):
    p=np.asarray(points,np.float32)
    for _ in range(2):
        nxt=np.roll(p,-1,axis=0);p=np.stack((.82*p+.18*nxt,.18*p+.82*nxt),axis=1).reshape(-1,2)
    ImageDraw.Draw(image).polygon([px(v,domain) for v in p],fill=value)
def strokes(items,domain):
    im=canvas();d=ImageDraw.Draw(im);scale=SIZE/(DOMAINS[domain][1]-DOMAINS[domain][0])
    for path,width in items:
        d.line([px(p,domain) for p in path],fill=255,width=max(1,round(width*scale)),joint='curve')
        for p in (path[0],path[-1]):
            x,z=px(p,domain);r=width*scale*.46;d.ellipse((x-r,z-r,x+r,z+r),fill=210)
    return np.asarray(im,dtype=np.float32)/255
def seeded_noise(shape,cells,seed):
    rng=np.random.default_rng(seed)
    small=Image.fromarray(rng.integers(0,65536,(cells,cells),dtype=np.uint16).astype(np.float32)/65535,mode='F')
    return np.asarray(small.resize((shape[1],shape[0]),Image.Resampling.BICUBIC),np.float32).clip(0,1)
def save(name,values):Image.fromarray(np.round(np.clip(values,0,1)*65535).astype(np.uint16)).save(OUT/(name+'.png'))
def softened(array,pixels=.55):return np.asarray(Image.fromarray(array.astype(np.float32),mode='F').filter(ImageFilter.GaussianBlur(pixels)),np.float32)
def edge_break(array,domain,seed,amplitude=.55):
    mm=(DOMAINS[domain][1]-DOMAINS[domain][0])/SIZE
    inside=array>.5;sd=(distance_transform_edt(inside)-distance_transform_edt(~inside))*mm
    variation=.65*seeded_noise(array.shape,128,seed)+.35*seeded_noise(array.shape,512,seed+1)
    return np.clip((sd+(variation-.5)*amplitude)/.09+.5,0,1)

sources={
 'chips.png':'10_Сколы_и_потёртости_покрытия/Сколы_с_потёртостями_01.png',
 'pitting.png':'12_Пористая_коррозия/Коррозия_10_Слабый_питтинг.png',
 'blisters.png':'13_Вспучивание_покрытия/Вспучивание_08_Подплёночные_островки.png',
 'wipe.png':'06_Разводы_и_следы_протирания/Протирание_по_диагонали_01.png',
 'dust.png':'03_Пыль_и_частицы/Пыль_редкая_01.png',
 'crackle.png':'14_Микротрещины_покрытия/Микротрещины_09_Слабое_старение.png'}
manifest=[]
for name,rel in sources.items():
    source=Path('E:/Models Blender/Маски_АЛЬФА')/rel;shutil.copy2(source,OUT/name)
    manifest.append({'source':str(source),'copy':name,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest(),
                     'rights':'Owner alpha library; not asserted CC0'})

for domain in ('front','rear'):
    im=canvas()
    for path in PAINT[domain]:polygon(im,path,domain)
    for path in HOLES[domain]:polygon(im,path,domain,0)
    cov=edge_break(np.asarray(im,dtype=np.float32)/255,domain,510 if domain=='front' else 520)
    # Sparse stencil perforation, with most silhouette decisions kept in authored contours.
    chip=np.asarray(Image.open(OUT/'chips.png').convert('L').resize((SIZE,SIZE)),np.float32)/255
    cov*=1-np.clip((chip-.83)/.17,0,1)*.84
    save(domain+'_enamel',cov)
    z,x=np.mgrid[DOMAINS[domain][3]:DOMAINS[domain][2]:complex(SIZE),DOMAINS[domain][0]:DOMAINS[domain][1]:complex(SIZE)]
    tone=.42+.17*np.exp(-((x+24)/19)**2-((z-44)/25)**2)-.14*np.exp(-((x-9)/25)**2-((z-21)/22)**2)
    tone+=.13*(seeded_noise(tone.shape,18,565)-.5)+.06*(seeded_noise(tone.shape,96,566)-.5)
    save(domain+'_oxide_tone',tone)
    varnish=.34+.42*seeded_noise(tone.shape,20,578)+.14*seeded_noise(tone.shape,96,579)
    save(domain+'_varnish_wear',varnish)
    # Export the actual authored contours as a vector source, not a raster-only dead end.
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="2048" viewBox="0 0 2048 2048">',
           '<rect width="2048" height="2048" fill="black"/>']
    for paths,color in ((PAINT[domain],'white'),(HOLES[domain],'black')):
        for p in paths:lines.append('<polygon fill="'+color+'" points="'+' '.join(f'{a:.2f},{b:.2f}' for a,b in (px(v,domain) for v in p))+'"/>')
    lines.append('</svg>');(OUT/(domain+'_layout.svg')).write_text('\n'.join(lines),encoding='utf-8')

im=canvas()
for p in KEY_STEEL:polygon(im,p,'front')
save('front_key_steel',edge_break(np.asarray(im,np.float32)/255,'front',590,.18))
im=canvas()
for p in KEY_PITS:polygon(im,p,'front')
save('front_key_pits',np.asarray(im,np.float32)/255)
save('front_key_scratches',strokes(KEY_SCRATCHES,'front'))
steel_image=canvas()
pressure_curves=([.12,.80,.45,1.,.30,.60,.04],[.15,.55,.95,.40,.80,.18,.03],
                 [.20,.90,.55,.25,.70,.25,.02])
for index,(path,width) in enumerate(SHACKLE_STROKES):
    p=np.asarray(path,np.float32);lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    samples=np.linspace(0,lengths[-1],max(12,int(lengths[-1]/.07)))
    centre=np.column_stack([np.interp(samples,lengths,p[:,a]) for a in (0,1)])
    tangent=np.gradient(centre,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-8)
    normal=np.column_stack((-tangent[:,1],tangent[:,0]))
    press=np.interp(samples/lengths[-1],np.linspace(0,1,7),pressure_curves[index%3])*width*.5
    polygon(steel_image,np.r_[centre+normal*press[:,None],(centre-normal*press[:,None])[::-1]],'shackle')
steel=np.asarray(steel_image,np.float32)/255.
yy,xx=np.mgrid[:SIZE,:SIZE].astype(np.float32)
dx=(seeded_noise(steel.shape,112,597)-.5)*13.
dy=(seeded_noise(steel.shape,71,598)-.5)*7.
steel=map_coordinates(steel,[yy+dy,xx+dx],order=1,mode='constant')
steel*=np.clip((seeded_noise(steel.shape,150,597)-.30)/.38,0,1)
save('shackle_steel',steel)
im=canvas()
for p in SHACKLE_PAINT:polygon(im,p,'shackle')
save('shackle_enamel',edge_break(np.asarray(im,np.float32)/255,'shackle',599,.14))
save('shackle_variation',.25+.55*seeded_noise(steel.shape,48,601)+.15*seeded_noise(steel.shape,192,602))

band_image=Image.new('L',(SIZE,SIZE),255)
band_chips=[[(3,-7),(14,-9),(21,-4),(17,2),(7,3)],
            [(31,-11),(43,-8),(46,-2),(59,1),(69,8),(66,11),(50,8),(39,6),(35,0)],
            [(94,-10),(105,-6),(112,-8),(117,-3),(109,0),(99,-2)],
            [(119,2),(130,0),(138,6),(131,10),(122,8)],
            [(167,-8),(180,-11),(190,-7),(192,-1),(181,2),(170,-1)],
            [(211,-2),(215,-8),(225,-8),(229,-3),(225,4),(231,8),(221,10),(214,4)]]
for p in band_chips:polygon(band_image,p,'band',0)
save('band_enamel',edge_break(np.asarray(band_image,np.float32)/255,'band',610,.60))
save('band_oxide_tone',.35+.38*seeded_noise((SIZE,SIZE),20,612))
save('band_varnish_wear',.25+.65*seeded_noise((SIZE,SIZE),32,613))
layout={'domains_mm':DOMAINS,'paint_paths':PAINT,'negative_chips':HOLES,'key_steel':KEY_STEEL,
        'key_pits':KEY_PITS,'key_scratches':KEY_SCRATCHES,'shackle_strokes':SHACKLE_STROKES,
        'shackle_paint':SHACKLE_PAINT,'authoring':'Individually authored contours/strokes from visual reference; seeded border breakup only',
        'reference_pixels_projected':False}
(OUT/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
baseline_paths=['models/padlock_v01_geometry.blend','models/padlock_v04_textured.blend','models/padlock_v04_studio.blend','painter/padlock_v04_textured.spp']
baseline_paths+=['textures/export_v04/'+p.name for p in (WORK/'textures'/'export_v04').glob('*.png')]
baseline={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in baseline_paths}
checkpoint=WORK/'checks'/'v05_baseline.json'
if checkpoint.exists():assert json.loads(checkpoint.read_text(encoding='utf-8'))==baseline
else:checkpoint.write_text(json.dumps(baseline,indent=2),encoding='utf-8')
print('AUTHORED_V05_SOURCES_READY',OUT)
