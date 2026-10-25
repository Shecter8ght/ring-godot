# Карты из Substance Painter → материал группы деталей в Blender (развёртка уже в деталях, см. sp_export.py).
# blender --background <файл с развёрткой> --python tools/vss_m_v8/sp_apply.py -- <группа> <папка экспорта> [out.blend]
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


def apply(group, folder):
    m = material(group, folder)
    objs = sp_export.group_objects(group)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
    print("APPLIED", group, len(objs))


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    apply(a[0], a[1])
    if len(a) > 2:
        bpy.ops.wm.save_as_mainfile(filepath=a[2], compress=True)
        print("SAVED", a[2])
