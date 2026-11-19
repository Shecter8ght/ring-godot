"""ВЕРАС-54 v14, игровая сетка: окончательная развёртка (после приёмки сетки владельцем 2026-11-19).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_uv.py -- [--margin 8] [--group 4] [--dry]

Геометрия не меняется: вершины, треугольники, узлы, нормали, швы и жёсткие рёбра — те же (game_lp.py). Острова те же,
что у черновой развёртки (Smart UV + разрезанные «рамки»); перекладывается только их место и масштаб —
tools/asset_kit/uv.py layout с отступами владельца (8 пикс между деталями, 4 внутри детали на 4K; было 12 / 6), теми же
классами видимости (атрибут граней vis_cls) и теми же глазами (от бедра, в прицел), заслоняет — LOD0 в сборе (как при
первой укладке, LOD1 тогда ещё не было).
LOD1 (схлопывание LOD0 с переносом его развёртки) получает новую развёртку тем же движением островов: у каждого острова
LOD0 преобразование «старое место → новое» (подобие, по петлям острова), грань LOD1 — по острову, в котором лежит её
середина в старой развёртке (растр островов с добором 6 пикс).
Прежние файлы — рядом: lp/VERAS54_Game_LP_uv_draft.blend, lp/parts_uv_draft.json (не перезаписываются).
--dry — только укладка и отчёт, без сохранения.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402
from asset_kit import uv_pack  # noqa: E402
import game_lp as G  # noqa: E402

LP = G.OUT / 'VERAS54_Game_LP.blend'
DRAFT = G.OUT / 'VERAS54_Game_LP_uv_draft.blend'
DRAFT_JSON = G.OUT / 'parts_uv_draft.json'
DILATE_PX = 6
# порядок укладки и начальная догадка заполнения по атласам — подобраны опытами с укладчиком на островах из --dump
# (вне Blender): у Body «по длинной стороне» 67,7 % против 59,1 % «по площади» при тех же отступах
PACK = {'Body': dict(order='side', fill_guess=0.72), 'Front': dict(order='side', fill_guess=0.66),
        'Mag': dict(order='area', fill_guess=0.55)}
log = lambda *a: print('VERAS14_UV', *a, flush=True)  # noqa: E731


def arg(name, default):
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return type(default)(a[a.index(name) + 1]) if name in a else default


def label_map(meshes, isl, size):
    """Номер острова в каждом пикселе старой развёртки атласа (−1 — пусто), добран на DILATE_PX."""
    L = np.full((size, size), -1, np.int32)
    for n, i in enumerate(isl):
        m = meshes[i.mi]
        px = m.uv[i.loops] * size
        x0, y0 = int(np.floor(px[:, 0].min())) - 1, int(np.floor(px[:, 1].min())) - 1
        w = int(np.ceil(px[:, 0].max())) - x0 + 2
        h = int(np.ceil(px[:, 1].max())) - y0 + 2
        r = uv_pack.raster((px - (x0, y0))[i.tri_local], w, h)
        ys, xs = np.nonzero(r)
        ys, xs = ys + y0, xs + x0
        ok = (ys >= 0) & (ys < size) & (xs >= 0) & (xs < size)
        L[ys[ok], xs[ok]] = n
    for _ in range(DILATE_PX):
        e = L < 0
        if not e.any():
            break
        cand = L.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s = np.roll(np.roll(L, dy, 0), dx, 1)
            cand = np.where((cand < 0) & (s >= 0), s, cand)
        L = np.where(e, cand, L)
    return L


def fit_affine(a, b):
    """Аффинное a → b (n × 2) по петлям острова; ошибка — наибольшая, в долях UV."""
    A = np.hstack([a, np.ones((len(a), 1))])
    X, *_ = np.linalg.lstsq(A, b, rcond=None)
    return X, float(np.abs(A @ X - b).max()) if len(a) else 0.0


def main():
    margin, group = arg('--margin', 8), arg('--group', 4)
    dry = '--dry' in sys.argv
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    rec = json.loads((G.OUT / 'parts.json').read_text(encoding='utf-8'))
    lod0 = [o for o in bpy.data.collections['GAME'].all_objects if o.type == 'MESH']
    lod1 = [o for o in bpy.data.collections['GAME_LOD1'].all_objects if o.type == 'MESH']
    seen, game = set(), []
    for o in sorted(lod0, key=lambda x: x.name):
        if o.data.name not in seen:
            game.append(o)
            seen.add(o.data.name)
    seen1, lod1u = set(), []
    for o in sorted(lod1, key=lambda x: x.name):
        if o.data.name not in seen1:
            lod1u.append(o)
            seen1.add(o.data.name)
    cls = {o.data.name: G.face_attr_get(o, 'vis_cls') for o in game}
    co_before = {o.data.name: np.array([v.co[:] for v in o.data.vertices]) for o in game + lod1u}
    eyes = [kit_uv.Eye(G.EYE_HIP, name='hip'), kit_uv.Eye(G.EYE_ADS, k_max=kit_uv.ADS_K, name='ads')]
    out = {}
    for atlas, size in G.ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        classes = [cls[o.data.name] for o in objs]
        old_meshes = [kit_uv._Mesh(o, 'GameUV') for o in objs]
        old_isl = kit_uv.islands_of(old_meshes, classes)
        before = kit_uv.report(objs, size, classes=classes)
        rep = kit_uv.layout(objs, size, classes=classes, eyes=eyes, occluders=lod0, log=log, hidden_pool=True,
                            precision=0.004, margin=margin, group_margin=group, **PACK[atlas],
                            dump=str(G.WORK / f'uvdump_{atlas}.npz') if '--dump' in sys.argv else None)
        rep['report'] = kit_uv.report(objs, size, classes=classes)
        rep['verify'] = kit_uv.verify(objs, size, classes=classes, margin=margin, group_margin=group)
        log('атлас', atlas, 'было', before['fill'], before['px_mm_visible'], 'стало', rep['fill'], rep['report']['px_mm_visible'],
            rep['verify'])
        # преобразования островов: старое место → новое
        new_uv = [kit_uv._Mesh(o, 'GameUV').uv for o in objs]
        T, worst = [], 0.0
        for i in old_isl:
            X, e = fit_affine(old_meshes[i.mi].uv[i.loops], new_uv[i.mi][i.loops])
            T.append(X)
            worst = max(worst, e)
        L = label_map(old_meshes, old_isl, size)
        # LOD1 этого атласа
        miss = mixed = faces = 0
        for c in [c for c in lod1u if c['atlas'] == atlas]:
            m = kit_uv._Mesh(c, 'GameUV')
            fc = np.stack([np.bincount(m.poly_of_loop, m.uv[:, k], m.npoly) for k in range(2)], 1) / m.lt[:, None]
            # копии внахлёст у LOD1 стоят на месте хозяина (как у LOD0)
            pxy = np.clip((fc * size).astype(np.int64), 0, size - 1)
            lab = L[pxy[:, 1], pxy[:, 0]]
            lp = np.clip((m.uv * size).astype(np.int64), 0, size - 1)
            ll = L[lp[:, 1], lp[:, 0]]
            for p in np.flatnonzero(lab < 0):
                cand = ll[m.ls[p]:m.ls[p] + m.lt[p]]
                cand = cand[cand >= 0]
                if len(cand):
                    lab[p] = np.bincount(cand).argmax()
            miss += int((lab < 0).sum())
            lab_loop = lab[m.poly_of_loop]
            mixed += int(np.unique(m.poly_of_loop[(ll != lab_loop) & (ll >= 0)]).size)
            faces += m.npoly
            uvn = m.uv.copy()
            A = np.hstack([m.uv, np.ones((len(m.uv), 1))])
            for n in np.unique(lab[lab >= 0]):
                sel = lab_loop == n
                uvn[sel] = A[sel] @ T[n]
            m.write_uv(uvn)
        rep['lod1'] = {'faces': faces, 'without_island': miss, 'faces_on_two_islands': mixed,
                       'island_fit_err_px': round(worst * size, 4)}
        rep['lod1']['report'] = kit_uv.report([c for c in lod1u if c['atlas'] == atlas], size)
        rep['before'] = {k: before[k] for k in ('fill', 'islands', 'islands_small', 'px_mm', 'px_mm_visible', 'px_mm_hidden')}
        rec['atlases'][atlas] = {'size': size, 'objects': [o.name for o in objs], **rep}
        out[atlas] = rep
        log('LOD1', atlas, rep['lod1'])
    # геометрия не тронута
    for o in game + lod1u:
        co = np.array([v.co[:] for v in o.data.vertices])
        assert co.shape == co_before[o.data.name].shape and np.abs(co - co_before[o.data.name]).max() == 0.0, o.name
    rec['uv_final'] = {'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'margin_px': margin, 'group_margin_px': group,
                       'draft_blend': str(DRAFT), 'draft_json': str(DRAFT_JSON), 'geometry_changed': False}
    if dry:
        log('проба, не сохранено', f'{time.time() - t0:.0f} с')
        return
    if not DRAFT.exists():
        shutil.copy2(LP, DRAFT)
        shutil.copy2(G.OUT / 'parts.json', DRAFT_JSON)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(LP), compress=True)
    (G.OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                      newline='\n')
    log('сохранено', LP, {a: (r['fill'], r['report']['px_mm_visible']) for a, r in out.items()}, f'{time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
