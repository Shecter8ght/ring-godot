class_name Surfaces
extends RefCounted
## Из чего сделана поверхность в точке попадания: по материалу меша (стены/полы сектора),
## по типу пропа или по телу. Возвращает вид: concrete, tile, asphalt, metal, glass, wood,
## cardboard, fabric, plastic, flesh, snow. Для своих уровней из редактора: meta "surface" на
## StaticBody3D или на CollisionShape3D (например "metal") — главнее всего остального.

const MATERIAL_KIND := {
	"large_floor_tiles_02": "tile", "worn_tile_floor": "tile",
	"concrete_floor_worn_001": "concrete", "concrete_wall_006": "concrete", "concrete_panels": "concrete",
	"concrete_block_wall_02": "concrete", "painted_plaster_wall": "concrete",
	"asphalt_02": "asphalt",
	"painted_metal_shutter": "metal", "corrugated_iron_02": "metal", "metal_plate": "metal", "steel_dark": "metal",
	"glass": "glass", "sign_panel": "plastic",
	"gb_facade": "concrete", "gb_fire": "concrete", "gb_structural": "concrete", "gb_partition": "concrete",
	"gb_fence": "concrete", "gb_slab": "concrete",
	"gbf_tile": "tile", "gbf_concrete": "concrete", "gbf_asphalt": "asphalt",
}

const PROP_KIND := {
	"shelf_retail": "metal", "shelf_warehouse": "metal", "cart": "metal", "car": "metal", "truck": "metal",
	"barrel": "metal", "cabinet": "metal", "bin": "metal",
	"pallet_boxes": "cardboard", "box_stack": "cardboard",
	"desk": "wood", "bench": "wood", "checkout": "wood", "kiosk": "wood",
	"planter": "concrete",
}


static func kind_at(hit: Dictionary) -> String:
	var body: Object = hit.get("collider")
	if body == null:
		return "concrete"
	if body is Target:
		# поппер — сталь; бумажная мишень и манекен тира говорят о себе сами (meta "surface")
		return String((body as Node).get_meta("surface", "metal"))
	if body is Marauder or body is Player or body is RagdollPart:
		return "flesh"
	var node := body as Node
	if node == null:
		return "concrete"
	if node is CollisionObject3D and hit.has("shape"):
		var sn := (node as CollisionObject3D).shape_owner_get_owner((node as CollisionObject3D).shape_find_owner(int(hit.shape)))
		if sn and sn.has_meta("surface"):
			return String(sn.get_meta("surface"))
	if node.has_meta("surface"):
		return String(node.get_meta("surface"))
	if node.get_parent() is Door:
		return "metal"
	if PROP_KIND.has(node.name):
		return String(PROP_KIND[node.name])
	# Стены/полы сектора: один StaticBody на всё, форма названа по материалу (<id>_col).
	if node is CollisionObject3D and hit.has("shape"):
		var co := node as CollisionObject3D
		var owner_id := co.shape_find_owner(int(hit.shape))
		var shape_node := co.shape_owner_get_owner(owner_id)
		if shape_node:
			var mat_id := String(shape_node.name).trim_suffix("_col")
			if mat_id.begins_with("banner_"):
				return "fabric"
			if MATERIAL_KIND.has(mat_id):
				return String(MATERIAL_KIND[mat_id])
	return "concrete"
