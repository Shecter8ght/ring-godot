"""Мосин 1891/30 ПУ — ретопология игровой сетки той же процедурной сборкой, что и high-poly (build_*.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_retopo.py -- [rifle mount scope ammo]
→ _asset_src/mosin_pu_game/lr/Mosin_LR_<часть>.blend (не в git); дальше game_lp.py (вариант fp) берёт детали отсюда,
а не упрощением high-poly.

Сборка идёт теми же функциями формы (исходники и принятые high-poly не меняются), с подменами на время прогона:
- каждая сетка-решётка сразу после построения (mosin_lib.mesh_object: тела вращения, лофты, протяжки, выдавливания)
  теряет лишние петли — retopo_lib.loop_reduce с допуском детали: у глаза строже (затвор, коробка, шейка ложи, крепёж,
  прицел), вдали мягче (ствол, цевьё, накладка); сетка остаётся четырёхугольной, кольца и образующие ровные;
- клейма и цифры шкалы не врезаются (стенки букв — в карте нормалей с high-poly);
- фаски (модификаторы Bevel) снимаются: острое ребро игровой сетки — шов и жёсткое ребро, фаска приходит запеканием;
- накатка крышек барабанов прицела — гладкий диск (рифление — в карте нормалей).
Булевы вырезы (окна коробки, магазин и пазы в ложе, гнёзда винтов) режутся по уже облегчённым сеткам.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402
import retopo_lib as RT  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '_asset_src/mosin_pu_game/lr'
OUT.mkdir(parents=True, exist_ok=True)
PARTS = (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) or ['rifle', 'mount', 'scope', 'ammo']
log = lambda *a: print('MOSIN_RETOPO', *a, flush=True)

MM = 0.001
# допуск отклонения петли, мм: у глаза (шейка, гребень, коробка, затвор, начало накладки; x −380…+170 мм в осях
# винтовки, как EYE_X game_lp) — строже; переход за 150 мм
EYE_X = (-0.38, 0.17)
EYE_FALL = 0.15
TOL = {   # деталь (начало имени) → (у глаза, вдали), мм. Снимаемая вершина отходит от хорды соседей примерно вчетверо
    # дальше, чем потом прогиб оставшейся грани: допуск 0,12 даёт прогиб ~0,03 мм
    'Stock': (0.3, 0.6), 'Handguard': (0.3, 0.4), 'Barrel': (0.15, 0.3), 'CleaningRod': (0.2, 0.35),
    'Band': (0.2, 0.35), 'Handguard_Ferrule': (0.2, 0.3), 'Stock_NoseCap': (0.25, 0.25),
    'FrontSight': (0.25, 0.25), 'RearSight': (0.1, 0.12),
    'Bolt_Handle_Ball': (0.12, 0.12), 'Bolt_Knob': (0.1, 0.1), 'Bolt_Handle': (0.1, 0.1),
    'Bolt': (0.1, 0.1), 'Receiver': (0.1, 0.1), 'Magazine': (0.1, 0.15), 'Trigger': (0.1, 0.1),
    'Buttplate': (0.2, 0.25), 'Sling_Escutcheon': (0.2, 0.25),
    'Receiver_TangScrew': (0.07, 0.07), 'Stock_CrossScrew': (0.08, 0.08), 'Buttplate_Screw': (0.15, 0.15),
    'Magazine_FrontScrew': (0.15, 0.15),
    'Mount_LockScrew': (0.2, 0.2), 'Mount_RingScrew': (0.08, 0.08), 'Mount_Base_Screw': (0.08, 0.08),
    'Mount': (0.1, 0.1),
    'Scope_Lens': (0.25, 0.25), 'Scope_TurretElev_CapScrew': (0.1, 0.1), 'Scope_TurretWind_CapScrew': (0.1, 0.1),
    'Scope_Turret': (0.12, 0.12), 'Scope': (0.08, 0.08),
    'Cartridge': (0.1, 0.1),
    # резаки: видимые края вырезов — как у детали; каналы внутри дерева и металла — грубо
    'cut_channel': (0.6, 0.6), 'cut_rod': (0.6, 0.6), 'cut_hg': (0.6, 0.6), 'cut_cap': (0.6, 0.6),
    'cut_bore': (0.4, 0.4), 'cut_rodhole': (0.3, 0.3), 'cut_': (0.12, 0.25),
}
DEFAULT_TOL = (0.12, 0.25)
MAX_LEN = {'Stock': 0.16, 'Handguard': 0.16, 'Barrel': 0.2, 'CleaningRod': 0.2}
SKIP_REDUCE = ('cut_stamp', 'cut_scale', 'Scope_Reticle')
SKIP_BOOLEAN = ('cut_stamp', 'cut_scale')
STATS: dict = {}
_rifle_axes = True                       # допуск по x — только у деталей винтовки (у прицела и крепления — свои оси)


def tol_pair(name: str):
    best = None
    for k, v in TOL.items():
        if name.startswith(k) and (best is None or len(k) > len(best)):
            best = k
    return TOL[best] if best else DEFAULT_TOL


def tol_fn(name: str):
    near, far = tol_pair(name)
    if not _rifle_axes or near == far:
        return lambda co, t=far if not _rifle_axes else near: t * MM
    def f(co):
        out = max(EYE_X[0] - co.x, co.x - EYE_X[1], 0.0)
        k = min(1.0, out / EYE_FALL)
        return (near + (far - near) * k) * MM
    return f


def max_len(name: str) -> float:
    for k, v in MAX_LEN.items():
        if name.startswith(k):
            return v
    return 0.06


_orig_mesh_object = L.mesh_object
_orig_boolean = L.boolean


def mesh_object(name, verts, faces, mat=None, col=None, smooth_angle=35.0, face_mats=None):
    ob = _orig_mesh_object(name, verts, faces, mat, col, smooth_angle, face_mats)
    if not name.startswith(SKIP_REDUCE):
        before = len(ob.data.polygons)
        n = RT.loop_reduce(ob.data, tol_fn(name), max_len(name))
        bad = RT.non_manifold(ob.data)
        if bad:
            log('NON_MANIFOLD', name, bad)
        STATS.setdefault(name, []).append((before, len(ob.data.polygons), n))
    return ob


def boolean(target, cutter, op='DIFFERENCE', solver='EXACT', apply=True, remove_cutter=True, self_intersect=False):
    if cutter.name.startswith(SKIP_BOOLEAN):
        bpy.data.objects.remove(cutter, do_unlink=True)
        return
    before = len(target.data.polygons)
    cname = cutter.name
    keep = target.data.copy()
    _orig_boolean(target, cutter, op, solver, apply, False, self_intersect)
    after = len(target.data.polygons)
    if after < before * 0.5:
        # на облегчённой ложе точная булева местами считает тело вывернутым (паз хвостовика съедал её целиком) —
        # тогда заново быстрым решателем (FLOAT). «Самопересечения» точного тут не годятся: оставляли под поверхностью
        # ложи второй слой граней, лучи видимости game_lp считали такие грани прижатыми и удаляли — в ложе дыры
        old = target.data
        target.data = keep
        bpy.data.meshes.remove(old)
        keep = None
        _orig_boolean(target, cutter, op, 'FLOAT', apply, False, self_intersect)
        log('BOOL_RETRY_FLOAT', target.name, cname, before, '→', after, '→', len(target.data.polygons))
        after = len(target.data.polygons)
    if keep is not None:
        bpy.data.meshes.remove(keep)
    if remove_cutter and cutter.name in bpy.data.objects:
        bpy.data.objects.remove(cutter, do_unlink=True)
    if after < before * 0.5:
        log('BOOL_COLLAPSE', target.name, cname, op, before, '→', after)
    if target.name in os.environ.get('MOSIN_RETOPO_DEBUG', '').split(','):
        log('BOOL', target.name, cname, op, before, '→', after)


L.mesh_object = mesh_object
L.boolean = boolean
# триангуляция нужна была только перед врезкой клейм (точная булева на больших n-угольниках); клейм нет — сетка
# остаётся из четырёхугольников
L.triangulate = lambda ob: None


# длинные грани тел вращения (конус ствола и канал — одна грань на 64 см, шомпол — 67 см) режутся кольцами поперёк оси:
# иначе развёртку не разрезать на отрезки (остров длиннее атласа ужимает весь атлас), а лучи видимости из дула метят
# весь канал видимым. x — оси винтовки, м; 0,25 и 0,47 — швы развёртки под накладкой (game_uv.CUTS)
BISECT_X = {'Barrel': (0.12, 0.25, 0.36, 0.47, 0.58, 0.68), 'CleaningRod': (0.15, 0.25, 0.36, 0.47, 0.58)}


def bisect(o, xs) -> None:
    import bmesh
    from mathutils import Vector
    bm = bmesh.new()
    bm.from_mesh(o.data)
    inv = o.matrix_world.inverted()
    for x in xs:
        co = inv @ Vector((x, 0.0, 0.0))
        no = (inv.to_3x3().transposed() @ Vector((1.0, 0.0, 0.0))).normalized()
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-6)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def finish(path: Path) -> None:
    """Снять фаски, порезать длинные грани, сохранить."""
    for o in bpy.data.objects:
        for m in list(o.modifiers):
            if m.type == 'BEVEL':
                o.modifiers.remove(m)
        if o.type == 'MESH' and o.name in BISECT_X:
            bisect(o, BISECT_X[o.name])
    tris = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles()
            k = len(o.data.loop_triangles)
            tris += k
            q = sum(1 for p in o.data.polygons if len(p.vertices) == 4) / max(1, len(o.data.polygons))
            log('part', o.name, k, 'tris', f'quads {q:.0%}')
    log('total', path.name, tris)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    log('SAVED', path)


def knurl_plain(name, r, h, z0, teeth=60, depth=0.28, seg_per=3, mat='Scope_Body', col=None):
    """Крышка барабана без рифления: гладкий диск по наружному радиусу (рифление — в карте нормалей)."""
    ob = L.lathe(name, [(z0, 0.0), (z0, r), (z0 + h, r), (z0 + h, 0.0)], 96, mat, col, axis='Z')
    L.bevel_mod(ob, 0.35, 2, 50)
    return ob


bpy.context.preferences.use_preferences_save = False
for part in PARTS:
    STATS.clear()
    _rifle_axes = part == 'rifle'
    if part == 'rifle':
        import build_rifle as B
        # ложа: сечения реже и меньше точек (у high-poly 280 точек и шаг 0,4…4 мм) — дальше снимает loop_reduce
        B.STOCK_SEC = 64
        B.STOCK_STEP_K = 4.0
    elif part == 'mount':
        import build_mount as B
    elif part == 'scope':
        import build_scope as B
        B.knurl_disc = knurl_plain
    else:
        import build_cartridge as B
    target = OUT / f'Mosin_LR_{part}.blend'
    L.save_blend = lambda p, t=target: finish(t)
    B.build()
    for name, rows in sorted(STATS.items()):
        if not name.startswith('cut_'):
            log('reduce', name, ' '.join(f'{a}→{b} ({n} петель)' for a, b, n in rows))
