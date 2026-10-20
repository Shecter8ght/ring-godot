"""Build the first editable M02 anatomy candidate from installed CC0 MPFB assets.

Runs in a separate factory Blender process. Never opens or overwrites a user's scene.
The unbaked parametric source is retained separately from the clean T-pose model.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

import addon_utils
import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src" / "npc_m02"
REF = ROOT / "docs" / "design" / "concepts" / "npc_2026-10-20"
MODULE = "bl_ext.blender_org.mpfb"


def enable_mpfb():
    if MODULE not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module = MODULE
    addon_utils.enable(MODULE, default_set=False, persistent=False)
    services = {}
    for module, name in [
        ("humanservice", "HumanService"),
        ("targetservice", "TargetService"),
        ("rigservice", "RigService"),
        ("locationservice", "LocationService"),
        ("objectservice", "ObjectService"),
    ]:
        services[name] = getattr(importlib.import_module(MODULE + ".services." + module), name)
    return services


def active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def move_to(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)


def material(name, color, roughness=0.58):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1)
    return mat


def alpha_asset_material(name, image_path, tint, roughness=0.7):
    """A restrained preview material using the bundled asset's original alpha."""
    mat = material(name, tint, roughness)
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(image_path), check_existing=True)
    multiply = tree.nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1.0
    multiply.inputs[2].default_value = (*tint, 1.0)
    tree.links.new(texture.outputs["Color"], multiply.inputs[1])
    tree.links.new(multiply.outputs[0], bsdf.inputs["Base Color"])
    tree.links.new(texture.outputs["Alpha"], bsdf.inputs["Alpha"])
    if "surface_render_method" in mat.bl_rna.properties:
        identifiers = [e.identifier for e in mat.bl_rna.properties["surface_render_method"].enum_items]
        if "DITHERED" in identifiers:
            mat.surface_render_method = "DITHERED"
    return mat


def mesh_report(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    result = {
        "name": obj.name,
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "quads": sum(len(f.verts) == 4 for f in bm.faces),
        "triangles": sum(len(f.verts) == 3 for f in bm.faces),
        "ngons": sum(len(f.verts) > 4 for f in bm.faces),
        "boundary_edges": sum(e.is_boundary for e in bm.edges),
        "wire_edges": sum(e.is_wire for e in bm.edges),
        "nonmanifold_edges": sum(not e.is_manifold and not e.is_boundary for e in bm.edges),
        "uv_layers": [layer.name for layer in obj.data.uv_layers],
    }
    bm.free()
    return result


def evaluated_points(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(dg)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def add_asset(human, services, user_data, relative, kind, name, subdiv=1):
    before = set(bpy.data.objects)
    result = services["HumanService"].add_mhclo_asset(
        str(user_data / relative), human, asset_type=kind,
        subdiv_levels=subdiv, material_type="MAKESKIN",
    )
    if isinstance(result, bpy.types.Object):
        obj = result
    else:
        obj = max((o for o in set(bpy.data.objects) - before if o.type == "MESH"), key=lambda o: len(o.data.vertices))
    obj.name = name
    return obj


def make_shorts(body, cloth_col, cloth_mat, rig):
    """A fitted neutral cover derived from the body surface, with open cuffs."""
    shorts = body.copy()
    dg = bpy.context.evaluated_depsgraph_get()
    shorts.data = bpy.data.meshes.new_from_object(body.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    cloth_col.objects.link(shorts)
    shorts.name = "M02_Simple_Reference_Shorts"
    for mod in list(shorts.modifiers):
        shorts.modifiers.remove(mod)
    shorts.parent = rig
    shorts.data.materials.clear()
    shorts.data.materials.append(cloth_mat)
    bm = bmesh.new()
    bm.from_mesh(shorts.data)
    bm.normal_update()
    for vertex in bm.verts:
        vertex.co += vertex.normal * 0.014
    # Keep the connected lower torso / upper thighs, then cut a clean waist and cuffs.
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 1.08 or v.co.z < 0.58], context="VERTS")
    for z, normal in [(1.035, (0, 0, 1)), (0.65, (0, 0, -1))]:
        bmesh.ops.bisect_plane(
            bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            plane_co=(0, 0, z), plane_no=normal,
            clear_outer=True, clear_inner=False, dist=0.00001,
        )
    bm.to_mesh(shorts.data)
    bm.free()
    for p in shorts.data.polygons:
        p.use_smooth = True
    arm = shorts.modifiers.new("New_Anatomical_Rig", "ARMATURE")
    arm.object = rig
    shell = shorts.modifiers.new("Cloth_thickness", "SOLIDIFY")
    shell.thickness = 0.002
    shell.offset = 0
    return shorts


def camera(col, name, pos, target, ortho):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    col.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data.type = "ORTHO"
    data.ortho_scale = ortho
    data.lens = 75
    return obj


def area(col, name, pos, target, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    col.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def render_view(name, cams, folder, size):
    scene = bpy.context.scene
    scene.camera = cams[name]
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(folder / (name + ".png"))
    bpy.ops.render.render(write_still=True)


def build(args):
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / args.version
    out.mkdir(exist_ok=True)
    services = enable_mpfb()
    HumanService, TargetService, RigService = (services[n] for n in ["HumanService", "TargetService", "RigService"])
    data = Path(services["LocationService"].get_mpfb_data())
    user_data = Path(services["LocationService"].get_user_data())

    # Only the fresh factory scene of this process is cleared.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    anatomy = collection("01_M02_Anatomy")
    details = collection("02_Head_Parts")
    clothes = collection("03_Reference_Shorts")
    rigs = collection("04_New_Anatomical_Rig")
    refs = collection("05_Embedded_References")
    studio = collection("06_Review_Studio")

    macro = TargetService.get_default_macro_info_dict()
    macro.update(gender=1.0, age=0.58, muscle=0.69, weight=0.51, proportions=0.50, height=0.50)
    macro["race"] = {"caucasian": 0.92, "asian": 0.08, "african": 0.0}
    human = HumanService.create_human(scale=0.1, macro_detail_dict=macro)
    human.name = "M02_Body_Head"
    move_to(human, anatomy)

    # Moderate features from M02, retained in a parametric source for later correction.
    targets = {
        "head/head-oval": 0.16,
        "head/head-scale-vert-decr": 0.08,
        "head/head-age-incr": 0.12,
        "chin/chin-width-incr": 0.13,
        "chin/chin-prominent-incr": 0.13,
        "chin/chin-height-decr": 0.06,
        "nose/nose-scale-horiz-decr": 0.09,
        "nose/nose-scale-depth-incr": 0.10,
        "nose/nose-point-down": 0.07,
        "mouth/mouth-upperlip-volume-decr": 0.08,
        "mouth/mouth-lowerlip-volume-decr": 0.06,
        "neck/neck-scale-horiz-incr": 0.07,
        "forehead/forehead-trans-forward": 0.06,
        "expression/units/caucasian/mouth-open": -0.06,
    }
    for side in ["l", "r"]:
        targets[f"eyes/{side}-eye-height2-decr"] = 0.22
        targets[f"eyes/{side}-eye-bag-height-incr"] = 0.06
        targets[f"cheek/{side}-cheek-bones-incr"] = 0.08
    for name, weight in targets.items():
        shape = TargetService.load_target(human, str(data / "targets" / (name + ".target.gz")), weight=max(0, weight))
        if weight < 0:
            shape.slider_min = -1.0
            shape.value = weight
    bpy.context.view_layer.update()
    body_points = evaluated_points(human)
    low, high = min(v.z for v in body_points), max(v.z for v in body_points)
    # Uniformly scale every basis and target so the future rig sees correct geometry.
    factor = 1.78 / (high - low)
    for key in human.data.shape_keys.key_blocks:
        for vertex in key.data:
            vertex.co.z -= low
            vertex.co *= factor
    bpy.context.view_layer.update()

    clay = material("M02_Neutral_Anatomy_Clay", (0.28, 0.265, 0.245), 0.68)
    human.data.materials.clear()
    human.data.materials.append(clay)
    rig = HumanService.add_builtin_rig(human, "default", import_weights=True)
    rig.name = "M02_New_Anatomical_Rig"
    move_to(rig, rigs)

    asset_specs = [
        ("eyes/high-poly/high-poly.mhclo", "Eyes", "M02_Eyes", 1),
        ("teeth/teeth_base/teeth_base.mhclo", "Teeth", "M02_Teeth", 1),
        ("tongue/tongue01/tongue01.mhclo", "Tongue", "M02_Tongue", 1),
        ("eyebrows/eyebrow001/eyebrow001.mhclo", "Eyebrows", "M02_Eyebrows", 0),
        ("eyelashes/eyelashes01/eyelashes01.mhclo", "Eyelashes", "M02_Eyelashes", 0),
        ("hair/short02/short02.mhclo", "Hair", "M02_Separate_Short_Hair", 0),
    ]
    parts = []
    for relative, kind, name, subdivision in asset_specs:
        part = add_asset(human, services, user_data, relative, kind, name, subdivision)
        move_to(part, details)
        parts.append(part)

    for object_name, image_file, tint in [
        ("M02_Separate_Short_Hair", "hair/short02/short02_diffuse.png", (0.24, 0.17, 0.115)),
        ("M02_Eyebrows", "eyebrows/eyebrow001/eyebrow001.png", (0.23, 0.17, 0.12)),
        ("M02_Eyelashes", "eyelashes/eyelashes01/eyelashes01.png", (0.13, 0.10, 0.075)),
    ]:
        part = bpy.data.objects[object_name]
        part.data.materials.clear()
        part.data.materials.append(alpha_asset_material(object_name + "_Preview", user_data / image_file, tint))

    hair = bpy.data.objects["M02_Separate_Short_Hair"]
    hair_sub = hair.modifiers.new("Hair_Silhouette_Smoothing", "SUBSURF")
    hair_sub.levels = 1
    hair_sub.render_levels = 2
    eyes = bpy.data.objects["M02_Eyes"]
    # Preserve the separate cornea material/UV assignment of the eye asset.
    for eye_mat in eyes.data.materials:
        if not eye_mat or not eye_mat.use_nodes:
            continue
        eye_tree = eye_mat.node_tree
        for texture in list(eye_tree.nodes):
            if texture.type != "TEX_IMAGE" or not texture.image or "brown_eye" not in texture.image.name:
                continue
            old_links = [(link.to_node, link.to_socket) for link in texture.outputs["Color"].links]
            eye_color = eye_tree.nodes.new("ShaderNodeHueSaturation")
            eye_color.inputs["Hue"].default_value = 0.545
            eye_color.inputs["Saturation"].default_value = 0.65
            eye_color.inputs["Value"].default_value = 0.85
            eye_tree.links.new(texture.outputs["Color"], eye_color.inputs["Color"])
            for target_node, target_socket in old_links:
                eye_tree.links.new(eye_color.outputs["Color"], target_socket)

    # Preserve full MakeHuman topology, helpers and target sliders before baking.
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "M02_Parametric_Apose_Source.blend"), check_existing=False)

    active(rig)
    bpy.ops.object.mode_set(mode="POSE")
    pose = json.loads((data / "poses" / "default_fk" / "t-pose.json").read_text(encoding="utf-8"))
    RigService.set_pose_from_dict(rig, pose)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    RigService.apply_pose_as_rest_pose(rig)
    bpy.context.view_layer.update()

    points = evaluated_points(human)
    final_scale = 1.78 / (max(v.z for v in points) - min(v.z for v in points))
    matrix = Matrix.Scale(final_scale, 4)
    for obj in [human, *parts]:
        obj.data.transform(matrix, shape_keys=True)
        obj.location *= final_scale
    rig.data.transform(matrix)
    rig.location *= final_scale
    bpy.context.view_layer.update()

    # Remove only the fitting helpers from the review mesh; the source above retains them.
    body_index = human.vertex_groups["body"].index
    keep = {v.index for v in human.data.vertices if any(g.group == body_index and g.weight > 0.5 for g in v.groups)}
    for mod in list(human.modifiers):
        if mod.type == "MASK":
            human.modifiers.remove(mod)
    bm = bmesh.new()
    bm.from_mesh(human.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS")
    bm.to_mesh(human.data)
    bm.free()
    for poly in human.data.polygons:
        poly.use_smooth = True
    human.data.update()
    bpy.context.view_layer.update()

    # The rig's pose can shift soles slightly. Ground the complete character together.
    points = evaluated_points(human)
    bottom = min(v.z for v in points)
    rig.location.z -= bottom
    bpy.context.view_layer.update()
    sub = human.modifiers.new("Editable_Smooth_Surface", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    bpy.context.view_layer.update()
    # Give fitted hair cards a small clearance at the temples without cutting the hairline.
    hair = bpy.data.objects["M02_Separate_Short_Hair"]
    body_bvh = BVHTree.FromObject(human, bpy.context.evaluated_depsgraph_get())
    hair_to_body = human.matrix_world.inverted() @ hair.matrix_world
    body_to_hair = hair_to_body.inverted()
    for vertex in hair.data.vertices:
        world = hair.matrix_world @ vertex.co
        if not (1.60 < world.z < 1.72 and abs(world.x) > 0.06 and world.y < 0.04):
            continue
        position = hair_to_body @ vertex.co
        nearest, normal, _, distance = body_bvh.find_nearest(position)
        if nearest is not None and distance < 0.018 and (position - nearest).dot(normal) < 0.002:
            vertex.co = body_to_hair @ (nearest + normal * 0.002)
    hair.data.update()
    cloth_mat = material("M02_Plain_Gray_Shorts", (0.13, 0.15, 0.18), 0.88)
    shorts = make_shorts(human, clothes, cloth_mat, rig)

    # References are packed, isolated and disabled in rendering.
    for index, filename in enumerate(["M02_urban_average_front_v01.png", "M02_urban_average_sheet_v01.png"]):
        image = bpy.data.images.load(str(REF / filename), check_existing=True)
        image.pack()
        obj = bpy.data.objects.new("Reference_" + ("Front" if index == 0 else "Turnaround"), None)
        refs.objects.link(obj)
        obj.empty_display_type = "IMAGE"
        obj.data = image
        obj.empty_display_size = 2.0
        obj.location = (2.2 + index * 2.25, 0.35, 0.90)
        obj.rotation_euler = (math.pi / 2, 0, 0)
        obj.hide_render = True
        obj.color[3] = 0.65
    refs.hide_render = True
    refs.hide_viewport = True

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    for engine in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"]:
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 32
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.view_settings.exposure = -0.6
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (TypeError, ValueError):
        pass
    scene.world.use_nodes = True
    background = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    background.inputs[0].default_value = (0.18, 0.19, 0.20, 1)
    background.inputs[1].default_value = 1.0

    floor_mat = material("Studio_Backdrop", (0.18, 0.19, 0.20), 0.9)
    floor_bsdf = next(n for n in floor_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Emission Color" in floor_bsdf.inputs:
        floor_bsdf.inputs["Emission Color"].default_value = (0.15, 0.16, 0.17, 1.0)
        floor_bsdf.inputs["Emission Strength"].default_value = 0.8
    mesh = bpy.data.meshes.new("Studio_Floor")
    mesh.from_pydata([(-200, -200, -0.006), (200, -200, -0.006), (200, 200, -0.006), (-200, 200, -0.006)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("Studio_Floor", mesh)
    studio.objects.link(floor)
    floor.data.materials.append(floor_mat)
    area(studio, "Large_Key", (-2.5, -3.0, 3.1), (0, 0, 1.15), 300, 2.0)
    area(studio, "Soft_Fill", (2.0, -2.2, 2.1), (0, 0, 1.2), 65, 2.4)
    area(studio, "Shoulder_Separation", (0.8, 1.8, 2.8), (0, 0, 1.3), 150, 1.8)
    cams = {
        "body_front": camera(studio, "Camera_Body_Front", (0, -4, 0.90), (0, 0, 0.90), 2.02),
        "body_back": camera(studio, "Camera_Body_Back", (0, 4, 0.90), (0, 0, 0.90), 2.02),
        "body_profile": camera(studio, "Camera_Body_Profile", (4, 0, 0.90), (0, 0, 0.90), 2.02),
        "head_front": camera(studio, "Camera_Head_Front", (0, -3, 1.66), (0, -0.025, 1.66), 0.33),
        "head_profile": camera(studio, "Camera_Head_Profile", (3, 0, 1.66), (0, -0.025, 1.66), 0.40),
        "head_three_quarter": camera(studio, "Camera_Head_ThreeQuarter", (2.1, -3, 1.68), (0, -0.025, 1.66), 0.33),
    }
    scene.camera = cams["body_front"]
    scene.render.resolution_x = scene.render.resolution_y = 1536
    scene.render.resolution_percentage = 100

    rig.show_in_front = False
    active(human)
    for screen in bpy.data.screens:
        for ui_area in screen.areas:
            if ui_area.type == "VIEW_3D":
                ui_area.spaces.active.region_3d.view_distance = 3.0
                ui_area.spaces.active.region_3d.view_location = (0, 0, 0.9)
                ui_area.spaces.active.region_3d.view_rotation = Quaternion((1, 0, 0), math.pi / 2)
                ui_area.spaces.active.region_3d.view_perspective = "ORTHO"
                ui_area.spaces.active.clip_end = 200
                ui_area.spaces.active.shading.type = "SOLID"
                ui_area.spaces.active.shading.color_type = "MATERIAL"
                ui_area.spaces.active.shading.show_cavity = True
    text = bpy.data.texts.new("00_READ_ME")
    text.use_fake_user = True
    text.write("M02 — geometry candidate. Height 1.78 m.\n"
               "Editable body and head are one continuous quad surface. Eyes, teeth, tongue, eyebrows, eyelashes and hair are separate.\n"
               "The new anatomical MPFB rig is a preliminary fitting rig in T-rest pose. No old Persona/Mixamo rig is used.\n"
               "Reference shorts can be hidden independently. Embedded references are in collection 05.\n"
               "The unbaked parametric A-pose source is saved separately.\n"
               "Base mesh, morphs and bundled body parts are MakeHuman/MPFB CC0 core assets.\n"
               "Geometry requires owner review before final surface work, clothing production and game integration.\n")
    for obj in studio.objects:
        obj.hide_set(True)
    rig.hide_set(True)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    output_file = out / ("M02_Body_Head_Geometry_" + args.version.replace("geometry_", "") + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_file), check_existing=False)

    # Measure the cage, not the helper geometry or the studio floor.
    sub.show_viewport = False
    points = evaluated_points(human)
    report = {
        "file": str(output_file), "source": str(out / "M02_Parametric_Apose_Source.blend"),
        "blender": bpy.app.version_string, "macro": macro, "targets": targets,
        "height_m": max(v.z for v in points) - min(v.z for v in points),
        "arm_span_m": max(v.x for v in points) - min(v.x for v in points),
        "rig_bones": len(rig.data.bones), "rig_type": "new MPFB default anatomical rig, T rest",
        "meshes": [mesh_report(obj) for obj in [human, *parts, shorts]],
        "packed_images": sum(image.packed_file is not None for image in bpy.data.images),
    }
    sub.show_viewport = True
    (out / "geometry_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("NPC_M02_BUILT " + json.dumps({k: report[k] for k in ["file", "height_m", "arm_span_m", "rig_bones", "packed_images"]}))
    if args.render:
        for name in args.render.split(","):
            render_view(name, cams, out, (1536, 1536) if name.startswith("body") else (1400, 1600))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="geometry_v01")
    parser.add_argument("--render", default="body_front,head_three_quarter")
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build(parser.parse_args(arguments))
