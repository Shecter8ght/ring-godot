"""Двухэтажный оштукатуренный корпус по трём фотографиям владельца.

Лицевой фасад и повреждения — по фото. Габариты, невидимые стороны и объёмы внутри
оценочные; производственные UV/PBR выполняются после принятия геометрии.
"""
import math,random
from math import sin,cos,pi,exp
import bpy,bmesh
from mathutils import Matrix,Vector
from common import k,boolean,ring_rect,sheet

W,D,H=34.8,10.5,6.65
FRONT=-D/2
BAYS=[-15.6+i*2.6 for i in range(13)]
ENTRY=(3,9)
OPEN=[]
SPALLS=[
 [(-13.85,6.64),(-11.75,6.64),(-11.88,6.41),(-12.17,6.36),(-12.42,6.43),(-12.60,6.32),(-13.06,6.36),(-13.25,6.48),(-13.73,6.43)],
 [(9.77,6.64),(12.27,6.64),(12.18,6.40),(11.86,6.29),(11.57,6.35),(11.31,6.26),(10.99,6.30),(10.77,6.41),(10.33,6.38),(10.14,6.46)],
 [(15.12,6.64),(17.4,6.64),(17.4,6.22),(16.98,6.27),(16.68,6.36),(16.33,6.28),(16.04,6.35),(15.61,6.33),(15.41,6.47),(15.21,6.48)]
]


def openings():
    result=[]
    for i,x in enumerate(BAYS):
        w=1.62 if i in (0,2,4,8,12) else 1.91
        if i in ENTRY:
            result.append(dict(i=i,x=x,z=.27,w=1.82,h=2.42,door=True))
            result.append(dict(i=i,x=x,z=3.03,w=1.53,h=1.94,door=False,landing=True))
        else:
            for z in (1.0,4.10): result.append(dict(i=i,x=x,z=z,w=w,h=1.94,door=False))
    return result


def plaster_offset(x,z):
    # Небольшие наплывы и вздутия под окрасочным слоем, а не военные разрушения.
    broad=.003*sin(.73*x+1.4*z)+.0025*cos(2.1*x-.8*z)
    wrinkles=.013*cos(9.4*z+.7*sin(.8*x))+.006*sin(15.7*z+1.1*x)
    belt=exp(-((z-3.55)/1.08)**2)
    local=.018*exp(-((x-10.0)/2.5)**2-((z-3.60)/1.3)**2)*sin(5*x+4*z)
    offset=max(-.003,broad+wrinkles*belt+local)
    # На примыканиях к раме штукатурка не превращается в свисающую штору.
    edge=1
    for op in OPEN:
        dx=max(abs(x-op['x'])-op['w']/2,0)
        dz=max(op['z']-z,z-op['z']-op['h'],0)
        if dx<.10 and dz<.10: edge=min(edge,min(1,max(dx,dz)/.075))
    return offset*edge


def grid_plaster():
    xs={round(-W/2+i*W/290,6) for i in range(291)}
    zs={round(i*H/74,6) for i in range(75)}
    for o in OPEN:
        xs.update([round(o['x']-o['w']/2,6),round(o['x']+o['w']/2,6)])
        zs.update([round(o['z'],6),round(o['z']+o['h'],6)])
    xs,zs=sorted(xs),sorted(zs); nx=len(xs)
    verts=[(x,FRONT-.017-plaster_offset(x,z),z) for z in zs for x in xs]
    faces=[]
    for j in range(len(zs)-1):
        zm=(zs[j]+zs[j+1])/2
        for i in range(nx-1):
            xm=(xs[i]+xs[i+1])/2
            if any(abs(xm-o['x'])<o['w']/2 and o['z']<zm<o['z']+o['h'] for o in OPEN): continue
            a=j*nx+i; faces.append((a,a+1,a+nx+1,a+nx))
    # Удалить лишь вершины, не вошедшие ни в одну грань проёмов.
    used=sorted({i for f in faces for i in f}); lookup={v:i for i,v in enumerate(used)}
    ob=k.mesh('FACADE | continuous rippled plaster', [verts[i] for i in used],
              [tuple(lookup[i] for i in f) for f in faces],'plaster',0,True)
    mod=ob.modifiers.new('Physical 22 mm plaster coat','SOLIDIFY'); mod.thickness=.022; mod.offset=-1
    bpy.context.view_layer.objects.active=ob; bpy.ops.object.modifier_apply(modifier=mod.name)
    return ob


def window(x,z,w,h,y=FRONT,s=-1,label='PVC'):
    outer=[(x-w/2,z),(x+w/2,z),(x+w/2,z+h),(x-w/2,z+h)]
    inner=[(x-w/2+.075,z+.075),(x+w/2-.075,z+.075),(x+w/2-.075,z+h-.075),(x-w/2+.075,z+h-.075)]
    yf=y+s*.008
    ring_rect(label+' | perimeter frame',outer,inner,yf,yf-s*.105,'plastic')
    zt=z+h-.42
    k.box(label+' | transom rail',(x,yf-s*.04,zt),(w-.13,.076,.058),'plastic',.003)
    count=3 if w>1.8 else 2
    left=x-w/2+.075; clear=w-.15
    for i in range(1,count):
        xx=left+i*clear/count
        k.box(label+' | upright mullion',(xx,yf-s*.04,(z+.075+zt)/2),(.060,.075,zt-z-.075),'plastic',.003)
    for i in range(count):
        a=left+i*clear/count+.018; b=left+(i+1)*clear/count-.018
        k.box(label+' | lower glass',((a+b)/2,yf-s*.047,(z+.09+zt-.035)/2),(b-a,.006,zt-z-.125),'glass',.001)
        # Уплотнитель по границе стекла, без нарисованного чёрного прямоугольника.
        pts=[(a,yf-s*.031,z+.09),(b,yf-s*.031,z+.09),(b,yf-s*.031,zt-.035),(a,yf-s*.031,zt-.035),(a,yf-s*.031,z+.09)]
        k.section(label+' | glazing seal',pts,.0023,'rubber',8)
    ga,gb=zt+.035,z+h-.075
    k.box(label+' | upper transom glass',(x,yf-s*.047,(ga+gb)/2),(w-.18,.006,gb-ga),'glass',.001)
    k.section(label+' | transom glazing seal',[(x-w/2+.09,yf-s*.031,ga),(x+w/2-.09,yf-s*.031,ga),
        (x+w/2-.09,yf-s*.031,gb),(x-w/2+.09,yf-s*.031,gb),(x-w/2+.09,yf-s*.031,ga)],.0023,'rubber',8)
    for xx in (left+clear/count-.045,): k.bar(label+' | window latch',(xx,yf+s*.015,z+.91),(xx,yf+s*.015,z+1.03),.006,'plastic',12)
    # Слив с уклоном наружу и капельником.
    ya,yb=y-s*.045,y+s*.28
    sheet(label+' | folded metal sill',[(x-w/2-.07,ya,z-.018),(x+w/2+.07,ya,z-.018),
       (x+w/2+.09,yb,z-.052),(x-w/2-.09,yb,z-.052)],'metal',.012)
    k.box(label+' | sill drip edge',(x,yb,z-.074),(w+.18,.014,.045),'metal',.003)


def entry(x,index):
    w,h,z=1.82,2.42,.27
    outer=[(x-w/2-.065,z-.01),(x+w/2+.065,z-.01),(x+w/2+.065,z+h+.065),(x-w/2-.065,z+h+.065)]
    inner=[(x-w/2,z),(x+w/2,z),(x+w/2,z+h),(x-w/2,z+h)]
    ring_rect('ENTRY | timber frame',outer,inner,FRONT-.012,FRONT+.13,'wood')
    for side in (-1,1):
        cx=x+side*(w/4+.002)
        k.box('ENTRY | closed door leaf',(cx,FRONT+.026,z+h/2),(w/2-.012,.065,h-.014),'wood',.006)
        for zz,ph in ((z+.45,.60),(z+1.51,1.27)):
            k.box('ENTRY | inset moulded panel',(cx,FRONT-.011,zz),(w/2-.17,.015,ph),'wood',.013)
        k.box('ENTRY | pull backplate',(x+side*.08,FRONT-.038,z+1.1),(.048,.012,.22),'metal',.003)
        k.section('ENTRY | vertical pull',[(x+side*.08,FRONT-.044,z+1.05),(x+side*.08,FRONT-.09,z+1.05),
             (x+side*.08,FRONT-.09,z+1.25),(x+side*.08,FRONT-.044,z+1.25)],.008,'metal',12)
    for level in (0,1):
        k.box('ENTRY | concrete step',(x,FRONT-.30-.22*(1-level),.06+.12*level),(2.12,.73-.23*level,.12),'concrete',.012)
    # Помятый фальцевый козырёк: форма листа повторяет изгиб на первом фото.
    def canopy(u,v):
        xx=(2*u-1)*1.28; yy=FRONT-.035-1.12*v
        dent=-.075*exp(-((u-.76)/.11)**2)*v**3 if index==0 else -.028*sin(pi*u)*v
        return x+xx,yy,2.98-.13*v+dent+.012*sin(4*pi*u)*v
    k.patch('ENTRY | bent canopy sheet',canopy,64,24,'metal',.018)
    for xx in (-1.24,1.24): k.beam('ENTRY | canopy frame',(x+xx,FRONT-.02,2.93),(x+xx,FRONT-1.15,2.80),.045,.045,'metal',.003)
    k.beam('ENTRY | canopy front fascia',(x-1.29,FRONT-1.16,2.77),(x+1.29,FRONT-1.16,2.77),.075,.035,'metal',.004)
    for xx in (-1.10,1.10):
        k.bar('ENTRY | canopy suspension',(x+xx,FRONT-.035,3.58),(x+xx,FRONT-1.07,2.83),.008,'metal',16)
    # Тонкая наружная труба огибает пониженное окно лестничной клетки.
    k.section('ENTRY | painted surface conduit',[(x-1.14,FRONT-.037,3.34),(x-1.14,FRONT-.037,5.12),
      (x+1.14,FRONT-.037,5.12),(x+1.14,FRONT-.037,3.34)],.017,'metal',12)
    k.section('ENTRY | vertical lamp conduit',[(x,FRONT-.035,5.12),(x,FRONT-.035,6.1)],.012,'metal',12)
    k.box('ENTRY | luminaire wall plate',(x,FRONT-.025,6.10),(.11,.025,.16),'metal',.006)
    k.section('ENTRY | luminaire bracket',[(x,FRONT-.05,6.12),(x,FRONT-.30,6.18),(x,FRONT-.47,6.10)],.014,'metal',16)
    k.soft('ENTRY | oval wall lamp',(x,FRONT-.44,6.12),(.24,.26,.12),'metal',.65)
    k.soft('ENTRY | lamp diffuser',(x,FRONT-.47,6.07),(.22,.24,.026),'diffuser',.65)


def damages(plaster):
    # Лишь крупные видимые отслоения у карниза; тонкая грязь и волосные трещины — будущий PBR.
    for j,poly in enumerate(SPALLS):
        cutter=k.extrude('TEMP_missing_plaster',poly,'Y',FRONT-.20,FRONT+.03,'interior',0)
        boolean(plaster,cutter)
        xmin,xmax=min(p[0] for p in poly)-.24,max(p[0] for p in poly)+.24
        zmin,zmax=min(p[1] for p in poly)-.10,max(p[1] for p in poly)+.08
        # Реальные кирпичные ряды видны только в проёмах штукатурки, остальное скрыто ею.
        for row in range(math.floor(zmin/.075),math.ceil(zmax/.075)):
            for col in range(math.floor(xmin/.26)-1,math.ceil(xmax/.26)+1):
                xx=col*.26+(row%2)*.13
                if xx-.122<-W/2 or xx+.122>W/2: continue
                k.box('DAMAGE | exposed brick course',(xx,FRONT+.038,row*.075+.033),(.246,.087,.065),'brick',.002)
    # Несколько крупных трещин от углов окон, снятых крупным планом на фото 2.
    cracks=[[(9.45,4.10),(9.40,3.91),(9.23,3.79),(9.20,3.56),(9.04,3.40)],
      [(11.355,4.10),(11.38,3.92),(11.50,3.82),(11.48,3.63)],
      [(7.15,3.34),(7.24,3.15),(7.15,2.99)],
      [(-4.20,4.10),(-4.28,3.96),(-4.24,3.77),(-4.36,3.54)],
      [(-13.30,2.94),(-13.26,3.10),(-13.32,3.21),(-13.27,3.36)]]
    for line in cracks:
        left=[]; right=[]
        for i,(x,z) in enumerate(line):
            r=.0028 if i<len(line)-1 else .0006
            left.append((x-r,z)); right.append((x+r,z))
        cutter=k.extrude('TEMP_plaster_corner_crack',left+list(reversed(right)),'Y',FRONT-.14,FRONT+.018,'interior',0)
        boolean(plaster,cutter)
    # Все срезы — тот же минеральный материал, а не чёрная заливка cutter.
    for face in plaster.data.polygons: face.material_index=0


def building():
    global OPEN
    OPEN=openings()
    wall=k.box('STRUCTURE | front masonry',(0,FRONT+.22,H/2),(W,.44,H),'mortar',.003)
    for o in OPEN:
        cutter=k.box('TEMP_window_opening',(o['x'],FRONT,o['z']+o['h']/2),(o['w'],1.25,o['h']),'interior',0)
        boolean(wall,cutter)
    for face in wall.data.polygons: face.material_index=0
    plaster=grid_plaster()
    for o in OPEN:
        if not o['door']: window(o['x'],o['z'],o['w'],o['h'],label='LANDING' if o.get('landing') else 'FRONT WINDOW')
    for index,i in enumerate(ENTRY): entry(BAYS[i],index)
    damages(plaster)
    # Невидимые стороны — сдержанная конструктивная реконструкция того же объёма.
    rear=k.box('STRUCTURE | rear masonry, reconstructed',(0,D/2-.22,H/2),(W,.44,H),'plaster',.003)
    for x in (-13,-7.8,-2.6,2.6,7.8,13):
        for z in (1.0,4.10):
            cut=k.box('TEMP_rear_window',(x,D/2,z+.97),(1.62,1.25,1.94),'interior',0); boolean(rear,cut)
            window(x,z,1.62,1.94,y=D/2,s=1,label='REAR | reconstructed window')
    for face in rear.data.polygons: face.material_index=0
    for side in (-1,1):
        ob=k.box('STRUCTURE | side wall, reconstructed',(side*(W/2-.22),0,H/2),(.44,D-.88,H),'plaster',.003)
        for yy in (-2.7,0,2.7):
            for z in (1.0,4.10):
                cut=k.box('TEMP_side_window',(side*W/2,yy,z+.97),(1.25,1.62,1.94),'interior',0); boolean(ob,cut)
                start=len(k.PARTS); window(yy if side>0 else -yy,z,1.62,1.94,y=0,label='SIDE | reconstructed window')
                tr=Matrix.Translation((side*W/2,0,0))@Matrix.Rotation(side*pi/2,4,'Z')
                for part in k.PARTS[start:]: part.matrix_world=tr@part.matrix_world
        for face in ob.data.polygons: face.material_index=0
    # Перекрытия и внутренние перегородки задают настоящую глубину за окнами.
    for z in (.15,3.39,6.48): k.box('STRUCTURE | floor slab',(0,0,z),(W-.8,D-.8,.18),'concrete',.006)
    for x in (-13.0,-5.2,0,5.2,13.0):
        for z in (1.77,5.00): k.box('INTERIOR | estimated partition',(x,-1.8,z),(.15,6.0,3.05),'plaster',.003)
    k.box('INTERIOR | rear corridor wall',(0,1.30,3.3),(W-.8,.15,6.2),'plaster',.003)
    # Низкая кровля и тонкий металлический отлив по верху карниза.
    k.box('ROOF | low roof deck',(0,0,6.67),(W+.18,D+.18,.14),'roof',.010)
    for yy in (-D/2-.09,D/2+.09):
        k.box('ROOF | folded eaves cover',(0,yy,6.74),(W+.25,.23,.035),'metal',.003)
        k.box('ROOF | downturned drip',(0,yy+math.copysign(.10,yy),6.69),(W+.24,.012,.10),'metal',.002)
    for xx in (-W/2-.09,W/2+.09): k.box('ROOF | end flashing',(xx,0,6.74),(.20,D+.24,.035),'metal',.003)
    # Собственная вывеска сохраняет тип/масштаб таблички, реальные названия не копируются.
    k.box('SIGN | faculty board',(0,FRONT-.055,3.18),(7.4,.05,.48),'paint',.005)
    k.lettering('SIGN | original title','УЧЕБНЫЙ КОРПУС',(0,FRONT-.084,3.06),.245,role='metal')
    for x in (-3.5,3.5):
        for z in (2.99,3.37): k.cylinder('SIGN | board fixing',(x,FRONT-.084,z),.009,.007,'metal','Y',20)
    k.box('DETAIL | address tablet',(9.2,FRONT-.046,3.24),(.92,.022,.24),'metal',.003)
    k.lettering('DETAIL | fictional address','17 А',(9.2,FRONT-.06,3.16),.13,role='paint')
    # Цоколь прерывается у входов, а не запирает дверной проём.
    cuts=sorted([-W/2]+[BAYS[i]-1.03 for i in ENTRY]+[BAYS[i]+1.03 for i in ENTRY]+[W/2])
    for a,b in zip(cuts,cuts[1:]):
        if any(a<(BAYS[i])<b for i in ENTRY): continue
        k.box('PLINTH | front mineral base',((a+b)/2,FRONT-.014,.17),(b-a,.048,.34),'concrete',.004)
