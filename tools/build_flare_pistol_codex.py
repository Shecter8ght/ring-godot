"""Редактируемая художественная ракетница по фото 8 владельца, без игрового экспорта.

Blender 5.2: --background --factory-startup --python tools/build_flare_pistol_codex.py
  -- build|render|parts|verify [папка комплекта]
Размеры в исходных профилях — оценка для игрового предмета, в миллиметрах.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

MM = 0.001
ROOT = Path(__file__).resolve().parents[1]
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "build"
DEFAULT_OUT = ROOT if Path(__file__).resolve().parent.name == "source" else ROOT / "_asset_src" / "flare_pistol_codex"
OUT = Path(ARGS[1]) if len(ARGS) > 1 else DEFAULT_OUT
MASTER = OUT / "models" / "launcher" / "flare_pistol_codex_geometry_v01.blend"


def collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def move_to(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)


def material(name, color, metal=0.0, rough=0.55):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    p = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    return mat


def mesh(name, verts, faces, col, mat, parent=None, smooth=False):
    data = bpy.data.meshes.new(name + "_editable")
    data.from_pydata([tuple(v * MM for v in co) for co in verts], [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    col.objects.link(obj)
    if mat:
        data.materials.append(mat)
    if parent:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    for f in data.polygons:
        f.use_smooth = smooth
    obj["author"] = "Codex"
    return obj


def bevel(obj, width, segments=5, angle=0.6):
    mod = obj.modifiers.new("Editable_edge_radii", "BEVEL")
    mod.width = width * MM
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = angle
    mod.harden_normals = True
    mod.use_clamp_overlap = True
    norm = obj.modifiers.new("Keep_broad_planes_clean", "WEIGHTED_NORMAL")
    norm.keep_sharp = True
    norm.weight = 40
    return obj


def empty(name, col, loc=(0, 0, 0), parent=None, display=0.01):
    obj = bpy.data.objects.new(name, None)
    col.objects.link(obj)
    obj.location = Vector(loc) * MM
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = display
    if parent:
        bpy.context.view_layer.update()
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return obj


def path(start, segments, count=10):
    """Кубические контуры сняты с силуэта фото, без усреднения других вариантов."""
    pts = [start]
    p0 = start
    for a, b, end in segments:
        for step in range(1, count + 1):
            t = step / count
            u = 1 - t
            pts.append(tuple(u ** 3 * p0[j] + 3 * u * u * t * a[j]
                             + 3 * u * t * t * b[j] + t ** 3 * end[j]
                             for j in range(2)))
        p0 = end
    if Vector(pts[0]).__sub__(Vector(pts[-1])).length < 1e-6:
        pts.pop()
    return pts


def prism(name, pts, y0, y1, col, mat, parent=None, radius=0):
    y0, y1 = sorted((y0, y1))
    n = len(pts)
    verts = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
    # Противоположные торцы и цельный пояс; concave cap остаётся редактируемым.
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n))
    if area < 0:
        pts = list(reversed(pts))
        verts = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, i + n, (i + 1) % n + n, (i + 1) % n) for i in range(n)]
    obj = mesh(name, verts, faces, col, mat, parent, True)
    if radius:
        bevel(obj, radius)
    return obj


def lathe(name, profile, axis, center, col, mat, parent=None, segments=128):
    """Замкнутый меридиональный профиль даёт настоящую стенку, а не cap в отверстии."""
    verts = []
    for t, r in profile:
        for i in range(segments):
            a = i * 2 * math.pi / segments
            if axis == "X":
                co = (t, r * math.cos(a), r * math.sin(a))
            elif axis == "Y":
                co = (r * math.cos(a), t, r * math.sin(a))
            else:
                co = (r * math.cos(a), r * math.sin(a), t)
            verts.append(tuple(co[j] + center[j] for j in range(3)))
    n = len(profile)
    faces = []
    for j in range(n):
        for i in range(segments):
            faces.append((j * segments + i, j * segments + (i + 1) % segments,
                          ((j + 1) % n) * segments + (i + 1) % segments,
                          ((j + 1) % n) * segments + i))
    obj = mesh(name, verts, faces, col, mat, parent, True)
    # Профиль может обходить наружную и внутреннюю стороны; normals наружу по объёму.
    recalc(obj)
    return obj


def recalc(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def disk(name, r, depth, axis, center, col, mat, parent=None, segments=96, radius=0.2):
    # Радиальные торцы соединены с единственным центральным vertex без нулевых граней.
    verts = []
    for d in [-depth / 2, depth / 2]:
        for i in range(segments):
            a = 2 * math.pi * i / segments
            if axis == "Y":
                co = (r * math.cos(a), d, r * math.sin(a))
            elif axis == "X":
                co = (d, r * math.cos(a), r * math.sin(a))
            else:
                co = (r * math.cos(a), r * math.sin(a), d)
            verts.append(tuple(co[j] + center[j] for j in range(3)))
    faces = [tuple(reversed(range(segments))), tuple(range(segments, 2 * segments))]
    faces += [(i, (i + 1) % segments, (i + 1) % segments + segments, i + segments)
              for i in range(segments)]
    obj = mesh(name, verts, faces, col, mat, parent, True)
    recalc(obj)
    if radius:
        bevel(obj, radius, 4)
    return obj


def boolean(target, cutter, name):
    mod = target.modifiers.new(name, "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    # Boolean идёт перед радиусами, исходные cutters сохраняются отдельно.
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_move_up(modifier=mod.name)
    if len(target.modifiers) > 2:
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    cutter.hide_render = True
    cutter.hide_set(True)
    cutter.display_type = "WIRE"


def driver(obj, prop, factor, index=1, kind="rotation_euler"):
    fc = obj.driver_add(kind, index)
    var = fc.driver.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    var.targets[0].id = bpy.data.objects["CTRL_Launcher"]
    var.targets[0].data_path = '["' + prop + '"]'
    fc.driver.expression = "v * " + str(factor)


def round_rect(x0, x1, z0, z1, r, count=12):
    pts = []
    for cx, cz, start in [(x1-r, z1-r, 0), (x0+r, z1-r, 90),
                           (x0+r, z0+r, 180), (x1-r, z0+r, 270)]:
        for i in range(count):
            a = math.radians(start + 90 * i / (count-1))
            pts.append((cx+r*math.cos(a), cz+r*math.sin(a)))
    return pts


def bolt(name, x, z, y, r, col, mat, parent=None, slotted=False):
    side = 1 if y > 0 else -1
    head = disk(name, r, 1.1, "Y", (x,y,z), col, mat, parent, radius=0.25)
    if slotted:
        cuts = bpy.data.collections["90_Construction_cutters"]
        slot = prism(name+"_slot_source", round_rect(x-r*.65,x+r*.65,z-.32,z+.32,.15),
                     y+side*.1, y+side*1.5, cuts, None, parent)
        boolean(head, slot, "Screwdriver_slot")
    return head


def barrel_side_strip(side, col, mat, parent):
    pts = round_rect(33, 102, 107.8, 113.8, 2.7)
    obj = prism("Barrel_side_blank_"+str(side), pts,
                side*15.8, side*16.58, col, mat, parent, .24)
    recalc(obj)
    # Узкая площадка прилегает к округлой стенке, без выступающих проводов.
    return obj


def build_launcher():
    scene = bpy.context.scene
    base = collection("01_Launcher_Codex")
    frame_col = collection("Frame_and_metal_body", base)
    barrel_col = collection("Barrel_break_open", base)
    grip_col = collection("Thin_plastic_grip_panels", base)
    small_col = collection("Levers_trigger_and_fasteners", base)
    cuts = collection("90_Construction_cutters", base)
    cuts.hide_render = True
    root = empty("CTRL_Launcher", frame_col)
    root["open_degrees"] = 0.0
    root["hammer_cock"] = 0.0
    root["trigger_press"] = 0.0
    root["latch_release"] = 0.0
    root["geometry_version"] = "v01 — owner review pending"
    root["reference"] = "Owner photo 8 silhouette, photo 7 cartridges; metal artistic adaptation"
    root["future_finish"] = "Bright matte red coating, edge/contact wear to metal in UCUPaint after approval"
    for prop, limits in [("open_degrees", (0,48)), ("hammer_cock", (0,1)),
                         ("trigger_press", (0,1)), ("latch_release", (0,1))]:
        root.id_properties_ui(prop).update(min=limits[0], max=limits[1], soft_min=limits[0],
                                          soft_max=limits[1])
    body_mat = bpy.data.materials["CHECK_Metal_body_unpainted"]
    steel = bpy.data.materials["CHECK_Exposed_steel"]
    dark = bpy.data.materials["CHECK_Thin_black_plastic"]
    body_pts = path((12,128), [
        ((15,129),(20,129),(22,126)),
        ((23,122),(22,113),(22,102)),
        ((33,99),(66,98),(78,98)),
        ((83,98),(85,95),(85,89)),
        ((85,82),(85,75),(83,73)),
        ((80,71),(63,72),(54,72)),
        ((51,69),(52,60),(51,53)),
        ((50,42),(43,37),(34,37)),
        ((25,37),(9,36),(3,39)),
        ((-3,42),(-8,47),(-16,49)),
        ((-30,51),(-41,42),(-43,29)),
        ((-44,21),(-43,13),(-41,8)),
        ((-40,3),(-43,-1),(-49,-1)),
        ((-61,-1),(-77,1),(-81,10)),
        ((-86,19),(-82,31),(-78,42)),
        ((-72,58),(-60,78),(-46,91)),
        ((-38,100),(-29,105),(-23,105)),
        ((-16,103),(-6,99),(0,103)),
        ((6,111),(8,123),(12,128)),
    ], 8)
    frame = prism("Frame_continuous_metal_casting", body_pts, -10.3, 10.3,
                  frame_col, body_mat, root, 1.15)
    hole_pts = path((8,70), [
        ((16,73),(32,73),(38,70)), ((46,67),(47,58),(44,52)),
        ((42,45),(37,42),(30,42)), ((22,41),(10,41),(6,44)),
        ((1,48),(1,63),(8,70)),
    ], 14)
    hole = prism("Trigger_guard_void_source", hole_pts, -19,19,cuts,None,root)
    boolean(frame, hole, "Open_trigger_guard")
    sling = disk("Lanyard_hole_source", 3.35, 50, "Y", (-47,5,5),cuts,None,root,radius=0)
    boolean(frame, sling, "Through_lanyard_eye")
    # Верхняя щель вмещает отдельный шарнирный узел; не полая имитация сплошного тела.
    slot = prism("Upper_fork_clearance_source", [(18,84.0),(83,84.0),(83,137),(18,137)],
                 -5.8,5.8,cuts,None,root)
    boolean(frame,slot,"Hinge_fork_clearance")
    # Боковая неглубокая площадка для будущей текстурной маркировки.
    for side in [-1,1]:
        cutter = prism("Receiver_label_recess_source_"+str(side),
                       round_rect(28,65,78,89,2.2), side*10.02,side*12,
                       cuts,None,root)
        recalc(cutter)
        boolean(frame,cutter,"Blank_label_recess_"+str(side))

    hinge = empty("PIVOT_Barrel_hinge", barrel_col, (75,0,94), root)
    driver(hinge,"open_degrees", math.pi/180)
    # Канал открыт с обеих сторон. Задний уступ расширен под видимый обод патрона.
    profile = [(23,15.5),(23.35,16.1),(24.1,16.4),(112.8,16.4),
               (114.0,16.1),(114.8,15.6),(114.8,13.6),(114.35,13.3),
               (25.8,13.3),(25.5,13.55),(23,13.55)]
    barrel = lathe("Barrel_true_open_wall",profile,"X",(0,0,112),barrel_col,
                   body_mat,hinge,160)
    barrel["channel"] = "Visual passage, open at both ends; no production construction specification"
    for side in [-1,1]:
        barrel_side_strip(side,barrel_col,body_mat,hinge)
    lug_pts = path((25,95.2), [
        ((33,93),(48,92),(58,88)), ((64,84),(74,84),(78,90)),
        ((81,94),(78,97.5),(73,97.5)), ((56,97.5),(37,97.5),(25,97.3)),
        ((24,97.0),(24,96.0),(25,95.2)),
    ],10)
    lug=prism("Barrel_underlug",lug_pts,-5.35,5.35,barrel_col,steel,hinge,.55)
    hole= disk("Hinge_pin_bore_source",2.6,28,"Y",(75,0,94),cuts,None,hinge,radius=0)
    boolean(lug,hole,"Through_hinge_pin")
    for side in [-1,1]:
        bolt("Main_hinge_head_"+str(side),75,94,side*10.5,3.15,small_col,steel,root,True)
        bolt("Frame_cross_pin_A_"+str(side),1,86,side*10.5,2.25,small_col,steel,root)
        bolt("Frame_cross_pin_B_"+str(side),24,86,side*10.5,2.25,small_col,steel,root)
    # Казённая площадка появляется при раскрытии; начинка — только видимые художественные детали.
    breech=disk("Breech_face",13.15,2.0,"X",(20.7,0,112),frame_col,steel,root,radius=.25)
    disk("Breech_face_pin",1.2,.23,"X",(21.85,0,112),frame_col,steel,root,radius=.05)
    eject=prism("Visible_extractor_tab",round_rect(22.4,24.1,96.9,98.2,.3),
                -3.0,3.0,barrel_col,steel,hinge,.15)
    eject["simplification"]="Exterior visual tab, no internal spring or working mechanism"

    grip_pts=path((-28,98),[
        ((-35,98),(-48,85),(-56,71)), ((-64,58),(-74,36),(-76,24)),
        ((-80,11),(-67,5),(-57,5)), ((-54,7),(-56,16),(-52,30)),
        ((-48,47),(-34,57),(-20,59)), ((-12,60),(-8,59),(-8,65)),
        ((-8,75),(-13,89),(-19,94)), ((-21,96),(-25,99),(-28,98)),
    ],10)
    for side in [-1,1]:
        panel=prism("Grip_panel_thin_"+str(side),grip_pts,side*10.05,side*12.05,
                    grip_col,dark,root,.22)
        recalc(panel)
        panel["visual_thickness_mm"]=2.0
        # Глубина винта и тонкий буртик читаются сбоку; поверхность пока без текстур.
        recess=disk("Grip_screw_recess_source_"+str(side),3.8,2.2,"Y",
                    (-61,side*12.5,27),cuts,None,root,radius=0)
        boolean(panel,recess,"Countersink_for_grip_screw")
        bolt("Grip_screw_"+str(side),-61,27,side*11.95,2.65,grip_col,steel,root,True)

    trig_pivot=empty("PIVOT_Trigger",small_col,(9,0,74),root)
    driver(trig_pivot,"trigger_press",-.17)
    trig_pts=path((10,76),[
        ((12,77),(15,76),(15,72)), ((12,64),(11,56),(17,48)),
        ((19,46),(17,44),(14,46)), ((6,50),(4,59),(7,67)),
        ((8,72),(8,75),(10,76)),
    ],10)
    prism("Trigger_curved_metal",trig_pts,-3.3,3.3,small_col,steel,trig_pivot,.5)

    hammer_pivot=empty("PIVOT_Hammer",small_col,(-9,0,106),root)
    driver(hammer_pivot,"hammer_cock",-.34)
    hammer_pts=path((-5,106),[
        ((-7,110),(-14,114),(-18,122)), ((-20,125),(-22,126),(-24,123)),
        ((-31,115),(-38,111),(-43,111)), ((-47,112),(-47,108),(-45,106)),
        ((-35,105),(-31,105),(-25,109)), ((-22,105),(-19,102),(-17,99)),
        ((-12,99),(-7,101),(-5,106)),
    ],8)
    hammer=prism("Hammer_exterior_profile",hammer_pts,-4.2,4.2,small_col,steel,
                 hammer_pivot,.3)
    # Вырезы под палец встроены в рычаг и следуют его pivot.
    for i in range(8):
        x=-42.4+i*2.0
        z=111 + max(0,(x+35))*.34
        notch=prism("Hammer_thumb_notch_source_"+str(i),
                    [(x-.3,z-.3),(x+.4,z-.3),(x+.4,z+2),(x-.3,z+2)],
                    -5.2,5.2,cuts,None,hammer_pivot)
        boolean(hammer,notch,"Thumb_serration_"+str(i))
    latch=empty("PIVOT_Breech_latch",small_col,(19,0,120),root)
    driver(latch,"latch_release",.16)
    lathe("Latch_rear_crossbar",[(17.2,2.3),(18,2.7),(19.2,2.7),(20,2.3)],"Z",
          (19,0,104),small_col,steel,latch,64)
    for side in [-1,1]:
        lever_pts=round_rect(16.9,20.8,114.5,124.1,1.0)
        prism("Breech_latch_ear_"+str(side),lever_pts,side*13.2,side*15.4,
              small_col,steel,latch,.35)
    empty("SOCKET_Muzzle",barrel_col,(114.8,0,112),hinge,.004)
    empty("SOCKET_Cartridge_axis",barrel_col,(23,0,112),hinge,.004)
    empty("SOCKET_Grip_owner_pose",frame_col,(-39,0,59),root,.008)
    return base


def build_cartridge(name, color_mat, x, y):
    col=collection(name)
    root=empty("CTRL_"+name,col,(x,y,0))
    root["type"]="red_illumination" if "Red" in name else "green_airdrop"
    root["author"]="Codex"
    shellmat=bpy.data.materials[color_mat]
    base=bpy.data.materials["CHECK_Cartridge_metal_head"]
    profile=[(9.0,12.25),(10,12.5),(59.8,12.5),(61,12.1),
             (61,11.1),(60,11.2),(11,11.2),(9,11.4)]
    sleeve=lathe(name+"_colored_sleeve",profile,"Z",(x,y,0),col,shellmat,root,128)
    # Небольшое завальцованное устье с видимым восьмилучевым декоративным crimp.
    disk(name+"_mouth_closure",11.15,.5,"Z",(x,y,60.7),col,shellmat,root,radius=.12)
    for i in range(8):
        a=2*math.pi*i/8
        pts=[]
        for r, da in [(1.2,-.02),(10.7,-.01),(10.7,.01),(1.2,.02)]:
            pts.append((x+r*math.cos(a+da),y+r*math.sin(a+da),61.02))
        # Складка — закрытая тонкая призма, без плавающих открытых плоскостей.
        verts=pts+[(px,py,pz+.12) for px,py,pz in pts]
        faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        fold=mesh(name+"_crimp_fold_"+str(i),verts,faces,col,shellmat,root)
        bevel(fold,.008,3)
    metal_profile=[(0,12.7),(.35,13.5),(1.65,13.5),(2.1,12.7),
                   (9.5,12.7),(10.2,12.4),(10.2,11.95),(1.7,11.95)]
    lathe(name+"_metal_head_rim",metal_profile,"Z",(x,y,0),col,base,root,128)
    disk(name+"_head_face",12.1,1.0,"Z",(x,y,.5),col,base,root,radius=.18)
    lathe(name+"_primer_ring",[(.01,3.6),(.12,3.85),(.31,3.6),(.31,2.95),(.01,2.95)],
          "Z",(x,y,0),col,base,root,80)
    disk(name+"_primer",2.85,.18,"Z",(x,y,-.015),col,
         bpy.data.materials["CHECK_Exposed_steel"],root,radius=.06)
    return col


def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def studio():
    scene=bpy.context.scene
    col=collection("80_Review_studio")
    world=bpy.data.worlds.new("Neutral_review_world")
    world.use_nodes=True
    next(n for n in world.node_tree.nodes if n.type=="BACKGROUND").inputs[0].default_value=(.18,.18,.18,1)
    next(n for n in world.node_tree.nodes if n.type=="BACKGROUND").inputs[1].default_value=.45
    scene.world=world
    for name,loc,power,size in [("Key_softbox",(.12,-.26,.38),2.5,.3),
                                ("Fill_softbox",(-.15,.22,.24),1.5,.28),
                                ("Rim_softbox",(.3,.14,.3),2.0,.24)]:
        data=bpy.data.lights.new(name,"AREA")
        data.energy=power
        data.shape="DISK"
        data.size=size
        obj=bpy.data.objects.new(name,data)
        col.objects.link(obj)
        obj.location=loc
        aim(obj,(.035,0,.07))
    cam=bpy.data.cameras.new("Review_camera")
    camera=bpy.data.objects.new("Review_camera",cam)
    col.objects.link(camera)
    camera.location=(.24,-.38,.24)
    cam.type="ORTHO"
    cam.ortho_scale=.31
    cam.clip_start=.0005
    cam.clip_end=10
    aim(camera,(.03,0,.065))
    scene.camera=camera
    scene.render.engine="CYCLES"
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1100
    scene.render.resolution_y=850
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.view_settings.view_transform="AgX"
    scene.render.image_settings.color_mode="RGB"
    scene.render.filepath=str(OUT/"previews"/"01_three_quarter.png")
    return col


def setup_viewport():
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    root=bpy.data.objects["CTRL_Launcher"]
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                space=area.spaces.active
                space.clip_start=.0005
                space.clip_end=100
                space.shading.type="MATERIAL"
                space.overlay.show_extras=False
                space.region_3d.view_distance=.37
                space.region_3d.view_location=Vector((.035,0,.065))
                space.region_3d.view_rotation=bpy.data.objects["Review_camera"].rotation_euler.to_quaternion()


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system="METRIC"
    scene.unit_settings.scale_length=1.0
    scene.unit_settings.length_unit="MILLIMETERS"
    material("CHECK_Metal_body_unpainted",(.35,.36,.37),.55,.5)
    material("CHECK_Exposed_steel",(.26,.28,.3),.8,.36)
    material("CHECK_Thin_black_plastic",(.033,.035,.039),0,.65)
    material("CHECK_Red_illumination",(.55,.012,.018),0,.62)
    material("CHECK_Green_airdrop",(.015,.23,.045),0,.62)
    material("CHECK_Cartridge_metal_head",(.42,.3,.12),.75,.42)
    material("COLOR_STUDY_Matte_bright_red",(.62,.014,.018),.12,.67)
    build_launcher()
    build_cartridge("02_Cartridge_Red_Illumination","CHECK_Red_illumination",143,-2)
    build_cartridge("03_Cartridge_Green_Airdrop","CHECK_Green_airdrop",181,0)
    studio()
    setup_viewport()
    text=bpy.data.texts.new("00_README_RU")
    text.write("Ракетница — Codex, геометрия v01\nОснова: компактный силуэт фото 8. Корпус — металл, накладки — 2 мм пластик.\n"
               "CTRL_Launcher: open_degrees (0..48), hammer_cock, trigger_press, latch_release (0..1).\n"
               "Драйверы показывают художественные движения отдельных деталей. Полный механизм не моделировался.\n"
               "Красный = осветительный патрон. Зелёный = вызов airdrop. Это имена/цвета ассетов, игровая логика не менялась.\n"
               "Финиш позже: яркий матовый красный, потёртости до металла; UCUPaint после одобрения геометрии.\n"
               "Оси: X к дульному срезу, Y поперёк, Z вверх; 1 единица = 1 метр.\n"
               "80_Review_studio — освещение. 90_Construction_cutters — скрытые источники вырезов.\n")
    MASTER.parent.mkdir(parents=True,exist_ok=True)
    (OUT/"previews").mkdir(parents=True,exist_ok=True)
    (OUT/"checks").mkdir(parents=True,exist_ok=True)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    print("CODEX_MASTER",str(MASTER),flush=True)


def set_gpu():
    try:
        prefs=bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type="OPTIX"
        prefs.get_devices()
        found=False
        for dev in prefs.devices:
            dev.use=dev.type!="CPU"
            found=found or dev.use
        if found:
            bpy.context.scene.cycles.device="GPU"
    except Exception as err:
        print("GPU fallback",str(err),flush=True)


def render_view(name,loc,target,scale,open_deg=0,only=None,red=False,res=(1100,850)):
    scene=bpy.context.scene
    ctrl=bpy.data.objects.get("CTRL_Launcher")
    if ctrl:
        ctrl["open_degrees"]=open_deg
        ctrl.update_tag()
    for colname in ["01_Launcher_Codex","02_Cartridge_Red_Illumination","03_Cartridge_Green_Airdrop"]:
        col=bpy.data.collections.get(colname)
        if col:
            col.hide_render=only is not None and colname not in only
    mat=bpy.data.materials["CHECK_Metal_body_unpainted"]
    shader=next(n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value=(.62,.014,.018,1) if red else (.35,.36,.37,1)
    shader.inputs["Metallic"].default_value=.12 if red else .55
    shader.inputs["Roughness"].default_value=.67 if red else .5
    bpy.context.view_layer.update()
    cam=scene.camera
    cam.location=loc
    aim(cam,target)
    cam.data.type="ORTHO"
    cam.data.ortho_scale=scale
    scene.render.resolution_x,scene.render.resolution_y=res
    scene.render.filepath=str(OUT/"previews"/(name+".png"))
    print("RENDER_BEGIN",name,flush=True)
    bpy.ops.render.render(write_still=True)
    print("RENDER_DONE",name,flush=True)


def render():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    set_gpu()
    pistol=["01_Launcher_Codex"]
    render_view("01_three_quarter",(.24,-.38,.24),(.042,0,.067),.32)
    render_view("02_left_profile",(.016,-.5,.065),(.016,0,.065),.228,only=pistol)
    render_view("03_right_profile",(.016,.5,.065),(.016,0,.065),.228,only=pistol)
    render_view("04_open_breech",(.22,-.30,.23),(.018,0,.084),.238,open_deg=48,only=pistol)
    # Полный ствол показывается отдельно, чтобы казённая площадка закрытой ракетницы не скрывала канал.
    for colname in ["Frame_and_metal_body","Thin_plastic_grip_panels","Levers_trigger_and_fasteners"]:
        bpy.data.collections[colname].hide_render=True
    render_view("05_bore_muzzle",(.34,0,.1118),(.068,0,.112),.054,only=pistol,res=(800,800))
    render_view("06_bore_rear",(-.1,0,.112),(.075,0,.112),.055,only=pistol,res=(800,800))
    for colname in ["Frame_and_metal_body","Thin_plastic_grip_panels","Levers_trigger_and_fasteners"]:
        bpy.data.collections[colname].hide_render=False
    render_view("07_grip_and_guard",(-.13,-.23,.052),(-.023,0,.051),.127,only=pistol)
    render_view("08_top_joints",(.03,-.11,.37),(.015,0,.09),.225,only=pistol)
    render_view("09_cartridges",(.22,-.18,.135),(.162,0,.031),.107,
                only=["02_Cartridge_Red_Illumination","03_Cartridge_Green_Airdrop"])
    render_view("10_color_study_only",(.22,-.32,.205),(.045,0,.067),.315,red=True)
    render_view("11_open_chamber_rear",(-.14,-.23,.235),(.034,0,.127),.17,open_deg=48,only=pistol)


def parts():
    for keep,folder,filename in [
        ("02_Cartridge_Red_Illumination","cartridge_red","cartridge_red_illumination_codex_v01.blend"),
        ("03_Cartridge_Green_Airdrop","cartridge_green","cartridge_green_airdrop_codex_v01.blend")]:
        bpy.ops.wm.open_mainfile(filepath=str(MASTER))
        for name in ["01_Launcher_Codex","02_Cartridge_Red_Illumination","03_Cartridge_Green_Airdrop"]:
            if name!=keep:
                col=bpy.data.collections[name]
                for obj in list(col.all_objects):
                    bpy.data.objects.remove(obj,do_unlink=True)
                bpy.data.collections.remove(col)
        root=bpy.data.objects["CTRL_"+keep]
        root.location=(0,0,0)
        bpy.data.texts["00_README_RU"].clear()
        bpy.data.texts["00_README_RU"].write("Патрон — Codex, геометрия v01\n"
            + ("Красный: осветительный.\n" if "Red" in keep else "Зелёный: вызов airdrop.\n")
            + "Отдельный ассет с origin в центре донца; ось Z к устью.\n"
            + "Размеры художественного игрового предмета по фото 7, не производственный чертёж.\n"
            + "Проверочные простые материалы; производственные UV и текстуры ещё не созданы.\n")
        bpy.context.view_layer.update()
        camera=bpy.context.scene.camera
        camera.location=(.08,-.13,.095)
        camera.data.ortho_scale=.085
        aim(camera,(0,0,.031))
        bpy.context.view_layer.objects.active=root
        root.select_set(True)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=="VIEW_3D":
                    area.spaces.active.region_3d.view_location=(0,0,.031)
                    area.spaces.active.region_3d.view_distance=.13
        filepath=OUT/"models"/folder/filename
        filepath.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(filepath))
        print("CODEX_PART",str(filepath),flush=True)


def evaluated_bounds(objects):
    dg=bpy.context.evaluated_depsgraph_get()
    coords=[]
    for obj in objects:
        if obj.type!="MESH":
            continue
        eval_obj=obj.evaluated_get(dg)
        data=eval_obj.to_mesh()
        coords.extend(eval_obj.matrix_world@v.co for v in data.vertices)
        eval_obj.to_mesh_clear()
    return {"min_mm":[min(p[i] for p in coords)*1000 for i in range(3)],
            "max_mm":[max(p[i] for p in coords)*1000 for i in range(3)],
            "dimensions_mm":[(max(p[i] for p in coords)-min(p[i] for p in coords))*1000 for i in range(3)]}


def verify():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    objects=[o for o in bpy.data.collections["01_Launcher_Codex"].all_objects
             if not any(c.name=="90_Construction_cutters" for c in o.users_collection)]
    report={"file":str(MASTER),"blender":bpy.app.version_string,
            "pistol_closed":evaluated_bounds(objects),"poses":[],"standalone_files":[]}
    ctrl=bpy.data.objects["CTRL_Launcher"]
    for deg in [0,24,48]:
        ctrl["open_degrees"]=deg
        ctrl.update_tag()
        bpy.context.view_layer.update()
        parent=bpy.data.objects["PIVOT_Barrel_hinge"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        child=bpy.data.objects["SOCKET_Muzzle"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        report["poses"].append({"open_degrees":deg,
                               "evaluated_hinge_world_deg":[math.degrees(a) for a in parent.matrix_world.to_euler()],
                               "muzzle_world_mm":[v*1000 for v in child.matrix_world.translation]})
    for colname in ["02_Cartridge_Red_Illumination","03_Cartridge_Green_Airdrop"]:
        report[colname]=evaluated_bounds(bpy.data.collections[colname].all_objects)
    closed_topology={"max_boundary_edges":0,"max_overfull_edges":0,
                     "max_wire_edges":0,"max_loose_vertices":0,
                     "max_nonfinite_vertices":0,"max_zero_area_faces":0}
    assembly=["Frame_and_metal_body","Barrel_break_open","Thin_plastic_grip_panels",
              "Levers_trigger_and_fasteners"]
    rays=[]
    for y,z in [(0,0),(6,0),(-6,0),(0,6),(0,-6),(9,9),(-9,9),(9,-9),(-9,-9),
                (12.5,0),(-12.5,0),(0,12.5),(0,-12.5)]:
        rays.extend([{"start":[22.8,y,112+z],"end":[116,y,112+z]},
                     {"start":[116,y,112+z],"end":[22.8,y,112+z]}])
    config={"schema_version":1,"description":"Visual geometry acceptance only; no real mechanism specification",
            "targets":[{"id":"launcher_geometry","collections":assembly,"finite_transforms":True,
                        "dimensions_mm":{"expected":[198.1,33.16,129.6],"tolerance_mm":.15},
                        "topology":{"base":closed_topology,"evaluated":closed_topology}},
                       {"id":"cartridges_geometry","collections":["02_Cartridge_Red_Illumination",
                                                                    "03_Cartridge_Green_Airdrop"],
                        "finite_transforms":True,"topology":{"base":closed_topology,"evaluated":closed_topology}}],
            "passages":[{"id":"barrel_both_directions_26_rays","collections":["Barrel_break_open"],
                         "frame":1,"unit":"mm","samples":rays,"max_hits":0}]}
    (OUT/"checks"/"audit-config.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    for fp in (OUT/"models").glob("cartridge*/*.blend"):
        bpy.ops.wm.open_mainfile(filepath=str(fp))
        objs=[o for o in bpy.context.scene.objects if o.type=="MESH"]
        report["standalone_files"].append({"file":str(fp),"bounds":evaluated_bounds(objs)})
    (OUT/"checks"/"reopen_dimensions_poses.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CODEX_REOPEN_CHECK",json.dumps(report,ensure_ascii=False),flush=True)


if MODE=="build":
    build()
elif MODE=="render":
    render()
elif MODE=="parts":
    parts()
elif MODE=="verify":
    verify()
else:
    raise ValueError(MODE)
