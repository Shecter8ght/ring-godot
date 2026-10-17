@tool
extends Node3D
## Наполнение черновика территории ТЦ серыми формами (владелец, 2026-10-17): укрытия, природа, ориентиры,
## маленькие истории и районы между участками. Данные — filler в data/blockouts/mall_study.json,
## раскладка — tools/mall_study_filler.py (пересборка — tools/build_mall_study.py).
## Дёшево для компьютера: одинаковые вещи рисуются пачками (MultiMesh) по клеткам, мелочь пропадает с
## расстояния (visibility_range) и не отбрасывает теней, коллизия — только у того, за чем прячутся.
## ЛЭП, теплотрасса и колея — по одной сетке на материал: их немного, а видно издалека.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const MallLandscape = preload("res://src/blockout/mall_landscape.gd")

## Цвета частей наборов; «white» — под цвет экземпляра (машины, гаражи, контейнеры).
const COLORS: Dictionary = {
	"white": Color(1.0, 1.0, 1.0), "concrete": Color(0.52, 0.53, 0.49), "wall": Color(0.63, 0.63, 0.58),
	"slab": Color(0.47, 0.49, 0.46), "dark": Color(0.2, 0.24, 0.23), "steel": Color(0.4, 0.36, 0.31),
	"rust": Color(0.56, 0.45, 0.33), "wood": Color(0.55, 0.45, 0.33), "wood_dark": Color(0.36, 0.29, 0.21),
	"olive": Color(0.36, 0.39, 0.27), "tarp": Color(0.42, 0.44, 0.33), "bus": Color(0.67, 0.66, 0.55),
	"cab": Color(0.6, 0.53, 0.42), "cabin": Color(0.62, 0.64, 0.6), "booth": Color(0.36, 0.45, 0.52),
	"profnastil": Color(0.48, 0.54, 0.53), "sand": Color(0.6, 0.55, 0.42), "sand_dark": Color(0.5, 0.45, 0.34),
	"dumpster": Color(0.33, 0.42, 0.36), "tent": Color(0.4, 0.46, 0.38), "burnt": Color(0.14, 0.13, 0.12),
	"suitcase": Color(0.32, 0.27, 0.3), "find": Color(0.84, 0.64, 0.23), "board": Color(0.42, 0.42, 0.4),
	"board_face": Color(0.78, 0.76, 0.69), "glass": Color(0.45, 0.52, 0.53), "weed": Color(0.45, 0.48, 0.28),
	"bush": Color(0.3, 0.37, 0.25), "birch": Color(0.8, 0.78, 0.71), "leaf": Color(0.42, 0.52, 0.31),
	"water": Color(0.24, 0.31, 0.32)}

## Цвета для «white», если у экземпляра своего нет: гаражи и контейнеры разные, но не пёстрые.
const VARY: Dictionary = {
	"garage": [Color(0.5, 0.52, 0.47), Color(0.45, 0.5, 0.52), Color(0.55, 0.47, 0.38), Color(0.4, 0.45, 0.38)],
	"container": [Color(0.55, 0.33, 0.27), Color(0.32, 0.42, 0.52), Color(0.36, 0.47, 0.37), Color(0.6, 0.55, 0.45)]}

## Наборы: части [форма, центр, размер, цвет, поворот°] — формы box, cyl (ось Y), cone, dome, prism;
## solid — коллизия [центр, размер]; range — дальность видимости, м (0 — всегда); shadow — тень;
## vary — разброс цвета «white»; water — блестящий материал лужи. Длинная ось — локальная Z.
const KITS: Dictionary = {
	"fbs": {"parts": [["box", Vector3(0, 0.3, 0), Vector3(0.6, 0.6, 2.4), "concrete"]],
		"solid": [[Vector3(0, 0.3, 0), Vector3(0.6, 0.6, 2.4)]], "range": 260.0},
	"jersey": {"parts": [["box", Vector3(0, 0.5, 0), Vector3(0.5, 0.8, 3.0), "wall"], ["box", Vector3(0, 0.1, 0), Vector3(0.75, 0.2, 3.0), "wall"]],
		"solid": [[Vector3(0, 0.45, 0), Vector3(0.7, 0.9, 3.0)]], "range": 260.0},
	"slab": {"parts": [["box", Vector3(0, 0.09, 0), Vector3(2.0, 0.18, 6.0), "slab"]],
		"solid": [[Vector3(0, 0.09, 0), Vector3(2.0, 0.18, 6.0)]], "range": 260.0},
	"pallets": {"parts": [["box", Vector3(0, 0.6, 0), Vector3(1.2, 1.2, 1.0), "wood"],
		["box", Vector3(0, 0.15, 0), Vector3(1.22, 0.06, 1.02), "wood_dark"], ["box", Vector3(0, 0.45, 0), Vector3(1.22, 0.06, 1.02), "wood_dark"],
		["box", Vector3(0, 0.75, 0), Vector3(1.22, 0.06, 1.02), "wood_dark"], ["box", Vector3(0, 1.05, 0), Vector3(1.22, 0.06, 1.02), "wood_dark"]],
		"solid": [[Vector3(0, 0.6, 0), Vector3(1.2, 1.2, 1.0)]], "range": 240.0},
	"reel": {"parts": [["cyl", Vector3(0, 1.1, 0), Vector3(2.2, 1.2, 2.2), "wood", Vector3(0, 0, 90)],
		["cyl", Vector3(0, 1.1, 0), Vector3(1.2, 1.24, 1.2), "dark", Vector3(0, 0, 90)]],
		"solid": [[Vector3(0, 1.1, 0), Vector3(1.2, 2.2, 2.0)]], "range": 260.0},
	"pipes": {"parts": [["cyl", Vector3(-1.05, 0.5, 0), Vector3(1.0, 8.0, 1.0), "rust", Vector3(90, 0, 0)],
		["cyl", Vector3(0, 0.5, 0), Vector3(1.0, 8.0, 1.0), "rust", Vector3(90, 0, 0)],
		["cyl", Vector3(1.05, 0.5, 0), Vector3(1.0, 8.0, 1.0), "rust", Vector3(90, 0, 0)],
		["cyl", Vector3(-0.52, 1.36, 0), Vector3(1.0, 8.0, 1.0), "rust", Vector3(90, 0, 0)],
		["cyl", Vector3(0.52, 1.36, 0), Vector3(1.0, 8.0, 1.0), "rust", Vector3(90, 0, 0)]],
		"solid": [[Vector3(0, 0.9, 0), Vector3(3.2, 1.8, 8.0)]], "range": 300.0},
	"car": {"parts": [["box", Vector3(0, 0.55, 0), Vector3(1.9, 0.8, 4.6), "white"], ["box", Vector3(0, 1.2, -0.2), Vector3(1.6, 0.55, 2.4), "white"],
		["box", Vector3(0, 1.22, -0.2), Vector3(1.64, 0.3, 2.1), "dark"],
		["box", Vector3(-0.85, 0.3, 1.4), Vector3(0.3, 0.6, 0.62), "dark"], ["box", Vector3(0.85, 0.3, 1.4), Vector3(0.3, 0.6, 0.62), "dark"],
		["box", Vector3(-0.85, 0.3, -1.4), Vector3(0.3, 0.6, 0.62), "dark"], ["box", Vector3(0.85, 0.3, -1.4), Vector3(0.3, 0.6, 0.62), "dark"]],
		"solid": [[Vector3(0, 0.55, 0), Vector3(1.9, 0.8, 4.6)], [Vector3(0, 1.2, -0.2), Vector3(1.6, 0.55, 2.4)]], "range": 420.0},
	"truck": {"parts": [["box", Vector3(0, 0.75, 0), Vector3(2.2, 0.5, 7.2), "dark"], ["box", Vector3(0, 1.75, 2.75), Vector3(2.5, 1.9, 1.9), "olive"],
		["box", Vector3(0, 2.0, 2.75), Vector3(2.54, 0.6, 1.5), "dark"], ["box", Vector3(0, 2.05, -1.0), Vector3(2.5, 2.1, 4.8), "tarp"],
		["box", Vector3(-1.1, 0.55, 2.6), Vector3(0.4, 1.1, 1.1), "dark"], ["box", Vector3(1.1, 0.55, 2.6), Vector3(0.4, 1.1, 1.1), "dark"],
		["box", Vector3(-1.1, 0.55, -2.0), Vector3(0.4, 1.1, 2.4), "dark"], ["box", Vector3(1.1, 0.55, -2.0), Vector3(0.4, 1.1, 2.4), "dark"]],
		"solid": [[Vector3(0, 1.55, 0.2), Vector3(2.5, 3.1, 7.2)]], "range": 420.0},
	"truck_cab": {"parts": [["box", Vector3(0, 0.8, -0.8), Vector3(2.2, 0.6, 6.0), "dark"], ["box", Vector3(0, 2.0, 1.4), Vector3(2.5, 2.6, 2.3), "cab"],
		["box", Vector3(0, 2.5, 2.56), Vector3(2.3, 0.9, 0.02), "dark"],
		["box", Vector3(-1.1, 0.55, 1.6), Vector3(0.4, 1.1, 1.1), "dark"], ["box", Vector3(1.1, 0.55, 1.6), Vector3(0.4, 1.1, 1.1), "dark"],
		["box", Vector3(-1.1, 0.55, -2.4), Vector3(0.4, 1.1, 2.4), "dark"], ["box", Vector3(1.1, 0.55, -2.4), Vector3(0.4, 1.1, 2.4), "dark"]],
		"solid": [[Vector3(0, 1.65, 0.0), Vector3(2.5, 3.3, 6.0)]], "range": 420.0},
	"trailer": {"parts": [["box", Vector3(0, 0.75, 0), Vector3(2.2, 0.4, 13.0), "dark"], ["box", Vector3(0, 2.45, 0), Vector3(2.5, 3.0, 13.0), "wall"],
		["box", Vector3(-1.1, 0.5, -5.0), Vector3(0.4, 1.0, 2.6), "dark"], ["box", Vector3(1.1, 0.5, -5.0), Vector3(0.4, 1.0, 2.6), "dark"]],
		"solid": [[Vector3(0, 2.05, 0), Vector3(2.5, 3.8, 13.0)]], "range": 420.0},
	"bus_wreck": {"parts": [["box", Vector3(0, 1.7, 0), Vector3(2.55, 2.6, 12.0), "bus"], ["box", Vector3(0, 2.2, 0), Vector3(2.59, 0.9, 10.4), "dark"],
		["box", Vector3(-1.1, 0.5, 3.6), Vector3(0.4, 1.0, 1.0), "dark"], ["box", Vector3(1.1, 0.5, 3.6), Vector3(0.4, 1.0, 1.0), "dark"],
		["box", Vector3(-1.1, 0.5, -3.6), Vector3(0.4, 1.0, 1.0), "dark"], ["box", Vector3(1.1, 0.5, -3.6), Vector3(0.4, 1.0, 1.0), "dark"]],
		"solid": [[Vector3(0, 1.5, 0), Vector3(2.55, 3.0, 12.0)]], "range": 420.0},
	"container40": {"parts": [["box", Vector3(0, 1.3, 0), Vector3(2.44, 2.6, 12.2), "white"], ["box", Vector3(0, 1.3, 6.11), Vector3(2.2, 2.3, 0.02), "dark"]],
		"solid": [[Vector3(0, 1.3, 0), Vector3(2.44, 2.6, 12.2)]], "range": 420.0, "vary": "container"},
	"container20": {"parts": [["box", Vector3(0, 1.3, 0), Vector3(2.44, 2.6, 6.1), "white"], ["box", Vector3(0, 1.3, 3.06), Vector3(2.2, 2.3, 0.02), "dark"]],
		"solid": [[Vector3(0, 1.3, 0), Vector3(2.44, 2.6, 6.1)]], "range": 420.0, "vary": "container"},
	"garage": {"parts": [["box", Vector3(0, 1.2, 0), Vector3(3.2, 2.4, 6.0), "white"], ["box", Vector3(0, 1.0, 3.01), Vector3(2.6, 1.9, 0.02), "dark"],
		["box", Vector3(0, 2.43, 0), Vector3(3.3, 0.06, 6.2), "steel"]],
		"solid": [[Vector3(0, 1.2, 0), Vector3(3.2, 2.4, 6.0)]], "range": 420.0, "vary": "garage"},
	"garage_open": {"parts": [["box", Vector3(0, 1.2, -2.95), Vector3(3.2, 2.4, 0.1), "white"], ["box", Vector3(-1.55, 1.2, 0), Vector3(0.1, 2.4, 6.0), "white"],
		["box", Vector3(1.55, 1.2, 0), Vector3(0.1, 2.4, 6.0), "white"], ["box", Vector3(0, 2.43, 0), Vector3(3.3, 0.06, 6.2), "steel"],
		["box", Vector3(0, 0.02, 0), Vector3(3.0, 0.04, 5.8), "dark"], ["box", Vector3(1.0, 0.95, 3.3), Vector3(1.3, 1.9, 0.04), "dark", Vector3(0, 55, 0)]],
		"solid": [[Vector3(0, 1.2, -2.95), Vector3(3.2, 2.4, 0.1)], [Vector3(-1.55, 1.2, 0), Vector3(0.1, 2.4, 6.0)],
			[Vector3(1.55, 1.2, 0), Vector3(0.1, 2.4, 6.0)], [Vector3(0, 2.43, 0), Vector3(3.2, 0.06, 6.0)]], "range": 420.0, "vary": "garage"},
	"cabin": {"parts": [["box", Vector3(0, 1.32, 0), Vector3(2.4, 2.6, 6.0), "cabin"], ["box", Vector3(1.21, 1.6, -1.6), Vector3(0.02, 0.8, 1.0), "dark"],
		["box", Vector3(1.21, 1.6, 1.6), Vector3(0.02, 0.8, 1.0), "dark"], ["box", Vector3(1.21, 1.05, 0), Vector3(0.02, 1.9, 0.9), "dark"],
		["box", Vector3(0, 0.05, -2.6), Vector3(2.4, 0.1, 0.2), "steel"], ["box", Vector3(0, 0.05, 2.6), Vector3(2.4, 0.1, 0.2), "steel"]],
		"solid": [[Vector3(0, 1.32, 0), Vector3(2.4, 2.6, 6.0)]], "range": 420.0},
	"booth": {"parts": [["box", Vector3(0, 1.1, 0), Vector3(1.2, 2.2, 1.2), "booth"]], "solid": [[Vector3(0, 1.1, 0), Vector3(1.2, 2.2, 1.2)]], "range": 260.0},
	"fence": {"parts": [["box", Vector3(0, 1.15, 0), Vector3(0.05, 2.1, 3.0), "profnastil"], ["box", Vector3(0, 1.15, 1.5), Vector3(0.1, 2.3, 0.1), "steel"]],
		"solid": [[Vector3(0, 1.15, 0), Vector3(0.1, 2.3, 3.0)]], "range": 420.0},
	"stub": {"parts": [["box", Vector3(0, 0.8, 0), Vector3(0.45, 1.6, 0.45), "concrete"], ["box", Vector3(0, 1.85, 0), Vector3(0.06, 0.5, 0.06), "rust"]],
		"solid": [[Vector3(0, 0.8, 0), Vector3(0.45, 1.6, 0.45)]], "range": 260.0},
	"rebar": {"parts": [["box", Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 9.0), "rust"]], "solid": [[Vector3(0, 0.15, 0), Vector3(0.4, 0.3, 9.0)]], "range": 200.0},
	"sandbags": {"parts": [["box", Vector3(0, 0.5, 0), Vector3(0.7, 1.0, 1.8), "sand"], ["box", Vector3(0, 0.33, 0), Vector3(0.72, 0.04, 1.82), "sand_dark"],
		["box", Vector3(0, 0.66, 0), Vector3(0.72, 0.04, 1.82), "sand_dark"]],
		"solid": [[Vector3(0, 0.5, 0), Vector3(0.7, 1.0, 1.8)]], "range": 260.0},
	"dumpster": {"parts": [["box", Vector3(0, 0.65, 0), Vector3(1.3, 1.1, 1.8), "dumpster"], ["box", Vector3(0, 1.24, 0), Vector3(1.36, 0.08, 1.86), "dark"]],
		"solid": [[Vector3(0, 0.64, 0), Vector3(1.3, 1.28, 1.8)]], "range": 240.0},
	"tent": {"parts": [["prism", Vector3(0, 0.65, 0), Vector3(2.0, 1.3, 2.6), "tent"]], "solid": [[Vector3(0, 0.5, 0), Vector3(1.6, 1.0, 2.4)]], "range": 200.0},
	"fire_ring": {"parts": [["cyl", Vector3(0, 0.02, 0), Vector3(1.0, 0.04, 1.0), "burnt"], ["box", Vector3(0.6, 0.1, 0), Vector3(0.25, 0.2, 0.25), "concrete"],
		["box", Vector3(-0.6, 0.1, 0), Vector3(0.25, 0.2, 0.25), "concrete"], ["box", Vector3(0, 0.1, 0.6), Vector3(0.25, 0.2, 0.25), "concrete"],
		["box", Vector3(0, 0.1, -0.6), Vector3(0.25, 0.2, 0.25), "concrete"], ["box", Vector3(0.42, 0.1, 0.42), Vector3(0.22, 0.18, 0.22), "concrete"],
		["box", Vector3(-0.42, 0.1, 0.42), Vector3(0.22, 0.18, 0.22), "concrete"], ["box", Vector3(0.42, 0.1, -0.42), Vector3(0.22, 0.18, 0.22), "concrete"],
		["box", Vector3(-0.42, 0.1, -0.42), Vector3(0.22, 0.18, 0.22), "concrete"]], "range": 120.0},
	"log": {"parts": [["cyl", Vector3(0, 0.18, 0), Vector3(0.36, 2.0, 0.36), "wood", Vector3(90, 0, 0)]], "range": 140.0},
	"cart": {"parts": [["box", Vector3(0, 0.8, 0), Vector3(0.6, 0.55, 0.9), "steel"], ["box", Vector3(0, 0.3, 0), Vector3(0.5, 0.06, 0.8), "steel"],
		["box", Vector3(0, 0.55, -0.4), Vector3(0.5, 0.6, 0.04), "steel"]], "range": 140.0},
	"suitcase": {"parts": [["box", Vector3(0, 0.12, 0), Vector3(0.45, 0.22, 0.65), "suitcase"]], "range": 110.0},
	"find": {"parts": [["cyl", Vector3(0, 0.2, 0), Vector3(0.38, 0.6, 0.38), "find", Vector3(90, 0, 0)],
		["box", Vector3(0, 0.4, 0), Vector3(0.05, 0.05, 0.3), "dark"]], "range": 130.0},
	"billboard": {"parts": [["box", Vector3(-3.5, 5.0, 0), Vector3(0.5, 10.0, 0.5), "steel"], ["box", Vector3(3.5, 5.0, 0), Vector3(0.5, 10.0, 0.5), "steel"],
		["box", Vector3(0, 11.0, 0), Vector3(12.0, 4.0, 0.3), "board"], ["box", Vector3(0, 11.0, 0.17), Vector3(11.6, 3.6, 0.04), "board_face"],
		["box", Vector3(0, 8.85, 0.5), Vector3(12.0, 0.08, 0.9), "steel"]],
		"solid": [[Vector3(-3.5, 5.0, 0), Vector3(0.5, 10.0, 0.5)], [Vector3(3.5, 5.0, 0), Vector3(0.5, 10.0, 0.5)]], "range": 0.0},
	"billboard_fallen": {"parts": [["box", Vector3(0, 1.0, 0), Vector3(12.0, 0.3, 4.0), "board", Vector3(14, 0, 0)],
		["box", Vector3(0, 1.17, 0.04), Vector3(11.6, 0.04, 3.6), "board_face", Vector3(14, 0, 0)],
		["box", Vector3(-3.5, 1.0, -3.2), Vector3(0.5, 2.0, 0.5), "steel"], ["box", Vector3(3.5, 1.0, -3.2), Vector3(0.5, 2.0, 0.5), "steel"],
		["box", Vector3(-3.5, 0.3, 1.0), Vector3(0.5, 0.5, 5.0), "steel"], ["box", Vector3(3.5, 0.3, 1.0), Vector3(0.5, 0.5, 5.0), "steel"]],
		"solid": [[Vector3(0, 0.9, 0), Vector3(12.0, 1.4, 4.0)]], "range": 420.0},
	"bus_stop": {"parts": [["box", Vector3(0, 1.25, -1.0), Vector3(6.0, 2.3, 0.1), "glass"], ["box", Vector3(-3.0, 1.25, -0.1), Vector3(0.1, 2.3, 1.8), "glass"],
		["box", Vector3(3.0, 1.25, -0.1), Vector3(0.1, 2.3, 1.8), "glass"], ["box", Vector3(0, 2.55, -0.1), Vector3(6.4, 0.12, 2.4), "steel"],
		["box", Vector3(0, 0.45, -0.6), Vector3(4.0, 0.08, 0.45), "wood"], ["box", Vector3(0, 0.22, -0.6), Vector3(3.6, 0.44, 0.1), "steel"]],
		"solid": [[Vector3(0, 1.25, -1.0), Vector3(6.0, 2.3, 0.1)], [Vector3(-3.0, 1.25, -0.1), Vector3(0.1, 2.3, 1.8)],
			[Vector3(3.0, 1.25, -0.1), Vector3(0.1, 2.3, 1.8)]], "range": 420.0},
	"weed": {"parts": [["cone", Vector3(0, 0.5, 0), Vector3(0.7, 1.0, 0.7), "weed"]], "range": 70.0, "shadow": false},
	"bush": {"parts": [["dome", Vector3(0, 0.5, 0), Vector3(1.0, 1.0, 1.0), "bush"]], "range": 180.0},
	"sapling": {"parts": [["box", Vector3(0, 1.0, 0), Vector3(0.09, 2.0, 0.09), "birch"], ["cone", Vector3(0, 2.4, 0), Vector3(1.3, 2.4, 1.3), "leaf"]],
		"range": 170.0},
	"puddle": {"parts": [["cyl", Vector3(0, 0.01, 0), Vector3(1.0, 0.02, 1.0), "water"]], "range": 90.0, "shadow": false, "water": true}}

var landscape: MallLandscape
var generated: Node3D
var body: StaticBody3D
var stats: Dictionary = {}
var _meshes: Dictionary = {}
var _shapes: Dictionary = {}
var _matte: StandardMaterial3D
var _water: StandardMaterial3D


func _ready() -> void:
	landscape = get_node_or_null("../Landscape") as MallLandscape
	if landscape == null or landscape.plan.is_empty():
		return
	rebuild()


func rebuild() -> void:
	var filler: Dictionary = landscape.plan.get("filler", {}) as Dictionary
	if filler.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Filler"
	add_child(generated)
	body = StaticBody3D.new()
	body.name = "ItemsCollision"
	body.collision_mask = 0
	generated.add_child(body)
	_matte = StandardMaterial3D.new()
	_matte.vertex_color_use_as_albedo = true
	_matte.roughness = 0.9
	_water = StandardMaterial3D.new()
	_water.vertex_color_use_as_albedo = true
	_water.roughness = 0.12
	_water.metallic = 0.15
	stats = {"instances": 0, "batches": 0, "collision_shapes": 0}
	_items(filler)
	var g: RefCounted = Geometry.new(generated, Geometry.materials())
	var lines: Dictionary = filler.get("lines", {}) as Dictionary
	_power_line(g, lines.get("power", {}) as Dictionary)
	_heat_main(g, lines.get("heat", {}) as Dictionary)
	for rut: Array in lines.get("ruts", []):
		landscape.drape_strip(g, MallLandscape.poly(rut), 0.55, "mud", 0.05)
	g.finish()
	_stories(filler.get("stories", []) as Array)
	stats.collision_shapes = body.get_child_count() + (g.body as StaticBody3D).get_child_count()
	set_meta("stats", stats)


# ---------------------------------------------------------------- россыпь наборов пачками

## Экземпляры по наборам и клеткам: клетка — половина дальности видимости (32–160 м), чтобы дальние
## клетки отсекались целиком; позиция пачки — середина клетки (от неё считается дальность).
func _items(filler: Dictionary) -> void:
	var tints: Array = filler.get("tints", [])
	var groups: Dictionary = {}
	for item: Array in filler.get("items", []):
		var kit_id: String = String(item[0])
		if not KITS.has(kit_id):
			push_warning("Наполнение: нет набора " + kit_id)
			continue
		var kit: Dictionary = KITS[kit_id]
		var x: float = float(item[1])
		var z: float = float(item[2])
		var yaw: float = deg_to_rad(float(item[3]))
		var s: float = float(item[4]) if item.size() > 4 else 1.0
		var dy: float = float(item[5]) if item.size() > 5 else 0.0
		var tint: int = int(item[6]) if item.size() > 6 else -1
		var roll: float = deg_to_rad(float(item[7])) if item.size() > 7 else 0.0
		var basis: Basis = Basis(Vector3.UP, yaw) * Basis(Vector3.BACK, roll)
		var lift: float = 0.0
		if roll != 0.0:
			# машина на боку или на крыше — поднять, чтобы легла на землю, а не ушла в неё
			var box: AABB = _mesh(kit_id).get_aabb()
			var low: float = INF
			for k: int in range(8):
				low = minf(low, (basis * box.get_endpoint(k)).y)
			lift = -low
		var origin: Vector3 = Vector3(x, landscape.ground(x, z) + dy + lift * s, z)
		var xform: Transform3D = Transform3D(basis.scaled(Vector3.ONE * s), origin)
		var color: Color = Color.WHITE
		if tint >= 0 and tint < tints.size():
			color = Color(String(tints[tint]))
		elif kit.has("vary"):
			var choices: Array = VARY[kit.vary]
			color = choices[absi(int(x * 7.0) + int(z * 13.0)) % choices.size()]
		_group(groups, kit_id, xform, color)
		for solid: Array in kit.get("solid", []):
			_solid(xform, solid[0] as Vector3, solid[1] as Vector3, s)
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	for patch: Array in filler.get("weeds", []):
		rng.seed = int(patch[4])
		var c: Vector2 = Vector2(float(patch[0]), float(patch[1]))
		var radius: float = float(patch[2])
		for k: int in range(int(patch[3])):
			var p: Vector2 = c + Vector2.from_angle(rng.randf() * TAU) * radius * sqrt(rng.randf())
			var size: float = rng.randf_range(0.55, 1.35)
			var t: Transform3D = Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(size, size * rng.randf_range(0.7, 1.3), size)),
				Vector3(p.x, landscape.ground(p.x, p.y) - 0.05, p.y))
			_group(groups, "weed", t, Color(rng.randf_range(0.85, 1.1), rng.randf_range(0.9, 1.1), rng.randf_range(0.8, 1.0)))
	for key: String in groups:
		var group: Dictionary = groups[key]
		_batch(String(group.kit), group.transforms as Array, group.colors as Array)


func _group(groups: Dictionary, kit_id: String, xform: Transform3D, color: Color) -> void:
	var kit: Dictionary = KITS[kit_id]
	var reach: float = float(kit.get("range", 260.0))
	var cell: float = clampf(reach * 0.5, 32.0, 160.0)
	var key: String = kit_id
	if reach > 0.0:
		key += "|%d|%d" % [floori(xform.origin.x / cell), floori(xform.origin.z / cell)]
	if not groups.has(key):
		groups[key] = {"kit": kit_id, "transforms": [], "colors": []}
	(groups[key].transforms as Array).append(xform)
	(groups[key].colors as Array).append(color)


func _batch(kit_id: String, transforms: Array, colors: Array) -> void:
	var kit: Dictionary = KITS[kit_id]
	var center: Vector3 = Vector3.ZERO
	for t: Transform3D in transforms:
		center += t.origin
	center /= float(transforms.size())
	var multi: MultiMesh = MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_colors = true
	multi.mesh = _mesh(kit_id)
	multi.instance_count = transforms.size()
	for i: int in range(transforms.size()):
		var t: Transform3D = transforms[i]
		multi.set_instance_transform(i, Transform3D(t.basis, t.origin - center))
		multi.set_instance_color(i, colors[i])
	var visual: MultiMeshInstance3D = MultiMeshInstance3D.new()
	visual.name = "%s_%d" % [kit_id, int(stats.batches)]
	visual.multimesh = multi
	visual.position = center
	visual.material_override = _water if kit.get("water", false) else _matte
	visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if kit.get("shadow", true) else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var reach: float = float(kit.get("range", 260.0))
	if reach > 0.0:
		visual.visibility_range_end = reach
		visual.visibility_range_end_margin = reach * 0.1
		visual.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	generated.add_child(visual)
	stats.instances = int(stats.instances) + transforms.size()
	stats.batches = int(stats.batches) + 1


## Сетка набора в местных метрах: части с цветом в вершинах — один материал на всё наполнение.
func _mesh(kit_id: String) -> ArrayMesh:
	if _meshes.has(kit_id):
		return _meshes[kit_id] as ArrayMesh
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for part: Array in (KITS[kit_id] as Dictionary).parts:
		var arrays: Array = _shape(String(part[0]))
		var rotation_deg: Vector3 = part[4] if part.size() > 4 else Vector3.ZERO
		var basis: Basis = Basis.from_euler(rotation_deg * (PI / 180.0)) * Basis.from_scale(part[2] as Vector3)
		var normal_basis: Basis = basis.inverse().transposed()
		var center: Vector3 = part[1]
		var color: Color = COLORS[part[3]]
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		for index: int in arrays[Mesh.ARRAY_INDEX] as PackedInt32Array:
			st.set_color(color)
			st.set_normal((normal_basis * normals[index]).normalized())
			st.add_vertex(center + basis * vertices[index])
	var mesh: ArrayMesh = st.commit()
	_meshes[kit_id] = mesh
	return mesh


## Единичные формы (размер 1 по всем осям, центр в нуле).
func _shape(kind: String) -> Array:
	var primitive: PrimitiveMesh
	match kind:
		"cyl", "cone", "dome":
			var cylinder: CylinderMesh = CylinderMesh.new()
			cylinder.top_radius = {"cyl": 0.5, "cone": 0.0, "dome": 0.28}[kind]
			cylinder.bottom_radius = 0.5
			cylinder.height = 1.0
			cylinder.radial_segments = 8 if kind == "cyl" else 7
			cylinder.rings = 1
			primitive = cylinder
		"prism":
			var prism: PrismMesh = PrismMesh.new()
			prism.size = Vector3.ONE
			primitive = prism
		_:
			var cube: BoxMesh = BoxMesh.new()
			cube.size = Vector3.ONE
			primitive = cube
	return primitive.get_mesh_arrays()


## Коллизия части набора: коробка с поворотом экземпляра, размеры — по масштабу экземпляра.
func _solid(xform: Transform3D, center: Vector3, size: Vector3, s: float) -> void:
	var key: String = "%s|%.2f" % [str(size), s]
	if not _shapes.has(key):
		var box: BoxShape3D = BoxShape3D.new()
		box.size = size * s
		_shapes[key] = box
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.shape = _shapes[key] as BoxShape3D
	shape.transform = Transform3D(xform.basis.orthonormalized(), xform.origin + xform.basis * center)
	body.add_child(shape)


# ---------------------------------------------------------------- ЛЭП

## Опоры ЛЭП (решётчатая башня 27 м, две траверсы) и провода с провисом; последние — на крышу подстанции.
func _power_line(g: RefCounted, line: Dictionary) -> void:
	var towers: Array = line.get("towers", [])
	if towers.size() < 2:
		return
	var mounts: Array = []
	for i: int in range(towers.size()):
		var p: Vector2 = _v2(towers[i])
		var dir: Vector2 = (_v2(towers[mini(i + 1, towers.size() - 1)]) - _v2(towers[maxi(i - 1, 0)])).normalized()
		var across: Vector2 = Vector2(-dir.y, dir.x)
		var y: float = landscape.ground(p.x, p.y)
		_tower(g, p, y, dir, across)
		var points: Array[Vector3] = []
		# низ гирлянд изоляторов на траверсах и грозотрос на вершине
		for m: Vector2 in [Vector2(-7.0, 16.6), Vector2(7.0, 16.6), Vector2(-5.0, 21.6), Vector2(5.0, 21.6), Vector2(0.0, 27.6)]:
			points.append(Vector3(p.x + across.x * m.x, y + m.y, p.y + across.y * m.x))
		mounts.append(points)
	for i: int in range(towers.size() - 1):
		var a: Array = mounts[i]
		var b: Array = mounts[i + 1]
		for k: int in range(5):
			var span: float = (a[k] as Vector3).distance_to(b[k] as Vector3)
			_wire(g, a[k] as Vector3, b[k] as Vector3, span / 32.0)
	var end: Array = line.get("end", [])
	if end.size() == 3:
		var last: Array = mounts[mounts.size() - 1]
		for k: int in range(4):
			var to: Vector3 = Vector3(float(end[0]) + float(k - 1.5) * 1.6, float(end[2]) + landscape.ground(float(end[0]), float(end[1])), float(end[1]))
			_wire(g, last[k] as Vector3, to, 1.2)


func _tower(g: RefCounted, p: Vector2, y: float, dir: Vector2, across: Vector2) -> void:
	var at: Callable = func(u: float, h: float, v: float) -> Vector3:
		return Vector3(p.x + across.x * u + dir.x * v, y + h, p.y + across.y * u + dir.y * v)
	var levels: Array[float] = [0.0, 7.0, 13.0, 18.2, 23.2, 27.6]
	var half: Array[float] = [3.0, 2.2, 1.6, 1.1, 0.8, 0.5]
	var corners: Array[Vector2] = [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]
	for li: int in range(levels.size() - 1):
		for c: int in range(4):
			var c0: Vector2 = corners[c]
			var c1: Vector2 = corners[(c + 1) % 4]
			var lo0: Vector3 = at.call(c0.x * half[li], levels[li], c0.y * half[li])
			var hi0: Vector3 = at.call(c0.x * half[li + 1], levels[li + 1], c0.y * half[li + 1])
			var lo1: Vector3 = at.call(c1.x * half[li], levels[li], c1.y * half[li])
			var hi1: Vector3 = at.call(c1.x * half[li + 1], levels[li + 1], c1.y * half[li + 1])
			g.beam(lo0, hi0, 0.22, 0.22, "steel", li == 0)
			g.beam(hi0, hi1, 0.1, 0.1, "steel")
			g.beam(lo0, hi1, 0.07, 0.07, "steel")
			g.beam(lo1, hi0, 0.07, 0.07, "steel")
	g.beam(at.call(-7.4, 18.2, 0.0), at.call(7.4, 18.2, 0.0), 0.35, 0.5, "steel")
	g.beam(at.call(-5.4, 23.2, 0.0), at.call(5.4, 23.2, 0.0), 0.3, 0.45, "steel")
	# гирлянды изоляторов — отвесно вниз от траверс
	for m: Vector2 in [Vector2(-7.0, 18.2), Vector2(7.0, 18.2), Vector2(-5.0, 23.2), Vector2(5.0, 23.2)]:
		g.box(at.call(m.x, m.y - 0.85, 0.0), Vector3(0.16, 1.5, 0.16), "dark", false)


## Провод — ломаная по параболе провиса.
func _wire(g: RefCounted, a: Vector3, b: Vector3, sag: float) -> void:
	var previous: Vector3 = a
	for i: int in range(1, 13):
		var t: float = float(i) / 12.0
		var p: Vector3 = a.lerp(b, t) - Vector3.UP * sag * 4.0 * t * (1.0 - t)
		g.beam(previous, p, 0.05, 0.05, "dark")
		previous = p


# ---------------------------------------------------------------- теплотрасса

## Две трубы в изоляции на опорах в 1 м над землёй — снизу можно проползти; над дорогой и пожарным
## проездом поднимаются П-образно; через трубы — мостики-перелазы. Коллизия — по трубам и опорам.
func _heat_main(g: RefCounted, heat: Dictionary) -> void:
	var line: PackedVector2Array = MallLandscape.poly(heat.get("points", []))
	if line.size() < 2:
		return
	var total: float = 0.0
	for i: int in range(line.size() - 1):
		total += line[i].distance_to(line[i + 1])
	var low: float = float(heat.low)
	var high: float = float(heat.high)
	# отрезки «низко / высоко» по порталам
	var breaks: Array[float] = [0.0]
	for portal: Array in heat.get("portals", []):
		breaks.append(float(portal[0]))
		breaks.append(float(portal[1]))
	breaks.append(total)
	for r: int in range(breaks.size() - 1):
		var s0: float = breaks[r]
		var s1: float = breaks[r + 1]
		if s1 - s0 < 0.05:
			continue
		var lift: float = high if r % 2 == 1 else low
		var count: int = maxi(1, ceili((s1 - s0) / 6.0))
		var previous: Vector3 = _pipe_at(line, s0, lift)
		_pipe_support(g, line, s0, lift)
		for k: int in range(1, count + 1):
			var s: float = lerpf(s0, s1, float(k) / float(count))
			var p: Vector3 = _pipe_at(line, s, lift)
			var side: Vector3 = Vector3(-(p - previous).z, 0.0, (p - previous).x).normalized() * 0.45
			for offset: Vector3 in [side, -side]:
				g.beam(previous + offset + Vector3.UP * 0.35, p + offset + Vector3.UP * 0.35, 0.55, 0.55, "wall")
			_collision_beam(g.body as StaticBody3D, previous + Vector3.UP * 0.37, p + Vector3.UP * 0.37, 1.6, 0.74)
			_pipe_support(g, line, s, lift)
			previous = p
		# стояки у портала: трубы вверх и вниз (у стены ТЦ трубы входят в неё поверху — там стояка нет)
		if r % 2 == 1:
			for s: float in [s0, s1]:
				if s < 0.1 or s > total - 0.1:
					continue
				var base: Vector3 = _pipe_at(line, s, low)
				var dir: Vector2 = _direction_at(line, s)
				var side2: Vector3 = Vector3(-dir.y, 0.0, dir.x) * 0.45
				for offset: Vector3 in [side2, -side2]:
					var mid: Vector3 = base + offset + Vector3.UP * ((high - low) * 0.5 + 0.35)
					g.box(mid, Vector3(0.55, high - low + 0.55, 0.55), "wall", true)
	for s: float in heat.get("stiles", []):
		_stile(g, line, s, low)


func _pipe_at(line: PackedVector2Array, s: float, lift: float) -> Vector3:
	var p: Vector2 = _point_at(line, s)
	return Vector3(p.x, landscape.ground(p.x, p.y) + lift, p.y)


func _pipe_support(g: RefCounted, line: PackedVector2Array, s: float, lift: float) -> void:
	var p: Vector2 = _point_at(line, s)
	var dir: Vector2 = _direction_at(line, s)
	var across: Vector2 = Vector2(-dir.y, dir.x)
	var y: float = landscape.ground(p.x, p.y)
	for side: float in [-0.8, 0.8]:
		g.box(Vector3(p.x + across.x * side, y + lift * 0.5, p.y + across.y * side), Vector3(0.18, lift, 0.18), "steel", true)
	g.box(Vector3(p.x, y + lift - 0.05, p.y), Vector3(1.9, 0.12, 0.25), "steel", false, -atan2(across.y, across.x))


## Мостик через трубы: по лестнице вверх, площадка над трубами, по лестнице вниз.
func _stile(g: RefCounted, line: PackedVector2Array, s: float, low: float) -> void:
	var p: Vector2 = _point_at(line, s)
	var dir: Vector2 = _direction_at(line, s)
	var across: Vector2 = Vector2(-dir.y, dir.x)
	var y: float = landscape.ground(p.x, p.y)
	var top: float = y + low + 0.86
	var at: Callable = func(u: float, h: float) -> Vector3:
		return Vector3(p.x + across.x * u, h, p.y + across.y * u)
	g.stairs(at.call(-3.8, landscape.ground(p.x - across.x * 3.8, p.y - across.y * 3.8)), at.call(-1.2, top), 1.0, 8, "steel")
	g.stairs(at.call(3.8, landscape.ground(p.x + across.x * 3.8, p.y + across.y * 3.8)), at.call(1.2, top), 1.0, 8, "steel")
	g.box(at.call(0.0, top - 0.05), Vector3(2.5, 0.1, 1.1), "steel", true, -atan2(across.y, across.x))
	for side: float in [-0.55, 0.55]:
		var rail: Vector3 = at.call(0.0, top + 0.5) + Vector3(dir.x, 0.0, dir.y) * side
		g.box(rail, Vector3(2.5, 0.05, 0.05), "steel", false, -atan2(across.y, across.x))


func _point_at(line: PackedVector2Array, s: float) -> Vector2:
	for i: int in range(line.size() - 1):
		var d: float = line[i].distance_to(line[i + 1])
		if s <= d or i == line.size() - 2:
			return line[i].lerp(line[i + 1], clampf(s / maxf(d, 0.001), 0.0, 1.0))
		s -= d
	return line[line.size() - 1]


func _direction_at(line: PackedVector2Array, s: float) -> Vector2:
	for i: int in range(line.size() - 1):
		var d: float = line[i].distance_to(line[i + 1])
		if s <= d or i == line.size() - 2:
			return (line[i + 1] - line[i]).normalized()
		s -= d
	return Vector2.RIGHT


func _collision_beam(target: StaticBody3D, a: Vector3, b: Vector3, width: float, depth: float) -> void:
	var length_m: float = a.distance_to(b)
	if length_m < 0.01:
		return
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(width, depth, length_m)
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.shape = box
	shape.transform = Transform3D(Basis.looking_at((b - a).normalized(), Vector3.UP), (a + b) * 0.5)
	target.add_child(shape)


# ---------------------------------------------------------------- истории

## Подписи историй и районов над местом — для прогулки по черновику, видны вблизи.
func _stories(list: Array) -> void:
	for story: Dictionary in list:
		var at: Array = story.at
		var label: Label3D = Label3D.new()
		label.text = String(story.label)
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.font_size = 64
		label.pixel_size = 0.012
		label.outline_size = 12
		label.modulate = Color("f0c27a")
		label.visibility_range_end = 160.0
		label.position = Vector3(float(at[0]), landscape.ground(float(at[0]), float(at[1])) + float(story.get("height", 5.0)), float(at[1]))
		generated.add_child(label)


func _v2(p: Variant) -> Vector2:
	var a: Array = p
	return Vector2(float(a[0]), float(a[1]))
