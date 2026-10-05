"""Запись вручную заданного городского плана в редактируемые сцены Godot.

Случайного размещения и генерации планировки во время игры нет. Повторный запуск
перезаписывает сцены районов; после изменений нужно перепечь навигацию.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scenes/levels/zone02"
BOUNDARY = [
    [-750, -535], [-660, -625], [-350, -625], [-90, -620],
    [175, -625], [650, -625], [750, -535], [746, -350],
    [750, -90], [743, 160], [750, 390], [750, 535],
    [660, 625], [320, 625], [0, 620], [-250, 625],
    [-660, 625], [-750, 535], [-750, 430], [-745, 180],
    [-750, -50], [-750, -320],
]
RIVER = [[-820, 505], [-660, 520], [-430, 548], [-210, 557], [-20, 550], [180, 558], [460, 577], [820, 590]]
PADS: list[dict] = []
BUILDINGS: list[dict] = []
ROADS: list[dict] = []
COUNTS = {"residential_corpora": 16, "garage_rows": 10, "bus_platforms": 6,
          "bus_placeholders": 12, "checkpoint_complexes": 3,
          "ai_spawn_points": 12, "extraction_points": 3, "store_parking_spaces": 96}


def base_height(x: float, z: float) -> float:
    return -0.004 * (x + z)


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ground(x: float, z: float) -> float:
    height = base_height(x, z)
    for pad in PADS:
        x0, z0, x1, z1 = pad["rect"]
        distance = max(x0 - x, x - x1, z0 - z, z - z1, 0)
        if distance < 8:
            height = pad["height"] + (height - pad["height"]) * smooth(distance / 8)
    distance = float("inf")
    for a, b in zip(RIVER, RIVER[1:]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz)))
        distance = min(distance, math.hypot(x - a[0] - dx * t, z - a[1] - dz * t))
    if distance < 66:
        height = -11 + (height + 11) * smooth((distance - 40) / 26)
    return round(height, 4)


def gvalue(value) -> str:
    if isinstance(value, Raw):
        return value.text
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return "{" + ", ".join(gvalue(k) + ": " + gvalue(v) for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(gvalue(v) for v in value) + "]"
    return str(round(value, 5)) if isinstance(value, float) else str(value)


class Raw:
    def __init__(self, text: str):
        self.text = text


def v2(x, z):
    return Raw(f"Vector2({x}, {z})")


def v3(x, y, z):
    return Raw(f"Vector3({round(x, 4)}, {round(y, 4)}, {round(z, 4)})")


class Scene:
    def __init__(self, name: str):
        self.resources: dict[str, tuple[str, str]] = {}
        self.nodes: list[str] = [f'[node name="{name}" type="Node3D"]']

    def resource(self, path: str, kind="PackedScene") -> Raw:
        if path not in self.resources:
            self.resources[path] = (str(len(self.resources) + 1), kind)
        return Raw(f'ExtResource("{self.resources[path][0]}")')

    def node(self, name: str, parent=".", scene=None, kind="Node3D", groups=None, **attrs):
        header = f'[node name="{name}" parent="{parent}"'
        if scene:
            header += f" instance={gvalue(self.resource(scene))}"
        else:
            header += f' type="{kind}"'
        if groups:
            header += " groups=" + gvalue(groups)
        header += "]"
        self.nodes.append(header + "\n" + "\n".join(k + " = " + gvalue(v) for k, v in attrs.items()))
        return name if parent == "." else parent + "/" + name

    def props(self, name, x, z, pieces, parent="Props", yaw=0, y=None, surface="concrete"):
        return self.node(name, parent, "res://scenes/world/urban_props.tscn",
                         position=v3(x, ground(x, z) if y is None else y, z),
                         rotation_degrees=v3(0, yaw, 0), surface=surface,
                         pieces=Raw("Array[Dictionary](" + gvalue(pieces) + ")"))

    def save(self, filename: str):
        lines = [f'[gd_scene load_steps={len(self.resources) + 1} format=3]', ""]
        for path, (index, kind) in self.resources.items():
            lines.append(f'[ext_resource type="{kind}" path="{path}" id="{index}"]')
        lines += ["", "\n\n".join(self.nodes), ""]
        (OUT / filename).write_text("\n".join(lines), encoding="utf-8")


def box(at, size, color=(0.57, 0.59, 0.61), collision=False, **kwargs):
    return dict(at=list(at), size=list(size), color=list(color), collision=collision, **kwargs)


def rectangle_pad(x, z, width, depth, height=None):
    height = base_height(x, z) if height is None else height
    PADS.append(dict(rect=[x - width / 2, z - depth / 2, x + width / 2, z + depth / 2], height=height))


def building(scene: Scene, name: str, x, z, width, depth, height, floors=1,
             yaw=0, title="", style="service", doors=True, category="secondary"):
    y = base_height(x, z) + 0.14
    rw, rd = (depth, width) if abs(yaw) == 90 else (width, depth)
    rectangle_pad(x, z, rw + 5, rd + 5, y - 0.04)
    path = scene.node(name, "Buildings", "res://scenes/world/blockout_building.tscn",
                      position=v3(x, y, z), rotation_degrees=v3(0, yaw, 0),
                      size=v2(width, depth), height=height, simple_collision=True,
                      display_name=title)
    if doors:
        scene.node("DoorFront", path, "res://scenes/world/blockout_opening.tscn", position=v3(0, 0, -depth / 2), width=1.6)
        scene.node("DoorRear", path, "res://scenes/world/blockout_opening.tscn", position=v3(width / 4, 0, depth / 2), width=1.6)
    scene.node("Facade", path, script=scene.resource("res://src/world/urban_facade.gd", "Script"),
               floors=floors, style=style, window_pitch=4.5)
    if category in ["landmark", "secondary"]:
        # Штатная группа питания управляет также светом городской застройки.
        for index, dx in enumerate([-width / 3, 0, width / 3] if width > 60 else [0]):
            scene.node(f"InteriorLight_{index}", path, kind="OmniLight3D", groups=["mall_lights"],
                       position=v3(dx, 2.8, 0), light_color=Raw("Color(1, 0.87, 0.72, 1)"),
                       light_energy=1.4, omni_range=min(22, max(width, depth) * .65),
                       distance_fade_enabled=True, distance_fade_begin=120, distance_fade_length=30)
    if category == "landmark":
        for side in [-1, 1]:
            scene.node(f"EntranceLight_{side}", path, kind="OmniLight3D", groups=["mall_lights"],
                       position=v3(side * width / 4, 4.5, depth / 2 + 3),
                       light_color=Raw("Color(1, 0.87, 0.72, 1)"), light_energy=2.2, omni_range=26,
                       distance_fade_enabled=True, distance_fade_begin=180, distance_fade_length=30)
    BUILDINGS.append(dict(name=name, center=[x, z], size=[rw, rd], height=height, category=category))
    return path


def new_district(name):
    scene = Scene(name)
    scene.node("Buildings")
    scene.node("Props", groups=["urban_prop_batches"])
    scene.node("Gameplay")
    return scene


def tree(scene: Scene, name, x, z, height=8, crown=5, parent="Props"):
    COUNTS["trees"] = COUNTS.get("trees", 0) + 1
    scene.props(name, x, z, [
        box((0, height * .32, 0), (.45, height * .64, .45), (.31, .33, .29), True, shape="cylinder", surface="wood"),
        box((0, height * .7, 0), (crown, height * .6, crown), (.25, .43, .26), shape="sphere"),
    ], parent=parent, surface="wood")


def bench(scene, name, x, z, yaw=0):
    scene.props(name, x, z, [box((0, .45, 0), (2, .18, .5), (.47, .44, .39), True),
                            box((0, .83, .21), (2, .62, .12), (.47, .44, .39)),
                            box((-.7, .2, 0), (.12, .4, .4)), box((.7, .2, 0), (.12, .4, .4))], yaw=yaw, surface="wood")


def container(scene, name, x, z, yaw=0):
    scene.props(name, x, z, [box((0, 1.3, 0), (6.05, 2.6, 2.44), (.45, .49, .46), True, surface="metal"),
                            box((0, 1.35, -1.24), (5.8, 2.3, .08), (.27, .32, .3))], yaw=yaw, surface="metal")


def car(scene, name, x, z, yaw=0, color=(.45, .51, .57)):
    scene.props(name, x, z, [box((0, .65, 0), (1.8, .85, 4.4), color, True, surface="metal"),
                            box((0, 1.28, .15), (1.5, .55, 2.2), color),
                            box((0, 1.3, -.98), (1.42, .4, .08), (.16, .23, .27)),
                            box((-.95, .35, -1.25), (.22, .6, .6), (.17, .18, .18)),
                            box((.95, .35, -1.25), (.22, .6, .6), (.17, .18, .18)),
                            box((-.95, .35, 1.25), (.22, .6, .6), (.17, .18, .18)),
                            box((.95, .35, 1.25), (.22, .6, .6), (.17, .18, .18))], yaw=yaw, surface="metal")


def fence(scene, name, a, b, height=2.2, parent="Props", concrete=False):
    x, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    length = math.dist(a, b)
    yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    base_y = ground(x, z)
    panels = max(1, math.ceil(length / 20))
    pieces = []
    for index in range(panels):
        left, right = index / panels, (index + 1) / panels
        samples = [ground(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                   for t in [left + (right - left) * j / 4 for j in range(5)]]
        low, high = min(samples) - .5, max(samples) + height
        at = -length / 2 + (index + .5) * length / panels
        pieces.append(box((at, (low + high) / 2 - base_y, 0),
                          (length / panels + .04, high - low, .7 if concrete else .16),
                          (.5, .52, .53), True, render=concrete,
                          surface="concrete" if concrete else "metal"))
        if not concrete:
            rail_base = samples[2] - base_y
            for level in [height * .3, height * .65, height]:
                pieces.append(box((at, rail_base + level, 0),
                                  (length / panels, .09, .1), (.36, .4, .4)))
    if not concrete:
        for at in range(int(length / 3) + 1):
            t = min(1, at * 3 / length)
            post_y = ground(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) - base_y
            pieces.append(box((-length / 2 + at * 3, post_y + height / 2, 0),
                              (.12, height, .12), (.36, .4, .4)))
    scene.props(name, x, z, pieces, parent=parent, yaw=yaw)


def parking(scene, name, x, z, cols, rows, width=2.5):
    pieces = [box((0, -.02, 0), (cols * width + 14, .12, rows * 12 + 10), (.24, .25, .26), True, surface="asphalt")]
    for row in range(rows):
        row_z = (row - (rows - 1) / 2) * 12
        for col in range(cols + 1):
            pieces.append(box(((col - cols / 2) * width, .05, row_z), (.08, .015, 5), (.8, .81, .78), shadow=False))
        pieces.append(box((0, .05, row_z + 2.5), (cols * width, .015, .08), (.8, .81, .78), shadow=False))
    rectangle_pad(x, z, cols * width + 14, rows * 12 + 10)
    scene.props(name, x, z, pieces, y=base_height(x, z), surface="asphalt")


def loot(scene, name, x, z, title, table="storage", parent="Gameplay", y=None):
    scene.node(name, parent, "res://scenes/world/loot_container.tscn", position=v3(x, ground(x, z) if y is None else y, z),
               display_name=title, table=table, look=5)


def road(scene, name, points, width=8, sidewalk=2.5, markings=True, bridge=False):
    expanded = []
    for a, b in zip(points, points[1:]):
        subdivisions = max(1, math.ceil(math.dist(a, b) / 25))
        for step in range(subdivisions):
            t = step / subdivisions
            x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            expanded.append((x, base_height(x, z) if bridge or (name == "NorthSouthAvenue" and z > 470) else ground(x, z), z))
    x, z = points[-1]
    expanded.append((x, base_height(x, z) if bridge or (name == "NorthSouthAvenue" and z > 470) else ground(x, z), z))
    raw = "PackedVector3Array(" + ", ".join(str(round(v, 4)) for point in expanded for v in point) + ")"
    scene.node(name, "Roads", "res://scenes/world/urban_road.tscn", points=Raw(raw),
               carriage_width=width, sidewalk_width=sidewalk, sidewalks=sidewalk > 0, markings=markings)
    ROADS.append(dict(id=name, points=points, width=width, sidewalk=sidewalk))


def residential():
    scene = new_district("Residential")
    homes = [
        ("R01", -595, -400, 100, 14, 5, 0), ("R02", -515, -335, 110, 15, 6, 0),
        ("R03", -395, -395, 90, 14, 5, 90), ("R04", -260, -425, 88, 14, 5, 90),
        ("R05", -590, -185, 105, 16, 6, 0), ("R06", -500, -115, 96, 15, 5, 0),
        ("R07", -400, -195, 96, 14, 5, 90), ("R08", -280, -160, 74, 14, 4, 90),
        ("R09", -585, 55, 96, 14, 5, 0), ("R10", -490, 120, 80, 16, 6, 0),
        ("R11", -385, 55, 105, 15, 5, 90), ("R12", -250, 95, 86, 14, 5, 90),
        ("R13", -590, 210, 75, 14, 5, 0), ("R14", -440, 230, 60, 15, 4, 0),
        ("R15", -205, -500, 50, 14, 4, 0), ("R16", -185, 210, 55, 14, 4, 90),
    ]
    for name, x, z, width, depth, floors, yaw in homes:
        building(scene, name, x, z, width, depth, floors * 3.0 + .8, floors, yaw,
                 title="", style="residential", category="residential")
        if name in ["R01", "R05", "R09"]:
            building(scene, name + "_Wing", x - width / 2 + 7, z + 18, 38, 14,
                     floors * 3 + .8, floors, 90, style="residential", category="residential_wing")
        if name == "R02":
            for side in [-1, 1]:
                building(scene, f"R02_Wing_{side}", x + side * (width / 2 - 7), z - 20,
                         34, 14, 18.8, 6, 90, style="residential", category="residential_wing")
    courts = [(-525, -370), (-520, -150), (-520, 88), (-320, 195)]
    for index, (x, z) in enumerate(courts, 1):
        scene.props(f"Playground_{index}", x, z, [
            box((0, .05, 0), (25, .1, 18), (.48, .52, .42)),
            box((-6, 1.2, 0), (.2, 2.4, .2)), box((6, 1.2, 0), (.2, 2.4, .2)),
            box((0, 2.4, 0), (12.2, .2, .2)), box((3, .5, 4), (3, 1, 3), (.53, .57, .59), True),
            box((-4, .2, 4), (6, .4, 4), (.57, .53, .43), True)])
        for off, (dx, dz) in enumerate([(-25, -16), (22, -12), (-24, 19), (28, 21), (0, 16), (-18, 0)]):
            tree(scene, f"CourtyardTree_{index}_{off}", x + dx, z + dz, 7 + off % 3, 4 + off % 2)
        bench(scene, f"Bench_{index}_A", x - 18, z + 9)
        bench(scene, f"Bench_{index}_B", x + 18, z + 9, 180)
        parking(scene, f"CourtyardParking_{index}", x + 90, z + 37, 8, 1)
        building(scene, f"Utility_{index}", x + 43, z + 19, 6, 8, 3.6, category="secondary")
        container(scene, f"Waste_{index}", x - 52, z + 25)
        loot(scene, f"Loot_Residential_{index}", x + 44, z + 12, "Дворовой ящик")
        car(scene, f"CourtyardCar_{index}", x + 92, z + 37)
    scene.save("zone02_residential.tscn")


def commercial():
    scene = new_district("Commercial")
    store = building(scene, "Supermarket", 20, -190, 110, 70, 9.2, 2,
                     title="МАГАЗИН", style="store", category="landmark")
    scene.node("LoadingGate", store, "res://scenes/world/blockout_opening.tscn", position=v3(-25, 0, -35), kind=1, width=5)
    rectangle_pad(20, -98, 140, 90)
    scene.props("ParkingApron", 20, -98, [box((0, -.02, 0), (140, .12, 90), (.25, .26, .27), True, surface="asphalt")], y=base_height(20, -98))
    parking(scene, "CustomerParking", 20, -98, 24, 4)
    for i in range(18):
        car(scene, f"CustomerCar_{i:02}", -6 + (i % 8) * 5, -116 + (i // 8) * 12,
            color=[(.43, .5, .55), (.58, .59, .55), (.6, .34, .31)][i % 3])
    for i, x in enumerate([-40, 20, 80]):
        tree(scene, f"ParkingTree_{i}", x, -63, 7, 4)
        scene.props(f"ParkingIsland_{i}", x, -63, [box((0, .2, 0), (5, .4, 8), (.48, .51, .47), True)])
    scene.props("TrolleyCanopy", -22, -145, [box((0, 2.2, 0), (12, .18, 4), (.5, .53, .56)),
                                                   box((-5, 1.1, 0), (.2, 2.2, .2), collision=True),
                                                   box((5, 1.1, 0), (.2, 2.2, .2), collision=True)])
    rectangle_pad(20, -252, 100, 36)
    scene.props("LoadingYard", 20, -252, [box((0, -.03, 0), (100, .14, 36), (.32, .33, .34), True)], y=base_height(20, -252))
    for i, x in enumerate([-12, 8, 28]):
        scene.props(f"LoadingRamp_{i}", x, -230, [box((0, .5, 0), (9, 1, 6), collision=True)])
        container(scene, f"LoadingContainer_{i}", x + 3, -253, 90)
        loot(scene, f"Loot_Store_{i}", x + 3, -261, "Разгрузочный ящик")
    building(scene, "StoreWorkshop", 98, -251, 16, 12, 4.2)
    container(scene, "WasteCollection", -56, -242)
    for i, x in enumerate([-35, -10, 15, 40]):
        scene.props(f"TradingShelf_{i}", x, -188, [box((0, 1.15, 0), (12, 2.3, 1), (.42, .46, .48), True, surface="metal")], y=base_height(20, -190) + .14)
    loot(scene, "Loot_Store_Safe", 58, -168, "Касса магазина", "safe", y=base_height(20, -190) + .14)
    scene.save("zone02_store.tscn")


def administration():
    scene = new_district("Administration")
    building(scene, "AdministrationBuilding", 0, 260, 100, 60, 17, 4,
             title="АДМИНИСТРАЦИЯ", style="public", category="landmark")
    rectangle_pad(0, 175, 100, 80)
    scene.props("CivicSquare", 0, 175, [box((0, -.04, 0), (100, .16, 80), (.63, .64, .62), True)], y=base_height(0, 175))
    for i in range(4):
        scene.props(f"EntranceStep_{i}", 0, 223 + i * .4,
                    [box((0, .09 * (i + 1), 0), (30, .18 * (i + 1), .5), collision=True)])
    scene.props("EntrancePortico", 0, 220, [box((0, 5.4, 0), (32, .5, 8), (.67, .68, .67)),
                         *[box((x, 2.7, 0), (1.2, 5.4, 1.2), (.67, .68, .67), True) for x in [-12, -4, 4, 12]]])
    scene.props("Fountain", 0, 168, [box((0, .35, 0), (12, .7, 12), (.53, .6, .62), True),
                                   box((0, 1.3, 0), (3, 2.6, 3), (.69, .7, .68), True)])
    for i, x in enumerate([-40, -23, 23, 40]):
        tree(scene, f"SquareTree_{i}", x, 171, 8, 5)
        scene.props(f"SquarePlanter_{i}", x, 171, [box((0, .35, 0), (5, .7, 5), (.47, .51, .49), True)])
        bench(scene, f"SquareBench_{i}", x, 187)
    for i, x in enumerate([-17, -12, -7]):
        scene.props(f"Flagpole_{i}", x, 213, [box((0, 5, 0), (.15, 10, .15), (.64, .67, .69)),
                                                   box((1, 8.8, 0), (2, 1.2, .06), (.37, .48, .6))])
    parking(scene, "StaffParking", 0, 333, 10, 2)
    building(scene, "AdminArchive", 55, 338, 18, 14, 5.5)
    building(scene, "AdminSubstation", -52, 334, 8, 12, 4)
    for i in range(3):
        container(scene, f"ArchiveContainer_{i}", -34 + i * 8, 365)
    fence(scene, "RearFenceWest", (-70, 302), (-70, 370))
    fence(scene, "RearFenceEast", (72, 304), (72, 371))
    fence(scene, "RearFenceLeft", (-70, 371), (-8, 371))
    fence(scene, "RearFenceRight", (8, 371), (72, 371))
    loot(scene, "Loot_Admin_01", 44, 244, "Шкаф администрации", "office", y=base_height(0, 260) + .14)
    loot(scene, "Loot_Admin_02", 55, 330, "Архивный ящик", "office")
    scene.save("zone02_administration.tscn")


def bus_station():
    scene = new_district("BusStation")
    building(scene, "Terminal", 380, 185, 80, 30, 7.2, 1,
             title="АВТОСТАНЦИЯ", style="public", category="landmark")
    rectangle_pad(380, 290, 292, 246)
    scene.props("StationApron", 380, 290, [box((0, -.04, 0), (292, .18, 246), (.29, .3, .31), True, surface="asphalt")], y=base_height(380, 290))
    scene.props("PassengerSquare", 380, 222, [box((0, .04, 0), (110, .16, 28), (.58, .59, .58), True)])
    for i, z in enumerate([252, 277, 302, 327, 352, 377], 1):
        scene.props(f"Platform_{i}", 380, z, [box((0, .12, 0), (76, .24, 5), (.65, .66, .65), True)], y=base_height(380, 290))
        canopy = scene.node(f"Canopy_{i}", "Buildings", "res://scenes/world/blockout_building.tscn",
                            position=v3(380, base_height(380, 290), z), kind=3,
                            size=v2(70, 4.8), height=4.6)
        for offset, x in enumerate([350, 405]):
            pieces = [box((0, 1.65, 0), (2.5, 2.8, 12), (.69, .57, .23), True, surface="metal"),
                      box((0, 3.07, 0), (2.5, .26, 12), (.7, .71, .68)),
                      box((0, 2.25, -5.98), (2.1, 1.0, .07), (.16, .25, .29)),
                      box((-1.26, 2.3, 0), (.05, .9, 10), (.18, .27, .3)),
                      box((1.26, 2.3, 0), (.05, .9, 10), (.18, .27, .3))]
            for side in [-1, 1]:
                for axle in [-3.8, 3.8]:
                    pieces.append(box((side * 1.27, .5, axle), (.15, 1, 1), (.16, .17, .18)))
            scene.props(f"Bus_{i}_{offset}", x, z + 8, pieces, yaw=90, y=base_height(380, 290), surface="metal")
    parking(scene, "TerminalParking", 285, 209, 12, 2)
    building(scene, "BusRepair", 494, 347, 22, 36, 6.5)
    building(scene, "BusDispatch", 500, 251, 18, 12, 4.5)
    scene.props("FuelBay", 494, 300, [box((0, 2.5, 0), (14, .2, 10), (.5, .56, .54)),
                                            box((0, .8, 0), (1.5, 1.6, 1), (.5, .56, .54), True)])
    for i, z in enumerate([205, 242, 280, 318, 356, 400]):
        tree(scene, f"StationTree_{i}", 245, z, 8, 5)
        bench(scene, f"PassengerBench_{i}", 335, z)
    fence(scene, "StationEastFence", (530, 198), (530, 422))
    fence(scene, "StationSouthFence", (255, 423), (450, 423))
    container(scene, "BusServiceContainer", 496, 395)
    loot(scene, "Loot_Bus_01", 380, 193, "Пассажирский багаж", "office", y=base_height(380, 185) + .14)
    loot(scene, "Loot_Bus_02", 505, 393, "Ящик ремонтной зоны")
    scene.save("zone02_bus_station.tscn")


def garages():
    scene = new_district("Garages")
    for col, x in enumerate([420, 540]):
        for row, z in enumerate([-385, -369, -353, -337, -321]):
            index = col * 5 + row + 1
            length = 88 if col == 0 else 96
            name = f"GarageRow_{index:02}"
            path = building(scene, name, x, z, length, 7, 3.6, 1,
                            style="garage", doors=False, category="garage_row")
            for side in [-1, 1]:
                scene.node(f"OpenBay_{side}", path, "res://scenes/world/blockout_opening.tscn",
                           position=v3(-length / 2 + 13.3, 0, side * 3.5), kind=1, width=3.5)
            doors = []
            for bay in range(int(length / 3.8)):
                if bay != 3:
                    doors.append(box((-length / 2 + 1.9 + bay * 3.8, 1.35, -3.7), (3.45, 2.7, .09), (.36, .41, .43)))
            scene.props(name + "_Doors", x, z, doors, y=base_height(x, z) + .14)
    building(scene, "GarageWorkshop", 420, -245, 30, 22, 5.4, title="ГАРАЖИ")
    building(scene, "TyreWorkshop", 538, -240, 20, 15, 4.2)
    building(scene, "GarageStorage", 573, -211, 12, 18, 4)
    for i in range(5):
        car(scene, f"AbandonedCar_{i}", 390 + i * 32, -285, 90, (.44, .46, .43))
        container(scene, f"WorkshopContainer_{i}", 380 + i * 41, -206)
    fence(scene, "GarageFenceNorth", (355, -423), (610, -423))
    fence(scene, "GarageFenceEast", (625, -415), (625, -232))
    loot(scene, "Loot_Garage_01", 413, -247, "Инструментальный ящик")
    loot(scene, "Loot_Garage_02", 587, -212, "Складской ящик")
    scene.save("zone02_garages.tscn")


def sports():
    scene = new_district("SportsField")
    rectangle_pad(560, 20, 125, 88)
    pieces = [box((0, .035, 0), (105, .07, 68), (.26, .43, .3), True)]
    for z in [-34, 34]:
        pieces.append(box((0, .076, z), (105, .015, .16), (.88, .9, .86), shadow=False))
    for x in [-52.5, 0, 52.5]:
        pieces.append(box((x, .076, 0), (.16, .015, 68), (.88, .9, .86), shadow=False))
    for side in [-1, 1]:
        pieces += [box((side * 52.5, 1.22, -3.66), (.12, 2.44, .12), (.84, .86, .84)),
                   box((side * 52.5, 1.22, 3.66), (.12, 2.44, .12), (.84, .86, .84)),
                   box((side * 52.5, 2.44, 0), (.12, .12, 7.32), (.84, .86, .84)),
                   box((side * 36, .076, 0), (.16, .015, 40.32), (.88, .9, .86), shadow=False)]
        for z in [-20.16, 20.16]:
            pieces.append(box((side * 44.25, .076, z), (16.5, .015, .16), (.88, .9, .86), shadow=False))
    for index in range(32):
        angle = math.tau * index / 32
        pieces.append(box((math.cos(angle) * 9.15, .076, math.sin(angle) * 9.15), (1.82, .015, .14),
                          (.88, .9, .86), rotation=[0, -math.degrees(angle) + 90, 0], shadow=False))
    scene.props("FootballPitch", 560, 20, pieces, y=base_height(560, 20))
    for name, a, b in [
        ("NorthWest", (500, -21), (554, -21)), ("NorthEast", (560, -21), (620, -21)),
        ("SouthWest", (500, 61), (551, 61)), ("SouthEast", (557, 61), (620, 61)),
        ("East", (620, -21), (620, 61)), ("WestNorth", (500, -21), (500, 15)),
        ("WestSouth", (500, 22), (500, 61))]:
        fence(scene, "FieldFence_" + name, a, b, 4.5)
    building(scene, "ChangingRooms", 555, -42, 20, 10, 3.8)
    for i, z in enumerate([-16, 40]):
        scene.props(f"Grandstand_{i}", 633, z, [box((0, .3, 0), (8, .6, 16), collision=True),
                                                       box((2, .75, 0), (4, 1.5, 16), collision=True),
                                                       box((3, 1.2, 0), (2, 2.4, 16), collision=True)])
    scene.save("zone02_sports_field.tscn")


def checkpoints():
    scene = new_district("Checkpoints")
    for label, x, z, yaw in [("West", -714, 0, 90), ("East", 714, 80, -90), ("South", -20, 604, 0)]:
        root = scene.node(label + "Checkpoint", position=v3(x, base_height(x, z), z), rotation_degrees=v3(0, yaw, 0))
        scene.node("Props", root, groups=["urban_prop_batches"])
        scene.node("Buildings", root)
        pieces = [box((0, -.1, 0), (46, .25, 44), (.33, .34, .35), True, surface="asphalt")]
        if label == "South":
            pieces.append(box((0, -3.4, 0), (46, 6.6, 44), (.48, .5, .5), True))
        for lane in [-6, -2, 2, 6]:
            pieces += [box((lane + 1.7, .6, -8), (.5, 1.2, 4), (.65, .66, .64), True),
                       box((lane - 1.7, .75, 0), (.6, 1.5, .6), (.64, .63, .61), True),
                       box((lane, 1.25, 0), (3.2, .14, .14), (.7, .42, .37), True)]
        for side in [-1, 1]:
            pieces += [box((side * 20, 5.5, -12), (.25, 11, .25), (.49, .51, .52)),
                       box((side * 20, 11, -12), (1, .4, .7), (.83, .82, .69))]
        scene.props("CheckpointRoad", 0, 0, pieces, parent=root + "/Props", y=0)
        for name, bx, bz, w, d in [("ControlBooth", -14, -1, 4, 6), ("ControlOffice", 16, 7, 10, 15)]:
            bp = scene.node(name, root + "/Buildings", "res://scenes/world/blockout_building.tscn",
                            position=v3(bx, 0, bz), size=v2(w, d), height=3.6, simple_collision=True)
            scene.node("Door", bp, "res://scenes/world/blockout_opening.tscn", position=v3(0, 0, -d / 2))
            scene.node("Facade", bp, script=scene.resource("res://src/world/urban_facade.gd", "Script"), floors=1)
            angle = math.radians(yaw)
            center = [round(x + bx * math.cos(angle) + bz * math.sin(angle), 4),
                      round(z - bx * math.sin(angle) + bz * math.cos(angle), 4)]
            BUILDINGS.append(dict(name=label + name, center=center, size=[d, w] if yaw else [w, d], height=3.6, category="checkpoint"))
        for off, lx in enumerate([-14, 16]):
            light = scene.node(f"Floodlight_{off}", root, kind="SpotLight3D", position=v3(lx, 7, -10),
                               rotation_degrees=v3(-60, 0, 0), groups=["mall_lights"],
                               light_color=Raw("Color(1, 0.87, 0.67, 1)"), light_energy=2.0,
                               spot_range=32.0, spot_angle=55.0, shadow_enabled=False)
        scene.node("Extraction_" + label, root, "res://scenes/world/extraction_point.tscn",
                   position=v3(0, .08, 12 if label == "South" else -12), display_name={"West": "Западный КПП", "East": "Восточный КПП", "South": "Южный КПП"}[label],
                   radius=6.0)
    scene.save("zone02_checkpoints.tscn")


def secondary():
    scene = new_district("Services")
    entries = [
        ("Cafe", -105, -425, 20, 15, 6, 2), ("MedicalPost", -76, -343, 22, 18, 7, 2),
        ("NorthOffice", 130, -465, 28, 20, 9, 3), ("NorthShop", 130, -357, 18, 14, 5, 1),
        ("EastOffice", 255, -245, 24, 18, 9, 3), ("Bakery", 225, -112, 18, 16, 6, 2),
        ("UtilityNorth", -638, -515, 8, 12, 4, 1), ("WestWorkshop", -654, 314, 16, 12, 4.5, 1),
        ("SouthOffice", -255, 340, 25, 18, 9, 3), ("Clinic", 170, 250, 22, 24, 9, 3),
        ("Pharmacy", 173, 173, 12, 15, 4.2, 1), ("Laundry", 253, -7, 16, 12, 5, 1),
        ("Transformer", 185, -33, 6, 8, 3.5, 1), ("EastMarket", 706, -175, 20, 24, 7, 2),
        ("EastService", 670, 259, 18, 20, 6, 2), ("DispatchSouth", 112, 403, 18, 14, 6, 2),
        ("WaterUtility", -345, 443, 12, 10, 4, 1), ("SouthStorage", 565, 422, 18, 12, 4.5, 1),
        ("NorthKiosk", 257, -490, 7, 7, 3.6, 1), ("GarageTransformer", 315, -245, 8, 10, 4, 1),
        ("WestKiosk", -640, -43, 7, 7, 3.6, 1), ("SportsKiosk", 639, -47, 8, 8, 3.8, 1),
    ]
    for name, x, z, w, d, h, floors in entries:
        building(scene, name, x, z, w, d, h, floors)
    for i, (x, z) in enumerate([(-630, 340), (-245, 390), (150, 356), (655, 355)]):
        parking(scene, f"ServiceParking_{i}", x, z, 8, 2)
        for car_id in range(3):
            car(scene, f"ServiceCar_{i}_{car_id}", x - 5 + car_id * 5, z - 6)
    scene.node("GridGenerator", "Gameplay", script=scene.resource("res://src/world/mall_generator.gd", "Script"),
               position=v3(181, base_height(185, -33), -34), display_name="Городской генератор", where="у городской подстанции")
    scene.node("GridBreaker", "Gameplay", script=scene.resource("res://src/world/mall_breaker.gd", "Script"),
               position=v3(185, base_height(185, -33), -39), display_name="Рубильник района", power_area="районе")
    for index, (x, z) in enumerate([(-106, -420), (175, 171), (254, -5), (669, 252)]):
        loot(scene, f"Loot_Service_{index}", x, z, "Сервисный ящик")
    scene.save("zone02_services.tscn")


def world():
    scene = Scene("World")
    scene.node("Terrain", scene="res://scenes/world/urban_terrain.tscn")
    scene.node("Roads")
    scene.node("Sidewalks")
    scene.node("River")
    scene.node("Lighting")
    scene.node("Vegetation", groups=["urban_prop_batches"])
    scene.node("Props", groups=["urban_prop_batches"])
    road(scene, "WestEastAvenue", [[-750, 0], [-620, -10], [-460, -20], [-180, -20], [-70, 20], [180, 30], [360, 55], [580, 80], [750, 80]], 14, 4)
    road(scene, "NorthApproach", [[0, -625], [0, -425]], 14, 4)
    road(scene, "NorthSouthAvenue", [[-25, -400], [-110, -365], [-140, -250], [-140, -20], [-145, 160], [-160, 340], [-90, 425], [-20, 480], [-20, 625]], 14, 4)
    road(scene, "NorthRoundabout", [[round(math.cos(i * math.tau / 32) * 25, 3), round(-400 + math.sin(i * math.tau / 32) * 25, 3)] for i in range(33)], 9, 3, False)
    scene.props("RoundaboutGarden", 0, -400, [box((0, .3, 0), (30, .6, 30), (.36, .45, .35), True, shape="cylinder")])
    for i, (x, z) in enumerate([(-4, -404), (5, -396), (4, -407)]):
        tree(scene, f"RoundaboutTree_{i}", x, z)
    road(scene, "NorthEastLink", [[25, -400], [150, -401], [270, -425], [340, -435], [615, -435], [690, -370]], 9, 3)
    road(scene, "CivicCrossStreet", [[-145, 100], [50, 105], [210, 105], [340, 120], [535, 145], [710, 166]], 9, 3)
    road(scene, "ResidentialWestStreet", [[-690, -525], [-700, -300], [-695, -65], [-693, 180], [-665, 350]], 8, 2.5)
    road(scene, "ResidentialSpine", [[-348, -525], [-346, -320], [-350, -80], [-344, 165], [-320, 350]], 8, 2.5)
    road(scene, "ResidentialNorthLink", [[-700, -300], [-550, -310], [-350, -310], [-145, -300]], 8, 2.5)
    road(scene, "ResidentialMiddleLink", [[-695, -65], [-540, -64], [-345, -70], [-142, -70]], 8, 2.5)
    road(scene, "ResidentialSouthLink", [[-693, 175], [-540, 175], [-350, 165], [-145, 166]], 8, 2.5)
    road(scene, "SouthServiceRoad", [[-665, 350], [-430, 389], [-245, 395], [-90, 425], [110, 443], [325, 465], [570, 457], [710, 355]], 8, 2.5)
    road(scene, "EastDistrictStreet", [[690, -370], [660, -250], [680, -90], [710, 80], [710, 166], [700, 355]], 8, 2.5)
    road(scene, "CommercialAccess", [[-140, -270], [-65, -278], [107, -276], [150, -198], [149, -67], [147, 25]], 6, 2)
    road(scene, "GarageWestAccess", [[340, -435], [340, -288], [350, -205], [330, -125], [360, 55]], 7, 2)
    road(scene, "GarageEastAccess", [[615, -435], [615, -290], [650, -193], [655, -108], [655, 80], [580, 80]], 7, 2)
    for i, z in enumerate([-377, -361, -345, -329]):
        road(scene, f"GarageLane_{i}", [[360, z], [605, z]], 7, 0, False)
    road(scene, "GarageServiceLane", [[340, -288], [460, -288], [612, -288]], 7, 1.5)
    road(scene, "AdminRearAccess", [[-157, 321], [-81, 326], [-75, 376], [80, 376], [142, 329], [160, 280]], 6, 2, False)
    road(scene, "BusStationAccess", [[235, 111], [235, 225], [245, 403], [520, 437], [550, 352], [550, 235], [535, 145]], 8, 2.5)
    road(scene, "SportsAccess", [[490, 70], [478, 2], [490, -65], [580, -81], [660, -80]], 6, 2, False)
    court_drives = [
        [[-437, -310], [-437, -387], [-579, -387], [-589, -349], [-695, -350]],
        [[-438, -70], [-438, -140], [-445, -169], [-576, -169], [-593, -137], [-695, -137]],
        [[-435, 175], [-435, 104], [-450, 72], [-577, 72], [-596, 106], [-693, 112]],
        [[-344, 165], [-363, 205], [-350, 251], [-225, 256], [-225, 167], [-145, 166]],
    ]
    for i, ((x, z), drive) in enumerate(zip([(-525, -370), (-520, -150), (-520, 88), (-320, 195)], court_drives)):
        road(scene, f"CourtAccess_{i}", drive, 5.5, 0, False)
        for j, (dx, dz, w, d) in enumerate([(0, 0, 60, 2.5), (-20, 0, 2.5, 34), (24, 1, 2.5, 32)]):
            scene.props(f"CourtyardPath_{i}_{j}", x + dx, z + dz, [box((0, .01, 0), (w, .06, d), (.57, .59, .56))])
    # Река ниже городского уровня; мост сохраняет продольный уклон улицы.
    for i, (a, b) in enumerate(zip(RIVER, RIVER[1:])):
        x, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        scene.props(f"Water_{i}", x, z, [box((0, 0, 0), (math.dist(a, b) + 2, .035, 100), (.19, .4, .51), shadow=False)], parent="River", yaw=yaw, y=-8)
    bridge_y = base_height(-20, 545)
    scene.props("SouthBridge", -20, 545, [box((0, -.4, 0), (14, .8, 140), (.54, .56, .57), True),
                                         box((-6.3, .5, 0), (.2, 1.2, 140), collision=True),
                                         box((6.3, .5, 0), (.2, 1.2, 140), collision=True),
                                         *[box((0, -4, z), (10, 8, 2.5), (.5, .52, .53), True) for z in [-47, -12, 23, 52]]], y=bridge_y)
    for i, (x, z) in enumerate([(-720, 454), (-650, 473), (-566, 494), (-454, 484), (-345, 486), (-210, 490), (101, 483), (185, 492), (330, 515), (505, 514), (659, 524)]):
        scene.props(f"BankRock_{i}", x, z, [box((0, .5, 0), (4 + i % 3, 2, 3.5), (.42, .46, .43), True, shape="sphere")])
    # Озеленение следует улицам, дворам и берегу, а не равномерной сетке.
    tree_id = 0
    for line in [
        [(-715, -540), (-715, -300), (-712, 80), (-680, 335)],
        [(-605, -35), (-350, -38), (-155, -42)],
        [(176, -515), (210, -345), (209, -175)],
        [(310, 93), (450, 113), (675, 134)],
        [(-650, 442), (-420, 470), (-240, 478), (-65, 474)],
        [(150, 480), (380, 506), (666, 508)],
        [(650, -416), (650, -275), (658, -114)],
        [(-74, 135), (-76, 205), (-77, 285)],
    ]:
        for a, b in zip(line, line[1:]):
            steps = max(2, int(math.dist(a, b) / 18))
            for j in range(steps):
                t = j / steps
                x = a[0] + (b[0] - a[0]) * t + math.sin(j * 1.9) * 4
                z = a[1] + (b[1] - a[1]) * t + math.cos(j * 2.3) * 3
                tree(scene, f"StreetTree_{tree_id:03}", x, z, 6 + tree_id % 6, 3.5 + tree_id % 4, "Vegetation")
                tree_id += 1
    # Небольшие зелёные карманы и сервисные площадки закрывают пустые промежутки между районами.
    pockets = [(-625, -548), (-500, -548), (-367, -564), (-175, -563), (135, -558),
               (313, -550), (480, -544), (629, -531), (-480, -456), (-210, -385),
               (-595, -235), (-250, -256), (-244, 17), (267, -355), (273, -183),
               (310, -44), (423, -168), (545, -142), (614, -128), (-603, 289),
               (-470, 299), (-285, 285), (105, 70), (180, 316), (611, 215)]
    for pocket, (x, z) in enumerate(pockets):
        for offset, (dx, dz) in enumerate([(-11, -4), (-3, 2), (8, -7), (12, 9), (-7, 12), (0, 17)]):
            tree(scene, f"GreenPocket_{pocket}_{offset}", x + dx, z + dz, 6 + offset, 4 + offset % 3, "Vegetation")
        if pocket in [0, 3, 5, 12, 15, 17, 19, 22, 23]:
            scene.props(f"PocketServicePad_{pocket}", x + 23, z + 10,
                        [box((0, -.02, 0), (12, .1, 10), (.43, .47, .43)),
                         box((-3, .55, 0), (4, 1.1, 1), (.59, .6, .58), True),
                         box((3, .75, 2), (2, 1.5, 1.4), (.41, .46, .45), True)])
    for i, (x, z) in enumerate([(-665, 17), (-355, 8), (-164, 65), (180, 72), (571, 115), (672, -79)]):
        scene.props(f"BusShelter_{i}", x, z, [box((0, 2.8, 0), (8, .2, 3), (.5, .54, .56)),
                                                      box((-3.7, 1.4, 0), (.18, 2.8, .18), collision=True),
                                                      box((3.7, 1.4, 0), (.18, 2.8, .18), collision=True),
                                                      box((0, .45, 0), (5, .2, .6), collision=True)])
    for i, (x, z) in enumerate([(-340, -65), (-140, -70), (-145, 100), (360, 55), (710, 80), (-20, 460)]):
        scene.props(f"Crossing_{i}", x, z, [box(((j - 4) * 1.2, .07, 0), (.6, .02, 14), (.83, .84, .8), shadow=False) for j in range(9)])
    for i, road_def in enumerate(ROADS[:6]):
        for j, (x, z) in enumerate(road_def["points"][1:-1]):
            scene.props(f"LampPole_{i}_{j}", x + 12, z - 6, [box((0, 4.5, 0), (.18, 9, .18), (.46, .49, .51)),
                                                                      box((1.1, 8.8, 0), (2.2, .15, .2)),
                                                                      box((2.1, 8.65, 0), (.7, .25, .4), (.87, .84, .69))])
            scene.node(f"StreetLight_{i}_{j}", "Lighting", kind="OmniLight3D", groups=["mall_lights"],
                       position=v3(x + 14.1, ground(x + 12, z - 6) + 8.4, z - 6),
                       light_color=Raw("Color(1, 0.86, 0.68, 1)"), light_energy=1.8, omni_range=24,
                       distance_fade_enabled=True, distance_fade_begin=140, distance_fade_length=30)
    # Вне северной границы только далёкий силуэт существующего круглого ТЦ, без игровой зоны.
    scene.props("NorthBackgroundGround", 0, -800,
                [box((0, -.15, 0), (1500, .3, 350), (.39, .44, .34), shadow=False),
                 box((0, .02, 0), (14, .05, 350), (.26, .28, .29), shadow=False)], y=2.5)
    scene.props("DistantMallRing", 0, -850, [box((0, 11.25, 0), (250, 22.5, 250), (.6, .62, .63), shape="cylinder"),
                                                   box((0, 25, 0), (60, 10, 60), (.54, .65, .69), shape="sphere")], y=2.5)
    scene.save("zone02_world.tscn")


def perimeter():
    scene = Scene("Perimeter")
    scene.node("Props", groups=["urban_prop_batches"])
    checkpoints = [(-748, 0, 32), (748, 80, 32), (-20, 624, 26)]
    for index, (a, b) in enumerate(zip(BOUNDARY, BOUNDARY[1:] + BOUNDARY[:1])):
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dz)
        cuts = []
        for gx, gz, width in checkpoints:
            t = ((gx - a[0]) * dx + (gz - a[1]) * dz) / (length * length)
            offset = abs((gx - a[0]) * dz - (gz - a[1]) * dx) / length
            if 0 < t < 1 and offset < 12:
                cuts.append((max(0, t * length - width / 2), min(length, t * length + width / 2)))
        segments = []
        start = 0
        for left, right in sorted(cuts):
            segments.append((start, left))
            start = right
        segments.append((start, length))
        for part, (left, right) in enumerate(segments):
            if right - left < .1:
                continue
            aa = (a[0] + dx * left / length, a[1] + dz * left / length)
            bb = (a[0] + dx * right / length, a[1] + dz * right / length)
            fence(scene, f"Wall_{index}_{part}", aa, bb, 4.5 + (index % 3) * .5, concrete=index % 5 != 3)
    for index, (x, z) in enumerate([(-741, -520), (-737, -340), (-736, 180), (-731, 420),
                                    (738, -493), (731, -260), (735, 290), (731, 488),
                                    (-612, 612), (-404, 617), (266, 615), (521, 615)]):
        scene.props(f"PerimeterTower_{index}", x, z, [box((0, 4.5, 0), (5, 9, 5), (.52, .55, .56), True),
                                                             box((0, 9.3, 0), (6, .6, 6), (.42, .46, .48))])
    # Береговое ограждение направляет к единственному мосту и исключает маршруты под водой.
    fence(scene, "RiverGuardWest", (-750, 452), (-100, 485), height=2.3)
    fence(scene, "RiverGuardEast", (50, 484), (748, 522), height=2.3)
    scene.save("zone02_perimeter.tscn")


def main_scene():
    scene = Scene("Zone02_UrbanBelt")
    scene.nodes[0] += '\nscript = ' + gvalue(scene.resource("res://src/world/sector_level.gd", "Script")) + '\nsector_path = "res://data/sectors/zone02_urban_belt.json"'
    scene.node("World", scene="res://scenes/levels/zone02/zone02_world.tscn")
    scene.node("Perimeter", "World", "res://scenes/levels/zone02/zone02_perimeter.tscn")
    scene.node("Districts")
    for name, filename in [("Residential", "residential"), ("Commercial", "store"),
                           ("Administration", "administration"), ("BusStation", "bus_station"),
                           ("Garages", "garages"), ("SportsField", "sports_field"), ("Services", "services")]:
        scene.node(name, "Districts", f"res://scenes/levels/zone02/zone02_{filename}.tscn")
    scene.node("Checkpoints", scene="res://scenes/levels/zone02/zone02_checkpoints.tscn")
    scene.node("Props")
    scene.node("Gameplay")
    scene.node("PlayerSpawn", "Gameplay", "res://scenes/world/spawn_point.tscn", position=v3(-100, ground(-100, -580) + .12, -580))
    scene.node("AI_Spawns", "Gameplay")
    ai_points = [(-515, -350), (-513, -138), (-531, 82), (-300, 183), (55, -257), (110, -111),
                 (40, 193), (40, 345), (355, 240), (480, 389), (390, -290), (585, -268)]
    for index, (x, z) in enumerate(ai_points, 1):
        scene.node(f"AI_TestSpawn_{index:02}", "Gameplay/AI_Spawns", kind="Marker3D",
                   groups=["ai_spawn_points"], position=v3(x, ground(x, z) + .16, z))
    scene.node("Navigation")
    scene.node("Audio")
    scene.node("Lighting")
    scene.node("Debug")
    scene.node("WorldEnvironment", kind="WorldEnvironment", environment=scene.resource("res://scenes/levels/zone02/zone02_environment.tres", "Environment"))
    scene.node("Sun", kind="DirectionalLight3D", rotation_degrees=v3(-24, -62, 0),
               light_color=Raw("Color(1, 0.8, 0.62, 1)"), light_energy=2.4,
               shadow_enabled=True, directional_shadow_max_distance=240.0)
    scene.node("CameraRig", scene="res://scenes/player/camera_rig.tscn")
    scene.node("HUD", kind="CanvasLayer")
    scene.node("Root", "HUD", kind="Control", layout_mode=3, anchors_preset=15,
               anchor_right=1.0, anchor_bottom=1.0, grow_horizontal=2, grow_vertical=2, mouse_filter=2)
    scene.node("Status", "HUD/Root", kind="Label", offset_left=24.0, offset_top=20.0,
               offset_right=700.0, offset_bottom=48.0, text="HP 100")
    scene.node("Dead", "HUD/Root", kind="Label", visible=False)
    scene.save("../zone02_urban_belt.tscn")


def definition():
    courts = [("res_north", "Северный двор", [-565, -392, -460, -346]),
              ("res_middle", "Средний двор", [-555, -172, -445, -134]),
              ("res_south", "Южный двор", [-550, 74, -445, 106]),
              ("res_east", "Восточный двор", [-334, 178, -272, 219]),
              ("loading", "Разгрузка", [-20, -270, 70, -243]),
              ("store_parking", "Парковка магазина", [-46, -133, 76, -72]),
              ("civic_square", "Площадь", [-42, 140, 42, 202]),
              ("admin_rear", "Служебный двор", [-36, 305, 36, 355]),
              ("bus_platforms", "Платформы", [330, 238, 452, 386]),
              ("bus_service", "Ремонтная зона", [470, 373, 515, 410]),
              ("garage_service", "Гаражный проезд", [375, -299, 600, -273]),
              ("garage_yard", "Мастерские", [366, -260, 408, -214]),
              ("sports", "Спортивная площадка", [507, -10, 612, 50])]
    rooms = []
    for name, title, rect in courts:
        x, z = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        rooms.append(dict(id="zone02_" + name, name=title, type="yard", rect=rect, y=ground(x, z), outdoor=True))
    districts = [dict(id=name, name=title, rect=rect) for name, title, rect in [
        ("residential", "Жилые кварталы", [-680, -480, -150, 260]),
        ("commercial", "Магазин", [-105, -280, 150, -50]),
        ("administration", "Администрация", [-140, 120, 140, 385]),
        ("bus_station", "Автостанция", [230, 160, 530, 423]),
        ("garages", "Гаражи", [330, -423, 630, -193]),
        ("sports", "Футбольное поле", [500, -21, 620, 61])]]
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(BOUNDARY, BOUNDARY[1:] + BOUNDARY[:1]))) / 2
    COUNTS["buildings"] = len(BUILDINGS)
    COUNTS["secondary_buildings"] = sum(b["category"] == "secondary" for b in BUILDINGS)
    COUNTS["roads"] = len(ROADS)
    result = dict(id="zone02_urban_belt", name="Зона 2 · Городской пояс", layout="cartesian_scene",
                  greybox=True, bounds=[-750, -625, 750, 625], boundary=BOUNDARY,
                  area_m2=area, units="metres", north="-Z", spawn=[-100, ground(-100, -580), -580],
                  camera_yaw=180, terrain=dict(pads=PADS), rooms=rooms, districts=districts,
                  roads=ROADS, river=dict(points=RIVER, width=100, surface_y=-8),
                  buildings=BUILDINGS, counts=COUNTS)
    path = ROOT / "data/sectors/zone02_urban_belt.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(area_m2=area, **COUNTS), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    residential()
    commercial()
    administration()
    bus_station()
    garages()
    sports()
    secondary()
    checkpoints()
    world()
    perimeter()
    definition()
    main_scene()
