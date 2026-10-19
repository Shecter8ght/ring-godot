"""Общее для поз и клипов (v02, под v13 — tools/veras54_v13/clips): рукоятки под цевьём на риге, боевой хват, касание,
быстрые превью, гильза задержки, запасной магазин быстрой перезарядки."""
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

GAME = Path("E:/Games/RING-godot")
LOW = GAME / "_asset_src/veras_attachments"
TEX = GAME / "assets/models/attachments"
# Нижняя планка цевья: середина (место рукоятки по умолчанию в игре — z 0.2765 от пистолетной рукоятки).
RAIL = Vector((-0.14, -0.5995, 1.6655))


def _w(src) -> Vector:
    """Точка рукоятки (её оси: X вперёд, Y влево, Z вверх) → мир сцены (оружие смотрит по −Y)."""
    return RAIL + Vector((src[1], -src[0], src[2]))


def _dir(src) -> Vector:
    return Vector((src[1], -src[0], src[2])).normalized()


# cap — центр торца рукоятки, axis — вдоль неё вниз, hand — середина костяшек от торца, center / spacing — середина четырёх пальцев на рукоятке от торца и их шаг,
# pitch / yaw — довороты кисти (град), ahead — костяшки вперёд от оси, thumb_axis — вокруг чего довести большой.
GRIPS = {
    "varn_v1": {"cap": _w((0.0, 0.0, -0.093)), "axis": _dir((0.0, 0.0, -1.0)), "radius": 0.0135, "length": 0.076, "hand": 0.047, "center": 0.042, "spacing": 0.019,
                "pitch": 4.0, "yaw": 0.0, "ahead": -0.004, "thumb_down": 0.012, "thumb_dir": Vector((-0.55, 0.83, 0.0)),
                "release": (0.032, 0.014, 0.0)},
    "varn_v2": {"cap": _w((0.0, 0.055, -0.070)), "axis": _dir((0.0, 0.676, -0.737)), "radius": 0.0135, "length": 0.078, "hand": 0.029, "center": 0.040, "spacing": 0.019,
                "pitch": 4.0, "yaw": 50.0, "ahead": -0.004, "thumb_down": 0.012, "thumb_dir": Vector((-0.4, 0.83, -0.4)),
                # локоть разведён влево, предплечье поднимается к кисти на ~14°, кулак задран относительно предплечья
                # (фото владельца: РК-1 под 45°, и его правки 2026-10-10); пальцы — ровной стопкой
                "pole": Vector((0.8, -0.3, 1.55)), "stack": True, "release": (0.022, 0.014, 0.02)},
}


# Задержка «гильза не вышла»: затвор недозакрыт на эту долю хода, гильза зажата между зеркалом затвора и передней
# кромкой окна выброса, торчит вправо. База гильзы и её ось — в мире сцены (боевая поза; оси VERAS54 → мир:
# x → −y, y → x). v13: крышка сплошная (выреза нет), окно выброса — x 154…226 мм, z 2…14 мм над осью канала; ход рамы
# 100,6 мм — затвор приоткрыт на 30 мм (зеркало на x 210), донце в 3 мм перед зеркалом (край закраины — в чашке затвора),
# гильза выходит в окно вправо и чуть вверх (проверка — clips/jam_check.py).
JAM_OPEN = 0.30
JAM_CASE_BASE = Vector((-0.144, -0.4628, 1.705))
JAM_CASE_DIR = Vector((-0.93, -0.30, 0.25))


def add_jam_case(wr):
    """Кость JamCase (дочерняя WeaponRoot) и гильза на ней; возвращает pose-кость. Уже есть — берёт её."""
    if "JamCase" not in wr.data.bones:
        to_arm = wr.matrix_world.inverted()
        head = to_arm @ JAM_CASE_BASE
        tail = to_arm @ (JAM_CASE_BASE + JAM_CASE_DIR.normalized() * 0.03)
        bpy.context.view_layer.objects.active = wr
        wr.hide_set(False)
        bpy.ops.object.mode_set(mode="EDIT")
        eb = wr.data.edit_bones.new("JamCase")
        eb.head, eb.tail = head, tail
        eb.parent = wr.data.edit_bones["WeaponRoot"]
        eb.use_deform = True
        bpy.ops.object.mode_set(mode="OBJECT")
    if "JamCase • stuck case" not in bpy.data.objects:
        src = bpy.data.objects["Magazine • loaded case 1"]
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        # гильза лежит вдоль своей X (дульце к +X): донце — в начало, ось — по Y (вдоль кости)
        xs = [v.co.x for v in me.vertices]
        cy = sum(v.co.y for v in me.vertices) / len(me.vertices)
        cz = sum(v.co.z for v in me.vertices) / len(me.vertices)
        me.transform(Matrix.Rotation(math.radians(90), 4, "Z") @ Matrix.Translation((-min(xs), -cy, -cz)))
        ob = bpy.data.objects.new("JamCase • stuck case", me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        ob.parent = wr
        ob.parent_type = "BONE"
        ob.parent_bone = "JamCase"
        # объект у кости стоит от её хвоста: вернуть к голове
        ob.matrix_world = wr.matrix_world @ wr.pose.bones["JamCase"].matrix
    return wr.pose.bones["JamCase"]


def add_spare_mag(wr):
    """Второй магазин для быстрой перезарядки: кость SpareMag (копия Magazine_Control — в покое магазин
    стоит в оружии) и копии корпуса, пятки и двух верхних патронов на ней. В быстрой перезарядке он
    играет старый магазин, который выбивают новым; вне её скрыт. Возвращает pose-кость."""
    if "SpareMag" not in wr.data.bones:
        bpy.context.view_layer.objects.active = wr
        wr.hide_set(False)
        bpy.ops.object.mode_set(mode="EDIT")
        src = wr.data.edit_bones["Magazine_Control"]
        eb = wr.data.edit_bones.new("SpareMag")
        eb.head, eb.tail, eb.roll = src.head.copy(), src.tail.copy(), src.roll
        eb.parent = src.parent
        eb.use_deform = True
        bpy.ops.object.mode_set(mode="OBJECT")
    if not any(o.name.startswith("SpareMag •") for o in bpy.data.objects):
        bpy.context.view_layer.update()
        root = bpy.data.objects["Magazine"]

        def under(ob) -> bool:
            q = ob.parent
            while q is not None:
                if q == root:
                    return True
                q = q.parent
            return False

        for ob in [o for o in bpy.data.objects if o.type == "MESH" and under(o)]:
            n = ob.name
            if "ollower" in n:
                continue
            if "loaded" in n and n.rsplit(" ", 1)[-1] not in ("1", "2"):
                continue
            world = ob.matrix_world.copy()
            cp = ob.copy()
            cp.name = "SpareMag • " + ("round " + n.rsplit(" ", 1)[-1] + (" case" if "case" in n else " bullet") if "loaded" in n else n)
            cp.animation_data_clear()
            bpy.context.scene.collection.objects.link(cp)
            cp.parent = wr
            cp.parent_type = "BONE"
            cp.parent_bone = "SpareMag"
            cp.matrix_world = world
            cp.hide_viewport = cp.hide_render = False
    return wr.pose.bones["SpareMag"]


def hide_suppressor() -> None:
    for c in bpy.data.collections:
        if "Suppressor" in c.name:
            c.hide_viewport = True
            c.hide_render = True
    for ob in list(bpy.data.objects):
        if ob.name.startswith("chk_"):
            bpy.data.objects.remove(ob, do_unlink=True)


def add_grip(gid: str):
    """Игровая сетка рукоятки с картами «100» — на планке цевья, дочерняя кости WeaponRoot."""
    old = bpy.data.objects.get("Foregrip")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    with bpy.data.libraries.load(str(LOW / f"{gid}_low.blend"), link=False) as (_, dst):
        dst.objects = ["Body"]
    ob = dst.objects[0]
    ob.name = "Foregrip"
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("Foregrip • " + gid)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    for channel, socket in (("base_color", "Base Color"), ("roughness", "Roughness"), ("metallic", "Metallic"), ("normal", "Normal")):
        path = TEX / gid / f"{gid}_100_{channel}.png"
        if not path.exists():
            continue
        image = bpy.data.images.load(str(path))
        image.colorspace_settings.name = "sRGB" if channel == "base_color" else "Non-Color"
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        if channel == "normal":
            nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
            mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs[socket])
        else:
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs[socket])
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    wr = bpy.data.objects["VERAS54_WeaponRig"]
    world = Matrix.Translation(RAIL) @ Matrix.Rotation(math.radians(-90), 4, "Z")
    ob.parent = wr
    ob.parent_type = "BONE"
    ob.parent_bone = "WeaponRoot"
    ob.matrix_world = world
    return ob


def ready_pose(arms) -> dict:
    """Боевой хват владельца (кадр 1 его действия) — базисы всех костей рук."""
    sc = bpy.context.scene
    ad = arms.animation_data or arms.animation_data_create()
    act = bpy.data.actions["VERAS54_Grip_Manual_v02"]
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    sc.frame_set(1)
    bpy.context.view_layer.update()
    pose = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
    ad.action = None
    return pose


def bvh_of(obs, dg) -> BVHTree:
    verts, polys = [], []
    for o in obs:
        ob = o.evaluated_get(dg)
        me = ob.to_mesh()
        b = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        polys += [[b + i for i in p.vertices] for p in me.polygons]
        ob.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


VIEWS = {  # откуда смотреть на точку focus: смещение камеры
    "fps": None,
    "left": Vector((0.42, -0.05, 0.02)),
    "below": Vector((0.16, -0.14, -0.38)),
    "front": Vector((0.14, -0.42, -0.06)),
    "right": Vector((-0.42, -0.06, 0.04)),
    # крупно у рукоятки затвора / окна выброса: справа-сверху-спереди и справа-снизу
    "close": Vector((-0.17, -0.12, 0.10)),
    "close_low": Vector((-0.18, -0.08, -0.05)),
}


def preview(prefix: Path, focus: Vector, views, frames=None) -> None:
    """Быстрые кадры для собственной проверки (EEVEE): вид стрелка и крупные планы вокруг focus."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    fps_cam = bpy.data.objects["FPS • Camera"]
    cam = bpy.data.objects.get("chk_cam")
    if cam is None:
        cam = bpy.data.objects.new("chk_cam", bpy.data.cameras.new("chk_cam"))
        sc.collection.objects.link(cam)
        cam.data.lens = 28
        cam.data.clip_start = 0.01
    sun = bpy.data.objects.get("chk_sun")
    if sun is None:
        sun = bpy.data.objects.new("chk_sun", bpy.data.lights.new("chk_sun", "SUN"))
        sc.collection.objects.link(sun)
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(120))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for f in (frames or [sc.frame_current]):
        sc.frame_set(f)
        for v in views:
            if VIEWS[v] is None:
                sc.camera = fps_cam
            else:
                cam.location = focus + VIEWS[v]
                z = (cam.location - focus).normalized()
                x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
                m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
                m.translation = cam.location
                cam.matrix_world = m
                sc.camera = cam
            sc.render.filepath = str(prefix) + f"_{v}" + (f"_{f:03d}" if frames else "") + ".png"
            bpy.ops.render.render(write_still=True)
    sc.camera = fps_cam
