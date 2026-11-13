extends SceneTree
## Проба: узлы модели контейнера и диапазоны видимости (lc_vis_probe.gd -- <вид>).
func _init() -> void:
	var kind: String = OS.get_cmdline_user_args()[0]
	var v: LootContainerVisual = LootContainerVisual.create(kind, "", 0)
	root.add_child(v)
	for n: Node in v.find_children("*", "MeshInstance3D", true, false):
		var m: MeshInstance3D = n as MeshInstance3D
		print(m.get_path(), " vis ", m.visible, " begin ", m.visibility_range_begin, " end ", m.visibility_range_end, " fade ", m.visibility_range_fade_mode, " tris ", m.mesh.get_faces().size() / 3)
	quit()
