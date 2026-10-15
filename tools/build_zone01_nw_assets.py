"""Игровая архитектура первого фрагмента: подъезд, рынок и дома у оврага.

Blender --background --factory-startup --python-exit-code 1 --python tools/build_zone01_nw_assets.py
Существующие фасады и PBR не перезаписывает. Оси, UV и экспорт — как у build_khrushchevka.
Планировки — авторская игровая адаптация поэтажных чертежей 1-464 из референсы/zone01_nw.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_khrushchevka as kh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/zone01/nw"
SOURCE = ROOT / "_asset_src/zone01_nw"
CX = -4.8
X0, X1 = -12.8, 3.2
FH, PLINTH = 2.8, 1.1
OPEN_FLATS = [(0, "front_left"), (0, "rear_left"), (1, "front_right"),
              (2, "rear_left"), (3, "front_left"), (4, "rear_right")]


def up_quad(b, mat, corners):
    points = [Vector(v) for v in corners]
    if (points[1]-points[0]).cross(points[2]-points[0]).y < 0:
        points.reverse()
    b.quad(mat, points)


class Architecture(kh.Builder):
    def solid(self, mat, center, size, yaw=0.0, bevel=0.008):
        super().box(mat, center, size, yaw=yaw, bevel=bevel)
        self.collide(center, size, yaw)

    def wall_x(self, x0, x1, z, y, h, t, mat="NWPlaster", door=None):
        if door is None:
            self.solid(mat, ((x0+x1)/2, y+h/2, z), (x1-x0, h, t))
            return
        dx, dw, dh = door
        for a, b in [(x0, dx-dw/2), (dx+dw/2, x1)]:
            if b-a > .01:
                self.solid(mat, ((a+b)/2, y+h/2, z), (b-a, h, t))
        self.solid(mat, (dx, y+(h+dh)/2, z), (dw, h-dh, t))
        self.frame(dx, y, z, dw, dh)

    def wall_z(self, x, z0, z1, y, h, t, mat="NWPlaster", door=None):
        if door is None:
            self.solid(mat, (x, y+h/2, (z0+z1)/2), (t, h, z1-z0))
            return
        dz, dw, dh = door
        for a, b in [(z0, dz-dw/2), (dz+dw/2, z1)]:
            if b-a > .01:
                self.solid(mat, (x, y+h/2, (a+b)/2), (t, h, b-a))
        self.solid(mat, (x, y+(h+dh)/2, dz), (t, h-dh, dw))
        for side in (-1, 1):
            self.box("NWTrim", (x, y+dh/2, dz+side*(dw/2+.035)), (t+.055, dh+.06, .065), bevel=.008)
        self.box("NWTrim", (x, y+dh+.03, dz), (t+.055, .075, dw+.12), bevel=.008)

    def frame(self, x, y, z, w, h):
        for side in (-1, 1):
            self.box("NWTrim", (x+side*(w/2+.035), y+h/2, z), (.065, h+.06, .23), bevel=.006)
        self.box("NWTrim", (x, y+h+.035, z), (w+.14, .075, .23), bevel=.006)

    def rail(self, a, b, height=.95):
        av, bv = Vector(a), Vector(b)
        count = max(1, int((bv-av).length/.35))
        for i in range(count+1):
            p = av.lerp(bv, i/count)
            self.cyl("Railing", p, p+Vector((0, height, 0)), .016, 8)
            self.collide(p+Vector((0,height/2,0)),(.04,height,.04))
        self.cyl("NWHandrail", av+Vector((0, height, 0)), bv+Vector((0, height, 0)), .028, 10)

    def stairs(self, x, z0, z1, y0, y1, width, n, rail=True, mat="Concrete"):
        # Геометрические ступени совпадают с физикой; боковых невидимых пандусов нет.
        for i in range(n):
            a = z0+(z1-z0)*i/n
            b = z0+(z1-z0)*(i+1)/n
            top = y0+(y1-y0)*(i+1)/n
            self.solid(mat, (x, top-.09, (a+b)/2), (width, .18, abs(b-a)+.008), bevel=.004)
        # Наклонная тетива — визуальная опора между площадками.
        for side in (-1, 1):
            self.cyl("Railing", (x+side*width*.45, y0-.12, z0), (x+side*width*.45, y1-.12, z1), .045, 8)
        if rail:
            self.rail((x+width/2-.04, y0, z0), (x+width/2-.04, y1, z1))


class Panel(Architecture):
    """Сохраняет рисунок существующего фасада, убирая заглушки выбранной жилой секции."""
    def box(self, mat, center, size, yaw=0.0, bevel=0.0, pitch=0.0):
        if min(size) <= .001:
            return
        x, y, z = center
        sx, sy, sz = size
        if mat == "Mastic" and sx > 50:
            # Мастика нужна только в швах, сплошной экран за окнами здесь не нужен.
            return
        if mat in {"Interior", "Curtain1", "Curtain2", "Curtain3", "Void"} and X0 < x < X1:
            return
        if mat == "Plinth" and z > 5 and y < 1.2 and x-sx/2 < CX+.8-.0001 and x+sx/2 > CX-.8+.0001:
            # Вход не перекрыт цоколем ниже окна лестницы.
            for a, b in [(x-sx/2, CX-.8), (CX+.8, x+sx/2)]:
                if b > a:
                    self.box(mat, ((a+b)/2, y, z), (b-a, sy, sz), yaw, bevel, pitch)
            return
        super().box(mat, center, size, yaw, bevel, pitch)
        if mat in {"PanelConcrete", "Plinth"} and max(size) > .2 and abs(pitch) < .01:
            kh.Builder.collide(self, center, size, yaw)

    def collide(self, center, size, yaw=0.0):
        if size[0] > 50 and size[1] > 10:
            return
        super().collide(center, size, yaw)


def panel_entrance(b, rng, x, face, out, plinth, style):
    if abs(x-CX) > .1:
        return ORIGINAL_ENTRANCE(b, rng, x, face, out, plinth, style)
    b.frame(x, .30, face, 1.5, 2.2)
    b.solid("DoorMetal", (x-.82, 1.38, face+.65), (.06, 2.16, 1.25))
    b.box("Concrete", (x, 3.05, face+.85), (2.7, .16, 1.8), bevel=.025)
    b.solid("Concrete", (x, .20, face+.65), (2.8, .20, 1.3))
    b.stairs(x, face+1.9, face+1.3, 0, .30, 2.3, 2, False)
    b.solid("Concrete", (x, .23, 5.0), (3.0, .14, 1.8))
    # Низ входа — полуплощадка. Два коротких марша соединяют его с подвалом и первым этажом.
    b.stairs(CX+.77, 4.2, 1.7, .30, 1.1, 1.34, 8)
    b.stairs(CX-.77, 1.7, 4.2, -1.7, .30, 1.34, 14)
    return dict(x=x, z=face+1.9, sill=.30)


ORIGINAL_ENTRANCE = kh.entrance
ORIGINAL_WALL = kh.wall_with_window
ORIGINAL_WINDOW = kh.window


def panel_wall(b, mat, x0, x1, y0, y1, face, out, thick, win, bevel):
    if abs((x0+x1)/2-CX) < .1 and out > 0 and y0 < 1.2:
        win = (CX, .30, 1.5, 2.2)
    ORIGINAL_WALL(b, mat, x0, x1, y0, y1, face, out, thick, win, bevel)


def panel_window(b, rng, x, y, w, h, face, out, depth, ground_floor, kind="room", frame=None):
    if abs(x-CX) < .1 and kind == "stair" and y < 2.6:
        return
    # Доступные комнаты получают настоящие световые проёмы; стёкла выбиты, рамки остаются.
    if X0 < x < X1:
        for a, cy, sw, sh in [(x, y, w, .06), (x, y+h, w, .06),
                               (x-w/2, y+h/2, .06, h), (x+w/2, y+h/2, .06, h),
                               (x, y+h/2, .045, h)]:
            b.box("FrameWhite", (a, cy, face-out*depth), (sw, sh, .08), bevel=.006)
        b.box("Galv", (x, y-.03, face), (w+.12, .025, .35), pitch=out*8)
    else:
        ORIGINAL_WINDOW(b, rng, x, y, w, h, face, out, depth, ground_floor, kind, frame)


def apartment(b, floor, which, opened):
    y = PLINTH+floor*FH
    front = which.startswith("front")
    left = which.endswith("left")
    xa, xb = (X0+.2, CX-1.6) if left else (CX+1.6, X1-.2)
    if not front:
        xa, xb = (X0+.2, CX) if left else (CX, X1-.2)
    za, zb = (0, 5.47) if front else (-5.47, -.1)
    # Мокрые зоны около лестничного ядра, одни и те же на всех этажах.
    core_edge = xb if left else xa
    kx = core_edge+(-1.25 if left else 1.25)
    kitchen_z = 3.9 if front else -3.9
    b.solid("NWTile", (kx, y+.012, kitchen_z), (2.35, .025, 2.7), bevel=0)
    # Кухня и комната разделены стеной с дверью, санузел у входа.
    split_x = core_edge+(-2.55 if left else 2.55)
    b.wall_z(split_x, za, zb, y, 2.58, .12, door=(1.05 if front else -1.0, .88, 2.08))
    wz = 2.05 if front else -2.05
    b.wall_x(min(kx-1.2, kx+1.2), max(kx-1.2, kx+1.2), wz, y, 2.58, .12,
             door=(kx, .82, 2.05))
    # Керамическая сантехника — низкополигональная архитектурная деталь, не сундук-заглушка.
    b.box("NWEnamel", (kx-.65, y+.39, .8 if front else -.8), (.55, .78, .45), bevel=.06)
    b.cyl("Galv", (kx-.65, y+.79, .8 if front else -.8), (kx-.65, y+.96, .8 if front else -.8), .014, 10)
    # Закрытые квартиры обозначены настоящей створкой в существующем проёме.
    if not opened:
        if front:
            b.solid("DoorMetal", (CX+(-1.6 if left else 1.6), y+1.04, .9), (.07, 2.08, .96))
        else:
            dx = CX+(-.8 if left else .8)
            b.solid("DoorMetal", (dx, y+1.04, -1.18), (.88, 2.08, .07))


def build_panel():
    originals = kh.Builder, kh.entrance, kh.wall_with_window, kh.window
    try:
        kh.Builder, kh.entrance, kh.wall_with_window, kh.window = Panel, panel_entrance, panel_wall, panel_window
        b, info = kh.build_panel(11)
    finally:
        kh.Builder, kh.entrance, kh.wall_with_window, kh.window = originals
    # Глухие соседние секции остаются глухими; их физика не пересекает жилой подъезд.
    for a, c in [(-28.8, X0), (X1, 28.8)]:
        b.solid("Interior", ((a+c)/2, 7.55, 0), (c-a, 15.6, 10.9), bevel=0)
    for x in (X0, X1):
        b.wall_z(x, -5.49, 5.49, -1.7, 16.8, .24)
    # Фундамент и пол подвала. Грунт под секцией вынимается только в сцене этой карты.
    b.solid("Concrete", ((X0+X1)/2, -1.8, 0), (X1-X0, .2, 11.0))
    b.wall_x(X0, X1, -5.45, -1.7, 2.8, .3, "Concrete")
    b.wall_x(X0, X1, 5.45, -1.7, 2.0, .3, "Concrete")
    # Каждый этаж: плита вырезана по настоящей лестничной клетке.
    for f in range(6):
        y = PLINTH+f*FH
        for a, c in [(X0, CX-1.6), (CX+1.6, X1)]:
            b.solid("NWFloor", ((a+c)/2, y-.1, 0), (c-a, .2, 11.0))
        b.solid("NWFloor", (CX, y-.1, -2.6), (3.2, .2, 5.8))
        b.solid("Concrete", (CX, y-.1, .85), (3.2, .2, 1.7))
        if f == 5:
            break
        for x in (CX-1.6, CX+1.6):
            b.wall_z(x, 0, 5.47, y, 2.6, .18, door=(.9, .96, 2.08))
            # Нижняя окрашенная часть подъезда.
            b.box("NWStairPaint", (x + (.105 if x < CX else -.105), y+.65, 3.55), (.025, 1.3, 3.75))
        # Две задние квартиры имеют отдельные дверные проёмы с общей перемычкой.
        for a, c in [(CX-1.6,CX-1.24),(CX-.36,CX+.36),(CX+1.24,CX+1.6)]:
            b.solid("NWPlaster",((a+c)/2,y+1.04,-1.18),(c-a,2.08,.18))
        b.solid("NWPlaster",(CX,y+2.34,-1.18),(3.2,.52,.18))
        for dx in (CX-.8,CX+.8): b.frame(dx,y,-1.18,.88,2.08)
        b.wall_z(CX, -5.47, -1.3, y, 2.6, .16)
        b.wall_x(X0, CX-1.6, 0, y, 2.6, .18)
        b.wall_x(CX+1.6, X1, 0, y, 2.6, .18)
        for which in ("front_left", "front_right", "rear_left", "rear_right"):
            apartment(b, f, which, (f, which) in OPEN_FLATS)
        if f < 4:
            b.solid("Concrete", (CX, y+1.3, 4.84), (3.0, .2, 1.28))
            b.stairs(CX-.77, 1.7, 4.2, y, y+1.4, 1.34, 9)
            b.stairs(CX+.77, 4.2, 1.7, y+1.4, y+2.8, 1.34, 9)
        else:
            # На пятом этаже лестница заканчивается: ограждаем только сторону без марша.
            b.rail((CX-1.5,y,1.7),(CX-.1,y,1.7))
        # Стояки и радиатор около окна площадки.
        b.cyl("NWHeating", (CX-1.35, y+.1, 5.16), (CX-1.35, y+2.6, 5.16), .022, 10)
        for k in range(9):
            b.box("NWHeating", (CX-.6+k*.12, y+.58, 5.16), (.075, .55, .09), bevel=.018)
    info.update(kind="panel_1_464_playable", accessible_floors=5, basement=True,
                open_apartments=[list(v) for v in OPEN_FLATS], section=[X0, X1])
    b.collide((0,15.15,0),(57.3,.1,11.3))
    return b, info


def window_wall(b, width, z, y, h, windows, mat="NWPlaster", thick=.28):
    # Фасад без экрана за стеклом; в интерактивных помещениях проёмы физически открыты.
    starts = [(-width/2, width/2)]
    for x, sill, w, wh in windows:
        updated = []
        for a, c in starts:
            if x-w/2 > a: updated.append((a, x-w/2))
            if x+w/2 < c: updated.append((x+w/2, c))
        starts = updated
        b.solid(mat, (x, y+sill/2, z), (w, sill, thick))
        b.solid(mat, (x, y+(sill+wh+h)/2, z), (w, h-sill-wh, thick))
        for dx, cy, sw, sh in [(x, y+sill, w+.1, .07), (x, y+sill+wh, w+.1, .07),
                               (x-w/2, y+sill+wh/2, .07, wh), (x+w/2, y+sill+wh/2, .07, wh),
                               (x, y+sill+wh/2, .05, wh)]:
            b.box("FrameWhite", (dx, cy, z), (sw, sh, thick+.06), bevel=.005)
    for a, c in starts:
        if c-a > .01: b.solid(mat, ((a+c)/2, y+h/2, z), (c-a, h, thick))


def house_side_window(b, x, center, y):
    sill, width, height, wall_h = .85,1.45,1.35,2.78
    b.solid("NWPlaster",(x,y+sill/2,0),(.28,sill,9))
    b.solid("NWPlaster",(x,y+(sill+height+wall_h)/2,0),(.28,wall_h-sill-height,9))
    for a,c in [(-4.5,center-width/2),(center+width/2,4.5)]:
        b.solid("NWPlaster",(x,y+sill+height/2,(a+c)/2),(.28,height,c-a))
    for z in (center-width/2,center,center+width/2):
        b.box("FrameWhite",(x,y+sill+height/2,z),(.34,height,.065),bevel=.005)
    for yy in (y+sill,y+sill+height):
        b.box("FrameWhite",(x,yy,center),(.34,.065,width+.1),bevel=.005)


def build_hangar():
    b = Architecture()
    b.solid("Concrete", (0, -.12, 0), (24, .24, 42))
    b.wall_x(-12, 12, -21, 0, 7.1, .28, "Brick", (0, 4.6, 4.4))
    b.wall_x(-12, 12, 21, 0, 7.1, .28, "Brick", (0, 4.6, 4.4))
    for side in (-1,1):
        b.wall_z(side*12,-21,21,0,5.0,.28,"Brick",(0 if side<0 else 7,1.4,2.2))
        b.solid("Brick",(side*12,6.75,0),(.28,.7,42))
        for z in range(-21,22,7):
            b.solid("Brick",(side*12,5.7,z),(.28,1.4,.32))
        for y in (5.0,6.4): b.box("FrameWhite",(side*12,y,0),(.3,.07,42))
        for z in range(-19,21,2): b.box("FrameWhite",(side*12,5.7,z),(.3,1.4,.045))
    # Промышленная несущая схема: колонны, фермы, прогоны, профлист.
    for z in range(-20, 21, 7):
        for side in (-1, 1):
            b.solid("NWWarehouseSteel", (side*11.5, 3.45, z), (.25, 6.9, .25))
            b.cyl("NWWarehouseSteel", (side*11.5, 7.0, z), (0, 9.0, z), .09, 10)
        b.cyl("NWWarehouseSteel", (-11.5, 6.9, z), (11.5, 6.9, z), .08, 10)
        for x in range(-10, 11, 2):
            b.cyl("NWWarehouseSteel", (x, 6.9, z), (x+1, 9-abs(x+1)*2/11.5, z), .035, 8)
    for side in (-1, 1):
        b.box("CorrGrey",(side*6.2,8.015,0),(43.2,.1,math.hypot(12.4,2.13)),
              yaw=90,pitch=side*math.degrees(math.atan2(2.13,12.4)))
        b.collisions.append(dict(pos=[side*6.2,8.015,0],size=[43.2,.1,math.hypot(12.4,2.13)],
                                 rotation=[side*math.degrees(math.atan2(2.13,12.4)),90,0]))
    for z in (-21.03, 21.03):
        for x in range(-11, 12, 2):
            rh = max(.05, 2.0*(1-abs(x)/12))
            b.box("CorrGrey", (x, 7.05+rh/2, z), (2.02, rh, .07))
        b.cyl("NWWarehouseSteel",(-2.5,4.65,z),(2.5,4.65,z),.17,12)
    b.box("CorrGrey",(0,4.9,-22.0),(6.4,.08,2.5),pitch=5)
    for x in (-3.0,3.0): b.solid("NWWarehouseSteel",(x,2.4,-23.0),(.12,4.8,.12))
    for side in (-1,1): b.cyl("Galv",(side*12.2,0,-20),(side*12.2,7.0,-20),.06,12)
    # Антресоль занимает только западный задний угол, основной пролёт остаётся свободным.
    b.solid("NWFloor", (-7.5, 3.5, 15.3), (8.2, .22, 10.8))
    for x in (-11.4, -3.5):
        for z in (10.1, 20.2):
            b.solid("NWWarehouseSteel", (x, 1.72, z), (.2, 3.45, .2))
    b.wall_x(-11.5, -3.5, 12.1, 3.61, 2.7, .15, "NWOffice", (-9.8, 1.05, 2.15))
    b.wall_z(-3.5, 12.1, 20.65, 3.61, 2.7, .15, "NWOffice")
    b.stairs(-10.35, -1.0, 10.0, 0, 3.61, 1.5, 22)
    b.rail((-9.4,3.61,10),(-3.5,3.61,10))
    b.rail((-3.5,3.61,10),(-3.5,3.61,12.1))
    b.solid("NWOffice", (-7.5, 6.39, 16.4), (8.1, .16, 8.5))
    return b, dict(kind="warehouse", width=24, depth=42, height=9.1, mezzanine_y=3.61)


def build_stall(opened, palette):
    b = Architecture()
    metal = ["CorrGreen", "CorrBlue", "CorrYellow"][palette]
    b.solid("Concrete", (0, -.08, 0), (7, .16, 5.4))
    b.wall_x(-3.5,3.5,-2.7,0,2.9,.14,metal)
    for x in (-3.5,3.5): b.wall_z(x,-2.7,2.7,0,2.9,.14,metal)
    b.wall_x(-3.5,3.5,2.7,0,2.9,.14,metal,(0,2.9,2.4))
    if not opened:
        b.solid("CorrGrey", (0,1.18,2.69),(2.85,2.36,.08))
    else:
        # Поднятая роллета и её направляющие, отверстие остаётся настоящим.
        b.cyl("Galv",(-1.6,2.62,2.72),(1.6,2.62,2.72),.13,12)
    b.box(metal,(0,2.98,0),(7.35,.08,5.8),pitch=-2)
    # Навес с провисанием, металлическая кромка и два тонких стояка.
    for i in range(8):
        za=2.7+2.1*i/8; zb=2.7+2.1*(i+1)/8
        ya=2.83-.3*(i/8)-.09*math.sin(i*math.pi/8)
        yb=2.83-.3*((i+1)/8)-.09*math.sin((i+1)*math.pi/8)
        up_quad(b,"NWAwning"+str(palette),[(-3.4,ya,za),(3.4,ya,za),(3.4,yb,zb),(-3.4,yb,zb)])
        b.quad("NWAwning"+str(palette),[(-3.4,ya-.008,za),(3.4,ya-.008,za),(3.4,yb-.008,zb),(-3.4,yb-.008,zb)])
    for x in (-3.3,3.3): b.cyl("Galv",(x,0,4.65),(x,2.5,4.65),.035,10)
    b.box("NWSign",(0,2.76,2.86),(3.7,.38,.05),bevel=.008)
    b.box("Galv",(0,2.96,-2.8),(7.2,.1,.14))
    return b, dict(kind="market_stall", opened=opened, width=7,depth=5.4,height=3.15)


def build_house(attic=True, mansard=False, closed=False):
    b = Architecture()
    y=.27; top=3.05; ridge=6.35 if mansard else 6.1
    b.solid("Concrete",(0,.085,0),(8.15,.37,9.15))
    b.solid("NWFloor",(0,y-.04,0),(7.65,.08,8.65))
    b.wall_x(-4,4,4.5,y,top-y,.28,"NWPlaster",(-2.1,1.05,2.15))
    window_wall(b,8,-4.5,y,top-y,[(-2.15,.85,1.4,1.35),(.45,.85,1.15,1.35)])
    house_side_window(b,-4,.5,y)
    house_side_window(b,4,-2.8,y)
    for z in (-4.52,4.52):
        b.box("FrameTeal",(0,top-.2,z),(8.1,.15,.08))
    for side in (-1,1):
        b.box("Slate",(side*2.2,(3.06+ridge)/2,0),(9.9,.1,math.hypot(4.4,ridge-3.06)),
              yaw=90,pitch=side*math.degrees(math.atan2(ridge-3.06,4.4)))
        b.collisions.append(dict(pos=[side*2.2,(3.06+ridge)/2,0],size=[9.9,.1,math.hypot(4.4,ridge-3.06)],
                                 rotation=[side*math.degrees(math.atan2(ridge-3.06,4.4)),90,0]))
        b.box("Galv",(side*4.35,3.0,0),(.14,.12,9.8))
        for z in (-4.3,4.3): b.cyl("Galv",(side*4.2,.1,z),(side*4.2,3.0,z),.045,10)
    # Два торцевых фронтона со световыми проёмами чердака.
    for z in (-4.5,4.5):
        side_top=top+(ridge-top)*.8
        profiles=[ [(-4,top),(-.8,top),(-.8,side_top)],
                   [(.8,top),(4,top),(.8,side_top)],
                   [(-.8,top),(.8,top),(.8,top+.36),(-.8,top+.36)],
                   [(-.8,top+1.65),(.8,top+1.65),(.8,side_top),(0,ridge),(-.8,side_top)] ]
        for profile in profiles:
            # Цельная наклонная кромка под скатом вместо ступенчатого ряда коробок.
            b.quad("WoodPlanks",[(x,yy,z+.06) for x,yy in profile])
            b.quad("WoodPlanks",[(x,yy,z-.06) for x,yy in reversed(profile)])
            for a,c in zip(profile,profile[1:]+profile[:1]):
                b.quad("WoodPlanks",[(a[0],a[1],z-.06),(c[0],c[1],z-.06),
                                     (c[0],c[1],z+.06),(a[0],a[1],z+.06)])
        for i in range(16):
            xa=-4+i*.5; xb=xa+.5; xc=(xa+xb)/2
            h=(ridge-top)*(1-max(abs(xa),abs(xb))/4)
            if abs(xc)<.8:
                b.collide((xc,top+.18,z),(.5,.36,.12))
                if h>1.65: b.collide((xc,top+(1.65+h)/2,z),(.5,h-1.65,.12))
            elif h>.01: b.collide((xc,top+h/2,z),(.5,h,.12))
    b.solid("BrickRed",(-2.5,4.5,-1.7),(.65,3.8,.65))
    b.box("Concrete",(-2.5,6.44,-1.7),(.82,.1,.82))
    b.wall_x(-3.72,-.1,2.25,y,2.55,.12,door=(-2.1,.98,2.08))
    b.wall_x(-3.72,-.1,-1.2,y,2.55,.12,door=(-1.0,.92,2.08))
    b.wall_z(-.1,-4.25,4.25,y,2.55,.12,door=(3.1,1.15,2.08))
    b.wall_z(-.15,-4.25,-1.2,y,2.55,.12,door=(-2.2,.82,2.05))
    b.box("NWTile",(-1.95,y+.01,-2.8),(3.5,.02,2.8))
    if attic and not closed:
        # Отверстие над лестницей не закрыто цельной потолочной плитой.
        b.solid("NWFloor",(-1.8,3.01,0),(3.9,.18,8.5))
        b.solid("NWFloor",(2.65,3.01,0),(2.2,.18,8.5))
        b.solid("NWFloor",(.85,3.01,3.025),(1.4,.18,2.45))
        b.solid("NWFloor",(.85,3.01,-3.85),(1.4,.18,.8))
        b.stairs(.85,-3.1,1.85,y,3.1,1.42,17,True,"WoodPlanks")
        b.rail((.15,3.1,-3.35),(.15,3.1,1.85))
        # Стропильные пары по настоящим скатам.
        for z in (-3.7,-1.85,0,1.85,3.7):
            b.cyl("NWHandrail",(-3.7,3.18,z),(0,ridge-.12,z),.065,8)
            b.cyl("NWHandrail",(3.7,3.18,z),(0,ridge-.12,z),.065,8)
    else:
        b.solid("NWPlaster",(0,3.0,0),(7.7,.18,8.7))
    if closed: b.solid("DoorMetal",(-2.1,y+1.075,4.5),(1.03,2.15,.06))
    b.solid("Concrete",(-2.1,.17,5.1),(1.8,.2,1.15))
    b.box("Slate",(-2.1,2.72,5.2),(2.1,.06,1.5),pitch=-9)
    return b, dict(kind="house", width=8,depth=9,height=ridge,attic=attic and not closed,floor_y=.27,attic_y=3.1)


def build_shed():
    b=Architecture()
    b.solid("Concrete",(0,-.05,0),(3.2,.1,4.2))
    b.wall_x(-1.5,1.5,-2,0,2.4,.12,"WoodPlanks")
    b.wall_x(-1.5,1.5,2,0,2.4,.12,"WoodPlanks",(0,1.1,2.1))
    for x in (-1.5,1.5): b.wall_z(x,-2,2,0,2.4,.12,"WoodPlanks")
    b.box("CorrGrey",(0,2.47,0),(3.5,.055,4.5),pitch=-6)
    for z in (-1.9,1.9):
        for x in (-1.4,1.4): b.box("NWHandrail",(x,1.2,z),(.12,2.4,.12))
    b.solid("DoorMetal",(-.61,1.05,2.4),(.055,2.1,1.05))
    return b,dict(kind="shed",width=3,depth=4,height=2.7)


def build_garden_fence():
    b=Architecture()
    for x in (-1.5,1.5):
        b.solid("NWHandrail",(x,.79,0),(.12,1.58,.12))
        b.box("Galv",(x,1.6,0),(.145,.04,.145),bevel=.008)
    for y in (.35,1.15): b.box("NWHandrail",(0,y,0),(3.0,.09,.075))
    for i in range(21):
        x=-1.45+i*.145
        b.box("WoodPlanks",(x,.78,.06),(.115,1.45,.025),bevel=.008)
        for y in (.35,1.15): b.cyl("Galv",(x,y,.075),(x,y,.082),.005,6)
    # Тонкая деревянная ограда не превращается в толстую бетонную стену.
    b.collide((0,.78,.06),(3.0,1.45,.04))
    return b,dict(kind="garden_fence",width=3,height=1.65)


def build_bridge():
    b=Architecture()
    b.solid("NWWarehouseSteel",(0,-.1,0),(58,.2,3.1))
    for x in range(-28,29,2):
        b.box("NWHandrail",(x,.025,0),(1.99,.05,3.05),bevel=.005)
    for side in (-1,1):
        z=side*1.61
        b.solid("NWWarehouseSteel",(0,-.34,z),(58,.45,.16))
        b.solid("NWWarehouseSteel",(0,1.3,z),(58,.07,.09))
        b.collide((0,.65,z),(58,1.3,.08))
        for x in range(-29,30,3):
            b.box("NWWarehouseSteel",(x,.6,z),(.09,1.4,.09))
            if x<27:
                b.cyl("NWWarehouseSteel",(x,0,z),(x+3,1.25,z),.025,8)
                b.cyl("NWWarehouseSteel",(x,1.25,z),(x+3,0,z),.025,8)
    return b,dict(kind="footbridge",length=58,width=3.2,height=1.4)


def build_cabinet(kind):
    b=Architecture()
    chest=kind=="chest"; kitchen=kind=="kitchen"
    w,h,d=(1.2,.72,.6) if chest else ((1.2,.88,.62) if kitchen else (1.05,1.92,.58))
    mat="WoodPlanks" if chest else "NWFurniture"
    # Корпус из панелей, утопленные фасады, цоколь, полки, ручки и петли.
    b.solid(mat,(0,h/2,0),(w,h,d),bevel=.025)
    for i in range(2):
        x=(i-.5)*w/2
        b.box("NWTrim",(x,h*.52,d/2+.015),(w/2-.035,h*.87,.035),bevel=.012)
        b.cyl("Galv",(x+w*.15,h*.5,d/2+.07),(x+w*.15,h*.65,d/2+.07),.012,10)
        for yy in (.16,.8):
            b.box("Galv",(x-w*.22,h*yy,d/2+.04),(.025,.075,.016),bevel=.003)
    if chest:
        b.box(mat,(0,h+.035,0),(w+.035,.07,d+.035),bevel=.025)
        for x in (-w*.33,w*.33): b.box("Railing",(x,h/2,d/2+.04),(.045,h*.8,.025))
    if kitchen:
        b.box("NWEnamel",(0,h+.025,0),(w+.04,.05,d+.05),bevel=.015)
        # Мойка и кран с заметной чашей и бортом.
        b.box("Galv",(-.25,h+.055,0),(.45,.018,.37),bevel=.04)
        b.cyl("Galv",(-.25,h+.07,-.18),(-.25,h+.34,-.18),.016,12)
        b.cyl("Galv",(-.25,h+.34,-.18),(-.25,h+.34,.02),.016,12)
    return b,dict(kind=kind,width=w,height=h,depth=d)


def export(name,b,info):
    assert all(min(c["size"]) > 0 for c in b.collisions), name+": nonpositive collision"
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
    obj=b.to_object(name)
    bpy.context.view_layer.objects.active=obj; obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")),export_format="GLB",use_selection=True,
                              export_yup=True,export_texcoords=True,export_normals=True,
                              export_materials="EXPORT",export_animations=False)
    info.update(triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),collisions=b.collisions,materials=sorted(b.data))
    # Сохраняем редактируемую производную; утверждённые исходники прежнего фасада не трогаем.
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/(name+"_v01.blend")))
    print("NW_ASSET",name,info["triangles"],"triangles",len(b.collisions),"colliders",flush=True)
    return info


def main():
    OUT.mkdir(parents=True,exist_ok=True); SOURCE.mkdir(parents=True,exist_ok=True)
    models={"panel_playable":build_panel(),"market_hangar":build_hangar(),
            "house_attic":build_house(),"house_mansard":build_house(mansard=True),
            "house_closed":build_house(attic=False,closed=True),"garden_shed":build_shed(),
            "garden_fence":build_garden_fence(),"ravine_bridge":build_bridge()}
    for palette in range(3):
        for opened in (False,True):
            models[f"market_stall_{palette}_{'open' if opened else 'closed'}"]=build_stall(opened,palette)
    for kind in ("kitchen",): models[kind]=build_cabinet(kind)
    manifest={name:export(name,*data) for name,data in models.items()}
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")


if __name__=="__main__": main()
