"""Купе Ильи: сборка кузова панелями в Blender.

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/build_coupe.py -- \
        <черновик.blend (колёса)> <выход.blend>

Поле формы — fieldcore + field_profiles.npz, панели — layout.py. Черновой объём остаётся
тёмной подложкой (утоплен на 8 мм): видно, где панелей ещё нет.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import fieldcore  # noqa: E402
import layout  # noqa: E402
from surface import Surface  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
BASE, OUT = Path(argv[0]), Path(argv[1])

MATERIALS = {
    "paint": ((0.42, 0.43, 0.45), 0.35, 0.0),
    "lamp_glass": ((0.05, 0.06, 0.07), 0.05, 0.0),
    "trim_black": ((0.02, 0.02, 0.02), 0.5, 0.0),
    "chrome": ((0.8, 0.8, 0.8), 0.1, 1.0),
    "glass": ((0.03, 0.035, 0.04), 0.02, 0.0),
    "lamp_red": ((0.35, 0.02, 0.02), 0.08, 0.0),
    "trim_gloss_black": ((0.015, 0.015, 0.016), 0.12, 0.0),
    "mesh_black": ((0.01, 0.01, 0.01), 0.7, 0.0),
    "carbon": ((0.03, 0.03, 0.032), 0.25, 0.0),
    "chrome_dark": ((0.25, 0.25, 0.26), 0.18, 1.0),
    "rubber": ((0.03, 0.03, 0.03), 0.85, 0.0),
    "mirror": ((0.9, 0.9, 0.9), 0.02, 1.0),
    "paint_inner": ((0.36, 0.37, 0.39), 0.5, 0.0),
    "engine_metal": ((0.12, 0.12, 0.13), 0.45, 0.6),
    "hose": ((0.02, 0.02, 0.02), 0.75, 0.0),
    "plastic_white": ((0.75, 0.74, 0.70), 0.4, 0.0),
    "battery": ((0.05, 0.05, 0.055), 0.6, 0.0),
    "lead": ((0.45, 0.45, 0.47), 0.5, 0.9),
    "cable_red": ((0.45, 0.02, 0.02), 0.5, 0.0),
    "cable_black": ((0.02, 0.02, 0.02), 0.5, 0.0),
    "brick": ((0.45, 0.17, 0.10), 0.9, 0.0),
    "leather": ((0.06, 0.055, 0.05), 0.55, 0.0),
    "interior_soft": ((0.05, 0.05, 0.05), 0.7, 0.0),
    "carpet": ((0.03, 0.03, 0.03), 0.95, 0.0),
    "headliner": ((0.20, 0.20, 0.20), 0.9, 0.0),
    "screen_off": ((0.01, 0.012, 0.015), 0.08, 0.0),
    "screen_on": ((0.35, 0.65, 0.95), 0.2, 0.0),
    "liner": ((0.035, 0.035, 0.035), 0.9, 0.0),
    "lamp_drl": ((0.9, 0.92, 0.95), 0.2, 0.0),
    "lens": ((0.6, 0.62, 0.65), 0.05, 0.0),
    "plate": ((0.92, 0.92, 0.90), 0.4, 0.0),
    "plate_text": ((0.02, 0.02, 0.02), 0.5, 0.0),
    "rim_black": ((0.02, 0.02, 0.022), 0.3, 0.6),
    "brake_steel": ((0.35, 0.35, 0.36), 0.45, 1.0),
    "caliper": ((0.08, 0.08, 0.09), 0.35, 0.2),
}


def material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb, rough, metal = MATERIALS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0))
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = rough
    m.metallic = metal
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if name in ("screen_on", "lamp_drl"):
        b.inputs["Emission Color"].default_value = (*rgb, 1.0)
        b.inputs["Emission Strength"].default_value = 3.0 if name == "screen_on" else 6.0
    return m


bpy.ops.wm.open_mainfile(filepath=str(BASE))
body = bpy.data.objects.get("Body_blockout")
if body is not None:
    ghost = bpy.data.materials.new("blockout_ghost")
    ghost.diffuse_color = (0.12, 0.13, 0.16, 1.0)
    body.data.materials.clear()
    body.data.materials.append(ghost)
    disp = body.modifiers.new("inset", "DISPLACE")
    disp.strength = -0.008
    disp.mid_level = 0.0
    # Кузов собран панелями целиком — черновик только для сверки, в кадр не идёт
    body.hide_render = True
    body.hide_set(True)

t0 = time.time()
surf = Surface(fieldcore.BodyField(fieldcore.load_profiles(HERE / "field_profiles.npz")))
col = bpy.data.collections.new("Body")
bpy.context.scene.collection.children.link(col)
total = 0
layout_S: dict = {}
_orig_build_rear = layout.build_rear


def _keep_S(surf_, S, out):
    layout_S.update(S)
    return _orig_build_rear(surf_, S, out)


layout.build_rear = _keep_S
for name, mat, V, F in layout.build_all(surf):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material(mat))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    total += len(F)
    print(f"  {name}: {len(V)} вершин, {len(F)} граней")
print(f"панелей: {len(col.objects)}, граней {total}, {time.time() - t0:.1f} с")

# Номера: К 417 МР (буквы номера совпадают с латинскими), регион 77
def plate(name: str, center, facing_y: float) -> None:
    import bmesh
    w, h, t = 0.520, 0.112, 0.003
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= t
        v.co.z *= h
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) > 1e-6],
                    offset=0.008, segments=4, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material("plate"))
    ob = bpy.data.objects.new(name, me)
    ob.location = center
    col.objects.link(ob)
    for txt, size, dx in (("K 417 MP", 0.075, -0.035), ("77", 0.050, 0.205)):
        cu = bpy.data.curves.new(name + "_t", "FONT")
        cu.body = txt
        cu.size = size
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.extrude = 0.0006
        to = bpy.data.objects.new(name + "_" + txt.replace(" ", ""), cu)
        to.rotation_euler = (1.5708, 0, 0 if facing_y < 0 else 3.14159)
        to.location = (center[0] + (dx if facing_y < 0 else -dx), center[1] + facing_y * (t / 2 + 0.0004), center[2])
        col.objects.link(to)
        to.data.materials.append(material("plate_text"))


plate("Plate_Front", (0.0, -2.338, 0.372), -1.0)
plate("Plate_Rear", (0.0, 2.503, 0.555), 1.0)

# Колёса: одна сетка на четыре места (связанные копии), старые черновые шины и диски — долой
import wheel  # noqa: E402

for ob in list(bpy.data.objects):
    if ob.parent is not None and ob.parent.name.startswith("Wheel_") and ob.type == "MESH":
        bpy.data.objects.remove(ob)
meshes = []
for name, mat, V, F in wheel.wheel_parts():
    me = bpy.data.meshes.new(f"Wheel_{name}")
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material(mat))
    meshes.append((name, me))
wcol = bpy.data.collections.get("Wheels")
for root in [o for o in bpy.data.objects if o.name.startswith("Wheel_") and o.type == "EMPTY"]:
    for name, me in meshes:
        ob = bpy.data.objects.new(f"{name}_{root.name[6:]}", me)
        ob.parent = root
        (wcol or col).objects.link(ob)
print("колёса:", sum(len(me.polygons) for _, me in meshes), "граней на колесо")
# --- Подкапотное, капот на петле, состояния для заказа ------------------------------------------
import numpy as np  # noqa: E402

import engine_bay as eb  # noqa: E402
import parts as pt_  # noqa: E402
from seams import VIEWS  # noqa: E402


def add(name: str, mat: str, V, F, collection) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material(mat))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def new_col(name: str, parent=None) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


bay = new_col("EngineBay")
add("Bay_Aprons", "paint_inner", *eb.aprons(), bay)
add("Bay_Radiator_Frame", "paint_inner", *eb.radiator_frame(), bay)
add("Engine", "engine_metal", *eb.engine(), bay)
add("Engine_Badge", "chrome", *eb.badge_on_engine(), bay)
hoses, clamps = eb.hanging_hoses()
add("Radiator_Hoses_Cut", "hose", *hoses, bay)
add("Radiator_Hose_Clamps", "chrome_dark", *clamps, bay)
add("Coolant_Tank", "plastic_white", *eb.coolant_tank(), bay)
add("Fuse_Box", "trim_black", *eb.fuse_box(), bay)
add("Brake_Reservoir", "plastic_white", *eb.brake_reservoir(), bay)
add("Strut_Brace", "trim_gloss_black", *eb.strut_brace(), bay)
add("Battery_Tray", "trim_black", *eb.battery_tray(), bay)

st_bat_on = new_col("State_Battery_Installed")
st_bat_off = new_col("State_Battery_Missing")
body_, posts_, bar_ = eb.battery()
add("Battery", "battery", *body_, st_bat_on)
add("Battery_Posts", "lead", *posts_, st_bat_on)
add("Battery_Clamp", "trim_black", *bar_, st_bat_on)
pos, neg, cl = eb.battery_cables(True)
add("Cable_Pos_Installed", "cable_red", *pos, st_bat_on)
add("Cable_Neg_Installed", "cable_black", *neg, st_bat_on)
add("Cable_Clamps_Installed", "lead", *cl, st_bat_on)
pos, neg, cl = eb.battery_cables(False)
add("Cable_Pos_Loose", "cable_red", *pos, st_bat_off)
add("Cable_Neg_Loose", "cable_black", *neg, st_bat_off)
add("Cable_Clamps_Loose", "lead", *cl, st_bat_off)
st_bat_off.hide_render = True
for ob in st_bat_off.objects:
    ob.hide_set(True)

# Капот: внутренняя панель и петля у короба (повернуть Hood_Hinge по X: −0.87 рад — открыт)
hood = bpy.data.objects["Hood"]
hood_loop = layout_S["_hood_loop"]
import domain  # noqa: E402

# Отступ контура по поверхности (с распутыванием углов), затем задник на 2,6 см ниже обшивки
inner_loop = domain.loop_on_surface(surf, VIEWS["top"], hood_loop, 0.02, 0.035, False)
hi = add("Hood_Inner", "paint_inner", *pt_.backing(surf, VIEWS["top"], inner_loop, 0.026), col)
hinge = bpy.data.objects.new("Hood_Hinge", None)
hinge.empty_display_type = "ARROWS"
hinge.empty_display_size = 0.15
hinge.location = (0.0, -0.925, 0.975)
col.objects.link(hinge)
bpy.context.view_layer.update()
for ob in (hood, hi):
    ob.parent = hinge
    ob.matrix_parent_inverse = hinge.matrix_world.inverted()

# Колесо переднее левое: снято — машина на кирпичах. Шина и диск уходят, тормоз остаётся на машине.
st_w_on = new_col("State_Wheel_FL_On")
st_w_off = new_col("State_Wheel_FL_Off")
for ob in list(bpy.data.objects):
    if ob.parent is not None and ob.parent.name == "Wheel_FL" and not ob.name.startswith(("Brake_Disc", "Caliper")):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        st_w_on.objects.link(ob)
add("Bricks_FL", "brick", *eb.bricks_under_hub(0.66, -1.40), st_w_off)
add("Knuckle_FL", "engine_metal", *eb.knuckle(1.0, -1.4355), st_w_off)
st_w_off.hide_render = True
for ob in st_w_off.objects:
    ob.hide_set(True)

# --- Салон ----------------------------------------------------------------------------------------
import interior  # noqa: E402

cab = new_col("Interior")
ip = interior.interior_parts()
faces = ip.pop("_screen_faces")
for nm, (mat, mesh) in ip.items():
    add(nm, mat, *mesh, cab)
roof_me = bpy.data.objects["Roof"].data
rv = np.array([v.co[:] for v in roof_me.vertices])
rf = [tuple(p.vertices) for p in roof_me.polygons]
add("Headliner", "headliner", *interior.headliner(surf, (rv, rf)), cab)
add("Screens_Lit", "screen_on", *faces, st_bat_on)
add("Screens_Dark", "screen_off", *faces, st_bat_off)
for ob in st_bat_off.objects:
    ob.hide_set(True)

# Черновой объём остаётся в своём файле (Coupe_Ilya_blockout_*.blend); в модели его нет
if body is not None:
    bpy.data.objects.remove(body)
# Знаки и подобные мелкие детали собраны из кусков — сварить совпадающие вершины
import bmesh  # noqa: E402

for ob in bpy.data.objects:
    if ob.type == "MESH" and ("Badge" in ob.name or ob.name.startswith(("Mirror_Glass", "Exhaust"))):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(ob.data)
        bm.free()

OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("сохранено:", OUT)
