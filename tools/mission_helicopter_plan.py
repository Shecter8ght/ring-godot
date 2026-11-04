"""Editable design diagrams; proposed geometry, never input to the level builder.

Run: python -X utf8 tools/mission_helicopter_plan.py
All metric dimensions below are unapproved design proposals. See mission_helicopter.md.
"""
from pathlib import Path
import math
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'plans'
FONT = Path('C:/Windows/Fonts/arial.ttf')
BOLD = Path('C:/Windows/Fonts/arialbd.ttf')
INK = '#24372e'
MUTED = '#52685b'
PAPER = '#f4f1e7'
ORANGE = '#bd642f'


class Sheet:
    def __init__(self, size):
        self.im = Image.new('RGB', size, PAPER)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, text, size=25, fill=INK, bold=False):
        f = ImageFont.truetype(str(BOLD if bold else FONT), size)
        self.d.text(xy, text, font=f, fill=fill, spacing=7)

    def wrapped(self, xy, text, width=34, size=24, fill=INK, bold=False):
        lines = textwrap.wrap(text, width=width)
        self.text(xy, '\n'.join(lines), size, fill, bold)
        return len(lines) * (size + 7)

    def line(self, pts, fill, width=3, dash=None):
        if dash is None:
            self.d.line(pts, fill=fill, width=width, joint='curve')
            return
        phase = 0.0
        period = sum(dash)
        for a, b in zip(pts, pts[1:]):
            length = math.dist(a, b)
            if length == 0:
                continue
            position = 0.0
            while position < length:
                active = phase < dash[0]
                remaining = (dash[0] if active else period) - phase
                step = min(remaining, length - position)
                if active:
                    p = tuple(a[k] + (b[k] - a[k]) * position / length for k in (0, 1))
                    q = tuple(a[k] + (b[k] - a[k]) * (position + step) / length for k in (0, 1))
                    self.d.line([p, q], fill=fill, width=width)
                position += step
                phase = (phase + step) % period
                if abs(period - phase) < 0.001:
                    phase = 0

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.im.save(OUT / name)
        print(OUT / name)


def plan():
    s = Sheet((1600, 1900))
    s.text((60, 35), 'ВЕРТОЛЁТ · ПЕРВАЯ СХЕМА КАРТЫ', 43, bold=True)
    s.text((60, 100), 'ПРЕДЛОЖЕНИЕ v01 · 04.11.2026 · размещение, высоты и размер не утверждены', 25, ORANGE)
    s.text((60, 144), 'Рабочая рамка 2 × 3 км. Все отметки высот — от уровня озера.', 25)
    x0, y0, scale = 60, 220, 0.5

    def p(x, z):
        return (round(x0 + (x + 1000) * scale), round(y0 + (z + 1500) * scale))

    def poly(points, color, outline=None, width=2):
        pts = [p(*v) for v in points]
        s.d.polygon(pts, fill=color)
        if outline:
            s.line(pts + [pts[0]], outline, width)

    def route(points, color, width=5, dash=None):
        s.line([p(*v) for v in points], color, width, dash)

    def node(x, z, number):
        a, b = p(x, z)
        s.d.ellipse((a-23, b-23, a+23, b+23), fill=INK, outline=PAPER, width=3)
        s.text((a-8 if number < 10 else a-15, b-17), str(number), 27, PAPER, True)

    s.d.rectangle((60, 220, 1060, 1720), fill='#d6dfc8', outline='#93a28c', width=3)
    for x in range(-500, 1000, 500):
        route([(x, -1500), (x, 1500)], '#c3cfb8', 1)
    for z in range(-1000, 1500, 500):
        route([(-1000, z), (1000, z)], '#c3cfb8', 1)

    # Mountains are regions with routes, not impassable walls.
    poly([(-1000,-1500),(-1000,1300),(-820,1080),(-740,700),(-850,300),
          (-750,-100),(-900,-500),(-650,-1080),(-340,-1500)], '#9fad97')
    poly([(1000,-1500),(1000,1500),(770,1250),(830,900),(710,620),
          (800,350),(730,-50),(850,-400),(600,-1100),(300,-1500)], '#a5b29c')
    for offset in (0, 75, 150):
        route([(-930+offset,-1450),(-780+offset,-1060),(-890+offset,-650),
               (-800+offset,-200),(-900+offset,250),(-780+offset,650)], '#82927e', 2)
        route([(920-offset,-1450),(740-offset,-1080),(880-offset,-650),
               (780-offset,-180)], '#84937e', 2)

    # Upper reservoir and a separate, much lower downstream river.
    lake = [(-80,-1160),(-180,-1000),(-240,-740),(-210,-430),(-300,-160),
            (-240,160),(-280,400),(-340,800),(-190,715),(0,670),(190,715),
            (340,800),(320,450),(250,200),(340,-70),(260,-330),
            (310,-650),(170,-980),(70,-1160)]
    poly(lake, '#8cb9bd', '#4d858b', 3)
    poly([(-50,785),(70,785),(100,960),(60,1150),(135,1320),(100,1500),
          (30,1500),(55,1310),(-20,1140),(15,960)], '#7ca6ac')
    # Lower gorge is shown in warm grey so it is not read as water at lake level.
    route([(-140,890),(-160,1050),(-130,1240),(-190,1490)], '#ad9d85', 12)
    route([(190,890),(210,1070),(180,1230),(240,1490)], '#ad9d85', 12)

    # Roads and two proposed connections.
    west = [(-950,-1250),(-650,-1080),(-650,-850),(-480,-570),(-550,-200),
            (-520,0),(-560,420),(-460,640),(-340,800)]
    east = [(900,-1260),(650,-1100),(650,-900),(500,-600),(620,-300),
            (600,180),(470,480),(340,800)]
    route(west, '#73786d', 12)
    route(east, '#73786d', 12)
    route([(340,800),(600,900),(700,1100),(850,1350)], '#73786d', 7)
    north = [(-650,-1080),(-400,-1240),(-140,-1320),(180,-1320),(420,-1210),(650,-1100)]
    route(north, ORANGE, 5, (15, 10))
    route([(-780,1400),(-640,1220),(-760,1050),(-520,900),(-610,750),(-460,640)], '#73786d', 7)
    route([(-640,1220),(-430,1150),(-280,1210),(-190,1060),(-80,1080)], '#73786d', 7)
    # Mountain paths and switchbacks.
    for points in [
        [(-650,-850),(-850,-1000),(-710,-1160),(-860,-1270),(-700,-1400)],
        [(-520,0),(-720,-120),(-650,-290),(-820,-390),(-700,-550)],
        [(650,-900),(820,-780),(700,-650),(860,-500),(730,-350),(830,-200)],
        [(600,180),(790,70),(690,-70),(830,-200)],
    ]:
        route(points, '#ebddbc', 5)

    # Buildings are scale hints, not a finished building layout.
    for i in range(15):
        x = -640 + (i % 3) * 90
        z = -150 + (i // 3) * 70
        a, b = p(x, z)
        s.d.rectangle((a-9,b-7,a+9,b+7), fill='#cbbb9c', outline='#7c7866', width=2)
    for x,z,w,h in [(-610,420,80,35),(-450,420,95,30),(-560,550,70,30),
                    (-720,-900,80,35),(-550,-900,80,35),(-720,-740,80,35)]:
        a,b=p(x,z); s.d.rectangle((a,b,a+w/2,b+h/2), fill='#c2b69c',outline='#756b5a',width=2)
    a,b=p(-790,-980); c,d=p(-470,-670)
    s.d.rectangle((a,b,c,d),outline='#93794e',width=3)

    # Sanatorium: multi-building ensemble and a terraced park descending to the lake.
    poly([(370,40),(760,-10),(870,150),(800,420),(510,530),(330,340)], '#b3c79d', '#8fa17d', 2)
    for x,z,w,h in [(520,30,260,55),(490,200,95,130),(710,160,95,130)]:
        a,b=p(x,z); s.d.rectangle((a,b,a+w/2,b+h/2),fill='#eee6ce',outline='#95846d',width=3)
    a,b=p(640,200); s.d.ellipse((a-15,b-15,a+15,b+15),fill='#9fc6cc',outline='#f3eddc',width=4)
    for points in [[(640,200),(520,260),(560,350),(400,390),(440,480),(330,420)],
                   [(520,30),(440,100),(480,180),(360,230),(400,300),(285,280)]]:
        route(points, '#f4e5bd', 7)
    route([(300,140),(290,260),(320,390)], '#dec58f', 11)

    # Arch curves upstream in plan. No dam technology is simulated here.
    dam=[(x, 800-130*(1-(x/340)**2)) for x in range(-340,341,10)]
    route(dam,'#6f7c7a',24)
    route(dam,'#e7e5d9',12)
    route([(160,840),(260,900),(220,1040),(110,1110)], '#ece8d9', 5, (10,8))

    for x,z,n in [(-520,0,1),(-560,420,2),(-650,-850,3),(650,-900,4),
                  (640,200,5),(0,700,6),(-80,1080,7)]:
        node(x,z,n)

    s.text(p(-160,-500),'ОЗЕРО',31,'#2b626a',True)
    s.text(p(-170,-410),'0 м',24,'#2b626a')
    s.text(p(-920,-1400),'+500…650 м',22,INK,True)
    s.text(p(540,-1410),'+450…650 м',22,INK,True)
    s.text(p(-890,1360),'Нижний подход',20,MUTED)
    s.text(p(170,1240),'Ущелье',22,MUTED)
    s.text(p(200,1310),'−250 м',22,MUTED,True)

    # Proposal for four entry/exit regions, not configured extraction points.
    for x,z,tag in [(-950,-1250,'A'),(900,-1260,'B'),(-780,1400,'C'),(850,1350,'D')]:
        a,b=p(x,z)
        s.d.rectangle((a-14,b-14,a+14,b+14),fill='#f7efe0',outline=ORANGE,width=3)
        s.text((a+19,b-17),tag,24,ORANGE,True)

    # Legend stays separate from the map so labels never obscure a route.
    col, y = 1110, 230
    s.text((col,y),'МЕСТА · РАССТАНОВКА',26,bold=True); y+=44
    s.text((col,y),'НА ОЦЕНКУ',25,ORANGE,True); y+=60
    entries=[
        ('1 · Рабочий посёлок','12–18 участков. В схеме показано 15. Место преступления; связь с лесопилкой.'),
        ('2 · Лесопилка','Производственный двор, цеха, штабеля и хозяйственные проходы.'),
        ('3 · Старый военный склад','Занят мародёрами. Здесь добывается ПЗРК боем или скрытно.'),
        ('4 · Старая ПВО','На горной террасе. Второй способ подготовки; высота +220 м — предложение.'),
        ('5 · Санаторий','Главный и два жилых корпуса, парк и пляж. Недавно опустел, занят мародёрами. Террасы +40…80 м.'),
        ('6 · Арочная плотина','Предложение: высота около 260 м. Доступны гребень, галереи и подножие.'),
        ('7 · Нижнее ущелье','Предлагаемые дороги и технические подходы к подножию плотины.'),
    ]
    for title, body in entries:
        s.text((col,y),title,25,bold=True); y+=38
        y+=s.wrapped((col,y),body,31,23,MUTED)+27
    y+=8
    s.line([(col,y),(col+62,y)],ORANGE,5,(15,10))
    s.text((col+78,y-15),'Северный обход',22); y+=36
    s.text((col,y),'Его наличие не утверждено.',21,ORANGE); y+=46
    s.wrapped((col,y),'A–D: предложенные районы входа / выхода. Условия и точные точки не выбраны.',32,22,MUTED)

    # North and metric scale apply only to this proposed frame.
    s.line([(1010,330),(1010,260)],INK,4)
    s.d.polygon([(1010,245),(1000,268),(1020,268)],fill=INK)
    s.text((997,217),'С',25,INK,True)
    s.line([(80,1780),(330,1780)],INK,6)
    for x in (80,205,330): s.line([(x,1770),(x,1790)],INK,3)
    s.text((80,1800),'0',22); s.text((180,1800),'250',22); s.text((295,1800),'500 м',22)
    s.text((540,1766),'Полёт, три места падения и население — следующий слой.',23,ORANGE)
    s.text((540,1805),'Это схема связей. Рельеф и время пути ещё не проверены.',23,MUTED)
    s.save('mission_helicopter_map_v01.png')


def sections():
    s=Sheet((1800,1700))
    s.text((60,30),'ВЕРТОЛЁТ · ВЫСОТНЫЕ РАЗРЕЗЫ',43,bold=True)
    s.text((60,92),'ПРЕДЛОЖЕНИЕ v01 · числа, расстояния и профили ещё не утверждены',25,ORANGE)
    s.text((60,155),'А · ВДОЛЬ ВОДОХРАНИЛИЩА И ЧЕРЕЗ ПЛОТИНУ',28,bold=True)
    water=410
    s.d.polygon([(90,water),(1190,water),(1190,726),(1060,696),(900,645),
                 (700,540),(500,490),(330,water)],fill='#9fc4c7')
    terrain=[(60,300),(180,360),(330,410),(500,490),(700,540),(900,645),
             (1060,696),(1190,726),(1335,748),(1500,780),(1740,800),(1740,840),(60,840)]
    s.d.polygon(terrain,fill='#b9c3aa')
    s.line(terrain[:-3],'#809276',4)
    # Conceptual axial section: it communicates level differences, not structural design.
    s.d.polygon([(1185,398),(1203,398),(1265,726),(1185,726)],fill='#aeb5b1',outline='#6c7975',width=4)
    for yy in (470,560,650):
        s.d.rectangle((1193,yy,1212,yy+9),fill='#52665e')
    s.line([(330,410),(1184,410)],'#47858c',4)
    s.text((490,350),'ВОДОХРАНИЛИЩЕ · 0 м',28,'#2b626a',True)
    s.text((1100,265),'Гребень',26,INK,True)
    s.line([(1170,305),(1194,394)],INK,2)
    s.text((1320,500),'Галереи',25,INK,True)
    s.line([(1310,535),(1210,564)],INK,2)
    s.text((1370,700),'Подножие · −250 м',25,INK,True)
    s.text((1320,315),'Высота стены',25,ORANGE,True)
    s.text((1320,353),'около 260 м',30,ORANGE,True)
    s.line([(1290,400),(1290,726)],ORANGE,3)
    s.line([(1278,400),(1302,400)],ORANGE,3)
    s.line([(1278,726),(1302,726)],ORANGE,3)
    s.text((60,860),'Сверху — вода у гребня. Снизу — полная высота стены и глубокое ущелье.',25)
    s.text((60,980),'Б · ОТ ОЗЕРА ЧЕРЕЗ САНАТОРИЙ В ГОРЫ',28,bold=True)
    ground=[(70,1550),(350,1550),(470,1510),(640,1465),(780,1440),
            (960,1420),(1110,1370),(1250,1300),(1430,1240),(1610,1175),(1740,1130)]
    s.d.polygon(ground+[(1740,1610),(70,1610)],fill='#b2c2a0')
    s.line(ground,'#768b6b',4)
    s.line([(70,1550),(350,1550)],'#55939a',8)
    # Resort building silhouettes and garden levels, intentionally no fixed floor count.
    for x,y,w,h in [(645,1460,120,78),(800,1430,68,55),(905,1424,70,55)]:
        s.d.rectangle((x,y-h,x+w,y),fill='#e6ddc5',outline='#99886c',width=3)
        for xx in range(x+12,x+w-5,20):
            for yy in range(y-h+12,y-5,20): s.d.rectangle((xx,yy,xx+7,yy+10),fill='#7e9389')
    s.line([(355,1547),(400,1534),(410,1520),(455,1510),(465,1490),(520,1480),
            (535,1468),(590,1465),(610,1448),(640,1448)],'#efe1b8',7)
    s.line([(1020,1402),(1130,1385),(1100,1365),(1210,1340),(1190,1317),
            (1320,1280),(1290,1260),(1430,1240)],'#eee1b9',5)
    s.text((100,1570),'Пляж · 0 м',23,INK,True)
    s.text((480,1310),'Санаторий · +40…80 м',26,INK,True)
    s.text((1070,1450),'Горные маршруты · +150…350 м',24,INK,True)
    s.text((1370,1102),'Вершины · +450…700 м',23,INK,True)
    s.text((60,1630),'Схематические разрезы: горизонтальный масштаб условный. Они не задают конструкцию плотины.',22,MUTED)
    s.save('mission_helicopter_sections_v01.png')


if __name__ == '__main__':
    plan()
    sections()
