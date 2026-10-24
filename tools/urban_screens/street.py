"""Самостоятельные уличные конструкции. Каждый id имеет отдельный рецепт формы."""
import math
from math import pi,sin,cos
import meshkit as k

REGISTRY={}
def model(fn):
    REGISTRY[fn.__name__]=fn
    return fn


@model
def jersey():
    profile=[(-.31,0),(.31,0),(.31,.12),(.17,.42),(.12,.82),(.09,.85),(-.09,.85),(-.12,.82),(-.17,.42),(-.31,.12)]
    k.extrude('Cast_body_double_slope',profile,'X',-1,1,'concrete',.014)
    for x in (-.62,.62):
        k.section('Lifting_eye',[(x-.055,0,.83),(x-.055,0,.91),(x-.035,0,.94),(x+.035,0,.94),(x+.055,0,.91),(x+.055,0,.83)],.009,'metal')
    for x in (-.97,.97):
        for y in (-.19,.19):
            k.box('Mould_end_recess',(x,y,.2),(.012,.06,.1),'interior',.004)


@model
def crowd():
    k.section('Continuous_bent_outer_tube',k.rounded_path_xz(2.3,1.02,0,.1,.14),.02)
    k.bar('Lower_rail',(-1.14,0,.22),(1.14,0,.22),.016)
    for i in range(17):
        x=-1.04+i*.13
        k.bar('Welded_vertical_picket',(x,0,.23),(x,0,1.1),.008)
    for x in (-.8,.8):
        k.bar('Removable_T_foot',(x,-.32,.035),(x,.32,.035),.023)
        k.bar('Foot_socket',(x,0,.035),(x,0,.18),.025)
        for y in (-.29,.29): k.box('Rubber_foot_end',(x,y,.026),(.065,.08,.05),'rubber',.012)
    for x in (-1.19,1.19):
        for z in (.4,.85):
            k.section('Interlock_hook',[(x,0,z),(x+.06,0,z),(x+.06,0,z-.05)],.009)


@model
def crate():
    for i in range(6):
        x=-.51+i*.204
        for z in (.035,.81): k.box('Lid_floor_plank',(x,0,z),(.197,.8,.045),'wood',.003)
    for z in (.14,.31,.48,.65):
        for y in (-.39,.39): k.box('Side_board',(0,y,z),(1.2,.035,.158),'wood',.002)
        for x in (-.58,.58): k.box('End_board',(x,0,z),(.035,.745,.158),'wood',.002)
    for y in (-.425,.425):
        for x in (-.49,.49):
            k.box('Vertical_binding',(x,y,.43),(.09,.045,.86),'wood',.004)
            for z in (.12,.3,.48,.68,.81): k.cylinder('Nail_head',(x,y+math.copysign(.025,y),z),.0045,.004,'metal','Y',12)
    for x in (-.52,.52): k.box('Floor_runner',(x,0,.025),(.12,.76,.05),'wood',.004)
    k.lettering('Fictional_crate_code','RING / 014',(0,-.451,.43),.09)


@model
def cone():
    n=64
    outer=[]
    for i in range(n):
        a=2*pi*i/n
        scale=.21/max(abs(cos(a)),abs(sin(a)))
        outer.append((scale*cos(a),scale*sin(a)))
    verts=[]
    for z in (.005,.05):
        for ring in (outer,[(.15*cos(2*pi*i/n),.15*sin(2*pi*i/n)) for i in range(n)]):
            verts.extend((x,y,z) for x,y in ring)
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                  (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
    k.mesh('Hollow_square_rubber_base',verts,faces,'rubber',.008)
    k.lathe('Hollow_PVC_shell',[(.17,.05),(.172,.075),(.043,.71),(.038,.75),(.025,.75),(.03,.71),(.155,.075),(.15,.05),(.17,.05)],role='plastic')
    for z0,z1 in ((.25,.34),(.48,.57)):
        r0=.172-(z0-.075)*.203
        r1=.172-(z1-.075)*.203
        k.lathe('Reflective_sleeve',[(r0+.001,z0),(r1+.001,z1),(r1+.002,z1),(r0+.002,z0),(r0+.001,z0)],role='reflector')


def wire_grid(name,w,h,y,z,spacing=.12,r=.0035):
    for i in range(round(w/spacing)+1):
        x=-w/2+w*i/round(w/spacing)
        k.bar(name+'_vertical',(x,y,z),(x,y,z+h),r,sides=8)
    for i in range(round(h/spacing)+1):
        zz=z+h*i/round(h/spacing)
        k.bar(name+'_horizontal',(-w/2,y,zz),(w/2,y,zz),r,sides=8)


@model
def mesh_barrier():
    k.panel_frame('Welded_RHS_frame',2,1.55,0,.24,'paint',.045)
    wire_grid('Square_wire_mesh',1.91,1.45,0,.29,.09,.004)
    for x in (-.89,.89):
        k.box('Splayed_foot',(x,0,.035),(.16,.78,.07),'paint',.008)
        k.beam('Rear_brace',(x,0,1.05),(x,.35,.07),.035,.035,'paint')
        for y in (-.29,.29): k.bolt('Foot_bolt',(x,y,.08))


@model
def planter():
    for y in (-.36,.36): k.box('Stone_side_wall',(0,y,.32),(3,.08,.58),'stone',.007)
    for x in (-1.46,1.46): k.box('Stone_end_wall',(x,0,.32),(.08,.65,.58),'stone',.007)
    k.box('Inner_bottom',(0,0,.07),(2.85,.65,.1),'stone',.006)
    for y in (-.36,.36): k.box('Top_coping',(0,y,.625),(3.04,.105,.05),'stone',.004)
    for x in (-1.46,1.46): k.box('Top_end_coping',(x,0,.625),(.105,.65,.05),'stone',.004)
    k.box('Recessed_soil',(0,0,.5),(2.81,.61,.03),'soil',.01)
    for x in (-.9,.9):
        k.box('Hidden_plinth',(x,0,.025),(.4,.55,.05),'stone',.005)
        for y in (-.402,.402): k.cylinder('Drain_insert',(x,y,.11),.015,.006,'interior','Y')


@model
def bench_tube():
    for x in (-.66,.66):
        k.section('Bent_side_frame',[(x,-.29,.035),(x,-.29,.32),(x,-.22,.43),(x,.2,.43),(x,.26,.5),(x,.27,.81)],.026)
        k.bar('Rear_leg',(x,.22,.04),(x,.22,.44),.026)
        for y in (-.29,.22): k.foot('Floor_flange',x,y,.10,.11)
    for i in range(5): k.box('Seat_timber_slat',(0,-.22+i*.1,.47),(1.8,.088,.036),'wood',.006)
    for i in range(3): k.box('Back_timber_slat',(0,.27,.57+i*.105),(1.8,.032,.09),'wood',.006)
    for x in (-.66,.66):
        for y in (-.22,-.02,.18): k.bolt('Seat_fastener',(x,y,.493),r=.006)


@model
def bollard():
    k.lathe('Profiled_post',[(0,0),(.095,0),(.095,.025),(.077,.045),(.052,.075),(.052,.84),(.065,.85),(.065,.88),(.05,.91),(.03,.94),(0,.95)],role='paint')
    k.lathe('Reflective_neck_band',[(.052,.72),(.054,.72),(.054,.77),(.052,.77),(.052,.72)],role='reflector')
    for a in (0,pi/2,pi,3*pi/2): k.bolt('Base_anchor',(.072*cos(a),.072*sin(a),.03),r=.005)


@model
def bin_faceted():
    k.lathe('Faceted_bin_shell',[(.16,.05),(.22,.08),(.22,.66),(.18,.71),(.18,.87),(.2,.9),(.17,.9),(.15,.86),(.15,.72),(.19,.65),(.19,.1),(.16,.08),(.16,.05)],role='paint',n=8)
    k.cylinder('Inner_liner_floor',(0,0,.11),.185,.02,'interior',n=8)
    k.box('Service_door',(0,-.207,.38),(.27,.025,.42),'paint',.009)
    k.cylinder('Door_lock',(.09,-.225,.47),.012,.009,'metal','Y')
    for z in (.23,.53): k.cylinder('Door_hinge',(-.15,-.205,z),.009,.065)
    k.cylinder('Recessed_plinth',(0,0,.025),.165,.05,'rubber',n=8)


@model
def lightbox():
    outline=[(x,z+1.1) for x,z in k.rounded_rect(1.16,1.95,.08)]
    k.extrude('Rounded_aluminium_case',outline,'Y',-.13,.13,'metal',.004)
    for y in (-.136,.136):
        k.box('Recessed_ad_panel',(0,y,1.16),(1.04,.012,1.72),'diffuser',.025)
        for x in (-.49,.49): k.box('Panel_pressure_strip',(x,y+math.copysign(.009,y),1.16),(.012,.009,1.71),'metal',.001)
    for x in (-.35,.35):
        k.box('Mounting_leg',(x,0,.12),(.08,.16,.24),'metal',.004)
        k.foot('Leg_anchor',x,0,.22,.26)
    k.box('Lower_service_cover',(0,-.135,.23),(.8,.012,.12),'metal',.004)
    for x in (-.35,.35): k.bolt('Cover_screw',(x,-.146,.23),'Y',.005)


@model
def sandbags():
    for row in range(3):
        count=4 if row<2 else 3
        for i in range(count):
            x=(i-(count-1)/2)*.46+(.045 if row%2 else 0)
            y=.025*sin(i*1.7+row)
            z=.12+row*.225
            k.soft('Seamed_filled_sack',(x,y,z),(.53,.6,.26),'fabric',.6,i+row*4)
            pts=[(x+.24*cos(t),y+.282*sin(t),z+.018*sin(5*t+i)) for t in [2*pi*j/64 for j in range(65)]]
            k.section('Sack_stitching_ridge',pts,.0025,'fabric',8)


def sign_plate(name,shape,z,y=0):
    prof=[(x,zz+z) for x,zz in shape]
    k.extrude(name,prof,'Y',y-.015,y+.015,'enamel',.003)
    for zz in (z-.16,z+.16):
        k.box('Rear_clamp',(0,y+.04,zz),(.2,.035,.035),'metal',.003)
        for x in (-.065,.065): k.bolt('Clamp_bolt',(x,y+.065,zz),'Y',.005)


def sign_post(height=2.7):
    k.cylinder('Galvanized_post',(0,.06,height/2),.03,height)
    k.lathe('Weighted_concrete_foot',[(0,0),(.13,0),(.13,.06),(.09,.15),(.065,.19),(0,.19)],(0,.06,0),role='concrete')


@model
def parking_sign():
    sign_post()
    sign_plate('Folded_parking_sign',k.rounded_rect(.5,.5,.025),2.4)
    k.lettering('Parking_letter','P',(0,-.019,2.22),.4,role='reflector')


@model
def handrail_slope():
    for x,z in [(-1.3,.15),(0,.4),(1.3,.65)]:
        k.bar('Stanchion',(x,0,z),(x,0,z+.86),.022)
        k.box('Sloped_floor_flange',(x,0,z),(.13,.13,.02),'metal',.006)
        for dx in (-.04,.04): k.bolt('Flange_bolt',(x+dx,0,z+.016),r=.006)
    k.section('Continuous_sloped_handrail',[(-1.42,0,1.01),(-1.3,0,1.01),(1.3,0,1.51),(1.42,0,1.51)],.025)
    k.bar('Lower_sloped_rail',(-1.3,0,.55),(1.3,0,1.05),.012)


def cabinet_shell(name,w,d,h,z0=.08,role='paint'):
    # Стенки, отбортованная крышка и отдельная дверь сохраняют реальные зазоры.
    for x in (-w/2+.015,w/2-.015): k.box(name+'_side',(x,0,z0+h/2),(.03,d,h),role,.004)
    k.box(name+'_back',(0,d/2-.015,z0+h/2),(w,.03,h),role,.004)
    for z in (z0,z0+h): k.box(name+'_cap',(0,0,z),(w+.015,d+.015,.035),role,.004)
    k.box(name+'_door',(0,-d/2-.003,z0+h/2),(w-.07,.03,h-.07),role,.007)
    k.cylinder(name+'_lock',(w*.32,-d/2-.024,z0+h*.65),.014,.012,'metal','Y')
    for z in (z0+.18,z0+h-.18): k.cylinder(name+'_hinge',(-w/2+.04,-d/2-.019,z),.01,.08)


@model
def street_cabinet():
    cabinet_shell('Weatherproof_cabinet',.85,.4,1.4,.12)
    k.box('Concrete_plinth',(0,0,.06),(.86,.43,.12),'concrete',.009)
    k.box('Rain_canopy',(0,-.015,1.545),(.9,.46,.045),'paint',.008)
    for z in (.32,.36,.4): k.box('Door_vent_gap',(0,-.226,z),(.48,.007,.014),'interior',.002)
    k.box('Identification_plate',(.14,-.226,1.28),(.22,.006,.09),'metal',.004)


@model
def warning_a():
    for side in (-1,1):
        before=len(k.PARTS)
        k.box('Plywood_warning_leaf',(0,0,.58),(.72,.035,1.12),'wood',.01)
        for x in (-.325,.325): k.box('Side_binding',(x,-.023,.58),(.035,.025,1.1),'metal',.003)
        k.box('Blank_warning_face',(0,-.023,.63),(.58,.008,.79),'reflector',.012)
        k.transform(k.since(before),(0,side*.19,0),(side*math.radians(18),0,0))
    k.cylinder('Upper_pivot',(0,0,1.13),.025,.78,axis='X')
    for x in (-.28,.28):
        for j in range(12): k.ring('Limit_chain_link',(x,-.24+j*.043,.38-.035*sin(pi*j/11)),.014,.002,axis='X' if j%2 else 'Z',n=16)


@model
def basket_bin():
    for z in (.06,.13,.7,.76): k.ring('Rolled_bin_ring',(0,0,z),.21,.013)
    for j in range(32):
        a=2*pi*j/32
        ob=k.box('Vertical_bin_slat',(.208*cos(a),.208*sin(a),.42),(.028,.008,.62),'metal',.002)
        ob.rotation_euler.z=a+pi/2
    k.lathe('Inner_bucket',[(.18,.1),(.185,.12),(.185,.72),(.175,.72),(.175,.13),(.18,.1)],role='interior')
    k.cylinder('Bucket_floor',(0,0,.12),.176,.015,'interior')
    for a in (0,2*pi/3,4*pi/3): k.bar('Raised_leg',(.16*cos(a),.16*sin(a),0),(.16*cos(a),.16*sin(a),.12),.016)


@model
def tactile():
    k.box('Mineral_tile_base',(0,0,.013),(.6,.6,.026),'stone',.003)
    for x in (-.22,-.11,0,.11,.22):
        prof=[(xx+x,zz+.026) for xx,zz in [(-.025,0),(-.022,.017),(-.015,.027),(.015,.027),(.022,.017),(.025,0)]]
        k.extrude('Rounded_directional_rib',prof,'Y',-.28,.28,'stone',.004)


@model
def speed_bump():
    prof=[(-.25,0)]+[(t,.055*(1-(t/.25)**2)) for t in [-.25+i*.5/32 for i in range(1,33)]]
    k.extrude('Rubber_convex_section',prof,'X',-.5,.5,'rubber',.001)
    for x in (-.39,.39):
        for y in (-.10,.1):
            k.cylinder('Bolt_recess',(x,y,.045),.019,.008,'interior',n=32)
            k.bolt('Countersunk_anchor',(x,y,.047),r=.009)
    for x in (-.2,.2): k.box('Reflective_insert',(x,0,.056),(.18,.18,.004),'reflector',.01)


@model
def crossing_sign():
    sign_post(2.8)
    sign_plate('Thick_protective_border',k.rounded_rect(.8,.8,.07),2.38)
    k.box('Inner_blue_plate',(0,-.024,2.38),(.64,.018,.64),'enamel',.02)
    k.extrude('White_warning_triangle',[(-.27,2.11),(.27,2.11),(0,2.65)],'Y',-.04,-.035,'reflector',.002)
    for x in (-.16,-.08,0,.08,.16): k.box('Crossing_zebra_symbol',(x,-.045,2.19),(.047,.009,.025),'interior',.001)
    k.cylinder('Pedestrian_head',(.02,-.05,2.49),.029,.012,'interior','Y',24)
    for a,b in [((.01,-.05,2.45),(-.02,-.05,2.35)),((-.02,-.05,2.35),(-.09,-.05,2.26)),((-.02,-.05,2.35),(.08,-.05,2.26)),((0,-.05,2.42),(.1,-.05,2.37)),((0,-.05,2.42),(-.09,-.05,2.37))]: k.bar('Pedestrian_symbol',a,b,.012,'interior',12)


@model
def guardrail():
    # W-сечение проката, а не плоская доска; осознанная деформация по длине.
    prof=[(-.07,.0),(-.04,.04),(.03,.075),(.04,.12),(0,.16),(-.04,.2),(-.03,.245),(.04,.28),(.07,.32)]
    verts=[]
    for j in range(49):
        x=-1.7+j*3.4/48
        dent=.18*math.exp(-((x-.35)/.45)**2)
        for offset in (0,.004):
            verts.extend((x,y+dent+offset,z+.42) for y,z in prof)
    n=len(prof); faces=[]
    for j in range(48):
        for layer in range(2):
            for p in range(n-1):
                a=j*2*n+layer*n+p; b=a+2*n
                faces.append((a,a+1,b+1,b))
        for p in (0,n-1):
            a=j*2*n+p; faces.append((a,a+2*n,a+3*n,a+n))
    for j in (0,48):
        for p in range(n-1):
            a=j*2*n+p; faces.append((a,a+1,a+n+1,a+n))
    k.mesh('Dented_W_beam_shell',verts,faces,'metal',.001)
    for x in (-1.3,0,1.3):
        k.extrude('C_section_stanchion',[(-.05,0),(.05,0),(.05,.018),(-.032,.018),(-.032,.1),(.05,.1),(.05,.118),(-.05,.118)],'Z',0,.7,'metal',.002).location=(x,.14,0)
        for z in (.5,.68): k.bolt('Rail_fixing',(x,.13,z),'Y')


@model
def curb_corner():
    for j in range(8):
        a0=j*pi/16; a1=(j+1)*pi/16-.006
        points=[(r*cos(a),r*sin(a),z) for z in (0,.24) for r in (1.78,2.0) for a in (a0,a1)]
        k.mesh('Radius_cast_curb_segment',points,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],'concrete',.009)


@model
def drain():
    for x in (-.29,.29): k.box('Cast_outer_side',(x,0,.065),(.025,.4,.12),'metal',.003)
    for y in (-.19,.19): k.box('Cast_outer_end',(0,y,.065),(.56,.025,.12),'metal',.003)
    for x in [-.25+i*.05 for i in range(11)]: k.box('Open_grate_rib',(x,0,.11),(.022,.35,.025),'metal',.004)
    for y in (-.09,.09): k.box('Underside_cross_rib',(0,y,.08),(.56,.018,.04),'metal',.003)


@model
def ticket_machine():
    outline=[(-.2,.08),(.2,.08),(.2,1.18),(.16,1.25),(-.19,1.17)]
    k.extrude('Folded_terminal_body',outline,'Y',-.16,.16,'paint',.012)
    k.box('Reader_panel',(0,-.17,.93),(.33,.025,.4),'interior',.018)
    k.box('LCD_display',(0,-.188,1.02),(.24,.012,.105),'screen',.006)
    k.box('Ticket_output_recess',(0,-.19,.81),(.19,.02,.03),'interior',.004)
    k.box('Ticket_output_lip',(0,-.21,.788),(.2,.05,.012),'metal',.002)
    k.cylinder('Request_button',(.09,-.196,.89),.025,.015,'plastic','Y')
    k.box('Service_access',(0,.17,.55),(.32,.022,.72),'paint',.006)
    k.foot('Terminal_flange',0,0,.45,.35)
    k.box('Rain_visor',(0,-.07,1.25),(.45,.32,.03),'paint',.01)


@model
def barrier_arm():
    cabinet_shell('Barrier_drive',.38,.4,.95,.06)
    k.foot('Drive_flange',0,0,.46,.48)
    k.cylinder('Output_shaft',(.23,0,.88),.065,.16,axis='X')
    k.box('Arm_clamp',(.33,0,.88),(.3,.16,.18),'metal',.01)
    k.extrude('Hollow_boom_outer',[(-.035,-.055),(.035,-.055),(.035,.055),(-.035,.055)],'X',.3,3.78,'paint',.005).location.z=.88
    for x in (.65,1.45,2.25,3.05): k.box('Boom_reflective_band',(x,-.038,.88),(.35,.005,.09),'reflector',.002)
    k.box('End_rubber_cap',(3.8,0,.88),(.04,.085,.13),'rubber',.007)
    for y in (-.07,.07): k.bolt('Clamp_fixing',(.36,y,.99),r=.012)


@model
def guide_board():
    sign_post(2.5)
    sign_plate('Rectangular_direction_board',k.rounded_rect(.38,1.5,.02),1.0,-.01)
    for i in range(4):
        zz=.4+i*.31
        k.extrude('Diagonal_reflector',[(-.18,zz),(.18,zz+.18),(.18,zz+.29),(-.18,zz+.11)],'Y',-.031,-.027,'reflector',.001)
    shape=[(.24*cos(2*pi*i/64),.24*sin(2*pi*i/64)) for i in range(64)]
    sign_plate('Round_direction_sign',shape,2.14)
    k.extrude('Arrow_symbol',[(-.12,2.25),(.06,2.07),(-.01,2.07),(-.01,2.0),(.16,2.0),(.16,2.17),(.09,2.17),(.09,2.1),(-.08,2.28)],'Y',-.026,-.021,'reflector',.001)


def tyre(name,loc,r=.31,width=.16,axis='Z'):
    k.lathe(name,[(r*.63,-width/2),(r*.88,-width/2),(r*.97,-width*.32),(r,width*.05),(r*.97,width*.32),(r*.88,width/2),(r*.63,width/2),(r*.60,width*.33),(r*.60,-width*.33),(r*.63,-width/2)],loc,axis,'rubber',64)
    for j in range(48):
        a=2*pi*j/48
        pts=[]
        for q in (-1,0,1):
            z=q*width*.3; ang=a+q*.025
            p=(r*1.002*cos(ang),r*1.002*sin(ang),z)
            if axis=='X': p=(p[2],p[0],p[1])
            if axis=='Y': p=(p[0],p[2],p[1])
            pts.append(tuple(p[k0]+loc[k0] for k0 in range(3)))
        k.section(name+'_tread',pts,.0035,'rubber',6)


@model
def tire_delineator():
    tyre('Hollow_tyre_weight',(0,0,.09),.31,.18)
    k.box('Steel_inner_cross',(0,0,.05),(.48,.08,.035),'metal',.003)
    k.box('Delineator_foot',(0,0,.18),(.24,.18,.06),'plastic',.015)
    k.extrude('Delineator_shell',[(-.09,.18),(.09,.18),(.075,.94),(.055,.99),(-.055,.99),(-.075,.94)],'Y',-.025,.025,'plastic',.014)
    for z in (.35,.62): k.extrude('Reflective_diagonal',[(-.078,z),(.078,z+.13),(.078,z+.23),(-.078,z+.1)],'Y',-.029,-.026,'reflector',.001)


@model
def lane_island():
    outline=k.rounded_rect(4.8,1,.48,16)
    k.extrude('Raised_rounded_concrete_island',outline,'Z',0,.18,'concrete',.015)
    for x in (-1.3,1.3):
        k.ring('Cable_conduit_rim',(x,0,.186),.035,.004,'metal')
        k.cylinder('Cable_conduit_shadow',(x,0,.181),.03,.003,'interior')
    for side in (-1,1):
        for x in [-1.6+i*.4 for i in range(9)]:
            k.box('Kerb_reflector',(x,side*.502,.11),(.16,.004,.07),'reflector',.003)
