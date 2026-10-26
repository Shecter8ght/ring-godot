"""«Проспект», ограждения и город: карты Painter → игровые детали LOD0, файл просмотра игровой версии в Blender.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/game_apply.py -- \
        <модуль> <lod0.blend> <папка textures> <выход.blend>

Материал набора «<набор>» получает карты <набор>_baseColor / _occlusionRoughnessMetallic / _normal (выгрузка Painter
пресетом glTF: R — AO, G — шероховатость, B — металл; нормали OpenGL). Razor и Barbed — плиточные карты проволоки
(wire_textures.py — запустить до этого шага в ту же папку textures), прозрачность отсечением 0,5 (в glTF — alphaMode MASK).
Glass — прозрачный материал без карт. Коллекции «LOD0 | <вариант>» остаются как в game.py.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GLASS = {"Glass": ((0.10, 0.12, 0.12), 0.30, 0.04), "GlassDark": ((0.04, 0.05, 0.05), 0.55, 0.06),
         "Lamp": ((0.85, 0.85, 0.80), 1.0, 0.10)}       # рассеиватель светильника — непрозрачный: снизу на 8 м не видно
                                                          # сквозь, а прозрачный — отдельный проход у каждой опоры


def pbr(m: bpy.types.Material, folder: Path, ts: str, alpha_clip: bool = False) -> None:
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])

    def img(suffix: str, noncolor: bool):
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
    # glTF: AO — из R той же карты (экспортёр узнаёт узел «glTF Material Output» с входом Occlusion)
    try:
        grp = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output",
                                                                                            "ShaderNodeTree")
        if "Occlusion" not in [s.name for s in grp.interface.items_tree]:
            grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree = grp
        nt.links.new(sp.outputs["Red"], g.inputs["Occlusion"])
    except Exception as e:                      # без AO материал всё равно годен
        print("AO для glTF не подключено:", e)
    if alpha_clip:
        rnd = nt.nodes.new("ShaderNodeMath")
        rnd.operation = "ROUND"                   # экспортёр glTF: Round → alphaMode MASK, порог 0,5
        nt.links.new(bc.outputs["Alpha"], rnd.inputs[0])
        nt.links.new(rnd.outputs[0], b.inputs["Alpha"])
        m.surface_render_method = "DITHERED"
    # сплошные тела — односторонние (в glTF doubleSided = false): двусторонний материал в игре удваивает растр в тенях;
    # лента и колючка — плоские полосы, видны с обеих сторон
    m.use_backface_culling = not alpha_clip


def glass(m: bpy.types.Material, kind: str) -> None:
    rgb, alpha, rough = GLASS.get(kind, GLASS["Glass"])
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*rgb, alpha)
    m.surface_render_method = "BLENDED" if alpha < 1.0 else "DITHERED"
    m.use_backface_culling = False


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    mod_name, lod0, folder, out = argv[0], Path(argv[1]), Path(argv[2]), Path(argv[3])
    bpy.ops.wm.open_mainfile(filepath=str(lod0))
    for m in bpy.data.materials:
        if m.name in ("Razor", "Barbed"):
            pbr(m, folder, m.name, alpha_clip=True)
        elif m.name == "Rebar":
            pbr(m, folder, m.name)
        elif m.name in GLASS:
            glass(m, m.name)
        elif (folder / f"{m.name}_baseColor.png").exists():
            pbr(m, folder, m.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    print("сохранено:", out, importlib.util.find_spec(mod_name) is not None)


main()
