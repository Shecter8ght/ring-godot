"""Мебель, медицинское оснащение, банк и интерьерный свет."""
import math
from math import pi,sin,cos
import meshkit as k
from street import cabinet_shell
REGISTRY={}
def model(fn): REGISTRY[fn.__name__]=fn; return fn


@model
def turnstile():
    profile=[(x,z+.57) for x,z in k.rounded_rect(.26,1.02,.07)]
    k.extrude('Radius_end_body',profile,'Y',-.5,.5,'metal',.004)
    k.box('Black_reader_top',(0,-.27,1.073),(.21,.3,.018),'screen',.022)
    k.box('Service_access',(0,-.511,.51),(.19,.015,.72),'metal',.008)
    k.cylinder('Service_lock',(.05,-.523,.68),.01,.01,axis='Y')
    k.extrude('Glass_swing_flap',[(.12,.25),(.64,.25),(.7,.36),(.7,.9),(.62,1.02),(.12,1.02)],'Y',-.05,-.038,'glass',.008)
    k.cylinder('Flap_pivot',(.12,-.044,.62),.02,.74)
    k.box('Floor_pedestal',(0,0,.035),(.28,.8,.07),'interior',.012)


@model
def reception_stone():
    k.box('Front_stone_fascia',(0,-.52,.59),(3.6,.09,1.12),'stone',.008)
    k.box('Right_return',(1.75,.22,.59),(.1,1.5,1.12),'stone',.008)
    k.box('Upper_front_counter',(0,-.48,1.14),(3.64,.38,.06),'stone',.006)
    k.box('Upper_return_counter',(1.62,.23,1.14),(.35,1.5,.06),'stone',.006)
    k.box('Inner_worktop',(-.08,-.03,.76),(3.1,.65,.045),'wood',.005)
    for x in (-1.4,.9):
        before=len(k.PARTS)
        cabinet_shell('Inner_storage',.48,.5,.68,.05)
        k.transform(k.since(before),(x,.05,0))
    k.box('Recessed_black_plinth',(0,-.46,.045),(3.45,.15,.09),'interior',.003)


@model
def sofa():
    k.soft('Upholstered_base',(0,.03,.29),(2.0,.79,.28),'fabric',.25)
    for x in (-.49,.49):
        k.soft('Separate_seat_cushion',(x,-.07,.48),(.94,.67,.17),'fabric',.35)
        ob=k.soft('Separate_back_cushion',(x,.29,.67),(.95,.18,.43),'fabric',.38)
        ob.rotation_euler.x=math.radians(-8)
    for x in (-.93,.93): k.soft('Rolled_padded_arm',(x,0,.55),(.21,.8,.34),'fabric',.5)
    for x in (-.78,.78):
        for y in (-.28,.28): k.cylinder('Recessed_sofa_leg',(x,y,.095),.035,.19,'metal',n=32)
    for x in (-.49,.49):
        pts=[(x+.465*cos(a),-.07+.325*sin(a),.487) for a in [2*pi*j/96 for j in range(97)]]
        k.section('Seat_edge_piping',pts,.003,'fabric',8)


@model
def coffee_table():
    k.lathe('Thin_round_stone_top',[(0,.39),(.43,.39),(.44,.397),(.44,.42),(.43,.427),(0,.427)],role='stone',n=96)
    k.ring('Under_top_steel_ring',(0,0,.37),.35,.014)
    for a in (pi/4,3*pi/4,5*pi/4,7*pi/4):
        k.section('Angled_table_leg',[(.37*cos(a),.37*sin(a),.015),(.27*cos(a),.27*sin(a),.12),(.3*cos(a),.3*sin(a),.37)],.014)
        k.cylinder('Table_rubber_foot',(.37*cos(a),.37*sin(a),.012),.022,.02,'rubber',n=24)


@model
def wall_niche():
    for x in (-.23,.23): k.box('Niche_side',(x,0,.45),(.02,.13,.9),'metal',.003)
    for z in (.01,.89): k.box('Niche_cap',(0,0,z),(.46,.13,.02),'metal',.003)
    k.box('Recessed_reflector_back',(0,.055,.45),(.44,.012,.86),'metal',.003)
    k.extrude('Folded_up_reflector',[(-.06,.02),(.045,.02),(.045,.11),(.025,.11)],'X',-.21,.21,'metal',.002)
    k.box('Hidden_linear_diffuser',(0,-.025,.07),(.4,.035,.015),'diffuser',.004)
    for x in (-.21,.21):
        for z in (.04,.86): k.bolt('Mount_screw',(x,-.071,z),'Y',.004)


@model
def medical_tent():
    # Непримитивное арочное сечение с приподнятыми вертикальными боковинами.
    w,h,length=4.5,3.1,5.5
    def shape(a):
        return (2.25*cos(a),1.2+1.9*sin(a))
    k.patch('Outer_coated_fabric',lambda u,v:(shape(pi*u)[0]+.012*sin(10*pi*v)*sin(pi*u),-2.75+5.5*v,shape(pi*u)[1]-.025*sin(10*pi*v)*sin(pi*u)),64,64,'fabric',.012)
    for side in (-1,1):
        k.patch('Vertical_tent_skirt',lambda u,v:(side*(2.25+.012*sin(8*pi*u)*sin(pi*v)),-2.75+5.5*u,1.2*v),48,16,'fabric',.01)
    for y in [-2.7+i*1.08 for i in range(6)]:
        k.section('Internal_arch_frame',[(shape(pi*i/48)[0]*.985,y,shape(pi*i/48)[1]-.035) for i in range(49)],.035)
        for x in (-2.21,2.21): k.bar('Arch_frame_lower_leg',(x,y,.05),(x,y,1.2),.035)
        k.section('Raised_fabric_arch_seam',[(shape(pi*i/48)[0]*1.002,y-.015,shape(pi*i/48)[1]+.003) for i in range(49)],.004,'fabric',8)
    # Передний торец формируется вокруг настоящего прохода 1,56 × 2,42 м.
    for side in (-1,1):
        k.patch('Front_side_fabric',lambda u,v:(side*(.82+(2.22-.82)*u),-2.75,.03+min(2.95,1.2+1.9*math.sqrt(max(0,1-((.82+1.4*u)/2.25)**2)))*v),32,32,'fabric',.01)
    k.patch('Front_above_entry',lambda u,v:(-.82+1.64*u,-2.75,2.45+(.65-.13*(2*u-1)**2)*v),24,12,'fabric',.012)
    k.patch('Closed_rear_fabric',lambda u,v:(-2.23+4.46*u,2.75,(1.2+1.9*math.sqrt(max(0,1-((-2.23+4.46*u)/2.25)**2)))*v),64,40,'fabric',.01)
    for x in (-.81,.81): k.box('Entrance_jamb',(x,-2.77,1.22),(.065,.07,2.44),'metal',.005)
    k.box('Entrance_header',(0,-2.77,2.45),(1.69,.07,.06),'metal',.005)
    # Откинутая мягкая входная створка как отдельная оболочка.
    before=len(k.PARTS)
    k.patch('Open_entry_flap',lambda u,v:(1.56*u,0,.05+2.37*v+.012*sin(8*pi*u)*sin(5*pi*v)),32,32,'fabric',.015)
    k.transform(k.since(before),(-.81,-2.79,0),(0,0,-pi/2.8))
    for side in (-1,1):
        for z in (1.7,1.82): k.box('Reference_colour_band',(side*2.26,0,z),(.008,5.38,.065),'reflector',.001)


def hanging_cloth(name,x,y,z,w,h):
    k.patch(name,lambda u,v:(x+(u-.5)*w,y+.018*sin(10*pi*u)*sin(pi*v),z+h*v-.02*sin(pi*u)),40,24,'fabric',.002)
    for i in range(9): k.ring('Curtain_hanger',(x-w*.45+i*w*.1125,y,z+h),.016,.0025,axis='X',n=20)


@model
def medical_screen():
    for i in range(3):
        before=len(k.PARTS)
        k.section('Bent_screen_leaf_frame',k.rounded_path_xz(.58,1.55,0,.17,.07),.014)
        k.bar('Screen_lower_tie',(-.27,0,.3),(.27,0,.3),.012)
        hanging_cloth('Pleated_medical_fabric',0,0,.34,.51,1.28)
        for x in (-.26,.26): k.caster('Screen_caster',x,0,.055,.04)
        k.transform(k.since(before),((i-1)*.58,.12 if i!=1 else 0,0),(0,0,(-.32 if i==0 else .32) if i!=1 else 0))
    for x in (-.29,.29):
        for z in (.42,1.48): k.cylinder('Interleaf_hinge',(x,.01,z),.018,.08)


@model
def wheelchair():
    for x in (-.31,.31):
        k.ring('Rear_tyre',(x,.18,.32),.3,.019,'rubber','X',96)
        k.ring('Wheel_rim',(x,.18,.32),.278,.009,'metal','X',96)
        k.ring('Hand_push_rim',(x+math.copysign(.035,x),.18,.32),.256,.009,'metal','X',96)
        k.cylinder('Rear_hub',(x,.18,.32),.028,.11,axis='X')
        for j in range(28):
            a=2*pi*j/28
            k.bar('Tensioned_wheel_spoke',(x,.18,.32),(x,.18+.275*cos(a),.32+.275*sin(a)),.0018,sides=6)
        k.section('Chair_main_side',[(x,-.43,.14),(x,-.28,.49),(x,.3,.49),(x,.36,.91),(x,.46,.93)],.014)
        k.bar('Chair_side_front_leg',(x,-.28,.49),(x,-.35,.11),.014)
        k.caster('Front_castor',x,-.37,.09,.075)
        k.section('Armrest_support',[(x,-.25,.49),(x,-.2,.67),(x,.24,.67),(x,.29,.51)],.013)
        k.soft('Vinyl_armrest',(x,.01,.69),(.07,.43,.045),'rubber',.4)
        k.box('Foot_rest',(x*.7,-.52,.13),(.23,.22,.025),'metal',.012)
    k.patch('Hanging_vinyl_seat',lambda u,v:(-.28+.56*u,-.26+.54*v,.49-.035*sin(pi*u)),32,24,'rubber',.006)
    k.patch('Vinyl_backrest',lambda u,v:(-.28+.56*u,.31+.04*v,.5+.38*v-.02*sin(pi*u)),32,24,'rubber',.006)
    k.bar('Folding_crossbrace_A',(-.28,-.1,.2),(.28,-.1,.48),.012)
    k.bar('Folding_crossbrace_B',(.28,-.08,.2),(-.28,-.08,.48),.012)
    k.bar('Rear_axle',(-.35,.18,.32),(.35,.18,.32),.012)


@model
def stretcher():
    for x in (-.3,.3):
        k.bar('Longitudinal_stretcher_tube',(x,-1.03,.73),(x,1.03,.73),.018)
        for y in (-.94,.94): k.cylinder('Rubber_carry_grip',(x,y,.73),.024,.18,'rubber','Y')
        for y in (-.65,.65):
            k.beam('Folding_leg',(x,y,.7),(x,y*.8,.08),.026,.026)
            k.bar('Leg_diagonal',(x,y*.8,.1),(x,0,.7),.012)
        k.bar('Side_tension_rod',(x,-.52,.22),(x,.52,.22),.01)
    k.patch('Suspended_canvas_bed',lambda u,v:(-.28+.56*u,-.85+1.7*v,.73-.045*sin(pi*u)*sin(pi*v)),32,64,'fabric',.004)
    for y in (-.65,.65): k.bar('Folding_end_crossbar',(-.3,y,.18),(.3,y,.18),.014)
    for y in (-.55,0,.55): k.box('Patient_restraint_strap',(0,y,.734),(.58,.035,.004),'fabric',.001)


@model
def medical_cart():
    for x in (-.3,.3):
        for y in (-.19,.19):
            k.bar('Cart_stanchion',(x,y,.16),(x,y,.83),.012)
            k.caster('Cart_caster',x,y,.065,.05)
    for z in (.23,.77):
        k.box('Steel_tray',(0,0,z),(.65,.43,.016),'metal',.012)
        for x in (-.32,.32): k.box('Tray_raised_side',(x,0,z+.032),(.012,.41,.055),'metal',.005)
        for y in (-.21,.21): k.box('Tray_raised_end',(0,y,z+.032),(.64,.012,.055),'metal',.005)
    k.section('Push_handle',[(-.3,.19,.78),(-.3,.19,.9),(.3,.19,.9),(.3,.19,.78)],.013)


@model
def atm():
    cabinet_shell('ATM_safe_housing',.72,.6,1.06,.06)
    # Фасция с настоящей нишей экрана собрана по периметру.
    for x in (-.335,.335):
        k.extrude('ATM_sloped_cheek',[(-.3,1.05),(-.21,1.5),(.25,1.55),(.3,1.05)],'X',x-.025,x+.025,'paint',.012)
    k.box('ATM_top_visor',(0,.015,1.525),(.72,.57,.05),'paint',.009)
    k.box('ATM_screen_back',(0,-.145,1.32),(.55,.025,.28),'screen',.008)
    for x in (-.29,.29): k.box('ATM_screen_bezel_side',(x,-.19,1.32),(.045,.06,.34),'paint',.005)
    for z in (1.14,1.5): k.box('ATM_screen_bezel_end',(0,-.19,z),(.6,.06,.045),'paint',.005)
    k.box('ATM_keyboard_shelf',(0,-.29,1.07),(.59,.25,.04),'metal',.008)
    for j in range(4):
        for i in range(3): k.box('ATM_numeric_key',(-.07+i*.042,-.35+j*.035,1.095),(.034,.028,.009),'plastic',.004)
    for i in range(3): k.box('ATM_function_key',(.12,-.35+i*.045,1.095),(.055,.03,.01),'plastic',.004)
    k.box('Cash_aperture_shadow',(0,-.322,.83),(.39,.02,.055),'interior',.006)
    k.box('Cash_aperture_lip',(0,-.354,.798),(.4,.07,.016),'metal',.003)
    k.box('Card_reader_housing',(.22,-.33,.99),(.13,.055,.055),'plastic',.008)
    k.box('Card_slot',(.22,-.362,.995),(.087,.008,.006),'interior',.001)
    k.box('Receipt_slot',(-.19,-.327,.98),(.15,.008,.012),'interior',.001)


@model
def bank_kiosk():
    k.extrude('Tapered_kiosk_column',[(-.21,.05),(.21,.05),(.19,1.3),(.3,1.5),(.23,1.65),(-.22,1.5)],'Y',-.17,.17,'paint',.012)
    panel=k.box('Angled_screen_panel',(0,-.2,1.43),(.49,.05,.36),'interior',.015)
    panel.rotation_euler.x=math.radians(-12)
    display=k.box('Recessed_touch_screen',(0,-.233,1.43),(.42,.012,.29),'screen',.006)
    display.rotation_euler.x=math.radians(-12)
    k.box('Keyboard_rest',(0,-.24,1.13),(.5,.3,.035),'metal',.01)
    k.box('Heavy_kiosk_base',(0,0,.035),(.58,.42,.07),'metal',.02)
    k.box('Rear_service_door',(0,.184,.68),(.32,.015,.87),'paint',.007)
    k.cylinder('Rear_door_lock',(.1,.2,.8),.011,.009,axis='Y')


@model
def armchair():
    k.soft('Thick_bucket_shell_base',(0,.02,.41),(.73,.7,.18),'fabric',.45)
    k.soft('Separate_bucket_seat',(0,-.07,.49),(.6,.55,.15),'fabric',.5)
    def fn(u,v):
        a=-.07*pi+1.14*pi*u
        r=.34+.025*v
        return (r*cos(a),.05+r*.82*sin(a),.43+.37*v+.045*sin(pi*u))
    ob=k.patch('Continuous_wrapping_back_and_arms',fn,72,24,'fabric',.055)
    for x in (-.25,.25):
        for y in (-.23,.23):
            k.beam('Splayed_tubular_leg',(x*1.15,y*1.15,.02),(x,y,.38),.025,.025,'metal',.005)
            k.cylinder('Nylon_foot',(x*1.15,y*1.15,.015),.02,.024,'rubber',n=24)
    k.section('Back_edge_piping',[fn(i/96,1) for i in range(97)],.003,'fabric',8)


@model
def teller_desk():
    k.box('Teal_front_fascia',(0,-.34,.64),(1.55,.08,1.2),'paint',.007)
    for x in (-.72,.72): k.box('Laminate_side',(x,0,.61),(.065,.7,1.15),'wood',.005)
    k.box('Public_counter',(0,-.29,1.23),(1.6,.4,.045),'wood',.007)
    k.box('Lower_worktop',(0,.09,.77),(1.42,.57,.035),'wood',.005)
    before=len(k.PARTS)
    cabinet_shell('Drawer_pedestal',.43,.48,.69,.035)
    k.transform(k.since(before),(.46,.05,0))
    for z in (.2,.4,.6): k.box('Drawer_pull',(.46,-.215,z),(.18,.025,.022),'metal',.005)
    k.box('Cable_cover',(0,.16,.795),(.19,.075,.006),'metal',.006)
    k.box('Recessed_desk_plinth',(0,-.28,.04),(1.43,.14,.08),'interior',.003)


@model
def reception_lit():
    k.box('Reception_front_light_panel',(0,-.47,.62),(4.14,.055,.9),'diffuser',.008)
    for x in (-2.05,2.05): k.box('Stone_counter_end',(x,.01,.64),(.1,1.05,1.02),'stone',.006)
    k.box('Black_stone_public_top',(0,-.34,1.13),(4.2,.48,.055),'stone',.006)
    k.box('Internal_worktop',(0,.2,.78),(3.98,.62,.04),'stone',.005)
    for x in (-1.35,1.35):
        k.box('Interior_storage_pedestal',(x,.21,.41),(.55,.53,.73),'wood',.008)
        k.box('Interior_storage_door',(x,-.067,.41),(.49,.025,.64),'wood',.005)
    for z in (.14,1.08): k.box('Bronze_front_trim',(0,-.508,z),(4.2,.018,.025),'metal',.003)
    k.box('Recessed_dark_plinth',(0,-.38,.06),(3.98,.16,.12),'interior',.003)
    k.lettering('Original_reception_name','ВЕРШИНА',(1.2,-.512,.62),.13)


@model
def ring_chandelier():
    prof=[(1.04,0),(1.1,0),(1.105,.012),(1.105,.09),(1.09,.105),(1.04,.105),(1.04,0)]
    k.lathe('Bronze_ring_body',prof,role='metal',n=192)
    k.lathe('Recessed_opal_ring',[(1.048,-.004),(1.095,-.004),(1.095,.009),(1.048,.009),(1.048,-.004)],role='diffuser',n=192)
    for i in range(12):
        a=2*pi*i/12
        k.bar('Radial_suspension_wire',(1.065*cos(a),1.065*sin(a),.1),(.055*cos(a),.055*sin(a),.84),.0025,sides=8)
    k.lathe('Central_cable_hub',[(0,.78),(.075,.78),(.075,.86),(.04,.89),(0,.89)],n=48)
    for j in range(10): k.ring('Suspension_chain_link',(0,0,.91+j*.034),.024,.004,axis='X' if j%2 else 'Y',n=24)
    k.cylinder('Ceiling_rose',(0,0,1.26),.12,.035)


@model
def monitor():
    outline=[(x,z+.29) for x,z in k.rounded_rect(.56,.33,.025)]
    k.extrude('Tapered_monitor_shell',outline,'Y',-.018,.018,'metal',.003)
    k.box('Inset_black_bezel',(0,-.024,.29),(.53,.012,.3),'interior',.014)
    k.box('LCD_surface',(0,-.032,.298),(.502,.005,.267),'screen',.008)
    k.extrude('Curved_monitor_stand',[(-.025,.02),(.025,.02),(.04,.22),(.015,.25),(-.015,.22)],'X',-.026,.026,'metal',.004)
    k.box('Weighted_monitor_foot',(0,.025,.014),(.26,.21,.028),'metal',.016)
    k.box('Rear_connector_recess',(0,.026,.22),(.18,.015,.055),'interior',.004)
    for x in (-.055,0,.055): k.box('Rear_display_port',(x,.036,.22),(.025,.009,.012),'metal',.001)
    k.ring('Stand_cable_passthrough',(0,.028,.12),.018,.004,axis='Y',n=32)


@model
def credenza():
    for x in (-1.17,-.4,.4,1.17): k.box('Vertical_storage_panel',(x,0,.47),(.03,.45,.76),'wood',.003)
    for z in (.11,.45,.84): k.box('Long_storage_shelf',(0,0,z),(2.4,.45,.025),'wood',.003)
    k.box('Storage_rear_panel',(0,.216,.47),(2.36,.018,.72),'wood',.002)
    for x in (-1,1):
        for y in (-.15,.15): k.box('Recessed_cabinet_leg',(x,y,.05),(.055,.055,.1),'metal',.008)
    for x in (-.8,0,.8): k.box('Shelf_edge_trim',(x,-.228,.46),(.77,.012,.018),'metal',.002)


@model
def water_bottle():
    profile=[(0,.012),(.07,.012),(.12,0),(.138,.018),(.145,.04),(.14,.065),(.135,.1)]
    for z in (.12,.19,.26,.33): profile.extend([(.135,z),(.144,z+.012),(.144,z+.03),(.135,z+.042)])
    profile.extend([(.133,.39),(.122,.42),(.09,.45),(.036,.47),(.033,.49),(.028,.49),(.029,.467),(.083,.445),(.115,.414),(.126,.385),(.126,.075),(.12,.03),(.07,.023),(0,.023)])
    k.lathe('Ribbed_hollow_PET_bottle',profile,role='glass',n=128)
    k.lathe('Screw_cap',[(0,.489),(.036,.489),(.038,.497),(.038,.514),(.033,.52),(0,.52)],role='plastic')
    for j in range(32):
        a=j*pi/16; k.bar('Cap_grip_ridge',(.038*cos(a),.038*sin(a),.496),(.038*cos(a),.038*sin(a),.514),.001,'plastic',6)


@model
def industrial_light():
    prof=[(-.09,.0),(-.09,.04),(-.065,.1),(.065,.1),(.09,.04),(.09,0),(.07,0),(.06,.07),(-.06,.07),(-.07,0)]
    k.extrude('Pressed_steel_reflector',prof,'X',-.625,.625,'metal',.003)
    k.box('Yellowed_prismatic_diffuser',(0,0,.015),(1.19,.135,.03),'diffuser',.012)
    for x in (-.59,.59): k.box('Luminaire_end_cap',(x,0,.055),(.055,.18,.11),'plastic',.007)
    for x in (-.42,.42):
        k.bar('Suspension_rod',(x,0,.1),(x,0,.25),.005)
        k.section('Diffuser_safety_clip',[(x,-.095,.06),(x,-.08,-.01),(x,.08,-.01),(x,.095,.06)],.0035,sides=8)


@model
def square_light():
    for x in (-.58,.58): k.box('Side_aluminium_profile',(x,0,.045),(.04,1.2,.09),'metal',.004)
    for y in (-.58,.58): k.box('End_aluminium_profile',(0,y,.045),(1.12,.04,.09),'metal',.004)
    for x in (-.58,.58): k.box('Side_recessed_diffuser',(x,0,-.003),(.023,1.12,.009),'diffuser',.002)
    for y in (-.58,.58): k.box('End_recessed_diffuser',(0,y,-.003),(1.12,.023,.009),'diffuser',.002)
    for x in (-.5,.5):
        for y in (-.5,.5):
            k.bar('Hanging_steel_wire',(x,y,.09),(x,y,.48),.0018,sides=8)
            k.cylinder('Cable_ceiling_anchor',(x,y,.49),.016,.025)


@model
def belt_post():
    k.lathe('Weighted_profiled_base',[(0,0),(.18,0),(.18,.022),(.172,.036),(.13,.052),(.04,.065),(.028,.09),(.028,.89),(0,.89)],role='metal',n=96)
    k.lathe('Rubber_base_ring',[(.145,0),(.175,0),(.177,.012),(.145,.012),(.145,0)],role='rubber',n=96)
    k.lathe('Retractable_belt_head',[(0,.87),(.045,.87),(.055,.9),(.055,.99),(.043,1.0),(0,1.0)],role='plastic')
    k.box('Belt_exit_slot',(0,-.055,.944),(.025,.006,.045),'interior',.003)
    k.box('Short_extracted_belt',(0,-.12,.945),(.003,.12,.043),'fabric',.001)
    k.box('Belt_attachment_clip',(0,-.187,.945),(.02,.018,.06),'plastic',.003)
