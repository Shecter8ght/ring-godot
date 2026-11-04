"""Current soft-S residential concept: editable top-view SVG, PNG and room data.

Documentation only. v02 follows the owner's revision to three floors, ordinary rooms,
always-working lifts, end service stairs and technical roof access. Historical v01 is preserved.
Dimensions are working GAME metres after the E multiplier, pending geometry/FPS validation.
Run: python -X utf8 tools/shell_s_plan.py
"""
from pathlib import Path
import html
import json
import math
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/plans'
INK='#273e42'
PAPER='#f6f3e9'
PALETTE={'single':'#e6e1c7','double':'#c8dce3','triple':'#d1dfc0','suite':'#dec8d9'}
NAMES={'single':'1-местный','double':'2-местный','triple':'3-местный','suite':'Люкс · 2 места'}
BEDS={'single':1,'double':2,'triple':3,'suite':2}
OX,OY,SCALE=600,1020,12


def xy(x,y): return (OX+x*SCALE,OY+y*SCALE)


def polar(center,r,angle):
    a=math.radians(angle)
    return (center[0]+r*math.cos(a),center[1]+r*math.sin(a))


def arc(center,r,a0,a1):
    count=max(2,math.ceil(abs(a1-a0)*2))
    return [polar(center,r,a0+(a1-a0)*i/count) for i in range(count+1)]


def sector(center,rin,rout,a0,a1):
    return arc(center,rout,a0,a1)+arc(center,rin,a1,a0)


class Sheet:
    def __init__(self):
        self.im=Image.new('RGB',(1800,2050),PAPER); self.d=ImageDraw.Draw(self.im)
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="2050" viewBox="0 0 1800 2050"><rect width="1800" height="2050" fill="{PAPER}"/>']

    def polygon(self,points,fill,stroke=INK,width=2):
        points=[tuple(map(float,p)) for p in points]
        self.d.polygon(points,fill=fill)
        if stroke: self.d.line(points+[points[0]],fill=stroke,width=width,joint='curve')
        pts=' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
        self.svg.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>')

    def line(self,points,fill=INK,width=2):
        self.d.line(points,fill=fill,width=width,joint='curve')
        pts=' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
        self.svg.append(f'<polyline points="{pts}" fill="none" stroke="{fill}" stroke-width="{width}"/>')

    def text(self,at,text,size=24,fill=INK,bold=False,centre=False):
        f=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',size)
        x,y=at
        if centre: x-=self.d.textlength(text,font=f)/2
        self.d.text((x,y),text,font=f,fill=fill)
        self.svg.append(f'<text x="{x:.2f}" y="{y+size:.2f}" font-family="Arial,sans-serif" font-size="{size}" fill="{fill}" font-weight="{700 if bold else 400}">{html.escape(text)}</text>')

    def rectangle(self,box,fill,stroke=INK,width=2):
        a,b,c,d=box
        self.polygon([(a,b),(c,b),(c,d),(a,d)],fill,stroke,width)

    def circle(self,center,r,fill,stroke=INK,width=2):
        x,y=center
        self.d.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=stroke,width=width)
        self.svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>')


def generate(floor=1):
    s=Sheet()
    s.text((60,30),'ЖИЛОЙ КОРПУС · СИЛУЭТ МЯГКОЙ S',42,bold=True)
    s.text((60,95),f'ЭТАЖ {floor} ИЗ 3 · ПЛАНИРОВОЧНАЯ ВЕРСИЯ v02 · 04.11.2026',25,'#b76635',True)
    s.text((60,143),'Три этажа, работающие лифты и служебные лестницы приняты. Детали — рабочие.',23)

    specs=[('Л',(0,-27.5),120,300),('П',(0,27.5),300,480)]
    types=[('single',10),('single',10),('double',14),('double',14),('triple',18),('double',14),
           ('triple',18),('double',14),('triple',18),('single',10),('double',14),('double',14)]
    rooms=[]; corridors=[]; exits=[]; service_stairs=[]
    # The building contains only two oppositely opening annular wings. The central
    # hall joins their neck; it does not add a third arm or close either courtyard.
    for prefix,center,start,end in specs:
        s.circle(xy(*center),20*SCALE,'#e2e8d5',None)
        courtyard='ДВОР А' if prefix=='Л' else 'ДВОР Б'
        s.text(xy(center[0],center[1]-2),courtyard,26,'#5e795d',True,True)
        subtitle='открыт вправо →' if prefix=='Л' else '← открыт влево'
        s.text(xy(center[0],center[1]+1.5),subtitle,22,'#5e795d',False,True)

        # Exterior balcony strip and the inner curved corridor.
        s.polygon([xy(*p) for p in sector(center,32,33.8,start,end)],'#e7e3d7','#8b938a',2)
        stairs_start=end-12
        ca0=90 if prefix=='Л' else 270; ca1=stairs_start
        corridor=sector(center,21,24,ca0,ca1)
        corridors.append({'wing':prefix,'center':center,'radii':[21,24],'angles':[ca0,ca1]})
        s.polygon([xy(*p) for p in corridor],'#efe3ac',INK,2)
        angle=start
        sequence=types if prefix=='Л' else list(reversed(types))
        for num,(kind,span) in enumerate(sequence,1):
            a,b=angle,angle+span; mid=(a+b)/2; ident=f'{prefix}{floor}{num:02}'
            poly=sector(center,24,32,a,b)
            area=0.5*(32**2-24**2)*math.radians(span)
            door=polar(center,24,mid)
            rooms.append({'id':ident,'wing':prefix,'type':kind,'beds':BEDS[kind],
                          'center':list(center),'angles':[a,b],'radii':[24,32],
                          'area_game_m2':round(area,1),'area_nominal_m2':round(area/1.3**2,1),
                          'door_to_corridor':list(door),'door_clear_game_m':1.2})
            s.polygon([xy(*p) for p in poly],PALETTE[kind],INK,2)
            # Window segment and a visible door gap at the corridor edge.
            s.line([xy(*p) for p in arc(center,32,a+span*0.18,b-span*0.18)],'#548d9b',5)
            halfdoor=math.degrees(0.6/24)
            s.line([xy(*p) for p in arc(center,24,mid-halfdoor,mid+halfdoor)],'#efe3ac',6)
            s.circle(xy(*door),4,'#b86f3d',None)
            label=xy(*polar(center,28.2,mid))
            s.text((label[0],label[1]-17),ident,19,INK,True,True)
            occupancy='ЛЮКС' if kind=='suite' else f'{BEDS[kind]} мест.'
            s.text((label[0],label[1]+10),occupancy,15,INK,False,True)
            angle=b
        assert abs(angle-stairs_start)<1e-8
        # Reserve the last twelve degrees for an aligned service core on all floors.
        core_poly=sector(center,21,32,stairs_start,end)
        s.polygon([xy(*p) for p in core_poly],'#c5d5df',INK,3)
        stair_mid=(stairs_start+end)/2
        entry=polar(center,22.5,stairs_start)
        stair_id=f'{prefix}С{floor}'
        service_stairs.append({'id':stair_id,'wing':prefix,'center':center,
                              'radii':[21,32],'angles':[stairs_start,end],
                              'door_from_corridor':list(entry),'roof_access_proposed':True})
        # Two straight flights sit inside the annular service sector.
        a=math.radians(stair_mid); ur=(math.cos(a),math.sin(a)); ut=(-math.sin(a),math.cos(a))
        def local(r,t):return (center[0]+ur[0]*r+ut[0]*t,center[1]+ur[1]*r+ut[1]*t)
        for lo,hi in [(-1.6,-0.1),(0.1,1.6)]:
            s.polygon([xy(*local(r,t)) for r,t in [(23,lo),(26,lo),(26,hi),(23,hi)]],
                      '#e3ebec','#6a8189',1)
            for step in range(11):
                r=23+step*0.3;s.line([xy(*local(r,lo)),xy(*local(r,hi))],'#6a8189',1)
        label=xy(*polar(center,29.4,stair_mid))
        s.text((label[0],label[1]-13),f'{prefix}С',20,INK,True,True)
        s.circle(xy(*entry),5,'#b86f3d',None)
        exitpoint=polar(center,22.5,end)
        tip=polar(center,22.5,end+8)
        if floor==1:
            exits.append({'wing':prefix,'point':list(exitpoint),'type':'service_stair_garden_exit'})
            s.line([xy(*exitpoint),xy(*tip)],'#559163',6)
            q=xy(*tip); s.circle(q,7,'#559163',None)

    # Central shared hall covers only the two corridor necks; rooms stay outside it.
    hall=[(-12,-10),(12,-10),(12,10),(-12,10)]
    s.polygon([xy(*p) for p in hall],'#d4e7ec',INK,3)
    # Restore two open corridor connections rather than drawing an enclosing wall.
    s.line([xy(-12,-9.3),xy(-12,-6.5)],'#efe3ac',8)
    s.line([xy(12,6.5),xy(12,9.3)],'#efe3ac',8)
    s.text(xy(0,-9),'ОБЩИЙ ХОЛЛ',24,INK,True,True)

    # Helical stair: proposal 7.6 m diameter, with a clear central well.
    stair=xy(0,-0.5); s.circle(stair,3.8*SCALE,'#eff3f0',INK,2)
    s.circle(stair,0.9*SCALE,'#a6bfc4',INK,2)
    for i in range(22):
        a=math.radians(i*360/22)
        s.line([(stair[0]+0.9*SCALE*math.cos(a),stair[1]+0.9*SCALE*math.sin(a)),
                (stair[0]+3.8*SCALE*math.cos(a),stair[1]+3.8*SCALE*math.sin(a))],'#6f8990',1)
    s.text(xy(0,3.9),'лестница',17,INK,False,True)
    lifts=[]
    for n,x in enumerate((-8,8),1):
        rect=[x-1.5,4,x+1.5,7.5]; lifts.append({'id':f'LIFT{n}','rect':rect})
        a,b=xy(rect[0],rect[1]); c,d=xy(rect[2],rect[3])
        s.rectangle((a,b,c,d),'#b4c6ce',INK,2)
        s.text((a+4,b+8),f'Л{n}',18,INK,True)
        s.line([xy(x-0.7,4),xy(x+0.7,4)],'#d4e7ec',5)
    # Reception and waiting belong to the ground-floor concept only.
    a,b=xy(-10,-6);c,d=xy(-6,-4);s.rectangle((a,b,c,d),'#a88c69' if floor==1 else '#a8bca5',INK,1)
    a,b=xy(6,-6);c,d=xy(10,-4);s.rectangle((a,b,c,d),'#a8bca5',INK,1)
    if floor==1:
        s.line([xy(12,-4.2),xy(12,-1.8)],'#d4e7ec',8)
        s.line([xy(12,-3),xy(21,-3)],'#438957',5)
        s.text(xy(22,-5),'Вход',21,'#438957',True)
        s.text(xy(22,-2.5),'1-го этажа',18,'#438957')

    # Separate schedule: colors describe room categories, never selected facade materials.
    x,y=1110,230
    s.text((x,y),'НОМЕРНОЙ ФОНД · НА ОЦЕНКУ',26,bold=True);y+=55
    for kind in ('single','double','triple'):
        s.rectangle((x,y+4,x+28,y+28),PALETTE[kind],INK,1)
        s.text((x+42,y),NAMES[kind],24);y+=44
    s.rectangle((x,y+4,x+28,y+28),'#c5d5df',INK,1)
    s.text((x+42,y),'ЛС / ПС — служебные лестницы',23);y+=44
    s.text((x,y+10),'Цвета — категории, не отделка фасада.',20,'#6c7b71');y+=70
    s.text((x,y),'Крыло Л / крыло П',24,bold=True);y+=40
    for i in range(12):
        a=rooms[i];b=rooms[i+12]
        label=f"{a['id']} · {NAMES[a['type']]}     {b['id']} · {NAMES[b['type']]}"
        s.text((x,y),label,20);y+=34
    y+=35
    for text,size,bold in [
        ('24 номера на показанном этаже',25,True),
        ('48 гостевых мест — рабочий расчёт',23,False),
        ('Все 3 этажа с обычными номерами.',22,False),
        ('Лифты работают постоянно.',22,False),
        ('Президентского люкса нет.',22,False),
    ]:
        s.text((x,y),text,size,bold=bold);y+=37
    y+=25
    notes=['РАЗМЕРЫ · ИГРОВЫЕ МЕТРЫ',
           'Коридор: ширина 3,0 м.',
           'Номерная полоса: глубина 8,0 м.',
           'Центральный холл: 24 × 20 м.',
           'Винтовая лестница: Ø7,6 м.',
           'Лифты: две зоны 3 × 3,5 м.',
           'Все размеры пока предложены.',
           '',
           'Санузлы, прихожие и мебель',
           'ещё нужно разложить внутри',
           'каждой номерной ячейки.',
           '',
           'ЛС и ПС связывают 1–3 этажи.',
           'Выходы из них на крышу —',
           'предложение конкретного доступа.']
    for i,text in enumerate(notes):
        s.text((x,y),text,23 if i==0 else 21,bold=i==0);y+=34

    s.text((90,1930),'0',22);s.line([(120,1915),(240,1915)],INK,5);s.text((225,1930),'10 м',22)
    s.text((390,1910),'Отдельные парковки и размещение второго S-корпуса — следующий план участка.',22)
    s.text((390,1950),'72 номера / 144 места в корпусе — расчёт одинакового фонда 3 этажей, не финальная приёмка.',20,'#a26537')

    # Validate topology and numeric program of this diagram only.
    assert len(rooms)==24 and sum(r['beds'] for r in rooms)==48
    assert rooms[0]['center'][1]<0<rooms[-1]['center'][1]
    for r in rooms:
        a,b=r['angles']; mid=(a+b)/2; cx,cy=r['center']; dx,dy=r['door_to_corridor']
        assert abs(math.hypot(dx-cx,dy-cy)-24)<1e-8
        assert b>a and r['area_game_m2']>0
    OUT.mkdir(parents=True,exist_ok=True)
    png=OUT/f'residential_shell_s_floor_{floor}_v02.png'; svg=OUT/f'residential_shell_s_floor_{floor}_v02.svg'
    s.im.save(png); svg.write_text('\n'.join(s.svg+['</svg>']),encoding='utf-8')
    data={'status':'revised_planning_proposal_under_approved_constraints',
          'approved_constraints_date':'2026-11-04',
          'version':'v02','floor':floor,'storeys':3,'units':'game_metres_after_E',
          'building_count_approved':2,'form_approved':'soft_S_opposite_curves',
          'room_layout_proposed':True,
          'metric_dimensions_status':'working_values_pending_geometry_and_FPS_validation',
          'rooms':rooms,'corridors':corridors,
          'hall_polygon':hall,'stair':{'center':[0,-0.5],'outer_radius':3.8,'well_radius':0.9},
          'lifts':lifts,'lift_operation':'always_operational','lift_stops':[1,2,3],
          'main_ground_floor_entry':[12,-3] if floor==1 else None,
          'service_stairs':service_stairs,
          'ground_floor_exits':exits,'materials_status':'deferred_by_owner',
          'presidential_suite':'cancelled_by_owner','roof_access_required':True}
    out=ROOT/f'docs/design/data/residential_shell_s_floor_{floor}_v02.json'
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Floor {floor}: two opposite curves, 24 ordinary rooms / 48 proposed beds, two service cores.')
    print(png);print(svg);print(out)
    return data


def generate_roof(floors):
    s=Sheet()
    s.text((60,30),'S-КОРПУС · ТЕХНИЧЕСКАЯ КРЫША И СВЯЗИ',40,bold=True)
    s.text((60,95),'3 ЖИЛЫХ ЭТАЖА · БЕЗ ПРЕЗИДЕНТСКОГО ЛЮКСА · v02',25,'#b76635',True)
    s.text((60,143),'Доступ на крышу принят. Два выхода и маршрут между ними — планировочное предложение.',23)
    for prefix,center,start,end in [('Л',(0,-27.5),120,300),('П',(0,27.5),300,480)]:
        s.circle(xy(*center),20*SCALE,'#e2e8d5',None)
        s.text(xy(0,center[1]-1.5),'ДВОР '+('А' if prefix=='Л' else 'Б'),25,'#5e795d',True,True)
        s.polygon([xy(*p) for p in sector(center,21,33.8,start,end)],'#d7d9d1',INK,2)
        neck0=90 if prefix=='Л' else 270
        s.polygon([xy(*p) for p in sector(center,21,24,neck0,start)],'#d7d9d1',INK,2)
        s.polygon([xy(*p) for p in sector(center,21.5,31.5,end-11.5,end-0.5)],'#b9cfd9',INK,2)
        label=xy(*polar(center,29,end-6));s.text((label[0],label[1]-12),prefix+'С',22,INK,True,True)
        angles=(155,205,250) if prefix=='Л' else (335,385,430)
        for angle in angles:
            p=polar(center,29.6,angle); a,b=xy(p[0]-1.3,p[1]-1.1);c,d=xy(p[0]+1.3,p[1]+1.1)
            s.rectangle((a,b,c,d),'#adb9b3','#738079',1)
    s.polygon([xy(*p) for p in [(-12,-10),(12,-10),(12,10),(-12,10)]],'#d7d9d1',INK,3)
    for x in (-8,8):
        a,b=xy(x-1.5,4);c,d=xy(x+1.5,7.5);s.rectangle((a,b,c,d),'#b5beb8',INK,1)
    # Walkable roof route is a planning path, not painted wayfinding in the final asset.
    path=arc((0,-27.5),26,294,120)+[(-9,-5),(0,-5),(8,5)]+arc((0,27.5),26,300,474)
    s.line([xy(*p) for p in path],'#c17b36',5)
    for p in (path[0],path[-1]):s.circle(xy(*p),8,'#c17b36',None)
    s.text(xy(0,-2),'КРЫША ХОЛЛА',19,INK,True,True)

    x=1110;s.text((x,235),'СХЕМА ВЕРТИКАЛЬНЫХ СВЯЗЕЙ',25,bold=True)
    columns={'ЛС':1145,'Центр':1320,'Лифты':1480,'ПС':1660}
    yy={0:430,3:630,2:830,1:1030}
    for label,cx in columns.items():s.text((cx,335),label,22,bold=True,centre=True)
    for level in (3,2,1):
        y=yy[level];s.line([(1120,y),(1700,y)],'#b1bdb3',6)
        s.text((1120,y-55),f'{level} этаж',23,bold=True)
    for label in ('ЛС','ПС'):
        cx=columns[label];s.line([(cx,yy[0]),(cx,yy[1])],'#577b8d',5)
        for level in (0,1,2,3):s.circle((cx,yy[level]),10,'#b9cfd9',INK,1)
    for label in ('Центр','Лифты'):
        cx=columns[label];s.line([(cx,yy[3]),(cx,yy[1])],'#577b8d',5)
        for level in (1,2,3):s.circle((cx,yy[level]),10,'#d7e7ea',INK,1)
    s.line([(columns['ЛС'],yy[0]),(columns['ПС'],yy[0])],'#c17b36',5)
    s.text((1120,yy[0]-55),'Техническая крыша',23,bold=True)
    notes=[
        'ЛС / ПС: служебные лестницы.',
        'Центр: основная винтовая лестница.',
        'Лифты: постоянно работают на 1–3.',
        'Пассажирской остановки на крыше нет.',
        '',
        'Два технических выхода на крышу',
        'предлагаются для сквозного обхода.',
        'Оранжевая линия — маршрут на схеме,',
        'не обязательная разметка кровли.',
        '',
        'Кровля с парапетом и техоборудованием.',
        'Точные ограждения, двери, высоты',
        'и проходы ещё детализируются.',
        '',
        'На крыше нет номеров и люксов.',
        'Лестничные надстройки — технические,',
        'не четвёртый жилой этаж.'
    ]
    y=1130
    for line in notes:s.text((x,y),line,22);y+=36
    s.text((390,1910),'Схема движения: 1–3 этажи связаны тремя лестницами и двумя работающими лифтами.',21)
    s.text((390,1950),'Материалы, оборудование кровли и точная конструкция лестниц ещё обсуждаются.',22,'#a26537')
    png=OUT/'residential_shell_s_roof_v02.png';svg=OUT/'residential_shell_s_roof_v02.svg'
    s.im.save(png);svg.write_text('\n'.join(s.svg+['</svg>']),encoding='utf-8')

    # Connectivity audit of the design graph, including the proposed roof bypass.
    graph={}
    def edge(a,b):
        graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
    for f in floors:
        n=f['floor'];h=f'H{n}'
        for wing in ('Л','П'):
            c=f'C{wing}{n}';st=f'S{wing}{n}';edge(h,c);edge(c,st)
            for r in f['rooms']:
                if r['wing']==wing:edge(c,r['id'])
        for key in ('M','E1','E2'):edge(h,f'{key}{n}')
    for n in (1,2):
        for key in ('SЛ','SП','M','E1','E2'):edge(f'{key}{n}',f'{key}{n+1}')
    edge('SЛ3','RЛ');edge('RЛ','RП');edge('RП','SП3')
    def reachable(start,blocked=set()):
        seen={start};todo=[start]
        while todo:
            for nxt in graph[todo.pop()]-seen-blocked:seen.add(nxt);todo.append(nxt)
        return seen
    assert reachable('H1')==set(graph)
    # Both wings remain mutually accessible through service stairs and the roof
    # even when all three central halls are omitted from this abstract route audit.
    bypass=reachable('SЛ1',{'H1','H2','H3'})
    assert all(r['id'] in bypass for f in floors for r in f['rooms'])
    data={'version':'v02','storeys':3,'presidential_suite':'cancelled',
          'lift_operation':'always_operational','lift_stops':[1,2,3],
          'roof_is_technical':True,'roof_rooms':0,'roof_access_required':True,
          'two_roof_accesses_status':'proposal','proposed_access_stairs':['ЛС','ПС'],
          'route_graph':{key:sorted(v) for key,v in graph.items()},
          'validation':'all rooms reachable; proposed roof bypass connects wings without central halls',
          'capacity_working':{'rooms_per_floor':24,'beds_per_floor':48,'rooms_per_building':72,
                              'beds_per_building':144,'beds_two_buildings':288}}
    out=ROOT/'docs/design/data/residential_shell_s_vertical_v02.json'
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Validated: connected floor/roof graph; proposed roof bypass works without central hall nodes.')
    print(png);print(svg);print(out)


if __name__=='__main__':
    floors=[generate(n) for n in (1,2,3)]
    for a,b in zip(floors,floors[1:]):
        assert a['hall_polygon']==b['hall_polygon']
        assert a['stair']==b['stair'] and a['lifts']==b['lifts']
        for sa,sb in zip(a['service_stairs'],b['service_stairs']):
            assert sa['center']==sb['center'] and sa['angles']==sb['angles'] and sa['radii']==sb['radii']
    assert sum(sum(r['beds'] for r in f['rooms']) for f in floors)==144
    print('Validated: all vertical cores align across three floors; 144 proposed beds per building.')
    generate_roof(floors)
