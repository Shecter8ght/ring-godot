"""Банкомат, бункер и ларёк: видимые узлы строятся по сохранённым фото."""
import math
from math import pi,sin,cos
from mathutils import Matrix,Vector
from common import k,boolean,rounded_panel,rounded_opening,sheet,ring_rect,tube_rect,shell_loft


def atm():
    # NCR SelfServ 22e, CEN-I front access: 450 × 784 × 1412 мм.
    # Номера производителя используются только в карточке источника.
    front,rear=-.376,.353
    for x in (-.222,.222):
        k.box('Safe_structural_side',(x,(front+rear)/2,.47),(.006,rear-front,.94),'paint',.001)
        k.box('Upper_sheet_side',(x,.017,1.167),(.006,.672,.47),'paint',.001)
    k.box('Rear_steel_panel',(0,rear-.003,.707),(.438,.006,1.41),'paint',.002)
    for z in (.008,.838,1.405): k.box('Steel_cross_plate',(0,-.005,z),(.438,.704,.012),'metal',.001)
    k.box('Recessed_base_plinth',(0,-.01,.025),(.43,.70,.05),'interior',.004)
    # Фасонная пластиковая фасция с действительными нишами.
    fascia=rounded_panel('Moulded_fascia_outer',.45,.59,.048,(0,-.371,1.117),'plastic',.012,.001)
    rounded_opening(fascia,'Display_recess',.411,.277,(0,-.39,1.201),.15,.012)
    rounded_opening(fascia,'Keypad_privacy_well',.16,.157,(0,-.393,.96),.15,.003)
    rounded_opening(fascia,'Receipt_pocket',.079,.042,(-.15,-.39,.923),.15,.004)
    # Широкое чёрное поле дисплея сидит внутри скруглённой рамки.
    rounded_panel('Display_module_back',.403,.269,.012,(0,-.351,1.201),'interior',.01,.0005)
    rounded_panel('Display_glass',.305,.229,.004,(0,-.361,1.201),'screen',.004,.0003)
    for side in (-1,1):
        for z in (1.119,1.159,1.199,1.239):
            k.lathe('Function_key_escutcheon',[(0,-.003),(.0095,-.003),(.01,.002),(.008,.006),(0,.006)],(side*.185,-.367,z),'Y','chrome',32)
        k.box('Display_side_shadow',(side*.166,-.365,1.201),(.003,.003,.223),'interior',.0003)
    rounded_panel('Top_advert_insert',.412,.048,.005,(0,-.399,1.367),'interior',.006,.0003)
    k.cylinder('Camera_lens',(0,-.404,1.367),.009,.005,'glass','Y',48)
    k.ring('Camera_bezel',(0,-.405,1.367),.011,.0012,'metal','Y',48)
    # Клавиатура стоит на наклонном дне углубления, а не на внешней полке.
    y0,y1=-.411,-.326
    z0,z1=.891,.931
    sheet('Keypad_recess_floor',[(-.075,y0,z0),(.075,y0,z0),(.075,y1,z1),(-.075,y1,z1)],'metal',.004)
    for x in (-.077,.077):
        k.extrude('Moulded_keypad_privacy_wing',[(y0,.887),(y0,1.018),(y1,1.038),(y1,.925)],'X',x-.005,x+.005,'plastic',.001)
    k.box('Keypad_top_wall',(0,y1,.978),(.15,.012,.112),'plastic',.001)
    for row in range(4):
        for col in range(3):
            x=-.048+col*.033; y=y0+.012+row*.018
            z=z0+(y-y0)/(y1-y0)*(z1-z0)+.005
            ob=k.box('Recessed_numeric_key',(x,y,z),(.026,.013,.006),'metal',.0015)
            pivot=Vector((x,y,z))
            ob.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(math.atan2(z1-z0,y1-y0),4,'X')@Matrix.Translation(-pivot)
        y=y0+.012+row*.018; z=z0+(y-y0)/(y1-y0)*(z1-z0)+.005
        ob=k.box('Recessed_function_key',(.053,y,z),(.026,.013,.006),'plastic',.0015)
        pivot=Vector((.053,y,z))
        ob.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(math.atan2(z1-z0,y1-y0),4,'X')@Matrix.Translation(-pivot)
    # Круглый ввод карты со щелью, защитным носиком и отдельным световым кольцом.
    k.lathe('Card_reader_socket',[(0,-.012),(.047,-.012),(.049,0),(.046,.013),(.035,.018),(0,.018)],(.15,-.395,.977),'Y','plastic',64)
    k.ring('Card_entry_indicator',(.15,-.416,.977),.034,.003,'diffuser','Y',64)
    reader=rounded_panel('Card_reader_nose',.069,.039,.029,(.15,-.415,.974),'plastic',.008,.001)
    rounded_opening(reader,'Real_card_insertion_slot',.052,.0065,(.15,-.426,.977),.08,.0015)
    k.box('Card_channel_dark_interior',(.15,-.389,.977),(.051,.005,.006),'interior',.0005)
    rounded_panel('Card_reader_lower_key_panel',.063,.019,.004,(.15,-.401,.865),'metal',.008,.0005)
    k.cylinder('Reader_key_access',(.136,-.405,.865),.006,.004,'interior','Y',24)
    # Выдача чека: небольшой карман с глубиной и козырьком.
    k.box('Receipt_pocket_rear',(-.15,-.35,.923),(.076,.004,.038),'interior',.002)
    k.box('Receipt_output_lip',(-.15,-.399,.902),(.083,.026,.006),'plastic',.001)
    k.lathe('Receipt_arch_shadow',[(0,-.003),(.018,-.003),(.018,.003),(0,.003)],(-.15,-.397,.954),'Y','interior',48)
    # Самостоятельный модуль выдачи купюр; прорезь открыта внутрь.
    cash=rounded_panel('Cash_presenter_front',.448,.164,.035,(0,-.371,.735),'paint',.006,.001)
    rounded_opening(cash,'Cash_delivery_pocket',.205,.047,(0,-.388,.74),.12,.002)
    k.box('Cash_delivery_dark_back',(0,-.335,.742),(.201,.005,.043),'interior',.001)
    k.box('Cash_presenter_lower_lip',(0,-.394,.716),(.208,.035,.006),'metal',.001)
    for i in range(14): k.box('Cash_shutter_vertical_segment',(-.094+i*.0145,-.365,.741),(.013,.007,.027),'metal',.0007)
    # Сейфовая дверь со скруглением нижних углов и зазором по периметру.
    profile=[(-.204,.11),(-.205,.64),(.205,.64),(.204,.11),(.194,.074),(.176,.063),(-.176,.063),(-.194,.074)]
    door=k.extrude('Safe_front_door',profile,'Y',-.385,-.367,'paint',.003)
    k.cylinder('Safe_key_cylinder',(-.17,-.39,.488),.008,.009,'chrome','Y',32)
    k.box('Safe_key_slot',(-.17,-.396,.488),(.002,.003,.007),'interior',.0002)
    for z in (.18,.56): k.cylinder('Concealed_safe_hinge',(.213,-.36,z),.006,.065,'metal')
    # Задняя крышка, точки крепежа и ввод кабеля — конструктивная реконструкция.
    rounded_panel('Rear_service_cover',.356,.44,.004,(0,.357,1.105),'paint',.007,.001)
    for x in (-.156,.156):
        for z in (.91,1.30): k.bolt('Rear_cover_fastener',(x,.361,z),'Y',.003)
    for x in (-.08,.08): k.cylinder('Rear_cable_grommet',(x,.359,.08),.016,.012,'rubber','Y',32)


def dumpster():
    # Бункер РостМеталл 1408, открытый вариант: 3300 × 1900 × 1420 мм.
    # Узлы и наклонные стенки сверены с реальными ref_02/ref_03.
    rings=[]
    for z,l,w in [(.095,2.37,1.28),(.655,3.27,1.89),(1.383,3.27,1.89)]:
        pts=k.rounded_rect(l,w,.018,2)
        rings.append([(x,y,z) for x,y in pts])
    body=shell_loft('Tapered_skip_steel_shell',rings,'paint',False,False,0)
    solid=body.modifiers.new('3 mm physical sheet, open mouth','SOLIDIFY'); solid.thickness=.003; solid.offset=-1
    # Дно — отдельный лист, его край заведен под стенку.
    k.extrude('Welded_skip_floor',k.rounded_rect(2.37,1.28,.018,2),'Z',.089,.096,'paint',.0008)
    # Замкнутая полая рама верхнего пояса; четыре косых стыка.
    for y in (-.954,.954): tube_rect('Top_RHS_longitudinal',(-1.65,y,1.395),(1.65,y,1.395),.05,.05,.003,'paint')
    for x in (-1.625,1.625): tube_rect('Top_RHS_end',(x,-.93,1.395),(x,.93,1.395),.05,.05,.003,'paint')
    # Два продольных полоза, торцевые заглушки и опорные пятки.
    for y in (-.57,.57):
        tube_rect('Ground_runner',(-1.18,y,.048),(1.18,y,.048),.085,.095,.004,'paint')
        for x in (-1.15,1.15): k.box('Runner_end_closure',(x,y,.048),(.007,.085,.095),'paint',.001)
    # На фото верхняя стенка усилена вертикальными полосами и поясом у перелома.
    for side in (-1,1):
        y=side*.952
        for x in (-.91,.91):
            tube_rect('Upper_side_stiffener',(x,y,.668),(x,y,1.37),.035,.04,.003,'paint')
        tube_rect('Upper_side_lower_chord',(-1.57,y,.675),(1.57,y,.675),.04,.04,.003,'paint')
        # Четыре точки строповки с настоящим пальцем между косынками.
        for x in (-.99,.99):
            for dx in (-.047,.047):
                sheet('Lifting_pin_gusset',[(x+dx,y,.93),(x+dx,y,1.12),(x+dx,y+side*.105,.945)],'metal',.007,.0008)
            k.cylinder('Lifting_pin',(x,y+side*.074,.969),.022,.132,'metal','X',48)
            for dx in (-.07,.07): k.cylinder('Lifting_pin_retainer',(x+dx,y+side*.074,.969),.027,.009,'metal','X',32)
            k.bar('Lifting_bracket_weld',(x-.055,y+side*.004,.936),(x+.055,y+side*.004,.936),.0025,'metal',8)
        # Вертикальный шов листов и переход наклонной части.
        k.section('Side_sheet_butt_weld',[(0,side*.644,.10),(0,side*.949,.655),(0,side*.949,1.372)],.0018,'metal',8)
        for x in (-1.13,1.13):
            k.section('Bottom_corner_reinforcement',[(x,side*.647,.12),(x+math.copysign(.435,x),side*.944,.65)],.009,'paint',8)
    for x in (-1.642,1.642):
        tube_rect('End_wall_stiffening_chord',(x,-.88,.67),(x,.88,.67),.04,.04,.003,'paint')
    # Умеренная геометрия непрерывных сварных швов по углам; цвет/грязь ещё не делаются.
    for j in range(4):
        a=rings[0][j*3]; b=rings[1][j*3]
        k.bar('Corner_continuous_weld',a,b,.002,'metal',8)


def kiosk():
    # Наружная конструкция по Mobifood ref_08: металл, три секции окна,
    # маркиза с волнистым краем и фриз с приподнятым центром. Габарит оценочный.
    w,d,h=2.8,2.2,2.84
    for x in (-1.34,1.34):
        for y in (-1.04,1.04):
            tube_rect('Welded_corner_post',(x,y,.07),(x,y,2.82),.075,.075,.003)
            k.box('Adjustable_support_foot',(x,y,.035),(.16,.16,.07),'metal',.006)
    k.box('Insulated_floor',(0,0,.105),(2.72,2.12,.1),'metal',.006)
    k.box('Rear_insulated_wall',(0,1.08,1.48),(2.78,.04,2.7),'paint',.002)
    k.box('Left_insulated_wall',(-1.38,0,1.48),(.04,2.12,2.7),'paint',.002)
    k.box('Inner_ceiling',(0,0,2.79),(2.72,2.12,.035),'metal',.002)
    # Правая стенка вокруг отдельной служебной двери; проём E 1,17 × 2,42.
    k.box('Right_front_wall_return',(1.38,-.63,1.48),(.04,.86,2.7),'paint',.002)
    k.box('Right_rear_wall_return',(1.38,.995,1.48),(.04,.17,2.7),'paint',.002)
    k.box('Door_header_wall',(1.38,.38,2.7),(.04,1.17,.25),'paint',.002)
    k.box('Rear_service_door',(1.406,.38,1.345),(.035,1.15,2.39),'paint',.005)
    for y in (-.213,.973): k.box('Service_door_jamb',(1.43,y,1.355),(.05,.035,2.46),'metal',.002)
    for z in (.13,2.58): k.box('Service_door_transom',(1.43,.38,z),(.05,1.22,.035),'metal',.002)
    for z in (.45,1.42,2.29): k.cylinder('Door_external_hinge',(1.44,.91,z),.012,.095)
    k.box('Door_lock_backplate',(1.433,-.08,1.15),(.01,.045,.12),'metal',.004)
    k.section('Service_door_pull',[(1.44,-.08,1.1),(1.48,-.08,1.1),(1.48,-.08,1.24),(1.44,-.08,1.24)],.009)
    # Низ фасада и облицовка углов — отдельные панели с монтажными швами.
    k.box('Front_lower_sandwich_wall',(0,-1.08,.58),(2.72,.04,.9),'paint',.003)
    k.box('Recessed_front_ad_panel',(0,-1.108,.58),(2.36,.012,.73),'paint',.003)
    for x in (-1.31,1.31): k.box('Folded_corner_cladding',(x,-1.11,1.47),(.17,.055,2.72),'metal',.003)
    for x in (-1.32,1.32):
        for z in (.28,1.0,2.57): k.cylinder('Cladding_flush_rivet',(x,-1.142,z),.003,.002,'metal','Y',16)
    # Действительное окно, раздельные направляющие и сдвинутая центральная створка.
    bottom,top=1.075,2.35
    for x in (-1.19,1.19): tube_rect('Window_side_extrusion',(x,-1.098,bottom),(x,-1.098,top),.035,.045,.002)
    for z in (bottom,top): tube_rect('Window_horizontal_extrusion',(-1.2,-1.098,z),(1.2,-1.098,z),.035,.065,.002)
    for y in (-1.135,-1.098,-1.065):
        k.box('Window_slider_track',(0,y,1.09),(2.35,.008,.018),'metal',.001)
    for x,y in ((-.79,-1.115),(-.43,-1.075),(.79,-1.115)):
        # Средняя створка задвинута за левую; проём остаётся физически открытым.
        glassw=.765
        k.box('Sliding_window_glass',(x,y,1.73),(glassw,.006,1.205),'glass',.001)
        for dx in (-glassw/2,glassw/2): k.box('Slider_vertical_profile',(x+dx,y,1.73),(.018,.025,1.235),'metal',.001)
        for z in (1.113,2.347): k.box('Slider_cross_profile',(x,y,z),(glassw,.025,.018),'metal',.001)
    k.box('Slider_pull',(-.1,-1.145,1.54),(.013,.024,.16),'metal',.003)
    # Верхняя фрамуга и широкий покупательский прилавок с загибом торца.
    k.box('Upper_transom_glass',(0,-1.098,2.50),(2.33,.006,.25),'glass',.001)
    for z in (2.37,2.65): tube_rect('Upper_transom_rail',(-1.2,-1.098,z),(1.2,-1.098,z),.025,.035,.002)
    k.box('Customer_stainless_counter',(0,-1.18,1.057),(2.9,.38,.035),'metal',.006)
    k.box('Customer_counter_downstand',(0,-1.371,1.033),(2.89,.012,.038),'metal',.002)
    for z in (.952,.999): k.box('Narrow_timber_facing_strip',(0,-1.115,z),(2.36,.025,.038),'wood',.002)
    # Крышка, карниз и профильный фриз с центральным подъёмом.
    k.box('Weatherproof_flat_roof',(0,0,2.86),(3.0,2.4,.09),'metal',.008)
    for y in (-1.19,1.19): k.box('Roof_rolled_drip',(0,y,2.82),(3.02,.025,.06),'metal',.002)
    crest=[(-1.51,2.91),(-1.51,3.05),(-1.05,3.15),(-.63,3.28),(.63,3.28),(1.05,3.15),(1.51,3.05),(1.51,2.91)]
    k.extrude('Raised_centre_fascia',crest,'Y',-1.17,-1.11,'paint',.006)
    for x in (-1.48,1.48): k.box('Side_fascia',(x,0,3.0),(.05,2.3,.21),'paint',.004)
    k.lettering('Original_food_sign','ПЕРЕКУС',(0,-1.207,3.02),.18,role='metal')
    # Маркиза: настоящая оболочка и отдельный волнистый край, без рисунка ткани.
    for stripe in range(18):
        x0=-1.42+stripe*2.84/18; sw=2.84/18
        k.patch('Awning_fabric_panel',lambda u,v:(x0+sw*u,-1.18-.61*v,2.79-.13*v-.045*sin(pi*v)),4,20,'fabric',.002)
        k.patch('Scalloped_awning_valance',lambda u,v:(x0+sw*u,-1.793,2.65-v*(.09+.035*sin(pi*u))),8,4,'fabric',.002)
    k.bar('Awning_front_roller',(-1.44,-1.775,2.663),(1.44,-1.775,2.663),.013)
    for x in (-1.41,1.41):
        k.section('Awning_articulated_support',[(x,-1.13,2.12),(x,-1.45,2.28),(x,-1.77,2.64)],.012)
        for y,z in ((-1.13,2.12),(-1.45,2.28),(-1.77,2.64)): k.cylinder('Awning_pivot',(x,y,z),.018,.033,axis='X')
    # Внутренний прилавок читается через окно. Скрытая планировка реконструирована.
    k.box('Interior_stainless_worktop',(0,-.46,.96),(2.48,.75,.04),'metal',.004)
    for x in (-1.05,1.05):
        for y in (-.7,-.2): tube_rect('Worktop_leg',(x,y,.15),(x,y,.94),.035,.035,.002)
    k.box('Interior_rear_worktop',(0,.68,.96),(2.45,.57,.035),'metal',.004)
    k.box('Undercounter_refrigerator',(.78,.68,.55),(.67,.53,.77),'paint',.012)
    k.box('Refrigerator_door',(.78,.403,.55),(.62,.025,.69),'metal',.006)
    k.bar('Refrigerator_pull',(.99,.381,.55),(.99,.381,.77),.006)
    # Базовая витрина для еды — стеклянная крышка и металлический лоток.
    k.box('Food_display_tray',(-.68,-.56,1.005),(.63,.4,.03),'metal',.004)
    for x in (-.98,-.38): sheet('Food_display_end',[(x,-.76,1.02),(x,-.76,1.27),(x,-.36,1.35),(x,-.36,1.02)],'glass',.006)
    sheet('Food_display_sloping_glass',[(-.98,-.76,1.27),(-.38,-.76,1.27),(-.38,-.36,1.35),(-.98,-.36,1.35)],'glass',.006)
    # Технический вывод вытяжки — отдельный небольшой узел на крыше, без бренда.
    k.cylinder('Roof_vent_duct',(.67,.6,3.0),.085,.28,'metal')
    k.lathe('Rain_cap_vent',[(0,.0),(.12,.0),(.12,.02),(.045,.075),(0,.075)],(.67,.6,3.15),role='metal')
