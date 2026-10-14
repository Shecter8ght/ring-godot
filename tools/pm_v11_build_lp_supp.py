"""Глушитель ПМ 60% → деталь Suppressor в lp/PM_Game_LP_v01.blend (остальные детали и их развёртки не трогаются).

Посадка на ствол: оси suppressor_v2 (ось +Y от переходника) → сцена ПМ: поворот +90° вокруг Z,
переходник у x = −79.22 мм, ось канала z = 112.53 мм (совпадает с глушителем в v11).
Насечка втулки — только источник запекания нормалей.
"""
from pathlib import Path
import json, math, importlib.util
import bpy, bmesh
from mathutils import Matrix

REV = Path(__file__).resolve().parents[1] / '_asset_src/pm_game'   # рабочая папка ассета (не в git)
SRC = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/19_Магазины_и_патрон_60_v01/01_Модели/suppressor_60_v01.blend')
SEAT = Matrix.Translation((-0.07922, 0.0, 0.11253)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
src_text = Path(__file__).with_name('pm_v11_build_lp.py').read_text(encoding='utf-8')
# берём только вспомогательные функции сборщика (без запуска его основной части)
helpers = src_text[:src_text.index("bpy.context.preferences.use_preferences_save = False")]
ns = {'__file__': str(Path(__file__).with_name('pm_v11_build_lp.py'))}
exec(compile(helpers, 'build_lp_helpers', 'exec'), ns)

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(REV / 'lp/PM_Game_LP_v01.blend'))
S = bpy.context.scene
lp = bpy.data.collections['PM_GAME_LP']
for o in list(bpy.data.objects):
    if o.name in ('Suppressor', 'Suppressor_Mesh'):
        bpy.data.objects.remove(o, do_unlink=True)
with bpy.data.libraries.load(str(SRC), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith('Suppressor |')]
supp_names = [o.name for o in dst.objects]
tmp = bpy.data.collections.new('SUPP_TMP')
S.collection.children.link(tmp)
for o in dst.objects:
    tmp.objects.link(o)
    o.parent = None
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
copies = []
for i, o in enumerate(dst.objects):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(SEAT @ eo.matrix_world)
    copies.append(bpy.data.objects.new(f'Supp_{i}', me))
low = ns['join'](copies, 'Suppressor_Mesh', lp)
before = ns['tris'](low.data)
after = ns['simplify'](low, 1600)
ns['unwrap']([low], 0.004)
mat = bpy.data.materials.get('GAME • Suppressor • 60') or bpy.data.materials.new('GAME • Suppressor • 60')
mat.use_nodes = True
low.data.materials.append(mat)
PM = bpy.data.objects['PM']
node = bpy.data.objects.new('Suppressor', None)
lp.objects.link(node)
node.empty_display_size = 0.006
node.parent = PM
node.matrix_world = Matrix.Translation((-0.08065, 0.0, 0.11253))   # точка посадки (как у v5)
bpy.context.view_layer.update()
w = low.matrix_world.copy()
low.parent = node
low.matrix_parent_inverse = node.matrix_world.inverted()
low.matrix_world = w
for c in list(bpy.data.collections):
    if c.name == 'SUPP_TMP':
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
bpy.ops.outliner.orphans_purge(do_recursive=True)
rec_path = REV / 'lp/parts.json'
rec = json.loads(rec_path.read_text(encoding='utf-8'))
rec['parts']['Suppressor'] = supp_names + ['Highpoly | visible crossed micro knurl']
rec['atlas']['Suppressor'] = ['Suppressor']
rec['materials']['Suppressor'] = 'GAME • Suppressor • 60'
rec['suppressor_seat'] = [list(r) for r in SEAT]
rec['meshes']['Suppressor_Mesh'] = after
rec_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(REV / 'lp/PM_Game_LP_v01.blend'))
print('PM_LP_SUPP', before, '->', after, 'px/mm', ns['texel_report']([low], 1024), flush=True)
