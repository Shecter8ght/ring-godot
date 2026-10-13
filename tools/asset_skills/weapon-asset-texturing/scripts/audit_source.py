"""Read-only Blender audit. Run with --python-exit-code 1 and arguments after --.

Only the JSON report is written. This deliberately does not assert equivalence of
all modifier settings, animation, shape keys, optical behavior or UCUPaint inputs.
"""
import argparse
import hashlib
import json
import sys
from array import array
from pathlib import Path

import bpy
import numpy as np

KINDS = {'MESH', 'FONT', 'CURVE', 'EMPTY', 'ARMATURE'}


def bulk(collection, attribute, size, typecode):
    data = array(typecode, [0]) * (len(collection) * size)
    collection.foreach_get(attribute, data)
    return data.tobytes()


def curve_shape(data):
    result = []
    for spline in data.splines:
        result.append({
            'type': spline.type, 'cyclic': spline.use_cyclic_u,
            'order': spline.order_u, 'resolution': spline.resolution_u,
            'points': [(list(p.co), p.radius, p.tilt, p.weight_softbody) for p in spline.points],
            'bezier': [(list(p.co), list(p.handle_left), list(p.handle_right),
                        p.handle_left_type, p.handle_right_type, p.radius, p.tilt)
                       for p in spline.bezier_points],
        })
    return {'splines': result, 'dimensions': data.dimensions,
            'bevel_depth': data.bevel_depth, 'extrude': data.extrude,
            'bevel_resolution': data.bevel_resolution, 'resolution_u': data.resolution_u}


def shape_signature(obj):
    data = obj.data
    if obj.type == 'MESH':
        digest = hashlib.sha256()
        for part in (bulk(data.vertices, 'co', 3, 'f'),
                     bulk(data.edges, 'vertices', 2, 'i'),
                     bulk(data.loops, 'vertex_index', 1, 'i'),
                     bulk(data.polygons, 'loop_start', 1, 'i'),
                     bulk(data.polygons, 'loop_total', 1, 'i')):
            digest.update(len(part).to_bytes(8, 'little'))
            digest.update(part)
        return digest.hexdigest()
    if obj.type == 'FONT':
        result = {'body': data.body, 'size': data.size, 'extrude': data.extrude,
                  'bevel_depth': data.bevel_depth, 'align_x': data.align_x,
                  'align_y': data.align_y, 'space_character': data.space_character,
                  'space_word': data.space_word, 'space_line': data.space_line,
                  'offset_x': data.offset_x, 'offset_y': data.offset_y,
                  'font': data.font.name if data.font else None}
    elif obj.type == 'CURVE':
        result = curve_shape(data)
    elif obj.type == 'ARMATURE':
        result = [{'name': b.name, 'parent': b.parent.name if b.parent else None,
                   'matrix': [v for row in b.matrix_local for v in row],
                   'length': b.length, 'deform': b.use_deform} for b in data.bones]
    else:
        return None
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.view_layer.update()
    objects = {}
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type not in KINDS:
            continue
        objects[obj.name] = {
            'type': obj.type, 'shape': shape_signature(obj),
            'parent': obj.parent.name if obj.parent else None,
            'parent_type': obj.parent_type, 'parent_bone': obj.parent_bone,
            'matrix_local': [round(v, 7) for row in obj.matrix_local for v in row],
            'modifiers': [(m.name, m.type, m.show_viewport, m.show_render) for m in obj.modifiers],
            'drivers': [(f.data_path, f.array_index, f.driver.expression)
                        for f in obj.animation_data.drivers] if obj.animation_data else [],
        }
        if obj.type == 'MESH':
            ev = obj.evaluated_get(graph)
            objects[obj.name]['evaluated_dimensions'] = [round(v, 7) for v in ev.dimensions]
    images, issues, manual = [], [], []
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT', 'COMPOSITING'}:
            continue
        packed = bool(im.packed_file or len(im.packed_files))
        filepath = bpy.path.abspath(im.filepath, library=im.library) if im.filepath else ''
        entry = {'name': im.name, 'source': im.source, 'packed': packed,
                 'filepath': im.filepath, 'resolved': filepath,
                 'size': list(im.size), 'color_space': im.colorspace_settings.name}
        blank = False
        if not packed and im.source == 'GENERATED' and im.generated_type == 'BLANK' and not im.is_dirty:
            pixels = np.empty(len(im.pixels), dtype=np.float32)
            im.pixels.foreach_get(pixels)
            if pixels.size and pixels.size % 4 == 0:
                rgba = pixels.reshape(-1, 4)
                blank = bool(np.allclose(rgba.min(axis=0), im.generated_color, atol=1e-7)
                             and np.allclose(rgba.max(axis=0), im.generated_color, atol=1e-7))
            entry['reconstructible_blank'] = blank
        images.append(entry)
        if im.source in {'MOVIE', 'SEQUENCE', 'TILED', 'VIEWER'}:
            manual.append(f'{im.name}: source {im.source} needs specialized dependency review')
        elif blank:
            manual.append(f'{im.name}: reproducible blank Generated image; pack after painting')
        elif not packed and (im.source == 'GENERATED' or not filepath or not Path(filepath).is_file()):
            issues.append(f'{im.name}: unpacked image has no persistent readable file')
    for lib in bpy.data.libraries:
        manual.append(f'Linked library: {bpy.path.abspath(lib.filepath)}')
    collisions = {}
    for im in bpy.data.images:
        if im.packed_file and im.filepath:
            filename = Path(im.filepath.replace('\\', '/')).name.casefold()
            digest = hashlib.sha256(bytes(im.packed_file.data)).hexdigest()
            collisions.setdefault(filename, {}).setdefault(digest, []).append(im.name)
    collisions = {name: hashes for name, hashes in collisions.items() if len(hashes) > 1}
    return {'path': str(path), 'objects': objects, 'images': images,
            'dependency_errors': issues, 'manual_review': manual,
            'packed_basename_collisions': collisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--strict-objects', action='store_true')
    parser.add_argument('--require-packed', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    reference, candidate, report = (p.resolve() for p in (args.reference, args.candidate, args.report))
    if not reference.is_file() or not candidate.is_file():
        raise FileNotFoundError('Both input blend files must exist')
    if report in {reference, candidate} or report.suffix.lower() != '.json':
        raise ValueError('Report must be a separate JSON path')
    original = snapshot(reference)
    final = snapshot(candidate)
    changes = {name: [key for key in record if final['objects'].get(name, {}).get(key) != record[key]]
               for name, record in original['objects'].items()
               if final['objects'].get(name) != record}
    added = sorted(set(final['objects']) - set(original['objects']))
    errors = list(final['dependency_errors'])
    if args.require_packed:
        errors += [f"{im['name']}: --require-packed failed" for im in final['images'] if not im['packed']]
    result = {
        'blender': bpy.app.version_string, 'reference': str(reference), 'candidate': str(candidate),
        'reference_object_count': len(original['objects']),
        'candidate_object_count': len(final['objects']),
        'geometry_changes': changes, 'added_objects': added,
        'images': final['images'], 'dependency_errors': errors,
        'manual_review': final['manual_review'],
        'packed_basename_collisions': final['packed_basename_collisions'],
        'limits': 'Not a full modifier/animation/shape-key/UCUPaint/optics audit; manual review remains.',
        'pass': not changes and not errors and (not args.strict_objects or not added),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SOURCE_AUDIT', json.dumps({k: result[k] for k in
          ('pass', 'reference_object_count', 'candidate_object_count', 'geometry_changes', 'added_objects', 'dependency_errors')}, ensure_ascii=False), flush=True)
    if not result['pass']:
        raise RuntimeError(f'Source audit failed; see {report}')


if __name__ == '__main__':
    main()
