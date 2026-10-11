"""Собственные записи шагов → очищенные моно OGG по проверенной карте нарезки.

python tools/prepare_owner_footsteps.py data/audio_recipes/owner_wet_asphalt.json
Нужны ffmpeg, numpy, scipy и soundfile. Расширению входного файла не доверяем:
диктофон iPhone может оставить M4A/AAC внутри файла с именем .ogg.
Сырьё и WAV-мастера сохраняются в _asset_src/<id>, в assets идут только OGG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy import ndimage, signal
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], data: bytes | None = None) -> bytes:
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout


def level(x: np.ndarray) -> float:
    return float(20 * np.log10(max(float(np.sqrt(np.mean(x * x))), 1e-10)))


def clean(x: np.ndarray, rate: int, recipe: dict, noise_ranges: list[list[float]]) -> np.ndarray:
    # Удаляем ветер/гул и неинформативные верха; удары и водяной хвост остаются.
    sos = signal.butter(3, [recipe['highpass_hz'], recipe['lowpass_hz']],
                        btype='bandpass', fs=rate, output='sos')
    filtered = signal.sosfiltfilt(sos, x)
    _, times, z = signal.stft(filtered, fs=rate, nperseg=1024, noverlap=768)
    quiet = np.zeros(len(times), dtype=bool)
    for start, end in noise_ranges:
        # Край окна не должен захватить соседний удар.
        quiet |= (times >= start + 1024 / rate) & (times <= end - 1024 / rate)
    if not quiet.any():
        raise ValueError('нет окон для профиля фонового шума')
    power = abs(z) ** 2
    noise = np.median(power[:, quiet], axis=1)[:, None]
    floor = 10 ** (-recipe['noise_reduction_db'] / 20)
    gain = np.sqrt(np.maximum(1 - recipe['noise_strength'] * noise / np.maximum(power, 1e-16), floor**2))
    # Мягкий спектральный пол и сглаживание вместо жёсткого гейта: нет рваного хвоста.
    gain = ndimage.gaussian_filter(gain, sigma=(1.2, .7))
    _, cleaned = signal.istft(z * gain, fs=rate, nperseg=1024, noverlap=768)
    return cleaned[:len(x)].astype(np.float32)


def fade(x: np.ndarray, rate: int, in_ms: float, out_ms: float) -> None:
    n_in = min(len(x), round(rate * in_ms / 1000))
    n_out = min(len(x), round(rate * out_ms / 1000))
    x[:n_in] *= np.sin(np.linspace(0, np.pi / 2, n_in)) ** 2
    x[-n_out:] *= np.cos(np.linspace(0, np.pi / 2, n_out)) ** 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text(encoding='utf-8'))
    ffmpeg = os.environ.get('FFMPEG') or shutil.which('ffmpeg') or r'D:\whisper\ffmpeg\bin\ffmpeg.exe'
    rate = int(recipe['rate'])
    incoming = ROOT / 'Записанные звуки'
    if incoming.is_dir():
        (incoming / '.gdignore').touch()
    archive = ROOT / '_asset_src' / recipe['id']
    archive.mkdir(parents=True, exist_ok=True)
    (archive / '.gdignore').touch()
    (archive / 'license.txt').write_text(
        f"{recipe['description']}\nАвтор: {recipe['author']}. Собственные записи владельца RING.\n"
        'Владелец поручил обработать и использовать записи в игре; CC0 не объявляется.\n', encoding='utf-8')
    sources = []
    clips = []
    preview = []
    comparisons = []
    output_prefix = ROOT / 'assets' / 'audio' / recipe['output_prefix']
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    clip_index = 0
    for source_index, source in enumerate(recipe['sources'], 1):
        path = ROOT / source['file']
        raw_bytes = path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if digest != source['sha256']:
            raise ValueError(f'исходник изменился: {path}')
        # Байт-в-байт копия имеет настоящее расширение контейнера.
        raw_name = f'take_{source_index:02d}_original.m4a' if raw_bytes[4:8] == b'ftyp' else f'take_{source_index:02d}_original{path.suffix}'
        (archive / raw_name).write_bytes(raw_bytes)
        raw = np.frombuffer(run([ffmpeg, '-v', 'error', '-i', str(path), '-ac', '1',
                                '-ar', str(rate), '-f', 'f32le', 'pipe:1']), dtype='<f4').copy()
        cleaned = clean(raw, rate, recipe, source['noise_ranges'])
        sf.write(archive / f'take_{source_index:02d}_raw.wav', raw, rate, subtype='PCM_24')
        sf.write(archive / f'take_{source_index:02d}_clean.wav', cleaned, rate, subtype='PCM_24')
        quiet_raw = np.concatenate([raw[round(a*rate):round(b*rate)] for a, b in source['noise_ranges']])
        quiet_clean = np.concatenate([cleaned[round(a*rate):round(b*rate)] for a, b in source['noise_ranges']])
        sources.append({'file': source['file'], 'sha256': digest, 'archive': raw_name,
                        'seconds': round(len(raw)/rate, 4), 'noise_before_db': round(level(quiet_raw),2),
                        'noise_after_db': round(level(quiet_clean),2),
                        'noise_reduction_db': round(level(quiet_raw)-level(quiet_clean),2)})
        for start, end in source['clips']:
            clip_index += 1
            lo, hi = round(start*rate), round(end*rate)
            if lo < 0 or hi > len(raw) or hi <= lo:
                raise ValueError(f'неверные границы: {start}, {end}')
            clip = cleaned[lo:hi].copy()
            original = raw[lo:hi].copy()
            target = 10 ** (recipe['peak_db'] / 20)
            rms_target = 10 ** (recipe['rms_db'] / 20)
            factor = min(target / max(float(max(abs(clip))), 1e-10),
                         rms_target / max(float(np.sqrt(np.mean(clip**2))), 1e-10),
                         10 ** (recipe['max_gain_db']/20))
            # Для сравнения одинаковый gain до/после и запас от перегрузки сырого сигнала.
            comparison_factor = min(factor, .95 / max(float(max(abs(original))), 1e-10))
            comparison_clean = clip * comparison_factor
            original *= comparison_factor
            clip *= factor
            fade(clip, rate, recipe['fade_in_ms'], recipe['fade_out_ms'])
            fade(original, rate, recipe['fade_in_ms'], recipe['fade_out_ms'])
            fade(comparison_clean, rate, recipe['fade_in_ms'], recipe['fade_out_ms'])
            out = output_prefix.with_name(output_prefix.name + f'{clip_index:02d}.ogg')
            master = archive / f'{out.stem}.wav'
            sf.write(master, clip, rate, subtype='PCM_24')
            run([ffmpeg, '-v', 'error', '-y', '-i', str(master), '-map_metadata', '-1',
                 '-c:a', 'libvorbis', '-q:a', '6', '-ac', '1', '-ar', str(rate), str(out)])
            decoded = np.frombuffer(run([ffmpeg, '-v', 'error', '-i', str(out), '-f', 'f32le',
                                         '-ac', '1', '-ar', str(rate), 'pipe:1']), dtype='<f4')
            if not np.isfinite(decoded).all() or max(abs(decoded)) >= .99:
                raise ValueError(f'перегрузка готового OGG: {out}')
            clips.append({'file': out.relative_to(ROOT/'assets'/'audio').as_posix(), 'take':source_index,
                          'start':start,'end':end,'duration':round(len(decoded)/rate,4),
                          'gain_db':round(20*np.log10(factor),2),
                          'peak_db':round(float(20*np.log10(max(abs(decoded)))),2),'rms_db':round(level(decoded),2),
                          'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
            preview.extend([clip, np.zeros(round(.65*rate)-len(clip),dtype=np.float32)])
            comparisons.extend([original, np.zeros(round(.3*rate),dtype=np.float32),
                                comparison_clean, np.zeros(round(.45*rate),dtype=np.float32)])
    sf.write(archive/'preview_clean.wav', np.concatenate(preview), rate, subtype='PCM_16')
    sf.write(archive/'preview_before_after.wav', np.concatenate(comparisons), rate, subtype='PCM_16')
    report = {'id':recipe['id'],'rate':rate,'channels':1,'sources':sources,'clips':clips}
    (archive/'processing_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'count':len(clips),'sources':sources,'clips':clips},ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main()
