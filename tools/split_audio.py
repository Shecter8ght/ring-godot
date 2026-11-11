#!/usr/bin/env python3
"""Нарезка входящего звука на отдельные варианты по паузам.

Зависимостей Python нет. PCM-WAV читается стандартной библиотекой; OGG, MP3 и
нестандартный WAV декодируются через ffmpeg. Результат всегда PCM WAV 16-bit.
Последняя строка stdout — JSON с результатом нарезки.
"""

from __future__ import annotations

import argparse
from array import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave


DEFAULT_RATE = 48_000
DEFAULT_CHANNELS = 2
WINDOW_MS = 10.0


class AudioData:
    def __init__(self, rate: int, channels: int, samples: array, decoder: str) -> None:
        self.rate = rate
        self.channels = channels
        self.samples = samples
        self.decoder = decoder

    @property
    def frames(self) -> int:
        return len(self.samples) // self.channels


def _to_s16(raw: bytes, width: int) -> array:
    out = array("h")
    if width == 1:
        out.extend((value - 128) << 8 for value in raw)
    elif width == 2:
        out.frombytes(raw)
        if sys.byteorder != "little":
            out.byteswap()
    elif width == 3:
        for at in range(0, len(raw) - 2, 3):
            value = int.from_bytes(raw[at : at + 3], "little", signed=True)
            out.append(max(-32768, min(32767, value >> 8)))
    elif width == 4:
        for at in range(0, len(raw) - 3, 4):
            value = int.from_bytes(raw[at : at + 4], "little", signed=True)
            out.append(max(-32768, min(32767, value >> 16)))
    else:
        raise ValueError(f"неподдерживаемая разрядность WAV: {width * 8} бит")
    return out


def _load_wave(path: Path) -> AudioData:
    with wave.open(str(path), "rb") as src:
        if src.getcomptype() != "NONE":
            raise ValueError(f"сжатый WAV: {src.getcomptype()}")
        channels = src.getnchannels()
        if channels < 1:
            raise ValueError("в WAV нет каналов")
        samples = _to_s16(src.readframes(src.getnframes()), src.getsampwidth())
        return AudioData(src.getframerate(), channels, samples, "wave")


def _find_ffmpeg() -> str:
    env = os.environ.get("FFMPEG", "").strip()
    candidates = [
        env,
        shutil.which("ffmpeg") or "",
        r"D:\whisper\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("ffmpeg не найден: для OGG/MP3 укажи FFMPEG или добавь ffmpeg в PATH")


def _load_ffmpeg(path: Path) -> AudioData:
    ffmpeg = _find_ffmpeg()
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(DEFAULT_RATE),
        "-ac",
        str(DEFAULT_CHANNELS),
        "pipe:1",
    ]
    done = subprocess.run(command, capture_output=True, check=False)
    if done.returncode != 0:
        error = done.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(error or f"ffmpeg завершился с кодом {done.returncode}")
    samples = array("h")
    samples.frombytes(done.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return AudioData(DEFAULT_RATE, DEFAULT_CHANNELS, samples, "ffmpeg")


def load_audio(path: Path) -> AudioData:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".wav":
        try:
            return _load_wave(path)
        except (wave.Error, EOFError, ValueError):
            pass
    return _load_ffmpeg(path)


def find_segments(
    audio: AudioData,
    threshold_db: float,
    min_silence_ms: float,
    min_clip_ms: float,
    padding_ms: float,
) -> dict[str, object]:
    if audio.frames == 0:
        raise ValueError("пустой аудиофайл")
    window_frames = max(1, round(audio.rate * WINDOW_MS / 1000.0))
    levels: list[float] = []
    peak = 0
    channels = audio.channels
    samples = audio.samples
    for frame_at in range(0, audio.frames, window_frames):
        frame_end = min(audio.frames, frame_at + window_frames)
        sample_at = frame_at * channels
        sample_end = frame_end * channels
        square_sum = 0.0
        count = max(1, sample_end - sample_at)
        for value in samples[sample_at:sample_end]:
            absolute = abs(int(value))
            peak = max(peak, absolute)
            square_sum += float(absolute * absolute)
        rms = math.sqrt(square_sum / count) / 32768.0
        levels.append(20.0 * math.log10(max(rms, 1.0e-9)))

    active = [index for index, level in enumerate(levels) if level >= threshold_db]
    segments: list[tuple[int, int]] = []
    silence_windows = max(1, math.ceil(min_silence_ms / WINDOW_MS))
    if active:
        group_start = active[0]
        previous = active[0]
        for current in active[1:]:
            if current - previous - 1 >= silence_windows:
                segments.append((group_start * window_frames, min(audio.frames, (previous + 1) * window_frames)))
                group_start = current
            previous = current
        segments.append((group_start * window_frames, min(audio.frames, (previous + 1) * window_frames)))

    padding_frames = round(audio.rate * padding_ms / 1000.0)
    min_clip_frames = round(audio.rate * min_clip_ms / 1000.0)
    padded: list[tuple[int, int]] = []
    for start, end in segments:
        start = max(0, start - padding_frames)
        end = min(audio.frames, end + padding_frames)
        if end - start < min_clip_frames:
            continue
        if padded and start <= padded[-1][1]:
            padded[-1] = (padded[-1][0], max(padded[-1][1], end))
        else:
            padded.append((start, end))

    rows = [
        {
            "start": round(start / audio.rate, 4),
            "end": round(end / audio.rate, 4),
            "duration": round((end - start) / audio.rate, 4),
            "start_frame": start,
            "end_frame": end,
        }
        for start, end in padded
    ]
    return {
        "ok": True,
        "decoder": audio.decoder,
        "rate": audio.rate,
        "channels": audio.channels,
        "duration": round(audio.frames / audio.rate, 4),
        "peak_db": round(20.0 * math.log10(max(peak / 32768.0, 1.0e-9)), 2),
        "segments": rows,
    }


def _fade(samples: array, channels: int, rate: int, fade_ms: float, fade_in: bool, fade_out: bool) -> None:
    frames = len(samples) // channels
    fade_frames = min(frames // 2, round(rate * fade_ms / 1000.0))
    for frame in range(fade_frames):
        gain = frame / max(1, fade_frames)
        mirror = frames - 1 - frame
        for channel in range(channels):
            at = frame * channels + channel
            end_at = mirror * channels + channel
            if fade_in:
                samples[at] = round(samples[at] * gain)
            if fade_out:
                samples[end_at] = round(samples[end_at] * gain)


def split_audio(audio: AudioData, analysis: dict[str, object], output_prefix: Path, fade_ms: float) -> list[str]:
    segments = analysis["segments"]
    assert isinstance(segments, list)
    outputs = [output_prefix.parent / f"{output_prefix.name}_{index:02d}.wav" for index in range(1, len(segments) + 1)]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("выходной файл уже существует: " + ", ".join(existing))
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    try:
        for row, output in zip(segments, outputs):
            assert isinstance(row, dict)
            start = int(row["start_frame"]) * audio.channels
            end = int(row["end_frame"]) * audio.channels
            clip = array("h", audio.samples[start:end])
            _fade(
                clip,
                audio.channels,
                audio.rate,
                fade_ms,
                fade_in=int(row["start_frame"]) > 0,
                fade_out=int(row["end_frame"]) < audio.frames,
            )
            temporary = output.with_suffix(".tmp.wav")
            with wave.open(str(temporary), "wb") as dst:
                dst.setnchannels(audio.channels)
                dst.setsampwidth(2)
                dst.setframerate(audio.rate)
                if sys.byteorder == "little":
                    dst.writeframes(clip.tobytes())
                else:
                    copy = array("h", clip)
                    copy.byteswap()
                    dst.writeframes(copy.tobytes())
            os.replace(temporary, output)
            made.append(output)
    except Exception:
        for path in made:
            path.unlink(missing_ok=True)
        raise
    return [str(path) for path in outputs]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("mode", choices=["analyze", "split"])
    result.add_argument("input")
    result.add_argument("--threshold-db", type=float, default=-36.0)
    result.add_argument("--min-silence-ms", type=float, default=180.0)
    result.add_argument("--min-clip-ms", type=float, default=60.0)
    result.add_argument("--padding-ms", type=float, default=35.0)
    result.add_argument("--fade-ms", type=float, default=3.0)
    result.add_argument("--output-prefix")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        audio = load_audio(Path(args.input))
        analysis = find_segments(audio, args.threshold_db, args.min_silence_ms, args.min_clip_ms, args.padding_ms)
        if args.mode == "split":
            if not args.output_prefix:
                raise ValueError("для split нужен --output-prefix")
            if len(analysis["segments"]) < 2:
                raise ValueError("найдено меньше двух частей; настрой порог тишины или минимальную паузу")
            analysis["files"] = split_audio(audio, analysis, Path(args.output_prefix), args.fade_ms)
        print(json.dumps(analysis, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:  # JSON ошибки нужен стенду, тип исключения — для диагностики.
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
