"""ARCHIVED: generate the former rectangular sanatorium proposal for historical study.

Superseded by the owner's shell-shaped building concept on 2026-11-04.
Do not use these layouts or capacities as the current design; see mission_helicopter.md 6.6.

Design documentation only: this does not create levels or prescribe building compliance.
Coordinates are nominal architectural metres; game width/depth is x1.3 (AGENTS.md).
Run: python -X utf8 tools/sanatorium_layout.py
"""
from pathlib import Path
import json
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
PAPER = '#f5f1e6'
INK = '#253b34'
COLORS = {'room':'#e9dfc6','public':'#d9e7d0','service':'#d7d9d6',
          'medical':'#d4e5e5','corridor':'#f2e8bd','stairs':'#c5d8e5','gallery':'#e3eddd'}


def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',size)


def room(ident, name, rect, kind='room', beds=0):
    return dict(id=ident,name=name,rect=list(rect),kind=kind,beds=beds)


def main_floor(level):
    pre=f'M{level}'
    spaces=[]
    # All levels share two circulation strips and the same two stair positions.
    spaces += [room(pre+'-C','Внутренний поперечный коридор',(-42,9,42,13),'corridor'),
               room(pre+'-G','Открытая парадная галерея',(-42,24,42,28),'gallery'),
               room(pre+'-S1','Парадная лестница и холл',(-7,13,7,24),'stairs'),
               room(pre+'-S2','Служебная лестница и лифтовое ядро',(34,0,42,9),'stairs')]
    if level==1:
        back=[(-42,-28,'Приёмка продуктов и разгрузочная', 'service'),
              (-28,-18,'Холодная и сухая кладовые','service'),
              (-18,0,'Кухня: подготовка и горячий цех','service'),
              (0,12,'Моечная и раздаточная','service'),
              (12,24,'Раздевалки и бытовые персонала','service'),
              (24,34,'Пост охраны и служебный вход','service')]
        front=[(-42,-20,'Столовая на 128 посадочных мест','public'),
               (-20,-7,'Приёмная: стойка, багаж, ожидание','public'),
               (7,24,'Вестибюль и гостиная','public'),
               (24,34,'Дежурный медпункт','medical'),
               (34,42,'Общественные санузлы','service')]
    elif level==2:
        back=[(-42,-30,'Физиотерапия','medical'),(-30,-20,'Диагностика','medical'),
              (-20,-10,'Процедурная','medical'),(-10,0,'Медицинский склад','service'),
              (0,12,'Два кабинета врачей, внутренняя приёмная','medical'),
              (12,24,'Бытовые медперсонала','service'),(24,34,'Чистая бельевая','service')]
        front=[(-42,-20,'Зал лечебной физкультуры','medical'),
               (-20,-7,'Кабинеты консультаций','medical'),
               (7,24,'Ожидание и галерея отдыха','public'),
               (24,34,'Массажные кабинеты','medical'),(34,42,'Общественные санузлы','service')]
    else:
        back=[(-42,-32,'Кабинет директора','service'),(-32,-22,'Бухгалтерия','service'),
              (-22,-12,'Архив и делопроизводство','service'),
              (-12,0,'Кабинет администрации','service'),(0,12,'Бильярдная','public'),
              (12,22,'Настольные игры','public'),(22,34,'Кладовая зала и персонала','service')]
        front=[(-42,-20,'Библиотека и читальный зал','public'),
               (-20,-7,'Тихая гостиная','public'),(7,24,'Зал собраний / кинопоказов','public'),
               (24,34,'Клубная комната','public'),(34,42,'Общественные санузлы','service')]
    for n,(a,b,name,kind) in enumerate(back,1):
        spaces.append(room(f'{pre}-B{n:02}',name,(a,0,b,9),kind))
    for n,(a,b,name,kind) in enumerate(front,1):
        spaces.append(room(f'{pre}-F{n:02}',name,(a,13,b,24),kind))
    # Every room has a door to a real adjacent circulation area. Front rooms also
    # reach the open gallery, providing a separate continuous circulation loop.
    links=[]
    for r in spaces:
        a,b,c,d=r['rect']; ident=r['id']
        if '-B' in ident:
            links.append(dict(a=ident,b=pre+'-C',door=[(a+c)/2,9]))
        elif '-F' in ident:
            links += [dict(a=ident,b=pre+'-C',door=[(a+c)/2,13]),
                      dict(a=ident,b=pre+'-G',door=[(a+c)/2,24])]
    links += [dict(a=pre+'-C',b=pre+'-S1',door=[0,13]),
              dict(a=pre+'-G',b=pre+'-S1',door=[0,24]),
              dict(a=pre+'-C',b=pre+'-S2',door=[38,9])]
    screens=[dict(x=-14,y0=9,y1=13,door_y=10,clear=1.5),
             dict(x=18,y0=9,y1=13,door_y=12,clear=1.5)]
    outside=[]
    if level==1:
        outside=[dict(space=pre+'-G',door=[0,28],purpose='Главный вход с парадной площади'),
                 dict(space=pre+'-G',door=[-39,28],purpose='Западный выход в парк'),
                 dict(space=pre+'-G',door=[39,28],purpose='Восточный выход в парк'),
                 dict(space=pre+'-B06',door=[29,0],purpose='Вход персонала'),
                 dict(space=pre+'-B01',door=[-35,0],purpose='Разгрузка'),
                 dict(space=pre+'-S2',door=[42,5],purpose='Служебный лестничный вход')]
    return dict(id=pre,building='M',level=level,bounds=[-42,0,42,28],spaces=spaces,links=links,
                corridor_screens=screens,exterior_doors=outside)


def residential_floor(building,level):
    pre=f'{building}{level}'
    spaces=[room(pre+'-C','Общий коридор',(-16,8,16,12),'corridor'),
            room(pre+'-G','Общая открытая галерея',(-16,20,16,22),'gallery'),
            room(pre+'-S1','Парадная лестница и этажный холл',(-21,0,-16,22),'stairs'),
            room(pre+'-S2','Служебная лестница, лифт, бельевая',(16,0,21,22),'stairs')]
    links=[dict(a=pre+'-C',b=pre+'-S1',door=[-16,10]),
           dict(a=pre+'-C',b=pre+'-S2',door=[16,10]),
           dict(a=pre+'-G',b=pre+'-S1',door=[-16,21]),
           dict(a=pre+'-G',b=pre+'-S2',door=[16,21])]
    for side,(y0,y1,door_y) in enumerate([(0,8,8),(12,20,12)]):
        for bay in range(6):
            a=-16+bay*32/6; c=-16+(bay+1)*32/6
            number=side*6+bay+1; ident=f'{building}{level}{number:02}'
            name='Двухместный номер, санузел и прихожая'
            spaces.append(room(ident,name,(a,y0,c,y1),'room',2))
            links.append(dict(a=ident,b=pre+'-C',door=[(a+c)/2,door_y]))
    screens=[dict(x=-5,y0=8,y1=12,door_y=9,clear=1.5),
             dict(x=5,y0=8,y1=12,door_y=11,clear=1.5)]
    outside=[]
    if level==1:
        outside=[dict(space=pre+'-S1',door=[-21,10],purpose='Парадный вход'),
                 dict(space=pre+'-S2',door=[21,10],purpose='Служебный вход'),
                 dict(space=pre+'-G',door=[-12,22],purpose='Выход в сад'),
                 dict(space=pre+'-G',door=[12,22],purpose='Выход к лестницам парка')]
    if building=='B':
        for r in spaces:
            a,b,c,d=r['rect']; r['rect']=[-c,b,-a,d]
        for edge in links: edge['door'][0]*=-1
        for screen in screens: screen['x']*=-1
        for edge in outside: edge['door'][0]*=-1
    return dict(id=pre,building=building,level=level,bounds=[-21,0,21,22],spaces=spaces,links=links,
                corridor_screens=screens,exterior_doors=outside)


def validate(floors):
    """Check proposal geometry and circulation; this is not a game/navmesh test."""
    nodes={}; graph={}
    for floor in floors:
        local={r['id']:r for r in floor['spaces']}
        assert len(local)==len(floor['spaces'])
        nodes.update(local)
        for ident in local: graph[ident]=set()
        for i,a in enumerate(floor['spaces']):
            x0,y0,x1,y1=a['rect']; assert x1>x0 and y1>y0
            for b in floor['spaces'][i+1:]:
                u0,v0,u1,v1=b['rect']
                assert min(x1,u1)-max(x0,u0)<=1e-6 or min(y1,v1)-max(y0,v0)<=1e-6,(a['id'],b['id'])
        for edge in floor['links']:
            a,b=local[edge['a']],local[edge['b']]; x,y=edge['door']
            for r in (a,b):
                x0,y0,x1,y1=r['rect']
                assert x0-1e-6<=x<=x1+1e-6 and y0-1e-6<=y<=y1+1e-6
                assert min(abs(x-x0),abs(x-x1),abs(y-y0),abs(y-y1))<1e-6
            graph[a['id']].add(b['id']); graph[b['id']].add(a['id'])
        for screen in floor['corridor_screens']:
            assert screen['clear']>0
            assert screen['door_y']-screen['clear']/2>=screen['y0']
            assert screen['door_y']+screen['clear']/2<=screen['y1']
        for edge in floor['exterior_doors']:
            r=local[edge['space']]; x,y=edge['door']; a,b,c,d=r['rect']
            assert a<=x<=c and b<=y<=d
            assert min(abs(x-a),abs(x-c),abs(y-b),abs(y-d))<1e-6
    for building,count in [('M',3),('A',4),('B',4)]:
        for level in range(1,count):
            for stair in ('S1','S2'):
                a=f'{building}{level}-{stair}'; b=f'{building}{level+1}-{stair}'
                assert nodes[a]['rect']==nodes[b]['rect']
                graph[a].add(b); graph[b].add(a)
        entrances=next(f for f in floors if f['building']==building and f['level']==1)['exterior_doors']
        assert len(entrances)>=2
        start=entrances[0]['space']; seen={start}; todo=[start]
        while todo:
            for nxt in graph[todo.pop()]-seen:
                seen.add(nxt); todo.append(nxt)
        expected={n for n in nodes if n.startswith(building)}
        assert seen==expected,(building,expected-seen)
    assert sum(r['beds'] for f in floors for r in f['spaces'])==192
    print(f'Validated: {len(nodes)} spaces; 192 beds; no overlaps; aligned stairs; all spaces reachable.')


def draw_floor(draw,floor,origin,scale):
    bx,by=origin; bound_x,bound_y,_,_=floor['bounds']
    def p(x,y): return (round(bx+(x-bound_x)*scale),round(by+(y-bound_y)*scale))
    for r in floor['spaces']:
        a,b,c,d=r['rect']; aa,bb=p(a,b); cc,dd=p(c,d)
        draw.rectangle((aa,bb,cc,dd),fill=COLORS[r['kind']],outline=INK,width=2)
        short=r['id'].split('-',1)[-1] if '-' in r['id'] else r['id']
        if r['kind']!='room':
            draw.text((aa+6,bb+7),short,font=font(18,True),fill=INK)
        if r['kind']=='room':
            # Sanitary enclosure is a room subzone; it does not create another bed.
            dy= d-2.4 if b==0 else b
            q=p(a,dy); t=p(a+2.2,dy+2.4)
            draw.rectangle((*q,*t),outline='#638d91',width=2)
            label_y=bb+7 if b==0 else bb+68
            draw.text((aa+6,label_y),short,font=font(18,True),fill=INK)
            draw.text((aa+7,label_y+29),'2 места',font=font(15),fill='#52675f')
        if r['kind']=='stairs':
            mid=(aa+cc)/2
            for yy in range(bb+40,min(dd-5,bb+145),9): draw.line((mid-12,yy,mid+12,yy),fill='#55768a',width=2)
    for e in floor['links']:
        xx,yy=p(*e['door'])
        draw.ellipse((xx-4,yy-4,xx+4,yy+4),fill='#be6b37',outline=PAPER,width=1)
    for screen in floor['corridor_screens']:
        x,y0,y1=screen['x'],screen['y0'],screen['y1']
        low=screen['door_y']-screen['clear']/2; high=screen['door_y']+screen['clear']/2
        draw.line([p(x,y0),p(x,low)],fill=INK,width=4)
        draw.line([p(x,high),p(x,y1)],fill=INK,width=4)
    for edge in floor['exterior_doors']:
        xx,yy=p(*edge['door'])
        draw.rectangle((xx-5,yy-5,xx+5,yy+5),fill='#4e8b59',outline=PAPER,width=1)


def diagram_main(floors):
    im=Image.new('RGB',(1800,1720),PAPER); d=ImageDraw.Draw(im)
    d.text((50,25),'САНАТОРИЙ · ГЛАВНЫЙ КОРПУС · 3 ЭТАЖА',font=font(37,True),fill=INK)
    d.text((50,80),'ПЛАНИРОВОЧНОЕ ПРЕДЛОЖЕНИЕ v01 · функции приняты, размеры и комнаты на оценку',font=font(23),fill='#b16634')
    for floor in [f for f in floors if f['building']=='M']:
        top=150+(floor['level']-1)*500
        d.text((50,top),f"{floor['level']} ЭТАЖ · сверху — хозяйственный фасад; снизу — парк и озеро",font=font(25,True),fill=INK)
        draw_floor(d,floor,(50,top+48),12)
        yy=top+45
        for r in floor['spaces']:
            if r['kind'] in ('corridor','gallery','stairs'): continue
            label=r['id'].split('-',1)[-1]+' · '+r['name']
            # Wrap long names using measured line widths.
            words=label.split(); line=''
            for word in words:
                trial=(line+' '+word).strip()
                if d.textlength(trial,font=font(18))>620:
                    d.text((1110,yy),line,font=font(18),fill=INK); yy+=24; line=word
                else: line=trial
            if line: d.text((1110,yy),line,font=font(18),fill=INK); yy+=27
        d.text((50,top+405),'C — коридор · G — галерея · S1 / S2 — лестницы · зелёные квадраты — наружные входы',font=font(20),fill=INK)
    d.text((50,1660),'Размерная основа 84 × 28 м → в игре 109,2 × 36,4 м по правилу E. Стены и проёмы уточняются.',font=font(22),fill=INK)
    path=DOCS/'plans/sanatorium_main_v01.png'; im.save(path); print(path)


def diagram_residential(floors):
    im=Image.new('RGB',(1800,1350),PAPER); d=ImageDraw.Draw(im)
    d.text((50,25),'САНАТОРИЙ · ЖИЛЫЕ КОРПУСА А И Б · ПО 4 ЭТАЖА',font=font(35,True),fill=INK)
    d.text((50,80),'ПРЕДЛОЖЕНИЕ v01 · 12 двухместных номеров на этаж · 96 мест в корпусе · 192 всего',font=font(23),fill='#b16634')
    for floor in [f for f in floors if f['building']=='A']:
        col=(floor['level']-1)%2; row=(floor['level']-1)//2
        x=50+col*880; y=155+row*490
        d.text((x,y),f"{floor['level']} ЭТАЖ · корпус Б: та же вместимость",font=font(24,True),fill=INK)
        draw_floor(d,floor,(x,y+48),17)
        d.text((x,y+440),'C — коридор · G — галерея · S1 / S2 — две лестницы',font=font(19),fill=INK)
    d.text((50,1170),'Все этажи доступны. Запирание номеров и маршруты мародёров ещё не назначены.',font=font(23),fill=INK)
    d.text((50,1210),'Корпус Б зеркален. Голубые рамки — санузлы; зелёные квадраты — наружные входы.',font=font(23),fill=INK)
    d.text((50,1250),'Размерная основа 42 × 22 м → в игре 54,6 × 28,6 м. Мебель и люди остаются 1:1.',font=font(23),fill=INK)
    path=DOCS/'plans/sanatorium_residential_v01.png'; im.save(path); print(path)


def main():
    floors=[main_floor(n) for n in (1,2,3)]
    floors += [residential_floor(b,n) for b in ('A','B') for n in (1,2,3,4)]
    validate(floors)
    data={'status':'archived_superseded_shell_concept_2026-11-04','version':'v01','units':'nominal_metres',
          'game_horizontal_multiplier':1.3,'floors':floors,
          'capacity':{'rooms_per_residential_floor':12,'beds_per_room':2,'beds_per_building':96,'total_beds':192},
          'parking_proposal':{'A':48,'B':48,'M':32,'cars_total':128,'coach_pockets_M':2}}
    out=DOCS/'design/data/sanatorium_layout_v01.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(out)
    (DOCS/'plans').mkdir(parents=True,exist_ok=True)
    diagram_main(floors); diagram_residential(floors)


if __name__=='__main__': main()
