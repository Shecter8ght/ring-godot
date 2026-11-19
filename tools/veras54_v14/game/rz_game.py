"""ВЕРАС-54 v14, игровая сетка: проба RizomUV (две попытки по слову владельца 19.11) и замеры развёрток для сравнения.
Геометрия принятой сетки не меняется: работа на копии этапа (VERAS54_Game_LP_stage.blend), результаты — в рабочей папке.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/rz_game.py -- <режим> [метка]
  export A    — наши острова (Smart UV + разрезание «рамок»), наша плотность (видимость, глаз) → rizom/A_<атлас>_in.obj
                для укладки в RizomUV без изменения масштаба (попытка А, rz_run.py, задание job_A.json)
  export B    — геометрия LOD0 по атласам в мм → rizom/B_<атлас>_in.obj для развёртки RizomUV целиком (попытка Б)
  import A    — укладка RizomUV → UV сетки, вписать в квадрат с отступом, замер → rizom/VERAS54_uv_A.blend
  ours B      — развёртка RizomUV (B_<атлас>_unw.obj) → наше разрезание «рамок» и наш укладчик → VERAS54_uv_Bour.blend
  export Bp   — острова развёртки RizomUV с нашей плотностью → rizom/Bp_<атлас>_in.obj (укладка RizomUV)
  import Bp   — укладка RizomUV островов Б → VERAS54_uv_Bp.blend
  base        — замер текущей развёртки (lp/VERAS54_Game_LP.blend)
Каждый замер — rizom/metrics_<метка>.json и картинки раскладок rizom/png/<метка>_<атлас>.png.
Соответствие OBJ: вершины и грани пишутся по порядку объектов атласа, RizomUV порядок сохраняет (Load без AutoWeld).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import game_lp as G  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402
from asset_kit import uv_pack  # noqa: E402

RZ = G.WORK / 'rizom'
PNG = RZ / 'png'
MARGIN = kit_uv.MARGIN_PX
log = lambda *a: print('VERAS14_RZ', *a, flush=True)  # noqa: E731


# ---------------------------------------------------------------------------------------------- сцена
def load(path: Path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    for c in [c for c in bpy.data.collections if c.name.startswith('GAME_LOD1')]:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
    seen, game = set(), []
    for o in sorted(objs, key=lambda x: x.name):
        if o.data.name not in seen:
            game.append(o)
        seen.add(o.data.name)
    cls = {o.data.name: G.face_attr_get(o, 'vis_cls') for o in game}
    G.refresh()
    return game, cls


def by_atlas(game):
    return {a: [o for o in game if o['atlas'] == a] for a in G.ATLAS_SIZE}


def eyes():
    return [kit_uv.Eye(G.EYE_HIP, name='hip'), kit_uv.Eye(G.EYE_ADS, k_max=kit_uv.ADS_K, name='ads')]


# ---------------------------------------------------------------------------------------------- OBJ
def write_obj(path: Path, objs, uvs: list, scale: float = 1.0) -> dict:
    """Сетки objs (мировые оси × scale) с развёрткой uvs (по петлям). vt общие у петель одной вершины с той же UV —
    так RizomUV видит острова. Возврат — карта для обратного чтения."""
    lines = []
    vbase = 0
    vt_all = []
    faces_meta = []
    for o, uv in zip(objs, uvs):
        m = kit_uv._Mesh(o, 'GameUV')
        for p in m.co * scale:
            lines.append(f'v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}')
        q = np.round(uv * 2 ** 24).astype(np.int64)
        key = np.stack([m.lv.astype(np.int64), q[:, 0], q[:, 1]], 1)
        _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel()
        base = len(vt_all) and sum(len(x) for x in vt_all)
        vt_all.append(uv[first])
        vti = inv + base
        fl = []
        for pi in range(m.npoly):
            ls = range(m.ls[pi], m.ls[pi] + m.lt[pi])
            fl.append('f ' + ' '.join(f'{m.lv[l] + 1 + vbase}/{vti[l] + 1}' for l in ls))
        faces_meta.append(dict(name=o.name, nv=len(m.co), npoly=m.npoly, nloop=len(m.lv)))
        lines.append(f'o {o.name.replace(".", "_")}')
        lines += fl
        vbase += len(m.co)
    vt = np.concatenate(vt_all)
    head = [f'vt {u:.9f} {v:.9f}' for u, v in vt]
    # вершины, затем vt, затем грани по объектам
    vs = [x for x in lines if x.startswith('v ')]
    rest = [x for x in lines if not x.startswith('v ')]
    path.write_text('\n'.join(vs + head + rest) + '\n', encoding='utf-8', newline='\n')
    return dict(objects=faces_meta, scale=scale)


def read_obj_uv(path: Path, objs) -> list:
    """UV по петлям объектов из OBJ RizomUV; грани и вершины сверяются с сеткой (порядок сохраняется)."""
    vt, faces = [], []
    with open(path, encoding='utf-8', errors='replace') as f:
        for ln in f:
            if ln.startswith('vt '):
                p = ln.split()
                vt.append((float(p[1]), float(p[2])))
            elif ln.startswith('f '):
                faces.append([tuple(int(x) if x else 0 for x in t.split('/')[:2]) for t in ln.split()[1:]])
    vt = np.array(vt)
    out = []
    fi = 0
    vbase = 0
    bad = 0
    for o in objs:
        m = kit_uv._Mesh(o, 'GameUV')
        uv = np.zeros((len(m.lv), 2))
        for pi in range(m.npoly):
            f = faces[fi]
            fi += 1
            ls = list(range(m.ls[pi], m.ls[pi] + m.lt[pi]))
            vids = [m.lv[l] + 1 + vbase for l in ls]
            fv = [t[0] for t in f]
            if fv != vids:
                # тот же треугольник с другого угла
                k = fv.index(vids[0]) if vids[0] in fv else -1
                if k < 0 or fv[k:] + fv[:k] != vids:
                    bad += 1
                    continue
                f = f[k:] + f[:k]
            for l, t in zip(ls, f):
                uv[l] = vt[t[1] - 1]
        out.append(uv)
        vbase += len(m.co)
    if fi != len(faces) or bad:
        raise RuntimeError(f'{path.name}: граней в OBJ {len(faces)}, прочитано {fi}, не совпало {bad}')
    return out


# ---------------------------------------------------------------------------------------------- острова с нашей плотностью
def scaled_islands(objs, classes) -> list:
    """Острова как в kit_uv.layout: по классам видимости, в метрах, множитель стороны k, поворот к наименьшему
    прямоугольнику; разложены рядами без наложений (для укладки в RizomUV без изменения масштаба). Возврат — UV по петлям."""
    meshes = [kit_uv._Mesh(o, 'GameUV') for o in objs]
    isl = kit_uv.islands_of(meshes, classes)
    for i in isl:
        c = classes[i.mi][i.polys]
        a = meshes[i.mi].poly_a3[i.polys]
        i.cls = int(max(kit_uv.CLASS_K, key=lambda k: float(a[c == k].sum())))
    ef = kit_uv.eye_factors(objs, eyes())
    for i in isl:
        m = meshes[i.mi]
        if i.cls != kit_uv.VISIBLE:
            i.k = kit_uv.CLASS_K[i.cls]
        else:
            a = m.poly_a3[i.polys]
            i.k = float((ef['k'][i.mi][i.polys] * a).sum() / max(a.sum(), 1e-30))
        i.to_metres(m)
    out = [m.uv.copy() for m in meshes]
    row_w = math.sqrt(sum(i.a3 * i.k ** 2 for i in isl)) * 1.6
    x = y = rh = 0.0
    gap = 0.002
    for i in sorted(isl, key=lambda i: -i.ext[1] * i.k):
        w, h = i.ext[0] * i.k, i.ext[1] * i.k
        if x + w > row_w and x > 0:
            x, y, rh = 0.0, y + rh + gap, 0.0
        out[i.mi][i.loops] = i.uvm * i.k + (x, y)
        x += w + gap
        rh = max(rh, h)
    log('островов', len(isl), 'ряд', round(row_w, 3))
    return out


def fit_square(objs, uvs, size: int) -> None:
    """Укладка RizomUV (без масштаба после) → равномерно вписать в квадрат с полуотступом у края, записать GameUV;
    каждый остров — своя группа (между всеми — полный отступ)."""
    allp = np.concatenate(uvs)
    lo, hi = allp.min(0), allp.max(0)
    r1 = (MARGIN + 1) // 2
    s = (1.0 - 2 * (r1 + 1) / size) / float((hi - lo).max())
    for o, uv in zip(objs, uvs):
        m = kit_uv._Mesh(o, 'GameUV')
        m.write_uv((uv - lo) * s + (r1 + 1) / size)
    for o in objs:
        m = kit_uv._Mesh(o, 'GameUV')
        grp = np.zeros(m.npoly, np.int32)
        for n, polys in enumerate(kit_uv._poly_islands(m)):
            grp[polys] = n + 1
        me = o.data
        for nm, val in (('uv_group', grp), ('uv_stack', np.zeros(m.npoly, np.int32))):
            at = me.attributes.get(nm) or me.attributes.new(nm, 'INT', 'FACE')
            at.data.foreach_set('value', val)
    log('вписано: масштаб', round(s, 5))


# ---------------------------------------------------------------------------------------------- замеры
def distortion(objs) -> dict:
    """Растяжение по треугольникам против плотности своего острова: площадь (|ln r|, доля вне 0,64–1,44 по площади) и
    углы (σ1/σ2 якобиана 3D → UV: среднее, доля > 1,25). Веса — площадь в 3D."""
    A = Lr = Sa = Cn = Sc = 0.0
    for o in objs:
        m = kit_uv._Mesh(o, 'GameUV')
        p = m.co[m.lv[m.tri]]
        q = m.uv[m.tri]
        e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        l1 = np.linalg.norm(e1, axis=1)
        ok = l1 > 1e-12
        x = e1 / np.maximum(l1, 1e-30)[:, None]
        nrm = np.cross(e1, e2)
        y = np.cross(nrm, e1)
        y /= np.maximum(np.linalg.norm(y, axis=1), 1e-30)[:, None]
        P = np.stack([np.stack([l1, np.zeros_like(l1)], 1), np.stack([(e2 * x).sum(1), (e2 * y).sum(1)], 1)], 2)
        Q = np.stack([q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]], 2)
        det = P[:, 0, 0] * P[:, 1, 1] - P[:, 0, 1] * P[:, 1, 0]
        ok &= np.abs(det) > 1e-18
        Pi = np.zeros_like(P)
        Pi[ok] = np.linalg.inv(P[ok])
        J = Q @ Pi
        sv = np.linalg.svd(J, compute_uv=False)
        a3 = m.tri_a3
        a2 = np.abs(m.tri_a2s)
        # плотность острова
        dens = np.zeros(len(a3))
        for polys in kit_uv._poly_islands(m):
            tr = kit_uv._ranges(m.tri_start[polys], m.tri_start[polys + 1] - m.tri_start[polys])
            dens[tr] = a2[tr].sum() / max(a3[tr].sum(), 1e-30)
        r = (sv[:, 0] * sv[:, 1]) / np.maximum(dens, 1e-30)
        cn = sv[:, 0] / np.maximum(sv[:, 1], 1e-30)
        w = np.where(ok & (a3 > 0) & (r > 0), a3, 0.0)
        A += w.sum()
        Lr += (w * np.abs(np.log(np.maximum(r, 1e-9)))).sum()
        Sa += w[(r < 0.64) | (r > 1.44)].sum()
        Cn += (w * np.minimum(cn, 10.0)).sum()
        Sc += w[cn > 1.25].sum()
    return dict(area_log_mean=round(Lr / A, 4), area_out_share=round(Sa / A, 4), angle_ratio_mean=round(Cn / A, 4),
                angle_over_1_25_share=round(Sc / A, 4))


def png(objs, size: int, path: Path, classes, res: int = 2048) -> None:
    """Раскладка картинкой: острова цветом (скрытые — тусклее), фон тёмный."""
    img = np.full((res, res, 4), (0.06, 0.06, 0.07, 1.0), np.float32)
    rng = np.random.default_rng(7)
    k = res / size
    for oi, o in enumerate(objs):
        m = kit_uv._Mesh(o, 'GameUV')
        for polys in kit_uv._poly_islands(m):
            tr = kit_uv._ranges(m.tri_start[polys], m.tri_start[polys + 1] - m.tri_start[polys])
            px = m.uv[m.tri[tr]] * res
            x0, y0 = int(max(0, math.floor(px[..., 0].min()))), int(max(0, math.floor(px[..., 1].min())))
            x1, y1 = int(min(res, math.ceil(px[..., 0].max()) + 1)), int(min(res, math.ceil(px[..., 1].max()) + 1))
            if x1 <= x0 or y1 <= y0:
                continue
            msk = uv_pack.raster(px - (x0, y0), x1 - x0, y1 - y0)
            col = 0.35 + 0.6 * rng.random(3)
            if (classes[oi][polys] != kit_uv.VISIBLE).mean() > 0.5:
                col *= 0.35
            sub = img[y0:y1, x0:x1]
            sub[msk, :3] = col
    del k
    im = bpy.data.images.new(path.stem, res, res, alpha=True)
    im.pixels.foreach_set(img.ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def measure(tag: str, game, cls) -> dict:
    PNG.mkdir(parents=True, exist_ok=True)
    out = {}
    for atlas, objs in by_atlas(game).items():
        size = G.ATLAS_SIZE[atlas]
        classes = [cls[o.data.name] for o in objs]
        rep = kit_uv.report(objs, size, classes=classes)
        ver = kit_uv.verify(objs, size, classes=classes)
        dist = distortion(objs)
        out[atlas] = dict(size=size, report=rep, verify=ver, distortion=dist)
        png(objs, size, PNG / f'{tag}_{atlas}.png', classes)
        log(tag, atlas, rep, ver, dist)
    (RZ / f'metrics_{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    return out


def save(tag: str) -> None:
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(RZ / f'VERAS54_uv_{tag}.blend'), compress=True)


# ---------------------------------------------------------------------------------------------- режимы
def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    mode, tag = argv[0], (argv[1] if len(argv) > 1 else '')
    RZ.mkdir(parents=True, exist_ok=True)
    stage = G.OUT / 'VERAS54_Game_LP_stage.blend'
    if mode == 'base':
        game, cls = load(G.OUT / 'VERAS54_Game_LP.blend')
        measure('base', game, cls)
        return
    game, cls = load(stage)
    groups = by_atlas(game)
    if mode == 'export' and tag == 'A':
        maps = {}
        for atlas, objs in groups.items():
            G.split_sparse(objs)
            uvs = scaled_islands(objs, [cls[o.data.name] for o in objs])
            maps[atlas] = write_obj(RZ / f'A_{atlas}_in.obj', objs, uvs)
        (RZ / 'A_map.json').write_text(json.dumps(maps, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    elif mode == 'export' and tag == 'B':
        for atlas, objs in groups.items():
            write_obj(RZ / f'B_{atlas}_in.obj', objs, [kit_uv._Mesh(o, 'GameUV').uv for o in objs], scale=1000.0)
    elif mode == 'export' and tag == 'Bp':
        for atlas, objs in groups.items():
            uvs = read_obj_uv(RZ / f'B_{atlas}_unw.obj', objs)
            for o, uv in zip(objs, uvs):
                kit_uv._Mesh(o, 'GameUV').write_uv(uv)
            G.split_sparse(objs)
            uvs = scaled_islands(objs, [cls[o.data.name] for o in objs])
            write_obj(RZ / f'Bp_{atlas}_in.obj', objs, uvs)
    elif mode == 'import':
        for atlas, objs in groups.items():
            uvs = read_obj_uv(RZ / f'{tag}_{atlas}_out.obj', objs)
            fit_square(objs, uvs, G.ATLAS_SIZE[atlas])
        measure(tag, game, cls)
        save(tag)
    elif mode == 'ours' and tag == 'B':
        rep_all = {}
        for atlas, objs in groups.items():
            uvs = read_obj_uv(RZ / f'B_{atlas}_unw.obj', objs)
            for o, uv in zip(objs, uvs):
                kit_uv._Mesh(o, 'GameUV').write_uv(uv)
            G.split_sparse(objs)
            classes = [cls[o.data.name] for o in objs]
            rep = kit_uv.layout(objs, G.ATLAS_SIZE[atlas], classes=classes, eyes=eyes(), log=log, hidden_pool=True,
                                precision=0.004)
            rep_all[atlas] = {k: v for k, v in rep.items() if k not in ('eyes', 'tries')}
        (RZ / 'layout_Bour.json').write_text(json.dumps(rep_all, ensure_ascii=False, indent=1), encoding='utf-8',
                                             newline='\n')
        measure('Bour', game, cls)
        save('Bour')
    else:
        raise SystemExit(f'неизвестный режим {mode} {tag}')


if __name__ == '__main__':
    main()
