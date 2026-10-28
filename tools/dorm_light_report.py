"""Validate r6 camera/image coverage and summarize measured frames (no rendered-image retouching)."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/screens/dorm'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rgb(path, rect):
    pixels = np.asarray(Image.open(path).convert('RGB'), dtype=float)
    x, y, xx, yy = rect
    value = pixels[y:yy, x:xx].mean((0, 1))
    return {'rgb': value.round(3).tolist(), 'luma_display_0_255': round(float(value @ [.2126, .7152, .0722]), 3)}


def sheet(filename, rows):
    width, height = 480, 270
    result = Image.new('RGB', (width * len(rows[0]), (height + 32) * len(rows)), '#14191e')
    draw = ImageDraw.Draw(result)
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 15)
    except OSError:
        font = ImageFont.load_default()
    for y, row in enumerate(rows):
        for x, name in enumerate(row):
            with Image.open(OUT / name) as original:
                preview = original.convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
            left, top = x * width, y * (height + 32)
            result.paste(preview, (left, top + 32))
            draw.text((left + 5, top + 8), name.replace('light_', '').replace('.png', ''), font=font, fill='#eeeeee')
    result.save(OUT / filename, quality=92)


def main():
    plan = load(ROOT / 'data/blockouts/dorm.json')
    manifest = load(OUT / 'light_views.json')
    perf = load(OUT / 'light_performance.json')
    assert len(manifest) == 143, len(manifest)
    assert len(perf['samples']) == 69, len(perf['samples'])
    assert len({row['file'] for row in manifest}) == 143
    views = {view['id']: view for view in plan['shots']}
    for row in manifest:
        reference = views[row['id']]
        for field in ['foot', 'look', 'eye_height']:
            assert row[field] == reference[field], (row['file'], field)
        assert row['revision'] == 6
        with Image.open(OUT / row['file']) as png:
            assert png.size == (1920, 1080), (row['file'], png.size)
            png.verify()
    cases = [case['id'] for case in plan['environment']['cases']]
    for case in cases:
        assert len([row for row in manifest if row['case'] == case]) == 14, case
        assert len([row for row in manifest if row['case'] == case + '_fov95']) == 3, case
    summary = {'revision': 6, 'validated_images': len(manifest), 'validated_samples': len(perf['samples']),
               'camera_positions_unchanged': True, 'cases': [], 'effects': [], 'calibration': {}}
    for case in cases:
        row = {'case': case, 'views': {}}
        for view in ['01_corridor', '09_lounge']:
            sample = next(s for s in perf['samples'] if s['case'] == case and s['view'] == view)
            keys = ['fps', 'gpu_frame_ms', 'gpu_frame_p95_ms', 'draw_calls_median', 'draw_shadow_median',
                    'shadow_sources_frustum', 'shadow_sources_origin_visible', 'shadow_sources_visible_receivers',
                    'shadow_lamps_visible_receivers', 'shadow_windows_visible_receivers', 'sun_visible_receiver_samples']
            row['views'][view] = {key: round(sample[key], 3) for key in keys}
        summary['cases'].append(row)
    for case in ['evening_A', 'evening_B']:
        for view in ['01_corridor', '02_room']:
            control = np.asarray(Image.open(OUT / f'light_{case}_effects_control_{view}.png').convert('RGB'), float)
            for effect in ['effects_repeat', 'ssil_on', 'ssil_strong', 'fog_off', 'post_off']:
                other = np.asarray(Image.open(OUT / f'light_{case}_{effect}_{view}.png').convert('RGB'), float)
                sample = next((s for s in perf['samples'] if s['case'] == case + '_' + effect and s['view'] == view), None)
                summary['effects'].append({'case': case, 'view': view, 'effect': effect,
                    'mean_absolute_pixel_difference_0_255': round(float(np.abs(other - control).mean()), 3),
                    'gpu_frame_ms': round(sample['gpu_frame_ms'], 3) if sample else None})
    for gi in ['A', 'B']:
        file = OUT / 'r6_calibration' / f'{gi}_02_room.png'
        summary['calibration'][gi] = {name: rgb(file, rect) for name, rect in {
            'wall_left': [460, 270, 730, 440], 'wall_right': [1220, 270, 1430, 440],
            'ceiling': [500, 70, 1400, 230]}.items()}
    sheet('light_r6_comparison.jpg', [
        [f'{prefix}_{case}_{view}.png' for prefix, case in [('light5', 'evening_A'), ('light', 'evening_A'),
                                                          ('light5', 'evening_B'), ('light', 'evening_B')]]
        for view in ['01_corridor', '02_room', '04_wash', '05_stairs_bottom', '07_hall', '08_street']])
    sheet('light_r6_effects.jpg', [[f'light_{case}_{effect}_{view}.png'
                                 for effect in ['effects_control', 'fog_off', 'post_off', 'ssil_strong']]
                                for case in ['evening_A', 'evening_B'] for view in ['01_corridor', '02_room']])
    (OUT / 'light_r6_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
