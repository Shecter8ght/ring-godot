"""Проверочные виды сохранённых прицелов и их посадки на ВСС."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Matrix, Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B


def diagnose() -> None:
    deps = bpy.context.evaluated_depsgraph_get()
    result = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bad = sum(len(edge.link_faces) != 2 for edge in bm.edges)
        if bad:
            result.append({'object': obj.name, 'nonmanifold_edges': bad,
                'boundary': sum(len(e.link_faces) == 1 for e in bm.edges),
                'overfull': sum(len(e.link_faces) > 2 for e in bm.edges)})
        bm.free()
        evaluated.to_mesh_clear()
    print('OPTICS_TOPOLOGY ' + json.dumps(result), flush=True)


def visibility(group: bpy.types.Collection, state: bool) -> None:
    for obj in list(group.objects):
        if obj is None:
            continue
        obj.hide_render = not state
        obj.hide_set(not state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mount', action='store_true')
    parser.add_argument('--diagnose', action='store_true')
    parser.add_argument('--game', action='store_true')
    parser.add_argument('--glb', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve()
    B.COLLECTIONS.update({c.name: c for c in bpy.data.collections})
    if args.glb:
        for obj in list(bpy.context.scene.objects):
            if obj.type not in {'LIGHT', 'CAMERA'}:
                bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    if args.diagnose:
        diagnose()
        return
    if args.mount:
        for identifier in ('PSO_VSS_4x24', 'Rail_4x32'):
            with bpy.data.libraries.load(str(output / (identifier + '.blend')), link=False) as (data, target):
                target.collections = [identifier]
            group = target.collections[0]
            bpy.context.scene.collection.children.link(group)
            root = next(o for o in group.objects if o.type == 'EMPTY' and o.name.startswith(identifier))
            root.location = Vector(root['on_vss_mm']) * .001
            root.name = identifier + '_Mounted'
            B.COLLECTIONS[identifier] = group
            bpy.context.view_layer.update()
        B.camera('Camera_Optic_Mount_Left', (.39, .5, .24), (.36, .015, .048), .46)
        B.camera('Camera_Rail_Clamp', (.37, -.27, .13), (.383, 0, .07), .19)
        B.camera('Camera_PSO_Clamp', (.26, .22, .05), (.342, .03, .028), .185)
        for identifier, suffix in [('PSO_VSS_4x24', 'pso'), ('Rail_4x32', 'rail')]:
            for other in ('PSO_VSS_4x24', 'Rail_4x32'):
                visibility(B.COLLECTIONS[other], other == identifier)
            B.render_views(output, 'mounted_' + suffix, [
                ('beauty', 'Camera_Beauty_Right', 1800, 800),
                ('left', 'Camera_Optic_Mount_Left', 1400, 850),
                ('clamp', 'Camera_PSO_Clamp' if suffix == 'pso' else 'Camera_Rail_Clamp', 1100, 800)])
        bpy.context.scene.camera = bpy.data.objects['Camera_Beauty_Right']
        B.save_scene(output / 'VSS_with_optics.blend')
    else:
        identifier = Path(bpy.data.filepath).stem.removesuffix('_Game')
        if identifier == 'VSS_Optics':
            views = [('gallery', 'Camera_Gallery', 1700, 1000)]
        else:
            views = [('beauty', 'Camera_Beauty', 1500, 800),
                ('left', 'Camera_Left', 1600, 850), ('right', 'Camera_Right', 1600, 850),
                ('front', 'Camera_Front', 850, 850), ('rear', 'Camera_Rear', 850, 850),
                ('bottom', 'Camera_Bottom', 1250, 950)]
        B.render_views(output, ('game_' if args.game else 'final_') + identifier, views)


if __name__ == '__main__':
    main()
