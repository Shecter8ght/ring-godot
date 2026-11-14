"""Выделить основу и покрытия из записей владельца для первой пробы."""

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt


AUDIO = Path(__file__).resolve().parents[1] / "assets" / "audio" / "sonora"
RATE = 48000


def make_layer(source: str, target: str, frequencies: tuple[int, int], duration: float) -> None:
    with wave.open(str(AUDIO / f"{source}.wav")) as original:
        assert (original.getnchannels(), original.getsampwidth(), original.getframerate()) == (1, 2, RATE)
        samples = np.frombuffer(original.readframes(original.getnframes()), dtype="<i2").astype(float)

    window = RATE // 400
    frames = samples[: len(samples) // window * window].reshape(-1, window)
    envelope = np.sqrt(np.mean(frames**2, axis=1))
    contact = np.flatnonzero(envelope > envelope.max() * 0.14)[0] * window
    start = max(0, contact - RATE // 200)
    filtered = sosfiltfilt(butter(3, frequencies, btype="bandpass", fs=RATE, output="sos"), samples)
    clip = filtered[start : start + round(duration * RATE)].copy()
    fade_in = RATE // 200
    fade_out = RATE // 20
    clip[:fade_in] *= np.linspace(0, 1, fade_in)
    clip[-fade_out:] *= np.linspace(1, 0, fade_out) ** 2
    clip = np.rint(clip * (14000 / np.max(np.abs(clip)))).astype("<i2")
    with wave.open(str(AUDIO / f"{target}.wav"), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(clip.tobytes())


if __name__ == "__main__":
    for take in range(1, 5):
        source = f"step_concrete_{take:02d}"
        make_layer(source, f"step_base_{take:02d}", (45, 235), 0.12)
        make_layer(source, f"step_layer_concrete_{take:02d}", (420, 10500), 0.22)
        make_layer(f"step_gravel_{take:02d}", f"step_layer_gravel_{take:02d}", (290, 11000), 0.33)
        make_layer(f"step_water_{take:02d}", f"step_layer_water_{take:02d}", (210, 11000), 0.36)
