"""NPC «мародёр»: сборка всех вещей на теле и материалы для просмотра в Blender.

Читает куртку (в её файле уже тело, скелет, брюки, берцы) и балаклаву, убирает тело под одеждой
(остаются кисти и кожа в прорези балаклавы), считает маски износа по месту (wear.py: края, швы,
локти, колени, сиденье, складки, сжатие ткани, верх) и назначает материалы (materials.py):
- куртка — поношенная кожа CC0 (fabric_leather_01 без шва), отделка стёрта по маскам, заломы там, где сжата;
- трикотаж (воротник, манжеты, пояс) — рубчик, петли вязки, катышки на краях;
- брюки — свой камуфляж «Лесополоса» по лекалам, саржа, выгорание, жирные пятна, грязь книзу;
- берцы — промасленная кожа CC0 (fabric_leather_02 без шва), сбитый носок, заломы сгиба, грязь;
- балаклава — вязка CC0 (knitted_fleece), катышки, влажное у рта;
- кожа рук — текстура MakeHuman (CC0), обветренная, грязь в складках.
Материалы узлами (Cycles); для игры потом — запекание в атласы на развёртках лекал.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/assemble.py [-- render]
→ _asset_src/npc_kit/npc_scav_<версия>.blend (+ снимки в previews/)
"""
from __future__ import annotations

import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import materials as mt  # noqa: E402
import pockets  # noqa: E402
import wear  # noqa: E402

OUT = kc.WORK / f"npc_scav_{kc.VERSION}.blend"
ZIP_GROOVE_W = 0.0065     # канавка под молнию: полуширина (кромки кожи у звеньев)
ZIP_GROOVE_D = 0.0028     # и глубина у оси


# ---------- молния ----------

def add_zipper(jacket: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    """Молния по центру переда: линия застёжки — вершины куртки у x = 0 спереди, по высоте через 1 см;
    тесьма 2,2 см, зубцы через 3 мм (вперемешку слева и справа), бегунок с язычком у ворота."""
    from mathutils.bvhtree import BVHTree
    me = jacket.data
    # Тесьма вшита под кромки полочек: кожа у центра переда загибается внутрь канавкой (кромки подходят
    # к звеньям вплотную), тесьма — на дне канавки, видны только звенья. Раньше молния лежала поверх кожи.
    me.update()
    for v in me.vertices:
        p = v.co
        if p.y > -0.04 or not 0.90 < p.z < 1.53 or abs(p.x) > ZIP_GROOVE_W:
            continue
        ends = gm.smoothstep((p.z - 0.90) / 0.02) * gm.smoothstep((1.53 - p.z) / 0.02)
        depth = ZIP_GROOVE_D * (1.0 - gm.smoothstep(abs(p.x) / ZIP_GROOVE_W)) * ends
        v.co = p - v.normal * depth
    me.update()
    pts = [v.co.copy() for v in me.vertices if abs(v.co.x) < 0.005 and v.co.y < -0.04 and 0.90 < v.co.z < 1.52]
    if len(pts) < 10:
        return None
    bins: dict[int, list[Vector]] = {}
    for p in pts:
        bins.setdefault(int(p.z / 0.01), []).append(p)
    line = []
    for k in sorted(bins):
        front = min(bins[k], key=lambda q: q.y)
        line.append(Vector((0.0, front.y, front.z)))
    for _ in range(4):
        line = [line[0]] + [(line[i - 1] + line[i] * 2 + line[i + 1]) / 4 for i in range(1, len(line) - 1)] + [line[-1]]
    bvh = BVHTree.FromObject(jacket, bpy.context.evaluated_depsgraph_get())
    # Равномерно через 3 мм.
    cum = [0.0]
    for a, b in zip(line, line[1:]):
        cum.append(cum[-1] + (b - a).length)
    step = 0.003
    samples = []
    t = 0.0
    j = 0
    while t < cum[-1]:
        while cum[j + 1] < t:
            j += 1
        f = (t - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        samples.append(line[j].lerp(line[j + 1], f))
        t += step
    bm = bmesh.new()
    tape_rows = []
    for k, p in enumerate(samples):
        tan = (samples[min(k + 1, len(samples) - 1)] - samples[max(k - 1, 0)]).normalized()
        hit = bvh.find_nearest(p)
        nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
        if nrm.y > 0:
            nrm = -nrm
        side = tan.cross(nrm).normalized()
        base = (hit[0] if hit[0] is not None else p) + nrm * 0.0006
        row = []
        for o in (-0.0065, -0.0025, 0.0025, 0.0065):
            # Тесьма — по дну канавки; края её уходят под загнутые кромки кожи.
            q = base + side * o
            h2 = bvh.find_nearest(q)
            if h2[0] is not None:
                n2 = h2[1] if h2[1].dot(nrm) > 0 else -h2[1]
                q = h2[0] - n2 * (0.0008 if abs(o) > 0.004 else -0.0006)
            row.append(bm.verts.new(q))
        tape_rows.append(row)
        base = (row[1].co + row[2].co) / 2
        # Зуб: брусок 3,6 × 2,2 × 1,6 мм, через один — с левой и правой ленты (сцепление); верх звеньев
        # чуть ниже кромок кожи.
        sgn = 1 if k % 2 else -1
        c = base + side * (0.0012 * sgn) + nrm * 0.0010
        hx, hy, hz = side * 0.0018, tan * 0.0011, nrm * 0.0008
        vs = [bm.verts.new(c + a * hx + b * hy + d * hz) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
    for r0, r1 in zip(tape_rows, tape_rows[1:]):
        for i in range(3):
            bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    # Бегунок и язычок у верхнего конца.
    top = samples[-4]
    tan = (samples[-1] - samples[-6]).normalized()
    hit = bvh.find_nearest(top)
    nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
    if nrm.y > 0:
        nrm = -nrm
    side = tan.cross(nrm).normalized()
    for (c, hs, ht, hn) in ((top + nrm * 0.0035, 0.0065, 0.011, 0.0028),
                            (top + nrm * 0.0055 - tan * 0.022, 0.0045, 0.013, 0.0008)):
        vs = [bm.verts.new(c + side * (a * hs) + tan * (b * ht) + nrm * (d * hn)) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
    mesh = bpy.data.meshes.new("Jacket_Zipper")
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Jacket_Zipper", mesh)
    col.objects.link(obj)
    tape = bpy.data.materials.new("Zipper_Tape")
    mt.mat_simple(tape, (0.02, 0.018, 0.016), 0.8, bump_scale=3000.0)
    metal = bpy.data.materials.new("Zipper_Metal")
    mt.mat_simple(metal, (0.30, 0.27, 0.22), 0.38, metal=1.0)
    mesh.materials.append(tape)
    mesh.materials.append(metal)
    # Порядок граней — как создавали: зубцы (6 на точку), тесьма, бегунок с язычком.
    t0 = 6 * len(samples)
    t1 = t0 + 3 * (len(tape_rows) - 1)
    for poly in mesh.polygons:
        poly.material_index = 0 if t0 <= poly.index < t1 else 1
    return obj


# ---------- сборка ----------

def under_balaclava_ear(f: bmesh.types.BMFace) -> bool:
    """Ухо и висок под балаклавой: тонкий край ушной раковины прорезал трикотаж между его вершинами
    (оранжевая полоска у уха, видна под шлемом высокого среза). Из прорези эти места не видны."""
    return all(abs(v.co.x) > 0.058 and 1.60 < v.co.z < 1.76 and v.co.y > -0.10 for v in f.verts)


def hide_covered_body(body: bpy.types.Object) -> None:
    """Под одеждой тело не рисуется: остаются кисти (с запасом под манжетой) и голова с шеей
    (под балаклавой; кожа видна в прорези)."""
    groups = {vg.index: vg.name for vg in body.vertex_groups}
    hand_bones = ("hand", "thumb", "index", "middle", "ring", "pinky")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    dl = bm.verts.layers.deform.active
    keep_v = set()
    for v in bm.verts:
        w = sum(wt for gi, wt in v[dl].items() if groups.get(gi, "").startswith(hand_bones))
        if w > 0.05 or v.co.z > 1.50:
            keep_v.add(v)
    kill = [f for f in bm.faces if not all(v in keep_v for v in f.verts) or under_balaclava_ear(f)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()


def thicken(obj: bpy.types.Object, bvh, thickness: float) -> None:
    """Толщина ткани внутрь (наружная поверхность — та, что из симуляции), с кромкой по краям:
    на низе, манжетах и вороте видно, что это материал, а не плёнка. Нормали — от тела (bvh —
    тело целиком, до того как спрятали закрытое одеждой)."""
    me = obj.data
    votes = 0
    for v in list(me.vertices)[::7]:
        loc, _, _, d = bvh.find_nearest(v.co)
        if loc is not None and d < 0.08:
            votes += 1 if v.normal.dot(v.co - loc) > 0 else -1
    if votes < 0:
        for poly in me.polygons:
            poly.flip()
        me.update()
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = -1.0
    mod.use_even_offset = True
    mod.use_rim = True
    mod.use_quality_normals = True
    kc.log(f"  толщина {obj.name}: {thickness * 1000:.1f} мм, нормали {'перевёрнуты' if votes < 0 else 'наружу'}")


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "jacket" / "jacket_sim.blend"))
    for name in ("96_Jacket_Work", "97_Snapshots", "98_Sim_Colliders"):
        col = bpy.data.collections.get(name)
        if col:
            for o in list(col.objects):
                bpy.data.objects.remove(o)
            bpy.data.collections.remove(col)
    with bpy.data.libraries.load(str(kc.WORK / "balaclava" / "balaclava.blend")) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("Balaclava")]
    bcol = kc.collection("05_Balaclava")
    for o in dst.objects:
        bcol.objects.link(o)
    body = bpy.data.objects["NPC_Body"]
    from mathutils.bvhtree import BVHTree
    body_bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    hide_covered_body(body)
    zip_obj = add_zipper(bpy.data.objects["Jacket"], bpy.data.collections["03_Jacket"])
    kc.log("NPC_ZIPPER", len(zip_obj.data.polygons) if zip_obj else 0, "граней")
    for n in ("NPC_Eyebrows",):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = True            # под балаклавой брови не видны
            o.hide_set(True)
    # Сначала толщина: она же выравнивает нормали наружу, от них считаются гребни, впадины и «верх».
    thicken(bpy.data.objects["Jacket"], body_bvh, 0.0016)
    thicken(bpy.data.objects["Pants"], body_bvh, 0.0010)
    rig = bpy.data.objects["NPC_Skeleton"]
    wear.jacket_masks(bpy.data.objects["Jacket"], rig, kc.log)
    wear.pants_masks(bpy.data.objects["Pants"], rig, kc.log)
    for name in ("Boots_L", "Boots_R"):
        wear.boot_masks(bpy.data.objects[name], kc.log)
    bala = bpy.data.objects.get("Balaclava")
    if bala:
        # Рот — по центру лица на 8,5 см ниже глаз, у передней поверхности.
        eyes = bpy.data.objects["NPC_Eyes"]
        pts = [eyes.matrix_world @ v.co for v in eyes.data.vertices]
        mouth = Vector((0.0, min(p.y for p in pts) - 0.005, sum(p.z for p in pts) / len(pts) - 0.085))
        wear.knit_masks(bala, mouth, kc.log)
    mats = bpy.data.materials
    mt.mat_leather_jacket(mats["Jacket_Leather"])
    mt.mat_rib(mats["Jacket_Rib"])
    mt.mat_camo(mats["Pants_Fabric"])
    mt.mat_boot_leather(mats["Boot_Leather"])
    mt.mat_rubber(mats["Boot_Rubber"], True)
    mt.mat_rubber(mats["Boot_Sole"], False)
    mt.mat_simple(mats["Boot_Lace"], (0.045, 0.032, 0.022), 0.85, bump_scale=2000.0)
    mt.mat_simple(mats["Boot_Metal"], (0.20, 0.20, 0.21), 0.42, metal=1.0)
    mt.mat_simple(mats["Boot_Mesh"], (0.05, 0.038, 0.028), 0.9, grid=True)
    mt.mat_knit(mats["Balaclava_Knit"])
    # Карманы-карго — объёмные нашивные детали со своей строчкой.
    pocket_mat = mats.new("Pocket_Fabric")
    mt.mat_camo(pocket_mat, stitch=True)
    snap = mats.new("Snap_Metal")
    mt.mat_simple(snap, (0.16, 0.155, 0.14), 0.45, metal=1.0)
    for pk in pockets.cargo_pockets(bpy.data.objects["Pants"], bpy.data.collections["02_Pants"], pocket_mat, snap):
        wear.pants_masks(pk, rig, kc.log)
        adj = wear.adjacency(pk.data)
        wear.write(pk, "bd", wear.dijkstra(adj, wear.boundary_vertices(pk.data), 0.03))
    skin = mats.new("NPC_Skin")
    mt.mat_skin(skin)
    body.data.materials.clear()
    body.data.materials.append(skin)
    eyes = bpy.data.objects["NPC_Eyes"]
    eye = mats.new("NPC_Eye")
    mt.mat_eye(eye)
    eyes.data.materials.clear()
    eyes.data.materials.append(eye)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name not in ("Studio_Floor",):
            for p in o.data.polygons:
                p.use_smooth = True
    kc.studio()
    kc.save(OUT)
    kc.log("NPC_ASSEMBLED", str(OUT))
    if "render" in args:
        cams = kc.view_cameras(1.8)
        cams["head"] = kc.camera("Cam_Head", (0.32, -0.95, 1.70), (0, -0.04, 1.62), 85)
        cams["boots"] = kc.camera("Cam_Boots", (0.75, -0.9, 0.35), (0.0, -0.05, 0.18), 70)
        cams["torso"] = kc.camera("Cam_Torso", (0.7, -1.4, 1.35), (0.0, 0.0, 1.22), 75)
        for view, size in (("front", (900, 1300)), ("three_quarter", (900, 1300)), ("back", (900, 1300)),
                           ("head", (900, 900)), ("torso", (1000, 900)), ("boots", (1000, 800))):
            kc.render(cams[view], kc.WORK / "previews" / f"scav_{kc.VERSION}_{view}.png", size, 128)


if __name__ == "__main__":
    main()
