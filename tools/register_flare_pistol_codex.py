"""Register the Codex flare asset without changing existing firearm definitions."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"data"/"weapons.json"
w=json.loads(path.read_text(encoding="utf-8"))
ip=ROOT/"data"/"items.json"
items=json.loads(ip.read_text(encoding="utf-8"))
asset="res://assets/models/weapons/flare_pistol_codex/"
old_launcher=items["items"].pop("signal_launcher",w["weapons"].get("signal_launcher",{}))
red=items["items"].pop("flare",w["ammo"].get("flare",{}))
green=items["items"].pop("supply_signal",w["ammo"].get("supply_signal",{}))
w["calibers"]["signal_26"]={"name":"Сигнальный патрон"}
w["models"]["flare_pistol_codex"]={"anim":"pistol","sockets":{}}
launcher=dict(old_launcher)
launcher.update(name="Компактная сигнальная ракетница",cat="weapon",size=[1,2],short="РАКЕТНИЦА",raid_only=True,
                desc="Однозарядная переломная ракетница. Красный патрон освещает местность, зелёный вызывает снабжение. Взять во вторичный слот; B выбирает тип следующего патрона, R раскрывает ствол, заряжает и взводит курок. ЛКМ — выстрел. Тип также выбирается через меню патрона в рюкзаке. Зелёный сигнал требует открытого неба и свободной площадки.")
launcher["model"]=asset+"flare_pistol_codex.glb"
launcher["weapon"]={"slot":"secondary","class":"PISTOL","caliber":"signal_26","model":"flare_pistol_codex",
                    "asset":asset+"flare_pistol_codex.glb","scale":1,"length":.1981,"internal_mag":1,
                    "mechanism":"break_action","mounts":{},"sound":"shot_pistol","reload_sound":"reload_pistol","cycle_sound":"",
                    "hand_grips":{"right":{"pos":[0,0,0],"fingers":[0,1,.12],"thumb":[-1,0,0],"curl":[55,75,45]},
                                  "left":{"pos":[.02,-.029,-.006],"fingers":[0,1,.1],"thumb":[1,0,0],"curl":[50,70,40]}},
                    "stats":{"spread":1,"ads_spread":.5,"ads_fov":65,"kick":.011,"kick_h":.004,"kick_bias":.1,
                             "recover":.4,"shake":.055,"ergo":75,"rpm":60,"auto":False,"reload":155/30,
                             "reload_empty":155/30,"range":80,"noise":60,"reliability":1,"wear":.012},
                    "rig":{"mechanism":"break_action","ads_z":.32,"shot_duration":23/30,
                           "barrel_open_deg":48,"hammer_cocked_deg":-19.480565,"trigger_angle_deg":-9.740283,
                           "reload":{"open_start":15/155,"open_end":29/155,"close_start":118/155,"close_end":127/155,
                                     "insert_start":90/155,"insert_end":109/155,"cock_start":130/155,"cock_end":143/155}},
                    "viewmodel":{"scene":asset+"flare_pistol_codex_viewmodel.glb","fps":30,"mechanism":"break_action",
                                 "clips":{"idle":"idle","idle_empty":"idle_empty","draw":"draw","reload":"reload_live",
                                          "reload_empty":"reload_empty","shot":"fire","holster":"holster"},
                                 "ads_z":.32,"hip_offset":[0,0,.015],"round_windows":{"old":[1,65],"new":[73,156]},
                                 "left_hand_windows":[[1,36],[70,117]],
                                 "events":{"open":30,"chamber_down":42,"shake_1":48,"shake_2":56,"case_free":58,
                                           "upright":70,"insert":110,"snap":123,"close":128,"cock":144}}}
w["weapons"]["signal_launcher"]=launcher
clearance_path = ROOT / "assets/models/weapons/flare_pistol_codex/clearance_boxes.json"
if clearance_path.exists():
    launcher["weapon"]["viewmodel"]["clearance_parts"] = json.loads(clearance_path.read_text(encoding="utf-8"))
for iid,item,effect,model,name in [("flare",red,"illumination","flare_red_codex.glb","Осветительный патрон — красный"),
                                   ("supply_signal",green,"airdrop","flare_green_codex.glb","Сигнальный патрон снабжения — зелёный")]:
    item=dict(item)
    item.update(name=name,cat="ammo",model=asset+model,
                ammo={"caliber":"signal_26","effect":effect,"damage":0,"pen":0,"armor_dmg":0,"pellets":1,"velocity":45})
    if iid=="flare":
        item["desc"]="Красный патрон для ракетницы: освещает местность 15 секунд. Выбрать для заряжания через меню патрона или B с ракетницей в руках, затем R и ЛКМ. Без ракетницы B по-прежнему зажигает осветительную ракету на земле."
    else:
        item["raid_only"]=True
        item["desc"]="Зелёный патрон для вызова airdrop. Выбрать для ракетницы, зарядить R и выстрелить ЛКМ под открытым небом у свободной площадки. Один сброс на рейд. Отказ вызова сохраняет патрон."
    w["ammo"][iid]=item
for target,data in ((path,w),(ip,items)):
    target.write_text(json.dumps(data,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
for name in ("flare_pistol_codex","flare_pistol_codex_viewmodel","flare_red_codex","flare_green_codex"):
    settings=ROOT/"assets/models/weapons/flare_pistol_codex"/(name+".glb.import")
    if settings.exists():
        text=settings.read_text(encoding="utf-8")
        text=text.replace("gltf/embedded_image_handling=1","gltf/embedded_image_handling=2")
        settings.write_text(text,encoding="utf-8")
credit="""\n\n## Компактная ракетница Codex (`assets/models/weapons/flare_pistol_codex/`)

Собственные игровые модели и материалы проекта, авторинг Codex по фотографиям владельца:
`flare_pistol_codex.glb`, `flare_red_codex.glb`, `flare_green_codex.glb` и FPS-версия
`flare_pistol_codex_viewmodel.glb`. Нативный UCUPaint worn_v01, исправления пазов/бойка,
уникальная UV, PBR и normal bake — собственная работа. Публичные фотографии и превью
Sketchfab использованы как ориентир формы; сторонние сетки/текстуры и логотипы не заимствованы.
Руководство Orion — https://www.orionsignals.com/wp-content/uploads/2021/02/SM_ALinsertw_Safety-WebVersion-1.21v4.pdf —
источник общей последовательности действий; отдельный боёк — визуальная реконструкция для игры.
FPS-руки, их сетка, материалы и веса повторно использованы из собственных ассетов владельца
ВЕРАС-54 (`VERAS54_Reload_Full_v05.blend`); источник не перезаписан. Новые клипы ракетницы — Codex.
Оценочные размеры ракетницы 198 × 33 × 130 мм, 12 348 треугольников; каждый патрон — 1 072;
FPS с руками и патронами — 21 396. Скрипты: `tools/prepare_flare_pistol_codex.py`,
`tools/animate_flare_pistol_codex.py`. Исходники — `_asset_src/flare_pistol_codex/` и
`E:/Models Blender/Ракетница — Codex/game_codex/`. Подробности: `docs/assets/flare_pistol_codex.md`.
"""
for name in ("CREDITS.md","ASSET_CREDITS.md"):
    target=ROOT/"assets"/name
    text=target.read_text(encoding="utf-8")
    if "## Компактная ракетница Codex" not in text:
        target.write_text(text+credit,encoding="utf-8")
print("REGISTERED signal_launcher, flare, supply_signal")
