"""Доля попаданий адресов внутри островов игровой развёртки (без полей) по атласам и по классам видимости."""
import json
import sys
import bpy
import numpy as np
sys.path.insert(0, 'E:/Games/RING-godot/tools')
from asset_kit import uv as kit_uv, uv_pack

W = 'E:/Games/RING-godot/_asset_src/veras54_v14/game/'
rec = json.load(open(W + 'lp/parts.json', encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=W + 'lp/VERAS54_Game_LP.blend')
out = {}
for atlas, a in rec['atlases'].items():
    size = a['size']
    hit = np.load(W + f'bake/{atlas}_hit.npz')['set'][::-1] > 0      # строка 0 — низ
    seen, objs = set(), []
    for o in bpy.data.collections['GAME'].all_objects:
        if o.type == 'MESH' and o.get('atlas') == atlas and o.data.name not in seen:
            seen.add(o.data.name)
            objs.append(o)
    cov = {0: np.zeros((size, size), bool), 1: np.zeros((size, size), bool), 2: np.zeros((size, size), bool)}
    for o in objs:
        m = kit_uv._Mesh(o, 'GameUV')
        vis = np.zeros(m.npoly, np.int32)
        o.data.attributes['vis_cls'].data.foreach_get('value', vis)
        for c in (0, 1, 2):
            t = m.tri[(vis[m.tri_poly] == c) & (m.stack[m.tri_poly] == 0)]
            if not len(t):
                continue
            px = m.uv[t] * size
            cov[c] |= uv_pack.raster(px, size, size, eps=0.25)
    res = {}
    for c, nm in ((0, 'visible'), (1, 'roomy'), (2, 'hidden')):
        n = int(cov[c].sum())
        res[nm] = round(float((hit & cov[c]).sum() / max(n, 1)), 4)
    allc = cov[0] | cov[1] | cov[2]
    res['all'] = round(float((hit & allc).sum() / allc.sum()), 4)
    out[atlas] = res
    print('HITCOV', atlas, res, flush=True)
json.dump(out, open(W + 'bake/hit_in_islands.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
