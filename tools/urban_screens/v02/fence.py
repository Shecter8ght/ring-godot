"""ПО-2М: монолитная рельефная плита с фартуком и самостоятельные стаканы ФО-2."""
from math import pi,sin,cos
import bpy
from common import k,boolean,rounded_opening,sharp_planar


def frustum(name,bottom,top,z0,z1,xc=0,yc=0,role='concrete'):
    verts=[]
    for (w,d),z in ((bottom,z0),(top,z1)):
        verts.extend([(xc+x*w/2,yc+y*d/2,z) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    return k.mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],role,0)


def relief(x,z,w,h):
    verts=[]
    for y,sw,sh in ((-.010,w,h),(-.078,w*.31,h*.30)):
        verts.extend([(x+sx*sw/2,y,z+sz*sh/2) for sx,sz in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    return k.mesh('TEMP_cast_relief',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'concrete',0)


def fence():
    # Заводская карточка 2500 × 3000 × 160 мм; монтажная статья подтверждает H=3000.
    # Плита включает две ножки и фартук; положение над грунтом определяется стаканами.
    zbase=.145
    profile=[(-1.25,0),(-1.17,0),(-1.095,.46),(-.975,.46),(-.895,0),
             (.895,0),(.975,.46),(1.095,.46),(1.17,0),(1.25,0),(1.25,3),(-1.25,3)]
    plate=k.extrude('Monolithic_PO2M_cast_panel',[(x,z+zbase) for x,z in profile],'Y',-.08,.08,'concrete',.003)
    # Отформованные углубления с двух сторон, не рамка поверх цельного ящика.
    rounded_opening(plate,'Front_relief_field',2.28,1.96,(0,-.10,1.88+zbase),.17,.015)
    rounded_opening(plate,'Rear_recessed_field',2.28,1.96,(0,.115,1.88+zbase),.15,.015)
    for y in (-.102,.102):
        rounded_opening(plate,'Lower_horizontal_frieze',2.28,.235,(0,y,.66+zbase),.095,.016)
    # 5 × 4 усечённых пирамиды объединяются с плитой: одна отливка, без наложенных панелек.
    for row in range(4):
        for col in range(5):
            x=-1.13+(col+.5)*2.26/5
            z=.915+zbase+(row+.5)*1.93/4
            boolean(plate,relief(x,z,2.26/5-.002,1.93/4-.002),'UNION')
    plate['panel_nominal_dimensions_m']=[2.5,.16,3.0]
    plate['module_pitch_m']=2.5
    plate['construction']='One cast panel: relief, frame, apron and legs'
    for face in plate.data.polygons: face.material_index=0
    sharp_planar(plate,.45)
    # В паре соседних секций ножки делят один стакан. Крайняя пара здесь полная.
    for xc in (-1.25,1.25):
        # Длинная сторона стакана поперёк забора; фартук проходит между стаканами.
        cup=frustum('FO2_foundation_cup',(.75,.95),(.48,.66),0,.55,xc)
        cutter=frustum('TEMP_tapered_socket',(.21,.35),(.39,.46),.14,.75,xc)
        boolean(cup,cutter)
        bevel=cup.modifiers.new('Cast foundation arris','BEVEL'); bevel.width=.004; bevel.segments=3
        weighted=cup.modifiers.new('Face weighted normals','WEIGHTED_NORMAL'); weighted.keep_sharp=True
        cup['nominal_dimensions_XYZ_m']=[.75,.95,.55]
        cup['shared_between_adjacent_panels']=True
        clearances=[]
        for j in range(41):
            raw_z=.405*j/40
            half_socket=.5*(.21+(.39-.21)*(zbase+raw_z-.14)/(.75-.14))
            half_joint=.080+.075*raw_z/.46
            clearances.append(half_socket-half_joint)
        assert min(clearances)>.01
        cup['paired_legs_min_lateral_clearance_m']=min(clearances)
        for side in (-1,1):
            # Петли утоплены частично, как у заводской подъёмной арматуры.
            cy=side*.285
            k.section('Foundation_lifting_eye',[(xc-.035,cy,.522),(xc-.035,cy,.568),
                (xc-.025,cy,.58),(xc+.025,cy,.58),(xc+.035,cy,.568),(xc+.035,cy,.522)],.0055,'metal',12)
    for xc in (-1.105,1.105):
        points=[(xc-.04,0,3.122)]
        points += [(xc+.04*cos(pi-i*pi/16),0,3.15+.04*sin(pi-i*pi/16)) for i in range(17)]
        points += [(xc+.04,0,3.122)]
        k.section('Panel_top_lifting_loop',points,.006,'metal',16)
