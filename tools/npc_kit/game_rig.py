"""NPC «мародёр» — скелет mixamorig_* с весами и экспорт в Godot.

Решение (память проекта, docs/animations.md): скелет — как у Persona (`assets/models/characters/persona_animated.glb`,
52 кости Mixamo), чтобы клипы, BodyMotion, ИК рук и сокеты оружия перешли без переделки. Клипы Godot — повороты
костей относительно их rest-ориентации, поэтому у нового скелета ориентации костей (направление и roll) берутся
у Persona один в один, а положения суставов — у NPC. Сетки NPC для этого ставятся в rest-позу Persona: исходный
скелет MPFB (`game_engine`, 53 кости) поворачивается по костям так, чтобы рамка каждой кости (ось + второй вектор:
поперёк таза, поперёк плеч, поперёк ладони) совпала с рамкой Persona; поза применяется к сеткам, и они привязываются
к новому скелету теми же весами (имена групп переведены по таблице MAP).

Веса: у игровых сеток тела (кисти, лицо), балаклавы и глаз группы MPFB есть с исходника; куртка, брюки, берцы —
переносом с полного тела `body/body_M.blend` (ближайшая грань), ≤ 4 влияния на вершину, нормировка.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/game_rig.py -- character|helmets|armor_poor|armor_mid|armor_top|belt|daypack|tourist|raid|pouches … [export] [deliver=<папка>]
→ _asset_src/npc_kit/game/npc_rig.blend; export → assets/models/characters/npc_marauder/npc_marauder.gltf (карты рядом)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import game_lp as gl  # noqa: E402
import kit_common as kc  # noqa: E402

PERSONA = kc.ROOT / "assets/models/characters/persona_animated.glb"
DONOR = kc.WORK / "body" / "body_M.blend"
OUT = gl.OUT
RIG_FILE = OUT / "npc_rig.blend"
EXPORT = kc.ROOT / "assets/models/characters/npc_marauder"
PERSONA_PREFIX = "mixamorig:"
PREFIX = "mixamorig_"
# имя узла скелета — как у Persona («Human.rig/Skeleton3D»): дорожки запечённых клипов (persona_clips.res)
# адресуют кости этим путём от корня модели
RIG_NAME = "Human.rig"

# MPFB game_engine → Mixamo (короткие имена, без приставки)
FINGERS = {"index": "Index", "middle": "Middle", "ring": "Ring", "pinky": "Pinky", "thumb": "Thumb"}
MAP = {"pelvis": "Hips", "spine_01": "Spine", "spine_02": "Spine1", "spine_03": "Spine2", "neck_01": "Neck", "head": "Head"}
for _s, _S in (("l", "Left"), ("r", "Right")):
    MAP.update({f"clavicle_{_s}": f"{_S}Shoulder", f"upperarm_{_s}": f"{_S}Arm", f"lowerarm_{_s}": f"{_S}ForeArm",
                f"hand_{_s}": f"{_S}Hand", f"thigh_{_s}": f"{_S}UpLeg", f"calf_{_s}": f"{_S}Leg", f"foot_{_s}": f"{_S}Foot",
                f"ball_{_s}": f"{_S}ToeBase"})
    for _f, _F in FINGERS.items():
        for _i in (1, 2, 3):
            MAP[f"{_f}_0{_i}_{_s}"] = f"{_S}Hand{_F}{_i}"
INV = {v: k for k, v in MAP.items()}


def short(persona_name: str) -> str:
    return persona_name.split(":", 1)[1] if ":" in persona_name else persona_name.replace(PREFIX, "")


# ---------- рамки костей ----------

def frame(axis: Vector, second: Vector) -> Matrix:
    """Ортонормированная рамка: Y — ось кости, X — второй вектор без доли вдоль оси, Z — их произведение."""
    y = axis.normalized()
    x = (second - y * second.dot(y)).normalized()
    z = y.cross(x).normalized()
    return Matrix((x, y, z)).transposed()


def second_vector(name: str, heads: dict[str, Vector]) -> Vector:
    """Второй вектор рамки по положениям суставов: таз и ноги — поперёк таза, шея и голова — поперёк плеч,
    ключица — вверх по позвоночнику, рука и пальцы — поперёк ладони (указательный → мизинец)."""
    if name in ("Hips", "Spine", "Spine1", "Spine2") or name.endswith(("UpLeg", "Leg", "Foot", "ToeBase")):
        return heads["LeftUpLeg"] - heads["RightUpLeg"]
    if name in ("Neck", "Head"):
        return heads["LeftShoulder"] - heads["RightShoulder"]
    side = "Left" if name.startswith("Left") else "Right"
    if name.endswith("Shoulder"):
        return heads["Neck"] - heads["Spine1"]
    return heads[f"{side}HandIndex1"] - heads[f"{side}HandPinky1"]


def ordered(arm: bpy.types.Object) -> list[str]:
    """Имена костей от корня к листьям."""
    out: list[str] = []
    stack = [b for b in arm.data.bones if b.parent is None]
    while stack:
        b = stack.pop(0)
        out.append(b.name)
        stack = list(b.children) + stack
    return out


# ---------- Persona ----------

def load_persona() -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(PERSONA))
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o is not arm:
            bpy.data.objects.remove(o)
    arm.name = "Persona_Rig"
    arm.matrix_world = Matrix.Identity(4)
    kc.move_to(arm, kc.collection("RIG_work"))
    return arm


def persona_data(arm: bpy.types.Object) -> dict[str, dict]:
    """Rest Persona: голова, ось (tail − head), roll, родитель — по коротким именам."""
    kc.make_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    data = {}
    for eb in arm.data.edit_bones:
        data[short(eb.name)] = {"head": eb.head.copy(), "axis": (eb.tail - eb.head), "roll": eb.roll,
                               "parent": short(eb.parent.name) if eb.parent else None}
    bpy.ops.object.mode_set(mode="OBJECT")
    return data


# ---------- веса ----------

def append_donor() -> bpy.types.Object:
    with bpy.data.libraries.load(str(DONOR), link=False) as (src, dst):
        dst.objects = ["NPC_Body"]
    donor = dst.objects[0]
    donor.name = "Donor_Body"
    kc.collection("RIG_work").objects.link(donor)
    donor.parent = None
    donor.matrix_world = Matrix.Identity(4)
    for m in list(donor.modifiers):
        donor.modifiers.remove(m)
    return donor


def transfer_weights(o: bpy.types.Object, donor: bpy.types.Object) -> None:
    for g in donor.vertex_groups:
        if g.name not in o.vertex_groups:
            o.vertex_groups.new(name=g.name)
    m = o.modifiers.new("Weights", "DATA_TRANSFER")
    m.object = donor
    m.use_vert_data = True
    m.data_types_verts = {"VGROUP_WEIGHTS"}
    m.vert_mapping = "POLYINTERP_NEAREST"
    m.layers_vgroup_select_src = "ALL"
    m.layers_vgroup_select_dst = "NAME"
    m.mix_mode = "REPLACE"
    m.mix_factor = 1.0
    gl.apply_mods(o)


def tidy_weights(o: bpy.types.Object, limit: int = 4) -> None:
    kc.make_active(o)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=limit)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    bpy.ops.object.vertex_group_clean(group_select_mode="ALL", limit=0.001)


def empty_vertices(o: bpy.types.Object) -> list[int]:
    return [v.index for v in o.data.vertices if not v.groups or max(g.weight for g in v.groups) < 1e-4]


def fill_empty_weights(o: bpy.types.Object, donor: bpy.types.Object) -> int:
    """Вершинам без веса (валик прорези балаклавы, оболочка берца) — веса с донора по ближайшей грани."""
    empty = empty_vertices(o)
    if not empty:
        return 0
    tmp = o.copy()
    tmp.data = o.data.copy()
    kc.collection("RIG_work").objects.link(tmp)
    for g in list(tmp.vertex_groups):
        tmp.vertex_groups.remove(g)
    transfer_weights(tmp, donor)
    names = {g.index: g.name for g in tmp.vertex_groups}
    for i in empty:
        for g in tmp.data.vertices[i].groups:
            if g.weight > 1e-4:
                grp = o.vertex_groups.get(names[g.group]) or o.vertex_groups.new(name=names[g.group])
                grp.add([i], g.weight, "REPLACE")
    bpy.data.objects.remove(tmp)
    return len(empty)


# подол куртки идёт за тазом, а не за бёдрами: веса ног у куртки — в таз
MERGE_INTO_PELVIS = {"G_Jacket": ("thigh_l", "thigh_r", "calf_l", "calf_r")}


def merge_groups(o: bpy.types.Object, into: str, names: tuple[str, ...]) -> None:
    dst = o.vertex_groups.get(into) or o.vertex_groups.new(name=into)
    for name in names:
        g = o.vertex_groups.get(name)
        if g is None:
            continue
        for v in o.data.vertices:
            for vg in v.groups:
                if vg.group == g.index and vg.weight > 0.0:
                    dst.add([v.index], vg.weight, "ADD")
        o.vertex_groups.remove(g)


def weight_report(o: bpy.types.Object) -> str:
    """Сколько вершин без веса и какие группы главные."""
    empty = len(empty_vertices(o))
    top: dict[str, int] = {}
    for v in o.data.vertices:
        if not v.groups or max(g.weight for g in v.groups) < 1e-4:
            continue
        g = max(v.groups, key=lambda g: g.weight)
        name = o.vertex_groups[g.group].name
        top[name] = top.get(name, 0) + 1
    main = ", ".join(f"{k} {v}" for k, v in sorted(top.items(), key=lambda kv: -kv[1])[:5])
    return f"без веса {empty}; главные: {main}"


# ---------- поза ----------

def pose_like_persona(npc: bpy.types.Object, persona: dict[str, dict]) -> float:
    """Повернуть кости MPFB так, чтобы рамка каждой совпала с рамкой Persona; вернуть наибольшую ошибку оси (°)."""
    P_heads = {n: d["head"] for n, d in persona.items()}
    worst = 0.0
    for mp in ordered(npc):
        if mp not in MAP:
            continue
        name = MAP[mp]
        bpy.context.view_layer.update()
        heads = {MAP[pb.name]: npc.matrix_world @ pb.head for pb in npc.pose.bones if pb.name in MAP}
        pb = npc.pose.bones[mp]
        head = npc.matrix_world @ pb.head
        axis = (npc.matrix_world @ pb.tail) - head
        f_cur = frame(axis, second_vector(name, heads))
        f_tgt = frame(persona[name]["axis"], second_vector(name, P_heads))
        rot = (f_tgt @ f_cur.transposed()).to_4x4()
        world = npc.matrix_world @ pb.matrix
        pb.matrix = npc.matrix_world.inverted() @ (Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ world)
        bpy.context.view_layer.update()
        axis_new = ((npc.matrix_world @ pb.tail) - (npc.matrix_world @ pb.head)).normalized()
        err = math.degrees(axis_new.angle(persona[name]["axis"].normalized()))
        worst = max(worst, err)
    return worst


# ---------- скелет ----------

def ground_offset(meshes: list[bpy.types.Object]) -> Vector:
    """Подошва берцев в исходнике ниже нуля (ботинок построен вниз от стопы): поднять модель, чтобы низ был на полу."""
    boots = [o for o in meshes if o.name.startswith("G_Boot") and "_LOD" not in o.name]
    if not boots:
        return Vector((0.0, 0.0, 0.0))
    low = min((o.matrix_world @ v.co).z for o in boots for v in o.data.vertices)
    return Vector((0.0, 0.0, -low)) if low < 0.0 else Vector((0.0, 0.0, 0.0))


def lift_meshes(meshes: list[bpy.types.Object], offset: Vector) -> None:
    for o in meshes:
        o.data.transform(Matrix.Translation(o.matrix_world.inverted().to_3x3() @ offset))
        o.data.update()


def build_rig(npc: bpy.types.Object, persona: dict[str, dict], offset: Vector) -> bpy.types.Object:
    """mixamorig_*: ориентации Persona, суставы NPC (в позе, поднятые на offset), длины MPFB."""
    bpy.context.view_layer.update()
    heads = {MAP[pb.name]: (npc.matrix_world @ pb.head) + offset for pb in npc.pose.bones if pb.name in MAP}
    lengths = {MAP[pb.name]: ((npc.matrix_world @ pb.tail) - (npc.matrix_world @ pb.head)).length
               for pb in npc.pose.bones if pb.name in MAP}
    arm = bpy.data.armatures.new(RIG_NAME)
    rig = bpy.data.objects.new(RIG_NAME, arm)
    kc.collection("GAME_LOD0").objects.link(rig)
    kc.make_active(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    order = []
    stack = [n for n, d in persona.items() if d["parent"] is None]
    while stack:
        n = stack.pop(0)
        order.append(n)
        stack = [c for c, d in persona.items() if d["parent"] == n] + stack
    for n in order:
        d = persona[n]
        eb = arm.edit_bones.new(PREFIX + n)
        eb.head = heads[n]
        eb.tail = heads[n] + d["axis"].normalized() * max(lengths[n], 0.01)
        eb.roll = d["roll"]
        if d["parent"]:
            eb.parent = arm.edit_bones[PREFIX + d["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def check_rig(rig: bpy.types.Object, persona_rig: bpy.types.Object) -> float:
    """Наибольшее расхождение ориентаций костей нового скелета и Persona (°) — должно быть ~0."""
    worst = 0.0
    for b in rig.data.bones:
        p = persona_rig.data.bones[PERSONA_PREFIX + short(b.name)]
        q1 = b.matrix_local.to_quaternion()
        q2 = p.matrix_local.to_quaternion()
        worst = max(worst, math.degrees(q1.rotation_difference(q2).angle))
    return worst


def rename_groups(o: bpy.types.Object) -> None:
    for g in o.vertex_groups:
        if g.name in MAP:
            g.name = PREFIX + MAP[g.name]
        elif not g.name.startswith(PREFIX):
            o.vertex_groups.remove(g)


def bind(o: bpy.types.Object, rig: bpy.types.Object) -> None:
    for m in list(o.modifiers):
        if m.type == "ARMATURE":
            o.modifiers.remove(m)
    m = o.modifiers.new("Armature", "ARMATURE")
    m.object = rig
    o.parent = rig
    o.matrix_parent_inverse = Matrix.Identity(4)


# ---------- материалы и экспорт ----------

def gltf_occlusion(m: bpy.types.Material) -> None:
    """R канала ORM — в occlusionTexture glTF (группа «glTF Material Output», как у ПМ)."""
    nt = m.node_tree
    if any(n.type == "GROUP" and n.node_tree and n.node_tree.name == "glTF Material Output" for n in nt.nodes):
        return
    sep = next((n for n in nt.nodes if n.type == "SEPARATE_COLOR"), None)
    if sep is None:
        return
    g = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [s.name for s in g.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]:
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = g
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])


def game_meshes() -> list[bpy.types.Object]:
    out = []
    for lvl in range(3):
        col = bpy.data.collections.get(f"GAME_LOD{lvl}")
        if col:
            out += [o for o in col.objects if o.type == "MESH"]
    return out


def export_gltf(path: Path, rig: bpy.types.Object, meshes: list[bpy.types.Object]) -> None:
    for o in meshes:
        if o.data.validate(verbose=False):
            kc.log(f"  {o.name}: сетка поправлена перед экспортом (validate)")
        for m in o.data.materials:
            if m:
                gltf_occlusion(m)
                if m.use_nodes:
                    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    if bsdf and bsdf.inputs["Alpha"].default_value < 0.999:
                        m.surface_render_method = "BLENDED"          # забрало — alphaMode BLEND в glTF
    bpy.ops.object.select_all(action="DESELECT")
    rig.hide_set(False)
    rig.select_set(True)
    for o in meshes:
        o.hide_set(False)
        o.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="", use_selection=True,
                              export_yup=True, export_apply=True, export_extras=True, export_animations=False,
                              export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
                              export_tangents=True, export_materials="EXPORT", export_image_format="AUTO",
                              export_skins=True, export_def_bones=False, export_all_influences=False,
                              export_rest_position_armature=True)
    kc.log(f"EXPORT {path} ({round(path.stat().st_size / 1e6, 2)} MB)")


# ---------- персонаж ----------

def character(do_export: bool, deliver: Path | None) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(gl.GAME))
    npc = bpy.data.objects["NPC_Skeleton"]
    persona_rig = load_persona()
    persona = persona_data(persona_rig)
    donor = append_donor()
    meshes = game_meshes()
    # веса: откуда нет — с полного тела
    for o in meshes:
        if not o.vertex_groups or not any(g.name in MAP for g in o.vertex_groups) or len(empty_vertices(o)) == len(o.data.vertices):
            for g in list(o.vertex_groups):
                o.vertex_groups.remove(g)
            transfer_weights(o, donor)
        filled = fill_empty_weights(o, donor)
        base = o.name.split("_LOD")[0]
        if base in MERGE_INTO_PELVIS:
            merge_groups(o, "pelvis", MERGE_INTO_PELVIS[base])
        tidy_weights(o)
        kc.log(f"  веса {o.name}: {weight_report(o)}" + (f"; добито с донора {filled}" if filled else ""))
        bind(o, npc)
    # поза Persona
    err = pose_like_persona(npc, persona)
    kc.log(f"  поза как у Persona: наибольшая ошибка оси {err:.2f}°")
    for o in meshes:
        gl.apply_mods(o)                         # сетки теперь в rest-позе Persona
        o.parent = None
    offset = ground_offset(meshes)
    lift_meshes(meshes, offset)
    kc.log(f"  модель поднята на {offset.z * 100:.1f} см: низ подошвы на полу")
    # новый скелет
    rig = build_rig(npc, persona, offset)
    kc.log(f"  скелет {RIG_NAME}: {len(rig.data.bones)} костей, расхождение ориентаций с Persona {check_rig(rig, persona_rig):.3f}°")
    hips = rig.data.bones[PREFIX + "Hips"].head_local.z
    kc.log(f"  таз в rest: {hips:.3f} м (Persona 0.938) — множитель высоты таза для клипов {hips / 0.938:.3f}")
    for o in meshes:
        rename_groups(o)
        bind(o, rig)
    for o in (npc, donor, persona_rig):
        o.hide_set(True)
        o.hide_render = True
    kc.save(RIG_FILE)
    kc.log(f"SAVED {RIG_FILE}")
    if do_export:
        export_gltf(EXPORT / "npc_marauder.gltf", rig, meshes)
        rig_json(rig, offset)
    if deliver:
        deliver_file(deliver)


# ---------- снаряжение ----------

EXPORT_GEAR = kc.ROOT / "assets/models/characters/npc_gear"
RIG_JSON = EXPORT / "npc_marauder_rig.json"
# вещь: игровой файл, что жёстко к одной кости (все веса в неё), иначе веса переносом с тела
GEAR = {
    "helmets": ("helmets_game.blend", "head"),
    "armor_poor": ("armor_poor_game.blend", None),
    "armor_mid": ("armor_mid_game.blend", None),
    "armor_top": ("armor_top_game.blend", None),
    "belt": ("belt_game.blend", None),
    "daypack": ("daypack_game.blend", None),
    "tourist": ("tourist_game.blend", None),
    "raid": ("raid_game.blend", None),
}


def rig_json(rig: bpy.types.Object, offset: Vector) -> None:
    import json
    data = {"ground_offset": round(offset.z, 6), "hips_rest": round(rig.data.bones[PREFIX + "Hips"].head_local.z, 6),
            "heads": {b.name: [round(c, 6) for c in b.head_local] for b in rig.data.bones}}
    RIG_JSON.parent.mkdir(parents=True, exist_ok=True)
    RIG_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


# каким костям можно держать вещь: рюкзак — только корпус (стропы у подмышек ловили веса плеч, и мешок уезжал
# за руками при вскидывании оружия); остальное — в корпус
TORSO = ("pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "neck_01")
ALLOWED = {"daypack": TORSO, "tourist": TORSO, "raid": TORSO}


def restrict_groups(o: bpy.types.Object, allowed: tuple[str, ...], fallback: str = "spine_03") -> int:
    """Веса чужих костей — в fallback; вернуть число затронутых вершин."""
    dst = o.vertex_groups.get(fallback) or o.vertex_groups.new(name=fallback)
    bad = [g for g in o.vertex_groups if g.name not in allowed]
    touched = 0
    for v in o.data.vertices:
        extra = sum(vg.weight for vg in v.groups if o.vertex_groups[vg.group] in bad)
        if extra > 0.0:
            dst.add([v.index], extra, "ADD")
            touched += 1
    for g in bad:
        o.vertex_groups.remove(g)
    return touched


def rigid_weights(o: bpy.types.Object, bone: str) -> None:
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    o.vertex_groups.new(name=bone).add(list(range(len(o.data.vertices))), 1.0, "REPLACE")


PLACES_SRC = kc.WORK / "pouches" / "places.json"
PLACES_OUT = EXPORT_GEAR / "places.json"
TIER_OF = {"armor_poor": "poor", "armor_mid": "mid", "armor_top": "top", "belt": "belt"}


def to_godot(v: Vector) -> list[float]:
    """Оси Blender (Z вверх, −Y вперёд) → Godot (Y вверх, +Z вперёд... у модели: −Y Blender = +Z Godot)."""
    return [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]


def dominant_bone(o: bpy.types.Object, point: Vector) -> str:
    """Главная кость ближайшей вершины сетки (группы MPFB)."""
    best, best_d = None, 1e9
    for v in o.data.vertices:
        d = ((o.matrix_world @ v.co) - point).length_squared
        if d < best_d and v.groups:
            best_d, best = d, v
    g = max(best.groups, key=lambda g: g.weight)
    return o.vertex_groups[g.group].name


def places_for(item: str, mesh: bpy.types.Object, npc: bpy.types.Object) -> list[dict]:
    """Места подсумков брони (places.json исходника, А-поза): привязка к главной кости у места — до позы."""
    import json
    tier = TIER_OF[item]
    src = json.loads(PLACES_SRC.read_text(encoding="utf-8"))[tier]
    out = []
    for rec in src["места"]:
        pos = Vector(rec["положение"])
        w, x, y, z = rec["поворот_wxyz"]
        bone = dominant_bone(mesh, pos)
        out.append({"n": rec["номер"], "name": rec["имя"], "kind": rec["вид"], "mirror": rec["зеркально"], "mpfb": bone,
                    "m": Matrix.Translation(pos) @ mathutils_quat(w, x, y, z).to_matrix().to_4x4()})
    return out


def mathutils_quat(w: float, x: float, y: float, z: float):
    from mathutils import Quaternion
    return Quaternion((w, x, y, z))


def places_write(item: str, places: list[dict], deltas: dict[str, Matrix], offset: Vector) -> None:
    """Места после позы Persona и подъёма модели — в оси Godot: положение в пространстве скелета, поворот (x, y, z, w),
    кость mixamorig_*; у места локальные оси: +X — поперёк, −Z — наружу от брони, +Y — вверх."""
    import json
    tier = TIER_OF[item]
    recs = []
    for p in places:
        m = Matrix.Translation(offset) @ deltas[p["mpfb"]] @ p["m"]
        loc, rot, _ = m.decompose()
        recs.append({"n": p["n"], "name": p["name"], "kind": p["kind"], "mirror": p["mirror"], "bone": PREFIX + MAP[p["mpfb"]],
                     "pos": to_godot(loc), "quat": [round(rot.x, 5), round(rot.z, 5), round(-rot.y, 5), round(rot.w, 5)]})
    src = json.loads(PLACES_SRC.read_text(encoding="utf-8"))[tier]
    data = json.loads(PLACES_OUT.read_text(encoding="utf-8")) if PLACES_OUT.exists() else {}
    data[tier] = {"item": item, "places": recs, "pairs_big": src.get("пары_под_большой", [])}
    PLACES_OUT.parent.mkdir(parents=True, exist_ok=True)
    PLACES_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    kc.log(f"  места подсумков «{tier}»: {len(recs)} → {PLACES_OUT.name} (кости: {sorted({r['bone'] for r in recs})})")


def gear(item: str, do_export: bool) -> None:
    """Вещь на том же скелете: веса, поза Persona, скелет как у персонажа (сверка суставов по json), экспорт."""
    import json
    blend, rigid = GEAR[item]
    ref = json.loads(RIG_JSON.read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(OUT / blend))
    npc = bpy.data.objects["NPC_Skeleton"]
    persona_rig = load_persona()
    persona = persona_data(persona_rig)
    donor = append_donor()
    meshes = game_meshes()
    for o in meshes:
        if rigid:
            rigid_weights(o, rigid)
        else:
            for g in list(o.vertex_groups):
                o.vertex_groups.remove(g)
            transfer_weights(o, donor)
            fill_empty_weights(o, donor)
            if item in ALLOWED:
                moved = restrict_groups(o, ALLOWED[item])
                if moved:
                    kc.log(f"    {o.name}: веса чужих костей сняты у {moved} вершин")
            tidy_weights(o)
        kc.log(f"  веса {o.name}: {weight_report(o)}")
        bind(o, npc)
    places = places_for(item, meshes[0], npc) if item in TIER_OF else []
    bpy.context.view_layer.update()
    pre = {pb.name: pb.matrix.copy() for pb in npc.pose.bones}
    err = pose_like_persona(npc, persona)
    kc.log(f"  поза как у Persona: наибольшая ошибка оси {err:.2f}°")
    deltas = {pb.name: pb.matrix @ pre[pb.name].inverted() for pb in npc.pose.bones}
    for o in meshes:
        gl.apply_mods(o)
        o.parent = None
    offset = Vector((0.0, 0.0, float(ref["ground_offset"])))
    lift_meshes(meshes, offset)
    if places:
        places_write(item, places, deltas, offset)
    rig = build_rig(npc, persona, offset)
    drift = max((b.head_local - Vector(ref["heads"][b.name])).length for b in rig.data.bones)
    kc.log(f"  скелет {RIG_NAME}: расхождение с Persona {check_rig(rig, persona_rig):.3f}°, суставы против персонажа — до {drift * 1000:.2f} мм")
    if drift > 0.001:
        raise RuntimeError(f"скелет вещи «{item}» не совпал со скелетом персонажа ({drift * 1000:.1f} мм)")
    for o in meshes:
        rename_groups(o)
        bind(o, rig)
    for o in (npc, donor, persona_rig):
        o.hide_set(True)
        o.hide_render = True
    path = OUT / f"{item}_rig.blend"
    kc.save(path)
    kc.log(f"SAVED {path}")
    if do_export:
        export_gltf(EXPORT_GEAR / item / f"{item}.gltf", rig, meshes)


def pouches(do_export: bool) -> None:
    """Подсумки — без скелета: отдельные сетки с ключами формы, место на броне даёт игра (places.json)."""
    bpy.ops.wm.open_mainfile(filepath=str(OUT / "pouches_game.blend"))
    meshes = game_meshes()
    for o in meshes:
        lo = [min((o.matrix_world @ v.co)[i] for v in o.data.vertices) for i in range(3)]
        hi = [max((o.matrix_world @ v.co)[i] for v in o.data.vertices) for i in range(3)]
        kc.log(f"  {o.name}: {gl.tris(o)} треугольников, ключи формы {[k.name for k in o.data.shape_keys.key_blocks[1:]] if o.data.shape_keys else []}, "
               f"габарит {[round((h - l) * 1000) for h, l in zip(hi, lo)]} мм, начало {[round(l * 1000) for l in lo]}..{[round(h * 1000) for h in hi]}")
    if do_export:
        for o in meshes:
            if o.data.validate(verbose=False):
                kc.log(f"  {o.name}: сетка поправлена перед экспортом (validate)")
            for m in o.data.materials:
                if m:
                    gltf_occlusion(m)
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.hide_set(False)
            o.select_set(True)
        path = EXPORT_GEAR / "pouches" / "pouches.gltf"
        path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="", use_selection=True,
                                  export_yup=True, export_apply=False, export_extras=True, export_animations=False,
                                  export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
                                  export_tangents=True, export_materials="EXPORT", export_image_format="AUTO",
                                  export_morph=True, export_morph_normal=True, export_skins=False)
        kc.log(f"EXPORT {path} ({round(path.stat().st_size / 1e6, 2)} MB)")


def deliver_file(folder: Path) -> None:
    for name in ("NPC_Skeleton", "Donor_Body", "Persona_Rig"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name not in ("GAME_LOD0", "GAME_LOD1", "GAME_LOD2", "99_Studio") and not c.objects and not c.children:
            bpy.data.collections.remove(c)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    readme = ("NPC «мародёр» v03 — игровая версия СО СКЕЛЕТОМ mixamorig_* (как у Persona в игре: 52 кости), на просмотр.\n"
              "Сетки стоят в rest-позе Persona (предплечья чуть согнуты вперёд); веса: тело и балаклава — с исходника,\n"
              "куртка, брюки, берцы — переносом с полного тела. LOD0 / LOD1 / LOD2 — коллекции GAME_LOD*.\n"
              "Скрипт: tools/npc_kit/game_rig.py.\n")
    txt = bpy.data.texts.get("00_ПРОЧТИ") or bpy.data.texts.new("00_ПРОЧТИ")
    txt.clear()
    txt.write(readme)
    folder.mkdir(parents=True, exist_ok=True)
    kc.save(folder / "NPC_Marauder_v03_риг.blend")
    kc.log(f"DELIVERED {folder / 'NPC_Marauder_v03_риг.blend'}")


def main() -> None:
    args = kc.args_after_dashes()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if "character" in args:
        character("export" in args, Path(dest) if dest else None)
    for item in args:
        if item in GEAR:
            gear(item, "export" in args)
    if "pouches" in args:
        pouches("export" in args)


if __name__ == "__main__":
    main()
