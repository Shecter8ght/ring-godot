"""OBJ атласа → по OBJ на объект (вершины перенумерованы) для развёртки RizomUV по частям; join — собрать обратно
в один OBJ атласа в исходном порядке (у не развёрнутых — исходные UV).
python -X utf8 tools/veras54_v14/game/rz_split.py split <in.obj> <папка>
python -X utf8 tools/veras54_v14/game/rz_split.py join <in.obj> <папка> <out.obj>"""
import sys
from pathlib import Path


def parse(path):
    v, vt, objs = [], [], []
    for ln in open(path, encoding='utf-8', errors='replace'):
        if ln.startswith('v '):
            v.append(ln)
        elif ln.startswith('vt '):
            vt.append(ln)
        elif ln.startswith('o '):
            objs.append([ln[2:].strip(), []])
        elif ln.startswith('f '):
            if not objs:
                objs.append(['', []])
            objs[-1][1].append([tuple(int(x) for x in t.split('/')[:2]) for t in ln.split()[1:]])
    return v, vt, objs


def write(path, v, vt, faces):
    vm, tm = {}, {}
    lines_v, lines_t, lines_f = [], [], []
    for f in faces:
        out = []
        for a, b in f:
            if a not in vm:
                vm[a] = len(vm) + 1
                lines_v.append(v[a - 1])
            if b not in tm:
                tm[b] = len(tm) + 1
                lines_t.append(vt[b - 1])
            out.append(f'{vm[a]}/{tm[b]}')
        lines_f.append('f ' + ' '.join(out) + '\n')
    Path(path).write_text(''.join(lines_v + lines_t + lines_f), encoding='utf-8', newline='\n')
    return vm


def main():
    mode, src, d = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    v, vt, objs = parse(src)
    if mode == 'split':
        d.mkdir(parents=True, exist_ok=True)
        for i, (name, faces) in enumerate(objs):
            write(d / f'p{i:02d}_in.obj', v, vt, faces)
            print(i, name, len(faces))
        return
    # join: v исходные, vt — из p<i>_unw.obj (если есть), иначе исходные
    out_vt, out_f = [], []
    for i, (name, faces) in enumerate(objs):
        p = d / f'p{i:02d}_unw.obj'
        if p.exists():
            v2, vt2, objs2 = parse(p)
            f2 = [f for _n, fs in objs2 for f in fs] if objs2 else None
            if f2 is None:
                f2 = []
                for ln in open(p, encoding='utf-8'):
                    if ln.startswith('f '):
                        f2.append([tuple(int(x) for x in t.split('/')[:2]) for t in ln.split()[1:]])
            assert len(f2) == len(faces), (name, len(f2), len(faces))
            base = len(out_vt)
            out_vt += vt2
            # вершины части: по порядку первого появления — как в split
            vm = {}
            for f in faces:
                for a, _b in f:
                    vm.setdefault(a, len(vm) + 1)
            inv = {b: a for a, b in vm.items()}
            for f, g in zip(faces, f2):
                gv = [inv[a] for a, _ in g]
                fv = [a for a, _ in f]
                assert sorted(gv) == sorted(fv), name
                out_f.append((name, [(a, b + base) for (a, b) in zip(gv, [b for _, b in g])]))
            print(i, name, 'RizomUV')
        else:
            base = len(out_vt)
            tm = {}
            for f in faces:
                for _a, b in f:
                    if b not in tm:
                        tm[b] = len(out_vt) + 1
                        out_vt.append(vt[b - 1])
            for f in faces:
                out_f.append((name, [(a, tm[b]) for a, b in f]))
            print(i, name, 'исходные UV')
    lines = list(v) + list(out_vt)
    cur = None
    for name, f in out_f:
        if name != cur:
            lines.append(f'o {name}\n')
            cur = name
        lines.append('f ' + ' '.join(f'{a}/{b}' for a, b in f) + '\n')
    Path(sys.argv[4]).write_text(''.join(lines), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
