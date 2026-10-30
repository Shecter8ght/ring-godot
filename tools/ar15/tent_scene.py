# AR-15 «ГРАНЬ-15»: окружение рендеров для владельца — армейская палатка, материалы, простые сетки, свет
# (tools/ar15/render_table.py). Всё — свои модели; текстуры — CC0 Poly Haven, уже в проекте: лён (npc_kit), фанера
# (assets/textures), небо (assets/sky). Модуль без побочных действий: функции вызывает сцена.
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = "E:/Games/RING-godot"
LINEN = ROOT + "/_asset_src/npc_kit/tex/rough_linen/rough_linen_"
PLY = ROOT + "/assets/textures/plywood/"
PLANKS = ROOT + "/assets/textures/wood_planks_grey/"
FOREST = ROOT + "/assets/textures/forest_floor/"
MASKS = ROOT + "/_asset_src/ar15/tex/wear/masks/"
HDRI = ROOT + "/assets/sky/kloppenheim_06_puresky.hdr"


def img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def _mapping(nt, scale):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    return mp


def mat_canvas(name, tint, scale, translucent=0.0, nstrength=0.8):
    """Брезент: полотняное переплетение и шероховатость — rough_linen (Poly Haven, CC0), цвет — серый рисунка × тон;
    у палатки — просвет солнца сквозь ткань."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bs = N.new("ShaderNodeBsdfPrincipled")
    mp = _mapping(nt, scale)
    diff = N.new("ShaderNodeTexImage"); diff.image = img(LINEN + "diff_2k.jpg")
    rough = N.new("ShaderNodeTexImage"); rough.image = img(LINEN + "rough_2k.png", True)
    nor = N.new("ShaderNodeTexImage"); nor.image = img(LINEN + "nor_gl_2k.png", True)
    for t in (diff, rough, nor):
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    bw = N.new("ShaderNodeRGBToBW")
    Lk.new(diff.outputs["Color"], bw.inputs["Color"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    Lk.new(bw.outputs["Val"], mix.inputs[6])
    mix.inputs[7].default_value = (*tint, 1.0)
    Lk.new(mix.outputs[2], bs.inputs["Base Color"])
    Lk.new(rough.outputs["Color"], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nstrength
    Lk.new(nor.outputs["Color"], nm.inputs["Color"])
    Lk.new(nm.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["Specular IOR Level"].default_value = 0.3
    if translucent > 0:
        tr = N.new("ShaderNodeBsdfTranslucent")
        tr.inputs["Color"].default_value = (tint[0] * 2.2, tint[1] * 2.1, tint[2] * 1.7, 1.0)
        Lk.new(nm.outputs["Normal"], tr.inputs["Normal"])
        ms = N.new("ShaderNodeMixShader"); ms.inputs[0].default_value = translucent
        Lk.new(bs.outputs[0], ms.inputs[1]); Lk.new(tr.outputs[0], ms.inputs[2])
        Lk.new(ms.outputs[0], out.inputs["Surface"])
    else:
        Lk.new(bs.outputs[0], out.inputs["Surface"])
    return m


def mat_wood(name, folder, scale, value=0.6):
    """Дерево по фото Poly Haven (albedo / arm / normal): фанера стола, доски пола."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = N["Principled BSDF"]
    mp = _mapping(nt, scale)
    al = N.new("ShaderNodeTexImage"); al.image = img(folder + "albedo.jpg")
    arm = N.new("ShaderNodeTexImage"); arm.image = img(folder + "arm.jpg", True)
    nor = N.new("ShaderNodeTexImage"); nor.image = img(folder + "normal.jpg", True)
    for t in (al, arm, nor):
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    hue = N.new("ShaderNodeHueSaturation"); hue.inputs["Value"].default_value = value
    Lk.new(al.outputs["Color"], hue.inputs["Color"])
    Lk.new(hue.outputs["Color"], bs.inputs["Base Color"])
    sep = N.new("ShaderNodeSeparateColor")
    Lk.new(arm.outputs["Color"], sep.inputs["Color"])
    Lk.new(sep.outputs["Green"], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap")
    Lk.new(nor.outputs["Color"], nm.inputs["Color"])
    Lk.new(nm.outputs["Normal"], bs.inputs["Normal"])
    return m


def mat_plain(name, color, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*color, 1.0)
    bs.inputs["Metallic"].default_value = metal
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Coat Weight"].default_value = coat
    return m


def mat_emit(name, color, strength):
    m = mat_plain(name, color, 0.5)
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Emission Color"].default_value = (*color, 1.0)
    bs.inputs["Emission Strength"].default_value = strength
    return m


def mat_stained(name, base, stains):
    """Ткань (ветошь, патчи) с пятнами нагара и масла: рисунок пятен — фото-маски CC0 (wear_masks.py), не шум.
    stains — [(маска, масштаб, цвет, сила)]."""
    m = mat_canvas(name, base, 6.0, nstrength=1.2)
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = [n for n in N if n.type == "BSDF_PRINCIPLED"][0]
    col = bs.inputs["Base Color"].links[0].from_socket
    for k, (mask, scale, color, amount) in enumerate(stains):
        mp = _mapping(nt, scale)
        mp.inputs["Location"].default_value = (0.37 * k, 0.61 * k, 0.0)
        t = N.new("ShaderNodeTexImage"); t.image = img(MASKS + mask, True)
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
        f = N.new("ShaderNodeMath"); f.operation = "MULTIPLY"; f.inputs[1].default_value = amount
        Lk.new(t.outputs["Color"], f.inputs[0])
        mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        Lk.new(f.outputs[0], mix.inputs[0])
        Lk.new(col, mix.inputs[6])
        mix.inputs[7].default_value = (*color, 1.0)
        col = mix.outputs[2]
    Lk.new(col, bs.inputs["Base Color"])
    return m


def overlay(m, mask, scale, color, amount, rough=0.0, loc=(0.0, 0.0)):
    """Пятна поверх материала по фото-маске CC0 (масло, грязь): цвет — умножением, блеск — сдвигом шероховатости."""
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = [n for n in N if n.type == "BSDF_PRINCIPLED"][0]
    mp = _mapping(nt, scale)
    mp.inputs["Location"].default_value = (loc[0], loc[1], 0.0)
    t = N.new("ShaderNodeTexImage"); t.image = img(MASKS + mask, True)
    Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    f = N.new("ShaderNodeMath"); f.operation = "MULTIPLY"; f.inputs[1].default_value = amount
    Lk.new(t.outputs["Color"], f.inputs[0])
    src = bs.inputs["Base Color"].links[0].from_socket
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    Lk.new(f.outputs[0], mix.inputs[0])
    Lk.new(src, mix.inputs[6])
    mix.inputs[7].default_value = (*color, 1.0)
    Lk.new(mix.outputs[2], bs.inputs["Base Color"])
    if rough:
        rl = bs.inputs["Roughness"].links
        r0 = rl[0].from_socket if rl else None
        add = N.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"; add.inputs[1].default_value = rough
        Lk.new(f.outputs[0], add.inputs[0])
        if r0 is not None:
            Lk.new(r0, add.inputs[2])
        else:
            add.inputs[2].default_value = bs.inputs["Roughness"].default_value
        cl = N.new("ShaderNodeClamp")
        Lk.new(add.outputs[0], cl.inputs[0])
        Lk.new(cl.outputs[0], bs.inputs["Roughness"])
    return m


# ── сетки ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def obj_from(coll, name, verts, faces, mat, uv=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        loop_uv = np.array([uv[li] for poly in me.polygons for li in poly.vertices], dtype=np.float32)
        layer.data.foreach_set("uv", loop_uv.ravel())
    me.update()
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    if mat is not None:
        o.data.materials.append(mat)
    coll.objects.link(o)
    return o


def grid(nx, ny):
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            k = j * nx + i
            faces.append((k, k + 1, k + nx + 1, k + nx))
    return faces


def tube(coll, name, p0, p1, r, mat, seg=24, r1=None):
    """Цилиндр (конус при r1) с развёрткой по длине и окружности."""
    p0, p1 = Vector(p0), Vector(p1)
    q = (p1 - p0).to_track_quat("Z", "Y")
    L = (p1 - p0).length
    verts, faces, uv = [], [], []
    for e, (p, rr) in enumerate(((p0, r), (p1, r if r1 is None else r1))):
        for s in range(seg + 1):
            ang = 2 * math.pi * s / seg
            verts.append(p + q @ Vector((rr * math.cos(ang), rr * math.sin(ang), 0.0)))
            uv.append((s / seg * 2 * math.pi * r, e * L))
    n = seg + 1
    for s in range(seg):
        faces.append((s, s + 1, n + s + 1, n + s))
    verts.append(p0); uv.append((0, 0))
    verts.append(p1); uv.append((0, L))
    c0, c1 = len(verts) - 2, len(verts) - 1
    for s in range(seg):
        faces.append((c0, s + 1, s))
        faces.append((c1, n + s, n + s + 1))
    return obj_from(coll, name, verts, faces, mat, uv=np.array(uv))


def lathe(coll, name, profile, mat, seg=48, at=(0, 0, 0)):
    """Тело вращения по профилю [(радиус, высота)] вокруг Z."""
    verts, faces, uv = [], [], []
    for j, (r, z) in enumerate(profile):
        for s in range(seg + 1):
            ang = 2 * math.pi * s / seg
            verts.append((at[0] + r * math.cos(ang), at[1] + r * math.sin(ang), at[2] + z))
            uv.append((s / seg, j / (len(profile) - 1)))
    n = seg + 1
    for j in range(len(profile) - 1):
        for s in range(seg):
            k = j * n + s
            faces.append((k, k + 1, k + n + 1, k + n))
    return obj_from(coll, name, verts, faces, mat, uv=np.array(uv))


def box(coll, name, center, size, mat, bevel=0.0, rot_z=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.rotation_euler = (0, 0, rot_z)
    for c in o.users_collection:
        c.objects.unlink(o)
    coll.objects.link(o)
    if mat is not None:
        o.data.materials.append(mat)
    if bevel:
        b = o.modifiers.new("Скругление", "BEVEL"); b.width = bevel; b.segments = 3
    return o


# ── палатка ──────────────────────────────────────────────────────────────────────────────────────────────────────────
# Владелец 30.10: «на кадрах, где видно стол и пространство за ним, его тоже нужно сделать реалистичным, а то как будто
# стол в параллельной вселенной». Поэтому палатка обжитая: брезент со швами полотнищ, разнотоном и грязью у низа,
# каркас (стойки по стенам, стропила, конёк), окна с сеткой, полог на входе со щелью на улицу, за ней — земля; внутри —
# раскладушки со спальниками, печка с трубой, ящики, цинки, канистра, каска, рюкзак, стул у стола, лампа над столом.
TX, TY, WALL, RIDGE = 2.6, 2.1, 1.7, 2.8
DOOR = (-0.55, 0.45, 1.85)           # проём во входной стене (y = −TY): x0, x1, верх
DOOR_GAP = 0.22                      # щель у правого края проёма — полог не до конца
WINDOWS = [(-0.45, 0.45, 1.0, 1.42, 1), (-1.65, -0.95, 1.0, 1.42, 1)]    # окна в дальней стене: x0, x1, z0, z1, сторона


def mat_tent(name, tint, translucent):
    """Брезент палатки: mat_canvas + разнотон крупными облаками (фото-маска), швы полотнищ (тёмные полосы по развёртке
    через 1,3 м), грязь и сырость у низа стен."""
    m = mat_canvas(name, tint, 2.5, translucent=translucent, nstrength=1.4)
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = [n for n in N if n.type == "BSDF_PRINCIPLED"][0]
    col = bs.inputs["Base Color"].links[0].from_socket
    mp = _mapping(nt, 0.35)
    cl = N.new("ShaderNodeTexImage"); cl.image = img(MASKS + "cloudy.png", True)
    Lk.new(mp.outputs["Vector"], cl.inputs["Vector"])
    var = N.new("ShaderNodeMapRange")
    var.inputs["To Min"].default_value, var.inputs["To Max"].default_value = 0.82, 1.12
    Lk.new(cl.outputs["Color"], var.inputs["Value"])
    m1 = N.new("ShaderNodeMix"); m1.data_type = "RGBA"; m1.blend_type = "MULTIPLY"; m1.inputs[0].default_value = 1.0
    Lk.new(col, m1.inputs[6])
    cv = N.new("ShaderNodeCombineColor")
    for i in range(3):
        Lk.new(var.outputs["Result"], cv.inputs[i])
    Lk.new(cv.outputs["Color"], m1.inputs[7])
    # швы: полотнища по 1,3 м (развёртка стены — 4 на всю длину 5,2 м)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["UV"], sep.inputs["Vector"])
    fr = N.new("ShaderNodeMath"); fr.operation = "PINGPONG"; fr.inputs[1].default_value = 0.5
    Lk.new(sep.outputs["X"], fr.inputs[0])
    seam = N.new("ShaderNodeMapRange")
    seam.inputs["From Min"].default_value, seam.inputs["From Max"].default_value = 0.004, 0.012
    seam.inputs["To Min"].default_value, seam.inputs["To Max"].default_value = 0.55, 1.0
    Lk.new(fr.outputs[0], seam.inputs["Value"])
    m2 = N.new("ShaderNodeMix"); m2.data_type = "RGBA"; m2.blend_type = "MULTIPLY"; m2.inputs[0].default_value = 1.0
    Lk.new(m1.outputs[2], m2.inputs[6])
    cs = N.new("ShaderNodeCombineColor")
    for i in range(3):
        Lk.new(seam.outputs["Result"], cs.inputs[i])
    Lk.new(cs.outputs["Color"], m2.inputs[7])
    # низ стен — грязь и сырость (по высоте в мире), рваная по фото-маске
    geo = N.new("ShaderNodeNewGeometry")
    gz = N.new("ShaderNodeSeparateXYZ")
    Lk.new(geo.outputs["Position"], gz.inputs["Vector"])
    low = N.new("ShaderNodeMapRange")
    low.inputs["From Min"].default_value, low.inputs["From Max"].default_value = 0.45, 0.02
    Lk.new(gz.outputs["Z"], low.inputs["Value"])
    gr = N.new("ShaderNodeTexImage"); gr.image = img(MASKS + "grime.png", True)
    mp2 = _mapping(nt, 1.6)
    Lk.new(mp2.outputs["Vector"], gr.inputs["Vector"])
    mx = N.new("ShaderNodeMath"); mx.operation = "MULTIPLY"
    Lk.new(low.outputs["Result"], mx.inputs[0])
    gr2 = N.new("ShaderNodeMath"); gr2.operation = "MULTIPLY_ADD"; gr2.inputs[1].default_value = 0.5
    gr2.inputs[2].default_value = 0.5
    Lk.new(gr.outputs["Color"], gr2.inputs[0])
    Lk.new(gr2.outputs[0], mx.inputs[1])
    m3 = N.new("ShaderNodeMix"); m3.data_type = "RGBA"; m3.blend_type = "MIX"
    Lk.new(mx.outputs[0], m3.inputs[0])
    Lk.new(m2.outputs[2], m3.inputs[6])
    m3.inputs[7].default_value = (0.05, 0.045, 0.03, 1.0)
    Lk.new(m3.outputs[2], bs.inputs["Base Color"])
    return m


def mat_painted(name, color, rough=0.55, metal=0.3, wear=0.35, under=(0.12, 0.11, 0.10), scale=9.0):
    """Крашеный металл (цинки, канистра, печка, каска): краска с потёртостями и грязью по фото-маскам CC0; under — что
    под краской (тёмный металл, у печки — ржавчина). Крупный рисунок при сильном износе читался мрамором (проба 30.10)."""
    m = mat_plain(name, color, rough, metal=metal)
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = N["Principled BSDF"]
    mp = _mapping(nt, scale)
    gr = N.new("ShaderNodeTexImage"); gr.image = img(MASKS + "grime.png", True)
    ch = N.new("ShaderNodeTexImage"); ch.image = img(MASKS + "chips.png", True)
    for t in (gr, ch):
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    m1 = N.new("ShaderNodeMix"); m1.data_type = "RGBA"
    f1 = N.new("ShaderNodeMath"); f1.operation = "MULTIPLY"; f1.inputs[1].default_value = wear * 0.7
    Lk.new(gr.outputs["Color"], f1.inputs[0])
    Lk.new(f1.outputs[0], m1.inputs[0])
    m1.inputs[6].default_value = (*color, 1.0)
    m1.inputs[7].default_value = (color[0] * 0.45, color[1] * 0.42, color[2] * 0.38, 1.0)
    m2 = N.new("ShaderNodeMix"); m2.data_type = "RGBA"
    f2 = N.new("ShaderNodeMath"); f2.operation = "MULTIPLY"; f2.inputs[1].default_value = wear
    Lk.new(ch.outputs["Color"], f2.inputs[0])
    Lk.new(f2.outputs[0], m2.inputs[0])
    Lk.new(m1.outputs[2], m2.inputs[6])
    m2.inputs[7].default_value = (*under, 1.0)
    Lk.new(m2.outputs[2], bs.inputs["Base Color"])
    Lk.new(f2.outputs[0], bs.inputs["Metallic"])
    return m


def build_tent(coll):
    tent_m = mat_tent("Брезент палатки", (0.17, 0.165, 0.075), 0.28)

    def surface(name, fn, nu, nv, hole=None):
        us, vs = np.linspace(0, 1, nu), np.linspace(0, 1, nv)
        U, Vv = np.meshgrid(us, vs)
        P = fn(U, Vv)
        faces = []
        for j in range(nv - 1):
            for i in range(nu - 1):
                k = j * nu + i
                if hole is not None and hole(P[j, i], P[j + 1, i + 1]):
                    continue
                faces.append((k, k + 1, k + nu + 1, k + nu))
        return obj_from(coll, name, P.reshape(-1, 3), faces, tent_m, uv=np.stack([U * 4, Vv * 2], -1).reshape(-1, 2))

    def wrinkle(P, amp):
        x = P[..., 0]
        return amp * (0.5 + 0.5 * np.cos(2 * math.pi * x / 1.3)) + 0.012 * np.sin(x * 9.0 + P[..., 2] * 4.0)

    def in_window(p0, p1):
        cx, cz = (p0[0] + p1[0]) / 2, (p0[2] + p1[2]) / 2
        return any(x0 < cx < x1 and z0 < cz < z1 for x0, x1, z0, z1, _ in WINDOWS)

    for side in (-1, 1):
        def wall(U, Vv, side=side):
            P = np.stack([-TX + 2 * TX * U, np.full_like(U, side * TY), WALL * Vv], -1)
            P[..., 1] -= side * wrinkle(P, 0.035) * np.sin(math.pi * Vv)
            return P
        if side < 0:
            hole = lambda p0, p1: DOOR[0] < (p0[0] + p1[0]) / 2 < DOOR[1] and (p0[2] + p1[2]) / 2 < DOOR[2]
        else:
            hole = in_window
        surface("Стена палатки", wall, 160, 60, hole)

        def roof(U, Vv, side=side):
            P = np.stack([-TX + 2 * TX * U, side * TY * (1 - Vv), WALL + (RIDGE - WALL) * Vv], -1)
            P[..., 2] -= wrinkle(P, 0.05) * np.sin(math.pi * Vv)
            return P
        surface("Скат крыши", roof, 120, 40)

        def gable(U, Vv, side=side):
            y = -TY + 2 * TY * U
            top = WALL + (RIDGE - WALL) * (1 - np.abs(y) / TY)
            return np.stack([np.full_like(y, side * TX), y, top * Vv], -1)
        surface("Торец палатки", gable, 80, 50)
    # полог входа: висит, у правого края — щель на улицу; скатка над проёмом
    def flap(U, Vv):
        x = DOOR[0] + (DOOR[1] - DOOR_GAP - DOOR[0]) * U
        z = DOOR[2] * Vv
        y = -TY + 0.015 + 0.03 * np.sin(U * 9.0 + Vv * 2.0) * (1 - Vv) + 0.06 * U * (1 - Vv) ** 2
        return np.stack([x, y, z], -1)
    surface("Полог входа", flap, 30, 40)
    tube(coll, "Скатанный полог", (DOOR[0] - 0.08, -TY + 0.03, DOOR[2] + 0.05), (DOOR[1] + 0.08, -TY + 0.03, DOOR[2] + 0.05),
         0.05, tent_m)
    # окна: сетка (полупрозрачная, тёмная) и скатанные клапаны над ними
    net = bpy.data.materials.new("Москитная сетка")
    net.use_nodes = True
    bsn = net.node_tree.nodes["Principled BSDF"]
    bsn.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
    bsn.inputs["Alpha"].default_value = 0.55
    for x0, x1, z0, z1, side in WINDOWS:
        y = side * (TY - 0.005)
        obj_from(coll, "Сетка окна", [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [(0, 1, 2, 3)], net, smooth=False)
        tube(coll, "Клапан окна", (x0 - 0.04, y - side * 0.02, z1 + 0.05), (x1 + 0.04, y - side * 0.02, z1 + 0.05), 0.035,
             tent_m)
    # каркас: стойки по стенам, стропила к коньку, конёк, центральные стойки
    pole_m = mat_painted("Каркас — краска", (0.07, 0.08, 0.05), rough=0.6, metal=0.4, wear=0.4)
    for x in np.arange(-TX + 0.05, TX, 1.3):
        for s in (-1, 1):
            yw = s * (TY - 0.06)
            tube(coll, "Стойка стены", (x, yw, 0.0), (x, yw, WALL - 0.02), 0.016, pole_m, seg=12)
            tube(coll, "Стропило", (x, yw, WALL - 0.02), (x, 0.0, RIDGE - 0.06), 0.016, pole_m, seg=12)
    for x in (-1.3, 1.3):
        tube(coll, "Центральная стойка", (x, 0.0, 0.0), (x, 0.0, RIDGE - 0.03), 0.022, pole_m)
    tube(coll, "Конёк", (-TX, 0.0, RIDGE - 0.05), (TX, 0.0, RIDGE - 0.05), 0.02, pole_m)
    obj_from(coll, "Пол", [(-TX, -TY, 0), (TX, -TY, 0), (TX, TY, 0), (-TX, TY, 0)], [(0, 1, 2, 3)],
             mat_wood("Пол — доски", PLANKS, 0.7, value=0.42),
             uv=np.array([(0, 0), (2 * TX, 0), (2 * TX, 2 * TY), (0, 2 * TY)]), smooth=False)
    obj_from(coll, "Земля снаружи", [(-40, -40, -0.01), (40, -40, -0.01), (40, 40, -0.01), (-40, 40, -0.01)], [(0, 1, 2, 3)],
             mat_wood("Земля — лесная подстилка", FOREST, 0.5, value=0.7),
             uv=np.array([(0, 0), (80, 0), (80, 80), (0, 80)]), smooth=False)
    return tent_m


def soft_pad(coll, name, cx, cy, hx, hy, z, thick, mat, along_x, quilt=0.2, seed=3):
    """Мягкое на раскладушке (спальник, одеяло): сетка с толщиной к середине, простёжкой поперёк, комками; края свисают
    за трубки."""
    rng = np.random.default_rng(seed + abs(int(cx * 100)) * 7 + abs(int(cy * 10)))
    nx, ny = 110, 50
    u, v = np.meshgrid(np.linspace(-1, 1, nx), np.linspace(-1, 1, ny))
    L, Wd = (hx, hy) if along_x else (hy, hx)
    body = thick * (1 - np.abs(v) ** 6) * (1 - np.abs(u) ** 10)
    q = quilt * thick * np.abs(np.sin(u * L * math.pi / 0.18)) ** 0.5 if quilt else 0.0
    lump = np.zeros_like(u)
    for _ in range(14):
        a0, b0, r = rng.uniform(-0.9, 0.9), rng.uniform(-0.8, 0.8), rng.uniform(0.1, 0.3)
        lump += rng.uniform(-0.25, 0.35) * thick * np.exp(-((u - a0) ** 2 + ((v - b0) * Wd / L) ** 2) / (r * r))
    hang = -0.06 * np.clip((np.abs(v) - 0.86) / 0.14, 0, 1) ** 1.5
    zz = z + body - q * (1 - np.abs(v) ** 4) + lump * (1 - np.abs(v) ** 4) + hang
    X, Y = u * L, v * Wd * (1 + 0.04 * np.clip(np.abs(v) - 0.86, 0, 1))
    if not along_x:
        X, Y = Y, X
    o = obj_from(coll, name, np.stack([cx + X, cy + Y, zz], -1).reshape(-1, 3), grid(nx, ny), mat,
                 uv=np.stack([u * L, v * Wd], -1).reshape(-1, 2))
    o.modifiers.new("Толщина", "SOLIDIFY").thickness = 0.006
    return o


def build_interior(coll, tc):
    """Обстановка: раскладушки со спальниками, печка с трубой, ящики, цинки, канистра, каска, рюкзак, стул у стола.
    tc — центр стола (x, y)."""
    olive = mat_painted("Краска — олив", (0.075, 0.085, 0.05))
    dark = mat_painted("Печь — сталь", (0.035, 0.032, 0.03), rough=0.75, metal=0.5, wear=0.5, under=(0.16, 0.07, 0.03))
    ply = mat_wood("Фанера ящиков", PLY, 1.0, value=0.5)
    bag_m = mat_canvas("Спальник — нейлон", (0.09, 0.10, 0.06), 6.0, nstrength=0.8)
    for n in bag_m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Roughness"].default_value = 0.45
    cot_m = mat_canvas("Брезент раскладушек", (0.20, 0.19, 0.085), 5.5, nstrength=2.0)
    legs = mat_painted("Ножки раскладушек", (0.07, 0.08, 0.045), rough=0.5, metal=0.35, wear=0.3)
    wool = mat_canvas("Одеяло шерстяное", (0.13, 0.12, 0.09), 4.0, nstrength=1.6)

    def cot(cx, cy, along_x=True, bag="spread"):
        L2, W2 = 0.95, 0.33
        sx, sy = (L2, W2) if along_x else (W2, L2)
        box(coll, "Раскладушка", (cx, cy, 0.44), (2 * sx, 2 * sy, 0.025), cot_m, bevel=0.01)
        for t in (-0.62, 0.0, 0.62):
            for s in (-1, 1):
                if along_x:
                    tube(coll, "Нога раскладушки", (cx + t, cy + s * W2, 0.43), (cx + t, cy - s * (W2 + 0.03), 0.0), 0.011, legs, seg=10)
                else:
                    tube(coll, "Нога раскладушки", (cx + s * W2, cy + t, 0.43), (cx - s * (W2 + 0.03), cy + t, 0.0), 0.011, legs, seg=10)
        if bag == "spread":
            soft_pad(coll, "Спальник", cx, cy, sx - 0.03, sy + 0.02, 0.455, 0.055, bag_m, along_x, quilt=0.22)
            pil = box(coll, "Подушка", (cx - (sx - 0.18 if along_x else 0), cy - (0 if along_x else sy - 0.18), 0.55),
                      (0.32 if along_x else 0.45, 0.45 if along_x else 0.32, 0.09), wool, bevel=0.035)
            pil.modifiers.new("Сглаживание", "SUBSURF").levels = 2
        else:
            ax = Vector((0.0, 1.0, 0.0)) if along_x else Vector((1.0, 0.0, 0.0))
            p = Vector((cx - (sx - 0.25 if along_x else 0), cy - (0 if along_x else sy - 0.25), 0.565))
            tube(coll, "Скатанный спальник", p - ax * 0.3, p + ax * 0.3, 0.11, bag_m)
            ox, oy = (0.25, 0) if along_x else (0, 0.25)
            soft_pad(coll, "Одеяло", cx + ox, cy + oy, 0.5 if along_x else sx + 0.04, sy + 0.04 if along_x else 0.5,
                     0.455, 0.02, wool, along_x, quilt=0.0)

    cot(-1.25, 1.55, True, "spread")
    cot(1.15, 1.55, True, "roll")
    cot(-2.2, -0.35, False, "roll")
    # печка-буржуйка в углу и труба через скат
    sx_, sy_ = 2.05, 0.55
    box(coll, "Печь", (sx_, sy_, 0.27), (0.42, 0.55, 0.44), dark, bevel=0.01)
    for dx in (-0.17, 0.17):
        for dy in (-0.22, 0.22):
            tube(coll, "Ножка печи", (sx_ + dx, sy_ + dy, 0.06), (sx_ + dx, sy_ + dy, 0.0), 0.012, dark, seg=8)
    tube(coll, "Труба печи", (sx_, sy_ + 0.15, 0.49), (sx_, sy_ + 0.15, 2.9), 0.055, dark, seg=20)
    box(coll, "Дверца печи", (sx_ - 0.212, sy_, 0.27), (0.006, 0.2, 0.16), dark, bevel=0.003)
    box(coll, "Лист под печью", (sx_, sy_, 0.002), (0.75, 0.85, 0.004), mat_painted("Лист", (0.25, 0.24, 0.22), 0.5, 0.8, 0.7))
    # ящики штабелем, цинки, канистра, каска, рюкзак
    box(coll, "Ящик", (-2.0, -1.55, 0.19), (0.62, 0.38, 0.38), ply, bevel=0.006, rot_z=math.radians(-6))
    box(coll, "Ящик", (-1.97, -1.53, 0.55), (0.55, 0.36, 0.34), ply, bevel=0.006, rot_z=math.radians(4))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(-1.92, -1.5, 0.72), segments=48, ring_count=24)
    h = bpy.context.active_object
    h.name = "Каска"
    h.scale = (1.15, 1.0, 0.85)
    for c in h.users_collection:
        c.objects.unlink(h)
    coll.objects.link(h)
    bm = bmesh.new()
    bm.from_mesh(h.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.002], context="VERTS")
    bm.to_mesh(h.data)
    bm.free()
    h.modifiers.new("Толщина", "SOLIDIFY").thickness = 0.008
    h.data.materials.append(mat_painted("Каска — краска", (0.07, 0.075, 0.05), rough=0.75, metal=0.1, wear=0.5))
    for k, (x, y, rz) in enumerate([(1.10, -1.30, 12), (1.38, -1.25, -5)]):
        box(coll, "Цинк", (tc[0] + x - 0.15, tc[1] + y + 0.45, 0.095), (0.30, 0.16, 0.19), olive, bevel=0.004,
            rot_z=math.radians(rz))
        box(coll, "Крышка цинка", (tc[0] + x - 0.15, tc[1] + y + 0.45, 0.196), (0.31, 0.17, 0.012), olive, bevel=0.003,
            rot_z=math.radians(rz))
    jc = box(coll, "Канистра", (1.05, -1.85, 0.235), (0.34, 0.165, 0.47), olive, bevel=0.02, rot_z=math.radians(8))
    tube(coll, "Горловина канистры", (1.0, -1.85, 0.47), (1.0, -1.85, 0.51), 0.022, olive, seg=16)
    bp = box(coll, "Рюкзак", (-1.55, 0.75, 0.25), (0.34, 0.24, 0.5), bag_m, bevel=0.07, rot_z=math.radians(25))
    bp.modifiers.new("Сглаживание", "SUBSURF").levels = 2
    bp.rotation_euler = (math.radians(-12), 0, math.radians(25))
    # стул у стола (раскладной), кружка на столе
    cx, cy = tc[0] + 0.25, tc[1] + 0.72
    for s in (-1, 1):
        tube(coll, "Ножка стула", (cx - 0.2, cy + s * 0.2, 0.45), (cx + 0.2, cy - s * 0.2, 0.0), 0.011, legs, seg=10)
        tube(coll, "Ножка стула", (cx + 0.2, cy + s * 0.2, 0.45), (cx - 0.2, cy - s * 0.2, 0.0), 0.011, legs, seg=10)
    box(coll, "Сиденье стула", (cx, cy, 0.455), (0.44, 0.40, 0.012), cot_m, bevel=0.004)
    enamel = mat_painted("Эмаль кружки", (0.10, 0.14, 0.09), rough=0.2, metal=0.0, wear=0.25, under=(0.03, 0.03, 0.03))
    mx_, my_ = tc[0] - 0.62, tc[1] + 0.32
    lathe(coll, "Кружка", [(0.0, 0.0), (0.040, 0.0), (0.041, 0.004), (0.041, 0.088), (0.0425, 0.09), (0.039, 0.09),
                          (0.038, 0.008), (0.0, 0.008)], enamel, at=(mx_, my_, 0.76))
    lathe(coll, "Чай", [(0.0, 0.068), (0.0385, 0.068)], mat_plain("Чай", (0.06, 0.025, 0.008), 0.05), at=(mx_, my_, 0.76))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.026, minor_radius=0.005, location=(mx_ + 0.045, my_, 0.76 + 0.05),
                                     rotation=(math.radians(90), 0, 0))
    hd = bpy.context.active_object
    hd.name = "Ручка кружки"
    hd.scale = (0.8, 1.0, 1.25)
    for c in hd.users_collection:
        c.objects.unlink(hd)
    coll.objects.link(hd)
    hd.data.materials.append(enamel)


def lights(coll, lamp_at, lamp_energy=50.0):
    """Небо (Poly Haven, CC0), солнце сбоку сверху (брезент просвечивает; в проём не заходит), лампа над столом на
    шнуре от конька, мягкий дневной свет от входа и окон."""
    sc = bpy.context.scene
    world = bpy.data.worlds.new("Палатка — небо")
    sc.world = world
    world.use_nodes = True
    wn = world.node_tree.nodes
    env = wn.new("ShaderNodeTexEnvironment"); env.image = img(HDRI)
    world.node_tree.links.new(env.outputs["Color"], wn["Background"].inputs["Color"])
    sun_d = bpy.data.lights.new("Солнце", "SUN")
    sun_d.energy, sun_d.angle, sun_d.color = 2.6, math.radians(2.5), (1.0, 0.86, 0.70)
    sun = bpy.data.objects.new("Солнце", sun_d)
    coll.objects.link(sun)
    sun.rotation_euler = Vector((-0.62, 0.22, -0.75)).normalized().to_track_quat("-Z", "Y").to_euler()
    lamp_d = bpy.data.lights.new("Лампа", "POINT")
    lamp_d.energy, lamp_d.shadow_soft_size, lamp_d.color = lamp_energy, 0.02, (1.0, 0.80, 0.58)
    lamp = bpy.data.objects.new("Лампа", lamp_d)
    lamp.location = lamp_at
    coll.objects.link(lamp)
    # плафон и колба (колба в кадре светится, тени не даёт)
    shade = mat_painted("Плафон", (0.06, 0.065, 0.045), rough=0.5, metal=0.5, wear=0.4)
    lathe(coll, "Плафон", [(0.0, 0.11), (0.012, 0.11), (0.02, 0.09), (0.10, 0.02), (0.105, 0.0), (0.0995, 0.0),
                           (0.095, 0.015), (0.018, 0.085), (0.0, 0.09)], shade,
          at=(lamp_at[0], lamp_at[1], lamp_at[2] - 0.02))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(lamp_at[0], lamp_at[1], lamp_at[2] + 0.0))
    bulb = bpy.context.active_object
    bulb.name = "Колба лампы"
    for c in bulb.users_collection:
        c.objects.unlink(bulb)
    coll.objects.link(bulb)
    bulb.data.materials.append(mat_emit("Колба", (1.0, 0.8, 0.55), 8.0))
    bulb.visible_shadow = False
    tube(coll, "Шнур лампы", (lamp_at[0], lamp_at[1], lamp_at[2] + 0.09), (lamp_at[0], lamp_at[1], RIDGE - 0.07), 0.003,
         mat_plain("Шнур", (0.02, 0.02, 0.02), 0.6), seg=8)
    for name, loc, rot, size, energy in (("Свет от входа", (0.0, -TY + 0.05, 0.95), (90, 0, 0), (1.0, 1.8), 110.0),
                                         ("Свет из окон", (-0.6, TY - 0.05, 1.21), (-90, 0, 0), (1.6, 0.42), 60.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.size_y, ld.shape = energy, size[0], size[1], "RECTANGLE"
        ld.color = (0.92, 0.96, 1.0)
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(v) for v in rot)
        lo.visible_camera = False           # сам источник в проёме читался белым щитом
        coll.objects.link(lo)
