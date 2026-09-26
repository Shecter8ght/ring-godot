"""Отдельные руки первого лица из Persona; исходный .blend не изменяется."""
from pathlib import Path
import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=r"D:\ПРОГРАММЫ\Blender 5\Projects\Persona.blend")
arm = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
arm.animation_data_clear()
names = {"Human", "Human.male_casualsuit05"}
for obj in bpy.data.objects:
    obj.select_set(obj == arm or obj.name in names)
    if obj.name not in names:
        continue
    obj.data = obj.data.copy()
    if obj.name == "Human":
        # В промежуточном Mixamo-риге пясть заменена постоянным весом 0.2.
        # Восстанавливаем сумму исходных MakeHuman-весов: ладонь не тянется за пальцами.
        for short, side in (("L", "Left"), ("R", "Right")):
            sources = {g.index for g in obj.vertex_groups
                       if g.name == "wrist." + short
                       or g.name.startswith("metacarpal") and g.name.endswith("." + short)}
            hand = obj.vertex_groups["mixamorig:" + side + "Hand"]
            weights = [(v.index, sum(g.weight for g in v.groups if g.group in sources))
                       for v in obj.data.vertices]
            hand.remove([v.index for v in obj.data.vertices])
            for index, weight in weights:
                if weight > 0:
                    hand.add([index], min(1.0, weight), "REPLACE")
    groups = {g.index for g in obj.vertex_groups if any(
        part in g.name for part in ("LeftArm", "RightArm", "ForeArm", "Hand"))}
    deform = {g.index for g in obj.vertex_groups if g.name in arm.data.bones}
    # В исходнике веса перенесённого Mixamo-рига не нормализованы (ладонь бывает 0.2).
    # Сравниваем долю среди деформирующих костей, иначе вырезаются части ладони.
    keep = {v.index for v in obj.data.vertices
            if sum(g.weight for g in v.groups if g.group in groups) > 0.0
            and sum(g.weight for g in v.groups if g.group in groups)
            >= 0.5 * sum(g.weight for g in v.groups if g.group in deform)}
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v.index not in keep], context="VERTS")
    mesh.to_mesh(obj.data)
    mesh.free()
    # Срез рукава не должен оставаться привязанным к скрытым груди/ключице.
    # Маски MakeHuman сохраняем; удаляем только веса остальных костей.
    allowed_names = {g.name for g in obj.vertex_groups if g.index in groups}
    for group in list(obj.vertex_groups):
        if group.name in arm.data.bones and group.name not in allowed_names:
            obj.vertex_groups.remove(group)
    for mod in obj.modifiers:
        if mod.type == "SUBSURF":
            mod.levels = max(mod.levels, mod.render_levels)
    if obj.name == "Human":
        mod = obj.modifiers.new("Finger smoothing", "SUBSURF")
        mod.levels = mod.render_levels = 1
    for face in obj.data.polygons:
        face.use_smooth = True
bpy.context.view_layer.objects.active = arm
output = ROOT / "assets/models/characters/persona_arms.glb"
bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", use_selection=True,
                          export_animations=False, export_apply=True)
print("EXPORTED ARMS", output.stat().st_size)
