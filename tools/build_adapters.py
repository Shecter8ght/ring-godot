"""Переходники для конструктора оружия: модели в Blender по размерам реальных изделий → GLB.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_adapters.py -- [id …]

Исходник — _asset_src/adapters/adapters.blend (пишется тут же), выход —
assets/models/attachments/adapters/<id>.glb. Собственная работа (CC0), источники размеров —
assets/CREDITS.md и _asset_src/adapters/asset-state.md.

Оси Blender: планка вдоль −Y (к дулу), +Z — от оружия, X — как в игре (−X — правая сторона
стрелка). После экспорта Y-up: игра +Z = Blender −Y, игра +Y = Blender +Z. Начало координат —
середина зажима на верхней поверхности планки (как рамка WeaponMods._adapter).
Узлы: "Arm" — поворотная часть (игра крутит её вокруг своей оси Z на крен точки), "Point_rail" —
точка, которую даёт переходник (верх площадки / планки), для проверки совпадения с данными.

Размеры (мм), MIL-STD-1913: паз 5.23, шаг 10.01, глубина 3.0, ширина головки ~21.2.
  mount_offset45_01  — Arisaka/Unity FAST Offset: основание 25.4 × 3 паза, 4.6 над планкой,
                       два упора, поперечный винт; площадка мини-коллиматора на 22 от оси планки.
  mount_riser_01     — Vector Optics SCRA-60: 40 длина, 25.4 до верха планки, сквозное окно.
  mount_rail_ext_01  — Vector Optics Extended Picatinny: консоль вперёд, двойной зажим, 120 длина.
  mount_adjustable_01— Strike Industries Rotatable: стальной зажим, поворотная шайба с рисками
                       каждые 15°, площадка 24 от оси.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src" / "adapters"
OUT = ROOT / "assets" / "models" / "attachments" / "adapters"
MM = 0.001

# шаг и паз Пикатинни
PITCH = 10.01 * MM
SLOT_W = 5.23 * MM
SLOT_D = 3.0 * MM


# ---------------------------------------------------------------- материалы

def material(name: str, color, metallic: float, rough: float):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = rough
    return m


def materials():
    # твёрдое анодирование — матовое, как корпус ВЕРАСа после правки глянца
    return {
        "anod": material("Adapter_Anodized", (0.035, 0.036, 0.038), 0.15, 0.62),
        "steel": material("Adapter_Steel", (0.22, 0.22, 0.23), 1.0, 0.38),
        "black_steel": material("Adapter_Phosphate", (0.06, 0.06, 0.065), 0.7, 0.55),
        "mark": material("Adapter_Engraving", (0.55, 0.55, 0.53), 0.6, 0.45),
    }


# ---------------------------------------------------------------- геометрия

def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name: str, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.01
    e.location = loc
    return link(e, parent)


def mesh_from(name: str, bm, mat, parent=None, bevel: float = 0.4, segments: int = 2):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob, parent)
    me.materials.append(mat)
    if bevel > 0:
        b = ob.modifiers.new("bevel", "BEVEL")
        b.width = bevel * MM
        b.segments = segments
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(40)
        b.harden_normals = True
    return ob


def box(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    return bm


def prism(profile, y0, y1):
    """Профиль в плоскости XZ, выдавленный вдоль Y от y0 до y1."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in profile]
    b = [bm.verts.new((x, y1, z)) for x, z in profile]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cylinder(r, depth, axis: str, center, segments=24):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r, depth=depth)
    rot = {"x": Matrix.Rotation(math.pi / 2, 4, "Y"), "y": Matrix.Rotation(math.pi / 2, 4, "X"), "z": Matrix.Identity(4)}[axis]
    bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return bm


def cut(target, cutter_bm, name="cut"):
    """Разность с замкнутым резцом (EXACT), резец удаляется."""
    # резец — дочерний к детали: сдвинул изделие в исходнике — резец едет вместе с ним
    cutter = mesh_from(name, cutter_bm, target.data.materials[0], target, bevel=0)
    m = target.modifiers.new(name, "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    # булева — раньше фаски: фаска должна снимать уже прорезанные края
    target.modifiers.move(target.modifiers.find(name), 0)
    cutter.hide_render = True
    cutter.hide_viewport = True
    return cutter


def rail_head(y0, y1, z0, parent, mat):
    """Головка Пикатинни на высоте z0 от y0 до y1 (y — к дулу отрицательный), пазы с шагом 10.01."""
    profile = [(-7.8 * MM, z0), (7.8 * MM, z0), (10.6 * MM, z0 + 2.0 * MM), (10.6 * MM, z0 + 2.5 * MM),
               (8.2 * MM, z0 + 4.6 * MM), (-8.2 * MM, z0 + 4.6 * MM), (-10.6 * MM, z0 + 2.5 * MM), (-10.6 * MM, z0 + 2.0 * MM)]
    head = mesh_from("RailHead", prism(profile, y0, y1), mat, parent, bevel=0.25)
    length = abs(y1 - y0)
    n = int((length - 3 * MM) / PITCH)
    start = (min(y0, y1) + max(y0, y1)) / 2 - (n - 1) * PITCH / 2
    for i in range(n):
        yc = start + i * PITCH
        cut(head, box(-12 * MM, 12 * MM, yc - SLOT_W / 2, yc + SLOT_W / 2, z0 + 4.6 * MM - SLOT_D, z0 + 6 * MM), f"slot{i}")
    return head


def clamp(length, parent, mats, bolts=1, z_top=4.6 * MM, steel=False):
    """Зажим Пикатинни: колодка над планкой, неподвижная губа слева, прижимная планка справа с
    поперечными винтами и гайками, упоры отдачи в пазах. length — вдоль планки."""
    body_mat = mats["black_steel"] if steel else mats["anod"]
    y0, y1 = -length / 2, length / 2
    # колодка: на 4.6 над планкой, ширина 24 (охватывает головку 21.2)
    body = mesh_from("ClampBody", box(-12 * MM, 9.0 * MM, y0, y1, 0.0, z_top), body_mat, parent)
    # неподвижная губа (+X, левая сторона стрелка): вниз до середины ласточкина хвоста с 45° скосом
    jaw_l = [(9.0 * MM, z_top), (12.4 * MM, z_top), (12.4 * MM, -5.5 * MM), (10.2 * MM, -5.5 * MM),
             (8.2 * MM, -3.4 * MM), (10.4 * MM, -1.6 * MM), (9.0 * MM, 0.0)]
    mesh_from("JawFixed", prism(jaw_l, y0, y1), body_mat, parent)
    # подвижная прижимная планка (−X): своя деталь
    jaw_r = [(-12.0 * MM, z_top - 0.4 * MM), (-14.8 * MM, z_top - 0.4 * MM), (-14.8 * MM, -5.5 * MM),
             (-12.6 * MM, -5.5 * MM), (-10.6 * MM, -3.4 * MM), (-12.8 * MM, -1.6 * MM), (-12.0 * MM, 0.0)]
    mesh_from("JawPlate", prism(jaw_r, y0 + 0.6 * MM, y1 - 0.6 * MM), body_mat, parent)
    # поперечные винты: шестигранная головка справа, гайка слева
    spacing = length / (bolts + 1)
    for i in range(bolts):
        yc = y0 + spacing * (i + 1)
        mesh_from(f"Bolt{i}", cylinder(1.9 * MM, 29 * MM, "x", (-0.8 * MM, yc, -3.2 * MM), 16), mats["steel"], parent, bevel=0.15)
        head = mesh_from(f"BoltHead{i}", cylinder(4.2 * MM, 3.4 * MM, "x", (-16.5 * MM, yc, -3.2 * MM), 6), mats["steel"], parent, bevel=0.3)
        cut(head, cylinder(1.6 * MM, 2.0 * MM, "x", (-18.0 * MM, yc, -3.2 * MM), 6), f"hex{i}")
        mesh_from(f"Nut{i}", cylinder(3.9 * MM, 2.6 * MM, "x", (13.7 * MM, yc, -3.2 * MM), 6), mats["steel"], parent, bevel=0.3)
        # упор отдачи — поперечный брусок в паз планки
        mesh_from(f"Lug{i}", box(-7.6 * MM, 7.6 * MM, yc - 2.4 * MM, yc + 2.4 * MM, -0.6 * MM, 0.2 * MM), body_mat, parent, bevel=0.2)
    return body


def optic_plate(parent, mats, top: float, width=24.0, length=34.0):
    """Площадка мини-коллиматора (посадка RMR): плита, два штифта-упора, резьбовые отверстия."""
    t = 3.6 * MM
    plate = mesh_from("OpticPlate", box(-width / 2 * MM, width / 2 * MM, -length / 2 * MM, length / 2 * MM, top - t, top), mats["anod"], parent, bevel=0.5)
    for yc in (-10.5 * MM, 10.5 * MM):
        cut(plate, cylinder(1.5 * MM, 8 * MM, "z", (0, yc, top), 16), "thread%d" % int(yc * 1e4))
    for yc in (-5.0 * MM, 5.0 * MM):
        mesh_from("RecoilBoss", cylinder(1.4 * MM, 1.6 * MM, "z", (0, yc, top + 0.8 * MM), 16), mats["anod"], parent, bevel=0.2)
    return plate


# ---------------------------------------------------------------- изделия

def offset45(mats):
    root = empty("mount_offset45_01")
    clamp(25.4 * MM, root, mats, bolts=1)
    arm = empty("Arm", (0, 0, 0), root)
    top = 22.0 * MM
    # стойка: трапеция в сечении, облегчающее окно
    stem = [(-7.0 * MM, 4.0 * MM), (7.0 * MM, 4.0 * MM), (5.5 * MM, top - 3.6 * MM), (-5.5 * MM, top - 3.6 * MM)]
    st = mesh_from("Stem", prism(stem, -10 * MM, 10 * MM), mats["anod"], arm, bevel=0.6)
    cut(st, box(-3.0 * MM, 3.0 * MM, -12 * MM, 12 * MM, 8.5 * MM, top - 7.5 * MM), "window")
    optic_plate(arm, mats, top)
    empty("Point_rail", (0, 0, top), arm)
    return root


def riser(mats):
    root = empty("mount_riser_01")
    length = 40.0 * MM
    top = 25.4 * MM
    clamp(length, root, mats, bolts=2)
    # корпус-«мост» со сквозным окном (see-through) и выборками по бокам
    body = mesh_from("RiserBody", box(-11.0 * MM, 11.0 * MM, -length / 2, length / 2, 4.0 * MM, top - 4.6 * MM), mats["anod"], root, bevel=0.6)
    cut(body, box(-14 * MM, 14 * MM, -length / 2 + 6 * MM, length / 2 - 6 * MM, 7.5 * MM, top - 9.5 * MM), "tunnel")
    for sx in (-1, 1):
        cut(body, box(sx * 11.6 * MM - 1.2 * MM, sx * 11.6 * MM + 1.2 * MM, -length / 2 + 3 * MM, length / 2 - 3 * MM, top - 8.5 * MM, top - 6.0 * MM), "groove%d" % sx)
    rail_head(-length / 2, length / 2, top - 4.6 * MM, root, mats["anod"])
    empty("Point_rail", (0, 0, top), root)
    return root


def rail_ext(mats):
    root = empty("mount_rail_ext_01")
    top = 12.0 * MM
    # зажим 40 мм, консоль вперёд: планка от +20 мм (к стрелку) до −100 мм (к дулу)
    clamp(40 * MM, root, mats, bolts=2, z_top=4.6 * MM)
    body = mesh_from("ExtBody", box(-9.0 * MM, 9.0 * MM, -100 * MM, 20 * MM, 4.0 * MM, top - 4.6 * MM), mats["anod"], root, bevel=0.6)
    # облегчающие выборки снизу консоли
    for i in range(3):
        y = -32 * MM - i * 22 * MM
        cut(body, box(-6.5 * MM, 6.5 * MM, y - 8 * MM, y + 8 * MM, 3.0 * MM, 5.6 * MM), "pocket%d" % i)
    rail_head(-100 * MM, 20 * MM, top - 4.6 * MM, root, mats["anod"])
    empty("Point_rail", (0, 0, top), root)
    return root


def adjustable(mats):
    root = empty("mount_adjustable_01")
    clamp(25.0 * MM, root, mats, bolts=1, steel=True)
    # неподвижное основание шайбы и поворотная шайба с рисками
    mesh_from("TurnBase", cylinder(11.0 * MM, 3.0 * MM, "z", (0, 0, 6.1 * MM), 40), mats["black_steel"], root, bevel=0.4)
    arm = empty("Arm", (0, 0, 0), root)
    disc = mesh_from("TurnDisc", cylinder(11.0 * MM, 3.0 * MM, "z", (0, 0, 9.1 * MM), 40), mats["anod"], arm, bevel=0.4)
    for k in range(7):
        a = math.radians(-45 + 15 * k)
        cut(disc, box(-0.35 * MM, 0.35 * MM, 8.6 * MM, 11.5 * MM, 9.9 * MM, 11.0 * MM), "tick%d" % k).rotation_euler = (0, 0, a)
    mesh_from("LockScrew", cylinder(3.2 * MM, 2.0 * MM, "z", (0, 0, 11.4 * MM), 24), mats["steel"], arm, bevel=0.3)
    top = 24.0 * MM
    stem = [(-6.0 * MM, 10.4 * MM), (6.0 * MM, 10.4 * MM), (5.0 * MM, top - 3.6 * MM), (-5.0 * MM, top - 3.6 * MM)]
    mesh_from("Stem", prism(stem, 4 * MM, 14 * MM), mats["anod"], arm, bevel=0.6)
    optic_plate(arm, mats, top)
    empty("Point_rail", (0, 0, top), arm)
    return root


BUILDS = {"mount_offset45_01": offset45, "mount_riser_01": riser, "mount_rail_ext_01": rail_ext, "mount_adjustable_01": adjustable}


def export(root, path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for ob in [root, *root.children_recursive]:
        if not ob.hide_render:
            ob.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_animations=False, export_cameras=False, export_lights=False)


def measure(root) -> list:
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in root.children_recursive:
        if ob.type != "MESH" or ob.hide_render:
            continue
        ev = ob.evaluated_get(deps)
        pts += [ev.matrix_world @ v.co for v in ev.data.vertices]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    tris = 0
    for ob in root.children_recursive:
        if ob.type == "MESH" and not ob.hide_render:
            ev = ob.evaluated_get(deps)
            tris += sum(len(p.vertices) - 2 for p in ev.data.polygons)
    return [round((mx[i] - mn[i]) / MM, 1) for i in range(3)], tris


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ids = [a for a in args if a in BUILDS] or list(BUILDS)
    clear()
    mats = materials()
    SRC.mkdir(parents=True, exist_ok=True)
    x = 0.0
    for aid in BUILDS:
        root = BUILDS[aid](mats)
        bpy.context.view_layer.update()
        size, tris = measure(root)
        print("ADAPTER %s size_mm(x, y, z)=%s tris=%d" % (aid, size, tris))
        if aid in ids:
            export(root, OUT / (aid + ".glb"))
        # в исходнике — рядом, для просмотра
        root.location.x = x
        x += 0.06
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "adapters.blend"))


main()
