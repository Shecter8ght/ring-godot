"""Revise the saved Codex v01 artistic asset, preserving its hierarchy and controls.

blender --background --factory-startup --python tools/revise_flare_pistol_codex.py
    -- revise|render|verify [asset folder]

Rounded contact surfaces are explicit editable mesh strips. The small finishing
bevel is independent of those strips and cannot clamp their radius at label cuts.
No production mechanism, game export or texturing is part of this script.
"""

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("flare_helpers", HERE / "build_flare_pistol_codex.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "revise"
DEFAULT_OUT = HERE.parent if HERE.name == "source" else HERE.parent / "_asset_src" / "flare_pistol_codex"
OUT = Path(ARGS[1]) if len(ARGS) > 1 else DEFAULT_OUT
SOURCE = OUT / "models" / "launcher" / "flare_pistol_codex_geometry_v01.blend"
MASTER = OUT / "models" / "launcher" / "flare_pistol_codex_geometry_v02.blend"
MM = .001


def smoothstep(lo, hi, x):
    t = max(0, min(1, (x - lo) / (hi - lo)))
    return t * t * (3 - 2 * t)


def cap_outline(obj):
    """Read the saved source contour instead of rebuilding the complete asset."""
    caps = [f for f in obj.data.polygons if len(f.vertices) > 20]
    cap = max(caps, key=lambda f: len(f.vertices))
    pts = [(obj.data.vertices[i].co.x / MM, obj.data.vertices[i].co.z / MM)
           for i in cap.vertices]
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
               - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if area > 0 else list(reversed(pts))


def inward_offsets(pts):
    """Offset a sampled CCW curve using bisectors; preserve the traced silhouette."""
    normals = []
    for i, p in enumerate(pts):
        before = (Vector(p) - Vector(pts[i - 1])).normalized()
        after = (Vector(pts[(i + 1) % len(pts)]) - Vector(p)).normalized()
        n0 = Vector((-before.y, before.x))
        n1 = Vector((-after.y, after.x))
        direction = (n0 + n1).normalized()
        normals.append(direction / max(.35, direction.dot(n0)))
    return normals


def radius_at(x, z):
    # Smoothly taper before the narrow heel/lanyard eye and thumb shoulder.
    contact = 1 - smoothstep(-18, 0, x)
    heel = smoothstep(11, 25, z)
    shoulder = 1 - smoothstep(94, 108, z)
    palm = 1 - smoothstep(-56, -40, x)
    hand_radius = 4.6 + 1.4 * palm
    return 1.15 + (hand_radius - 1.15) * contact * heel * shoulder


def rounded_frame_data(obj):
    pts = cap_outline(obj)
    normals = inward_offsets(pts)
    radii = [radius_at(x, z) for x, z in pts]
    rings = []
    half = 10.3
    steps = 14
    # Lower planar cap to outer flank, then upper flank to planar cap.
    for side in [-1, 1]:
        angles = [math.pi / 2 * i / steps for i in range(steps + 1)]
        if side < 0:
            angles.reverse()
        for a in angles:
            ring = []
            for p, normal, r in zip(pts, normals, radii):
                q = Vector(p) + normal * (r * (1 - math.cos(a)))
                y = side * (half - r + r * math.sin(a))
                ring.append((q.x, y, q.y))
            rings.append(ring)
    verts = [co for ring in rings for co in ring]
    n = len(pts)
    faces = [tuple(reversed(range(n)))]
    for j in range(len(rings) - 1):
        for i in range(n):
            faces.append((j * n + i, j * n + (i + 1) % n,
                          (j + 1) * n + (i + 1) % n, (j + 1) * n + i))
    faces.append(tuple((len(rings) - 1) * n + i for i in range(n)))
    data = bpy.data.meshes.new("Frame_v02_rounded_contact_loft_editable")
    data.from_pydata([tuple(v * MM for v in co) for co in verts], [], faces)
    data.materials.append(obj.data.materials[0])
    data.update()
    obj.data = data
    helpers.recalc(obj)
    for f in data.polygons:
        f.use_smooth = len(f.vertices) == 4
    # Original Boolean stack and construction sources remain editable.
    for mod in list(obj.modifiers):
        if mod.type in {"BEVEL", "WEIGHTED_NORMAL"}:
            obj.modifiers.remove(mod)
    helpers.bevel(obj, .10, 5, .72)
    obj["contact_radii_mm"] = "palm 6.0; finger side 4.6; tapered heel/shoulder; 14 strips per quarter"
    obj["revision_method"] = "Saved silhouette retained; editable mesh rounding precedes the preserved Boolean cuts"
    return BVHTree.FromPolygons([v.co for v in data.vertices],
                               [list(f.vertices) for f in data.polygons], all_triangles=False)


def rounded_guard_entry():
    cutter = bpy.data.objects["Trigger_guard_void_source"]
    pts = cap_outline(cutter)
    normals = inward_offsets(pts)
    n = len(pts)
    radius, half, steps = 1.3, 10.3, 12
    rings = []
    rings.append([(x - normal.x * radius, -19., z - normal.y * radius)
                  for (x, z), normal in zip(pts, normals)])
    for side in [-1, 1]:
        angles = [math.pi / 2 * i / steps for i in range(steps + 1)]
        if side < 0:
            angles.reverse()
        for a in angles:
            ring = []
            for p, normal in zip(pts, normals):
                q = Vector(p) - normal * (radius * (1 - math.cos(a)))
                ring.append((q.x, side * (half - radius + radius * math.sin(a)), q.y))
            rings.append(ring)
    rings.append([(x - normal.x * radius, 19., z - normal.y * radius)
                  for (x, z), normal in zip(pts, normals)])
    faces = [tuple(reversed(range(n)))]
    faces += [(j * n + i, j * n + (i + 1) % n,
               (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
              for j in range(len(rings) - 1) for i in range(n)]
    faces.append(tuple((len(rings) - 1) * n + i for i in range(n)))
    data = bpy.data.meshes.new("Guard_v02_rounded_entry_cut_editable")
    data.from_pydata([tuple(v * MM for v in co) for ring in rings for co in ring], [], faces)
    data.update()
    cutter.data = data
    helpers.recalc(cutter)
    for f in data.polygons:
        f.use_smooth = len(f.vertices) == 4
    cutter["entry_radius_mm"] = 1.3


def surface_y(tree, x, z, side):
    hit = tree.ray_cast(Vector((x * MM, side * .1, z * MM)), Vector((0, -side, 0)), .2)
    if hit[0] is None:
        raise ValueError(f"Grip point is outside frame: {x:.4f}, {z:.4f}")
    return side * hit[0].y / MM


def replace_panel(obj, tree, side):
    pts = cap_outline(obj)
    normals = inward_offsets(pts)
    r = .8
    rings = []
    for upper in [False, True]:
        angles = [math.pi / 2 * i / 10 for i in range(11)]
        if upper:
            angles.reverse()
        for a in angles:
            ring = []
            for p, normal in zip(pts, normals):
                q = Vector(p) + normal * r * (1 - math.sin(a))
                body_y = surface_y(tree, q.x, q.y, side)
                depth = (2.0 - r * (1 - math.cos(a))) if upper else r * (1 - math.cos(a))
                ring.append((q.x, side * (body_y + .018 + depth), q.y))
            rings.append(ring)
    n = len(pts)
    verts = [co for ring in rings for co in ring]
    faces = []
    for j in range(len(rings) - 1):
        faces += [(j * n + i, j * n + (i + 1) % n,
                   (j + 1) * n + (i + 1) % n, (j + 1) * n + i) for i in range(n)]
    # A curved cap cannot be represented by one non-planar n-gon. Constrain a
    # sampled interior grid and project all new vertices to the saved metal form.
    for upper in [False, True]:
        ring = rings[-1] if upper else rings[0]
        outline = [(x, z) for x, y, z in ring]
        coordinates = [Vector(p) for p in outline]
        for row in range(57):
            z = 5.8 + row * 1.7
            for column in range(45):
                x = -77.5 + column * 1.7
                if inside((x, z), outline) and distance_to_outline((x, z), outline) > .9:
                    coordinates.append(Vector((x, z)))
        result = delaunay_2d_cdt(coordinates, [], [list(range(n))], 1, 1e-8, True)
        mapped = []
        start = (len(rings) - 1) * n if upper else 0
        for co, ids in zip(result[0], result[3]):
            boundary = [i for i in ids if i < n]
            if boundary:
                mapped.append(start + boundary[0])
            else:
                mapped.append(len(verts))
                y = surface_y(tree, co.x, co.y, side) + .018 + (2.0 if upper else 0.)
                verts.append((co.x, side * y, co.y))
        faces += [tuple(mapped[i] for i in face) for face in result[2]]
    data = bpy.data.meshes.new(f"Thin_panel_v02_contoured_{side}_editable")
    data.from_pydata([tuple(v * MM for v in co) for co in verts], [], faces)
    data.materials.append(obj.data.materials[0])
    data.update()
    obj.data = data
    helpers.recalc(obj)
    for f in data.polygons:
        f.use_smooth = True
    for mod in list(obj.modifiers):
        if mod.type in {"BEVEL", "WEIGHTED_NORMAL"}:
            obj.modifiers.remove(mod)
    # The rim is already rounded. This finishing bevel affects the screw cut only.
    helpers.bevel(obj, .10, 4, .8)
    obj["visual_thickness_mm"] = 2.0
    obj["rim_radius_mm"] = .8
    obj["revision_method"] = "Contour follows the rounded metal; thin 2 mm shell with rounded front/back rim"
    return pts


def inside(p, pts):
    x, z = p
    value = False
    j = len(pts) - 1
    for i in range(len(pts)):
        a, b = pts[i], pts[j]
        if ((a[1] > z) != (b[1] > z)) and x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]:
            value = not value
        j = i
    return value


def distance_to_outline(p, pts):
    p = Vector(p)
    distance = 1e10
    for i, a in enumerate(pts):
        a, b = Vector(a), Vector(pts[(i + 1) % len(pts)])
        line = b - a
        t = max(0, min(1, (p - a).dot(line) / line.length_squared))
        distance = min(distance, (p - (a + t * line)).length)
    return distance


def grip_grain(panel, pts, tree, side):
    """Small closed, embedded pebbles: inspectable relief, no texture substitute."""
    rng = random.Random(8108)
    verts, faces = [], []
    count = 0
    bpy.context.view_layer.update()
    evaluated = panel.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    panel_tree = BVHTree.FromPolygons([v.co for v in data.vertices],
                                     [list(f.vertices) for f in data.polygons])
    evaluated.to_mesh_clear()
    # A modest relief for silhouette review; paint micrograin still belongs to UCUPaint.
    for row in range(112):
        z = 5.5 + row * .85
        for column in range(85):
            x = -79 + column * .85 + (row % 2) * .425
            x += rng.uniform(-.34, .34)
            zz = z + rng.uniform(-.34, .34)
            if not inside((x, zz), pts) or distance_to_outline((x, zz), pts) < 2.0:
                continue
            if math.hypot(x + 61, zz - 27) < 5.0:
                continue
            r = rng.uniform(.16, .27)
            height = rng.uniform(.025, .065)
            base_y = surface_y(panel_tree, x, zz, side)
            start = len(verts)
            # One embedded base ring, three rounded meridians, and a small top cap.
            ring_specs = [(r, -.045), (r * .9, height * .35),
                          (r * .62, height * .79), (r * .25, height)]
            for radius, dy in ring_specs:
                for segment in range(10):
                    angle = 2 * math.pi * segment / 10
                    verts.append((x + radius * math.cos(angle), side * (base_y + dy),
                                  zz + radius * math.sin(angle)))
            faces.append(tuple(start + i for i in reversed(range(10))))
            for ring in range(3):
                for segment in range(10):
                    a = start + ring * 10 + segment
                    b = start + ring * 10 + (segment + 1) % 10
                    faces.append((a, b, b + 10, a + 10))
            faces.append(tuple(start + 30 + i for i in range(10)))
            count += 1
    grain = helpers.mesh(f"Grip_fine_relief_{side}", verts, faces,
                         bpy.data.collections["Thin_plastic_grip_panels"],
                         panel.data.materials[0], panel.parent, True)
    helpers.recalc(grain)
    grain["embedded_pebbles"] = count
    grain["relief_height_mm"] = ".025–.065; reference: own photos of Orion sellers"
    return count


def barrel_details():
    cuts = bpy.data.collections["90_Construction_cutters"]
    barrel = bpy.data.objects["Barrel_true_open_wall"]
    parent = barrel.parent
    col = bpy.data.collections["Barrel_break_open"]
    mat = barrel.data.materials[0]
    for side in [-1, 1]:
        old = bpy.data.objects.get(f"Barrel_side_blank_{side}")
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        cutter = helpers.prism(f"Barrel_recess_v02_source_{side}",
                               helpers.round_rect(33, 102, 108.7, 115.3, 3.25, 18),
                               side * 15.77, side * 21.5, cuts, None, parent)
        helpers.recalc(cutter)
        helpers.boolean(barrel, cutter, f"Recessed_side_panel_{side}")
    helpers.bevel(barrel, .17, 6, .65)
    rib_pts = helpers.path((26.0, 127.9), [
        ((26, 128.5), (26.4, 129.4), (27.3, 129.4)),
        ((50, 129.4), (90, 129.4), (110.5, 129.4)),
        ((112, 129.4), (112.3, 128.2), (111.1, 127.9)),
        ((84, 127.9), (53, 127.9), (26, 127.9)),
    ], 12)
    rib = helpers.prism("Barrel_integral_top_rib_v02", rib_pts, -1.65, 1.65,
                        col, mat, parent, .28)
    helpers.recalc(rib)
    rib["reference"] = "Narrow integral top rib visible on compact Orion photos; custom metal adaptation"


def receiver_details():
    frame = bpy.data.objects["Frame_continuous_metal_casting"]
    cuts = bpy.data.collections["90_Construction_cutters"]
    for side in [-1, 1]:
        cutter = helpers.prism(f"Receiver_lower_blank_v02_source_{side}",
                               helpers.round_rect(35.3, 58.7, 73.9, 77.0, 1.5, 16),
                               side * 10.07, side * 12.4, cuts, None, frame.parent)
        helpers.recalc(cutter)
        # Add immediately before the small finishing bevel, after the primary loft.
        mod = frame.modifiers.new(f"Lower_marking_recess_{side}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
        bpy.context.view_layer.objects.active = frame
        while list(frame.modifiers).index(mod) > len(frame.modifiers) - 3:
            bpy.ops.object.modifier_move_up(modifier=mod.name)
        cutter.hide_render = True
        cutter.hide_set(True)
        cutter.display_type = "WIRE"
    # Ring-shaped seat around the main pivot. This is a local external detail.
    col = bpy.data.collections["Levers_trigger_and_fasteners"]
    steel = bpy.data.materials["CHECK_Exposed_steel"]
    for side in [-1, 1]:
        profile = [(side * 10.18, 3.0), (side * 10.38, 3.5),
                   (side * 10.62, 3.5), (side * 10.74, 3.25),
                   (side * 10.74, 2.85), (side * 10.18, 2.85)]
        helpers.lathe(f"Hinge_head_seat_v02_{side}", profile, "Y", (75, 0, 94),
                      col, steel, frame.parent, 96)


def revise():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    frame = bpy.data.objects["Frame_continuous_metal_casting"]
    tree = rounded_frame_data(frame)
    rounded_guard_entry()
    counts = []
    for side in [-1, 1]:
        panel = bpy.data.objects[f"Grip_panel_thin_{side}"]
        pts = replace_panel(panel, tree, side)
        counts.append(grip_grain(panel, pts, tree, side))
        # Saved screw is re-seated flush with the new 2 mm cover, without changing its pivot.
        screw = bpy.data.objects[f"Grip_screw_{side}"]
        delta = side * .268 * MM
        for v in screw.data.vertices:
            v.co.y += delta
        source = bpy.data.objects[f"Grip_screw_{side}_slot_source"]
        for v in source.data.vertices:
            v.co.y += delta
        recess = bpy.data.objects[f"Grip_screw_recess_source_{side}"]
        for v in recess.data.vertices:
            v.co.y += delta
    barrel_details()
    receiver_details()
    ctrl = bpy.data.objects["CTRL_Launcher"]
    ctrl["geometry_version"] = "v02 — rounded grip and reference detail; owner review pending"
    ctrl["reference"] = "Owner photo 8, Orion seller photos, Sketchfab public previews: i_c_e_m_a_n_, TallinJH, Lazy Hanby"
    ctrl["open_degrees"] = 0.
    ctrl.update_tag()
    text = bpy.data.texts["00_README_RU"]
    text.clear()
    text.write("Ракетница — Codex, геометрия v02\n"
               "Исправление сохранённой v01: округлая металлическая рукоять (4.6–6 мм в контакте),\n"
               "пластиковые 2 мм накладки по её форме, кант 0.8 мм, мелкий геометрический рельеф.\n"
               "По фото добавлены утопленные боковые выемки ствола, верхнее ребро и нижняя площадка маркировки.\n"
               "CTRL_Launcher: open_degrees (0..48), hammer_cock, trigger_press, latch_release (0..1).\n"
               "Полного рабочего механизма нет. Масштаб оценочный, это художественный игровой ассет.\n"
               "Красный патрон — осветительный; зелёный — airdrop.\n"
               "UCUPaint после согласования геометрии; красный эскиз — проверочный материал.\n"
               "Оси X к дульному срезу, Y поперёк, Z вверх, метры. Источники в references/web/sources.md.\n")
    bpy.context.view_layer.update()
    helpers.setup_viewport()
    bpy.context.scene.render.filepath = "//../../previews/v02/01_three_quarter.png"
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    (OUT / "checks" / "v02").mkdir(parents=True, exist_ok=True)
    (OUT / "checks" / "v02" / "revision.json").write_text(json.dumps({
        "source": str(SOURCE), "candidate": str(MASTER),
        "primary_palm_radius_mm": 6.0, "primary_finger_radius_mm": 4.6,
        "guard_inner_entry_radius_mm": 1.3,
        "rim_radius_mm": .8, "panel_thickness_mm": 2., "grain_count_per_panel": counts,
        "method": "Patch of saved v01; explicit quarter-round strips before preserved Boolean cuts",
    }, indent=2), encoding="utf-8")
    print("CODEX_V02_SAVED", str(MASTER), "grain", counts, flush=True)


def render_view(*args, **kwargs):
    return helpers.render_view(*args, **kwargs, directory=OUT / "previews" / "v02")


def render():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    (OUT / "previews" / "v02").mkdir(parents=True, exist_ok=True)
    helpers.set_gpu()
    pistol = ["01_Launcher_Codex"]
    views = [
        ("01_three_quarter", (.24, -.38, .24), (.042, 0, .067), .32),
        ("02_left_profile", (.016, -.5, .065), (.016, 0, .065), .228),
        ("03_right_profile", (.016, .5, .065), (.016, 0, .065), .228),
        ("07_grip_and_guard", (-.13, -.23, .052), (-.023, 0, .051), .127),
        ("12_palm_back_rounding", (-.28, -.045, .053), (-.062, 0, .052), .116),
        ("13_finger_front_rounding", (.12, -.06, .035), (-.038, 0, .044), .112),
        ("14_grip_heel", (-.095, -.1, -.17), (-.053, 0, .025), .091),
        ("15_panel_rim_macro", (-.14, -.2, .08), (-.056, 0, .061), .070),
        ("16_barrel_detail", (.18, -.26, .20), (.057, 0, .11), .170),
    ]
    for name, loc, target, scale in views:
        render_view(name, loc, target, scale, only=pistol if name != "01_three_quarter" else None)
    render_view("04_open_breech", (.22, -.30, .23), (.018, 0, .084), .238,
                        open_deg=48, only=pistol)
    render_view("11_open_chamber_rear", (-.14, -.23, .235), (.034, 0, .127), .17,
                        open_deg=48, only=pistol)
    render_view("10_color_study_only", (.22, -.32, .205), (.045, 0, .067), .315, red=True)
    for name in ["Frame_and_metal_body", "Thin_plastic_grip_panels", "Levers_trigger_and_fasteners"]:
        bpy.data.collections[name].hide_render = True
    render_view("05_bore_muzzle", (.34, 0, .1118), (.068, 0, .112), .054,
                        only=pistol, res=(800, 800))
    render_view("06_bore_rear", (-.1, 0, .112), (.075, 0, .112), .055,
                        only=pistol, res=(800, 800))
    # Fresh-load v01 for directly comparable contact views.
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    helpers.set_gpu()
    render_view("before_palm_back", (-.28, -.045, .053), (-.062, 0, .052), .116, only=pistol)
    render_view("before_finger_front", (.12, -.06, .035), (-.038, 0, .044), .112, only=pistol)


def verify():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    launcher = [o for o in bpy.data.collections["01_Launcher_Codex"].all_objects
                if not any(c.name == "90_Construction_cutters" for c in o.users_collection)]
    bounds = helpers.evaluated_bounds(launcher)
    report = {"file": str(MASTER), "bounds": bounds, "poses": []}
    ctrl = bpy.data.objects["CTRL_Launcher"]
    for deg in [0, 24, 48]:
        ctrl["open_degrees"] = deg
        ctrl.update_tag()
        bpy.context.view_layer.update()
        hinge = bpy.data.objects["PIVOT_Barrel_hinge"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        muzzle = bpy.data.objects["SOCKET_Muzzle"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        report["poses"].append({"degrees": deg,
                                "evaluated_hinge_degrees": [math.degrees(v) for v in hinge.matrix_world.to_euler()],
                                "muzzle_mm": [v / MM for v in muzzle.matrix_world.translation]})
    # Use preserved strict topology and passage criteria, measured candidate bounds.
    config = json.loads((OUT / "checks" / "audit-config.json").read_text(encoding="utf-8"))
    config["targets"][0]["dimensions_mm"]["expected"] = [198.1, 32.8, 130.4]
    config["targets"][0]["dimensions_mm"]["tolerance_mm"] = .15
    path = OUT / "checks" / "v02"
    path.mkdir(parents=True, exist_ok=True)
    (path / "audit-config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (path / "reopen_dimensions_poses.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("V02_REOPEN", json.dumps(report), flush=True)


if __name__ == "__main__":
    {"revise": revise, "render": render, "verify": verify}[MODE]()
