"""Current soft-S residential concept: editable top-view SVG, PNG and room data.

Documentation only. Floor 1 v01 accepted as a planning base on 2026-11-04.
The image retains the original proposal caption; JSON records the subsequent acceptance.
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


def generate():
    s=Sheet()
    s.text((60,30),'ЖИЛОЙ КОРПУС · СИЛУЭТ МЯГКОЙ S',42,bold=True)
    s.text((60,95),'ПЛАН ПЕРВОГО ЭТАЖА · ПРЕДЛОЖЕНИЕ v01 · 04.11.2026',25,'#b76635',True)
    s.text((60,143),'Форма и два корпуса приняты. Размеры, номерной фонд и детали холла — на оценку.',23)

    specs=[('Л',(0,-27.5),120,300),('П',(0,27.5),300,480)]
    types=[('single',10),('single',10),('double',14),('double',14),('triple',18),('double',14),
           ('suite',24),('double',14),('triple',18),('single',10),('double',14),('suite',20)]
    rooms=[]; corridors=[]; exits=[]
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
        ca0=90 if prefix=='Л' else 270; ca1=end
        corridor=sector(center,21,24,ca0,ca1)
        corridors.append({'wing':prefix,'center':center,'radii':[21,24],'angles':[ca0,ca1]})
        s.polygon([xy(*p) for p in corridor],'#efe3ac',INK,2)
        angle=start
        sequence=types if prefix=='Л' else list(reversed(types))
        for num,(kind,span) in enumerate(sequence,1):
            a,b=angle,angle+span; mid=(a+b)/2; ident=f'{prefix}{num:02}'
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
            s.text((label[0],label[1]-17),ident,21,INK,True,True)
            occupancy='ЛЮКС' if kind=='suite' else f'{BEDS[kind]} мест.'
            s.text((label[0],label[1]+10),occupancy,15,INK,False,True)
            angle=b
        assert abs(angle-end)<1e-8
        # End doors provide a garden loop on the ground floor, not a staircase at every end.
        exitpoint=polar(center,22.5,end)
        tip=polar(center,22.5,end+8)
        exits.append({'wing':prefix,'point':list(exitpoint),'type':'ground_floor_garden_exit'})
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
    a,b=xy(-10,-6);c,d=xy(-6,-4);s.rectangle((a,b,c,d),'#a88c69',INK,1)
    a,b=xy(6,-6);c,d=xy(10,-4);s.rectangle((a,b,c,d),'#a8bca5',INK,1)
    s.line([xy(12,-4.2),xy(12,-1.8)],'#d4e7ec',8)
    s.line([xy(12,-3),xy(21,-3)],'#438957',5)
    s.text(xy(22,-5),'Вход',21,'#438957',True)
    s.text(xy(22,-2.5),'1-го этажа',18,'#438957')

    # Separate schedule: colors describe room categories, never selected facade materials.
    x,y=1110,230
    s.text((x,y),'НОМЕРНОЙ ФОНД · НА ОЦЕНКУ',26,bold=True);y+=55
    for kind in ('single','double','triple','suite'):
        s.rectangle((x,y+4,x+28,y+28),PALETTE[kind],INK,1)
        s.text((x+42,y),NAMES[kind],24);y+=44
    s.text((x,y+10),'Цвета — категории, не отделка фасада.',20,'#6c7b71');y+=70
    s.text((x,y),'Крыло Л / крыло П',24,bold=True);y+=40
    for i in range(12):
        a=rooms[i];b=rooms[i+12]
        label=f"{a['id']} · {NAMES[a['type']]}     {b['id']} · {NAMES[b['type']]}"
        s.text((x,y),label,20);y+=34
    y+=35
    for text,size,bold in [
        ('24 номера на показанном этаже',25,True),
        ('46 гостевых мест — предложение',23,False),
        ('Верхние этажи будут отличаться.',22,False),
        ('Президентский люкс — отдельный',22,False),
        ('план верхнего этажа, ещё впереди.',22,False),
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
           'Служебные вертикальные связи',
           'верхних этажей проработать',
           'отдельно от центральной лестницы.']
    for i,text in enumerate(notes):
        s.text((x,y),text,23 if i==0 else 21,bold=i==0);y+=34

    s.text((90,1930),'0',22);s.line([(120,1915),(240,1915)],INK,5);s.text((225,1930),'10 м',22)
    s.text((390,1910),'Отдельные парковки и размещение второго S-корпуса — следующий план участка.',22)
    s.text((390,1950),'Типовой этаж не задаёт общую вместимость всего санатория. Материалы отложены.',22,'#a26537')

    # Validate topology and numeric program of this diagram only.
    assert len(rooms)==24 and sum(r['beds'] for r in rooms)==46
    assert rooms[0]['center'][1]<0<rooms[-1]['center'][1]
    for r in rooms:
        a,b=r['angles']; mid=(a+b)/2; cx,cy=r['center']; dx,dy=r['door_to_corridor']
        assert abs(math.hypot(dx-cx,dy-cy)-24)<1e-8
        assert b>a and r['area_game_m2']>0
    OUT.mkdir(parents=True,exist_ok=True)
    png=OUT/'residential_shell_s_floor_v01.png'; svg=OUT/'residential_shell_s_floor_v01.svg'
    s.im.save(png); svg.write_text('\n'.join(s.svg+['</svg>']),encoding='utf-8')
    data={'status':'accepted_as_planning_base','accepted_by_owner':'2026-11-04',
          'version':'v01','floor':1,'units':'game_metres_after_E',
          'building_count_approved':2,'form_approved':'soft_S_opposite_curves',
          'room_layout_proposed':False,
          'metric_dimensions_status':'working_values_pending_geometry_and_FPS_validation',
          'rooms':rooms,'corridors':corridors,
          'hall_polygon':hall,'stair':{'center':[0,-0.5],'outer_radius':3.8,'well_radius':0.9},
          'lifts':lifts,'main_ground_floor_entry':[12,-3],
          'ground_floor_exits':exits,'materials_status':'deferred_by_owner',
          'presidential_suite':'upper_floor_layout_pending'}
    out=ROOT/'docs/design/data/residential_shell_s_floor_v01.json'
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Validated: two opposite curves, 24 room sectors, 46 proposed beds, doors on corridor edge.')
    print(png);print(svg);print(out)


if __name__=='__main__':generate()
