#!/usr/bin/env python3
"""Выстрелы The Free Firearm Sound Library (CC0) по слоям дистанции → кандидаты стенда звуков.

python -X utf8 tools/prepare_firearm_layers.py [--only ключ,ключ] [--force]

Источник — нетронутый архив `_asset_src/sound_libraries/Free_Firearm_Sound_Library_CC0/Raw_Master_Tracks.zip`
(192 кГц, 24 бит, стерео). Каждый выстрел этой библиотеки записан с нескольких точек сразу; из них
получаются слои одного звука:

  self    — свой выстрел: микрофон за спиной стрелка (так стреляющий слышит своё оружие);
  near    — вблизи: пара микрофонов перед стрелком слева и справа;
  mid     — средняя дистанция;
  far     — вдали;
  distant — очень далеко: та же дальняя запись, воздух дополнительно гасит верхи (ISO 9613-1),
            отражения от местности дают раскат. Это обработка настоящей записи, не синтез.

Пара микрофонов вблизи и вдали разнесена (каналы сдвинуты на 1–2 мс): сложение в моно дало бы
гребёнку, поэтому каждый канал — отдельный вариант. Пики, срезанные при записи, восстанавливаются
сплайном; гул ниже 25 Гц убирается; громкость выравнивается по первым 150 мс (K-взвешивание),
чтобы слои стыковались в игре без скачков; хвост режется там, где он сам затих, а хвост с чужим
звуком (голос, лязг) укорачивается или вариант отбрасывается.

Результат — моно WAV 48 кГц / 16 бит в `_sound_try/Выстрелы_CC0_дистанции/<набор>/<слой>/`,
назначения и CC0 — в `_sound_try/_selection.json` (не одобрены: слушает и одобряет владелец),
карта нарезки с хешами — `data/audio_recipes/firearm_layers.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import zipfile

import numpy as np
from scipy import interpolate, ndimage, signal
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "_asset_src" / "sound_libraries" / "Free_Firearm_Sound_Library_CC0"
ZIP = LIB / "Raw_Master_Tracks.zip"
TRY = ROOT / "_sound_try"
OUT_NAME = "Выстрелы_CC0_дистанции"
OUT = TRY / OUT_NAME
SELECTION = TRY / "_selection.json"
RECIPE = ROOT / "data" / "audio_recipes" / "firearm_layers.json"
SOURCE = "Free Firearm Sound Library — Ben Jaszczak, Brian Nelson, Kevin Heras, Matthew Nanney"
VERSION = 1

RATE = 48_000
PRE_ROLL_S = 0.002
# Громкость первых 150 мс (K-взвешивание) у всех слоёв одна — слои сменяют друг друга без скачка.
# Вблизи почти вся энергия выстрела — в первой миллисекунде (щелчок), «тело» удара и эхо на 30–40 дБ
# тише; ухо в жизни это сглаживает (защитный рефлекс, интеграция громкости). Поэтому ограничитель
# с упреждением прижимает щелчок — по слою не больше gr дБ, отпускает за rel с — и «тело» слышно.
TARGET_EARLY_DB = -20.0
PEAK_LIMIT_DB = -1.0
# Параллельное уплотнение ближних слоёв (так делают звук выстрела в играх): к записи подмешивается
# копия, поднятая на lift дБ и прижатая ограничителем, — щелчок остаётся, «тело» удара и эхо слышнее.
# mix — доля копии. Дальним слоям не нужно: их энергия и так в эхе.
DENSITY = {"self": {"mix": 0.5, "lift": 24.0}, "near": {"mix": 0.5, "lift": 26.0}, "mid": {"mix": 0.35, "lift": 18.0}}
DENSITY_RELEASE_S = 0.008
LIMIT = {"self": {"gr": 16.0, "rel": 0.015}, "near": {"gr": 22.0, "rel": 0.01}, "mid": {"gr": 14.0, "rel": 0.02},
         "far": {"gr": 8.0, "rel": 0.04}, "distant": {"gr": 6.0, "rel": 0.06}}
LIMIT_LOOKAHEAD_S = 0.0015
EARLY_S = 0.15
# Хвост кончается, когда огибающая ниже пика на TAIL_DB (или у шума записи).
TAIL_DB = 72.0
# Длина хвоста по слою, с: дальше звук уже не слышен, а файл не раздувается.
MAX_LEN = {"self": 1.8, "near": 2.2, "mid": 2.8, "far": 3.2, "distant": 4.5}
LAYER_DIRS = {"self": "1 свой выстрел — из-за спины", "near": "2 вблизи", "mid": "3 средняя дистанция",
              "far": "4 вдали", "distant": "5 очень далеко — из дальней записи"}
# Пауза до следующего выстрела меньше этой — выстрел внутри серии, его хвост перекрыт.
MIN_GAP_S = 0.7
# Отбор события: выстрел — громче всего в дорожке; лязг затвора и голоса — тише на эту величину.
EVENT_PEAK_RANGE_DB = 9.0
# Чужой звук в хвосте: позже BUMP_FROM_S и громче достигнутого затухания на BUMP_DB. Раньше — эхо.
BUMP_FROM_S = 0.9
BUMP_DB = 14.0

# Наборы: событие стенда (слой «вблизи»; остальные слои — событие + _self/_mid/_far/_distant),
# название папки, оружие записи, дорожки по слоям. Соответствие стволам игры — docs/STATUS.md.
SETS: list[dict] = [
    {"key": "pistol", "event": "shot_pistol", "title": "Пистолет 9×19 — общий набор (Walther PPQ)",
     "gun": "Walther PPQ, 9 мм", "max": 6, "distant": True,
     "layers": {"self": ["X_38", "X_40"], "near": ["X_39", "X_41"], "mid": ["X_30", "X_32"], "far": ["X_31", "X_33"]}},
    {"key": "pm", "event": "wpn_hg_01_shot", "title": "ПМ (Bersa .380)",
     "gun": "Bersa, .380 ACP", "max": 6, "distant": True,
     "layers": {"self": ["F_44", "F_45"], "near": ["F_46", "F_47"], "mid": ["F_40", "F_41"], "far": ["F_42", "F_43"]}},
    {"key": "usp", "event": "wpn_hg_03_shot", "title": "USP .45 (Кольт 1911)",
     "gun": "Colt 1911, .45 ACP", "max": 6, "distant": True,
     "layers": {"self": ["A_35", "A_36"], "near": ["A_41", "A_42"], "mid": ["A_33", "A_34"], "far": ["A_39", "A_40"]}},
    {"key": "smg", "event": "shot_smg", "title": "Пистолеты-пулемёты — общий набор (шведский M45, 9 мм)",
     "gun": "Carl Gustav M45, 9 мм", "max": 6, "distant": True,
     "layers": {"self": ["G_26", "G_32"], "near": ["G_25", "G_31"], "mid": ["G_14", "G_20"], "far": ["G_13", "G_19"]}},
    {"key": "p90", "event": "wpn_smg_02_shot", "title": "P90 (ППШ, 7.62×25)",
     "gun": "ППШ, 7.62×25", "max": 6, "distant": True,
     "layers": {"self": ["P_25", "P_31"], "near": ["P_24", "P_30"], "mid": ["P_13", "P_15"], "far": ["P_12", "P_14"]}},
    {"key": "rifle", "event": "shot_rifle", "title": "Автоматы и карабины 5.45 и 5.56 — общий набор (AR-15)",
     "gun": "AR-15, 5.56×45", "max": 6, "distant": True,
     "layers": {"self": ["D_27", "D_29"], "near": ["D_31", "D_32"], "mid": ["D_23", "D_24"], "far": ["D_25", "D_26"]}},
    {"key": "veras", "event": "wpn_ar_01_shot", "title": "ВЕРАС-54 (АК-47)",
     "gun": "AK-47, 7.62×39", "max": 6, "distant": True,
     "layers": {"self": ["C_39", "C_42"], "near": ["C_25", "C_28"], "mid": ["C_31", "C_37", "C_38"],
                "far": ["C_17", "C_23", "C_24"]}},
    {"key": "mcx", "event": "wpn_ar_03_shot", "title": "MCX Virtus (Savage 10, .300 Blackout)",
     "gun": "Savage Model 10, .300 AAC Blackout", "max": 6, "distant": True,
     "layers": {"self": ["T_24", "T_26"], "near": ["T_25", "T_27"], "mid": ["T_16", "T_18"], "far": ["T_17", "T_19"]}},
    {"key": "battle", "event": "shot_battle", "title": "Тяжёлые винтовки 7.62×51 — общий набор (Springfield 1917, .30-06)",
     "gun": "Springfield 1917, .30-06", "max": 6, "distant": True,
     "layers": {"self": ["B_17", "B_18"], "near": ["B_23", "B_24"], "mid": ["B_15", "B_16"], "far": ["B_21", "B_22"]}},
    {"key": "pkm", "event": "wpn_lmg_01_shot", "title": "ПКМ (Мосин, 7.62×54R)",
     "gun": "Mosin-Nagant, 7.62×54R", "max": 6, "distant": True,
     "layers": {"self": ["M_20", "M_22"], "near": ["M_19", "M_21"], "mid": ["M_24", "M_26"], "far": ["M_23", "M_25"]}},
    {"key": "marksman", "event": "shot_marksman", "title": "Снайперские винтовки — общий набор (Tikka T3, .30-06)",
     "gun": "Tikka T3, .30-06", "max": 6, "distant": True,
     "layers": {"self": ["W_26", "W_28"], "near": ["W_27", "W_29"], "mid": ["W_22", "W_24"], "far": ["W_23", "W_25"]}},
    {"key": "shotgun", "event": "shot_shotgun", "title": "Ружья 12 калибра — общий набор (Mossberg, Nova, Model 12, Charles Daly)",
     "gun": "Mossberg 190, Benelli Nova, Winchester Model 12, Charles Daly, 12 калибр", "max": 8, "distant": True,
     "layers": {"self": ["N_27", "N_29", "O_18", "O_20", "K_19", "K_21", "H_18", "H_20"],
                "near": ["N_28", "N_30", "O_19", "O_21", "K_20", "K_22", "H_19", "H_21"],
                "mid": ["N_23", "N_25", "O_14", "O_16", "K_15", "K_17", "H_14", "H_16"],
                "far": ["N_24", "N_26", "O_15", "O_17", "K_16", "K_18", "H_15", "H_17"]}},
    {"key": "pistol_sup", "event": "shot_pistol_sup", "title": "Пистолет с глушителем — общий набор (Walther PPQ)",
     "gun": "Walther PPQ, 9 мм, глушитель", "max": 6, "distant": False,
     "layers": {"self": ["X_42", "X_44", "X_46"], "near": ["X_43", "X_45", "X_47"], "mid": ["X_34", "X_36"],
                "far": ["X_35", "X_37"]}},
    {"key": "sup939", "event": "shot_sup939", "title": "«Вал» и «Винторез» (Savage 10, .300 Blackout с глушителем)",
     "gun": "Savage Model 10, .300 AAC Blackout, глушитель, дозвуковой", "max": 6, "distant": False,
     "layers": {"self": ["T_28", "T_30"], "near": ["T_29", "T_31"], "mid": ["T_20", "T_22"], "far": ["T_21", "T_23"]}},
    {"key": "rifle_sup", "event": "shot_rifle_sup", "title": "Автомат с глушителем — общий набор (SKS с глушителем)",
     "gun": "Norinco SKS, 7.62×39, глушитель; записано на средней дистанции", "max": 6, "distant": False,
     "layers": {"near": ["U_17", "U_19"]}},
]

# Затухание звука в воздухе, дБ/м (ISO 9613-1, ≈15 °C, влажность 60 %), и сколько метров слой
# «очень далеко» дальше слоя «вдали».
AIR_DB_PER_M = [(0, 0.0), (63, 0.0001), (125, 0.0004), (250, 0.0011), (500, 0.0023), (1000, 0.0042),
                (2000, 0.0086), (4000, 0.024), (8000, 0.077), (16000, 0.25), (24000, 0.4)]
DISTANT_EXTRA_M = 280.0
# Раскат: рассеяние на местности и опушках приходит позже прямого звука и тянется дольше.
RUMBLE = {"rise_s": 0.07, "t60_s": 2.8, "lowpass_hz": 1300.0, "energy_db": 0.0,
          # отдельные отражения (опушка, стены, овраг): когда, с, и на сколько громче рассеянного
          # гула в этот момент, дБ; каждое — размытый «бум» ~0.12 с, а не щелчок
          "echoes": [(0.23, 6.0), (0.52, 5.0), (0.95, 4.0), (1.4, 3.0)], "echo_s": 0.12}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def db(v: float) -> float:
    return 20.0 * math.log10(max(v, 1e-12))


def moving_rms(x: np.ndarray, n: int) -> np.ndarray:
    c = np.cumsum(np.concatenate([[0.0], (x.astype(np.float64)) ** 2]))
    out = (c[n:] - c[:-n]) / n
    pad_l = n // 2
    return np.sqrt(np.maximum(np.concatenate([np.full(pad_l, out[0]), out, np.full(n - 1 - pad_l, out[-1])]), 0.0))


def declip(ch: np.ndarray) -> int:
    """Срезанные при записи пики — по сплайну соседних отсчётов. Возвращает число исправленных."""
    top = float(np.abs(ch).max())
    if top < 0.9:
        return 0
    mask = np.abs(ch) >= top * 0.999
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    fixed = 0
    k = 24
    for s, e in zip(starts, ends):
        if e - s < 2 or e - s > 4000 or s < k or e + k > len(ch):
            continue
        idx = np.concatenate([np.arange(s - k, s), np.arange(e, e + k)])
        spline = interpolate.CubicSpline(idx, ch[idx])
        rebuilt = spline(np.arange(s, e))
        # сплайн не должен улететь: реальный пик — разумно выше уровня среза
        sign = np.sign(ch[s])
        rebuilt = sign * np.clip(np.abs(rebuilt), top, top * 2.5)
        ch[s:e] = rebuilt
        fixed += e - s
    return fixed


def k_weight(x: np.ndarray) -> np.ndarray:
    """Предфильтр громкости BS.1770: «голова» +4 дБ выше 1.5 кГц и срез низа 38 Гц."""
    b1, a1 = signal.iirfilter(2, 1500.0, btype="highpass", ftype="butter", fs=RATE)
    shelf = x + (10 ** (4.0 / 20) - 1.0) * signal.lfilter(b1, a1, x)
    sos = signal.butter(2, 38.0, btype="highpass", fs=RATE, output="sos")
    return signal.sosfilt(sos, shelf)


def early_db(x: np.ndarray, onset: int) -> float:
    w = k_weight(x[max(0, onset - 96): onset + int(RATE * EARLY_S)])
    return db(float(np.sqrt(np.mean(w * w))))


def true_peak(x: np.ndarray) -> float:
    return float(np.abs(signal.resample_poly(x, 4, 1)).max())


def load_track(z: zipfile.ZipFile, index: dict[str, str], name: str) -> tuple[np.ndarray, dict]:
    raw = z.read(index[name])
    x, sr = sf.read(io.BytesIO(raw), always_2d=True, dtype="float64")
    fixed = sum(declip(x[:, c]) for c in range(x.shape[1]))
    sos = signal.butter(2, 25.0, btype="highpass", fs=sr, output="sos")
    x = signal.sosfilt(sos, x, axis=0)
    g = math.gcd(RATE, sr)
    x = signal.resample_poly(x, RATE // g, sr // g, axis=0)
    return x, {"track": name, "sha256": sha256(raw), "rate": sr, "declipped_samples": int(fixed)}


def find_shots(x: np.ndarray) -> list[int]:
    """Начала выстрелов (отсчёт 48 кГц): громкие события, после которых тишина не короче MIN_GAP_S."""
    m = np.abs(x).max(axis=1)
    fast = moving_rms(m, int(RATE * 0.003))
    noise = float(np.percentile(moving_rms(m, int(RATE * 0.03)), 8)) + 1e-9
    thr = max(noise * 40, float(fast.max()) * 0.1)
    above = np.where(fast > thr)[0]
    events: list[int] = []
    for i in above:
        if not events or i - events[-1] > RATE * 0.05:
            events.append(int(i))
    peaks = [float(m[e: e + int(RATE * 0.03)].max()) for e in events]
    top = max(peaks) if peaks else 0.0
    kept = [e for e, p in zip(events, peaks) if db(p) > db(top) - EVENT_PEAK_RANGE_DB]
    shots = []
    for k, e in enumerate(kept):
        nxt = kept[k + 1] if k + 1 < len(kept) else len(m)
        if (nxt - e) / RATE >= MIN_GAP_S:
            shots.append(e)
    return shots


def channel_onset(ch: np.ndarray, near: int) -> int:
    lo, hi = max(0, near - int(RATE * 0.006)), min(len(ch), near + int(RATE * 0.012))
    seg = np.abs(ch[lo:hi])
    peak = float(seg.max())
    first = int(np.argmax(seg > peak * 0.05))
    return lo + first


def cut_tail(ch: np.ndarray, onset: int, limit: int, noise: float) -> tuple[int, bool]:
    """Конец хвоста: огибающая ушла под порог и держится там 150 мс. Чужой звук в хвосте
    (см. BUMP_*) — конец перед ним. Возвращает (конец, чистый)."""
    seg = ch[onset: limit]
    env = moving_rms(seg, int(RATE * 0.04))
    peak = float(env[: int(RATE * 0.06)].max())
    thr = max(peak * 10 ** (-TAIL_DB / 20), noise * 2.0)
    hold = int(RATE * 0.15)
    below = env < thr
    end = len(seg)
    run = 0
    start_i = int(RATE * 0.08)
    for i in range(start_i, len(seg)):
        run = run + 1 if below[i] else 0
        if run >= hold:
            end = i - hold + int(RATE * 0.05)
            break
    clean = True
    # Затухание идёт вниз; резкий подъём над уже достигнутым минимумом — либо эхо от опушки и
    # стен (оставляем), либо чужой звук после хвоста: голос, лязг (режем перед ним).
    lvl = 20 * np.log10(np.maximum(env[:end], 1e-12))
    floor_run = np.minimum.accumulate(lvl)
    after = int(RATE * BUMP_FROM_S)
    bumps = np.where((lvl[after:] - floor_run[after:] > BUMP_DB) & (lvl[after:] > db(thr) + 6.0))[0]
    if len(bumps):
        clean = False
        end = after + int(bumps[0]) - int(RATE * 0.03)
    return onset + max(end, int(RATE * 0.12)), clean


def finish(y: np.ndarray, max_len: float) -> np.ndarray:
    y = y[: int(RATE * max_len)].copy()
    n_in = int(RATE * PRE_ROLL_S * 0.5)
    y[:n_in] *= 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, n_in))
    n_out = max(int(RATE * 0.12), int(len(y) * 0.3))
    n_out = min(n_out, len(y) - n_in)
    y[-n_out:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, n_out))
    return y


def limit(y: np.ndarray, ceiling_db: float, release_s: float) -> np.ndarray:
    """Ограничитель с упреждением: усиление заранее опускается под пик и плавно отпускается."""
    ceiling = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(y), 1e-12))
    la = max(1, int(RATE * LIMIT_LOOKAHEAD_S))
    # на время упреждения вперёд — наименьшее нужное усиление
    g = ndimage.minimum_filter1d(need, size=2 * la + 1, origin=-la // 2, mode="nearest")
    rel = 1.0 - math.exp(-1.0 / (RATE * release_s))
    out_g = np.empty_like(g)
    cur = 1.0
    for i in range(len(g)):
        cur = g[i] if g[i] < cur else cur + (1.0 - cur) * rel
        out_g[i] = cur
    # сгладить спуск, чтобы не щёлкало, и не пропустить ни одного пика
    smooth = np.convolve(out_g, np.hanning(la) / np.hanning(la).sum(), mode="same")
    return y * np.minimum(smooth, need)


def densify(y: np.ndarray, layer: str) -> np.ndarray:
    cfg = DENSITY.get(layer)
    if not cfg:
        return y
    yn = y / max(true_peak(y), 1e-9) * 10 ** (PEAK_LIMIT_DB / 20)
    heavy = limit(yn * 10 ** (cfg["lift"] / 20), PEAK_LIMIT_DB - 0.3, DENSITY_RELEASE_S)
    heavy *= 10 ** (PEAK_LIMIT_DB / 20) / max(true_peak(heavy), 1e-9)
    return (1.0 - cfg["mix"]) * yn + cfg["mix"] * heavy


def normalize(y: np.ndarray, onset: int, layer: str) -> tuple[np.ndarray, float, float, float]:
    """Громкость первых 150 мс → TARGET_EARLY_DB, пик ≤ PEAK_LIMIT_DB. Возвращает (звук, усиление,
    громкость начала, пик)."""
    cfg = LIMIT[layer]
    gain = 0.0
    out = y
    # ограничитель снимает пик, громкость начала растёт медленнее усиления — несколько проходов
    for _ in range(8):
        gain += TARGET_EARLY_DB - early_db(out, onset)
        over = db(true_peak(y)) + gain - (PEAK_LIMIT_DB - 0.3)
        if over > cfg["gr"]:
            gain -= over - cfg["gr"]
        out = y * 10 ** (gain / 20)
        if over > 0.0:
            out = limit(out, PEAK_LIMIT_DB - 0.3, cfg["rel"])
    tp = db(true_peak(out))
    if tp > PEAK_LIMIT_DB:
        out *= 10 ** ((PEAK_LIMIT_DB - tp) / 20)
        gain += PEAK_LIMIT_DB - tp
    return out, gain, early_db(out, onset), db(true_peak(out))


def air_filter(extra_m: float) -> np.ndarray:
    freqs = [f for f, _ in AIR_DB_PER_M]
    gains = [10 ** (max(-60.0, -a * extra_m) / 20) for _, a in AIR_DB_PER_M]
    nyq = RATE / 2
    f = np.array(freqs, dtype=float) / nyq
    f[-1] = 1.0
    lin = signal.firwin2(1025, f, gains)
    # минимальная фаза: у выстрела не появится «предэхо» перед ударом
    return signal.minimum_phase(lin, method="homomorphic")


def rumble_ir(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(RATE * RUMBLE["t60_s"] * 1.1)
    t = np.arange(n) / RATE
    env = (1.0 - np.exp(-t / (RUMBLE["rise_s"] / 3))) * 10 ** (-3 * t / RUMBLE["t60_s"])
    ir = rng.standard_normal(n) * env
    width = int(RATE * RUMBLE["echo_s"])
    for at, over_db in RUMBLE["echoes"]:
        i = int(RATE * (at + rng.uniform(-0.04, 0.04)))
        if i + width > n:
            continue
        diffuse = 10 ** (-3 * at / RUMBLE["t60_s"])
        # громкость окна Ханна по энергии ≈ 0.6 от пика — поправка, чтобы «над гулом» было честно
        burst = rng.standard_normal(width) * np.hanning(width) * diffuse * 10 ** (over_db / 20) / 0.61
        ir[i: i + width] += burst
    sos = signal.butter(2, RUMBLE["lowpass_hz"], btype="lowpass", fs=RATE, output="sos")
    return signal.sosfilt(sos, ir)


def make_distant(far: np.ndarray, onset: int, seed: int) -> np.ndarray:
    direct = signal.fftconvolve(far, air_filter(DISTANT_EXTRA_M))[: len(far)]
    tail = signal.fftconvolve(direct, rumble_ir(seed))
    e_direct = float(np.sum(direct ** 2))
    e_tail = float(np.sum(tail ** 2)) + 1e-20
    tail *= math.sqrt(e_direct / e_tail) * 10 ** (RUMBLE["energy_db"] / 20)
    out = np.zeros(max(len(tail), len(direct)))
    out[: len(direct)] += direct
    out[: len(tail)] += tail
    # конец — где раскат ушёл под порог хвоста, без тихого остатка
    env = moving_rms(out, int(RATE * 0.04))
    alive = np.where(env > env.max() * 10 ** (-TAIL_DB / 20))[0]
    return out[: int(alive[-1]) + int(RATE * 0.05)] if len(alive) else out


def write_wav(path: Path, y: np.ndarray, seed: int) -> str:
    rng = np.random.default_rng(seed)
    lsb = 1.0 / 32768
    dither = (rng.uniform(-0.5, 0.5, len(y)) + rng.uniform(-0.5, 0.5, len(y))) * lsb
    q = np.clip(np.round((y + dither) * 32767), -32768, 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    sf.write(buf, q, RATE, subtype="PCM_16", format="WAV")
    data = buf.getvalue()
    path.write_bytes(data)
    return sha256(data)


def layer_event(event: str, layer: str) -> str:
    return event if layer == "near" else f"{event}_{layer}"


def prepare_layer(z, index, tracks: list[str], layer: str, limit: int) -> tuple[list[dict], list[dict]]:
    """Все годные варианты слоя → отобрать до limit: разные выстрелы, оба канала по очереди."""
    variants: list[dict] = []
    sources: list[dict] = []
    for name in tracks:
        x, meta = load_track(z, index, name)
        sources.append(meta)
        shots = find_shots(x)
        noise = float(np.percentile(moving_rms(np.abs(x).max(axis=1), int(RATE * 0.03)), 8)) + 1e-9
        corr = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) if x.shape[1] > 1 else 1.0
        spaced = x.shape[1] > 1 and corr < 0.85
        channels = list(range(x.shape[1])) if spaced else [-1]
        for si, shot in enumerate(shots):
            nxt = shots[si + 1] if si + 1 < len(shots) else len(x)
            for c in channels:
                ch = x[:, c] if c >= 0 else x.mean(axis=1)
                on = channel_onset(ch, shot)
                start = max(0, on - int(RATE * PRE_ROLL_S))
                limit_i = min(nxt - int(RATE * 0.02), on + int(RATE * MAX_LEN[layer]))
                end, clean = cut_tail(ch, on, limit_i, noise)
                if (end - on) / RATE < 0.35:
                    continue
                y = finish(ch[start:end], MAX_LEN[layer])
                variants.append({"track": name, "shot": si + 1, "channel": "LR"[c] if c >= 0 else "M",
                                 "onset_s": round(on / RATE, 4), "start_s": round(start / RATE, 4),
                                 "len_s": round(len(y) / RATE, 3), "clean": clean, "audio": y,
                                 "onset_in": on - start, "early_raw": early_db(y, on - start)})
    if not variants:
        return [], sources
    med = float(np.median([v["early_raw"] for v in variants]))
    for v in variants:
        v["score"] = abs(v["early_raw"] - med) + (0.0 if v["clean"] else 6.0)
    # по очереди из разных дорожек и выстрелов, внутри — сначала ровные по громкости и чистые
    groups: dict[tuple, list[dict]] = {}
    for v in sorted(variants, key=lambda v: v["score"]):
        groups.setdefault((v["track"], v["shot"]), []).append(v)
    order = sorted(groups.values(), key=lambda g: g[0]["score"])
    picked: list[dict] = []
    while len(picked) < limit and any(order):
        for g in order:
            if g and len(picked) < limit:
                picked.append(g.pop(0))
    return [v for v in picked if v["score"] < 12.0], sources


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="ключи наборов через запятую")
    ap.add_argument("--force", action="store_true", help="перезаписать и одобренные кандидаты")
    args = ap.parse_args()
    only = {k for k in args.only.split(",") if k}

    selection: dict = json.loads(SELECTION.read_text(encoding="utf-8")) if SELECTION.is_file() else {}
    recipe: dict = json.loads(RECIPE.read_text(encoding="utf-8")) if RECIPE.is_file() else {}
    recipe.update({"id": "firearm_layers", "version": VERSION, "library": str(ZIP.relative_to(ROOT)).replace("\\", "/"),
                   "source": SOURCE, "license": "CC0 1.0", "rate": RATE, "target_early_db": TARGET_EARLY_DB,
                   "peak_limit_db": PEAK_LIMIT_DB, "limit": LIMIT, "density": DENSITY, "distant_extra_m": DISTANT_EXTRA_M, "rumble": RUMBLE})
    recipe.setdefault("sets", {})

    z = zipfile.ZipFile(ZIP)
    index = {i.filename.rsplit("/", 1)[1][:-4]: i.filename for i in z.infolist()
             if i.filename.startswith("Master Tracks/") and i.filename.endswith(".wav")}

    for s in SETS:
        if only and s["key"] not in only:
            continue
        set_dir = OUT / s["title"]
        rel_prefix = f"{OUT_NAME}/{s['title']}/"
        protected = [k for k, v in selection.items() if k.startswith(rel_prefix) and (v.get("use") or v.get("moved"))]
        if protected and not args.force:
            print(f"{s['key']}: пропущен — уже есть одобренные или перенесённые ({len(protected)}), --force перезапишет")
            continue
        for k in [k for k in selection if k.startswith(rel_prefix)]:
            del selection[k]
        if set_dir.exists():
            shutil.rmtree(set_dir)
        outputs: list[dict] = []
        all_sources: list[dict] = []
        far_picked: list[dict] = []
        for layer, tracks in s["layers"].items():
            picked, sources = prepare_layer(z, index, tracks, layer, int(s["max"]))
            all_sources += sources
            if layer == "far":
                far_picked = picked
            for v in picked:
                out, gain, e, pk = normalize(densify(v["audio"], layer), v["onset_in"], layer)
                name = f"{v['track']}_{v['shot']}{v['channel']}.wav"
                path = set_dir / LAYER_DIRS[layer] / name
                digest = write_wav(path, out, int(sha256(name.encode())[:8], 16))
                outputs.append({"file": path.relative_to(TRY).as_posix(), "event": layer_event(s["event"], layer),
                                "layer": layer, "track": v["track"], "shot": v["shot"], "channel": v["channel"],
                                "onset_s": v["onset_s"], "len_s": v["len_s"], "clean": v["clean"],
                                "gain_db": round(gain, 2), "early_db": round(e, 2), "peak_db": round(pk, 2), "sha256": digest})
        if s["distant"]:
            for k, v in enumerate(far_picked[: max(3, int(s["max"]) - 2)]):
                seed = int(sha256(f"{s['key']}{v['track']}{v['shot']}{v['channel']}".encode())[:8], 16)
                y = finish(make_distant(v["audio"], v["onset_in"], seed), MAX_LEN["distant"])
                out, gain, e, pk = normalize(y, v["onset_in"], "distant")
                name = f"{v['track']}_{v['shot']}{v['channel']}_далеко.wav"
                path = set_dir / LAYER_DIRS["distant"] / name
                digest = write_wav(path, out, seed & 0xFFFF)
                outputs.append({"file": path.relative_to(TRY).as_posix(), "event": layer_event(s["event"], "distant"),
                                "layer": "distant", "track": v["track"], "shot": v["shot"], "channel": v["channel"],
                                "from": "far", "seed": seed, "len_s": round(len(out) / RATE, 3),
                                "gain_db": round(gain, 2), "early_db": round(e, 2), "peak_db": round(pk, 2), "sha256": digest})
        for o in outputs:
            selection[o["file"]] = {"assigned": o["event"], "license": "cc0_1", "moved": "", "origin": o["file"],
                                    "seen": False, "source": SOURCE, "use": False}
        recipe["sets"][s["key"]] = {"event": s["event"], "title": s["title"], "gun": s["gun"],
                                   "layers": s["layers"], "sources": all_sources, "outputs": outputs}
        counts = {}
        for o in outputs:
            counts[o["layer"]] = counts.get(o["layer"], 0) + 1
        print(f"{s['key']}: {counts}", flush=True)
        SELECTION.write_text(json.dumps(selection, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8", newline="\n")
        RECIPE.parent.mkdir(parents=True, exist_ok=True)
        RECIPE.write_text(json.dumps(recipe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
