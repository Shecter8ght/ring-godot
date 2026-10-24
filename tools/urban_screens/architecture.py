"""Оригинальные архитектурные модули, без размещения в игровых уровнях."""
import math
from math import pi,sin,cos
import meshkit as k
from street import wire_grid,cabinet_shell
REGISTRY={}
def model(fn): REGISTRY[fn.__name__]=fn; return fn


@model
def canopy():
    k.beam('Main_RHS_column',(0,1.2,0),(0,1.2,3.18),.16,.18,bevel=.006)
    k.foot('Column_base',0,1.2,.34,.34)
    for x in (-1.5,0,1.5):
        k.beam('Cantilever_rafter',(x,1.25,3.1),(x,-1.5,3.25),.07,.12)
        k.bar('Tension_tie',(x,1.2,3.28),(x,-1.3,3.22),.009)
        for y in (-1.43,-.5,.5,1.25):
            k.box('Glass_clamp',(x,y,3.28),(.1,.055,.025),'metal',.004)
            k.bolt('Clamp_screw',(x,y,3.3),r=.005)
    for y in (-1.48,-.5,.5,1.25): k.beam('Glazing_purlin',(-1.6,y,3.23),(1.6,y,3.23),.055,.06)
    for i in range(2):
        for j in range(3): k.box('Laminated_glass_pane',(-.76+i*1.52,-1+j*.9,3.29),(1.48,.86,.016),'glass',.001)
    k.beam('Knee_brace',(0,1.2,2.35),(0,-.1,3.18),.07,.07)


@model
def guard_booth():
    k.box('Raised_floor',(0,0,.07),(2.1,1.9,.14),'metal',.012)
    for x in (-1,1):
        for y in (-.9,.9): k.beam('Corner_RHS',(x,y,.14),(x,y,2.5),.065,.065)
    for y in (-.92,.92):
        k.box('Lower_insulated_panel',(0,y,.6),(2.02,.045,.9),'paint',.004)
        for z in (1.08,2.38): k.box('Window_crossbar',(0,y,z),(2.05,.06,.055),'metal',.003)
        for x in (-.5,.5): k.box('Window_pane',(x,y,1.73),(.94,.012,1.24),'glass',.002)
        k.box('Window_mullion',(0,y,1.73),(.035,.04,1.28),'metal',.002)
    k.box('Left_lower_panel',(-1.02,0,.6),(.045,1.75,.9),'paint',.003)
    k.box('Left_window',(-1.02,0,1.73),(.014,1.73,1.23),'glass',.002)
    k.box('Door_leaf',(1.025,0,1.29),(.045,1.1,2.3),'paint',.004)
    k.box('Door_window',(1.052,0,1.7),(.012,.88,.94),'glass',.002)
    k.bar('Door_pull',(1.08,-.39,1.0),(1.08,-.39,1.24),.011)
    for z in (.45,2.13): k.cylinder('Door_hinge',(1.045,.59,z),.014,.13)
    k.box('Overhanging_roof',(0,0,2.55),(2.22,2.02,.15),'paint',.01)
    for y in (-1,1): k.box('Roof_drip_edge',(0,y,2.48),(2.22,.025,.05),'metal',.002)
    k.box('Internal_desk',(0,.56,1.03),(1.4,.48,.04),'wood',.006)


@model
def coffee_kiosk():
    for x in (-1.35,1.35):
        k.box('Insulated_side_wall',(x,0,1.25),(.1,1.8,2.5),'paint',.004)
        for j in range(20): k.box('Side_vertical_rib',(x+math.copysign(.053,x),-.84+j*.088,1.3),(.012,.024,2.4),'metal',.002)
    k.box('Rear_wall',(0,.86,1.25),(2.6,.08,2.5),'paint',.005)
    k.box('Front_lower_wall',(0,-.85,.48),(2.6,.08,.96),'paint',.005)
    k.box('Deep_timber_counter',(0,-.91,1.01),(2.7,.55,.07),'wood',.01)
    for x in (-1.27,1.27): k.box('Shutter_guide',(x,-.91,1.75),(.06,.09,1.36),'metal',.003)
    for j in range(5): k.box('Partly_lowered_shutter_slat',(0,-.9,2.39-j*.065),(2.48,.04,.06),'metal',.009)
    k.box('Roof_fascia',(0,-.08,2.55),(2.85,2.02,.2),'paint',.012)
    k.lettering('Fictional_coffee_name','КОФЕ / 04',(0,-1.105,2.5),.14)
    k.box('Service_worktop',(0,.3,.92),(2.3,.6,.045),'metal',.006)
    for x in (-1,1): k.box('Low_cabinet',(x,.35,.47),(.5,.6,.9),'paint',.008)


@model
def revolving_door():
    for z in (.045,2.68):
        k.lathe('Circular_door_track',[(1.2,z-.025),(1.3,z-.025),(1.3,z+.025),(1.2,z+.025),(1.2,z-.025)],role='metal',n=128)
    for side in (-1,1):
        start=-.95 if side==1 else pi-.95
        end=.95 if side==1 else pi+.95
        for layer in range(3):
            a0=start+(end-start)*layer/3+.01; a1=start+(end-start)*(layer+1)/3-.01
            k.patch('Curved_safety_glass',lambda u,v:(1.24*cos(a0+(a1-a0)*u),1.24*sin(a0+(a1-a0)*u),.09+2.54*v),36,4,'glass',.012)
        for a in (start,end): k.bar('Jamb',(1.245*cos(a),1.245*sin(a),.08),(1.245*cos(a),1.245*sin(a),2.64),.022)
    k.cylinder('Central_spindle',(0,0,1.36),.045,2.72)
    for i in range(3):
        a=i*2*pi/3
        before=len(k.PARTS)
        k.box('Rotating_glass_leaf',(.62,0,1.36),(1.14,.012,2.5),'glass',.002)
        for z in (.1,2.62): k.bar('Leaf_horizontal_rail',(.05,0,z),(1.2,0,z),.015)
        k.bar('Leaf_end_stile',(1.2,0,.1),(1.2,0,2.62),.018)
        k.bar('Leaf_push_bar',(.4,-.035,1.1),(1.1,-.035,1.1),.013)
        k.transform(k.since(before),rotation=(0,0,a))
    k.lathe('Top_canopy_fascia',[(0,2.68),(1.3,2.68),(1.3,2.8),(0,2.8)],role='metal',n=128)


@model
def glass_doors():
    # Проём 2,34 × 2,42 м; ширина/высота учитывают правило масштаба E.
    for x in (-1.28,0,1.28): k.box('Structural_stile',(x,0,1.37),(.06,.10,2.75),'metal',.003)
    for z in (.03,2.44,2.72): k.box('Frame_transom',(0,0,z),(2.62,.1,.06),'metal',.003)
    k.box('Transom_glass',(0,0,2.58),(2.5,.014,.2),'glass',.002)
    for side in (-1,1):
        x=side*.64
        for dx in (-.59,.59): k.box('Leaf_stile',(x+dx,-.02,1.23),(.045,.06,2.37),'metal',.002)
        for z in (.065,2.4): k.box('Leaf_rail',(x,-.02,z),(1.17,.06,.045),'metal',.002)
        k.box('Safety_glass',(x,-.02,1.23),(1.1,.014,2.28),'glass',.002)
        hx=side*.16
        k.section('Pull_handle',[(hx,-.05,.9),(hx,-.1,.9),(hx,-.1,1.4),(hx,-.05,1.4)],.012)
        for z in (.32,2.12): k.cylinder('Barrel_hinge',(side*1.235,-.025,z),.014,.09)
        k.box('Door_closer',(side*.95,0,2.36),(.2,.11,.06),'metal',.006)


@model
def canopy_bracket():
    for y in (-.07,.07):
        k.extrude('Triangular_web',[(-1.25,0),(1.25,.92),(-1.25,.92)],'Y',y-.008,y+.008,'metal',.003)
        k.beam('Top_flange',(-1.25,y,.94),(1.25,y,.94),.06,.06)
        k.beam('Sloped_flange',(-1.25,y,.0),(1.25,y,.92),.055,.055)
    k.box('Wall_mounting_plate',(-1.28,0,.48),(.035,.25,1.0),'metal',.005)
    for z in (.12,.45,.8):
        for y in (-.085,.085): k.bolt('Wall_anchor',(-1.305,y,z),'X',.012)
    for x in (-.8,0,.8): k.box('Glazing_mount',(x,0,.98),(.1,.18,.025),'metal',.003)


@model
def curtainwall():
    radius=12
    for z in (.04,1.08,3.06):
        pts=[(radius*sin(-.167+i*.334/48),radius*(1-cos(-.167+i*.334/48)),z) for i in range(49)]
        k.section('Curved_mullion',pts,.036,sides=8)
    for i in range(6):
        a=-.167+i*.334/5
        x=radius*sin(a); y=radius*(1-cos(a))
        k.box('Vertical_facade_mullion',(x,y,1.55),(.055,.09,3.1),'metal',.003)
    for i in range(5):
        a0=-.167+i*.334/5+.003; a1=-.167+(i+1)*.334/5-.003
        for z0,z1 in ((.09,1.03),(1.13,3.0)):
            k.patch('Curved_glazing_panel',lambda u,v:(radius*sin(a0+(a1-a0)*u),radius*(1-cos(a0+(a1-a0)*u)),z0+(z1-z0)*v),16,3,'glass',.012)


@model
def glass_railing():
    k.bar('Continuous_top_rail',(-1.25,0,1.02),(1.25,0,1.02),.025)
    for x in (-1.08,0,1.08):
        k.bar('Stainless_post',(x,0,.035),(x,0,1.02),.02)
        k.foot('Stainless_flange',x,0,.12,.12)
        for z in (.25,.78):
            k.cylinder('Glass_point_fixing',(x,-.025,z),.025,.04,axis='Y')
            k.bolt('Glass_spider_bolt',(x,-.052,z),'Y',.008)
    for x in (-.54,.54): k.box('Safety_glass_panel',(x,-.027,.55),(1.02,.012,.79),'glass',.002)


@model
def damaged_slab():
    # Фрактура задаётся в объёме: торцевая поверхность, рёбра арматуры и обломки.
    outline=[(-2,-1),(2,-1),(1.8,-.52),(1.98,-.1),(1.42,.05),(1.76,.46),(1.2,.62),(.9,.91),(.47,.7),(.12,1.0),(-.35,.82),(-.8,1),(-1.2,.65),(-1.65,.8),(-2,.52)]
    k.extrude('Fractured_reinforced_slab',outline,'Z',0,.28,'concrete',.004)
    for j in range(12):
        x=-1.8+j*.31
        y=.76+.12*sin(j*2.3)
        k.section('Exposed_bent_rebar',[(x,-.2,.18),(x,y,.18),(x+.06,y+.25,.12),(x+.02,y+.4,.23)],.008,'metal',12)
        for t in range(13): k.ring('Rebar_rib',(x,-.1+t*.07,.18),.009,.0015,axis='Y',n=12)
    for j in range(9):
        x=-1.8+j*.42
        k.extrude('Broken_edge_fragment',[(x-.1,.12),(x+.1,.04),(x+.15,.18),(x,.31)],'Y',.45,.7,'concrete',.002)


@model
def sound_fence():
    for x in (-1.46,1.46):
        profile=[(-.09,-.09),(.09,-.09),(.09,-.065),(.015,-.065),(.015,.065),(.09,.065),(.09,.09),(-.09,.09),(-.09,.065),(-.015,.065),(-.015,-.065),(-.09,-.065)]
        k.extrude('I_section_support',profile,'Z',0,3.4,'metal',.002).location.x=x
        k.foot('Steel_support_base',x,0,.28,.28)
    for j in range(23):
        z=.12+j*.12
        prof=[(-1.37,z),(-1.37,z+.1),(1.37,z+.1),(1.37,z)]
        k.extrude('Horizontal_acoustic_board',prof,'Y',-.045,.045,'paint',.006)
        k.bar('Pressed_horizontal_bead',(-1.37,-.052,z+.055),(1.37,-.052,z+.055),.008,'paint',8)
    for x in [-1.28+i*.16 for i in range(17)]: k.box('Upper_slotted_fin',(x,0,3.13),(.07,.08,.4),'paint',.003)
    k.box('Top_protective_rail',(0,0,3.38),(3,.13,.04),'metal',.003)


@model
def site_fence():
    k.panel_frame('Rear_welded_frame',2.4,1.9,.035,.07,'metal',.04)
    prof=[]
    for j in range(25):
        x=-1.22+j*.1
        prof.extend([(x,0),(x+.025,-.035),(x+.07,-.035),(x+.095,0)])
    # Тонкий реальный профлист с рёбрами и закрытыми торцами.
    shape=prof+[(x,y+.002) for x,y in reversed(prof)]
    k.extrude('Corrugated_steel_sheet',shape,'Z',.1,1.92,'paint',.0005)
    for x in (-.95,.95):
        k.beam('Rear_brace',(x,.02,1.35),(x,.52,.07),.035,.035)
        k.box('Concrete_foot',(x,.22,.035),(.35,.65,.07),'concrete',.012)
    for x in (-1,0,1):
        for z in (.17,1.82): k.bolt('Sheet_self_tapper',(x,-.04,z),'Y',.005)


@model
def wave_facade():
    def yy(x): return .42*sin(x*.65)+.13*sin(x*1.9)
    for z0,z1 in ((0,.28),(1.12,1.4)):
        k.patch('Curved_aluminium_fascia',lambda u,v:(-3.5+7*u,yy(-3.5+7*u),z0+(z1-z0)*v),96,4,'metal',.035)
    for z in (.29,1.1): k.section('Rolled_fascia_edge',[(-3.5+7*i/96,yy(-3.5+7*i/96),z) for i in range(97)],.025)
    for i in range(36):
        x=-3.4+i*6.8/35
        k.box('Vertical_vent_louvre',(x,yy(x)+.045,.7),(.075,.15,.78),'interior',.003)
    k.section('Lower_light_channel',[(-3.5+7*i/96,yy(-3.5+7*i/96)-.024,.12) for i in range(97)],.018,'diffuser')


@model
def triangle_panel():
    k.box('Cassette_backing',(0,.1,1.2),(2.4,.08,2.4),'metal',.004)
    step=.4
    for j in range(6):
        for i in range(6):
            x=-1.2+i*step; z=j*step
            for flip in (0,1):
                if flip: a,b,c=(x+.02,z+.02),(x+.38,z+.02),(x+.38,z+.38)
                else: a,b,c=(x+.02,z+.02),(x+.38,z+.38),(x+.02,z+.38)
                apex=((a[0]+b[0]+c[0])/3,-.14-(.025 if (i+j)%2 else 0),(a[1]+b[1]+c[1])/3)
                verts=[(a[0],0,a[1]),(b[0],0,b[1]),(c[0],0,c[1]),apex]
                k.mesh('Folded_triangular_cassette',verts,[(0,1,2),(0,3,1),(1,3,2),(2,3,0)],'metal',.002)


@model
def space_canopy():
    nx,ny=8,4
    for i in range(nx+1):
        for j in range(ny+1):
            p=(-2.6+i*.65,-1.3+j*.65,.5)
            if i<nx: k.bar('Upper_chord_X',p,(p[0]+.65,p[1],.5),.019)
            if j<ny: k.bar('Upper_chord_Y',p,(p[0],p[1]+.65,.5),.019)
            if i<nx and j<ny:
                q=(p[0]+.325,p[1]+.325,.05)
                for dx,dy in ((0,0),(.65,0),(0,.65),(.65,.65)): k.bar('Tetrahedral_web',q,(p[0]+dx,p[1]+dy,.5),.014)
                if i<nx-1: k.bar('Lower_chord_X',q,(q[0]+.65,q[1],.05),.018)
                if j<ny-1: k.bar('Lower_chord_Y',q,(q[0],q[1]+.65,.05),.018)
                for tri in [[(p[0]+.025,p[1]+.025,.54),(p[0]+.625,p[1]+.025,.54),(p[0]+.625,p[1]+.625,.54)],[(p[0]+.025,p[1]+.025,.54),(p[0]+.625,p[1]+.625,.54),(p[0]+.025,p[1]+.625,.54)]]:
                    glass=k.mesh('Triangular_roof_glass',tri,[(0,1,2)],'glass')
                    glass.modifiers.new('Laminated_glass_thickness','SOLIDIFY').thickness=.012


def stairs(name,width,n,run,rise,y0=0,z0=0):
    for i in range(n):
        k.box(name+'_riser',(0,y0+(i+.5)*run,z0+(i+1)*rise/2),(width,run-.003,(i+1)*rise),'stone',.006)
        k.box(name+'_nosing',(0,y0+i*run+.025,z0+(i+1)*rise+.004),(width,.065,.014),'stone',.004)


@model
def entry_steps():
    stairs('Granite_entry',4.6,6,.36,.15)
    k.box('Top_landing',(0,2.44,.45),(4.6,.56,.9),'stone',.007)
    for x in (-2.38,2.38):
        k.extrude('Side_stone_cheek',[(0,0),(2.72,0),(2.72,1.0),(2.1,1.0),(0,.14)],'X',x-.08,x+.08,'stone',.008)
    for x in (-1.1,1.1):
        for i in range(6): k.box('Tread_laying_joint',(x,(i+.5)*.36,(i+1)*.15+.008),(.004,.29,.002),'interior',0)


@model
def breached_wall():
    # 64 независимых скола по контуру и четыре разных сечения сквозь толщину.
    n=65; verts=[]
    def outer(t):
        s=t*9.6
        if s<3.1: return (-1.7,s)
        if s<6.5: return (-1.7+s-3.1,3.1)
        return (1.7,9.6-s)
    def inner(t,layer):
        if t<.22: x,z=-1.04,t/.22*1.6
        elif t>.78: x,z=1.04,(1-t)/.22*1.6
        else:
            a=pi-(t-.22)/.56*pi
            x,z=1.04*cos(a),1.6+1.12*sin(a)
        taper=sin(pi*t)**.2
        x+=(.037*sin(t*197+layer*1.9)+.027*sin(t*83-layer*.7))*taper
        z+=(.032*cos(t*183+layer*2.2))*taper
        return x,z
    for y in (-.15,.15):
        verts.extend((outer(i/(n-1))[0],y,outer(i/(n-1))[1]) for i in range(n))
    for layer,y in enumerate((-.15,-.055,.055,.15)):
        verts.extend((inner(i/(n-1),layer)[0],y,inner(i/(n-1),layer)[1]) for i in range(n))
    faces=[]
    for i in range(n-1):
        faces += [(i,i+1,2*n+i+1,2*n+i),(n+i,5*n+i,5*n+i+1,n+i+1),(i,n+i,n+i+1,i+1)]
        for layer in range(3):
            a=(layer+2)*n+i; b=a+n
            faces += [(a,a+1,b),(a+1,b+1,b)]
    for i in (0,n-1):
        faces.append((i,n+i,5*n+i,4*n+i,3*n+i,2*n+i))
    k.mesh('Fractured_portal_real_volume',verts,faces,'concrete',.001)
    for x in (-.72,-.12,.55):
        k.section('Exposed_header_rebar',[(x,0,3.05),(x+.035,0,2.72),(x-.04,-.06,2.57)],.009,'metal',12)
    for z in (.55,1.15,1.8,2.35):
        for side in (-1,1):
            k.section('Bent_lateral_rebar',[(side*1.35,.035,z),(side*1.0,.035,z+.03),(side*.86,-.05,z-.07)],.008,'metal',12)


@model
def loading_shutter():
    for x in (-1.91,1.91): k.box('Side_guide',(x,0,1.5),(.09,.16,3.0),'metal',.005)
    for j in range(39):
        z=.045+j*.075
        prof=[(-.015,z),(-.03,z+.016),(-.03,z+.058),(-.015,z+.073),(.005,z+.073),(.02,z+.055),(.02,z+.017),(.005,z)]
        k.extrude('Interlocking_shutter_slat',prof,'X',-1.86,1.86,'metal',.002)
    k.box('Top_roll_housing',(0,.025,3.08),(3.9,.28,.24),'paint',.009)
    k.box('Bottom_locking_bar',(0,-.015,.045),(3.7,.065,.075),'metal',.005)
    for x in (-1.1,1.1): k.section('Recessed_pull_handle',[(x-.08,-.05,.13),(x-.08,-.09,.13),(x+.08,-.09,.13),(x+.08,-.05,.13)],.009)
    k.cylinder('Shutter_central_lock',(0,-.055,.055),.015,.015,axis='Y')


@model
def concrete_portal():
    for x in (-1.6,1.6):
        k.extrude('Tapered_column_with_capital',[(x-.22,0),(x+.22,0),(x+.22,2.7),(x+.42,3.12),(x-.42,3.12),(x-.22,2.7)],'Y',-.45,.45,'concrete',.015)
        for z in (.85,1.75,2.6): k.box('Formwork_joint',(x,-.453,z),(.44,.004,.008),'interior',0)
    k.extrude('Haunched_concrete_beam',[(-2,3.1),(-1.3,3.1),(-.9,3.24),(.9,3.24),(1.3,3.1),(2,3.1),(2,3.5),(-2,3.5)],'Y',-.5,.5,'concrete',.009)
    for x in (-1.6,1.6):
        for y in (-.46,.46):
            for z in (.45,1.35,2.25): k.cylinder('Formwork_tie_recess',(x,y,z),.018,.004,'interior','Y',24)


@model
def terrace_stairs():
    stairs('Lower_flight',3.0,8,.3,.15)
    k.box('Intermediate_terrace',(0,2.8,.6),(4.2,.8,1.2),'stone',.009)
    before=len(k.PARTS)
    stairs('Offset_upper_flight',2.5,8,.3,.15,y0=3.2,z0=1.2)
    for ob in k.since(before): ob.location.x=-.6
    for x in (-1.53,1.53):
        k.section('Lower_handrail',[(x,-.1,1.0),(x,.25,1.0),(x,2.4,2.2),(x,3.15,2.2)],.022)
        for y in (.2,1.25,2.3):
            z=min(1.2,max(.15,(math.floor(y/.3)+1)*.15))
            k.bar('Lower_stanchion',(x,y,z),(x,y,z+1.0),.017)
    for x in (-1.89,.69):
        k.bar('Upper_handrail',(x,3.22,2.2),(x,5.6,3.4),.022)
        for y in (3.35,4.45,5.5):
            z=1.2+min(1.2,(math.floor((y-3.2)/.3)+1)*.15)
            k.bar('Upper_stanchion',(x,y,z),(x,y,z+.95),.017)


@model
def relief_wall():
    k.box('Wall_backing',(0,.08,1.55),(3,.12,3.1),'stone',.003)
    widths=[.9,1.2,.87]
    for row in range(5):
        x=-1.48
        order=widths[row%3:]+widths[:row%3]
        for col,w in enumerate(order):
            depth=.07+((row+col*2)%4)*.035
            k.box('Offset_stone_rectangle',(x+w/2,-depth/2,row*.62+.31),(w-.018,depth,.602),'stone',.005)
            x+=w
