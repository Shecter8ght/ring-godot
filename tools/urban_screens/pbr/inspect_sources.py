"""Только чтение геометрии всей партии: детали, слоты, размеры и имена."""
from pathlib import Path
import collections
import json
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan import ROOT, prepare

rows = prepare()
report = []
roles = collections.Counter()
for a in rows:
    if a['existing_pbr']:
        continue
    bpy.ops.wm.open_mainfile(filepath=a['source_blend'])
    bpy.context.view_layer.update()
    collection = bpy.data.collections['MODEL | editable components']
    parts = []
    points = []
    for ob in collection.objects:
        if ob.type not in ('MESH', 'CURVE', 'FONT'):
            continue
        role = ob.get('finish_role', '')
        roles[role] += 1
        bbox = [ob.matrix_world @ Vector(p) for p in ob.bound_box]
        points += bbox
        parts.append(dict(name=ob.name, role=role, type=ob.type,
            materials=[m.name if m else '' for m in ob.data.materials],
            dimensions_m=list(ob.dimensions), vertices=len(ob.data.vertices) if ob.type == 'MESH' else None))
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    report.append(dict(id=a['id'], key=a['key'], folder=a['folder'], parts=parts,
        low=low, high=high, dimensions_m=[high[i]-low[i] for i in range(3)]))
    print('SOURCE_INSPECTED', a['id'], len(parts), flush=True)
(ROOT / 'source_inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('INVENTORY_COMPLETE', len(report), dict(roles), flush=True)
