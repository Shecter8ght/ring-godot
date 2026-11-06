"""Общие FPS-руки из принятой игровой сцены ВЕРАС-54, без правки исходников.

Blender --background --factory-startup --python-exit-code 1 --python tools/export_shared_fps_arms.py
Сетка, UV и карты остаются от ВЕРАСа. Оси пальцев и имена рабочего скелета
согласованы с существующими профилями хватов Persona; их анимации не импортируются.
Источник — мастер FPS-рук с исправленными кистями (tools/fps_hands_master.py → FPS-руки/FPS_Arms_v14.blend, владелец
2026-11-06: «руки в порядок привести … исходник рук и трогай»): ладонь короче и уже, пальцы короче — запястье → кончик
~19 см; игра такие руки больше не уменьшает (в veras_arms.json — hands_fix, HandGripPose.hand_scale_for). Прежний
источник — Клипы v13/VERAS54_Reload_Full_v13.blend (риг и сетка те же, до правки кистей).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import struct

import bpy
from mathutils import Matrix, Quaternion, Vector
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fps_hands_fix as HF  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend")
REFERENCE = ROOT / "assets/models/characters/persona_arms.glb"
TEXTURES = ROOT / "assets/models/weapons/veras54"
WORK = ROOT / "_asset_src/shared_fps_arms"
OUT = ROOT / "assets/models/characters"
FINGERS = {"Index": "f_index", "Middle": "f_middle", "Ring": "f_ring", "Pinky": "f_pinky", "Thumb": "thumb"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hand_frame(bones: dict[str, Matrix], hand: str, index: str, middle: str, pinky: str) -> Matrix:
    forward = (bones[middle].translation - bones[hand].translation).normalized()
    across = bones[index].translation - bones[pinky].translation
    across = (across - forward * across.dot(forward)).normalized()
    return Matrix((across, forward, across.cross(forward))).transposed()


def reference_bones() -> dict[str, Matrix]:
    """Точные оси glTF, которые читает Godot; Blender importer переориентирует кости."""
    blob = REFERENCE.read_bytes()
    size = struct.unpack_from("<I", blob, 12)[0]
    document = json.loads(blob[20:20 + size])
    result = {}
    conversion = Matrix.Rotation(math.pi / 2, 4, "X")

    def visit(index: int, parent: Matrix) -> None:
        node = document["nodes"][index]
        if "matrix" in node:
            local = Matrix([node["matrix"][j:j + 4] for j in range(0, 16, 4)]).transposed()
        else:
            xyzw = node.get("rotation", (0, 0, 0, 1))
            local = Matrix.LocRotScale(Vector(node.get("translation", (0, 0, 0))), Quaternion((xyzw[3], *xyzw[:3])), Vector(node.get("scale", (1, 1, 1))))
        world = parent @ local
        result[node.get("name", "").replace(":", "_")] = conversion @ world
        for child in node.get("children", []):
            visit(child, world)

    for index in document["scenes"][document.get("scene", 0)]["nodes"]:
        visit(index, Matrix.Identity(4))
    return result


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "export").mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    original = bpy.data.objects["FPS_ArmsRig"]
    mesh = bpy.data.objects["FPS_Arms"]
    # Сетка в исходной bind-позе: ключи, IK и драйверы принятого автомата не переносятся.
    source_rest = {b.name: original.matrix_world @ b.matrix_local for b in original.data.bones}
    source_lengths = {b.name: b.length for b in original.data.bones}
    source_weights = []
    for vertex in mesh.data.vertices:
        source_weights.append({mesh.vertex_groups[g.group].name: g.weight for g in vertex.groups})
    # Кисти мастера уже исправлены (fps_hands_master.py): здесь — только замер и пометка для игры
    if "hands_fix" not in original:
        raise SystemExit("в источнике нет hands_fix: руки не из мастера с исправленными кистями")
    hands_fix = json.loads(original["hands_fix"])
    heads = {b.name: tuple(original.matrix_world @ b.head_local) for b in original.data.bones}
    world = mesh.matrix_world.copy()
    hands_after = HF.measure(heads, [tuple(world @ v.co) for v in mesh.data.vertices], source_weights)
    print("SHARED_FPS_ARMS кисти, см:", hands_after)
    mesh.animation_data_clear()
    mesh.parent = None
    mesh.matrix_world = Matrix.Identity(4)
    for modifier in list(mesh.modifiers):
        mesh.modifiers.remove(modifier)
    for obj in list(bpy.data.objects):
        if obj != mesh:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Только ориентации костей прежних профилей; геометрия Persona не попадает в результат.
    reference_rest = reference_bones()

    data = bpy.data.armatures.new("Shared_FPS_Arms")
    rig = bpy.data.objects.new("Shared_FPS_ArmsRig", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    root = data.edit_bones.new("FPS_Root")
    root.head, root.tail = (0, 0, 0), (0, 0, 0.1)
    root.use_deform = False
    mapping: dict[str, str] = {}
    offsets = {}
    for side, suffix in (("Left", "L"), ("Right", "R")):
        prefix = "mixamorig_" + side
        old_frame = hand_frame(reference_rest, prefix + "Hand", prefix + "HandIndex1", prefix + "HandMiddle1", prefix + "HandPinky1")
        new_frame = hand_frame(source_rest, "hand." + suffix, "f_index.01." + suffix, "f_middle.01." + suffix, "f_pinky.01." + suffix)
        alignment = new_frame @ old_frame.inverted()
        old_knuckle = old_frame.inverted() @ (reference_rest[prefix + "HandMiddle1"].translation - reference_rest[prefix + "Hand"].translation)
        new_knuckle = new_frame.inverted() @ (source_rest["f_middle.01." + suffix].translation - source_rest["hand." + suffix].translation)
        offset = Vector((0, 0.085, 0.01 if side == "Right" else -0.01)) + new_knuckle - old_knuckle
        offsets[side] = list(offset)
        shoulder = data.edit_bones.new(prefix + "Shoulder")
        shoulder.head = source_rest["upper_arm." + suffix].translation
        shoulder.tail = shoulder.head + Vector((0, 0, 0.05))
        shoulder.parent = root
        shoulder.use_deform = False
        specifications = [("upper_arm." + suffix, "Arm", "Shoulder"), ("forearm." + suffix, "ForeArm", "Arm"), ("hand." + suffix, "Hand", "ForeArm")]
        for finger, source_finger in FINGERS.items():
            for joint in range(1, 4):
                parent = "Hand" if joint == 1 else "Hand" + finger + str(joint - 1)
                specifications.append((f"{source_finger}.{joint:02d}.{suffix}", "Hand" + finger + str(joint), parent))
        for source_name, target_name, parent_name in specifications:
            target = prefix + target_name
            bone = data.edit_bones.new(target)
            basis = source_rest[source_name].to_3x3()
            if target_name.startswith("Hand"):
                basis = alignment @ reference_rest[target].to_3x3()
            matrix = basis.to_4x4()
            matrix.translation = source_rest[source_name].translation
            # Нулевая новая кость не принимает наклон matrix: сперва задаём длину.
            bone.length = source_lengths[source_name]
            bone.matrix = matrix
            bone.parent = data.edit_bones[prefix + parent_name]
            bone.use_deform = True
            mapping[source_name] = target
        for palm in range(1, 5):
            mapping[f"palm.{palm:02d}.{suffix}"] = prefix + "Hand"
    bpy.ops.object.mode_set(mode="OBJECT")
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)
    groups = {name: mesh.vertex_groups.new(name=name) for name in set(mapping.values())}
    for vertex, weights in zip(mesh.data.vertices, source_weights):
        combined = {}
        for name, weight in weights.items():
            target = mapping.get(name)
            if target:
                combined[target] = combined.get(target, 0.0) + weight
        total = sum(combined.values())
        if not total:
            raise RuntimeError(f"Вершина без веса: {vertex.index}")
        for name, weight in combined.items():
            groups[name].add([vertex.index], weight / total, "REPLACE")
    modifier = mesh.modifiers.new("Shared FPS skeleton", "ARMATURE")
    modifier.object = rig
    mesh.parent = rig
    mesh.name = "FPS_Arms"
    # Экспорт использует именно игровые 2K-карты, уже показанные владельцу на ВЕРАСе.
    image_paths = {p.name.lower(): p for p in TEXTURES.glob("arm*.png")}
    for image in bpy.data.images:
        name = Path(image.filepath).name.lower()
        if name in image_paths:
            if image.packed_file:
                image.unpack(method="REMOVE")
            image.filepath = str(image_paths[name])
            image.reload()
    rig["hands_source"] = "VERAS54_FPS_ArmsRig"
    rig["palm_offsets"] = offsets
    rig["hands_fix"] = json.dumps(hands_fix)
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in (mesh, rig))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / "Shared_FPS_Arms.blend"))
    temporary = WORK / "export/veras_arms.gltf"
    bpy.ops.export_scene.gltf(
        filepath=str(temporary), export_format="GLTF_SEPARATE", use_selection=True,
        export_animations=False, export_apply=False, export_extras=True,
        export_def_bones=False, export_yup=True,
    )
    document = json.loads(temporary.read_text(encoding="utf-8"))
    for image in document.get("images", []):
        filename = Path(image["uri"]).name
        matching = next(p for p in TEXTURES.glob("arm*.png") if p.stem.lower() == Path(filename).stem.lower())
        image["uri"] = "../weapons/veras54/" + matching.name
    for buffer in document.get("buffers", []):
        shutil.copy2(temporary.parent / buffer["uri"], OUT / buffer["uri"])
    (OUT / "veras_arms.gltf").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "source": str(SOURCE), "source_sha256": sha(SOURCE),
        "reference_axes": str(REFERENCE.relative_to(ROOT)), "reference_sha256": sha(REFERENCE),
        "vertices": len(mesh.data.vertices), "triangles": sum(len(p.vertices) - 2 for p in mesh.data.polygons),
        "bones": len(data.bones), "palm_offsets": offsets,
        "hands_fix": {"params": hands_fix, "cm": hands_after, "tool": "tools/fps_hands_master.py"},
        "textures": {p.name: sha(p) for p in TEXTURES.glob("arm*.png")},
        "note": "Сетка/UV ВЕРАС-54 из мастера FPS-рук v14 (кисти исправлены — hands_fix, игра их не уменьшает); "
                "отдельный скелет для прежних профилей хвата, без клипов оружия.",
    }
    (OUT / "veras_arms.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SHARED_FPS_ARMS", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
