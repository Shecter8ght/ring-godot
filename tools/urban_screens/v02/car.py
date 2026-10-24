"""Собственный кузов по двум снимкам одного серийного трёхдверного хэтчбека."""
import math
from math import pi,sin,cos
import bpy
import bmesh
from mathutils import Matrix,Vector
from common import k,boolean,sheet,shell_loft,rounded_panel,rounded_opening

# X — ширина, Y — продольная ось, перед -Y. Номинал из Volkswagen Vehicle data.
STATIONS=[(-2.102,.82,.215,.903),(-2.00,.839,.19,.923),(-1.82,.859,.17,.944),
 (-1.54,.877,.16,.973),(-1.27,.8795,.16,.986),(-.91,.877,.155,.98),
 (-.65,.875,.155,.973),(-.15,.878,.15,.971),(.45,.8795,.15,.98),
 (.95,.8795,.155,.989),(1.27,.877,.16,.987),(1.65,.862,.17,1.02),
 (1.93,.85,.19,1.06),(2.102,.83,.23,1.06)]
AXLES=(-1.314,1.264)
WHEEL_Z=.3173


def lerp(a,b,t): return a+(b-a)*t


def catmull(a,b,c,d,t):
    return .5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)


def station(y):
    for i in range(len(STATIONS)-1):
        if STATIONS[i][0]<=y<=STATIONS[i+1][0]:
            t=(y-STATIONS[i][0])/(STATIONS[i+1][0]-STATIONS[i][0])
            return tuple(catmull(STATIONS[max(0,i-1)][q],STATIONS[i][q],STATIONS[i+1][q],STATIONS[min(len(STATIONS)-1,i+2)][q],t) for q in range(4))
    return STATIONS[0] if y<STATIONS[0][0] else STATIONS[-1]


def body_x(y,z):
    _,w,z0,z1=station(y)
    profile=[(z0,.79),(z0+.04,.94),(z0+.12,.992),(z1-.16,1),(z1-.05,.976),(z1,.916)]
    for (a,x0),(b,x1) in zip(profile,profile[1:]):
        if a<=z<=b: return w*lerp(x0,x1,(z-a)/max(.001,b-a))
    return w*.916 if z>z1 else w*.79


def rotate_about(ob,pivot,axis,angle):
    p=Vector(pivot)
    ob.matrix_world=Matrix.Translation(p)@Matrix.Rotation(angle,4,axis)@Matrix.Translation(-p)@ob.matrix_world


def body_ring(y):
    _,w,z0,z1=station(y)
    left=[(-w*.79,z0),(-w*.94,z0+.04),(-w*.992,z0+.12),(-w,z1-.16),
          (-w*.976,z1-.05),(-w*.916,z1),(-w*.72,z1+.018),(-w*.36,z1+.03)]
    return [(x,nose_y(y,x,w),z) for x,z in left+[(0,z1+.034)]+[(-x,z) for x,z in reversed(left)]]


def nose_y(y,x,w):
    front=max(0,1-(y+2.102)/.34)
    rear=max(0,1-(2.102-y)/.31)
    shoulder=max(0,(abs(x)-.30)/.58)**2
    return y+front*.20*shoulder-rear*.12*shoulder


def front_y(x): return -2.102+.20*max(0,(abs(x)-.30)/.58)**2
def rear_y(x): return 2.102-.12*max(0,(abs(x)-.30)/.58)**2


def recessed_lamp(name,points,depth=.09):
    # Открытая лицевая чаша с боковыми стенками и настоящим задником.
    n=len(points)
    front=[tuple(p) for p in points]
    back=[(x,y+depth,z) for x,y,z in front]
    verts=front+back
    faces=[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    faces.append(tuple(n+i for i in range(n)))
    ob=k.mesh(name,verts,faces,'interior',0,True)
    mod=ob.modifiers.new('Moulded lamp bowl thickness','SOLIDIFY'); mod.thickness=.002
    return ob


def body_top(y,x):
    _,w,_,z1=station(y)
    knots=[(0,z1+.034),(.36*w,z1+.03),(.72*w,z1+.018),(.916*w,z1)]
    for (a,z0),(b,z2) in zip(knots,knots[1:]):
        if a<=abs(x)<=b: return lerp(z0,z2,(abs(x)-a)/(b-a))
    return z1


def surface(name,fn,nu=40,nv=24,role='paint',thickness=.003):
    return k.patch(name,fn,nu,nv,role,thickness)


def car_loft(name,rings):
    # Скруглённый торец не плоский: явные треугольники вместо non-planar n-gon.
    n=len(rings[0]); verts=[v for ring in rings for v in ring]
    faces=[]
    for j in range(len(rings)-1):
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n; c=(j+1)*n+(i+1)%n; d=(j+1)*n+i
            faces.extend([(a,b,c),(a,c,d)])
    for start,rev in ((0,True),((len(rings)-1)*n,False)):
        centre=sum((Vector(v) for v in verts[start:start+n]),Vector())/n
        ci=len(verts); verts.append(tuple(centre))
        for i in range(n):
            f=(ci,start+i,start+(i+1)%n)
            faces.append(tuple(reversed(f)) if rev else f)
    return k.mesh(name,verts,faces,'paint',0,True)


def outline(fn,nu=40,nv=24):
    return ([fn(i/nu,0) for i in range(nu)]+[fn(1,j/nv) for j in range(nv)]+
            [fn(1-i/nu,1) for i in range(nu)]+[fn(0,1-j/nv) for j in range(nv+1)])


def glazing(name,fn,nu=40,nv=24,gasket=.004):
    ob=surface(name,fn,nu,nv,'glass',.006)
    k.section(name+'_rubber_seal',outline(fn,nu,nv),gasket,'rubber',12)
    return ob


def rounded_profile(poly,r=.018,n=6):
    result=[]
    for i,p in enumerate(poly):
        p=Vector(p); a=Vector(poly[i-1]); b=Vector(poly[(i+1)%len(poly)])
        d=min(r,(p-a).length*.3,(p-b).length*.3)
        a=p+(a-p).normalized()*d; b=p+(b-p).normalized()*d
        for j in range(n):
            t=j/n
            result.append(tuple(a*(1-t)**2+p*(2*(1-t)*t)+b*t*t))
    return result


def body():
    rings=[body_ring(-2.102+4.204*i/176) for i in range(177)]
    shell=car_loft('Stamped_body_quarters_and_wings',rings)
    # Колёсные ниши вырезаются насквозь; это не чёрные круги поверх кузова.
    for yc in AXLES:
        cut=k.cylinder('TEMP_arch_cut',(0,yc,WHEEL_Z),.347,2.3,axis='X',n=128)
        boolean(shell,cut)
    # Настоящий объём салона и багажного проёма, без горизонтальной плиты под окнами.
    cut=k.box('TEMP_cabin_void',(0,.58,1.16),(1.448,2.48,1.33),'interior',0)
    boolean(shell,cut)
    cut=k.box('TEMP_boot_opening',(0,1.73,1.13),(1.33,1.12,1.03),'interior',0)
    boolean(shell,cut)
    # Отдельный капот с зазором по контуру.
    def hood(u,v):
        t=2*u-1; width=lerp(.594,.729,v)
        x=t*width
        y=lerp(-2.003+.14*t*t,-.747+.012*t*t,v)
        return x,y,body_top(y,x)+.0008
    hood_xy=[(p[0]*1.004,p[1]+(-.002 if p[1]<-1.4 else .002)) for p in outline(hood,64,60)[:-1]]
    cut=k.extrude('TEMP_engine_hood_recess',hood_xy,'Z',.70,1.5,'interior',0)
    boolean(shell,cut)
    surface('Separate_crowned_bonnet',hood,64,60,'paint',.003)
    k.section('Bonnet_shut_line',outline(hood,64,60),.0017,'interior',8)
    # Две самостоятельные двери; по фото выбран трёхдверный кузов.
    for side in (-1,1):
        yz=[(-.846,.222),(.586,.222),(.616,.28),(.616,.951),(-.736,.951),(-.826,.36)]
        x0,x1=sorted((side*.70,side*1.02))
        cut=k.extrude('TEMP_door_aperture',yz,'X',x0,x1,'interior',0)
        boolean(shell,cut)
        def door(u,v):
            z=.227+.718*v
            ymin=-.837+.105*v
            ymax=.608-.016*(1-v)**4
            y=lerp(ymin,ymax,u)
            x=body_x(y,z)-.002-.004*sin(pi*u)*sin(pi*v)
            return side*x,y,z
        surface('Separate_door_skin_L' if side<0 else 'Separate_door_skin_R',door,64,42,'paint',.008)
        k.section('Door_3mm_shut_line',outline(door,64,42),.0015,'interior',8)
        # Внутренняя обшивка и ручка двери видны через стекло.
        k.box('Interior_door_trim',(side*.782,-.08,.63),(.025,1.26,.43),'interior',.025)
        k.box('Door_inner_armrest',(side*.75,-.02,.67),(.075,.46,.06),'interior',.018)
        for y in (-.18,-.13): k.box('Door_window_rocker_switch',(side*.717,y,.705),(.018,.035,.008),'plastic',.003)
        k.soft('Exterior_pull_recess',(side*(body_x(.405,.83)+.003),.405,.83),(.009,.173,.052),'interior',.5)
        k.section('Exterior_handle',[(side*.891,.343,.83),(side*.904,.36,.84),(side*.904,.455,.84),(side*.891,.472,.83)],.009,'paint',16)
        # Широкий защитный молдинг в реальном месте контакта.
        k.box('Door_impact_moulding',(side*.884,-.09,.607),(.014,1.31,.045),'rubber',.008)
        k.box('Quarter_impact_moulding',(side*.884,.776,.607),(.014,.27,.045),'rubber',.007)
    # Скрытый пол, задняя стенка двигателя и багажная полка — видимая внутренняя глубина.
    k.box('Cabin_floor',(0,.49,.355),(1.43,2.5,.045),'interior',.01)
    k.box('Boot_load_floor',(0,1.57,.48),(1.29,.96,.035),'interior',.008)
    for side in (-1,1):
        k.box('Boot_side_liner',(side*.632,1.59,.66),(.04,.94,.34),'interior',.018)
        # Сформованные губы арок и внутренние подкрылки.
        for yc in AXLES:
            def lip(u,v):
                a=-.28+(pi+.56)*u; r=.348+.014*v
                y=yc+r*cos(a); z=WHEEL_Z+r*sin(a)
                return (side*(body_x(y,z)+.002),y,z)
            surface('Stamped_wheel_arch_return',lip,96,3,'paint',.002)
            surface('Black_inner_wheelhouse',lambda u,v:(side*lerp(.64,.86,v),yc+.345*cos(pi*u),WHEEL_Z+.345*sin(pi*u)),80,12,'interior',.003)
    # Локальные отдельные бамперы оставляют чистый шов по стыку.
    for is_front in (True,False):
        y0,y1=(-2.102,-1.81) if is_front else (1.81,2.102)
        ztop=.667 if is_front else .611
        cut=k.box('TEMP_bumper_separation',(0,(y0+y1)/2,(ztop-.002)/2),(2.2,y1-y0+.004,ztop-.002),'interior',0)
        boolean(shell,cut)
        br=[]
        for i in range(25):
            y=lerp(y0,y1,i/24); _,w,zb,_=station(y)
            wt=body_x(y,ztop)
            prof=[(-w*.77,.23),(-w*.96,.26),(-w,.36),(-w,ztop-.08),(-wt,ztop),
                  (wt,ztop),(w,ztop-.08),(w,.36),(w*.96,.26),(w*.77,.23)]
            br.append([(x,nose_y(y,x,w),z) for x,z in prof])
        bumper=car_loft('Rounded_front_bumper' if is_front else 'Rounded_rear_bumper',br)
        if is_front:
            rounded_opening(bumper,'Lower_grille_opening',1.02,.165,(0,-2.055,.386),.35,.025)
            k.box('Lower_grille_dark_back',(0,-1.98,.386),(1.0,.01,.15),'interior',.008)
            for j in range(6):
                k.section('Lower_grille_horizontal_louvre',[(x,front_y(x)-.004,.324+j*.024) for x in [-.5+i/40 for i in range(41)]],.0035,'plastic',8)
            for x in (-.35,-.175,0,.175,.35): k.box('Lower_grille_vertical_stiffener',(x,-2.07,.386),(.007,.015,.14),'plastic',.001)
            for side in (-1,1):
                fy=front_y(side*.651)
                rounded_opening(bumper,'Fog_lamp_recess',.24,.158,(side*.651,fy+.035,.385),.30,.038)
                rounded_panel('Fog_lamp_dark_housing',.235,.152,.105,(side*.651,fy+.035,.385),'interior',.035,.001)
                k.cylinder('Fog_lamp_reflector',(side*.651,fy-.006,.385),.052,.025,'chrome','Y',64)
                k.cylinder('Fog_lamp_lens',(side*.651,fy-.021,.385),.047,.006,'glass','Y',64)
                k.section('Bumper_protective_insert',[(side*x,front_y(x)-.007,.602) for x in [.46+i*.30/24 for i in range(25)]],.017,'rubber',12)
        else:
            surface('Rear_black_lower_valance',lambda u,v:((2*u-1)*.68,rear_y((2*u-1)*.68)+.005,.23+.17*v),64,12,'rubber',.025)
            for side in (-1,1): k.box('Rear_reflector',(side*.6,rear_y(.6)+.008,.56),(.18,.012,.025),'reflector',.008)
            rounded_opening(bumper,'Rear_number_plate_recess',.56,.135,(0,2.095,.512),.18,.012)
            rounded_panel('Rear_number_plate_back',.552,.128,.016,(0,2.062,.512),'interior',.009,.001)
            rounded_panel('Rear_registration_plate',.52,.11,.007,(0,2.075,.512),'metal',.006,.0007)
            surface('Rear_bumper_upper_return',lambda u,v:((2*u-1)*.72,rear_y((2*u-1)*.72)-.023*v,.611+.072*v),64,8,'paint',.014)
    # Тонкие боковые пороги с загибом, без геометрического раздувания масштаба.
    for side in (-1,1):
        k.section('Sill_lower_return',[(side*.792,-.91,.194),(side*.819,-.75,.19),(side*.821,.9,.19),(side*.806,.96,.2)],.012,'paint',16)
    return shell


def cabin():
    # Крыша и стёкла имеют двойную кривизну, стойки выполнены широкими панелями.
    def roof(u,v):
        t=2*u-1; y=lerp(-.13,1.50,v)
        width=.684-.018*cos(pi*v)
        return t*width,y,1.429+.056*(1-t*t)-.019*(2*v-1)**2
    surface('Double_curvature_roof_skin',roof,72,72,'paint',.004)
    def windscreen(u,v):
        t=2*u-1; width=lerp(.744,.655,v)
        return t*width,lerp(-.753,-.123,v)-.033*(1-t*t)*sin(pi*v),lerp(.968,1.423,v)+.039*(1-t*t)
    glazing('Curved_laminated_windscreen',windscreen,72,56,.005)
    for side in (-1,1):
        def a_pillar(u,v):
            inner=Vector(windscreen(0 if side<0 else 1,v))
            outer=Vector((side*lerp(.821,.71,v),lerp(-.697,-.035,v),lerp(.964,1.423,v)))
            return tuple(inner.lerp(outer,u))
        surface('Broad_A_pillar',a_pillar,8,56,'paint',.024)
        def front_side(u,v):
            y=lerp(lerp(-.684,-.029,v),.545,u)
            z=.974+.448*v+.014*sin(pi*u)*v
            x=lerp(.850,.712,v)+.009*sin(pi*u)*sin(pi*v)
            return side*x,y,z
        glazing('Long_front_door_glass',front_side,56,36,.005)
        def rear_side(u,v):
            y=lerp(.655,lerp(1.578,1.217,v),u)
            z=.986+.435*v-.024*u*v
            x=lerp(.858,.710,v)-.018*u*v+.006*sin(pi*u)
            return side*x,y,z
        glazing('Rear_quarter_glass',rear_side,52,36,.005)
        def b_pillar(u,v):
            return side*lerp(.86,.719,v),lerp(.557,.643,u),lerp(.967,1.44,v)
        surface('Black_B_pillar',b_pillar,6,32,'plastic',.025)
        def c_pillar(u,v):
            a=Vector((side*lerp(.858,.692,v),lerp(1.6,1.232,v),lerp(.986,1.4,v)))
            b=Vector((side*lerp(.76,.667,v),lerp(2.00,1.50,v),lerp(.958,1.414,v)))
            return tuple(a.lerp(b,u))
        surface('Broad_swept_C_pillar',c_pillar,22,42,'paint',.026)
        # Крашеная рейка над боковыми стёклами связана с крышей.
        surface('Roof_side_pressing',lambda u,v:(side*lerp(.709,.669,u),lerp(-.035,1.50,v),1.423+.008*sin(pi*v)+u*.012),5,64,'paint',.015)
        # Зеркало: основание на треугольнике двери, обтекаемый корпус и утопленное стекло.
        sheet('Mirror_sail_triangle',[(side*.827,-.694,.976),(side*.833,-.485,.978),(side*.779,-.544,1.084)],'plastic',.014)
        k.beam('Mirror_fold_neck',(side*.833,-.574,1.026),(side*.946,-.575,1.056),.047,.048,'plastic',.01)
        k.soft('Aerodynamic_mirror_shell',(side*.976,-.574,1.069),(.17,.235,.126),'paint',.65)
        k.soft('Mirror_glass_inset',(side*.976,-.447,1.069),(.139,.006,.088),'chrome',.45)
        k.box('Mirror_lower_black_housing',(side*.98,-.572,1.027),(.155,.207,.02),'plastic',.009)
    # Дворники находятся на лобовом стекле, а не за ним или на капоте.
    for x,y in ((-.38,-.77),(.24,-.77)):
        k.section('Wiper_metal_arm',[(x,y,.988),(x+.08,y+.09,1.045),(x+.22,y+.18,1.105)],.003,'plastic',10)
        k.section('Wiper_rubber_blade',[(x+.1,y+.13,1.072),(x+.34,y+.24,1.15)],.006,'rubber',12)
    k.box('Windscreen_cowl',(0,-.785,.956),(1.34,.13,.025),'interior',.008)
    for x in [-.58+i*.04 for i in range(30)]: k.box('Cowl_vent_slot',(x,-.812,.972),(.022,.04,.003),'interior',.0005)
    # Антенна на задней части крыши — без вымышленных длинных стоек.
    k.soft('Roof_aerial_base',(0,1.04,1.475),(.05,.105,.018),'rubber',.5)
    k.bar('Short_roof_aerial',(0,1.04,1.48),(0,1.15,1.67),.004,'rubber',12)


def lighting(shell):
    for side in (-1,1):
        shape=rounded_profile([(.341,.678),(.777,.678),(.807,.716),(.786,.83),(.735,.905),(.523,.899),(.425,.825),(.362,.748)])
        cut=k.extrude('TEMP_headlamp_body_aperture',[(side*x,z) for x,z in shape],'Y',-2.4,-1.65,'interior',0)
        boolean(shell,cut)
        points=[(side*x,front_y(x)-.006,z) for x,z in shape]
        recessed_lamp('Headlamp_moulded_back_shell',points,.11)
        sheet('Headlamp_curved_cover_lens',[(x,y-.008,z) for x,y,z in points],'glass',.005)
        k.section('Headlamp_outer_gasket',points+[points[0]],.004,'rubber',12)
        # Две чаши отражателей и нижняя полоска указателя поворота.
        for x,r in ((.524,.074),(.696,.055)):
            yy=front_y(x)+.022
            k.lathe('Headlamp_parabolic_reflector',[(.024,.047),(.032,.025),(.05,.007),(r,0),(r+.003,.004),(.052,.013),(.034,.031),(.024,.047)],(side*x,yy,.788),'Y','chrome',64)
            k.cylinder('Headlamp_bulb_cap',(side*x,yy+.021,.788),.024,.019,'glass','Y',32)
        for j in range(17):
            x=.38+j*.023; yy=front_y(x)-.002
            k.box('Headlamp_indicator_optic_rib',(side*x,yy,.696),(.011,.012,.021),'diffuser',.001)
    # Верхняя решётка прорезана в кузове между фарами.
    rounded_opening(shell,'Upper_radiator_grille',.715,.139,(0,-2.05,.817),.26,.022)
    k.box('Upper_grille_back',(0,-1.996,.817),(.70,.008,.13),'interior',.007)
    for z in (.772,.814,.856): k.section('Upper_grille_chrome_bar',[(x,front_y(x)-.004,z) for x in [-.35+i*.70/32 for i in range(33)]],.005,'chrome',10)
    # Собственный маленький знак вместо логотипа прототипа.
    k.extrude('Original_grille_emblem',[(-.028,.814),(0,.846),(.028,.814),(0,.782)],'Y',-2.116,-2.108,'metal',.001)
    for side in (-1,1):
        profile=rounded_profile([(.534,.761),(.808,.761),(.806,.992),(.718,1.007),(.588,.949)],.012)
        def lamp_y(x,z): return rear_y(x)+.005
        outer=[(side*x,lamp_y(x,z),z) for x,z in profile]
        cut=k.extrude('TEMP_rear_lamp_aperture',[(side*x,z) for x,z in profile],'Y',1.58,2.3,'interior',0)
        boolean(shell,cut)
        recessed_lamp('Rear_outer_lamp_housing',outer,-.12)
        sheet('Rear_outer_lamp_cover',[(x,y+.006,z) for x,y,z in outer],'glass',.006)
        k.section('Rear_lamp_outer_gasket',outer+[outer[0]],.004,'rubber',12)
        for x,z,r in ((.717,.923,.069),(.603,.87,.039)):
            yy=lamp_y(x,z)-.030
            k.cylinder('Rear_lamp_round_optic',(side*x,yy,z),r,.010,'diffuser','Y',64)
            k.ring('Rear_lamp_optic_bezel',(side*x,yy+.006,z),r+.003,.003,'chrome','Y',64)
    # Номерные панели и небольшой повторитель на переднем крыле.
    rounded_panel('Front_number_plate',.52,.11,.008,(0,-2.113,.563),'metal',.006,.0007)
    for side in (-1,1):
        k.soft('Wing_indicator',(side*.883,-.91,.877),(.008,.075,.022),'glass',.45)
    k.lathe('Hollow_exhaust_tip',[(.026,0),(.029,0),(.029,.19),(.024,.19),(.024,0),(.026,0)],(-.52,1.93,.225),'Y','metal',64)
    # Только локальный мусор после пересечения сложных Boolean, без ремеша кузова.
    bm=bmesh.new(); bm.from_mesh(shell.data)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(shell.data); bm.free()
    # Применить только фаску кузова и удалить её вырожденные микрограни.
    bpy.context.view_layer.objects.active=shell
    for mod in list(shell.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bm=bmesh.new(); bm.from_mesh(shell.data)
    bmesh.ops.dissolve_degenerate(bm,dist=2e-6,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(shell.data); bm.free()


def hatch():
    # Отдельная редактируемая сборка. Машина статичная, риг открывания не заявляется.
    hinge=Vector((0,1.50,1.437))
    empty=bpy.data.objects.new('HATCH | static closed assembly',None)
    k.COLLECTION.objects.link(empty); empty.location=hinge
    empty['configuration']='Static closed geometry; not rigged'
    start=len(k.PARTS)
    def fn(u,v):
        t=2*u-1
        if v<.10: width=lerp(.669,.526,v/.10)
        elif v<.38: width=lerp(.526,.566,(v-.10)/.28)
        elif v<.52: width=lerp(.566,.659,(v-.38)/.14)
        else: width=lerp(.659,.65,(v-.52)/.48)
        y=lerp(2.079,2.058,v/.39) if v<.39 else lerp(2.058,1.50,(v-.39)/.61)
        return (t*width,y+.009*t*t,lerp(.685,1.437,v)+.012*(1-t*t)*v)
    surface('Hatch_lower_painted_panel',lambda u,v:fn(u,.52*v),64,32,'paint',.018)
    surface('Hatch_top_header',lambda u,v:fn(u,.948+.052*v),64,5,'paint',.018)
    for side in (0,1):
        surface('Hatch_side_frame',lambda u,v:fn(.057*u if side==0 else .943+.057*u,.52+.428*v),6,40,'paint',.018)
    glazing('Curved_rear_hatch_glass',lambda u,v:fn(.062+.876*u,.528+.41*v),64,44,.005)
    k.section('Rear_hatch_outer_seal',outline(fn,64,48),.0045,'rubber',12)
    # Обогрев и стеклоочиститель — геометрические проверочные детали.
    for j in range(11):
        v=.55+j*.034
        k.section('Rear_glass_heater_line',[fn(.09+.82*i/48,v) for i in range(49)],.00035,'metal',6)
    p=Vector(fn(.62,.56))
    k.cylinder('Rear_wiper_pivot',tuple(p+Vector((0,.012,0))),.015,.025,'plastic','Y',32)
    k.section('Rear_wiper_blade',[tuple(Vector(fn(.34,.55))+Vector((0,.014,.005))),tuple(Vector(fn(.76,.55))+Vector((0,.014,.005)))],.0055,'rubber',12)
    hy=fn(.5,(.827-.685)/.752)[1]
    k.soft('Hatch_handle_recess',(0,hy+.012,.827),(.12,.025,.042),'interior',.5)
    surface('Roof_rear_spoiler',lambda u,v:((2*u-1)*.713,1.49+.17*v,1.453+.018*sin(pi*u)-.035*v),56,12,'paint',.016)
    for ob in k.PARTS[start:]:
        # Обновить pivot до вычисления parent inverse: иначе Blender ещё видит
        # единичную matrix_world и прибавляет координаты петли второй раз.
        bpy.context.view_layer.update()
        ob.parent=empty
        ob.matrix_parent_inverse=empty.matrix_world.inverted()
    # Газовые упоры отдельными узлами; их видимые посадочные места сохранены.
    for side in (-1,1):
        k.bar('Hatch_strut_body',(side*.616,1.81,.731),(side*.616,1.54,1.19),.008,'metal',16)
        k.bar('Hatch_strut_rod',(side*.616,1.54,1.19),(side*.616,1.42,1.39),.004,'chrome',12)
    return empty


def wheels():
    # 205/55 R16: наружный радиус около 0,317 м, без завышения размера колёс.
    for side in (-1,1):
        for yc in AXLES:
            cx=side*.7695
            profile=[(.203,-.103),(.265,-.103),(.305,-.085),(.3173,-.064),(.3173,.064),
                     (.305,.085),(.265,.103),(.203,.103),(.198,.081),(.198,-.081),(.203,-.103)]
            k.lathe('Real_section_road_tyre',profile,(cx,yc,WHEEL_Z),'X','rubber',128)
            # Единая сетка сегментов протектора: шесть смещённых дорожек.
            verts=[]; faces=[]
            for lane in range(6):
                xa=-.091+lane*.0305; xb=xa+.0265
                for j in range(96):
                    a0=2*pi*(j+(lane%2)*.47)/96; a1=a0+2*pi*.79/96
                    # Небольшой наклон блоков образует поперечные канавки.
                    ring=[]
                    for r in (.3166,.3186):
                        for x,a in ((xa,a0),(xb,a0+.006),(xb,a1+.006),(xa,a1)):
                            ring.append((cx+x,yc+r*cos(a),WHEEL_Z+r*sin(a)))
                    n=len(verts); verts.extend(ring)
                    faces += [tuple(n+t for t in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
            k.mesh('Staggered_tread_blocks',verts,faces,'rubber',.0003)
            outer=side*.878
            k.lathe('Cast_alloy_rim',[(.169,-.018),(.196,-.018),(.206,-.009),(.206,.011),(.198,.02),(.17,.02),(.169,-.018)],(outer,yc,WHEEL_Z),'X','metal',96)
            # Отдельный диск тормоза за настоящими промежутками спиц.
            k.lathe('Brake_disc',[(.045,-.005),(.165,-.005),(.165,.005),(.045,.005),(.045,-.005)],(side*.824,yc,WHEEL_Z),'X','metal',96)
            for j in range(10):
                a=2*pi*j/10
                yz=[]
                for r,t in ((.05,-.14),(.10,-.12),(.194,-.045),(.198,.035),(.12,.045),(.055,.14)):
                    yz.append((yc+r*cos(a+t),WHEEL_Z+r*sin(a+t)))
                k.extrude('Contoured_alloy_wheel_spoke',yz,'X',outer-.012,outer+.012,'metal',.002)
            k.cylinder('Wheel_centre_cap',(outer+side*.015,yc,WHEEL_Z),.048,.025,'metal','X',64)
            for j in range(5):
                a=2*pi*j/5
                k.bolt('Wheel_lug',(outer+side*.03,yc+.036*cos(a),WHEEL_Z+.036*sin(a)),'X',.006)
            k.soft('Brake_caliper',(side*.828,yc-.115,WHEEL_Z+.07),(.045,.068,.11),'metal',.5)
            # Ось и ступица находятся внутри колеса.
            k.cylinder('Wheel_hub_axle',(cx,yc,WHEEL_Z),.037,.22,'metal','X',48)


def interior():
    # Видимые формы панели сверены с официальной интерьерной фотографией ref_05.
    surface('Dashboard_top_skin',lambda u,v:((2*u-1)*.727,lerp(-.738,-.36,v),.951+.055*sin(pi*u)-.16*v),64,32,'interior',.03)
    k.box('Dashboard_lower_body',(0,-.48,.775),(1.37,.27,.23),'interior',.045)
    k.soft('Instrument_binnacle',(-.37,-.405,.963),(.49,.2,.19),'interior',.5)
    for x,r in ((-.465,.055),(-.275,.055),(-.37,.035)):
        k.cylinder('Instrument_dial',(x,-.286,.98),r,.008,'screen','Y',64)
        k.ring('Instrument_bezel',(x,-.293,.98),r+.003,.003,'chrome','Y',64)
    k.box('Centre_stack',(0,-.315,.79),(.33,.07,.44),'plastic',.022)
    for x in (-.085,.085):
        k.box('Centre_air_vent',(x,-.36,.971),(.128,.02,.069),'interior',.01)
        for j in range(5): k.box('Air_vent_slat',(x,-.375,.949+j*.0105),(.118,.009,.004),'plastic',.0008)
    rounded_panel('Radio_headunit',.27,.108,.014,(0,-.366,.851),'interior',.009,.001)
    k.box('Radio_display',(0,-.378,.86),(.174,.004,.039),'screen',.003)
    for x in (-.11,.11): k.cylinder('Radio_rotary_knob',(x,-.384,.854),.016,.016,'plastic','Y',40)
    for x in (-.088,0,.088): k.cylinder('Climate_control_knob',(x,-.377,.703),.025,.02,'plastic','Y',48)
    # Руль наклонён вокруг своей оси, а не вокруг нулевой точки сцены.
    centre=(-.365,-.216,1.002)
    start=len(k.PARTS)
    k.ring('Steering_wheel_rim',centre,.174,.018,'rubber','Y',96)
    k.soft('Steering_central_pad',centre,(.21,.064,.158),'interior',.6)
    for a in (.15,pi-.15,1.5*pi):
        k.beam('Steering_spoke',(-.365+.06*cos(a),-.216,1.002+.06*sin(a)),(-.365+.158*cos(a),-.216,1.002+.158*sin(a)),.027,.014,'plastic',.006)
    for ob in k.PARTS[start:]: rotate_about(ob,centre,'X',math.radians(13))
    k.bar('Steering_column',(-.365,-.27,.96),(-.365,-.43,.82),.034,'plastic',32)
    k.box('Floor_centre_console',(0,.19,.464),(.23,1.2,.18),'interior',.03)
    k.soft('Gear_selector_boot',(0,-.02,.572),(.14,.18,.10),'rubber',.4)
    k.bar('Gear_selector_stem',(0,-.02,.6),(0,-.04,.7),.012,'metal',24)
    k.soft('Gear_selector_knob',(0,-.04,.718),(.055,.085,.042),'plastic',.6)
    for x in (-.37,.37):
        k.soft('Front_seat_base',(x,.20,.46),(.50,.52,.16),'interior',.35)
        k.soft('Front_seat_centre_cushion',(x,.17,.55),(.35,.46,.10),'fabric',.35)
        for dx in (-.215,.215): k.soft('Front_seat_side_bolster',(x+dx,.18,.559),(.085,.47,.16),'interior',.45)
        start=len(k.PARTS)
        k.soft('Front_seat_back_centre',(x,.44,.846),(.37,.11,.56),'fabric',.35)
        for dx in (-.21,.21): k.soft('Front_seat_back_bolster',(x+dx,.424,.848),(.1,.17,.59),'interior',.45)
        for ob in k.PARTS[start:]: rotate_about(ob,(x,.44,.59),'X',math.radians(-9))
        for dx in (-.08,.08): k.bar('Headrest_chrome_post',(x+dx,.52,1.10),(x+dx,.52,1.22),.006,'chrome',16)
        k.soft('Front_headrest',(x,.525,1.23),(.28,.12,.18),'interior',.4)
        for dx in (-.18,.18): k.bar('Seat_runner',(x+dx,-.07,.36),(x+dx,.53,.36),.012,'metal',16)
    k.soft('Rear_bench_cushion',(0,1.12,.531),(1.34,.47,.14),'interior',.3)
    k.soft('Rear_bench_back',(0,1.35,.795),(1.34,.135,.52),'interior',.35)
    for x in (-.44,0,.44):
        k.soft('Rear_bench_headrest',(x,1.39,1.10),(.245,.105,.14),'interior',.4)
    for x in (-.47,-.33,-.2): k.box('Driver_pedal',(x,-.69,.43),(.065,.03,.12),'rubber',.005)
    k.soft('Interior_rear_view_mirror',(0,-.054,1.352),(.235,.041,.071),'interior',.45)
    k.bar('Interior_mirror_mount',(0,-.10,1.41),(0,-.05,1.365),.008,'plastic',16)


def car():
    shell=body()
    cabin()
    lighting(shell)
    hatch()
    wheels()
    interior()
