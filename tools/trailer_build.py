"""Нарезка настоящего дубля и собственная звуковая подложка трейлера RING."""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brag-output"
ASSETS = OUT / "composition/assets"
DURATION = 36
RATE = 48000


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def dependencies() -> None:
    """Локальные зависимости композиции: загружаются только при отсутствии."""
    files = {
        "fonts/oswald.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
        "fonts/oswald-LICENSE.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/OFL.txt",
        "fonts/golos.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/golostext/GolosText%5Bwght%5D.ttf",
        "fonts/golos-LICENSE.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/golostext/OFL.txt",
        "vendor/gsap.min.js": "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js",
    }
    for name, url in files.items():
        target = ASSETS / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, target)


def audio_envelope() -> None:
    """Спектр для яркости эмблемы; та же 4096-точечная сетка, что в Hyperframes."""
    sample_rate, samples = wavfile.read(ASSETS / "pulse.wav")
    mono = samples.astype(np.float64).mean(axis=1) / 32768
    window = np.hanning(4096)
    freqs = np.fft.rfftfreq(4096, 1 / sample_rate)
    bass = []
    for frame in range(DURATION * 30):
        center = round(frame * sample_rate / 30)
        first = max(0, center - 2048)
        section = mono[first:first + 4096]
        section = np.pad(section, (0, 4096 - len(section)))
        fft = np.abs(np.fft.rfft(section * window))
        bass.append(float(fft[(freqs >= 30) & (freqs < 90)].mean()))
    peak = max(max(bass), 1e-9)
    data = {"fps": 30, "frames": [{"bands": [round(v / peak, 4)]} for v in bass]}
    # Первый выпуск измерен официальным extract-audio-data.py; эта ветка обеспечивает
    # автономное повторение без установки набора навыков Hyperframes.
    target = ASSETS / "audio-data.js"
    if not target.exists():
        target.write_text("window.RING_AUDIO = " + json.dumps(data) + ";", encoding="utf-8")


def soundtrack() -> None:
    """Оригинальная партитура: пульс, низкий дрон и редкие металлические акценты."""
    rng = np.random.default_rng(270926)
    t = np.arange(RATE * DURATION) / RATE
    stereo = np.zeros((len(t), 2))
    noise = rng.normal(0, 1, len(t))
    air = sosfilt(butter(2, [180, 1700], fs=RATE, btype="band", output="sos"), noise)
    envelope = np.minimum(t / 1.0, 1) * np.minimum((DURATION - t) / 2, 1)
    for channel in range(2):
        phase = channel * 0.4
        drone = (np.sin(2 * np.pi * 73.416 * t + phase) * .022
                 + np.sin(2 * np.pi * 110.0 * t + np.sin(t * .14)) * .012
                 + np.sin(2 * np.pi * 146.93 * t + phase) * .008)
        stereo[:, channel] = drone * envelope + air * .009 * envelope

    def place(at: float, sample: np.ndarray, gain: float = 1, pan: float = 0) -> None:
        start = round(at * RATE)
        length = min(len(sample), len(t) - start)
        if start < 0 or length <= 0:
            return
        stereo[start:start + length, 0] += sample[:length] * gain * (1 - pan * .3)
        stereo[start:start + length, 1] += sample[:length] * gain * (1 + pan * .3)

    step = 60 / 96
    for beat in range(55):
        at = beat * step
        if at > 31.5:
            break
        progress = min(at / 25, 1)
        u = np.arange(int(RATE * .55)) / RATE
        phase = 2 * np.pi * (46 * u + 48 * .035 * (1 - np.exp(-u / .035)))
        kick = np.sin(phase) * np.exp(-u * 12) * (1 - np.exp(-u * 400))
        place(at, kick, .13 if beat % 4 == 0 else .075)
        # При боевых кадрах темп остаётся, но середина не спорит с выстрелами.
        tone_gain = .045 if not 10.5 < at < 16.5 else .024
        freq = [146.83, 146.83, 174.61, 164.81, 146.83, 220, 164.81, 130.81][beat % 8]
        pluck = (np.sin(2 * np.pi * freq * u) + .25 * np.sin(2 * np.pi * freq * 2 * u))
        pluck *= np.exp(-u * 10) * (1 - np.exp(-u * 300))
        place(at + step * .5, pluck, tone_gain, (-1) ** beat * .5)
        place(at + step * 1.25, pluck, tone_gain * .22, (-1) ** (beat + 1) * .7)
        if beat % 2 == 1 and at > 7:
            hiss = rng.normal(0, 1, len(u))
            hiss = sosfilt(butter(2, [500, 2600], fs=RATE, btype="band", output="sos"), hiss)
            place(at, hiss * np.exp(-u * 32), .035 + progress * .025)
    for at in [2.5, 7.5, 16.5, 21.5, 31.5]:
        u = np.arange(int(RATE * 2.5)) / RATE
        impact = np.sin(2 * np.pi * (42 * u + 16 * .16 * (1 - np.exp(-u / .16))))
        impact *= np.exp(-u * 3.2) * (1 - np.exp(-u * 100))
        metal = sum(np.sin(2 * np.pi * f * u) for f in [291, 407, 653]) / 3
        metal *= np.exp(-u * 2.7) * (1 - np.exp(-u * 60))
        place(at, impact * .18 + metal * .022)
    fade = np.minimum((DURATION - t) / 1.6, 1).clip(0, 1)
    stereo *= fade[:, None]
    stereo *= .5 / max(.5, float(np.max(np.abs(stereo))))
    wavfile.write(ASSETS / "pulse.wav", RATE, (stereo * 32767).astype(np.int16))


def clips() -> None:
    marks = json.loads((ROOT / "export/trailer/markers.json").read_text(encoding="utf-8"))
    definitions = [
        ("hook", "combat", .9, 2.5, 0),
        ("ring", "establish", 0, 5, 2.5),
        ("approach", "approach", 0, 3, 7.5),
        ("combat", "combat", .3, 6, 10.5),
        ("search", "search", 3.4, 2, 16.5),
        ("loot", "loot", .033333, 3, 18.5),
        ("run", "exit_approach", 0, 1.5, 21.5),
        ("evac", "evac", 0, 6, 23),
        ("result", "result", 0, 2.5, 29),
    ]
    edits = []
    for name, marker, offset, duration, start in definitions:
        source = round((marks[marker]["time"] + offset) * 30) / 30
        run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(source),
            "-i", str(ROOT / "export/trailer/raw.avi"), "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(ASSETS / f"{name}.mp4"))
        edits.append({"name": name, "start": start, "duration": duration, "source_start": source})
    (OUT / "edit-list.json").write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "2.5", "-i",
        str(ASSETS / "ring.mp4"), "-frames:v", "1", "-q:v", "2", str(ASSETS / "ring.jpg"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    dependencies()
    soundtrack()
    audio_envelope()
    if not args.audio_only:
        clips()
    print("Prepared", ASSETS)


if __name__ == "__main__":
    main()
