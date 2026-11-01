"""Ковёр общежития: настоящий ворс волокнами (Geometry Nodes) для рендера и для запекания игровых карт.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<файл с ковром>" --python-exit-code 1 \
      --python tools/dorm_modules/carpet_pile.py -- <карта цвета ковра .png> [объект] [сохранить в .blend]

Владелец 2026-11-01: «сделай этот ковёр из настоящей ткани с настоящим ворсом». На лице ковра (грани к −Y в осях
корня) — пучки по Пуассону с шагом ~2 мм (машинный ковёр, ~200 тыс. точек на м²), в пучке 12 шерстинок (кисточка:
корни в круге 0,3 мм, отклонение до 17°); у каждой шерстинки свои наклон, длина 6 мм × 0,75–1,15 и извитость; у
висящего на стене ворс приглажен вниз. Цвет — из карты цвета ковра по месту корня (та же развёртка, атрибут root_uv) и
свой тон у шерстинки, шейдер — Principled Hair (Chiang, по цвету): шерсть матовее волоса, чешуйки шире. Во вьюпорте —
доля пучков (Is Viewport), в рендере — все (~5 млн шерстинок).
"""
import math
import os
import sys

import bpy

GROUP = "Ворс ковра"
MAT = "Ковёр_ворс"
PILE = "Ковёр_ворс"


def _n(nt, kind, loc, **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def build_group(src: bpy.types.Object) -> bpy.types.NodeTree:
    """Ворс — на отдельном объекте-волосах (Curves): кривые узлов на объекте-сетке Cycles не рендерит как волосы;
    поверхность ковра берётся Object Info (src — сетка ковра, ворс — её дочерний объект без сдвига).
    Пучок не копия одного образца: сначала корни шерстинок (12 точек на пучок, каждая сдвинута своим случаем), потом
    на каждый корень — своя шерстинка (наклон, длина, извитость — по её номеру). Копия одной кисточки на все пучки
    в макро читалась повтором «ёлочек» (рендер 2026-11-01)."""
    old = bpy.data.node_groups.get(GROUP)
    if old is not None:
        bpy.data.node_groups.remove(old)
    nt = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    io = nt.interface
    io.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for name, val, lo, hi in (("Шаг пучков, м", 0.002, 0.0005, 0.01), ("Длина ворса, м", 0.006, 0.001, 0.03),
                              ("Наклон вниз", 0.07, 0.0, 1.5), ("Извитость", 0.12, 0.0, 1.0),
                              ("Толщина волокна, м", 0.00009, 0.00002, 0.001), ("Доля во вьюпорте", 0.03, 0.0, 1.0)):
        s = io.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat")
        s.default_value, s.min_value, s.max_value = val, lo, hi
    io.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    L = nt.links.new
    gi = _n(nt, "NodeGroupInput", (-2000, 0))
    go = _n(nt, "NodeGroupOutput", (2200, 0))

    def rnd(kind, lo, hi, seed, loc):
        r = _n(nt, "FunctionNodeRandomValue", loc, data_type=kind)
        r.inputs["Min"].default_value = lo
        r.inputs["Max"].default_value = hi
        r.inputs["Seed"].default_value = seed
        return r.outputs[0]

    def math_(op, a, b, loc):
        m = _n(nt, "ShaderNodeMath", loc, operation=op)
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                L(v, m.inputs[i])
        return m.outputs[0]

    def store(geo, name, kind, value, loc, domain="POINT"):
        st = _n(nt, "GeometryNodeStoreNamedAttribute", loc, data_type=kind, domain=domain)
        st.inputs["Name"].default_value = name
        L(geo, st.inputs["Geometry"])
        L(value, st.inputs["Value"])
        return st.outputs[0]

    def named(name, kind, loc):
        n = _n(nt, "GeometryNodeInputNamedAttribute", loc, data_type=kind)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    # лицо ковра: грани к −Y
    nrm = _n(nt, "GeometryNodeInputNormal", (-1800, 300))
    sep_n = _n(nt, "ShaderNodeSeparateXYZ", (-1650, 300))
    L(nrm.outputs[0], sep_n.inputs[0])
    face = _n(nt, "FunctionNodeCompare", (-1500, 300), data_type="FLOAT", operation="LESS_THAN")
    face.inputs[1].default_value = -0.5
    L(sep_n.outputs["Y"], face.inputs[0])
    info = _n(nt, "GeometryNodeObjectInfo", (-1650, 100), transform_space="RELATIVE")
    info.inputs["Object"].default_value = src
    sep = _n(nt, "GeometryNodeSeparateGeometry", (-1350, 150), domain="FACE")
    L(info.outputs["Geometry"], sep.inputs["Geometry"])
    L(face.outputs[0], sep.inputs["Selection"])

    # пучки по Пуассону; во вьюпорте — доля
    isv = _n(nt, "GeometryNodeIsViewport", (-1500, -100))
    sw = _n(nt, "GeometryNodeSwitch", (-1350, -100), input_type="FLOAT")
    sw.inputs["False"].default_value = 1.0
    L(isv.outputs[0], sw.inputs["Switch"])
    L(gi.outputs["Доля во вьюпорте"], sw.inputs["True"])
    # плотность сверху: 1 / шаг² с запасом — Пуассон сам прорежает до шага
    dens = math_("MULTIPLY", math_("POWER", gi.outputs["Шаг пучков, м"], -2.0, (-1500, -300)), 2.0, (-1350, -300))
    dist = _n(nt, "GeometryNodeDistributePointsOnFaces", (-1150, 100), distribute_method="POISSON")
    L(sep.outputs["Selection"], dist.inputs["Mesh"])
    L(gi.outputs["Шаг пучков, м"], dist.inputs["Distance Min"])
    L(dens, dist.inputs["Density Max"])
    L(sw.outputs[0], dist.inputs["Density Factor"])
    dist.inputs["Seed"].default_value = 7
    # место корня в развёртке (цвет волокна) и нормаль лица — на точку пучка, дальше их наследуют шерстинки
    tufts = store(dist.outputs["Points"], "root_uv", "FLOAT_VECTOR", named("UVMap", "FLOAT_VECTOR", (-1150, -150)),
                  (-950, 100))
    tufts = store(tufts, "nrm", "FLOAT_VECTOR", dist.outputs["Normal"], (-800, 100))

    # корни шерстинок: 12 точек в круге 0,3 мм вокруг середины пучка, поворот пучка — случайный вокруг нормали
    pts = _n(nt, "GeometryNodePoints", (-1000, -450))
    pts.inputs["Count"].default_value = 12
    L(rnd("FLOAT_VECTOR", (-0.0003, -0.0003, 0.0), (0.0003, 0.0003, 0.0), 3, (-1200, -450)), pts.inputs["Position"])
    rz = _n(nt, "ShaderNodeCombineXYZ", (-800, -250))
    L(rnd("FLOAT", 0.0, 6.283, 11, (-1000, -250)), rz.inputs["Z"])
    rze = _n(nt, "FunctionNodeEulerToRotation", (-650, -250))
    L(rz.outputs[0], rze.inputs[0])
    rot = _n(nt, "FunctionNodeRotateRotation", (-500, -150), rotation_space="LOCAL")
    L(dist.outputs["Rotation"], rot.inputs["Rotation"])
    L(rze.outputs[0], rot.inputs["Rotate By"])
    roots = _n(nt, "GeometryNodeInstanceOnPoints", (-350, 0))
    L(tufts, roots.inputs["Points"])
    L(pts.outputs["Points"], roots.inputs["Instance"])
    L(rot.outputs[0], roots.inputs["Rotation"])
    roots_r = _n(nt, "GeometryNodeRealizeInstances", (-200, 0))
    L(roots.outputs[0], roots_r.inputs[0])
    # у каждой шерстинки свой сдвиг корня (по её номеру) — пучки не повторяют друг друга
    jit = _n(nt, "GeometryNodeSetPosition", (-50, 0))
    L(roots_r.outputs[0], jit.inputs["Geometry"])
    L(rnd("FLOAT_VECTOR", (-0.00015, -0.00015, -0.00015), (0.00015, 0.00015, 0.00015), 17, (-200, -200)),
      jit.inputs["Offset"])
    # извитость — фаза шума своя у каждой шерстинки
    strands = store(jit.outputs[0], "phase", "FLOAT_VECTOR",
                    rnd("FLOAT_VECTOR", (0.0, 0.0, 0.0), (100.0, 100.0, 100.0), 19, (-50, -250)), (100, 0))

    # шерстинка: отрезок по нормали лица, наклон до ±17° и длина 0,75–1,15 — свои у каждой (ворс стоит щёткой;
    # одинаково приглаженный вниз читался рядами, как рогожа)
    line = _n(nt, "GeometryNodeCurvePrimitiveLine", (100, -500))
    line.inputs["End"].default_value = (0.0, 0.0, 1.0)
    res = _n(nt, "GeometryNodeResampleCurve", (250, -500))
    res.inputs["Count"].default_value = 6
    L(line.outputs[0], res.inputs["Curve"])
    align = _n(nt, "FunctionNodeAlignRotationToVector", (250, -250), axis="Z")
    L(named("nrm", "FLOAT_VECTOR", (100, -300)), align.inputs["Vector"])
    tilt = _n(nt, "FunctionNodeEulerToRotation", (250, -380))
    L(rnd("FLOAT_VECTOR", (-0.3, -0.3, 0.0), (0.3, 0.3, 6.283), 5, (100, -400)), tilt.inputs[0])
    rot2 = _n(nt, "FunctionNodeRotateRotation", (400, -300), rotation_space="LOCAL")
    L(align.outputs[0], rot2.inputs["Rotation"])
    L(tilt.outputs[0], rot2.inputs["Rotate By"])
    scl = math_("MULTIPLY", rnd("FLOAT", 0.75, 1.15, 13, (250, -650)), gi.outputs["Длина ворса, м"], (400, -650))
    inst = _n(nt, "GeometryNodeInstanceOnPoints", (550, 0))
    L(strands, inst.inputs["Points"])
    L(res.outputs[0], inst.inputs["Instance"])
    L(rot2.outputs[0], inst.inputs["Rotation"])
    L(scl, inst.inputs["Scale"])
    real = _n(nt, "GeometryNodeRealizeInstances", (700, 0))
    L(inst.outputs[0], real.inputs[0])

    # приглажен вниз: кончик уходит к −Z на «наклон» × длина, по квадрату параметра
    par = _n(nt, "GeometryNodeSplineParameter", (700, -300))
    lean = math_("MULTIPLY", math_("MULTIPLY", math_("POWER", par.outputs["Factor"], 2.0, (850, -300)),
                                   gi.outputs["Наклон вниз"], (1000, -300)), gi.outputs["Длина ворса, м"], (1150, -300))
    down = _n(nt, "ShaderNodeVectorMath", (1300, -300), operation="SCALE")
    down.inputs[0].default_value = (0.0, 0.0, -1.0)
    L(lean, down.inputs["Scale"])
    # извитость шерсти: шум вдоль шерстинки со своей фазой, к кончику сильнее
    posn = _n(nt, "GeometryNodeInputPosition", (700, -550))
    phase = _n(nt, "ShaderNodeVectorMath", (850, -550), operation="ADD")
    psc = _n(nt, "ShaderNodeVectorMath", (850, -700), operation="SCALE")
    psc.inputs["Scale"].default_value = 1.0 / 900.0
    L(named("phase", "FLOAT_VECTOR", (700, -700)), psc.inputs[0])
    L(posn.outputs[0], phase.inputs[0])
    L(psc.outputs[0], phase.inputs[1])
    noise = _n(nt, "ShaderNodeTexNoise", (1000, -550), noise_dimensions="3D")
    noise.inputs["Scale"].default_value = 900.0
    noise.inputs["Detail"].default_value = 1.0
    L(phase.outputs[0], noise.inputs["Vector"])
    cen = _n(nt, "ShaderNodeVectorMath", (1150, -550), operation="SUBTRACT")
    L(noise.outputs["Color"], cen.inputs[0])
    cen.inputs[1].default_value = (0.5, 0.5, 0.5)
    amp = math_("MULTIPLY", math_("MULTIPLY", par.outputs["Factor"], gi.outputs["Извитость"], (1150, -750)),
                gi.outputs["Длина ворса, м"], (1300, -750))
    fuzz = _n(nt, "ShaderNodeVectorMath", (1300, -550), operation="SCALE")
    L(cen.outputs[0], fuzz.inputs[0])
    L(amp, fuzz.inputs["Scale"])
    off = _n(nt, "ShaderNodeVectorMath", (1450, -400), operation="ADD")
    L(down.outputs[0], off.inputs[0])
    L(fuzz.outputs[0], off.inputs[1])
    setp = _n(nt, "GeometryNodeSetPosition", (1500, 0))
    L(real.outputs[0], setp.inputs["Geometry"])
    L(off.outputs[0], setp.inputs["Offset"])

    # толщина: у корня волокно (прядь) толще, к кончику вдвое тоньше
    rad = _n(nt, "ShaderNodeMapRange", (1500, -300))
    L(par.outputs["Factor"], rad.inputs["Value"])
    rad.inputs["To Min"].default_value = 1.0
    rad.inputs["To Max"].default_value = 0.45
    setr = _n(nt, "GeometryNodeSetCurveRadius", (1700, 0))
    L(setp.outputs[0], setr.inputs["Curve"])
    L(math_("MULTIPLY", rad.outputs["Result"], gi.outputs["Толщина волокна, м"], (1650, -300)), setr.inputs["Radius"])
    setm = _n(nt, "GeometryNodeSetMaterial", (1900, 0))
    L(setr.outputs[0], setm.inputs["Geometry"])
    L(setm.outputs[0], go.inputs["Geometry"])
    return nt


def fibre_material(color_png: str) -> bpy.types.Material:
    """Шерстинка: Principled Hair по цвету карты ковра в месте корня; шерсть матовая, чешуйки шире, чем у волоса."""
    m = bpy.data.materials.get(MAT) or bpy.data.materials.new(MAT)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, "ShaderNodeOutputMaterial", (600, 0))
    hair = _n(nt, "ShaderNodeBsdfHairPrincipled", (300, 0), model="CHIANG", parametrization="COLOR")
    hair.inputs["Roughness"].default_value = 0.45
    hair.inputs["Radial Roughness"].default_value = 0.7
    hair.inputs["Coat"].default_value = 0.0
    hair.inputs["IOR"].default_value = 1.55
    hair.inputs["Offset"].default_value = math.radians(3.0)
    hair.inputs["Random Roughness"].default_value = 0.2
    attr = _n(nt, "ShaderNodeAttribute", (-500, 0), attribute_type="GEOMETRY", attribute_name="root_uv")
    tex = _n(nt, "ShaderNodeTexImage", (-300, 0), interpolation="Linear")
    tex.image = bpy.data.images.load(color_png, check_existing=True)
    tex.image.colorspace_settings.name = "sRGB"
    nt.links.new(attr.outputs["Vector"], tex.inputs["Vector"])
    # цвет по волокну: внутри пряди свет рассеивается многократно — карта подаётся чуть светлее (гамма 0,85),
    # иначе ворс темнее и насыщеннее узора на поверхности под ним
    gam = _n(nt, "ShaderNodeGamma", (0, 0))
    gam.inputs["Gamma"].default_value = 0.85
    nt.links.new(tex.outputs["Color"], gam.inputs["Color"])
    # каждая шерстинка своего тона (±12 %) — пряжа из разных волокон, ворс «искрит»
    info = _n(nt, "ShaderNodeHairInfo", (-300, -250))
    k = _n(nt, "ShaderNodeMapRange", (-100, -250))
    k.inputs["To Min"].default_value = 0.88
    k.inputs["To Max"].default_value = 1.12
    nt.links.new(info.outputs["Random"], k.inputs["Value"])
    mul = _n(nt, "ShaderNodeMix", (150, 0), data_type="RGBA", blend_type="MULTIPLY")
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(gam.outputs["Color"], mul.inputs["A"])
    nt.links.new(k.outputs["Result"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], hair.inputs["Color"])
    nt.links.new(hair.outputs[0], out.inputs["Surface"])
    return m


def add_pile(ob: bpy.types.Object, color_png: str) -> bpy.types.Object:
    """Объект «Ковёр_ворс» (волосы) — дочерний к сетке ковра, в тех же коллекциях; прежний ворс заменяется."""
    old = bpy.data.objects.get(PILE)
    if old is not None:
        data = old.data
        bpy.data.objects.remove(old)
        bpy.data.hair_curves.remove(data)
    hair = bpy.data.objects.new(PILE, bpy.data.hair_curves.new(PILE))
    for c in ob.users_collection:
        c.objects.link(hair)
    hair.parent = ob
    hair.matrix_parent_inverse.identity()
    grp = build_group(ob)
    mod = hair.modifiers.new("Ворс", "NODES")
    mod.node_group = grp
    mat = fibre_material(color_png)
    next(n for n in grp.nodes if n.bl_idname == "GeometryNodeSetMaterial").inputs["Material"].default_value = mat
    hair.data.materials.append(mat)
    return hair


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    color_png = os.path.abspath(argv[0])
    name = argv[1] if len(argv) > 1 and argv[1] else "Ковёр_шерсть"
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.split(".")[0] == name and not o.hide_render)
    hair = add_pile(ob, color_png)
    print("PILE", ob.name, "→", hair.name, flush=True)
    if len(argv) > 2:
        bpy.ops.wm.save_as_mainfile(filepath=argv[2], compress=True)
        print("saved", argv[2])


if __name__ == "__main__":
    main()
