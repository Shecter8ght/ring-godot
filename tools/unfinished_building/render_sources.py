import bpy
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "high"
OUT = ROOT / "_asset_src" / "unfinished_building" / "catalog"
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.world.color = (0.18, 0.18, 0.18)
scene.world.use_nodes = True
scene.world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.32, 0.36, 0.42, 1)
scene.world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.45

camera_data = bpy.data.cameras.new("CatalogCamera")
camera = bpy.data.objects.new("CatalogCamera", camera_data)
scene.collection.objects.link(camera)
camera_data.type = "ORTHO"
scene.camera = camera

def light(name, location, energy, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj

lights = [
    light("Key", (4, -5, 7), 1400, 5),
    light("Fill", (-4, -1, 3), 800, 4),
    light("Rim", (2, 5, 5), 1100, 3),
]

for path in sorted(SOURCE.glob("*/*.fbx")):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    center = (low + high) * 0.5
    size = max(high - low)
    material = bpy.data.materials.new(path.stem)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    for suffix, socket in [("BaseColor", "Base Color"), ("Roughness", "Roughness")]:
        image_path = path.parent / f"{path.stem}_4K_{suffix}.jpg"
        if image_path.exists():
            image = bpy.data.images.load(str(image_path), check_existing=True)
            if suffix != "BaseColor":
                image.colorspace_settings.name = "Non-Color"
            texture = nodes.new("ShaderNodeTexImage")
            texture.image = image
            links.new(texture.outputs["Color"], bsdf.inputs[socket])
    normal_path = path.parent / f"{path.stem}_4K_Normal.jpg"
    if normal_path.exists():
        image = bpy.data.images.load(str(normal_path), check_existing=True)
        image.colorspace_settings.name = "Non-Color"
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = image
        normal = nodes.new("ShaderNodeNormalMap")
        links.new(texture.outputs["Color"], normal.inputs["Color"])
        links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    for obj in meshes:
        obj.data.materials.clear()
        obj.data.materials.append(material)
    for obj in lights:
        obj.location = center + Vector((obj.location.x, obj.location.y, obj.location.z)) * max(size * 0.4, 0.5)
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.data.size = max(size * 1.2, 0.5)
        obj.data.energy = max(700 * size * size, 80)
    camera.location = center + Vector((1.0, -1.35, 0.78)).normalized() * max(size * 2.5, 1.0)
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.ortho_scale = max(size * 1.15, 0.2)
    scene.render.filepath = str(OUT / f"{path.stem}.png")
    bpy.ops.render.render(write_still=True)
    print(f"CATALOG {path.stem}")
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"CATALOG_DIR {OUT}")
