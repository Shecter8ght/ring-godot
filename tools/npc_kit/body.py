"""NPC, этап 1: базовое тело (плотный мужчина 1,80 м) в A-позе на игровом скелете.

Тело, глаза, брови и ресницы — ядро MakeHuman/MPFB (CC0). Лицо под балаклавой не рисуем,
но глаза в прорези видны — их оставляем. A-поза (родная поза основы MakeHuman) — под неё
шьётся и садится одежда; скелет game_engine: 53 кости, имена как у манекена UE
(pelvis, spine_01…, upperarm_l…), их понимает перенос анимаций Godot.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/body.py [-- render]
→ _asset_src/npc_kit/body/body_M.blend (+ снимки body_*.png при render)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "body"
HEIGHT = 1.80

# Плотный, но не «качок»: широкие плечи и грудь, немного мягкий живот — как у мародёра на референсе.
MACRO = dict(gender=1.0, age=0.62, muscle=0.64, weight=0.60, proportions=0.62, height=0.58, cupsize=0.5, firmness=0.5)
RACE = {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
TARGETS = {
    "torso/torso-scale-horiz-incr": 0.10,
    "torso/torso-vshape-incr": 0.12,
    "neck/neck-scale-horiz-incr": 0.15,
    "armslegs/r-hand-scale-incr": 0.0,
}


def create(services: dict, scale: float) -> bpy.types.Object:
    hs, ts = services["HumanService"], services["TargetService"]
    macro = ts.get_default_macro_info_dict()
    macro.update(MACRO)
    macro["race"] = dict(RACE)
    human = hs.create_human(scale=scale, macro_detail_dict=macro)
    human.name = "NPC_Body"
    data = Path(services["LocationService"].get_mpfb_data())
    for name, weight in TARGETS.items():
        path = data / "targets" / (name + ".target.gz")
        if weight > 0 and path.exists():
            ts.load_target(human, str(path), weight=weight)
    bpy.context.view_layer.update()
    return human


def height_of(obj: bpy.types.Object) -> float:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    zs = [(ev.matrix_world @ v.co).z for v in mesh.vertices]
    ev.to_mesh_clear()
    return max(zs) - min(zs)


def bake_body(human: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Формы и маска помощников — в обычную сетку; группы вершин (веса скелета) сохраняются."""
    for mod in human.modifiers:
        if mod.type == "ARMATURE":
            mod.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(human.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = human.data
    human.data = baked
    baked.name = "NPC_Body"
    bpy.data.meshes.remove(old)
    human.modifiers.clear()
    arm = human.modifiers.new("Skeleton", "ARMATURE")
    arm.object = rig
    # Помощники и служебные группы MakeHuman игре не нужны: оставляем только веса костей.
    bones = {b.name for b in rig.data.bones}
    for vg in list(human.vertex_groups):
        if vg.name not in bones:
            human.vertex_groups.remove(vg)
    for poly in human.data.polygons:
        poly.use_smooth = True


def rotate_bone_to(rig: bpy.types.Object, name: str, target_dir: Vector) -> None:
    """Повернуть кость (с детьми) так, чтобы она смотрела вдоль target_dir; ось — через её начало."""
    pb = rig.pose.bones[name]
    bpy.context.view_layer.update()
    head = rig.matrix_world @ pb.head
    cur = (rig.matrix_world @ pb.tail - head).normalized()
    rot = cur.rotation_difference(target_dir.normalized()).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(pb.head) @ rot @ Matrix.Translation(-pb.head) @ pb.matrix
    bpy.context.view_layer.update()


def set_rest_pose(rig: bpy.types.Object, meshes: list[bpy.types.Object]) -> None:
    """Предплечья у MakeHuman вынесены вперёд почти на 45°: выпрямляем до сгиба 4°
    (почти прямая рука: перёд и зад рукава режутся одной плоскостью с торсом) и делаем это новой позой покоя."""
    kc.make_active(rig)
    bpy.ops.object.mode_set(mode="POSE")
    for side in ("l", "r"):
        up = rig.pose.bones["upperarm_" + side]
        u = (up.tail - up.head).normalized()
        fwd = Vector((0, -1, 0))
        perp = (fwd - u * u.dot(fwd)).normalized()
        bend = math.radians(4)
        rotate_bone_to(rig, "lowerarm_" + side, u * math.cos(bend) + perp * math.sin(bend))
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in meshes:
        kc.make_active(obj)
        for mod in list(obj.modifiers):
            if mod.type == "ARMATURE":
                bpy.ops.object.modifier_apply(modifier=mod.name)
    kc.make_active(rig)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in meshes:
        mod = obj.modifiers.new("Skeleton", "ARMATURE")
        mod.object = rig
        if len(obj.modifiers) > 1:
            with bpy.context.temp_override(object=obj):
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)


def ring_perimeter(points: list[tuple[float, float]]) -> float:
    """Обхват «рулеткой»: периметр выпуклой оболочки сечения."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return sum(math.dist(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull)))


def section(obj: bpy.types.Object, z: float, keep) -> dict:
    """Сечение тела плоскостью z: точки пересечения рёбер, отобранные keep(x, y)."""
    mw = obj.matrix_world
    pts = []
    for e in obj.data.edges:
        a, b = mw @ obj.data.vertices[e.vertices[0]].co, mw @ obj.data.vertices[e.vertices[1]].co
        if (a.z - z) * (b.z - z) < 0:
            t = (z - a.z) / (b.z - a.z)
            p = a.lerp(b, t)
            if keep(p.x, p.y):
                pts.append((p.x, p.y))
    if not pts:
        return {"z": z, "girth": 0.0}
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"z": round(z, 4), "girth": round(ring_perimeter(pts), 4),
            "x": [round(min(xs), 4), round(max(xs), 4)], "y": [round(min(ys), 4), round(max(ys), 4)],
            "center": [round((min(xs) + max(xs)) / 2, 4), round((min(ys) + max(ys)) / 2, 4)]}


def measure(body: bpy.types.Object, rig: bpy.types.Object) -> dict:
    bones = rig.data.bones
    crotch = bones["thigh_l"].head_local.z - 0.075
    arm_x = bones["upperarm_l"].head_local.x * 0.82
    torso = {}
    for name, z in [("neck", bones["neck_01"].head_local.z + 0.04), ("chest", 1.34), ("underbust", 1.24),
                    ("waist", 1.10), ("belly", 1.04), ("hip", 0.93), ("seat", 0.89)]:
        torso[name] = section(body, z, lambda x, y: abs(x) < (arm_x if z > 1.0 else 0.215))
    legs = {}
    for name, z in [("thigh_top", crotch - 0.02), ("thigh_mid", 0.68), ("knee", 0.52), ("calf", 0.38), ("ankle", 0.10)]:
        legs[name] = section(body, z, lambda x, y: x > 0.0)
    ys = [v.co.z for v in body.data.vertices if abs(v.co.x) < 0.04 and 0.6 < v.co.z < 1.0]
    return {"crotch_z_estimate": round(crotch, 4), "torso": torso, "left_leg": legs}


def main() -> None:
    args = kc.args_after_dashes()
    services = kc.enable_mpfb()
    kc.wipe_scene()
    # Первый проход — узнать рост при масштабе 0.1, второй — сразу нужного роста (скелет садится на готовое тело).
    probe = create(services, 0.1)
    scale = 0.1 * HEIGHT / height_of(probe)
    kc.wipe_scene()
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    human = create(services, scale)

    rig = services["HumanService"].add_builtin_rig(human, "game_engine", import_weights=True)
    rig.name = rig.data.name = "NPC_Skeleton"

    user = Path(services["LocationService"].get_user_data())
    parts = {}
    for rel, kind, name, sub in [
        ("eyes/high-poly/high-poly.mhclo", "Eyes", "NPC_Eyes", 1),
        ("eyebrows/eyebrow001/eyebrow001.mhclo", "Eyebrows", "NPC_Eyebrows", 0),
        ("eyelashes/eyelashes01/eyelashes01.mhclo", "Eyelashes", "NPC_Eyelashes", 0),
    ]:
        before = set(bpy.data.objects)
        res = services["HumanService"].add_mhclo_asset(str(user / rel), human, asset_type=kind,
                                                       subdiv_levels=sub, material_type="MAKESKIN")
        obj = res if isinstance(res, bpy.types.Object) else max(
            (o for o in set(bpy.data.objects) - before if o.type == "MESH"), key=lambda o: len(o.data.vertices))
        obj.name = name
        parts[name] = obj

    bake_body(human, rig)
    set_rest_pose(rig, [human, *parts.values()])
    col_body = kc.collection("01_Body")
    for obj in [human, rig, *parts.values()]:
        kc.move_to(obj, col_body)
    human.data.materials.clear()
    human.data.materials.append(kc.clay("Skin_Clay", (0.62, 0.47, 0.40), 0.55))

    bpy.context.view_layer.update()
    h = height_of(human)
    bones = {b.name: (list(b.head_local), list(b.tail_local)) for b in rig.data.bones}
    report = {
        "height_m": round(h, 4),
        "scale": scale,
        "macro": MACRO,
        "targets": TARGETS,
        "vertices": len(human.data.vertices),
        "faces": len(human.data.polygons),
        "bones": len(bones),
        "bone_positions": bones,
        "measure": measure(human, rig),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "body_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    kc.studio()
    kc.save(OUT / "body_M.blend")
    print("NPC_BODY", json.dumps({k: report[k] for k in ["height_m", "vertices", "faces", "bones"]}))
    if "render" in args:
        cams = kc.view_cameras(HEIGHT)
        hand = rig.data.bones["hand_l"].head_local
        cams["hands"] = kc.camera("Cam_Hands", (hand.x + 0.25, hand.y - 0.55, hand.z + 0.12), tuple(hand), 85)
        for view in ["front", "side", "head", "hands"]:
            kc.render(cams[view], OUT / f"body_{view}.png", (900, 1200), 48)


if __name__ == "__main__":
    main()
