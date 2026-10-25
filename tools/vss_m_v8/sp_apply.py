# Карты из Substance Painter → материал группы деталей в Blender (развёртка уже в деталях, см. sp_export.py).
# blender --background <файл с развёрткой> --python tools/vss_m_v8/sp_apply.py -- <группа|all> [<папка экспорта>] [out.blend]
# all — коробка (sp_receiver/export) и все наборы проекта «parts» (sp_parts/export).
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import sp_export  # noqa: E402  (GROUPS, group_objects; main() не вызывается при импорте ниже)


def material(group, folder):
    name = f"SP_{group}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])

    def img(suffix, noncolor):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(folder, f"{group}_{suffix}.png"), check_existing=True)
        t.image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        t.interpolation = "Cubic"
        return t
    bc = img("baseColor", False)
    orm = img("occlusionRoughnessMetallic", True)
    nm = img("normal", True)
    nt.links.new(bc.outputs[0], b.inputs["Base Color"])
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], b.inputs["Metallic"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nm.outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], b.inputs["Normal"])
    return m


ROOT = "E:/Games/RING-godot/_asset_src/vss_m_v8"


def apply(group, folder):
    m = material(group, folder)
    objs = sp_export.group_objects(group)
    for o in objs:
        n = max(1, len(o.data.materials))          # у патрона два слота (гильза, пуля) — оба на один материал
        o.data.materials.clear()
        for _ in range(n):
            o.data.materials.append(m)
    print("APPLIED", group, len(objs))


def apply_all():
    apply("receiver", ROOT + "/sp_receiver/export")
    for g in sp_export.PARTS:
        apply(g, ROOT + "/sp_parts/export")


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "all":
        apply_all()
        out = a[1] if len(a) > 1 else None
    else:
        apply(a[0], a[1])
        out = a[2] if len(a) > 2 else None
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print("SAVED", out)
