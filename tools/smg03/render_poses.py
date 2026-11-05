"""ИЗЛОМ-45: позы подвижных деталей для рендеров игровой сетки — с органов управления исходника (SMG03_Controls,
part_rig.py). Для каждой позы — мировая дельта каждого мовера относительно покоя (как game_lp.control_poses), узлы
игровой сетки — те же (game_lp.MOVERS) → JSON {поза: {узел: матрица 4×4 построчно}}.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<ПП-Vector_геометрия_v06.blend>" --python-exit-code 1 --python tools/smg03/render_poses.py -- <выход.json>
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from game_lp import CONTROLS, MOVERS  # noqa: E402

# позы рендеров (владелец 2026-11-05: «в статике, с отведённым затвором, со сложенным прикладом, во время стрельбы»)
POSES = {
    'static': {'safety': 1.0},
    'bolt_back': {'bolt_catch': 1.0, 'safety': 1.0},
    'folded': {'stock_fold': 1.0, 'safety': 1.0},
    'firing': {'bolt': 0.55, 'trigger': 1.0, 'selector': 1.0},
    'firing_bolt': {'bolt': 1.0, 'trigger': 1.0, 'selector': 1.0},
}


def refresh():
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    ctl = bpy.data.objects[CONTROLS]
    movers = {n: bpy.data.objects[n] for n in MOVERS if n in bpy.data.objects}
    base = {k: ctl[k] for k in ctl.keys() if not k.startswith('_')}
    dg = refresh()
    rest = {n: o.evaluated_get(dg).matrix_world.copy() for n, o in movers.items()}
    res = {}
    for pose, props in POSES.items():
        for k, v in base.items():
            ctl[k] = v
        for k, v in props.items():
            ctl[k] = v
        ctl.update_tag()
        dg = refresh()
        moved = {}
        for n, o in movers.items():
            d = o.evaluated_get(dg).matrix_world @ rest[n].inverted()
            if d.translation.length > 1e-6 or abs(d.to_quaternion().angle) > 1e-5:
                moved[MOVERS[n]] = [list(r) for r in d]
        res[pose] = moved
        print('POSE', pose, sorted(moved))
    for k, v in base.items():
        ctl[k] = v
    Path(out).write_text(json.dumps(res, indent=1), encoding='utf-8')
    print('POSES_SAVED', out)


if __name__ == '__main__':
    main()
