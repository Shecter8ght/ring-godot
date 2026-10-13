"""Read-only verification of the retained grenade source, without old .blend files.

Run in Blender with --python-exit-code 1; pass --root and --report after --.
The saved delivery certificate supplies the accepted geometry signatures.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def mesh_digest(mesh):
    chunks = []
    for seq, prop, count, dtype in [
        (mesh.vertices, 'co', 3, np.float32),
        (mesh.edges, 'vertices', 2, np.int32),
        (mesh.loops, 'vertex_index', 1, np.int32),
        (mesh.polygons, 'loop_start', 1, np.int32),
        (mesh.polygons, 'loop_total', 1, np.int32),
    ]:
        values = np.empty(len(seq) * count, dtype)
        seq.foreach_get(prop, values)
        chunks.append(values.tobytes())
    return hashlib.sha256(b''.join(chunks)).hexdigest()


def geometry(names):
    result = {}
    for name in names:
        obj = bpy.data.objects[name]
        mesh = obj.data
        keys = {}
        if mesh.shape_keys:
            for key in mesh.shape_keys.key_blocks:
                values = np.empty(len(key.data) * 3, np.float32)
                key.data.foreach_get('co', values)
                keys[key.name] = hashlib.sha256(values.tobytes()).hexdigest()
        result[name] = {
            'mesh': mesh_digest(mesh),
            'matrix': list(map(list, obj.matrix_world)),
            'parent': obj.parent.name if obj.parent else None,
            'keys': keys,
            'modifiers': [[m.name, m.type, getattr(m, 'levels', None),
                           getattr(m, 'render_levels', None)] for m in obj.modifiers],
        }
    return result


def inspect(root, file, accepted):
    bpy.ops.wm.open_mainfile(filepath=str(file))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    if geometry(accepted.keys()) != accepted:
        raise RuntimeError(f'Accepted geometry differs: {file}')
    if bpy.data.libraries:
        raise RuntimeError('Linked external Blender libraries require preservation')
    trees = [tree for tree in bpy.data.node_groups
             if getattr(tree, 'yp', None) and tree.yp.is_ypaint_node]
    layers = sum(len(tree.yp.layers) for tree in trees)
    if len(trees) != 4 or layers != 56:
        raise RuntimeError(('Unexpected native paint stack', len(trees), layers))
    images = []
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT', 'COMPOSITING'}:
            continue
        path = Path(bpy.path.abspath(image.filepath)).resolve()
        if not image.packed_file or not path.is_file() or not path.is_relative_to(root):
            raise RuntimeError(('Unpreserved image dependency', image.name, str(path)))
        digest = hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
        if digest != sha(path):
            raise RuntimeError(('Packed/external image mismatch', image.name))
        images.append({'name': image.name, 'path': str(path.relative_to(root)),
                       'sha256': digest, 'color_space': image.colorspace_settings.name,
                       'resolution': list(image.size)})
    if len(images) != 22:
        raise RuntimeError(('Unexpected image count', len(images)))
    for font in bpy.data.fonts:
        if font.filepath and font.filepath != '<builtin>' and not font.packed_file:
            raise RuntimeError(('Unpacked font', font.name, font.filepath))
    return {'file': str(file), 'sha256': sha(file), 'geometry_matches_acceptance': True,
            'native_stacks': len(trees), 'native_layers': layers, 'images': images,
            'linked_libraries': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    root = args.root.resolve()
    accepted = json.loads((root / 'checks/delivered_audit.json').read_text(
        encoding='utf-8-sig'))['unchanged_meshes']
    bpy.context.preferences.use_preferences_save = False
    # UCUPaint reads its AddonPreferences during registration; these preferences
    # exist only in this factory-startup process and are never saved globally.
    addon = addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    if addon is None:
        raise RuntimeError('The installed UCUPaint extension could not be enabled')
    rows = []
    for name in ('Grenade_MkII_UCUPaint_v08.blend', 'Grenade_MkII_Studio_v08.blend'):
        rows.append(inspect(root, root / name, accepted))
        print('CURRENT_SOURCE_VERIFIED', name, flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'pass': True, 'files': rows,
        'scope': 'Saved geometry, native stacks and self-contained image dependencies; '
                 'no render, bake, or saved blend edits.'}, ensure_ascii=False, indent=2),
        encoding='utf8')


if __name__ == '__main__':
    main()
