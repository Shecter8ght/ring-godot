"""Материалы и карты файла (только чтение): какие материалы у сеток и какие картинки в узлах."""
import bpy

for m in bpy.data.materials:
    imgs = []
    if m.use_nodes and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                imgs.append((n.image.name, n.image.filepath, n.image.colorspace_settings.name))
    users = [o.name for o in bpy.data.objects if o.type == "MESH" and any(s.material == m for s in o.material_slots)]
    print("MAT", m.name, len(users), users[:4], imgs, flush=True)
for o in bpy.data.objects:
    if o.type == "MESH" and "Round_01" in o.name:
        print("ROUND", o.name, [s.material.name if s.material else None for s in o.material_slots], o.data.name)
