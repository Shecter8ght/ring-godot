# ВСС-М v8: варианты основы приклада (wood_veneer_bake.py) на выбор владельцу. Каждый вариант — копия приклада со своим
# материалом в своей коллекции «Приклад_…»; коллекции переключаются в Outliner, «0 сейчас» — прежний стек Painter.
# Основа показана под простым полуматовым лаком, без износа, грязи и следов рук: их потом кладут слоями в Painter.
#   file:   blender --background --factory-startup <ВСС-М_v8_студия.blend> --python tools/vss_m_v8/wood_variants.py
#           -- file <папка карт> <выход.blend> <вариант,вариант>
#   render: blender --background --factory-startup <файл со сценой> --python tools/vss_m_v8/wood_variants.py
#           -- render <папка карт> <вариант> <папка снимков> <вид,вид> [ширина] [сэмплы]
import os
import sys
import bpy
from mathutils import Vector

STOCK = "Wood_stock_v8"
TITLES = {"A_dub_volnistyi": "A дуб, волнистое волокно", "B_yasen": "B ясень, прямое волокно",
          "C_krasnyi_dub": "C красный дуб, дуги"}
VIEWS = {
    "stock": ((120, -420, 60), (220, 0, -40), 45),
    "comb_top": ((180, -90, 130), (230, 0, 0), 45),
    "stock_rear": ((40, -150, 40), (90, 0, -30), 45),
    "window": ((150, -115, -25), (250, 0, -72), 40),
    "far": ((420, -900, 120), (300, 0, -40), 40),
}


def variant_material(name, maps, var):
    """Основа: цвет из карты, рельеф волокна, полуматовый лак (в порах матовее)."""
    m = bpy.data.materials.new("Wood_" + name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = bpy.data.images.load(f"{maps}/{var}_color.png", check_existing=True)
    hgt = nt.nodes.new("ShaderNodeTexImage")
    hgt.image = bpy.data.images.load(f"{maps}/{var}_height.png", check_existing=True)
    hgt.image.colorspace_settings.name = "Non-Color"
    for t in (col, hgt):
        nt.links.new(nt.nodes.new("ShaderNodeUVMap").outputs[0], t.inputs["Vector"])
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    r = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(hgt.outputs["Color"], r.inputs["Value"])
    r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = 0.2, 0.7
    r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = 0.55, 0.36
    nt.links.new(r.outputs[0], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.00012
    nt.links.new(hgt.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    for img in (col.image, hgt.image):
        img.pack()
    return m


def make_file(maps, out, variants):
    src = bpy.data.objects[STOCK]
    parent_coll = src.users_collection[0]
    cur = bpy.data.collections.new("Приклад_0 сейчас (Painter)")
    bpy.context.scene.collection.children.link(cur)
    parent_coll.objects.unlink(src)
    cur.objects.link(src)
    for v in variants:
        c = bpy.data.collections.new("Приклад_" + TITLES.get(v, v))
        bpy.context.scene.collection.children.link(c)
        o = src.copy()
        o.data = src.data.copy()
        o.name = STOCK + "_" + v
        o.data.materials.clear()
        o.data.materials.append(variant_material(v, maps, v))
        c.objects.link(o)
    # по умолчанию виден первый вариант, остальные выключены (глазом и в рендере)
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.name.startswith("Приклад_"):
            vis = lc.name.startswith("Приклад_A")
            lc.hide_viewport = not vis
            lc.collection.hide_render = not vis
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


def render(maps, var, out, views, w=1280, spp=96):
    sc = bpy.context.scene
    o = bpy.data.objects[STOCK]
    if var != "0":
        o.data.materials.clear()
        o.data.materials.append(variant_material(var, maps, var))
    if os.environ.get("LOOK_HDRI"):
        wd = bpy.data.worlds.new("LookHDRI")
        sc.world = wd
        wd.use_nodes = True
        nt = wd.node_tree
        nt.nodes.clear()
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(os.environ["LOOK_HDRI"], check_existing=True)
        bg = nt.nodes.new("ShaderNodeBackground")
        wo = nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(env.outputs[0], bg.inputs[0])
        nt.links.new(bg.outputs[0], wo.inputs[0])
        for ob in bpy.data.objects:
            if ob.type == "LIGHT":
                ob.hide_render = True
        sc.view_settings.exposure = 0.0
    sc.cycles.samples = spp
    sc.cycles.denoising_use_gpu = False
    sc.render.resolution_x = w
    sc.render.resolution_y = int(w * 0.5625)
    cd = bpy.data.cameras.new("VarCam")
    cam = bpy.data.objects.new("VarCam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    os.makedirs(out, exist_ok=True)
    for v in views:
        eye, tgt, lens = VIEWS[v]
        cam.location = Vector(eye) * 0.001
        cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens
        cd.clip_start = 0.01
        sc.render.filepath = os.path.join(out, f"{var}_{v}.png")
        bpy.ops.render.render(write_still=True)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "file":
        make_file(a[1], a[2], a[3].split(","))
    else:
        render(a[1], a[2], a[3], a[4].split(","), *(int(x) for x in a[5:7]))


main()
