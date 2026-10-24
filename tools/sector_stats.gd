extends Node
## Сводка собранного сектора: сколько стен, полов, дверей, стёкол, вывесок и огней даёт JSON.
## Нужна, чтобы правка SectorBuilder не меняла старые уровни: снять до правки и после — сравнить.
## godot --headless res://tools/sector_stats.tscn -- res://data/sectors/mall_map.json [ещё.json …]


func _ready() -> void:
	var paths: Array[String] = []
	for a: String in OS.get_cmdline_user_args():
		if a.ends_with(".json"):
			paths.append(a)
	if paths.is_empty():
		paths.append("res://data/sectors/mall_map.json")
	for path: String in paths:
		var builder := SectorBuilder.new()
		var t0 := Time.get_ticks_msec()
		var root: Node3D = builder.build(path)
		add_child(root)
		print("sector_stats: %s (%d мс)" % [path, Time.get_ticks_msec() - t0])
		for group: String in ["Floors", "Walls"]:
			var body := root.get_node_or_null(group)
			if body == null:
				continue
			var names: Array[String] = []
			for c: Node in body.get_children():
				var mi := c as MeshInstance3D
				if mi == null or String(mi.name).ends_with("_shadow"):
					continue
				names.append("%s=%d" % [mi.name, (mi.mesh as ArrayMesh).surface_get_array_len(0)])
			names.sort()
			print("  %s: %s" % [group, ", ".join(names)])
		for group: String in ["Doors", "Signs", "Lights", "Loot", "Markers"]:
			var n := root.get_node_or_null(group)
			print("  %s: %d" % [group, n.get_child_count() if n else 0])
		var panes := root.get_node_or_null("GlassPanes")
		print("  GlassPanes: %s" % ("есть" if panes else "нет"))
		print("  props: %d" % int(root.get_meta("prop_count", 0)))
	get_tree().quit()
