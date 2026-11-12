"""АСТЕН-919 (wpn_hg_02): риг для клипов рук — мастер FPS-рук v14 (кисти исправлены) и игровая сетка пистолета на костях
своего рига. Хват здесь не ставится (tools/asten919/clips/grip.py), руки — в позе мастера.

  FPS_ArmsRig (мастер): Weapon_CTRL — ручка оружия (наклоны в клипах), ik_hand.R / ik_hand.L — дочерние ей цели кистей.
  ASTEN919 (пустышка на кости Weapon_CTRL): оси исходника пистолета (м; +X — к дулу, +Y — влево, +Z — вверх; начало —
    зеркало затвора на оси канала).
  ASTEN919_WeaponRig: кости у точек вращения из parts.json, все смотрят к дулу (локальные оси кости: Y — к дулу, Z — вверх,
    X — вправо): WeaponRoot, Slide, Barrel, Trigger, SlideStop, SlideLock, MagCatch, Magazine_Control → Magazine →
    MagazineFollower, SpareMag_Control → SpareMag (старый магазин быстрой перезарядки), Case (стреляная гильза),
    JamCase (гильза задержки). Сетки игры — на своих костях; патроны Round_01…17 (1 — верхний) — на кости Magazine.
  Положение пистолета перед камерой — как у ПМ в хвате владельца (начало игры у рукояти — в точке WeaponFrame ПМ).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/asten919/clips/rig.py [-- <выход.blend>]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
MASTER = Path("E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend")
LP = ROOT / "_asset_src/asten919/game/lp/ASTEN919_Game_LP.blend"
REC = json.loads((ROOT / "_asset_src/asten919/game/lp/parts.json").read_text(encoding="utf-8"))
TEX = ROOT / "assets/models/weapons/asten919"
OUT = ROOT / "_asset_src/asten919/anim/ASTEN919_Rig_v01.blend"
READY_ACTION = "VERAS54_Grip_Manual_v02"

ORIGIN = Vector(REC["marks"]["Origin"])            # начало игры у рукояти (исходник, м)
ORIGIN_WORLD = Vector((-0.14, -0.321, 1.646))      # где оно стоит перед камерой (точка WeaponFrame ПМ в хвате владельца)
GRIP_A = math.radians(22.0)
MAG_UP = Vector((math.sin(GRIP_A), 0.0, math.cos(GRIP_A)))
PIV = {k: Vector(v) for k, v in REC["pivots"].items()}
FOLLOWER = Vector((-0.05304, 0.0, -0.10353))       # подаватель при 17 патронах (manifest: Magazine_Follower)
CASE_LEN = 0.01915
# гильза задержки: стоит в окне выброса «свечкой» — дно зажато затвором, дульце вправо-вверх
JAM_CASE_POS = Vector((0.014, -0.006, 0.004))
JAM_CASE_DIR = Vector((0.25, -0.62, 0.74))
BONES = {
    # имя: (голова, родитель, сетки)
    "WeaponRoot": (ORIGIN, None, ["Frame_Mesh", "FrameParts_Mesh", "RecoilSpring_Mesh"]),
    "Slide": (PIV["Slide"], "WeaponRoot", ["Slide_Mesh", "SlideParts_Mesh", "MosCover_Mesh"]),
    "Barrel": (PIV["Barrel"], "WeaponRoot", ["Barrel_Mesh", "MuzzleDevice_Mesh"]),
    "Trigger": (PIV["Trigger"], "WeaponRoot", ["Trigger_Mesh"]),
    "SlideStop": (PIV["SlideStop"], "WeaponRoot", ["SlideStop_Mesh"]),
    "SlideLock": (PIV["SlideLock"], "WeaponRoot", ["SlideLock_Mesh"]),
    "MagCatch": (PIV["MagCatch"], "WeaponRoot", ["MagCatch_Mesh"]),
    "Magazine_Control": (PIV["Magazine"], "WeaponRoot", []),
    "Magazine": (PIV["Magazine"], "Magazine_Control", ["Magazine_Mesh"]),
    "MagazineFollower": (FOLLOWER, "Magazine", ["Follower_Mesh"]),
    "SpareMag_Control": (PIV["Magazine"], "WeaponRoot", []),
    "SpareMag": (PIV["Magazine"], "SpareMag_Control", ["Part_SpareMag", "Part_SpareMagFollower"]),
    "Case": (Vector((0.0, 0.0, 0.0)), "WeaponRoot", ["Part_Case"]),
    "JamCase": (JAM_CASE_POS, "WeaponRoot", ["Part_JamCase"]),
}


def log(*a):
    print("ASTEN_RIG", *a, flush=True)


def material(atlas):
    m = bpy.data.materials.new(f"АСТЕН-919 • {atlas}")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "GameUV"

    def tex(kind, cs):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(TEX / f"asten919_{atlas}_100_{kind}.png"), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t
    nt.links.new(tex("albedo", "sRGB").outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex("orm", "Non-Color").outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "GameUV"
    nt.links.new(tex("normal", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def case_from_round(rd, coll):
    """Гильза из сетки патрона: всё, что дальше дульца (19,15 мм от дна), срезано, срез закрыт. Начало — дно гильзы,
    ось — локальная +X (как у патрона)."""
    me = rd.data.copy()
    me.name = "Case"
    bm = bmesh.new()
    bm.from_mesh(me)
    xs = sorted({round(v.co.x, 5) for v in bm.verts})
    cut = min(xs, key=lambda x: abs(x - CASE_LEN))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x > cut + 1e-5], context="VERTS")
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=64)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    log("гильза: кольца патрона по X, мм", [round(x * 1000, 2) for x in xs], "срез", round(cut * 1000, 2))
    out = {}
    for name in ("Part_Case", "Part_JamCase"):
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)
        o["atlas"] = "Magazine"
        out[name] = o
    return out


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else OUT
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    S = bpy.context.scene
    S.render.fps = 30
    arms = bpy.data.objects["FPS_ArmsRig"]
    for pb in arms.pose.bones:
        pb.rotation_mode = "XYZ"
    # поза мастера (хват владельца на ВЕРАСе) — как стартовая для плеч и локтей
    ad = arms.animation_data or arms.animation_data_create()
    act = bpy.data.actions[READY_ACTION]
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    S.frame_set(1)
    bpy.context.view_layer.update()
    pose = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
    ad.action = None
    for pb in arms.pose.bones:
        pb.matrix_basis = pose[pb.name]
    bpy.context.view_layer.update()

    # ---- пистолет: сетки игры
    with bpy.data.libraries.load(str(LP)) as (src, dst):
        dst.objects = list(src.objects)
    coll = bpy.data.collections.new("АСТЕН-919 — игровая сетка")
    S.collection.children.link(coll)
    mats, meshes = {}, {}
    for o in dst.objects:
        if o is None or o.type != "MESH" or "atlas" not in o:
            continue
        coll.objects.link(o)
        meshes[o.name] = o
    rd = meshes.pop("Round_Mesh")
    meshes.update(case_from_round(rd, coll))
    # старый магазин быстрой перезарядки — те же сетки
    for src_name, name in (("Magazine_Mesh", "Part_SpareMag"), ("Follower_Mesh", "Part_SpareMagFollower")):
        o = bpy.data.objects.new(name, meshes[src_name].data)
        coll.objects.link(o)
        o["atlas"] = "Magazine"
        meshes[name] = o
    for o in meshes.values():
        at = o["atlas"]
        if at not in mats:
            mats[at] = material(at)
        if o.data.users == 1 or not o.data.materials or o.data.materials[0] != mats[at]:
            o.data.materials.clear()
            o.data.materials.append(mats[at])
        if "GameUV" in o.data.uv_layers:
            o.data.uv_layers.active = o.data.uv_layers["GameUV"]
    log("сетки", sorted(meshes))

    # ---- пустышка оружия на Weapon_CTRL: оси исходника
    T = Matrix.Translation(ORIGIN_WORLD) @ Matrix.Rotation(math.radians(-90.0), 4, "Z") @ Matrix.Translation(-ORIGIN)
    root = bpy.data.objects.new("ASTEN919", None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.03
    coll.objects.link(root)
    root.parent = arms
    root.parent_type = "BONE"
    root.parent_bone = "Weapon_CTRL"
    bpy.context.view_layer.update()
    root.matrix_world = T
    bpy.context.view_layer.update()

    # ---- риг оружия
    data = bpy.data.armatures.new("ASTEN919_WeaponRig")
    wr = bpy.data.objects.new("ASTEN919_WeaponRig", data)
    coll.objects.link(wr)
    wr.parent = root
    wr.matrix_parent_inverse = Matrix.Identity(4)
    data.display_type = "STICK"
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = wr
    wr.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, parent, _) in BONES.items():
        eb = data.edit_bones.new(name)
        eb.head = Vector(head)
        eb.tail = Vector(head) + Vector((0.02, 0.0, 0.0))
        eb.align_roll(Vector((0, 0, 1)))
        eb.use_deform = False
        if parent:
            eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in wr.pose.bones:
        pb.rotation_mode = "XYZ"
    bpy.context.view_layer.update()
    b0 = wr.data.bones["Slide"].matrix_local.to_3x3()
    log("оси кости (в осях исходника): X", [round(v, 2) for v in b0.col[0]], "Y", [round(v, 2) for v in b0.col[1]],
        "Z", [round(v, 2) for v in b0.col[2]])

    def attach(o, bone, src_matrix):
        o.parent = wr
        o.parent_type = "BONE"
        o.parent_bone = bone
        bpy.context.view_layer.update()
        o.matrix_world = T @ src_matrix
    for name, (_, _, parts) in BONES.items():
        for part in parts:
            o = meshes.get(part)
            if o is None:
                log("нет сетки", part)
                continue
            if part == "Part_Case":
                m = Matrix.Identity(4)                       # в патроннике: дно у зеркала, ось по каналу
            elif part == "Part_JamCase":
                q = Vector((1, 0, 0)).rotation_difference(JAM_CASE_DIR.normalized())
                m = Matrix.Translation(JAM_CASE_POS) @ q.to_matrix().to_4x4()
            else:
                m = o.matrix_world.copy()
            attach(o, name, m)
    # патроны: одна сетка, 17 мест (1 — верхний); у старого магазина — два верхних
    for i, m in enumerate(REC["rounds"], 1):
        r = bpy.data.objects.new(f"Round_{i:02d}", rd.data)
        coll.objects.link(r)
        r.data.materials.clear() if r.data.materials and r.data.materials[0] != mats["Magazine"] else None
        if not r.data.materials:
            r.data.materials.append(mats["Magazine"])
        attach(r, "Magazine", Matrix(m))
        if i <= 2:
            s = bpy.data.objects.new(f"SpareRound_{i:02d}", rd.data)
            coll.objects.link(s)
            attach(s, "SpareMag", Matrix(m))
    bpy.data.objects.remove(rd, do_unlink=True)
    # метки
    for name, bone, p in (("Muzzle", "WeaponRoot", REC["marks"]["Muzzle"]), ("SightFront", "Slide", REC["marks"]["SightFront"]),
                          ("SightRear", "Slide", REC["marks"]["SightRear"]), ("WeaponFrame", "WeaponRoot", REC["marks"]["Origin"])):
        e = bpy.data.objects.new(name, None)
        e.empty_display_size = 0.006
        coll.objects.link(e)
        attach(e, bone, Matrix.Translation(Vector(p)))
    # старый магазин и гильзы в покое не видны: кости сжаты в точку (клипы их «включают» масштабом)
    for b in ("SpareMag_Control", "Case", "JamCase"):
        wr.pose.bones[b].scale = (0.001, 0.001, 0.001)
    bpy.context.view_layer.update()

    root["axes"] = "исходник: +X дуло, +Y влево, +Z вверх; м; начало — зеркало затвора на оси канала"
    root["origin_game"] = list(ORIGIN)
    S.frame_start, S.frame_end = 1, 1
    S.camera = bpy.data.objects.get("FPS • Camera")
    for t in list(bpy.data.texts):
        bpy.data.texts.remove(t)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    log("сохранено", out)


if __name__ == "__main__":
    main()
