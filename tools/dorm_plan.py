# -*- coding: utf-8 -*-
"""Поэтажные срезы общежития: фактические стены и центральная лестница."""
from __future__ import annotations
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont


def draw_plan(plan: dict, path: Path) -> None:
    image=Image.new("RGB",(3000,1700),"#f2f3f1")
    d=ImageDraw.Draw(image)

    def font(n=22,bold=False):
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",n)

    def text(x,y,s,n=22,color="#30383d",bold=False):
        d.multiline_text((x,y),s,font=font(n,bold),fill=color,spacing=7)

    text(50,28,f"RING  /  ОБЩЕЖИТИЕ · ПЛАНИРОВКА {plan['version']}",38,bold=True)
    text(50,83,"Центральная лестница напротив гостиной · разные комнаты · вход с вахтой и турникетом · чёрный выход",25)
    k,xmin,zmin=17,-1.2,min(p[1] for p in plan["outline"])-1.1
    core=plan["stair_core"]
    for f in range(3):
        ox,oy=50+f*990,210
        fy=plan["scale"]["floor_y"][f]
        text(ox,145,f"{f+1} ЭТАЖ · пол +{fy:.2f} м · потолок {plan['scale']['ceiling_clear'][f]:.1f} м",25,bold=True)

        def pt(x,z):
            return (ox+(x-xmin)*k,oy+(z-zmin)*k)

        def rect(r,color):
            d.rectangle([pt(r[0],r[1]),pt(r[2],r[3])],fill=color)

        d.polygon([pt(*p) for p in plan["outline"]],fill="#d2d6d7")
        for area in plan["circulation"]:
            if area["floor"]==f+1:
                rect(area["rect"],"#e9e3d7")
        rect(core["rect"],"#c4d3d9")
        for s in plan["spaces"]:
            if s["floor"]!=f+1 or not s["open"]:
                continue
            color={"room":"#f9f9f5","lounge":"#d7e6df","storage":"#e5e0d7","commandant":"#e5d7c4","stairs":"#c4d3d9"}.get(s["kind"],"#dce5e5")
            if "polygon" in s:
                d.polygon([pt(*p) for p in s["polygon"]],fill=color)
            else:
                rect(s["rect"],color)
        for key,section in plan["sections"].items():
            if key in ["Site","Roof"]:
                continue
            for geometry in [section,*section.get("groups",{}).values()]:
                for box in geometry["boxes"]:
                    x,y,z=box["at"]
                    sx,sy,sz=box["size"]
                    if not y-sy/2<=fy+1.4<=y+sy/2:
                        continue
                    mat=box["mat"]
                    color={"glass":"#a9cbd3","mattress":"#c4bba7","wood":"#918375","tile":"#a8bbb4","mirror":"#83b7c4"}.get(mat,"#465158")
                    if mat=="sealed" or "_bar" in box["id"]:
                        color="#a15745"
                    rect([x-sx/2,z-sz/2,x+sx/2,z+sz/2],color)
                for leaf in geometry.get("doors",[]):
                    x,y,z=leaf["at"]
                    if abs(y-fy)>.1:
                        continue
                    yaw=math.radians(leaf["yaw_closed"]+leaf["swing_sign"]*leaf["angle"])
                    def corner(a,b):
                        return pt(x+math.cos(yaw)*a+math.sin(yaw)*b,z-math.sin(yaw)*a+math.cos(yaw)*b)
                    points=[corner(0,-.02),corner(leaf["width"],-.02),corner(leaf["width"],.02),corner(0,.02)]
                    d.polygon(points,fill="#596350" if leaf["mat"]=="door_green" else "#75634f")
                    d.line([corner(0,0),corner(leaf["width"],0)],fill="#7d453c" if leaf["grille"] else "#75634f",width=2)
        for s in plan["spaces"]:
            if s["floor"]!=f+1 or not s["open"]:
                continue
            r=s["rect"]
            cx,cz=(r[0]+r[2])/2,(r[1]+r[3])/2
            name={"wash":"УМЫВ.","laundry":"СТИРКА","turn":"ПОВОРОТ","lounge":"ГОСТИНАЯ","storage":"КЛАД.",
                  "stairs":"ЛЕСТН.","commandant":"КОМЕНД.","watch":"ВАХТА","hall":"ХОЛЛ"}.get(s["kind"],s["label"])
            if s["kind"]=="room":
                cz=-4.6 if cz<0 else 4.6
                name+=f"\n×{s['width_scale']:.1f}"
            px,py=pt(cx,cz)
            ft=font(14,True)
            for j,line in enumerate(name.splitlines()):
                width=d.textbbox((0,0),line,font=ft)[2]
                d.text((px-width/2,py-10+j*18),line,font=ft,fill="#27363d")
        for stair in plan["stairs"]:
            if stair["floor"]!=min(f+1,2):
                continue
            a,b=stair["start"],stair["end"]
            d.line([pt(a[0],a[2]),pt(b[0],b[2])],fill="#acb4ba",width=25)
            for j in range(stair["count"]+1):
                z=a[2]+(b[2]-a[2])*j/stair["count"]
                d.line([pt(a[0]-.75,z),pt(a[0]+.75,z)],fill="#535f68",width=1)
        main=next(a["rect"] for a in plan["circulation"] if a["floor"]==f+1 and a["rect"][1]>-2)
        annex=next(a["rect"] for a in plan["circulation"] if a["floor"]==f+1 and a["rect"][1]<-2)
        cx=core["center_x"]
        ax=(annex[0]+annex[2])/2
        route=[pt(1.95,0),pt(cx,0),pt(cx,3.8),pt(cx+4,3.8),pt(cx,3.8),pt(cx,0),pt(ax,0),pt(ax,-28.2)]
        d.line(route,fill="#628e82",width=3)
        if f==0:
            d.line([pt(1.95,14),pt(1.95,8.4),pt(2.65,5.4),pt(1.95,0)],fill="#628e82",width=3)
            d.line([pt(main[2]-2,0),pt(main[2]+3.8,0)],fill="#628e82",width=3)
            px,py=pt(main[2]+.8,1)
            text(px,py,"Чёрный\nвыход",16)
        text(ox+20,oy+140,"СЕВЕР ↑\n\nЛестница в середине:\nдва марша по 1,5 м,\nмежду ними 30 см,\nсбоку пустот нет.\n\nЗа поворотом — службы.\nДальняя часть заварена.",20)
        rooms=[s for s in plan["spaces"] if s["floor"]==f+1 and s["open"] and s["kind"]=="room"]
        depth=f"{plan['scale']['room_depth']:.1f}".replace(".",",")
        corridor=f"{plan['scale']['corridor_clear']:.2f}".replace(".",",")
        text(ox,1160,f"{len(rooms)} жилых комнат · глубина {depth} м",24,bold=True)
        text(ox,1200,f"Ширина 3,9 / 5,07 / 5,46 / 5,85 м\nКоридор {corridor} м · створки окон +15%\nГабариты двухъярусных кроватей 1:1\nЗелёная нижняя часть стен, белый верх.",22)
        if f==0:
            text(ox,1350,"Тамбур → вахта / турникет → туалет\n→ комнаты → лестница / гостиная\n→ комнаты, комендант, чёрный выход.",22)
        if f==2:
            text(ox,1350,"Подъём на 4–5 этажи перекрыт.\nФинальная отделка ещё не начата.",22,"#994e3a",True)
    text(50,1510,"Белое — жилые комнаты; зелёное — гостиная; голубое — службы; песочное — комендант; красное — преграды.",24)
    text(50,1560,f"Этап 1, редакция {plan['version']}. Масштаб прежний; порталы, двери на петлях, подоконники, батареи. Всё новое — отдельными группами.",23)
    d.line([(55,1640),(225,1640)],fill="#30383d",width=3)
    text(245,1622,"10 м · одинаковый масштаб трёх этажей",22)
    path.parent.mkdir(parents=True,exist_ok=True)
    image.save(path)


if __name__=="__main__":
    import json
    root=Path(__file__).resolve().parent.parent
    draw_plan(json.loads((root/"data/blockouts/dorm.json").read_text(encoding="utf-8")),root/"docs/plans/dorm.png")
