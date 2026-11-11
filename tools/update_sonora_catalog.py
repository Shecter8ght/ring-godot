"""Migrate the owner's surface list and fill missing model/map sound cards.

Idempotent; keeps existing recordings and per-event fields. Back up the registry first.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8-sig'))


def write(name, value):
    (ROOT / 'data' / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


STEPS = [
    ('step_concrete', 'Шаг по бетону и асфальту', ['concrete', 'asphalt']),
    ('ladder_step', 'Шаг по вертикальной лестнице', ['ladder']),
    ('step_gravel', 'Шаг по гравию и камушкам', ['gravel', 'rubble']),
    ('step_dirt', 'Шаг по грунту', ['dirt', 'mud', 'snow']),
    ('step_wood', 'Шаг по дереву', ['wood']),
    ('step_carpet', 'Шаг по ковру', ['carpet', 'fabric']),
    ('step_metal', 'Шаг по металлу', ['metal']),
    ('step_sand', 'Шаг по песку', ['sand']),
    ('step_stone', 'Шаг по плитке', ['tile']),
    ('step_grass', 'Шаг по листьям', ['leaves', 'grass']),
    ('step_water', 'Шаг по лужам', ['water', 'puddle']),
    ('step_trash', 'Шаг по мусорным пакетам', ['trash', 'trash_bags', 'plastic', 'cardboard']),
    ('step_glass', 'Шаг по стеклу', ['glass']),
]
CASINGS = [
    ('concrete', 'бетон и асфальт', ['concrete', 'asphalt']),
    ('water', 'вода', ['water', 'puddle']),
    ('gravel', 'гравий', ['gravel', 'rubble']),
    ('wood', 'дерево', ['wood']),
    ('carpet', 'ковёр', ['carpet', 'fabric']),
    ('metal', 'металл', ['metal']),
    ('sand', 'песок', ['sand', 'dirt', 'mud', 'snow', 'grass', 'leaves', 'trash', 'trash_bags', 'plastic', 'cardboard']),
    ('tile', 'плитка', ['tile', 'glass']),
]


def applies(slot, w):
    condition = slot.get('condition', 'all')
    return {
        'not_integrally_suppressed': not w.get('integral', {}).get('suppressed', False),
        'suppressible': bool(w.get('integral', {}).get('suppressed')) or 'muzzle' in w.get('mounts', {}),
        'detachable_mag': 'internal_mag' not in w,
        'internal_mag': 'internal_mag' in w,
        'manual_cycle': bool(w.get('cycle_sound')),
        'break_action': w.get('action') == 'break',
        'not_break_action': w.get('action') != 'break',
        'automatic': bool(w.get('stats', {}).get('auto')),
        'rig_suppressor': 'suppressor' in w.get('rig', {}) and 'muzzle' in w.get('mounts', {}),
        'ejects_case': w.get('class') != 'SPECIAL',
    }.get(condition, True)


def main():
    registry, actions, slots = read('audio_events.json'), read('audio_actions.json'), read('weapon_sound_slots.json')
    events = registry['events']
    # Only unused old surfaces disappear. Assigned walking/running tile recordings are retained.
    obsolete = {'step_snow', 'step_snow_run', 'step_rubble', 'step_cardboard', 'step_crouch', 'step_asphalt_wet', 'step_dirt_run'}
    for e in events:
        if e.get('binding', {}).get('hook') in obsolete and e.get('files'):
            raise ValueError(f"Assigned obsolete sound needs an explicit migration: {e['id']}")
    events[:] = [e for e in events if e.get('binding', {}).get('hook') not in obsolete]
    actions['actions'][:] = [a for a in actions['actions'] if a['hook'] not in obsolete | {'loop:ambient'}]
    by_hook = {e['binding']['hook']: e for e in events if e['binding']['type'] == 'action'}

    def event(hook, name, category, profile=None, **extra):
        e = by_hook.get(hook)
        if e is None:
            e = dict(id=hook, binding=dict(type='action', hook=hook), type='one', files=[])
            events.append(e)
            by_hook[hook] = e
        e.update(name=name, category=category, profile=profile or hook, custom=True, **extra)
        return e

    def action(hook, name, category, profile=None, kind='one'):
        a = next((a for a in actions['actions'] if a['hook'] == hook), None)
        if a is None:
            a = {'hook': hook}
            actions['actions'].append(a)
        a.update(name=name, category=category, type=kind, profile=profile or hook, supportsObject=False)

    for hook, name, _surfaces in STEPS:
        event(hook, name, 'Шаги и движение', profile='step_stone', group='Поверхности под ногами')
        action(hook, name, 'Шаги и движение', profile='step_stone')
    for e in events:
        if e['binding'].get('hook') == 'step_stone_run':
            e.update(name='Бег по плитке', group='Бег — отдельная запись')
    for prefix, category in [('shell_', 'Гильзы'), ('shell_12_', 'Гильзы 12-го калибра')]:
        for suffix, label, _surfaces in CASINGS:
            hook = prefix + suffix
            name = 'Падение гильзы — ' + label
            profile = 'shell_metal' if suffix == 'metal' else 'shell_hard'
            event(hook, name, category, profile=profile, group='Поверхности')
            action(hook, name, category, profile=profile)
    existing_ids = {e['id'] for e in events}
    for wid, item in read('weapons.json')['weapons'].items():
        for s in slots['slots']:
            if not s.get('wired') or not applies(s, item.get('weapon', {})):
                continue
            eid = wid + '_' + s['id']
            if eid in existing_ids:
                if s.get('surface'):
                    next(e for e in events if e['id'] == eid)['surface'] = s['surface']
                continue
            e = dict(id=eid, name=s['name'], category='Оружие', weapon=wid, action=s['id'], group=s['group'], binding=dict(type='action', hook=eid), type='one', profile='shot_pistol' if s['id'].startswith('shot') else s['id'], files=[])
            if s.get('surface'):
                e['surface'] = s['surface']
            events.append(e)
            existing_ids.add(eid)
    for hook, name, kind in [('osoka_launch', 'Пуск — вышибной заряд', 'one'), ('osoka_motor', 'Маршевый двигатель ракеты', 'loop'), ('osoka_seeker_track', 'Головка — сопровождение цели', 'loop'), ('osoka_seeker_lock', 'Головка — цель захвачена', 'loop')]:
        event(hook, name, 'Оружие', profile=hook, weapon='wpn_mp_01', action=hook, group='Ракета и самонаведение', type=kind)
        action(hook, name, 'Осока', kind=kind)
    maps = [(f['id'], f['name'], f['scene']) for f in read('floors.json')['floors'] if f['scene']]
    maps.append(('hideout', 'Убежище', 'res://scenes/levels/hideout.tscn'))
    for mid, name, scene in maps:
        hook = 'ambient_' + mid
        event(hook, 'Окружение — ' + name, 'Окружение карт', profile='ambient', type='loop', map_scene=scene, group='Фоновая петля карты')
        action(hook, 'Окружение — ' + name, 'Окружение карт', profile='ambient', kind='loop')
    write('audio_surfaces.json', dict(schemaVersion=1, footsteps=[dict(hook=h, name=n, surfaces=s) for h,n,s in STEPS], casings=[dict(hook='shell_'+h, name=n, surfaces=s) for h,n,s in CASINGS]))
    write('audio_events.json', registry)
    write('audio_actions.json', actions)
    write('weapon_sound_slots.json', slots)
    print(f"Catalog updated: {len(events)} events, {len(STEPS)} step surfaces, {len(CASINGS)} casing surfaces, {len(maps)} maps")


if __name__ == '__main__':
    main()
