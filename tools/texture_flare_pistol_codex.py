"""Native UCUPaint authoring on the owner-approved, saved Codex geometry v02.

Blender 5.2.2 / UCUPaint 2.4.9, --python-exit-code 1.
-- prepare|test|build|render|inspect [asset folder]
Prepare emits silhouette guides; flare_pistol_wear_masks.py makes original image masks.
No topology, pivots, modifiers or game files are replaced by this authoring step.
"""

import addon_utils
import hashlib
import importlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent if HERE.name == "source" else HERE.parent / "_asset_src" / "flare_pistol_codex"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "build"
OUT = Path(ARGS[1]) if len(ARGS) > 1 else DEFAULT_OUT
SOURCE = OUT / "models" / "launcher" / "flare_pistol_codex_geometry_v02.blend"
ORIGINAL = OUT / "models" / "launcher" / "flare_pistol_codex_geometry_v01.blend"
MASTER = OUT / "models" / "launcher" / "flare_pistol_codex_ucupaint_worn_v01.blend"
TEST = OUT / "checks" / "texturing_v01" / "material_test.blend"
TEXTURES = OUT / "textures" / "worn_v01"
CHECKS = OUT / "checks" / "texturing_v01"
PREVIEWS = OUT / "previews" / "texturing_v01"
UV = "PaintUV"
GUIDE_UV = "WearGuideXZ"
SKILL = Path("C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing")
U = H = None


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native():
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    helper_path = HERE / "ucupaint_helpers.py"
    H = load_module(helper_path if helper_path.exists() else SKILL / "scripts" / "ucupaint_helpers.py", "flare_ucup_helpers")
    U = H.load_ucupaint()
    print("NATIVE_UCUPAINT", U.common.get_current_version_str(), flush=True)


def cap_outline(obj):
    cap = max(obj.data.polygons, key=lambda face: len(face.vertices))
    pts = [(obj.data.vertices[i].co.x * 1000, obj.data.vertices[i].co.z * 1000)
           for i in cap.vertices]
    area = sum(pts[i][0] * pts[(i+1) % len(pts)][1]
               - pts[(i+1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if area > 0 else pts[::-1]


def prepare():
    CHECKS.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ORIGINAL))
    data = {"coordinates": "mm; projected x/z", "extent_mm": [-95, 125, -10, 140],
            "frame_profile_v01": cap_outline(bpy.data.objects["Frame_continuous_metal_casting"]),
            "guard_profile": cap_outline(bpy.data.objects["Trigger_guard_void_source"])}
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    data["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    data["frame_side_cap_v02"] = cap_outline(bpy.data.objects["Frame_continuous_metal_casting"])
    (CHECKS / "projection_guides.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("WEAR_GUIDES_READY", flush=True)


def activate(obj):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.active_material_index = 0


def add_projection_uvs():
    """Projection coordinates for masks and a separate nondegenerate editing UV.

    Object procedural coordinates drive physical microdetail. These authoring UVs
    are not claimed as a unique low-poly/game atlas. Source topology is untouched.
    """
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        data = obj.data
        vertices = np.empty(len(data.vertices) * 3, dtype=np.float32)
        data.vertices.foreach_get("co", vertices)
        vertices = vertices.reshape(-1, 3)
        indexes = np.empty(len(data.loops), dtype=np.int32)
        data.loops.foreach_get("vertex_index", indexes)
        co = vertices[indexes] * 1000
        guide = np.column_stack(((co[:, 0] + 95) / 220, (co[:, 2] + 10) / 150)).astype(np.float32)
        uv = data.uv_layers.get(GUIDE_UV) or data.uv_layers.new(name=GUIDE_UV)
        uv.data.foreach_set("uv", guide.ravel())
        projected = np.empty((len(data.loops), 2), dtype=np.float32)
        for face in data.polygons:
            a = int(np.argmax(np.abs(face.normal)))
            axes = (1, 2) if a == 0 else (0, 2) if a == 1 else (0, 1)
            points = co[face.loop_start:face.loop_start+face.loop_total]
            projected[face.loop_start:face.loop_start+face.loop_total] = points[:, axes] / 220 + .5
        edit = data.uv_layers.get(UV) or data.uv_layers.new(name=UV)
        edit.data.foreach_set("uv", projected.ravel())
        data.uv_layers.active = edit
        edit.active_render = True
        # Object ownership mask; no shape or material indices are changed.
        is_frame = obj.name == "Frame_continuous_metal_casting" or "void_source" in obj.name or "Lanyard_hole" in obj.name
        color = data.color_attributes.get("Codex_FrameContact") or data.color_attributes.new(
            name="Codex_FrameContact", type="FLOAT_COLOR", domain="CORNER")
        rgba = np.ones((len(data.loops), 4), dtype=np.float32)
        rgba[:, :3] = 1. if is_frame else 0.
        color.data.foreach_set("color", rgba.ravel())
        data.update()


def make_stack(material_name, label, base_color, metal, rough):
    mat = bpy.data.materials[material_name]
    obj = next(o for o in bpy.data.objects if o.type == "MESH" and mat in list(o.data.materials)
               and not any(c.name == "90_Construction_cutters" for c in o.users_collection))
    activate(obj)
    p = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*base_color, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    bpy.ops.wm.y_quick_ypaint_node_setup(
        tree_name=label, color=True, metallic=True, roughness=True, normal=True, ao=False,
        switch_to_material_view=False, target_bsdf_name=p.name)
    node = next(n for n in mat.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
                and n.node_tree.yp.is_ypaint_node)
    tree = node.node_tree
    root_normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    root_normal.enable_smooth_bump = False
    root_normal.main_uv = UV
    node.label = label
    mat["authoring"] = "Native UCUPaint 2.4.9; Codex; wear reference supplied by owner"
    mat["finish"] = label
    return tree, obj


def layer(tree, name, color=None, metal=None, rough=None, height=None, source_type="COLOR",
          scale=None, amount=1., normal_distance=0.000025):
    # The native API names a new layer before its group exists. Its name callback
    # expects the group; suppress that callback only during native construction.
    tree.yp.halt_update = True
    result = U.Layer.add_new_layer(tree, name, source_type, -1, "MIX", "OVERLAY", "BUMP_MAP",
                                  "Object", UV, use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    values = {"Color": color, "Metallic": metal, "Roughness": rough, "Normal": height}
    for root, ch in zip(tree.yp.channels, result.channels):
        value = values[root.name]
        ch.enable = value is not None
        if not ch.enable:
            continue
        # 'source' means procedural height/color rather than a constant override.
        if value != "source":
            ch.override = True
            ch.override_type = "DEFAULT"
            H.sync_property(U, ch, "override_color" if root.type == "RGB" else "override_value", value)
        if root.type == "NORMAL":
            H.sync_property(U, ch, "bump_distance", normal_distance)
            H.sync_property(U, ch, "bump_midlevel", .5)
    if source_type == "NOISE":
        src = U.common.get_layer_source(result)
        src.inputs["Scale"].default_value = scale
        src.inputs["Detail"].default_value = 2.1
        src.inputs["Roughness"].default_value = .64
    H.sync_property(U, result, "intensity_value", amount)
    return result


def mask_ramp(mask, lo, hi, invert=False):
    module = importlib.import_module(U.__name__ + ".MaskModifier")
    module.add_new_mask_modifier(mask, "RAMP")
    modifier = mask.modifiers[-1]
    node = U.common.get_mask_tree(mask).nodes[modifier.ramp]
    node.color_ramp.elements[0].position = lo
    node.color_ramp.elements[1].position = hi
    node.color_ramp.elements[0].color = (1, 1, 1, 1) if invert else (0, 0, 0, 1)
    node.color_ramp.elements[1].color = (0, 0, 0, 1) if invert else (1, 1, 1, 1)
    return node


def noise_mask(target, name, scale, lo=None, hi=None, offset=(0, 0, 0)):
    result = U.Mask.add_new_mask(target, name, "NOISE", "Object", UV)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = 2.4
    src.inputs["Roughness"].default_value = .68
    result.translation = offset
    if lo is not None:
        H.local_noise_ramp(U, result, lo, hi)
    return result


def edge_mask(target, radius, lo=.015, hi=.09):
    result = U.Mask.add_new_mask(target, "Actual edges — local curvature", "EDGE_DETECT", "Object", UV,
                                 edge_detect_radius=radius, hemi_use_prev_normal=False)
    mask_ramp(result, lo, hi)
    return result


def image_mask(target, filename, label, guide=False):
    image = bpy.data.images.load(str(TEXTURES / filename), check_existing=True)
    image.colorspace_settings.name = "Non-Color"
    result = U.Mask.add_new_mask(target, label, "IMAGE", "UV" if guide else "Object",
                                 GUIDE_UV if guide else UV, image=image)
    src = U.common.get_mask_tree(result).nodes[result.source]
    if not guide:
        src.projection = "BOX"
        src.projection_blend = .18
        result.scale = (5., 5., 5.)  # 200 mm square original atlas, physical units.
    return result


def dirt(tree, color, amount=.28):
    result = layer(tree, "70 • Protected recess dirt", color, 0., .84, amount=amount)
    ao = U.Mask.add_new_mask(result, "Protected pocket proximity", "AO", "Object", UV,
                            ao_distance=.003, hemi_use_prev_normal=False)
    module = importlib.import_module(U.__name__ + ".MaskModifier")
    module.add_new_mask_modifier(ao, "INVERT")
    noise_mask(result, "Interrupted deposits", 940, .30, .57, (.012, .031, .003))
    return result


def coat(test=False):
    tree, obj = make_stack("CHECK_Metal_body_unpainted", "Codex • Red enamel over steel • worn",
                            (.58, .012, .015), 0., .59)
    layer(tree, "00 • Bright red matte enamel", (.58, .012, .015), 0., .59)
    layer(tree, "10 • Factory orange peel — 60 microns", height="source", source_type="NOISE",
          scale=2600, normal_distance=.000060)
    l = layer(tree, "12 • Uneven paint roughness", rough=.67, amount=.45)
    noise_mask(l, "Fine coating variation", 1700)
    l = layer(tree, "20 • Dark undercoat at broken edges", (.036, .032, .026), .35, .57, height=0., normal_distance=.000035)
    edge_mask(l, .00065, .025, .075)
    noise_mask(l, "Chipped coating breakup", 950, .47, .54, (.039, .012, .041))
    l = layer(tree, "30 • Exposed steel — small edge chips", (.32, .34, .36), 1., .32,
              height=0., normal_distance=.000055)
    edge_mask(l, .00050, .026, .085)
    noise_mask(l, "Uneven exposed edge", 1000, .40, .46)
    l = layer(tree, "32 • Palm / finger / heel contact wear", (.30, .32, .34), 1., .36,
              height=0., normal_distance=.00005)
    image_mask(l, "frame_contact_guide_v01.png", "Actual rounded hand-contact guide", guide=True)
    U.Mask.add_new_mask(l, "Frame ownership", "VCOL", "Object", UV, vcol_name="Codex_FrameContact")
    noise_mask(l, "Broken contact streaks", 720, .31, .53, (.020, .041, .013))
    l = layer(tree, "40 • Fine scratches through paint", (.28, .30, .32), 1., .42, height=0.,
              normal_distance=.00004, amount=.80)
    imask = image_mask(l, "scratches_through_v01.png", "Rare deep scratches — physical 200 mm atlas")
    noise_mask(l, "Interrupt deep scratches", 600, .23, .47)
    l = layer(tree, "42 • Superficial handling scuffs", (.42, .016, .019), 0., .67, height=0.,
              amount=.45, normal_distance=.000022)
    image_mask(l, "scratches_fine_v01.png", "Hairline scuffs — physical 200 mm atlas")
    l = layer(tree, "44 • Short coating fractures and small face chips", (.16, .165, .17), .85, .49,
              height=0., normal_distance=.000045, amount=.74)
    image_mask(l, "paint_fractures_v01.png", "Sparse short branching paint fractures — 200 mm atlas")
    noise_mask(l, "Broken fracture ends", 720, .23, .49, (.072, .005, .012))
    if not test:
        l = layer(tree, "50 • Hand polish on red finish", rough=.47, amount=.23)
        noise_mask(l, "Partial broad contact", 48, .49, .69)
        dirt(tree, (.034, .023, .014), .30)
    H.reconnect(U, tree)
    return tree


def bare_steel():
    tree, obj = make_stack("CHECK_Exposed_steel", "Codex • Bare worked steel • worn", (.21, .23, .25), 1., .43)
    layer(tree, "00 • Dark worked steel", (.21, .23, .25), 1., .43)
    layer(tree, "10 • Steel microfinish", height="source", source_type="NOISE", scale=3800, normal_distance=.000035)
    l = layer(tree, "12 • Mottled steel roughness", rough=.62, amount=.50)
    noise_mask(l, "Subtle finish variation", 1200)
    l = layer(tree, "18 • Worked steel tonal patina", (.10, .115, .125), 1., .58, amount=.38)
    noise_mask(l, "Irregular shallow tool marks", 920, .38, .61, (.012, .054, .009))
    l = layer(tree, "30 • Polished exposed tool edges", (.36, .38, .40), 1., .27)
    edge_mask(l, .00055, .008, .045)
    noise_mask(l, "Broken polish", 1100, .36, .51)
    l = layer(tree, "40 • Tool and handling hairlines", (.38, .40, .42), 1., .33, height=0.,
              normal_distance=.000035, amount=.72)
    image_mask(l, "scratches_fine_v01.png", "Small steel scuffs")
    dirt(tree, (.018, .013, .010), .24)
    H.reconnect(U, tree)
    return tree


def plastic():
    tree, obj = make_stack("CHECK_Thin_black_plastic", "Codex • Black molded plastic • worn", (.015, .017, .018), 0., .68)
    layer(tree, "00 • Black molded polymer", (.015, .017, .018), 0., .68)
    layer(tree, "10 • Factory polymer grain", height="source", source_type="NOISE", scale=4500, normal_distance=.00010)
    l = layer(tree, "12 • Polymer grain roughness", rough=.80, amount=.30)
    noise_mask(l, "Fine polymer variation", 3800)
    l = layer(tree, "30 • Rubbed polymer rim", (.029, .031, .032), 0., .44, amount=.48)
    edge_mask(l, .00042, .014, .085)
    noise_mask(l, "Uneven rubbing", 1700, .26, .55)
    l = layer(tree, "40 • Shallow plastic scuffs", (.04, .042, .041), 0., .74, height=0.,
              normal_distance=.000018, amount=.43)
    image_mask(l, "scratches_fine_v01.png", "Plastic abrasion hairlines")
    l = layer(tree, "50 • Palm contact polish", rough=.48, amount=.35)
    noise_mask(l, "Broad hand contact", 34, .47, .69)
    dirt(tree, (.025, .018, .011), .18)
    H.reconnect(U, tree)
    return tree


def ammo():
    trees = []
    for name, label, color in [("CHECK_Red_illumination", "Red illumination cartridge", (.55, .012, .016)),
                               ("CHECK_Green_airdrop", "Green airdrop cartridge", (.013, .20, .034))]:
        tree, obj = make_stack(name, "Codex • " + label, color, 0., .65)
        layer(tree, "00 • Colored cartridge sleeve", color, 0., .65)
        layer(tree, "10 • Sleeve microtexture", height="source", source_type="NOISE", scale=5700, normal_distance=.000012)
        l = layer(tree, "30 • Minor storage scuffs", tuple(min(c * 1.17 + .015, 1.) for c in color), 0., .71, amount=.13)
        image_mask(l, "scratches_fine_v01.png", "Small sleeve scuffs")
        H.reconnect(U, tree)
        trees.append(tree)
    tree, obj = make_stack("CHECK_Cartridge_metal_head", "Codex • Cartridge brass", (.42, .29, .105), 1., .39)
    layer(tree, "00 • Drawn brass head", (.42, .29, .105), 1., .39)
    layer(tree, "10 • Brass microfinish", height="source", source_type="NOISE", scale=7000, normal_distance=.000006)
    l = layer(tree, "20 • Slight brass oxidation", (.14, .095, .034), 1., .59, amount=.20)
    noise_mask(l, "Irregular brass patina", 540, .34, .66)
    l = layer(tree, "40 • Fine brass handling marks", (.45, .33, .16), 1., .34, amount=.30)
    image_mask(l, "scratches_fine_v01.png", "Fine brass marks")
    H.reconnect(U, tree)
    return trees + [tree]


def build(test=False):
    native()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    CHECKS.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    add_projection_uvs()
    trees = [coat(test)]
    if not test:
        trees += [bare_steel(), plastic()] + ammo()
    bpy.data.objects["CTRL_Launcher"]["texture_version"] = "worn_v01; geometry v02 approved by owner request 2026-10-11"
    scene = bpy.context.scene
    scene.cycles.preview_samples = 16
    scene.render.filepath = "//../../previews/texturing_v01/01_worn_overview.png"
    readme = bpy.data.texts["00_README_RU"]
    readme.clear()
    readme.write("Ракетница — Codex / UCUPaint worn_v01\n"
        "Геометрия: одобренная v02, форма, модификаторы и драйверы сохранены.\n"
        "CTRL_Launcher: open_degrees 0–48; hammer_cock, trigger_press, latch_release 0–1.\n"
        "Патроны: красный — осветительный; зелёный — вызов airdrop.\n"
        "Текстурирование worn_v01: нативные стеки UCUPaint 2.4.9.\n"
        "В каждом материале отдельные Color/Metallic/Roughness/Normal. Износ меняется включением\n"
        "и интенсивностью слоёв; маски изображения встроены. 200 мм — физический масштаб царапин.\n"
        "Маски созданы для этого ассета, пиксели фотографий не копировались.\n"
        "PaintUV — проекции для редактирования; WearGuideXZ — расположение контактного износа.\n"
        "Это не уникальная UV-развёртка для игрового bake; экспорт в игру не выполнялся.\n"
        "Кривизна кромок проверена в Cycles. Текстуры подготовлены к просмотру владельцем.\n")
    # Preserve closed pose and all construction sources; do not alter the camera's object hierarchy.
    for o in bpy.context.selected_objects:
        o.select_set(False)
    frame = bpy.data.objects["Frame_continuous_metal_casting"]
    frame.select_set(True)
    bpy.context.view_layer.objects.active = frame
    for obj in bpy.data.collections["90_Construction_cutters"].objects:
        obj.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "RENDERED"
                area.spaces.active.overlay.show_overlays = False
    for image in bpy.data.images:
        if image.type == "IMAGE":
            image.filepath = "//../../textures/worn_v01/" + Path(image.filepath).name
    bpy.ops.file.pack_all()
    filename = TEST if test else MASTER
    bpy.ops.wm.save_as_mainfile(filepath=str(filename))
    print("UCUP_WORN_SAVED", filename, "native_stacks", len(trees), flush=True)


def gpu():
    helpers = load_module(HERE / "build_flare_pistol_codex.py", "flare_geom_helpers")
    helpers.set_gpu()
    return helpers


def render_view(helpers, name, camera, target, scale, only=None, open_deg=0, res=(1250,1000), samples=40):
    scene = bpy.context.scene
    ctrl = bpy.data.objects["CTRL_Launcher"]
    ctrl["open_degrees"] = open_deg
    ctrl.update_tag()
    for col in ["01_Launcher_Codex", "02_Cartridge_Red_Illumination", "03_Cartridge_Green_Airdrop"]:
        bpy.data.collections[col].hide_render = only is not None and col not in only
    bpy.context.view_layer.update()
    scene.camera.location = camera
    helpers.aim(scene.camera, target)
    scene.camera.data.ortho_scale = scale
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.cycles.samples = samples
    scene.render.filepath = str(PREVIEWS / (name + ".png"))
    print("TEXTURE_RENDER_BEGIN", name, flush=True)
    bpy.ops.render.render(write_still=True)
    print("TEXTURE_RENDER_DONE", name, flush=True)


def render(test=False):
    native()
    bpy.ops.wm.open_mainfile(filepath=str(TEST if test else MASTER))
    helpers = gpu()
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    pistol = ["01_Launcher_Codex"]
    if test:
        render_view(helpers, "test_paint_and_edges", (.22,-.32,.205), (.035,0,.070), .238,
                    only=pistol, res=(1250,1250), samples=40)
        render_view(helpers, "test_hand_contact", (-.13,-.23,.052), (-.023,0,.051), .127,
                    only=pistol, res=(1250,1250), samples=40)
        return
    for name, cam, target, scale in [
        ("01_worn_overview", (.22,-.32,.205), (.045,0,.067), .315),
        ("02_worn_three_quarter", (.22,-.32,.205), (.026,0,.071), .244),
        ("03_left_profile", (.016,-.5,.065), (.016,0,.065), .228),
        ("04_right_profile", (.016,.5,.065), (.016,0,.065), .228),
        ("05_grip_guard_wear", (-.13,-.23,.052), (-.023,0,.051), .127),
        ("06_muzzle_and_barrel", (.18,-.26,.20), (.059,0,.111), .154),
        ("07_palm_contact", (-.24,-.07,.071), (-.054,0,.05), .118),
        ("08_steel_hammer_latch", (-.12,-.2,.23), (-.007,0,.112), .110),
        ("09_heel_screw_plastic", (-.095,-.1,-.17), (-.053,0,.025), .091),
    ]:
        render_view(helpers, name, cam, target, scale, only=None if name == "01_worn_overview" else pistol)
    render_view(helpers, "10_open_breech", (.22,-.30,.23), (.018,0,.084), .238, only=pistol, open_deg=48)
    render_view(helpers, "11_cartridges", (.22,-.18,.135), (.162,0,.031), .107,
                only=["02_Cartridge_Red_Illumination", "03_Cartridge_Green_Airdrop"])


def inspect():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    report = {"file": str(MASTER), "ucupaint": U.common.get_current_version_str(), "materials": [], "images": []}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nodes = [n for n in mat.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
                 and n.node_tree.yp.is_ypaint_node]
        for node in nodes:
            tree = node.node_tree
            entry = {"material": mat.name, "native_tree": tree.name,
                     "channels": [(c.name,c.type) for c in tree.yp.channels], "layers": []}
            for l in tree.yp.layers:
                value = U.common.get_entity_prop_value(l, "intensity_value")
                assert abs(value-l.intensity_value) < 1e-6, l.name
                le = {"name": l.name,"enabled": l.enable,"actual_intensity":value,
                      "channels":[],"masks":[]}
                for root,ch in zip(tree.yp.channels,l.channels):
                    if ch.enable:
                        e = {"name":root.name,"enabled":True}
                        if ch.override:
                            prop = "override_color" if root.type == "RGB" else "override_value"
                            actual = U.common.get_entity_prop_value(ch,prop)
                            e["actual_override"] = list(actual) if root.type == "RGB" else actual
                            expected = getattr(ch, prop)
                            aa = list(actual)[:3] if root.type == "RGB" else [actual]
                            ee = list(expected) if root.type == "RGB" else [expected]
                            assert len(aa) == len(ee) and all(abs(a-b)<1e-6 for a,b in zip(aa,ee)), (l.name,prop)
                        if root.type == "NORMAL":
                            e["bump_distance"] = U.common.get_entity_prop_value(ch,"bump_distance")
                            assert abs(e["bump_distance"] - ch.bump_distance)<1e-6, l.name
                        le["channels"].append(e)
                for m in l.masks:
                    src = U.common.get_mask_tree(m).nodes.get(m.source)
                    me = {"name":m.name,"type":m.type,"enabled":m.enable,
                          "modifiers":[mod.type for mod in m.modifiers],
                          "projection":src.projection if src and src.type == "TEX_IMAGE" else None}
                    if src and src.type == "TEX_NOISE":
                        me["actual_noise_scale"] = src.inputs["Scale"].default_value
                    if src and src.type == "TEX_IMAGE":
                        assert src.projection == ("BOX" if m.texcoord_type == "Object" else "FLAT"), m.name
                    mapping = U.common.get_mask_tree(m).nodes.get(m.mapping)
                    if mapping and mapping.type == "MAPPING":
                        actual = list(mapping.inputs["Scale"].default_value)
                        assert all(abs(a-b)<1e-6 for a,b in zip(actual,m.scale)), m.name
                        me["actual_mapping_scale"] = actual
                    le["masks"].append(me)
                entry["layers"].append(le)
            report["materials"].append(entry)
    for im in bpy.data.images:
        if im.type not in {"RENDER_RESULT","COMPOSITING"}:
            digest = hashlib.sha256(bytes(im.packed_file.data)).hexdigest() if im.packed_file else None
            external = TEXTURES / Path(im.filepath).name
            assert external.exists() and digest == hashlib.sha256(external.read_bytes()).hexdigest(), im.name
            report["images"].append({"name":im.name,"packed":bool(im.packed_file),"size":list(im.size),
                                      "color_space":im.colorspace_settings.name,"filepath":im.filepath,"sha256":digest})
    assert len(report["materials"]) == 6
    assert all(im["packed"] for im in report["images"])
    (CHECKS / "native_ucupaint_reopen.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("NATIVE_REOPEN_OK",len(report["materials"]),"materials",len(report["images"]),"packed images",flush=True)


def preservation():
    """Additional all-writable modifier RNA and control pose checks, read only."""
    native()
    def value(v):
        if isinstance(v,bpy.types.ID):
            return (v.name, v.library.filepath if v.library else None)
        if isinstance(v,(str,bool,int,float)) or v is None:
            return v
        try:
            return [value(x) for x in v]
        except TypeError:
            return str(v)
    def snapshot(path):
        bpy.ops.wm.open_mainfile(filepath=str(path))
        mods = {}
        for obj in bpy.context.scene.objects:
            for mod in obj.modifiers:
                props = {}
                for p in mod.bl_rna.properties:
                    if p.identifier == "rna_type" or p.is_readonly or p.type == "COLLECTION":
                        continue
                    props[p.identifier] = value(getattr(mod,p.identifier))
                mods[obj.name+"/"+mod.name] = props
        poses = {}
        ctrl=bpy.data.objects["CTRL_Launcher"]
        objects=list(bpy.data.collections["01_Launcher_Codex"].all_objects)
        for angle in [0,24,48]:
            ctrl["open_degrees"]=angle
            ctrl.update_tag()
            bpy.context.view_layer.update()
            dg=bpy.context.evaluated_depsgraph_get()
            poses[angle]={o.name:list(np.asarray(o.evaluated_get(dg).matrix_world).ravel()) for o in objects}
        return mods,poses
    reference_mods,reference_poses=snapshot(SOURCE)
    candidate_mods,candidate_poses=snapshot(MASTER)
    changed=[key for key in reference_mods if reference_mods[key]!=candidate_mods.get(key)]
    assert not changed and reference_mods.keys()==candidate_mods.keys(), changed
    pose_error=float(max(abs(a-b) for angle in reference_poses for name in reference_poses[angle]
                         for a,b in zip(reference_poses[angle][name],candidate_poses[angle][name])))
    assert pose_error<1e-7, pose_error
    report={"pass":True,"modifier_count":len(reference_mods),"changed_modifiers":changed,
            "modifier_properties":"all writable non-collection RNA fields",
            "poses_degrees":[0,24,48],"maximum_world_matrix_error":pose_error,
            "source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "candidate_sha256":hashlib.sha256(MASTER.read_bytes()).hexdigest()}
    (CHECKS/"modifier_and_pose_preservation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("MODIFIERS_AND_POSES_OK",len(reference_mods),"modifiers; maximum error",pose_error,flush=True)


if __name__ == "__main__":
    {"prepare":prepare,"test":lambda:build(True),"test-render":lambda:render(True),
     "build":build,"render":render,"inspect":inspect,"preservation":preservation}[MODE]()
