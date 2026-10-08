"""Двор хрущёвок (зона 1, объект 5) — детальная сцена scenes/levels/zone01/zone01_yard05.tscn
и точки россыпи data/zone01_yard_scatter.json (трава, деревья).

python tools/build_zone01_yard.py      (после tools/build_zone01.py — нужна карта высот)
Раскладка — по концепт-карте: корпус 1 (панельный 1-464) вдоль северной дороги, корпус 2
(панельный) на востоке, корпус 3 (кирпичный 1-447) на западе; подъезды смотрят во двор. Во дворе —
проезд кольцом с карманами парковки и въездом с северной дороги, тротуары у подъездов, лавки,
фонари, детская площадка в центре, контейнерная площадка, сушилки белья, газонные ограждения,
гаражи и «ракушки» у оврага, сараи, ряд тополей вдоль дороги, берёзы и клёны, сухая трава.
Перезаписывает сцену двора целиком: правки раскладки — здесь, не в .tscn.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np

import build_zone01 as z1

ROOT = z1.ROOT
OUT = z1.OUT / "zone01_yard05.tscn"
SCATTER = ROOT / "data/zone01_yard_scatter.json"
MODELS = "res://assets/zone01/models"
MAT = "res://assets/zone01/materials"
MANIFEST_K = f"{MODELS}/khrushchevka.json"
MANIFEST_P = f"{MODELS}/props.json"
RNG = random.Random(505)

# корпуса: модель, центр, поворот (локальный +Z — во двор)
BUILDINGS = [
    ("Korpus1", "khrushchevka_panel_a", -212.0, -138.0, 0.0),
    ("Korpus2", "khrushchevka_panel_b", -154.0, -108.0, -90.0),
    ("Korpus3", "khrushchevka_brick", -238.0, -80.0, 90.0),
]

# покрытие: имя, ломаная (x, z), ширина, материал, бордюр
DRIVE = [(-174, -160), (-174, -123), (-169, -118)]
PAVING = [
    ("DriveIn", [(-174.0, -160.0), (-174.0, -123.0)], 6.0, "asphalt", 0.0),
    ("DriveLoop", [(-223.0, -123.0), (-169.0, -123.0), (-169.0, -60.0), (-223.0, -60.0), (-223.0, -123.0)], 5.5, "asphalt", 0.15),
    ("DriveMarket", [(-196.0, -60.0), (-196.0, -50.0)], 5.5, "asphalt", 0.0),
    ("DriveGarages", [(-223.0, -118.0), (-262.0, -118.0)], 5.0, "asphalt", 0.0),
    ("GarageLane", [(-263.0, -162.0), (-263.0, -100.0)], 6.0, "asphalt", 0.0),
    ("WalkK1", [(-240.0, -128.4), (-184.0, -128.4)], 2.0, "walk", 0.12),
    ("WalkK2", [(-164.0, -136.0), (-164.0, -80.0)], 2.0, "walk", 0.12),
    ("WalkK3", [(-228.5, -106.0), (-228.5, -54.0)], 2.0, "walk", 0.12),
    ("ParkingN", [(-218.0, -117.4), (-176.0, -117.4)], 5.0, "asphalt", 0.0),
    ("ParkingE", [(-174.6, -112.0), (-174.6, -70.0)], 5.0, "asphalt", 0.0),
    ("ContainerApron", [(-169.0, -68.0), (-178.0, -68.0)], 4.0, "asphalt", 0.0),
]

PLAYGROUND = (-197.0, -92.0)


def load_heights() -> None:
    z1.H = np.fromfile(ROOT / "data/terrain/zone01_heights.r32", dtype="<f4").reshape(z1.NZ, z1.NX)


def footprint_y(x: float, z: float, w: float, d: float, yaw: float) -> float:
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    ys = []
    for lx in (-w / 2, 0, w / 2):
        for lz in (-d / 2, 0, d / 2):
            ys.append(z1.ground(x + lx * c + lz * s, z - lx * s + lz * c))
    return sum(ys) / len(ys)


def near_paving(x: float, z: float, margin: float) -> bool:
    for _, pts, width, _, _ in PAVING:
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            dx, dz = bx - ax, bz - az
            t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
            if math.hypot(x - ax - dx * t, z - az - dz * t) < width * 0.5 + margin:
                return True
    return False


def in_building(x: float, z: float, margin: float) -> bool:
    rects = [(-240.8, -143.8, -183.2, -132.2), (-165.8, -136.8, -142.2, -79.2), (-244.0, -107.2, -232.0, -52.8)]
    return any(x0 - margin < x < x1 + margin and z0 - margin < z < z1 + margin for x0, z0, x1, z1 in rects)


class Yard:
    def __init__(self) -> None:
        self.s = z1.Scene("Yard05")
        self.n = 0

    def model(self, parent: str, name: str, model: str, x: float, z: float, yaw: float = 0.0, y: float | None = None,
              manifest: str = MANIFEST_P, surface: str = "metal") -> None:
        gy = z1.ground(x, z) if y is None else y
        self.s.node(name, parent, kind="StaticBody3D", script=self.s.resource("res://src/world/district_model.gd", "Script"),
                    position=z1.v3(x, gy, z), rotation_degrees=z1.v3(0, yaw, 0),
                    model=f"{MODELS}/{model}.glb", manifest=manifest, surface=surface)


def main() -> None:
    load_heights()
    info = json.loads((ROOT / "assets/zone01/models/khrushchevka.json").read_text(encoding="utf-8"))
    y = Yard()
    s = y.s
    s.node("Buildings", groups=["nav_source"])
    for name, model, x, z, yaw in BUILDINGS:
        meta = info[model]
        by = footprint_y(x, z, meta["length"], meta["depth"], yaw)
        y.model("Buildings", name, model, x, z, yaw, by, MANIFEST_K, "concrete")

    # покрытие: проезды асфальт, тротуары — тоже асфальт, но светлее и с бордюром
    s.node("Paving", groups=["nav_source"])
    script = s.resource("res://src/world/district_paving.gd", "Script")
    asphalt = s.resource(f"{MAT}/YardAsphalt.tres", "Material")
    walk = s.resource(f"{MAT}/YardWalk.tres", "Material")
    curb = s.resource(f"{MAT}/Curb.tres", "Material")
    for name, pts, width, kind, curb_h in PAVING:
        raw = "PackedVector2Array(" + ", ".join(f"{x}, {z}" for x, z in pts) + ")"
        s.node(name, "Paving", kind="StaticBody3D", script=script, points=z1.Raw(raw), width=width,
               curb_height=curb_h, material=asphalt if kind == "asphalt" else walk, curb_material=curb,
               lift=0.05 if kind == "asphalt" else 0.1)

    s.node("Props", groups=["nav_source"])
    # лавки у подъездов и фонари вдоль проезда
    k1_doors = [-232.8, -216.8, -204.0, -188.0]
    k2_doors = [-128.8, -112.8, -100.0, -84.0]
    k3_doors = [-57.9, -74.9, -85.1, -102.1]
    for i, x in enumerate(k1_doors):
        y.model("Props", f"BenchK1_{i}", "bench_back" if i % 2 == 0 else "bench_plain", x + 2.6, -127.0, 180.0, surface="wood")
    for i, z in enumerate(k2_doors):
        y.model("Props", f"BenchK2_{i}", "bench_back", -165.4, z + 2.6, 90.0, surface="wood")
    for i, z in enumerate(k3_doors):
        if i != 2:
            y.model("Props", f"BenchK3_{i}", "bench_back" if i else "bench_plain", -227.2, z - 2.6, -90.0, surface="wood")
    for i, (x, z, yaw) in enumerate([(-226.5, -126.5, 45), (-196.0, -126.0, 0), (-165.5, -121.0, -90),
                                     (-165.8, -90.0, -90), (-166.0, -57.0, -135), (-196.0, -57.0, 180),
                                     (-226.0, -60.0, 135), (-226.0, -92.0, 90), (-174.0, -150.0, 0)]):
        y.model("Props", f"Lamp_{i}", "lamp_post", x, z, yaw, surface="concrete")

    # детская площадка
    px, pz = PLAYGROUND
    for name, model, dx, dz, yaw in [("Sandbox", "play_sandbox", -3.0, -4.0, 8), ("Swing", "play_swing", 7.0, 4.0, 90),
                                     ("Slide", "play_slide", -7.0, 8.0, -30), ("Carousel", "play_carousel", 4.0, -6.0, 0),
                                     ("Arch", "play_arch", 9.0, -3.0, 15)]:
        y.model("Props", name, model, px + dx, pz + dz, yaw)
    for i, (dx, dz, yaw) in enumerate([(-12, -2, -90), (-11, 6, -110), (0, 13, 180), (12, 10, 160)]):
        y.model("Props", f"PlayBench_{i}", "bench_plain", px + dx, pz + dz, yaw, surface="wood")
    # контейнерная площадка с баками (открытой стороной к проезду)
    y.model("Props", "ContainerSite", "container_site", -181.0, -68.0, 90.0, surface="concrete")
    # баки — скан Sketchfab (зелёные 0.75 м³, CC-BY), один опрокинут у площадки
    for i, (dz, model) in enumerate([(-1.6, "sf_dumpster_a"), (0.0, "sf_dumpster_b"), (1.6, "sf_dumpster_a")]):
        z1.sf_model(s, f"Dumpster_{i}", model, -181.6, -68.0 + dz, 90.0 + RNG.uniform(-8, 8), "Props")
    z1.sf_model(s, "DumpsterTipped", "sf_dumpster_tipped", -176.0, -63.5, 30.0, "Props")
    # сухие деревья у гаражей и брошенные бруски
    z1.sf_model(s, "DeadTree_0", "sf_dead_tree", -278.0, -96.0, 40.0, "Props", surface="wood")
    z1.sf_model(s, "DeadTree_1", "sf_dead_tree", -150.0, -150.0, 160.0, "Props", surface="wood")
    for i, (x, zz, yaw) in enumerate([(-258, -112, 20), (-257, -110.5, 75), (-180, -61, 130), (-230, -63, 10), (-246, -50, 95)]):
        z1.sf_model(s, f"WoodBlock_{i}", "sf_wood_block", x, zz, 0, "Props", y=z1.ground(x, zz) + 0.06, surface="wood",
                    rotation=(90, yaw, 0))
    # сушилки белья на газоне между корпусом 3 и площадкой
    y.model("Props", "Laundry_0", "laundry_pair", -214.0, -70.0, 0.0)
    y.model("Props", "Laundry_1", "laundry_pair", -214.0, -104.0, 0.0)
    # газонные ограждения вдоль тротуаров
    fences = []
    for x in range(-238, -186, 3):
        if all(abs(x + 1.5 - d) > 3.0 for d in k1_doors):
            fences.append((x + 1.5, -126.8, 0.0))
    for z in range(-134, -82, 3):
        if all(abs(z + 1.5 - d) > 3.0 for d in k2_doors):
            fences.append((-165.6, z + 1.5, 90.0))
    for i, (x, z, yaw) in enumerate(fences):
        y.model("Props", f"LawnFence_{i}", "lawn_fence", x, z, yaw + RNG.uniform(-2, 2))
    # гаражи у оврага: «ракушки» и металлические боксы воротами на проезд
    garages = []
    z = -160.0
    k = 0
    while z < -104:
        kind = ["rakushka_green", "garage_box_brown", "rakushka_rust", "garage_box_blue", "garage_box_open", "rakushka_green"][k % 6]
        rak = kind.startswith("rakushka")
        garages.append((kind, -269.5, z, 90.0 if rak else -90.0))
        z += 3.0 if rak else 3.6
        k += 1
    for i, (kind, x, gz, yaw) in enumerate(garages):
        y.model("Props", f"Garage_{i}", kind, x + RNG.uniform(-0.3, 0.3), gz, yaw + RNG.uniform(-3, 3))
    y.model("Props", "Sheds", "shed_row", -252.0, -46.0, 4.0, surface="wood")

    # брошенные машины — пока блокаут (модели — у владельца, docs/zone01_assets.md)
    for i, (x, zz, yaw) in enumerate([(-208, -117.4, 90), (-196, -117.6, 92), (-185, -117.2, 88), (-174.6, -100, 0),
                                      (-174.6, -86, 180), (-210, -60.5, 95), (-262.5, -140, 4)]):
        z1.car(s, f"Car_{i}", x, zz, yaw, (.35 + RNG.random() * .3, .36 + RNG.random() * .2, .3 + RNG.random() * .25), parent="Props")

    scatter(s)
    s.save(OUT)
    print("yard05:", OUT)


def scatter(s: z1.Scene) -> None:
    """Деревья и трава: точки в JSON, MultiMesh-клетки в сцене (DistrictScatter)."""
    trees: dict[str, list] = {f"tree_{k}_{v}": [] for k in ("birch", "poplar", "maple") for v in range(3)}
    # ели у домов — их сажали во дворах; одна взрослая и подрост
    trees["spruce_open"] = [(-158.5, -96.0)]
    trees["spruce_young_a"] = [(-246.5, -66.0), (-187.0, -131.0)]
    trees["spruce_young_b"] = [(-159.0, -128.0)]
    # ряд тополей между северной дорогой и корпусом 1
    for i, x in enumerate(range(-238, -180, 9)):
        trees[f"tree_poplar_{i % 3}"].append((x + RNG.uniform(-1, 1), -151.5 + RNG.uniform(-0.6, 0.6)))
    # берёзы и клёны во дворе — группами по газонам
    yard_spots = [(-214, -112), (-210, -108), (-185, -110), (-180, -104), (-216, -82), (-212, -78), (-178, -82),
                  (-182, -76), (-205, -66), (-188, -66), (-218, -96), (-181, -93), (-236, -114), (-246, -60),
                  (-158, -70), (-150, -142), (-232, -148), (-244, -128), (-248, -92), (-250, -74)]
    for i, (x, z) in enumerate(yard_spots):
        kind = "birch" if i % 3 != 2 else "maple"
        trees[f"tree_{kind}_{i % 3}"].append((x + RNG.uniform(-1.5, 1.5), z + RNG.uniform(-1.5, 1.5)))
    # клёны-самосев у гаражей и сараев
    for i in range(8):
        x, z = -276 + RNG.uniform(-3, 3), -160 + i * 8 + RNG.uniform(-2, 2)
        trees[f"tree_maple_{i % 3}"].append((x, z))
    data: dict[str, list] = {}
    for key, pts in trees.items():
        data[key] = [[round(x, 2), round(z1.ground(x, z) - 0.05, 3), round(z, 2), round(RNG.uniform(0, 360), 1),
                      round(RNG.uniform(0.85, 1.15), 3)] for x, z in pts]
    # подлесок (сканы Poly Haven): бурьян гуще у стен домов, гаражей и заборов, на газонах — пятнами,
    # кусты вдоль цоколей и у гаражей, на площадке почти ничего (вытоптано)
    rects = [(-240.8, -143.8, -183.2, -132.2), (-165.8, -136.8, -142.2, -79.2), (-244.0, -107.2, -232.0, -52.8),
             (-272.0, -162.0, -267.0, -104.0), (-258.0, -48.0, -246.0, -44.0)]
    nrng = np.random.default_rng(55)

    def wall_dist(x: float, z: float) -> float:
        return min(max(x0 - x, x - x1, z0 - z, z - z1, 0.0) for x0, z0, x1, z1 in rects)

    def accept(x: float, z: float) -> bool:
        return not near_paving(x, z, 0.3) and not in_building(x, z, 0.4) and not (-272.5 < x < -266.5 and -162 < z < -104)

    def kind_at(x: float, z: float, roll: float):
        w = wall_dist(x, z)
        play = math.hypot(x - PLAYGROUND[0], z - PLAYGROUND[1])
        if play < 12.0:
            return "grass" if roll < 0.04 else None
        bush = 0.05 * (1.0 if 0.6 < w < 2.5 else 0.0) + 0.004
        if roll < bush:
            return "bush"
        roll -= bush
        dens = 0.35 + 0.6 * max(0.0, 1.0 - w / 4.0) + 0.3 * (1.0 if x < -248 else 0.0)
        return ("grass" if roll > 0.05 else "weed") if roll < dens else None

    data.update(z1.scatter_undergrowth(nrng, -285.0, -162.0, -140.0, -44.0, accept, kind_at))
    SCATTER.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    script = s.resource("res://src/world/district_scatter.gd", "Script")
    s.node("Vegetation")
    for key in trees:
        extra = dict(far_model=f"{MODELS}/{key}_far.glb", near_distance=95.0) if key.startswith("spruce") else {}
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_yard_scatter.json",
               key=key, model=f"{MODELS}/{key}.glb", view_distance=550.0, cell=96.0, trunk_radius=0.25, **extra)
    z1.undergrowth_nodes(s, "Vegetation", "res://data/zone01_yard_scatter.json")
    print("trees", sum(len(v) for v in trees.values()), "кустов", sum(len(data[k]) for k in z1.UG_VIEW))


if __name__ == "__main__":
    main()
