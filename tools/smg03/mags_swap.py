"""ИЗЛОМ-45: новые магазины (part_magazine.py, собраны отдельно: build.py -- <магазины.blend> magazine) — в копию
принятой геометрии: остальные детали не пересобираются и остаются как были. Магазины — дочерние Magazine_mover, видимость
13 / 30 — по свойству mag30 пустышки SMG03_Controls (как part_rig.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<ПП-Vector_геометрия_v06.blend>" --python-exit-code 1 --python tools/smg03/mags_swap.py -- <магазины.blend> <выход.blend>
"""
import sys

import bpy

a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
PREFIX = ('Magazine13', 'Magazine30')

old = [o for o in bpy.data.objects if o.name.startswith(PREFIX)]
print('MAGS_SWAP старых', len(old))
for o in old:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

with bpy.data.libraries.load(src) as (fr, to):
    to.objects = [n for n in fr.objects if n.startswith(PREFIX)]
mover = bpy.data.objects['Magazine_mover']
ctrl = bpy.data.objects['SMG03_Controls']
c13 = bpy.data.collections['Magazine']
c30 = bpy.data.collections['Magazine_30']
mats = {m.name: m for m in bpy.data.materials}
n = 0
for o in to.objects:
    if o is None:
        continue
    is30 = o.name.startswith('Magazine30')
    (c30 if is30 else c13).objects.link(o)
    # материалы — прежние по имени (свои копии «Polymer.001» не плодить)
    for slot in o.material_slots:
        if slot.material is not None:
            base = slot.material.name.split('.')[0]
            if base in mats and slot.material is not mats[base]:
                slot.material = mats[base]
    # своя трансформация (у патронов — место в стопке): matrix_world только что подключённого объекта ещё не посчитан
    basis = o.matrix_basis.copy()
    o.parent = mover
    o.matrix_parent_inverse = mover.matrix_world.inverted()
    o.matrix_basis = basis
    for path in ('hide_viewport', 'hide_render'):
        fc = o.driver_add(path)
        d = fc.driver
        d.type = 'SCRIPTED'
        var = d.variables.new()
        var.name = 'mag30'
        var.type = 'SINGLE_PROP'
        var.targets[0].id = ctrl
        var.targets[0].data_path = '["mag30"]'
        d.expression = 'mag30<0.5' if is30 else 'mag30>=0.5'
    n += 1
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
print('MAGS_SWAP новых', n)
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print('MAGS_SWAP_SAVED', out)
