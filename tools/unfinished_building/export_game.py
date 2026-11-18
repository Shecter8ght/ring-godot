import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "high"
OUT = ROOT / "assets" / "models" / "unfinished_building"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "textures").mkdir(exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for path in sorted(SOURCE.glob("*/*.fbx")):
    bpy.ops.object.select_all(action="DESELECT")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    material = bpy.data.materials.new(f"UB_{path.stem}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Metallic"].default_value = 0.0
    textures = {}
    for suffix, socket in [("BaseColor", "Base Color"), ("Roughness", "Roughness")]:
        image_path = path.parent / f"{path.stem}_4K_{suffix}.jpg"
        if not image_path.exists():
            continue
        image = bpy.data.images.load(str(image_path), check_existing=True)
        if suffix != "BaseColor":
            image.colorspace_settings.name = "Non-Color"
        texture = nodes.new("ShaderNodeTexImage")
        texture.name = suffix
        texture.image = image
        textures[suffix] = texture
        links.new(texture.outputs["Color"], bsdf.inputs[socket])
    normal_path = path.parent / f"{path.stem}_4K_Normal.jpg"
    if normal_path.exists():
        image = bpy.data.images.load(str(normal_path), check_existing=True)
        image.colorspace_settings.name = "Non-Color"
        texture = nodes.new("ShaderNodeTexImage")
        texture.name = "Normal"
        texture.image = image
        textures["Normal"] = texture
        normal = nodes.new("ShaderNodeNormalMap")
        links.new(texture.outputs["Color"], normal.inputs["Color"])
        links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    ao_path = path.parent / f"{path.stem}_4K_AO.jpg"
    if ao_path.exists():
        image = bpy.data.images.load(str(ao_path), check_existing=True)
        image.colorspace_settings.name = "Non-Color"
        texture = nodes.new("ShaderNodeTexImage")
        texture.name = "AO"
        texture.image = image
        group_name = "glTF Material Output"
        group = bpy.data.node_groups.get(group_name)
        if group is None:
            group = bpy.data.node_groups.new(group_name, "ShaderNodeTree")
            group.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        occlusion = nodes.new("ShaderNodeGroup")
        occlusion.node_tree = group
        links.new(texture.outputs["Color"], occlusion.inputs["Occlusion"])
    for obj in meshes:
        obj.data.materials.clear()
        obj.data.materials.append(material)
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / f"{path.stem}.gltf"),
        export_format="GLTF_SEPARATE",
        export_texture_dir="textures",
        use_selection=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_yup=True,
    )
    print(f"EXPORTED {path.stem}")
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"EXPORT_DIR {OUT}")
