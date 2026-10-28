# -*- coding: utf-8 -*-
"""Поэтажный срез Г-образного общежития из тех же данных, что строят коллизии."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def draw_plan(plan: dict, path: Path) -> None:
    image = Image.new("RGB", (3000, 1700), "#f2f3f1")
    d = ImageDraw.Draw(image)

    def font(n=22, bold=False):
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", n)

    def text(x, y, s, n=22, color="#30383d", bold=False):
        d.multiline_text((x,y),s,font=font(n,bold),fill=color,spacing=7)

    text(50,28,"RING  /  ОБЩЕЖИТИЕ · ЭТАП 1",38,bold=True)
    text(50,83,"Отдельный серый стенд · гостиная с нишей · хозяйственное крыло за поворотом · север вверху",25)
    k, xmin, zmin = 17, -9.6, -41.2
    colors = {"room":"#f9f9f5","lounge":"#d7e6df","storage":"#e5e0d7"}
    for f in range(3):
        ox, oy = 50+f*990, 210
        fy = plan["scale"]["floor_y"][f]
        text(ox,145,f"{f+1} ЭТАЖ · пол +{fy:.2f} м · потолок {plan['scale']['ceiling_clear'][f]:.1f} м",25,bold=True)

        def pt(x,z):
            return (ox+(x-xmin)*k,oy+(z-zmin)*k)

        def rect(r,color):
            d.rectangle([pt(r[0],r[1]),pt(r[2],r[3])],fill=color)

        d.polygon([pt(*p) for p in plan["outline"]],fill="#d2d6d7")
        rect([0,-1.65,32.55,1.65],"#e9e3d7")
        rect([29.25,-40,32.55,-9.83],"#e9e3d7")
        for s in plan["spaces"]:
            if s["floor"]!=f+1 or not s["open"]:
                continue
            color = colors.get(s["kind"],"#dce5e5")
            if "polygon" in s:
                d.polygon([pt(*p) for p in s["polygon"]],fill=color)
            else:
                rect(s["rect"],color)
        for sec in [f"Floor{f+1}","WestStair","EastStair","NorthAnnex"]:
            for b in plan["sections"][sec]["boxes"]:
                x,y,z=b["at"]
                sx,sy,sz=b["size"]
                if not y-sy/2<=fy+1.4<=y+sy/2:
                    continue
                color = "#9bb8c3" if b["mat"]=="glass" else "#465158"
                if b["mat"]=="sealed" or "gate" in b["id"]:
                    color="#a15745"
                rect([x-sx/2,z-sz/2,x+sx/2,z+sz/2],color)
        for s in plan["spaces"]:
            if s["floor"]!=f+1 or not s["open"]:
                continue
            r=s["rect"]
            cx,cz=(r[0]+r[2])/2,(r[1]+r[3])/2
            name={"wash":"УМЫВ.","laundry":"СТИРКА","turn":"ПОВОРОТ","lounge":"ГОСТИНАЯ\nС НИШЕЙ","storage":"КЛАД."}.get(s["kind"],s["label"])
            if s["kind"]=="lounge":
                cx,cz=12.2,5.8
            if s["kind"]=="stairs":
                cx,cz=-4.5,2.8
                name="ЛЕСТНИЦА"
            px,py=pt(cx,cz)
            ft=font(15,True)
            for j,line in enumerate(name.splitlines()):
                width=d.textbbox((0,0),line,font=ft)[2]
                d.text((px-width/2,py-10+j*18),line,font=ft,fill="#27363d")
        for stair in plan["stairs"]:
            if stair["side"]!="west" or stair["floor"]!=min(f+1,2):
                continue
            a,b=stair["start"],stair["end"]
            d.line([pt(a[0],a[2]),pt(b[0],b[2])],fill="#acb4ba",width=25)
            for j in range(stair["count"]+1):
                x=a[0]+(b[0]-a[0])*j/stair["count"]
                d.line([pt(x,a[2]-.75),pt(x,a[2]+.75)],fill="#535f68",width=1)
        route=[pt(2.1,13.9),pt(2.1,0),pt(10,0),pt(10,4),pt(18.5,4),pt(18.5,0),pt(30.9,0),pt(30.9,-27)]
        d.line(route,fill="#628e82",width=3)
        text(ox+30,oy+150,"Открыты комнаты,\nобщая зона и службы.\n\nЗа красной решёткой\nвидно продолжение\nхозяйственного крыла.",20)
        text(ox+30,oy+345,"СЕВЕР ↑",22,bold=True)
        rooms=[s for s in plan["spaces"] if s["floor"]==f+1 and s["open"] and s["kind"]=="room"]
        text(ox,1160,f"{len(rooms)} жилых комнат 3,9 × 7,8 м",24,bold=True)
        text(ox,1200,"Коридор 3,30 м · гостиная ≈ 76 м²\nДвери 1,17 × 2,42 м · марш 1,50 м\nКухня / умывальня / душевые / туалеты\nрасположены за поворотом, с окнами.",22)
        if f==0:
            text(ox,1350,"Вход через крыльцо, тамбур и холл.\nВахта напротив. Лестница слева.",22)
        if f==2:
            text(ox,1350,"Подъём на 4–5 этажи перекрыт\nзаваренной решёткой.",22,"#994e3a",True)
    text(50,1510,"Белое — жилые комнаты; зелёное — гостиная; голубое — общие службы; красное — физическая преграда.",24)
    text(50,1560,"Здание 5-этажное. Открыты этажи 1–3; верхние два и дальняя часть хозкрыла закрыты. Мебель и отделка — следующие этапы.",23)
    a=(55,1640)
    d.line([a,(a[0]+170,a[1])],fill="#30383d",width=3)
    text(245,1622,"10 м  ·  масштаб схемы одинаков на всех этажах",22)
    path.parent.mkdir(parents=True,exist_ok=True)
    image.save(path)


if __name__=="__main__":
    import json
    root=Path(__file__).resolve().parent.parent
    draw_plan(json.loads((root/"data/blockouts/dorm.json").read_text(encoding="utf-8")),root/"docs/plans/dorm.png")
