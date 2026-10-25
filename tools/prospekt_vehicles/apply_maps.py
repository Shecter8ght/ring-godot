"""Транспорт «Проспекта»: карты из Substance Painter → игровая сетка LOD0, варианты для просмотра в Blender.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/apply_maps.py -- \
        <игровой .blend (game_kit.py)> <папка textures> <выход.blend> [цвет краски — только подпись]

Наборы: Body — у каждой семьи свои карты (textures/<семья>), Interior / Wheel / Under — свои у сгоревшей, у битой —
от целой (та же геометрия и развёртка). Стёкла и линзы — простые прозрачные материалы (в игре так же).
Коллекции «Целый», «Открыт», «Битый», «Сгоревший» стоят рядом вдоль X; колёса — копии одного колеса по местам,
створки «Открыт» повёрнуты на петлях (оси — из сборки, свойство сцены hinges).
Коробчатые (автобус, ПАЗ, ГАЗель): «Целый» и «Открыт»; задние колёса двускатные — внутреннее колесо пары — зеркальная
копия наружного; сдвижная дверь отъезжает назад, створки и распашные повёрнуты, как в build_bus.py.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from specs import CLASSES  # noqa: E402
from specs_bus import BOXES  # noqa: E402

GLASS = {"glass": ((0.06, 0.07, 0.075), 0.30, 0.04), "glass_broken": ((0.06, 0.07, 0.075), 0.40, 0.10),
         "lamp_glass": ((0.85, 0.87, 0.90), 0.18, 0.03), "lamp_red": ((0.55, 0.03, 0.02), 0.65, 0.08),
         "display": ((0.02, 0.025, 0.02), 1.0, 0.15)}


def sp_material(name: str, folder: Path, ts: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])

    def img(suffix, noncolor):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(folder / f"{ts}_{suffix}.png"), check_existing=True)
        t.image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        return t
    bc, orm, nm = img("baseColor", False), img("occlusionRoughnessMetallic", True), img("normal", True)
    nt.links.new(bc.outputs[0], b.inputs["Base Color"])
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], b.inputs["Metallic"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nm.outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], b.inputs["Normal"])
    return m


def glass_material(kind: str) -> bpy.types.Material:
    name = "GLASS_" + kind
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb, alpha, rough = GLASS.get(kind, GLASS["glass"])
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*rgb, alpha)
    try:
        m.surface_render_method = "BLENDED"
    except AttributeError:
        m.blend_method = "BLEND"
    return m


def mirrored(ob: bpy.types.Object) -> bpy.types.Object:
    """Копия колеса лицом внутрь: сетка отражена по оси колеса, нормали развёрнуты (развёртка та же)."""
    c = ob.copy()
    c.data = ob.data.copy()
    x = float(sum(v.co.x for v in c.data.vertices) / max(1, len(c.data.vertices)))
    c.data.transform(Matrix.Translation((x, 0, 0)) @ Matrix.Scale(-1.0, 4, (1, 0, 0)) @ Matrix.Translation((-x, 0, 0)))
    c.data.flip_normals()
    return c


def assemble_box(scn, spec: dict, hinges: dict, fam_col: dict, wheel_x: float) -> None:
    """Коробчатая: «Целый» и «Открыт» рядом вдоль X; колёса по местам, задние — пары."""
    wheel = [o for o in fam_col["clean"].objects if o["group"] == "wheel"]
    inner = [mirrored(o) for o in wheel]
    slide = [d for d in spec["lay"]["doors_r"] + spec["lay"]["doors_l"] if d["kind"] == "slide"]
    for i, (title, v) in enumerate((("Целый", "intact"), ("Открыт", "open"))):
        col = bpy.data.collections.new(title)
        scn.collection.children.link(col)
        root = bpy.data.objects.new(f"{spec['name']}_{v}", None)
        root.empty_display_type = "ARROWS"
        col.objects.link(root)
        root.location = (i * (spec["width"] + 1.5), 0, 0)
        hob = {}
        for g, (a, ax, sgn) in hinges.items():
            e = bpy.data.objects.new(f"Hinge_{g}_{i}", None)
            e.empty_display_type = "SINGLE_ARROW"
            col.objects.link(e)
            e.parent = root
            q = Vector(ax).normalized().to_track_quat("Z", "Y")
            e.matrix_basis = Matrix.Translation(Vector(a)) @ q.to_matrix().to_4x4()
            hob[g] = (e, sgn)
        bpy.context.view_layer.update()
        for ob in fam_col["clean"].objects:
            if ob["group"] == "wheel":
                continue
            c = ob.copy()
            col.objects.link(c)
            grp = ob["group"]
            par = hob[grp][0] if grp in hob else root
            c.parent = par
            if par is not root:
                c.matrix_parent_inverse = par.matrix_basis.inverted()
            elif v == "open" and grp.startswith("door_") and slide:
                sgn = -1.0 if grp.startswith("door_r") else 1.0      # сдвижная: наружу и назад по направляющей
                c.location.x += sgn * 0.07
                c.location.y += (slide[0]["y1"] - slide[0]["y0"]) - 0.08
        yf, yr = spec["wheel_y"]
        places = []
        for sgn in (1.0, -1.0):
            places.append(("F", sgn, sgn * spec["track_f"] / 2, yf, wheel))
            if spec.get("dual_rear"):
                gp = spec["dual_gap"] / 2
                places.append(("R", sgn, sgn * (spec["track_r"] / 2 + gp), yr, wheel))
                places.append(("Ri", sgn, sgn * (spec["track_r"] / 2 - gp), yr, inner))
            else:
                places.append(("R", sgn, sgn * spec["track_r"] / 2, yr, wheel))
        for nm, sgn, x, y, src in places:
            hub = bpy.data.objects.new(f"Wheel_{nm}{'L' if sgn > 0 else 'R'}_{i}", None)
            col.objects.link(hub)
            hub.parent = root
            hub.location = (x, y, spec["wheel_z"])
            hub.rotation_euler = (0, 0, 0 if sgn > 0 else math.pi)
            for ob in src:
                c = ob.copy()
                col.objects.link(c)
                c.parent = hub
                c.location = (-wheel_x, 0, 0)
        if v == "open":
            for g, (e, sgn) in hob.items():
                deg = 82.0 if g[-1] in "ab" else (70.0 if g.startswith("rdoor") else 60.0)
                e.matrix_basis = e.matrix_basis @ Matrix.Rotation(math.radians(deg) * sgn, 4, "Z")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    game, tex, out = Path(argv[0]), Path(argv[1]), Path(argv[2])
    bpy.ops.wm.open_mainfile(filepath=str(game))
    scn = bpy.context.scene
    hinges = json.loads(scn["hinges"])
    dz = float(scn.get("burnt_dz", 0.0))
    cls = scn.get("vehicle_class") or next((k for k in CLASSES if k in game.stem.lower()), "sedan")
    box = cls in BOXES
    spec = BOXES[cls] if box else CLASSES[cls]
    fam_col = {c.name[5:]: c for c in bpy.data.collections if c.name.startswith("LOD0_")}

    def folder(fam, ts):
        f = tex / fam
        if (f / f"{ts}_baseColor.png").exists():
            return f
        return tex / "clean"

    for fam, col in fam_col.items():
        for ob in col.objects:
            ts, mat = ob["tex_set"], ob["mat"]
            ob.data.materials.clear()
            if ts == "Glass":
                ob.data.materials.append(glass_material(mat))
            else:
                ob.data.materials.append(sp_material(f"SP_{fam}_{ts}", folder(fam, ts), ts))
    if box:
        assemble_box(scn, spec, hinges, fam_col, float(scn.get("wheel_x", 3.5)))
    variants = [] if box else [("Целый", "clean", None), ("Открыт", "clean", spec.get("open_cfg")),
                               ("Битый", "wreck", spec.get("wreck_open")), ("Сгоревший", "burnt", spec.get("burnt_open"))]
    for i, (title, fam, cfg) in enumerate(variants):
        if fam not in fam_col:
            continue
        col = bpy.data.collections.new(title)
        scn.collection.children.link(col)
        root = bpy.data.objects.new(f"{spec['name']}_{fam}_{i}", None)
        root.empty_display_type = "ARROWS"
        col.objects.link(root)
        root.location = (i * 3.2, 0, 0)
        hob = {}
        for g, (a, ax, sgn) in hinges.items():
            e = bpy.data.objects.new(f"Hinge_{g}_{i}", None)
            e.empty_display_type = "SINGLE_ARROW"
            col.objects.link(e)
            e.parent = root
            a = Vector(a) - Vector((0, 0, dz if fam == "burnt" else 0.0))
            q = Vector(ax).normalized().to_track_quat("Z", "Y")
            e.matrix_basis = Matrix.Translation(a) @ q.to_matrix().to_4x4()
            hob[g] = (e, sgn)
        bpy.context.view_layer.update()
        wheel = []
        for ob in fam_col[fam].objects:
            if ob["group"] == "wheel":
                wheel.append(ob)
                continue
            c = ob.copy()
            col.objects.link(c)
            par = hob[ob["group"]][0] if ob["group"] in hob else root
            c.parent = par
            if par is not root:
                c.matrix_parent_inverse = par.matrix_basis.inverted()
        clean_wheel = [o for o in fam_col["clean"].objects if o["group"] == "wheel"]
        wz = spec["wheel_z"] - (dz if fam == "burnt" else 0.0)
        for nm, y in (("F", spec["wheel_y"][0]), ("R", spec["wheel_y"][1])):
            for side in (1, -1):
                hub = bpy.data.objects.new(f"Wheel_{nm}{'L' if side > 0 else 'R'}_{i}", None)
                col.objects.link(hub)
                hub.parent = root
                hub.location = (side * spec["track"] / 2, y, wz)
                steer = math.radians(spec.get("wreck_steer", 14.0)) if fam == "wreck" and nm == "F" else 0.0
                hub.rotation_euler = (0, 0, (0 if side > 0 else math.pi) + steer)
                src = wheel if (fam != "wreck" or (nm == "F" and side > 0)) else clean_wheel
                for ob in src:
                    c = ob.copy()
                    col.objects.link(c)
                    c.parent = hub
                    c.location = (-3.5, 0, 0)
        if cfg:
            for g, deg in cfg.items():
                if g in hob:
                    e, sgn = hob[g]
                    e.matrix_basis = e.matrix_basis @ Matrix.Rotation(math.radians(deg) * sgn, 4, "Z")
    for col in fam_col.values():
        col.hide_viewport = True
        col.hide_render = True
    bpy.context.preferences.filepaths.save_version = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True)
    bpy.ops.file.make_paths_relative()              # карты — рядом в папке машины, файл переносится вместе с ней
    bpy.ops.wm.save_mainfile()
    print("сохранено:", out)


if __name__ == "__main__":
    main()
