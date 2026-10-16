"""Исследование в метрах по плану владельца; исходный PNG никогда не изменяется."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SCALE = 0.8
ORIGIN = (775, 420)


def point(pixel):
    return [round((pixel[0] - ORIGIN[0]) * SCALE, 3), round((pixel[1] - ORIGIN[1]) * SCALE, 3)]


def points(pixels):
    return [point(p) for p in pixels]


def building(key, label, pixel, size, floors=1, height=3.0, yaw=0, kind="mass", region=2):
    return {"id": key, "label": label, "at": point(pixel), "size": size, "floors": floors,
            "story_height": height, "yaw": yaw, "kind": kind, "region": region, "base_y": 0.0}


buildings = [
    building("Panel_01", "Панельный дом · 5 этажей", (486, 336), [55, 12]),
    building("Panel_02", "Панельный дом · 5 этажей", (522, 365), [52, 12], yaw=90),
    building("Panel_03", "Панельный дом · 5 этажей", (441, 393), [53, 12], yaw=90),
    building("Panel_04", "Панельный дом · 5 этажей", (520, 443), [56, 12], yaw=90),
    building("Panel_05", "Панельный дом · 5 этажей", (482, 484), [44, 12]),
    building("Panel_06_Enterable", "Жилой дом · сквозной проход и лестница", (589, 409), [56, 12], yaw=90, kind="apartments"),
    building("Panel_07", "Панельный дом · 5 этажей", (642, 452), [62, 12], yaw=90),
    building("Panel_08", "Панельный дом · 5 этажей", (693, 380), [40, 12], yaw=20),
    building("Panel_09", "Панельный дом · 5 этажей", (747, 414), [48, 12], yaw=90),
    building("Panel_10", "Панельный дом · 5 этажей", (605, 520), [56, 12]),
    building("Panel_11", "Панельный дом · 5 этажей", (725, 482), [48, 12], yaw=70),
    building("Swamp_Service_Hut", "Служебная постройка у затопления", (412, 282), [20, 11], height=3.3, yaw=85, kind="hall", region=1),
    building("Swamp_Pump", "Опорная постройка на берегу", (617, 284), [28, 10], height=3.8, kind="hall", region=1),
    building("Northern_Service", "Закрытый технический корпус", (861, 138), [62, 17], height=5, region=3),
    building("Construction_09F", "Недострой · 9 этажей, высота 28,8 м", (904, 248), [64, 28], floors=9, height=3.2, kind="skeleton", region=3),
    building("Construction_05F", "Недострой · 5 этажей, высота 16 м", (934, 320), [52, 26], floors=5, height=3.2, yaw=90, kind="skeleton", region=3),
    building("Crane", "Башенный кран · 38 м", (866, 303), [6, 6], height=38, yaw=20, kind="crane", region=3),
    building("Site_Hut_A", "Бытовка стройки", (807, 233), [9, 3], height=2.7, yaw=90, region=3),
    building("Site_Hut_B", "Бытовка стройки", (813, 316), [9, 3], height=2.7, yaw=90, region=3),
    building("Sports_Club", "Спортивный павильон", (925, 545), [38, 14], height=4, kind="hall", region=4),
    building("Sports_Hall", "Спортивный зал", (972, 531), [48, 27], height=8, yaw=90, kind="hall", region=4),
    building("Bus_Terminal", "Автостанция · зал и проход", (811, 655), [68, 18], height=5.5, yaw=90, kind="hall", region=5),
    building("Bus_Repair_Hangar", "Ремонтный ангар", (637, 628), [44, 23], height=7, yaw=-28, kind="hall", region=5),
    building("Bus_Dispatch", "Диспетчерская", (704, 714), [24, 12], floors=2, height=3.1, region=5),
    building("Bus_Gates_Hut", "Пост у выезда", (571, 603), [12, 8], height=3, kind="hall", region=5),
    building("Station", "Железнодорожная станция", (1058, 614), [51, 16], height=6, yaw=73, kind="hall", region=6),
    building("Rail_Warehouse", "Железнодорожный склад", (1081, 538), [48, 18], height=6, yaw=73, kind="hall", region=6),
    building("Rail_Workshop", "Мастерская", (1081, 685), [27, 17], height=5, yaw=73, region=6),
]
for b in buildings[:11]:
    b["floors"] = 5
for i in range(3):
    buildings.append(building(f"Bus_Canopy_{i+1}", "Пассажирский перрон", (739, 606 + i*29), [57, 4], height=4.2, kind="canopy", region=5))
for i, pixel in enumerate([(715,609), (758,635), (703,666), (751,691), (656,689), (604,638)]):
    buildings.append(building(f"Bus_{i+1}", "Габарит автобуса · 12 м", pixel, [12, 2.6], height=3.1, yaw=0 if i != 5 else -25, kind="bus", region=5))
for i in range(8):
    buildings.append(building(f"Garage_{i+1:02d}", "Гараж у железной дороги", (1012 + i*5.8, 706 + i*1.3), [4.3, 6.4], height=3.1, yaw=17, region=6))
for i, pixel in enumerate([(844,346),(852,346),(860,346),(807,270),(969,223),(976,223)]):
    buildings.append(building(f"Site_Stack_{i+1}", "Штабель стройматериалов", pixel, [5, 2.6], height=1.4, region=3))


def road(key, width, pixels):
    return {"id": key, "width": width, "points": points(pixels)}


plan = {
    "version": 1, "purpose": "Отдельный проходимый тест масштаба, не замена игровой zone01",
    "reference": "docs/design/concepts/urban_belt_2026-10-15/01_urban_belt_starting_concept.png",
    "scale_m_per_pixel": SCALE, "pixel_origin": list(ORIGIN), "envelope_m": [690,650],
    "north": "-Z", "render_style": "Приглушённый серо-зелёный, пасмурный; материалы условные",
    "boundary": points([(360,50),(485,26),(610,33),(705,66),(798,54),(893,85),(990,95),(1105,128),
                        (1148,268),(1175,440),(1195,560),(1172,680),(1200,810),(1107,801),
                        (1000,779),(925,759),(830,759),(725,752),(634,710),(540,682),
                        (490,644),(440,630),(424,573),(383,457),(379,306),(363,183)]),
    "swamp": points([(403,91),(456,53),(548,54),(610,93),(678,83),(713,102),(787,92),
                     (815,117),(804,175),(782,210),(773,262),(745,303),(704,321),
                     (659,293),(634,252),(568,273),(503,264),(450,240),(410,215),(398,166)]),
    "dry_ridges": [points([(399,158),(441,175),(475,151),(515,162),(548,196),(586,201),
                            (617,230),(656,247),(671,280),(701,302)]),
                    points([(488,74),(521,98),(558,116),(606,112),(647,144),(677,171),
                            (724,179),(773,191),(788,209)])],
    "swamp_remains": points([(583,181)]),
    "river": points([(1090,84),(1093,139),(1094,216),(1101,270),(1118,310)]),
    "tracks": points([(1106,468),(1146,555),(1148,647),(1121,724),(1145,787)]),
    "platform": points([(1108,550),(1117,620),(1100,691)]),
    "sports_at": point((862,470)),
    "pads": [{"at":point((889,283)),"size":[139,142],"yaw":0},
             {"at":point((730,646)),"size":[133,113],"yaw":0},
             {"at":point((1063,621)),"size":[53,112],"yaw":-17}],
    "roads": [
        road("west_forest",7,[(361,48),(384,110),(393,175),(382,253),(392,323),(391,412),(418,480),(446,554),(423,600),(368,636)]),
        road("northern_residential",8,[(390,307),(456,302),(548,306),(637,312),(710,337),(788,358),(891,391),(990,416)]),
        road("residential_spine",8,[(548,306),(554,372),(553,466),(556,538),(534,563)]),
        road("south_artery",9,[(446,554),(534,563),(618,551),(712,555),(797,582),(890,613),(985,642),(1027,701),(1089,752),(1174,789)]),
        road("central_artery",9,[(712,555),(739,496),(763,437),(788,358),(797,287),(809,193),(920,211),(1018,226)]),
        road("east_artery",9,[(986,72),(946,143),(943,187),(1004,201),(1037,171),(1065,142),(1090,142)]),
        road("east_to_mall",10,[(1018,226),(1016,279),(1012,325),(1090,337),(1195,355)]),
        road("station_artery",9,[(1012,325),(1007,407),(1005,455),(1022,482),(1005,543),(1001,587),(985,642)]),
        road("sports_north",6,[(763,437),(825,418),(905,420),(1005,455)]),
        road("sports_south",6,[(739,496),(788,543),(887,568),(968,603),(1001,587)]),
        road("bus_west_access",6,[(575,570),(575,615),(590,666),(650,706),(747,726),(819,722),(828,608)]),
        road("rail_service",5,[(1022,482),(1075,466),(1102,504),(1112,557),(1088,652),(1100,696)]),
        road("panel_west_court",3,[(405,349),(471,351),(479,399),(470,453),(420,468)]),
        road("panel_east_court",3,[(563,344),(608,344),(681,352),(713,401),(706,474),(675,497),(654,495)]),
        road("residential_to_court",2.3,[(655,498),(702,511),(739,496),(802,483)]),
        road("swamp_south_walk",2.1,[(412,294),(468,289),(530,287),(592,290),(644,300),(701,302),(749,323),(797,333)]),
    ],
    "buildings": buildings,
    "locations": [
        {"id":1,"label":"БОЛОТО","at":point((556,151)),"spawn":point((430,294)),"look":point((556,151))},
        {"id":2,"label":"ПАНЕЛЬНЫЕ ДОМА","at":point((614,440)),"spawn":point((553,538)),"look":point((553,365))},
        {"id":3,"label":"НЕДОСТРОЙ","at":point((918,290)),"spawn":point((832,280)),"look":point((904,248))},
        {"id":4,"label":"СПОРТПЛОЩАДКА","at":point((862,470)),"spawn":point((796,485)),"look":point((862,470))},
        {"id":5,"label":"АВТОСТАНЦИЯ","at":point((760,656)),"spawn":point((695,587)),"look":point((780,656))},
        {"id":6,"label":"ЖЕЛЕЗНАЯ ДОРОГА","at":point((1075,620)),"spawn":point((1023,645)),"look":point((1117,620))},
    ],
    "exits": [{"label":"Лесная дорога","at":point((370,84))},
              {"label":"Служебный выезд","at":point((423,600))},
              {"label":"Железнодорожный подход","at":point((1145,776))},
              {"label":"Старый мост","at":point((1073,143))},
              {"label":"Направление к ТЦ","at":point((1172,351))}],
    "probe_routes": [
        {"id":"residential_street","points":points([(553,532),(553,466),(554,372),(548,312)])},
        {"id":"bus_to_sports","points":points([(575,574),(618,551),(712,555),(739,496),(763,437),(825,418)])},
        {"id":"construction_to_station","points":points([(1018,250),(1012,325),(1007,407),(1005,455),(1022,482),(1005,543),(1001,587),(985,642)])},
        {"id":"swamp_dry_ridge","points":points([(399,158),(441,175),(475,151),(515,162),(548,196),(586,201),(617,230),(656,247),(671,280),(701,302)])},
    ],
}


def area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly, poly[1:]+poly[:1])))/2


plan["boundary_area_m2"] = round(area(plan["boundary"]),1)
plan["swamp_polygon_area_m2"] = round(area(plan["swamp"]),1)
data_dir = ROOT / "data/blockouts"
data_dir.mkdir(parents=True, exist_ok=True)
(data_dir / "urban_belt_study.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

scene = ['[gd_scene format=3]',
         '[ext_resource type="Script" path="res://src/blockout/study_landscape.gd" id="1_land"]',
         '[ext_resource type="Script" path="res://src/blockout/study_building.gd" id="2_build"]',
         '[sub_resource type="ProceduralSkyMaterial" id="SkyMat"]',
         'sky_top_color = Color(0.37, 0.43, 0.46, 1)',
         'sky_horizon_color = Color(0.63, 0.67, 0.65, 1)',
         'ground_bottom_color = Color(0.28, 0.32, 0.29, 1)',
         'ground_horizon_color = Color(0.63, 0.67, 0.65, 1)',
         'sun_angle_max = 0.5',
         '[sub_resource type="Sky" id="Sky"]', 'sky_material = SubResource("SkyMat")',
         '[sub_resource type="Environment" id="Environment"]',
         'background_mode = 2', 'sky = SubResource("Sky")',
         'ambient_light_source = 3', 'ambient_light_color = Color(0.66, 0.72, 0.75, 1)',
         'ambient_light_energy = 0.50', 'reflected_light_source = 2',
         'tonemap_mode = 2', 'tonemap_exposure = 1.05',
         'fog_enabled = true', 'fog_light_color = Color(0.57, 0.63, 0.61, 1)',
         'fog_light_energy = 0.65', 'fog_density = 0.0004',
         'ssao_enabled = true', 'ssao_radius = 1.5', 'ssao_intensity = 1.3',
         '[node name="UrbanBeltStudy" type="Node3D"]',
         'metadata/purpose = "Отдельный масштабный тест по рисунку владельца · 2026-10-16"',
         '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
         'environment = SubResource("Environment")',
         '[node name="OvercastSun" type="DirectionalLight3D" parent="."]',
         'rotation_degrees = Vector3(-48, -38, 0)',
         'light_color = Color(0.88, 0.91, 0.87, 1)', 'light_energy = 0.75',
         'light_angular_distance = 5.0', 'shadow_enabled = true',
         'directional_shadow_max_distance = 150.0',
         '[node name="Landscape" type="Node3D" parent="."]', 'script = ExtResource("1_land")']
for region_id, region in enumerate(["Swamp", "Residential", "Construction", "Sports", "BusStation", "Railway"],1):
    scene.append(f'[node name="{region}" type="Node3D" parent="."]')
    for b in buildings:
        if b["region"] != region_id:
            continue
        scene.extend([f'[node name="{b["id"]}" type="Node3D" parent="{region}"]',
                      f'position = Vector3({b["at"][0]}, {b["base_y"]}, {b["at"][1]})',
                      f'rotation_degrees = Vector3(0, {b["yaw"]}, 0)', 'script = ExtResource("2_build")',
                      f'kind = "{b["kind"]}"',f'footprint = Vector2({b["size"][0]}, {b["size"][1]})',
                      f'floors = {b["floors"]}',f'story_height = {b["story_height"]}',
                      f'label = "{b["label"]}"'])
dest = ROOT / "scenes/levels/urban_belt_study.tscn"
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text("\n\n".join(scene)+"\n",encoding="utf-8")
report = {"envelope_m":plan["envelope_m"],"boundary_area_m2":plan["boundary_area_m2"],
          "swamp_polygon_area_m2":plan["swamp_polygon_area_m2"],"buildings":len(buildings),
          "source_scale":"0.8 м/пиксель, рабочее предположение по домам и проездам",
          "roads":len(plan["roads"]),"tallest_building_m":28.8,"crane_m":38}
(ROOT / "docs/design/urban_belt_study_dimensions.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
