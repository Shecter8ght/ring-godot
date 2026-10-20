"""Reopen a delivered M02 blend in fresh Blender and check native mesh/rig integrity."""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy


def points(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(dg)
    mesh = evaluated.to_mesh()
    result = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    evaluated.to_mesh_clear()
    return result


def verify(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    body = bpy.data.objects["M02_Body_Head"]
    rig = bpy.data.objects["M02_New_Anatomical_Rig"]
    assert body.type == "MESH" and rig.type == "ARMATURE"
    assert all(math.isfinite(value) for vertex in body.data.vertices for value in vertex.co)
    assert any(mod.type == "ARMATURE" and mod.object == rig for mod in body.modifiers)
    for mod in body.modifiers:
        if mod.type == "SUBSURF":
            mod.show_viewport = False
    bpy.context.view_layer.update()
    rest = points(body)
    height = max(p.z for p in rest) - min(p.z for p in rest)
    assert abs(height - 1.78) < 0.001, height
    bm = bmesh.new()
    bm.from_mesh(body.data)
    topology = {
        "vertices": len(bm.verts), "faces": len(bm.faces),
        "quads": sum(len(face.verts) == 4 for face in bm.faces),
        "boundary_edges": sum(edge.is_boundary for edge in bm.edges),
        "nonmanifold_edges": sum(not edge.is_manifold for edge in bm.edges),
    }
    bm.free()
    assert topology["faces"] == topology["quads"]
    assert topology["nonmanifold_edges"] == 0
    deform_groups = {group.index for group in body.vertex_groups if group.name in rig.data.bones and rig.data.bones[group.name].use_deform}
    unweighted = sum(not any(group.group in deform_groups and group.weight > 0.00001 for group in vertex.groups) for vertex in body.data.vertices)
    assert unweighted == 0, unweighted
    packed = [image.name for image in bpy.data.images if image.source == "FILE" and image.filepath]
    missing_packed = [image.name for image in bpy.data.images if image.source == "FILE" and image.filepath and not image.packed_file]
    assert not missing_packed, missing_packed
    tests = []
    for label, candidates, angle, minimum in [
        ("elbow", ["lowerarm01.L"], 1.0, 0.03),
        ("knee", ["lowerleg01.L"], 1.0, 0.03),
        ("index_finger", ["finger2-1.L", "finger2-2.L"], 0.6, 0.002),
    ]:
        name = next((candidate for candidate in candidates if candidate in rig.pose.bones), None)
        assert name, (label, "missing bone")
        bone = rig.pose.bones[name]
        original = bone.matrix_basis.copy()
        bone.rotation_mode = "XYZ"
        bone.rotation_euler.x += angle
        bpy.context.view_layer.update()
        posed = points(body)
        maximum = max((a - b).length for a, b in zip(rest, posed))
        assert maximum > minimum, (label, maximum)
        assert all(math.isfinite(value) for point in posed for value in point)
        tests.append({"joint": label, "bone": name, "max_displacement_m": maximum, "finite": True})
        bone.matrix_basis = original
        bpy.context.view_layer.update()
    source = path.parent / "M02_Parametric_Apose_Source.blend"
    assert source.is_file()
    result = {
        "file": str(path), "reopened_in": bpy.app.version_string,
        "height_m": height, "topology": topology,
        "unweighted_vertices": unweighted, "rig_bones": len(rig.data.bones),
        "packed_files": packed, "deformation_checks": tests,
        "parametric_source": str(source), "status": "PASS",
    }
    bpy.ops.wm.open_mainfile(filepath=str(source))
    source_body = bpy.data.objects["M02_Body_Head"]
    result["source_shape_keys"] = len(source_body.data.shape_keys.key_blocks)
    assert result["source_shape_keys"] > 20
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    file = parser.parse_args(args).file.resolve()
    result = verify(file)
    (file.parent / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("NPC_M02_VERIFY " + json.dumps(result))
