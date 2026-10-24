"""Крупные дорожные, технические и транспортные предметы по кадрам."""
import math
from math import pi,sin,cos
import meshkit as k
import bpy
from street import wire_grid,cabinet_shell,tyre
REGISTRY={}
def model(fn): REGISTRY[fn.__name__]=fn; return fn


@model
def hedgehog():
    profile=[(-.09,-.09),(.09,-.09),(.09,-.065),(.015,-.065),(.015,.065),(.09,.065),(.09,.09),(-.09,.09),(-.09,.065),(-.015,.065),(-.015,-.065),(-.09,-.065)]
    for angles in ((0,pi/4,0),(0,-pi/4,0),(pi/2,0,0)):
        before=len(k.PARTS)
        k.extrude('Rolled_I_beam',profile,'Z',-.95,.95,'metal',.002)
        k.transform(k.since(before),(0,0,.73),angles)
    for y in (-.105,.105):
        k.box('Central_gusset',(0,y,.73),(.36,.016,.3),'metal',.006)
        for x in (-.12,.12): k.bolt('Central_connection',(x,y,.73),'Y',.014)


@model
def concrete_cube():
    # Нерегулярные торцевые профили позволяют отличить скол от текстурного пятна.
    shape=[(-.6,0),(.6,0),(.6,.42),(.55,.48),(.57,.65),(.45,.8),(-.45,.8),(-.6,.61)]
    k.extrude('Chamfered_roadblock',shape,'Y',-.425,.425,'concrete',.009)
    for x in (-.32,.32):
        k.section('Recessed_lifting_loop',[(x-.045,0,.78),(x-.045,0,.86),(x+.045,0,.86),(x+.045,0,.78)],.009)
    for y in (-.42,.42):
        for x in (-.35,.35): k.cylinder('Formwork_tie_mark',(x,y,.4),.023,.005,'interior','Y',24)


@model
def logo_pylon():
    k.box('Stone_monument_base',(0,0,.09),(1.0,.42,.18),'stone',.01)
    k.extrude('Splayed_stone_pylon',[(-.44,.18),(.44,.18),(.38,2.8),(-.38,2.8)],'Y',-.16,.16,'stone',.012)
    k.box('Recessed_wayfinding_face',(0,-.17,1.53),(.64,.018,2.25),'paint',.007)
    for z in (1.89,2.15):
        k.extrude('Original_abstract_symbol',[(-.15,z),(.0,z+.18),(.15,z),(0,z-.18)],'Y',-.19,-.175,'metal',.002)
    k.lettering('Original_city_name','РИНГ',(0,-.197,.82),.18)


@model
def plaza_seat():
    for x in (-.95,.95): k.box('Seat_stone_pier',(x,0,.21),(.3,.6,.42),'stone',.006)
    k.box('Hollow_seat_front',(0,-.29,.25),(2.15,.1,.45),'stone',.006)
    k.box('Hollow_seat_back',(0,.29,.25),(2.15,.1,.45),'stone',.006)
    for i in range(3): k.box('Polished_coping_slab',(-.733+i*.733,0,.51),(.725,.7,.08),'stone',.005)
    k.box('Recessed_plinth',(0,0,.035),(1.95,.49,.07),'interior',.004)


@model
def tram_track():
    for row in range(6):
        for x in (-.73,0,.73): k.box('Concrete_track_paving',(x,-2.5+row,.07),(.72,.988,.14),'concrete',.004)
    # Головка и желобчатая губа — самостоятельное непрерывное сечение.
    section=[(-.07,0),(.07,0),(.07,.02),(.025,.02),(.025,.105),(.052,.12),(.052,.16),(.005,.17),(-.005,.17),(-.005,.125),(-.028,.125),(-.028,.165),(-.055,.165),(-.055,.12),(-.025,.105),(-.025,.02),(-.07,.02)]
    for x in (-.76,.76):
        before=len(k.PARTS)
        k.extrude('Grooved_tram_rail',section,'Y',-3,3,'metal',.0015)
        k.transform(k.since(before),(x,0,.015))
        for y in (-2.65,-1.4,-.15,1.1,2.35):
            k.box('Rail_bearing_pad',(x,y,.025),(.22,.18,.025),'rubber',.004)
            for dx in (-.1,.1): k.bolt('Rail_fastener',(x+dx,y,.05),r=.009)


def lamp_head(name,loc,length=.65):
    x,y,z=loc
    prof=[(-length/2,0),(length/2-.07,0),(length/2,.035),(length/2-.04,.09),(-length/2+.06,.12),(-length/2,.07)]
    ob=k.extrude(name+'_diecast_body',prof,'X',-.12,.12,'metal',.006)
    ob.location=(x,y,z)
    k.box(name+'_opal_lens',(x,y-.02,z-.006),(.18,length-.12,.015),'diffuser',.02)
    for i in range(6): k.box(name+'_cooling_fin',(x,y-.2+i*.07,z+.11),(.22,.013,.025),'metal',.002)


def lamp_pole(height):
    k.lathe('Tapered_lighting_column',[(0,0),(.12,0),(.12,.08),(.085,.14),(.055,1),(.04,height),(0,height)],role='paint')
    k.box('Column_service_hatch',(0,-.064,.53),(.07,.012,.24),'paint',.01)
    k.bolt('Hatch_lock',(0,-.073,.59),'Y',.005)
    for a in (0,pi/2,pi,3*pi/2): k.bolt('Base_anchor',(.088*cos(a),.088*sin(a),.09),r=.01)


@model
def twin_light():
    lamp_pole(6.55)
    for side in (-1,1):
        pts=[(side*(.04+1.7*sin(pi/2*t)),0,6.15+.75*(1-cos(pi/2*t))) for t in [i/24 for i in range(25)]]
        k.section('Bent_lamp_arm',pts,.028)
        before=len(k.PARTS)
        lamp_head('Twin_street_lamp',(0,0,0),.65)
        k.transform(k.since(before),(side*1.7,0,6.91),(0,0,side*pi/2))


@model
def wayfinding():
    k.extrude('Thin_wayfinding_monolith',[(x,z+1.24) for x,z in k.rounded_rect(.6,2.42,.025)],'Y',-.09,.09,'paint',.003)
    k.box('Flush_front_panel',(0,-.095,1.4),(.52,.012,1.93),'paint',.005)
    k.box('Heavy_base',(0,0,.045),(.64,.26,.09),'metal',.008)
    k.lettering('District_number','4',(0,-.105,1.9),.4)
    k.lettering('District_name','СЕКТОР',(0,-.105,1.65),.075)
    for i in range(6): k.box('Direction_line',(0,-.105,1.35-i*.17),(.35,.004,.008),'reflector',0)


@model
def bench_stone():
    for x in (-.76,.76):
        prof=[(-.28,0),(.28,0),(.21,.38),(.24,.43),(-.24,.43),(-.21,.38)]
        k.extrude('Sculpted_cast_stone_leg',prof,'X',x-.12,x+.12,'concrete',.01)
        k.box('Underseat_steel_strip',(x,0,.43),(.06,.5,.015),'metal',.003)
    for i in range(5):
        y=-.22+i*.11
        k.box('Bench_timber_slat',(0,y,.46),(2.0,.095,.04),'wood',.006)
        for x in (-.76,.76): k.bolt('Countersunk_slat_fixing',(x,y,.483),r=.006)


@model
def billboard():
    k.box('Billboard_box',(0,0,2.6),(3,.22,1.8),'metal',.015)
    k.box('Blank_front_print_panel',(0,-.118,2.6),(2.86,.008,1.65),'reflector',.004)
    for x in (-1,1):
        k.beam('Billboard_support',(x,.02,0),(x,.02,2.7),.10,.10)
        k.foot('Billboard_foundation',x,.02,.3,.3)
        k.beam('Rear_sign_brace',(x,.1,1.5),(x,.5,3.3),.04,.04)
    for z in (1.95,3.2): k.box('Back_stiffener',(0,.14,z),(2.9,.06,.06),'metal',.003)


@model
def dump_bed():
    k.box('Heavy_steel_floor',(0,0,.16),(2.4,4.4,.12),'metal',.008)
    for x in (-1.2,1.2):
        k.extrude('Pressed_dump_side',[(-2.2,.2),(2.2,.2),(2.2,1.6),(-1.9,1.6),(-2.2,1.18)],'X',x-.035,x+.035,'paint',.008)
        for y in (-1.75,-.9,-.05,.8,1.65):
            lo,hi=sorted((x+math.copysign(.037,x),x+math.copysign(.13,x)))
            k.extrude('External_tapered_rib',[(y-.055,.22),(y+.055,.22),(y+.12,1.56),(y-.12,1.56)],'X',lo,hi,'paint',.004)
    k.extrude('Sloping_front_board',[(-2.2,.2),(-1.88,1.6),(-1.8,1.6),(-2.12,.2)],'X',-1.2,1.2,'paint',.005)
    k.box('Tailgate',(0,2.18,.9),(2.4,.07,1.4),'paint',.009)
    for x in (-.9,0,.9): k.box('Tailgate_rib',(x,2.24,.93),(.09,.08,1.2),'paint',.004)
    for x in (-.9,.9):
        k.cylinder('Tailgate_hinge',(x,2.25,1.54),.045,.22,axis='X')
        k.box('Chassis_runner',(x,0,.06),(.14,4,.12),'metal',.006)


@model
def privacy_screen():
    k.section('Bent_screen_frame',k.rounded_path_xz(1.75,1.72,0,.12,.08),.019)
    k.bar('Bottom_screen_rail',(-.85,0,.23),(.85,0,.23),.016)
    k.patch('Sagging_tarpaulin',lambda u,v:((- .81+1.62*u),.035*sin(pi*u)*sin(4*pi*v)+.012*sin(13*pi*u),.28+1.49*v-.04*sin(pi*u)),40,30,'fabric',.002)
    for x in (-.72,.72): k.bar('Cross_foot',(x,-.35,.035),(x,.35,.035),.023)
    for x in [-.75+i*.15 for i in range(11)]:
        for z in (.3,1.72): k.ring('Lacing_grommet',(x,-.01,z),.008,.002,axis='Y',n=16)


@model
def water_barrier():
    shape=[(-.24,0),(.24,0),(.24,.15),(.14,.35),(.13,.75),(.09,.8),(-.09,.8),(-.13,.75),(-.14,.35),(-.24,.15)]
    k.extrude('Moulded_water_barrier_shell',shape,'X',-.72,.72,'plastic',.02)
    for x in (-.45,0,.45):
        for side in (-1,1): k.extrude('Moulded_stiffening_rib',[(side*.145,.25),(side*.163,.25),(side*.15,.71),(side*.133,.71)],'X',x-.025,x+.025,'plastic',.007)
    for x,sgn in ((-.75,-1),(.75,1)):
        k.box('Moulded_end_interlock',(x,0,.4),(.1,.11,.35),'plastic',.012)
        k.cylinder('Interlock_pin_boss',(x,0,.61),.05,.06,'plastic')
    k.cylinder('Filler_cap',(.4,0,.813),.06,.025,'plastic')
    for j in range(16):
        a=j*pi/8
        k.bar('Cap_grip',(.4+.058*cos(a),.058*sin(a),.808),(.4+.058*cos(a),.058*sin(a),.83),.003,'plastic',6)


@model
def checkpoint_cabinet():
    cabinet_shell('Checkpoint_power_unit',.65,.42,1.12,.12)
    for x in (-.23,.23): k.beam('Raised_unit_leg',(x,0,0),(x,0,.2),.055,.055)
    k.box('Angled_socket_panel',(0,-.235,.88),(.49,.055,.31),'interior',.01)
    for x in (-.15,0,.15):
        k.cylinder('Weatherproof_socket',(x,-.27,.88),.039,.035,'plastic','Y')
        k.box('Socket_hinged_cover',(x,-.298,.91),(.07,.012,.06),'plastic',.008)
    k.box('Power_unit_visor',(0,-.02,1.28),(.73,.54,.06),'paint',.012)
    k.section('Upper_lifting_handle',[(-.1,0,1.32),(-.1,0,1.39),(.1,0,1.39),(.1,0,1.32)],.012)


@model
def single_light():
    lamp_pole(5.2)
    k.section('Angled_LED_arm',[(0,0,4.9),(0,-.07,5.18),(0,-.58,5.5)],.032)
    lamp_head('Single_LED_fixture',(0,-.7,5.49),.6)


@model
def lit_parapet():
    k.box('Stone_lower_body',(0,.025,.3),(2.5,.35,.6),'stone',.006)
    k.box('Light_recess_rear',(0,-.175,.58),(2.38,.035,.16),'interior',.002)
    k.box('Light_strip_diffuser',(0,-.199,.58),(2.25,.009,.04),'diffuser',.004)
    k.box('Overhanging_stone_coping',(0,-.025,.715),(2.5,.4,.07),'stone',.004)
    for x in (-1.21,1.21): k.box('Channel_end_cap',(x,-.15,.64),(.07,.12,.15),'stone',.004)
    for x in (-.625,.625): k.box('Stone_laying_joint',(x,-.154,.29),(.003,.003,.52),'interior',0)


@model
def plywood_case():
    k.box('Plywood_floor',(0,0,.035),(.8,.6,.04),'wood',.002)
    for x in (-.39,.39): k.box('Plywood_side',(x,0,.325),(.02,.58,.6),'wood',.002)
    for y in (-.29,.29): k.box('Plywood_end',(0,y,.325),(.76,.02,.6),'wood',.002)
    k.box('Separate_plywood_lid',(0,0,.63),(.8,.6,.035),'wood',.003)
    for x in (-.39,.39):
        for y in (-.29,.29):
            for z in (.055,.61):
                k.box('Corner_angle_X',(x,y,z),(.07,.012,.065),'metal',.003)
                k.box('Corner_angle_Y',(x,y,z),(.012,.07,.065),'metal',.003)
                k.bolt('Corner_rivet',(x,y+math.copysign(.01,y),z),'Y',.004)
    for x in (-.24,.24):
        k.box('Lid_toggle_catch',(x,-.31,.59),(.045,.018,.08),'metal',.003)
        k.cylinder('Lid_hinge',(x,.306,.6),.008,.08,axis='X')
    for x in (-.405,.405):
        k.box('Recessed_handle_backplate',(x,0,.36),(.008,.2,.09),'interior',.008)
        k.section('Folding_recessed_handle',[(x, -.07,.37),(x+math.copysign(.01,x),-.07,.32),(x+math.copysign(.01,x),.07,.32),(x,.07,.37)],.007)


@model
def lattice_barrier():
    for x in (-1.18,1.18):
        k.box('End_upright',(x,0,.55),(.045,.06,.99),'metal',.004)
        k.bar('End_cross_foot',(x,-.3,.035),(x,.3,.035),.022)
    for j in range(8):
        x=-1.15+j*.288
        for flip in (-1,1):
            k.beam('Crossed_flat_link',(x,-flip*.013,.18 if flip==1 else .94),(x+.288,-flip*.013,.94 if flip==1 else .18),.032,.009,'paint',.002)
        for xx,zz in ((x,.18),(x,.94),(x+.144,.56)):
            k.cylinder('Scissor_pivot',(xx,-.028,zz),.014,.013,axis='Y',n=24)


@model
def checkpoint_cage():
    for side in (-1,1):
        before=len(k.PARTS)
        k.panel_frame('Side_frame',2,2.1,0,.08,'metal',.04)
        wire_grid('Cage_mesh',1.92,2.0,0,.13,.11,.003)
        k.transform(k.since(before),(side*.99,0,0),(0,0,pi/2))
    k.panel_frame('Back_frame',2,2.1,.99,.08,'metal',.04)
    wire_grid('Back_mesh',1.92,2.0,.99,.13,.11,.003)
    for x in (-.99,.99): k.beam('Front_stanchion',(x,-.99,0),(x,-.99,2.2),.045,.045)
    k.panel_frame('Front_gate',1.8,2.02,-1,.1,'metal',.035)
    wire_grid('Gate_mesh',1.73,1.94,-1,.14,.11,.003)
    for z in (.35,1.8): k.cylinder('Gate_barrel_hinge',(-.94,-1,z),.016,.12)
    k.box('Slide_bolt',(.8,-1.04,1.05),(.25,.04,.035),'metal',.004)
    for x in (-.99,.99):
        for y in (-.99,.99): k.foot('Post_flange',x,y,.15,.15)


@model
def traffic_light():
    k.lathe('Tapered_signal_pole',[(0,0),(.105,0),(.105,.14),(.07,.2),(.055,4.25),(.045,4.35),(0,4.35)],role='paint')
    k.section('Swept_signal_console',[(0,0,4.1)]+[(2.3*(1-cos(pi/2*i/24)),0,4.1+.65*sin(pi/2*i/24)) for i in range(1,25)],.045,'paint')
    for x,z0 in ((2.3,3.95),(0,2.4)):
        k.box('Signal_backplate',(x,.02,z0),(.37,.1,1.05),'paint',.045)
        for i in range(3):
            z=z0+.32-i*.32
            k.cylinder('Optical_lens',(x,-.06,z),.115,.035,'glass','Y',64)
            # Незамкнутый козырёк над каждой линзой.
            k.patch('Deep_signal_visor',lambda u,v:(x+.13*cos(-.2*pi+1.4*pi*u),-.07-.22*v,z+.13*sin(-.2*pi+1.4*pi*u)),32,4,'paint',.006)
        k.box('Rear_signal_access',(x,.09,z0),(.28,.045,.95),'paint',.025)
    k.foot('Signal_base',0,0,.3,.3)


@model
def generator():
    cabinet_shell('Diesel_generator',1.35,.7,.8,.25)
    for x in (-.6,.6):
        for y in (-.29,.29): k.box('Vibration_mount',(x,y,.22),(.12,.1,.08),'rubber',.012)
    k.box('Underframe',(0,0,.18),(1.5,.8,.1),'metal',.008)
    for y in (-.38,.38):
        k.box('Engine_vent_shadow',(0,y,.76),(.96,.008,.36),'interior',.002)
        k.slotted_panel('Engine_vent',(0,y,.76),(1.0,.025,.38),13,'paint')
    for x in (-.55,.55):
        k.section('Folding_carry_handle',[(x,-.34,1.02),(x,-.47,1.08),(x+.18,-.47,1.08),(x+.18,-.34,1.02)],.018)
    for x in (-.75,.75):
        k.cylinder('Generator_wheel',(x,.1,.2),.2,.11,'rubber','X',48)
        k.cylinder('Wheel_hub',(x+math.copysign(.06,x),.1,.2),.075,.025,'metal','X',32)
    k.box('Electrical_control_panel',(-.68,-.01,.68),(.025,.47,.4),'interior',.008)
    for y in (-.14,.02,.18): k.cylinder('Power_socket',(-.705,y,.65),.04,.03,'plastic','X')
    k.box('Meter',(-.71,-.09,.8),(.015,.14,.08),'screen',.003)
    k.section('Exhaust_pipe',[(.4,.22,1.0),(.4,.22,1.2),(.3,.22,1.25)],.022)
    k.cylinder('Fuel_cap',(-.35,0,1.07),.055,.025,'plastic')


@model
def detour_board():
    k.box('Folded_metal_sign',(0,0,.8),(1.6,.035,.7),'paint',.015)
    for x in (-.76,.76): k.box('Folded_vertical_edge',(x,.035,.8),(.025,.05,.68),'metal',.003)
    for x in (-.57,-.19,.19,.57):
        k.extrude('Diagonal_reflector',[(x-.16,.47),(x-.04,.47),(x+.16,1.13),(x+.04,1.13)],'Y',-.023,-.02,'reflector',.001)
    for x in (-.58,.58):
        k.beam('Sign_A_frame_front',(x,-.35,.02),(x,0,1.18),.035,.035)
        k.beam('Sign_A_frame_back',(x,.35,.02),(x,0,1.18),.035,.035)
        k.bar('Foot_tie',(x,-.35,.09),(x,.35,.09),.01)
    k.beam('Rear_horizontal_tie',(-.58,.26,.3),(.58,.26,.3),.03,.03)


@model
def power_cable():
    pts=[]
    for i in range(721):
        a=i*2*pi/120
        r=.29+.014*sin(a*.17)+.006*cos(a*2)
        pts.append((r*cos(a),r*.82*sin(a),.025+.014*i/120))
    k.section('Six_irregular_cable_turns',pts,.012,'rubber',12)
    k.section('Cable_free_end',[pts[-1],(.25,-.2,.08),(.3,-.4,.03),(.4,-.42,.025)],.012,'rubber',12)
    for loc,axis in [((.43,-.42,.035),'X'),((.29,0,.035),'Y')]:
        k.cylinder('Industrial_connector',loc,.032,.11,'rubber',axis)
        for i in (-1,0,1):
            if axis=='X': k.cylinder('Connector_pin',(.5,-.42+i*.012,.035),.003,.02,'metal','X',16)
            else: k.cylinder('Connector_pin',(.29+i*.012,.07,.035),.003,.02,'metal','Y',16)


@model
def tank():
    prof=[(0,-2.8)]+[(1.05*sin(i*pi/48),-2.8+.5*(1-cos(i*pi/48))) for i in range(1,25)]
    prof += [(1.05,2.3)]+[(1.05*cos(i*pi/48),2.3+.5*sin(i*pi/48)) for i in range(1,25)]
    k.lathe('Elliptical_ended_tank',prof,(0,0,1.18),'Y','paint',128)
    for y in (-1.8,1.8):
        k.extrude('Steel_saddle_support',[(-1.08,0),(1.08,0),(1.08,.6),(.75,.47),(.45,.27),(-.45,.27),(-.75,.47),(-1.08,.6)],'Y',y-.16,y+.16,'metal',.01)
        k.ring('Tank_reinforcement_band',(0,y,1.18),1.058,.018,'metal','Y',128)
    k.cylinder('Top_access_neck',(0,.1,2.29),.27,.14)
    k.cylinder('Top_hatch',(0,.1,2.38),.3,.04)
    for i in range(12):
        a=2*pi*i/12; k.bolt('Hatch_bolt',(.255*cos(a),.1+.255*sin(a),2.407),r=.009)
    for y in (-.65,.65): k.section('Tank_ladder_side',[(1.02,y,.15),(1.08,y,1.2),(.85,y,1.9),(.55,y,2.2)],.022)
    for j in range(9):
        z=.24+j*.22; x=1.07 if z<1.2 else 1.07-(z-1.2)*.55
        k.bar('Ladder_rung',(x,-.65,z),(x,.65,z),.013)
    k.section('Drain_pipe',[(0,-2.3,.4),(0,-2.65,.4),(0,-2.65,.15)],.045)
    k.ring('Drain_valve_wheel',(0,-2.65,.18),.12,.012,axis='Y')


@model
def service_cage():
    for y in (-.4,.4):
        k.panel_frame('Service_cage_frame',1.7,1.7,y,.05,'metal',.035)
        wire_grid('Service_cage_mesh',1.62,1.61,y,.1,.075,.0025)
    for x in (-.83,.83):
        for z in (.07,1.72): k.bar('Depth_frame',(x,-.4,z),(x,.4,z),.017)
    k.box('Fan_mounting_plate',(0,.18,.88),(1.4,.025,1.55),'paint',.006)
    for z in (.48,1.25):
        k.cylinder('Fan_motor',(0,.08,z),.11,.25,axis='Y')
        for i in range(5):
            a=i*2*pi/5
            ob=k.extrude('Swept_fan_blade',[(.08,0),(.32,.05),(.34,.14),(.11,.14)],'Y',-.035,-.02,'metal',.005)
            from mathutils import Matrix
            ob.matrix_world=Matrix.Translation((0,-.11,z))@Matrix.Rotation(a,4,'Y')@ob.matrix_world
        for r in (.12,.2,.29,.36): k.ring('Fan_safety_wire',(0,-.16,z),r,.003,axis='Y')
    k.box('Door_latch',(.7,-.435,.8),(.1,.025,.1),'metal',.004)


def subtract(ob,cutter):
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Modelled wheel opening / cavity','BOOLEAN')
    mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
    while ob.modifiers[0]!=mod:
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    k.PARTS.remove(cutter)
    bpy.data.objects.remove(cutter,do_unlink=True)


@model
def hatchback():
    # Собственный кузов по продольным сечениям; не оболочка поверх фотографии.
    stations=[(-2.1,.59,.42,.65),(-1.92,.79,.3,.75),(-1.55,.86,.24,.81),
              (-.95,.89,.23,.83),(-.2,.9,.23,.85),(.65,.9,.23,.85),
              (1.35,.88,.25,.82),(1.92,.8,.32,.76),(2.1,.63,.4,.7)]
    def catmull(a,b,c,d,t):
        return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
    dense=[]
    for i in range(len(stations)-1):
        for j in range(8):
            t=j/8
            dense.append(tuple(catmull(stations[max(0,i-1)][q],stations[i][q],stations[i+1][q],stations[min(len(stations)-1,i+2)][q],t) for q in range(4)))
    dense.append(stations[-1])
    verts=[]
    for y,w,z0,z1 in dense:
        profile=[(-w*.76,z0),(-w*.9,z0+.014),(-w*.98,z0+.045),(-w,z0+.10),
                 (-w,z1-.14),(-w*.97,z1-.065),(-w*.9,z1-.018),(-w*.72,z1),
                 (-w*.36,z1+.021),(0,z1+.03),(w*.36,z1+.021),(w*.72,z1),
                 (w*.9,z1-.018),(w*.97,z1-.065),(w,z1-.14),(w,z0+.10),
                 (w*.98,z0+.045),(w*.9,z0+.014),(w*.76,z0)]
        verts.extend((x,y,z) for x,z in profile)
    ns=len(profile)
    faces=[]
    for j in range(len(dense)-1):
        for i in range(ns): faces.append((j*ns+i,j*ns+(i+1)%ns,(j+1)*ns+(i+1)%ns,(j+1)*ns+i))
    faces += [tuple(reversed(range(ns))),tuple((len(dense)-1)*ns+i for i in range(ns))]
    body=k.mesh('Lofted_hatchback_body',verts,faces,'paint',.008,True)
    # Порядок: отверстия до фаски, чтобы арки оставались ровными.
    for y in (-1.28,1.27):
        cutter=k.cylinder('TEMP_wheel_arch_cutter',(0,y,.32),.36,2.3,axis='X',n=96)
        subtract(body,cutter)
    cutter=k.box('TEMP_real_boot_cavity',(0,1.47,1.1),(1.3,1.1,1.3),'interior',0)
    subtract(body,cutter)
    for x in (-.83,.83):
        for y in (-1.28,1.27):
            tyre('Road_tyre',(x,y,.32),.31,.18,'X')
            k.lathe('Alloy_rim_profile',[(.17,-.105),(.23,-.105),(.238,-.08),(.21,.07),(.17,.07),(.17,-.105)],(x,y,.32),'X','metal',64)
            k.cylinder('Wheel_hub',(x+math.copysign(.105,x),y,.32),.06,.025,axis='X')
            for j in range(5):
                a=j*2*pi/5
                k.beam('Alloy_wheel_spoke',(x+math.copysign(.1,x),y+.05*cos(a),.32+.05*sin(a)),(x+math.copysign(.08,x),y+.215*cos(a+.12),.32+.215*sin(a+.12)),.026,.018)
                k.bolt('Wheel_lug',(x+math.copysign(.122,x),y+.042*cos(a),.32+.042*sin(a)),'X',.007)
    k.box('Boot_floor',(0,1.47,.46),(1.25,1.0,.03),'interior',.008)
    k.box('Rear_seat_back',(0,.89,.87),(1.3,.13,.47),'interior',.035)
    # Кабина: крыша, настоящие стойки, отдельное остекление.
    k.patch('Crowned_roof',lambda u,v:((u-.5)*1.44,-.32+1.25*v,1.55+.045*sin(pi*u)-.025*(2*v-1)**2),48,40,'paint',.035)
    for side in (-1,1):
        x=side*.73
        k.beam('A_pillar',(side*.82,-.98,.83),(x,-.32,1.55),.045,.045,'paint',.009)
        k.beam('B_pillar',(side*.87,.25,.83),(x,.25,1.57),.055,.045,'paint',.008)
        k.beam('C_pillar',(side*.84,1.18,.83),(x,.91,1.54),.075,.06,'paint',.009)
        k.section('Roof_side_rail',[(x,-.32,1.55),(x,.25,1.57),(x,.91,1.54)],.023,'paint')
        for name,points in [('Front_side_window',[(side*.83,-.89,.9),(side*.85,.19,.9),(x,.19,1.51),(x,-.29,1.5)]),('Rear_side_window',[(side*.85,.3,.9),(side*.82,1.09,.9),(x,.86,1.5),(x,.3,1.52)])]:
            ob=k.mesh(name,points,[(0,1,2,3)],'glass')
            ob.modifiers.new('Safety_glass_thickness','SOLIDIFY').thickness=.008
        k.section('Door_shutline',[(side*.897,-.8,.37),(side*.897,-.82,.76),(side*.902,.23,.78),(side*.902,.25,.37),(side*.897,-.8,.37)],.002,'interior',6)
        k.soft('Door_pull',(side*.918,.04,.73),(.025,.14,.032),'metal',.55)
        k.bar('Mirror_stalk',(side*.8,-.72,1.0),(side*.98,-.7,1.0),.014)
        k.soft('Mirror_shell',(side*1.01,-.69,1.04),(.16,.22,.10),'paint',.65)
        k.box('Mirror_glass',(side*1.01,-.575,1.04),(.11,.006,.065),'glass',.012)
    ob=k.mesh('Sloped_front_windscreen',[(-.78,-.94,.88),(.78,-.94,.88),(.69,-.34,1.52),(-.69,-.34,1.52)],[(0,1,2,3)],'glass')
    ob.modifiers.new('Laminated_windscreen_thickness','SOLIDIFY').thickness=.009
    for x in (-.36,.34):
        k.bar('Windscreen_wiper',(x,-.9,.94),(x+.22,-.62,1.14),.004,'rubber',8)
    # Открытый багажный люк с отдельной рамой; рабочая поза не является анимацией.
    before=len(k.PARTS)
    ob=k.mesh('Hatch_glass',[(-.68,0,0),(.68,0,0),(.68,.65,-.61),(-.68,.65,-.61)],[(0,1,2,3)],'glass')
    ob.modifiers.new('Rear_glass_thickness','SOLIDIFY').thickness=.008
    for x in (-.72,.72): k.beam('Hatch_side_frame',(x,0,0),(x,.9,-.78),.055,.055,'paint',.009)
    for y,z in ((0,0),(.9,-.78)): k.beam('Hatch_cross_frame',(-.73,y,z),(.73,y,z),.055,.055,'paint',.008)
    k.box('Hatch_lower_skin',(0,.83,-.72),(1.4,.22,.12),'paint',.018)
    k.transform(k.since(before),(0,1.02,1.54),(math.radians(68),0,0))
    for side in (-1,1): k.bar('Boot_gas_strut',(side*.65,1.73,.77),(side*.65,1.68,1.98),.007)
    for x in (-.39,.39):
        k.soft('Front_seat_cushion',(x,-.13,.64),(.53,.48,.15),'interior',.45)
        k.soft('Front_seat_back',(x,.04,.94),(.53,.16,.62),'interior',.45)
        k.soft('Front_headrest',(x,.06,1.25),(.28,.12,.17),'interior',.5)
    k.box('Dashboard',(0,-.69,.92),(1.35,.3,.18),'interior',.045)
    k.ring('Steering_wheel',(-.38,-.48,1.04),.16,.016,'rubber','Y')
    k.box('Front_grille_recess',(0,-2.112,.53),(.9,.025,.15),'interior',.012)
    for z in (.49,.53,.57): k.box('Grille_horizontal_bar',(0,-2.131,z),(.87,.015,.012),'metal',.002)
    for x in (-.43,.43):
        k.soft('Front_headlamp',(x,-2.124,.67),(.3,.045,.115),'glass',.4)
        k.soft('Rear_lamp',(x,2.118,.68),(.25,.04,.14),'glass',.4)
    for y in (-2.141,2.14): k.box('Registration_plate',(0,y,.4),(.52,.015,.11),'metal',.005)
    k.cylinder('Exhaust_tailpipe',(.54,1.98,.22),.031,.21,'metal','Y')


@model
def escalator():
    # Базовый подъём 3 м, собственные ступени и замкнутый возврат поручней.
    sideprofile=[(-.65,.08),(.5,.08),(5.7,3.08),(6.5,3.08),(6.5,3.4),(5.62,3.4),(.42,.4),(-.65,.4)]
    for x in (-.68,.68):
        k.extrude('Inclined_support_truss',sideprofile,'X',x-.1,x+.1,'metal',.006)
        k.extrude('Balustrade_panel',[(-.6,.38),(.45,.38),(5.65,3.38),(6.45,3.38),(6.45,4.02),(5.6,4.02),(.4,1.02),(-.6,1.02)],'X',x-.035,x+.035,'metal',.006)
        for j in range(11):
            y=.5+j*.5; z=.41+(y-.5)*3/5.2
            k.box('Balustrade_panel_joint',(x-.04,y,z+.3),(.005,.006,.55),'interior',0)
        # Верхний ход и возврат резинового поручня, округлённые оконечности.
        path=[(x,-.53,.98),(x,.42,.98),(x,5.62,3.98),(x,6.28,3.98)]
        path += [(x,6.28+.17*sin(pi*i/16),3.81+.17*cos(pi*i/16)) for i in range(1,17)]
        path += [(x,5.69,3.64),(x,.49,.64),(x,-.53,.64)]
        path += [(x,-.53-.17*sin(pi*i/16),.81-.17*cos(pi*i/16)) for i in range(1,17)]
        path.append(path[0])
        k.section('Continuous_rubber_handrail',[(xx,yy,zz+.09) for xx,yy,zz in path],.035,'rubber',20)
    for i in range(15):
        y=.5+i*5.2/15; z=.39+(i+1)*.2
        k.box('Escalator_step_tread',(0,y,z),(.99,.36,.024),'metal',.003)
        k.box('Escalator_step_riser',(0,y-.168,z-.095),(.99,.018,.19),'metal',.002)
        for j in range(40):
            x=-.48+j*.0245
            k.box('Tread_grip_rib',(x,y,z+.018),(.010,.34,.012),'metal',.002)
            k.box('Riser_vertical_rib',(x,y-.18,z-.095),(.009,.006,.18),'metal',.001)
    for y,z in ((-.12,.39),(6.08,3.39)):
        k.box('Landing_access_plate',(0,y,z),(1.1,.82,.035),'metal',.004)
        for j in range(42): k.box('Landing_comb_tooth',(-.5+j*.0244,y+.35,z+.022),(.011,.11,.014),'metal',.001)
    for x in (-.72,.72):
        k.cylinder('Emergency_stop_button',(x,-.56,.63),.023,.025,'plastic','Y')
        k.box('Service_key_panel',(x,-.6,.78),(.08,.02,.09),'metal',.007)
