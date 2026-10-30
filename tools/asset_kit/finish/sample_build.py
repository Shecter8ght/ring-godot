# Каталог отделок: универсальный образец для карточек — брусок оружейного масштаба, на котором сразу видно плоскость,
# кромку, углубление, цилиндр и мелкий крепёж (выбор владельца 2026-10-30: «универсальный образец»). Запускается в
# Blender в фоне:
#   blender --background --factory-startup --python-exit-code 1 --python tools/asset_kit/finish/sample_build.py -- <папка>
# Пишет <папка>/finish_sample.blend и finish_sample.fbx (для Painter: сетка сама себе high-poly, одна текстура).
# Размеры — мм, оси: X — длина, Y — ширина, Z — высота; в сцене — метры.
import math
import sys
from pathlib import Path

import bmesh
import bpy

OUT = Path(sys.argv[sys.argv.index("--") + 1]).resolve() if "--" in sys.argv else Path.cwd()
MM = 0.001
L, W, H = 120.0, 36.0, 24.0     # брусок, как ствольная коробка пистолета-пулемёта
CH = 1.2                        # фаска кромок (скругление в 3 сегмента) — у серийных деталей кромки не режут глаз
PX_MM = 14.0                    # плотность развёртки, как у принятых стволов (AR-15: 11–14 пикс/мм на 4K)
RES = 4096


def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def obj_from_bm(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("b", "BOOLEAN")
    m.object = cutter
    m.operation = op
    m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def box(name, sx, sy, sz, loc):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx * MM
        v.co.y *= sy * MM
        v.co.z *= sz * MM
        v.co.x += loc[0] * MM
        v.co.y += loc[1] * MM
        v.co.z += loc[2] * MM
    return obj_from_bm(name, bm)


def cyl(name, r, depth, loc, axis="Z", seg=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r * MM, radius2=r * MM, depth=depth * MM)
    rot = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    ob = obj_from_bm(name, bm)
    ob.rotation_euler = rot
    ob.location = (loc[0] * MM, loc[1] * MM, loc[2] * MM)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.select_set(False)
    return ob


def bevel(ob, width, seg=3, angle=40):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = width * MM
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    m.use_clamp_overlap = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)


def smooth(ob, angle=35):
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:
        pass


def build():
    clean()
    # корпус: брусок, сверху продольный паз, на боку окно-углубление и сквозное отверстие оси
    body = box("Body", L, W, H, (0, 0, 0))
    boolean(body, box("cut_slot", L * 0.62, 8.0, 10.0, (-6, 0, H / 2)))                 # паз сверху, глубина 5
    boolean(body, box("cut_pocket", 34.0, 10.0, 12.0, (-28, -W / 2, -2)))                # карман на боку, глубина 5
    boolean(body, cyl("cut_hole", 3.5, W + 4, (30, 0, -4), "Y", 40))                     # ось Ø7 насквозь
    boolean(body, cyl("cut_relief", 6.0, 3.0, (30, -W / 2, -4), "Y", 48))                # цековка у оси
    # поперечные рифления на задней части — мелкий рельеф, где блик рвётся
    for i in range(6):
        boolean(body, box(f"cut_rib{i}", 1.6, W + 4, 2.4, (46 + i * 2.6, 0, H / 2)))
    bevel(body, CH, 3, 40)
    smooth(body)

    # ствол-цилиндр, выходит из торца: блик собирается в полосу; ступень и фаска на конце
    barrel = cyl("Barrel", 7.0, 44.0, (-L / 2 - 22 + 2, 0, 2), "X", 64)
    step = cyl("BarrelStep", 9.0, 8.0, (-L / 2 - 2, 0, 2), "X", 64)
    for ob in (barrel, step):
        bevel(ob, 0.6, 2, 30)
        smooth(ob)
    # винт с потайной головкой и шлицем на боку, гайка сверху — мелкий крепёж
    screw = cyl("Screw", 3.0, 2.0, (8, -W / 2 - 0.6, -4), "Y", 32)
    boolean(screw, box("cut_slot_s", 6.5, 1.2, 0.8, (8, -W / 2 - 1.4, -4)))
    bevel(screw, 0.3, 2, 30)
    smooth(screw)
    nut = cyl("Nut", 5.5, 3.0, (-40, 0, H / 2 + 1.2), "Z", 6)
    boolean(nut, cyl("cut_nut", 2.5, 6.0, (-40, 0, H / 2 + 1.2), "Z", 32))
    bevel(nut, 0.4, 2, 30)
    smooth(nut)

    parts = [body, barrel, step, screw, nut]
    for ob in parts:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")   # Painter сам режет n-угольники криво
        bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.0, area_weight=0.0, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    # одна сетка, одна развёртка; укладка — общим модулем проекта нельзя (он завязан на оружейные наборы), поэтому
    # штатная упаковка Blender с плотностью, заданной масштабом: острова в одном масштабе по мм
    bpy.ops.object.select_all(action="DESELECT")
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    ob = body
    ob.name = "FinishSample"
    ob.data.name = "FinishSample"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True, shape_method="CONCAVE", scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    mat = bpy.data.materials.new("FinishSample")
    ob.data.materials.append(mat)
    return ob


def density(ob):
    """Пикселей текстуры на мм: корень из (площадь UV в пикселях / площадь поверхности в мм²)."""
    me = ob.data
    uv = me.uv_layers.active.data
    area3 = sum(p.area for p in me.polygons) / (MM * MM)
    area2 = 0.0
    for p in me.polygons:
        pts = [uv[i].uv for i in p.loop_indices]
        s = 0.0
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            s += a.x * b.y - b.x * a.y
        area2 += abs(s) / 2
    return math.sqrt(area2 * RES * RES / area3), area2


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ob = build()
    px, fill = density(ob)
    print(f"SAMPLE tris={sum(len(p.vertices) - 2 for p in ob.data.polygons)} fill={fill:.2f} px_mm@{RES}={px:.1f}")
    ob["finish_px_mm"] = px
    ob["finish_res"] = RES
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "finish_sample.blend"))
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(filepath=str(OUT / "finish_sample.fbx"), use_selection=True, apply_unit_scale=True,
                             axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE", use_tspace=True)
    (OUT / "finish_sample.json").write_text(
        '{"px_mm": %.3f, "res": %d, "fill": %.3f}\n' % (px, RES, fill), encoding="utf-8")


main()
