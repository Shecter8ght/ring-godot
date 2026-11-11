#!/usr/bin/env python3
"""Присланные владельцем звуки → записи проекта: моно WAV 48 кГц 16 бит в assets/audio.

python -X utf8 tools/prepare_sound.py <префикс> <файл> [<файл> ...] [--peak -1] [--no-match]

<префикс> — куда класть относительно assets/audio, без номера: guns/hg_01_shot_room_ даст
guns/hg_01_shot_room_01.wav, _02.wav … в порядке файлов. Файлы-источники не меняются.

Что делается с каждым файлом (то же, что в tools/prepare_firearm_layers.py, но проще):
  • в моно (среднее каналов; если каналы сильно разошлись по фазе — левый), гул ниже 20 Гц убирается;
  • тишина перед ударом срезается, остаётся 2 мс (иначе выстрел запаздывает на её длину);
  • 48 кГц; конец плавно гасится (хвост уже в тишине — коротко, обрезан по уровню — длиннее);
  • громкость первых 150 мс у всех файлов набора выравнивается по медиане (варианты не прыгают
    по громкости), затем весь набор одним коэффициентом укладывается в пик --peak дБ (−1).
Источник и лицензию вписывать в assets/CREDITS.md отдельно (скрипт их не знает).
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from scipy import signal
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "assets" / "audio"
RATE = 48_000
PRE_ROLL_S = 0.002
ONSET_DB = -35.0          # начало удара — первый отсчёт выше этого уровня от пика
EARLY_S = 0.150           # окно, по которому выравнивается громкость
PHASE_MIN_CORR = 0.5      # ниже — каналы почти в противофазе, среднее съест звук
FADE_QUIET_S = 0.020      # конец уже тихий (ниже −60 дБ от пика)
FADE_LOUD_S = 0.120       # файл обрезан, пока хвост ещё слышен


def db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-9))


def load_mono(path: Path) -> tuple[np.ndarray, int, float]:
    y, sr = sf.read(str(path), always_2d=True)
    corr = 1.0
    if y.shape[1] >= 2:
        l, r = y[:, 0], y[:, 1]
        corr = float(np.corrcoef(l, r)[0, 1]) if np.std(l) > 0 and np.std(r) > 0 else 1.0
        mono = y.mean(axis=1) if corr >= PHASE_MIN_CORR else l
    else:
        mono = y[:, 0]
    return mono.astype(np.float64), int(sr), corr


def to_rate(y: np.ndarray, sr: int) -> np.ndarray:
    if sr == RATE:
        return y
    g = math.gcd(sr, RATE)
    return signal.resample_poly(y, RATE // g, sr // g)


def prepare(path: Path) -> dict:
    y, sr, corr = load_mono(path)
    sos = signal.butter(2, 20.0, btype="highpass", fs=sr, output="sos")
    y = signal.sosfiltfilt(sos, y)
    y = to_rate(y, sr)
    peak = float(np.max(np.abs(y)))
    onset = int(np.argmax(np.abs(y) > peak * 10 ** (ONSET_DB / 20.0)))
    start = max(0, onset - int(PRE_ROLL_S * RATE))
    y = y[start:]
    onset -= start
    # конец: окна по 10 мс, последний выше −60 дБ от пика; дальше — тишина, режем
    win = int(0.010 * RATE)
    n = len(y) // win
    env = np.array([np.sqrt(np.mean(y[i * win:(i + 1) * win] ** 2)) for i in range(n)])
    alive = np.where(env > peak * 10 ** (-60.0 / 20.0))[0]
    end = min(len(y), (int(alive[-1]) + 2) * win) if len(alive) else len(y)
    cut_level = db(float(env[min(len(env) - 1, max(0, end // win - 1))]) / peak) if len(env) else -120.0
    fade = int((FADE_LOUD_S if cut_level > -45.0 else FADE_QUIET_S) * RATE)
    y = y[:end].copy()
    fade = min(fade, len(y) // 2)
    if fade > 0:
        y[-fade:] *= 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fade)))
    early = y[onset:onset + int(EARLY_S * RATE)]
    return {"name": path.name, "y": y, "corr": corr, "onset": onset, "src_sr": sr,
            "early_db": db(float(np.sqrt(np.mean(early ** 2)))), "cut_db": cut_level}


def write_wav(path: Path, y: np.ndarray, seed: int) -> None:
    rng = np.random.default_rng(seed)
    lsb = 1.0 / 32768.0
    dither = (rng.uniform(-0.5, 0.5, len(y)) + rng.uniform(-0.5, 0.5, len(y))) * lsb
    q = np.clip(np.round((y + dither) * 32767.0), -32768, 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), q, RATE, subtype="PCM_16", format="WAV")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prefix", help="например guns/hg_01_shot_room_")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--peak", type=float, default=-1.0, help="пик набора, дБFS (−1)")
    ap.add_argument("--no-match", action="store_true", help="не выравнивать громкость по набору")
    args = ap.parse_args()

    items = [prepare(Path(f)) for f in args.files]
    target = float(np.median([it["early_db"] for it in items]))
    gains = [0.0 if args.no_match else target - it["early_db"] for it in items]
    peaks = [db(float(np.max(np.abs(it["y"])))) + g for it, g in zip(items, gains)]
    master = min(0.0, args.peak - max(peaks))
    print(f"{'файл':<46}{'корр.':>6}{'удар, мс':>9}{'длит., с':>9}{'гром.150мс':>11}{'коэфф., дБ':>11}{'пик, дБ':>9}")
    for i, (it, g) in enumerate(zip(items, gains), start=1):
        total = g + master
        y = it["y"] * 10 ** (total / 20.0)
        out = AUDIO / f"{args.prefix}{i:02d}.wav"
        write_wav(out, y, i)
        flag = "  (каналы разошлись — взят левый)" if it["corr"] < PHASE_MIN_CORR else ""
        print(f"{it['name'][:44]:<46}{it['corr']:>6.2f}{1000.0 * it['onset'] / RATE:>9.1f}{len(y) / RATE:>9.2f}"
              f"{it['early_db']:>11.1f}{total:>11.1f}{db(float(np.max(np.abs(y)))):>9.1f}{flag}")
        print(f"   → {out.relative_to(ROOT).as_posix()}")
    print(f"выровнено по медиане первых 150 мс ({target:.1f} дБFS); общий коэффициент {master:+.1f} дБ под пик {args.peak:.0f} дБ")


if __name__ == "__main__":
    main()
