"""Дом 7 «Проспекта» в Godot: материалы домов серии (.tres) и сцена дома (system Python, без Godot).
  python -X utf8 tools/prospekt_houses/house7_godot.py [materials] [scene]

materials → scenes/levels/prospekt/houses/materials/<слот>.tres — общие для домов серии (имя файла = имя поверхности glTF):
  шейдер фасада src/world/houses/house_facade.gdshader с фото-наборами CC0 проекта, тоном и контрастом как tint_lum в
  tools/prospekt_houses/materials.py (материалы v01), окна — house_window.gdshader, перфорация — house_perf.gdshader.
scene → scenes/levels/prospekt/houses/house7.tscn по assets/models/prospekt_houses/house7/house7.json: три LOD (glTF),
  коллизии-коробки, замки владельца на цепи и на служебной двери, растения клумбы. ПЕРЕЗАПИСЫВАЕТ сцену — после ручных правок
  владельца не запускать (или запускать с выводом в другую папку: HOUSE7_SCENE_OUT=<путь .tscn>).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAT_DIR = "scenes/levels/prospekt/houses/materials"
MODEL = "assets/models/prospekt_houses/house7"
TX = "assets/textures"
HT = "assets/textures/prospekt_houses"


def srgb(r, g, b):
    return "Color(%.4f, %.4f, %.4f, 1)" % (r / 255.0, g / 255.0, b / 255.0)


def lin2srgb(c):
    def f(x):
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return "Color(%.4f, %.4f, %.4f, 1)" % tuple(f(x) for x in c)


PH = {  # фото-наборы: albedo, normal, orm, средняя яркость фото (сырые 0…1, как mean_lin в materials.py)
    "plaster": (TX + "/painted_plaster_wall/albedo.jpg", TX + "/painted_plaster_wall/normal.jpg", TX + "/painted_plaster_wall/arm.jpg", 0.645),
    "conc": (TX + "/concrete_wall_007/albedo.jpg", TX + "/concrete_wall_007/normal.jpg", TX + "/concrete_wall_007/arm.jpg", 0.495),
    "wood": (TX + "/plywood/albedo.jpg", TX + "/plywood/normal.jpg", TX + "/plywood/arm.jpg", 0.3756),
    "roof": (TX + "/tarred_gravel/albedo.jpg", TX + "/tarred_gravel/normal.jpg", TX + "/tarred_gravel/arm.jpg", 0.2324),
    "soil": (TX + "/mud_forest/albedo.jpg", TX + "/mud_forest/normal.jpg", TX + "/mud_forest/arm.jpg", 0.1417),
    "metal_dark": (HT + "/metal_dark_albedo.webp", HT + "/metal_dark_normal.png", HT + "/metal_dark_orm.webp", 0.4267),
    "metal_light": (HT + "/metal_light_albedo.webp", HT + "/metal_light_normal.png", HT + "/metal_light_orm.webp", 0.7772),
}

# слот → (набор, плитка м, тон sRGB, контраст, rough_mul, rough_min, metal_mul, крупная маска (файл, м, сила), грязь: цвет (лин.),
#         сила, светлое, налёт, бетон: стяжки и parallax)
FACADE = {
    "panel_beige": ("plaster", 1.5, (236, 192, 166), 0.55, 0.95, 0.0, 0.0, ("m_plaque", 14.0, 0.03), (0.045, 0.040, 0.034), 1.0, 0.15, 0.25, False),
    "dark_panel": ("metal_dark", 1.0, (52, 54, 58), 0.5, 0.9, 0.5, 0.15, ("m_marble", 9.0, 0.10), (0.12, 0.115, 0.105), 0.9, 0.5, 0.0, False),
    "concrete": ("conc", 2.0, (164, 157, 147), 0.7, 1.0, 0.62, 0.0, ("m_marble", 5.0, 0.12), (0.05, 0.048, 0.044), 0.9, 0.2, 0.55, True),
    "alu_frame": ("metal_light", 0.8, (40, 41, 44), 0.2, 0.6, 0.38, 0.35, ("m_plaque", 9.0, 0.0), (0.10, 0.095, 0.085), 0.6, 0.2, 0.0, False),
    "steel": ("metal_light", 0.8, (120, 122, 124), 0.5, 0.9, 0.5, 0.85, ("m_plaque", 9.0, 0.0), (0.16, 0.15, 0.135), 0.8, 0.3, 0.0, False),
    "chain_steel": ("metal_light", 0.4, (112, 110, 108), 0.5, 1.0, 0.5, 0.6, ("m_plaque", 0.25, 0.15), (0.12, 0.062, 0.034), 0.5, 0.0, 0.0, False),
    "galvanized": ("metal_light", 0.9, (150, 154, 156), 0.6, 1.0, 0.4, 0.9, ("m_plaque", 9.0, 0.05), (0.10, 0.09, 0.08), 0.8, 0.3, 0.0, False),
    "door_steel": ("metal_dark", 0.8, (64, 74, 68), 0.5, 1.0, 0.5, 0.0, ("m_plaque", 9.0, 0.05), (0.08, 0.075, 0.07), 0.9, 0.2, 0.0, False),
    "wood": ("wood", 0.6, (178, 122, 74), 0.9, 1.0, 0.55, 0.0, ("m_marble", 3.0, 0.08), (0.05, 0.04, 0.035), 0.6, 0.1, 0.0, False),
    "roof_membrane": ("roof", 1.2, (70, 68, 66), 0.8, 1.0, 0.7, 0.0, ("m_plaque", 9.0, 0.06), (0.04, 0.038, 0.035), 0.5, 0.3, 0.0, False),
    "soil": ("soil", 0.8, (66, 50, 38), 1.0, 1.0, 0.85, 0.0, ("m_plaque", 3.0, 0.05), (0.04, 0.03, 0.02), 0.0, 0.0, 0.0, False),
}


class Res:
    def __init__(self):
        self.ext = []

    def add(self, typ, path):
        for i, (t, p) in enumerate(self.ext):
            if p == path:
                return 'ExtResource("%d")' % (i + 1)
        self.ext.append((typ, path))
        return 'ExtResource("%d")' % len(self.ext)

    def head(self, kind, extra_steps=0):
        lines = ['[gd_resource type="%s" load_steps=%d format=3]' % (kind, len(self.ext) + 1 + extra_steps), ""]
        for i, (t, p) in enumerate(self.ext):
            lines.append('[ext_resource type="%s" path="res://%s" id="%d"]' % (t, p, i + 1))
        lines.append("")
        return lines


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def facade_mat(name, spec):
    (ps, tile, tint, c, rmul, rmin, mmul, big, dcol, damt, lamt, algae, conc) = spec
    alb, nrm, orm, mean = PH[ps]
    R = Res()
    sh = R.add("Shader", "src/world/houses/house_facade.gdshader")
    p = {"albedo_tex": R.add("Texture2D", alb), "normal_tex": R.add("Texture2D", nrm), "orm_tex": R.add("Texture2D", orm),
         "mask_big": R.add("Texture2D", HT + "/%s.png" % big[0]), "mask_grain": R.add("Texture2D", HT + "/m_grain.png")}
    if conc:
        p["height_tex"] = R.add("Texture2D", HT + "/conc_height.png")
    lines = R.head("ShaderMaterial")
    lines += ["[resource]", 'resource_name = "%s"' % name, "render_priority = 0", "shader = %s" % sh]
    for k, v in p.items():
        lines.append("shader_parameter/%s = %s" % (k, v))
    vals = {"tile_m": tile, "tint": srgb(*tint), "tint_contrast": c, "photo_mean": mean, "rough_mul": rmul, "rough_min": rmin,
            "metal_mul": mmul, "big_scale_m": big[1], "big_amount": big[2], "dirt_col": lin2srgb(dcol), "dirt_amount": damt,
            "light_amount": lamt, "algae_amount": algae, "tie_holes": "true" if conc else "false"}
    for k, v in vals.items():
        lines.append("shader_parameter/%s = %s" % (k, v))
    write("%s/%s.tres" % (MAT_DIR, name), "\n".join(lines) + "\n")


def window_mat(name, room_light, depth):
    R = Res()
    sh = R.add("Shader", "src/world/houses/house_window.gdshader")
    a = R.add("Texture2D", HT + "/curtains.png")
    g = R.add("Texture2D", HT + "/m_grain.png")
    cr = R.add("Texture2D", HT + "/m_crack.png")
    lines = R.head("ShaderMaterial")
    lines += ["[resource]", 'resource_name = "%s"' % name, "render_priority = 0", "shader = %s" % sh,
              "shader_parameter/curtain_atlas = %s" % a, "shader_parameter/mask_grain = %s" % g, "shader_parameter/mask_crack = %s" % cr,
              "shader_parameter/room_light = %s" % room_light, "shader_parameter/room_depth = %s" % depth]
    write("%s/%s.tres" % (MAT_DIR, name), "\n".join(lines) + "\n")


def perf_mat():
    R = Res()
    sh = R.add("Shader", "src/world/houses/house_perf.gdshader")
    t = R.add("Texture2D", HT + "/perf_alpha.png")
    a = R.add("Texture2D", HT + "/metal_dark_albedo.webp")
    lines = R.head("ShaderMaterial")
    lines += ["[resource]", 'resource_name = "perf_metal"', "render_priority = 0", "shader = %s" % sh,
              "shader_parameter/perf_tex = %s" % t, "shader_parameter/albedo_tex = %s" % a,
              "shader_parameter/tint = %s" % srgb(46, 47, 50)]
    write("%s/perf_metal.tres" % MAT_DIR, "\n".join(lines) + "\n")


def std_mat(name, props, tex=None, tex2=None):
    R = Res()
    t = R.add("Texture2D", tex) if tex else None
    t2 = R.add("Texture2D", tex2) if tex2 else None
    lines = R.head("StandardMaterial3D")
    lines += ["[resource]", 'resource_name = "%s"' % name]
    if t:
        lines.append("albedo_texture = %s" % t)
    if t2:
        lines += ["normal_enabled = true", "normal_texture = %s" % t2]
    lines += props
    return lines


def materials():
    for k, v in FACADE.items():
        facade_mat(k, v)
    window_mat("window_glass", 1.0, 3.0)
    window_mat("vestibule_glass", 3.0, 4.0)        # светлая штукатурка вестибюля, но света нет: читается только вблизи
    perf_mat()
    write(MAT_DIR + "/rail_glass.tres", "\n".join(std_mat("rail_glass", [
        "transparency = 1", "cull_mode = 2", "albedo_color = Color(0.55, 0.6, 0.6, 0.28)", "roughness = 0.08", "metallic_specular = 0.6"])) + "\n")
    write(MAT_DIR + "/lamp_dead.tres", "\n".join(std_mat("lamp_dead", ["albedo_color = Color(0.62, 0.6, 0.55, 1)", "roughness = 0.7"])) + "\n")
    write(MAT_DIR + "/notice.tres", "\n".join(std_mat("notice", ["roughness = 0.85"], HT + "/notice.png")) + "\n")
    write(MODEL + "/house7_lod2.tres", "\n".join(std_mat("house7_lod2", ["roughness = 0.9"], MODEL + "/house7_lod2_albedo.png",
                                                          MODEL + "/house7_lod2_normal.png")) + "\n")
    print("materials ok")


def tr(pos, yaw_deg=0.0, scale=1.0):
    import math
    c, s = math.cos(math.radians(yaw_deg)) * scale, math.sin(math.radians(yaw_deg)) * scale
    return "Transform3D(%.5f, 0, %.5f, 0, %.5f, 0, %.5f, 0, %.5f, %.4f, %.4f, %.4f)" % (c, -s, scale, s, c, pos[0], pos[1], pos[2])


def scene(out=None):
    info = json.load(open(os.path.join(ROOT, MODEL, "house7.json"), encoding="utf-8"))
    ext = []

    def add(typ, path):
        ext.append((typ, path))
        return len(ext)

    i_script = add("Script", "src/world/houses/house_model.gd")
    i_l = [add("PackedScene", MODEL + "/house7_lod%d.gltf" % k) for k in range(3)]
    i_g0 = add("Texture2D", MODEL + "/house7_lod0_grime.png")
    i_g1 = add("Texture2D", MODEL + "/house7_lod1_grime.png")
    i_m2 = add("Material", MODEL + "/house7_lod2.tres")
    i_lock = add("PackedScene", "assets/models/props/padlock_01/padlock_01.gltf")
    i_lilac = add("PackedScene", "assets/models/plants/lilac_c_lod0.glb")
    i_hedge = add("PackedScene", "assets/models/plants/hedge_b_lod0.glb")
    subs = []
    nodes = []
    for b in info["collisions"]:
        subs.append(("BoxShape3D_%s" % b["name"], b["size"]))
    L = ['[gd_scene load_steps=%d format=3]' % (len(ext) + len(subs) + 1), ""]
    for k, (t, p) in enumerate(ext):
        L.append('[ext_resource type="%s" path="res://%s" id="%d"]' % (t, p, k + 1))
    L.append("")
    for sid, size in subs:
        L += ['[sub_resource type="BoxShape3D" id="%s"]' % sid, "size = Vector3(%.4f, %.4f, %.4f)" % tuple(size), ""]
    L += ['[node name="House7" type="Node3D"]', 'script = ExtResource("%d")' % i_script,
          'grime_lod0 = ExtResource("%d")' % i_g0, 'grime_lod1 = ExtResource("%d")' % i_g1, 'lod2_material = ExtResource("%d")' % i_m2,
          'metadata/source = "tools/prospekt_houses/house7_game.py + house7_godot.py"', ""]
    for k in range(3):
        L += ['[node name="LOD%d" parent="." instance=ExtResource("%d")]' % (k, i_l[k]), ""]
    L += ['[node name="Collision" type="StaticBody3D" parent="."]', "collision_mask = 0", ""]
    for b in info["collisions"]:
        L += ['[node name="%s" type="CollisionShape3D" parent="Collision"]' % b["name"],
              "transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, %.4f, %.4f, %.4f)" % tuple(b["center"]),
              'shape = SubResource("BoxShape3D_%s")' % b["name"], 'metadata/surface = "concrete"', ""]
    for pl in info["padlocks"]:
        bar = pl["bar"]
        pos = (bar[0], bar[1] - 0.114, bar[2])             # перемычка дужки модели — на 0,114 м выше основания корпуса
        L += ['[node name="%s" parent="." instance=ExtResource("%d")]' % ("PadlockChain" if "chain" in pl["name"] else "PadlockDoor", i_lock),
              "transform = %s" % tr(pos, pl["yaw_deg"]), ""]
    L += ['[node name="Planter" type="Node3D" parent="."]', ""]
    n = 0
    for k, bed in enumerate(info["beds"]):
        top = bed["top"]
        for (dx, kind, yaw, sc) in ((-1.05, "hedge", 0.0, 0.3), (0.0, "lilac", 40.0 + 25 * k, 0.32), (1.05, "hedge", 180.0, 0.27)):
            L += ['[node name="%s_%d" parent="Planter" instance=ExtResource("%d")]' % (kind, n, i_lilac if kind == "lilac" else i_hedge),
                  "transform = %s" % tr((top[0] + dx, top[1], top[2]), yaw, sc), ""]
            n += 1
    out = out or os.environ.get("HOUSE7_SCENE_OUT") or os.path.join(ROOT, "scenes/levels/prospekt/houses/house7.tscn")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("scene ok", out)


if __name__ == "__main__":
    args = sys.argv[1:] or ["materials", "scene"]
    if "materials" in args:
        materials()
    if "scene" in args:
        scene()
