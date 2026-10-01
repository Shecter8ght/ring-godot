"""Свежие виды сохранённых источников, GLB и примерки магазина на исходной ВСС."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B
from build_vss_mag_ammo import visible


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--glb', type=Path)
    parser.add_argument('--mount', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve()
    identifier = Path(bpy.data.filepath).stem.removesuffix('_Game')
    B.COLLECTIONS.update({c.name: c for c in bpy.data.collections})
    if args.mount:
        for obj in list(bpy.data.collections['04_Magazine'].objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        with bpy.data.libraries.load(str(output / 'Magazine_939_10_Loaded.blend'), link=False) as (data, target):
            target.collections = ['Magazine_939_10_Loaded']
        group = target.collections[0]
        bpy.context.scene.collection.children.link(group)
        root = next(o for o in group.objects if o.name.startswith('Magazine_939_10_Loaded') and o.parent is None)
        visible(root, True)
        root.location = Vector(root['on_vss_mm']) * .001
        bpy.context.view_layer.update()
        B.camera('Camera_Magazine_Mount', (.52, -.28, .075), (.456, 0, -.058), .22)
        B.render_views(output, 'mounted_magazine', [('beauty', 'Camera_Beauty_Right', 1600, 750),
                      ('fit', 'Camera_Magazine_Mount', 1250, 1000)])
        B.save_scene(output / 'VSS_with_separate_magazine.blend')
        return
    if args.glb:
        for obj in list(bpy.context.scene.objects):
            if obj.type not in {'CAMERA', 'LIGHT'}:
                bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    prefix = 'game_' if args.glb else 'reopened_'
    if identifier == 'VSS_Magazine_Ammo':
        views = [('gallery', 'Camera_Gallery', 1700, 1000)]
    elif identifier.startswith('Cartridge'):
        views = [('beauty', 'Camera_Cartridge', 1500, 800), ('base', 'Camera_Cartridge_Base', 1000, 800)]
    else:
        views = [('beauty', 'Camera_Beauty', 1300, 1000), ('top', 'Camera_Top', 1300, 1000),
                 ('side', 'Camera_Side', 1050, 1000), ('front', 'Camera_Front', 950, 1000),
                 ('rear', 'Camera_Rear', 950, 1000), ('bottom', 'Camera_Bottom', 1050, 1000)]
    B.render_views(output, prefix + identifier, views)


if __name__ == '__main__':
    main()
