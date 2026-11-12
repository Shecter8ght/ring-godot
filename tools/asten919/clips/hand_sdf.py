"""АСТЕН-919, клипы рук: поля расстояний пистолета для посадки кистей и проверки «рука в оружии».

Поля деталей high-poly (tools/asten919/build.py: _asset_src/asten919/fine, plain) обрезаны узкой полосой у поверхности
(±4 вокселя) — для подгонки хвата нужна настоящая дальность. Здесь детали собираются в четыре группы по тому, как они
двигаются в клипах, на общую сетку 0,4 мм, знак берётся из полей, дальность — преобразованием расстояний (scipy):

  static  — рамка с начинкой, ствол с гайкой, направляющая пружины, кнопка магазина, рычаг задержки, защёлка затвора;
  slide   — затвор с прицельными, крышками и выбрасывателем;
  mag     — корпус магазина с пяткой и вкладышем;
  trigger — спуск с предохранителем;
  whole   — всё вместе в положении покоя, пустоты (шахта, полость затвора) залиты: «сплошной пистолет» для посадки
            кисти в хвате (сквозь тонкую стенку рукояти подбор иначе «проваливается» в шахту).

Оси и единицы — исходника (мм; +X дуло, +Z верх, −Y правая сторона стрелка). Читает их tools/asten919/clips/sdf_grid.py.

python -X utf8 tools/asten919/clips/hand_sdf.py [группа …]   → _asset_src/asten919/anim/sdf/<группа>.npz
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "_asset_src/asten919"
OUT = SRC / "anim/sdf"
H = 0.4
CLOSE_R = 2.6
PAD = 30.0                                    # запас вокруг детали: дальше — «далеко», значение обрезано
GROUPS = {
    "static": ["Frame", "Locking_Block", "Trigger_Housing", "Barrel_Threaded", "Thread_Protector", "Guide_Rod",
               "Mag_Catch", "Slide_Stop", "Slide_Lock"],
    "slide": ["Slide", "Slide_Cover_Plate", "Extractor", "MOS_Cover_Plate", "Front_Sight", "Rear_Sight"],
    "mag": ["Magazine_Body", "Magazine_Floorplate", "Magazine_Insert"],
    "trigger": ["Trigger", "Trigger_Safety"],
}
# рамка и затвор без мелкого рельефа (plain, воксель 0,16–0,2 мм) — вчетверо легче, для кисти разницы нет
PLAIN = {"Frame", "Slide"}


def field_of(name):
    path = (SRC / "plain" if name in PLAIN else SRC / "fine") / f"{name}.npz"
    d = np.load(path)
    return d["field"], float(d["h"]), np.array(d["lo"], float)


def build(group):
    t = time.time()
    parts = [(n, *field_of(n)) for n in GROUPS[group]]
    lo = np.min([p[3] for p in parts], axis=0) - PAD
    hi = np.max([p[3] + np.array(p[1].shape) * p[2] for p in parts], axis=0) + PAD
    n = np.ceil((hi - lo) / H).astype(int) + 1
    inside = np.zeros(n, bool)
    axes = [lo[i] + np.arange(n[i]) * H for i in range(3)]
    for name, f, h, plo in parts:
        idx, ok = [], []
        for i in range(3):
            k = np.rint((axes[i] - plo[i]) / h).astype(int)
            good = (k >= 0) & (k < f.shape[i])
            idx.append(np.clip(k, 0, f.shape[i] - 1))
            ok.append(good)
        sub = f[np.ix_(*idx)] < 0
        sub &= ok[0][:, None, None] & ok[1][None, :, None] & ok[2][None, None, :]
        inside |= sub
        print(f"  {name}: воксель {h:.3f}, внутри {int(sub.sum())} ячеек", flush=True)
    out = ndimage.distance_transform_edt(~inside, sampling=H)
    inn = ndimage.distance_transform_edt(inside, sampling=H)
    sdf = (out - inn).astype(np.float32)
    sdf -= np.sign(sdf) * (H * 0.5)            # граница — между ячейками
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"{group}.npz", sdf=sdf.astype(np.float16), h=H, lo=lo)
    print(f"SDF {group}: сетка {tuple(n)}, от {lo.round(1)} до {hi.round(1)} мм, {time.time() - t:.1f} с", flush=True)
    return dict(lo=lo.round(3).tolist(), shape=[int(v) for v in n], h=H, parts=GROUPS[group])


def build_whole():
    """Все группы на сетке static; щели до 1,2 мм закрыты, замкнутые пустоты залиты (окно скобы остаётся)."""
    t = time.time()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sdf_grid import Grid
    base = np.load(OUT / "static.npz")
    lo = np.array(base["lo"], float)
    n = base["sdf"].shape
    inside = base["sdf"].astype(np.float32) < 0
    ax = [lo[i] + np.arange(n[i]) * H for i in range(3)]
    for g in ("slide", "mag", "trigger"):
        grid = Grid.load(g)
        # только ячейки внутри коробки группы
        sel = [np.where((ax[i] >= grid.lo[i]) & (ax[i] <= grid.lo[i] + (grid.n[i] - 2) * grid.h))[0] for i in range(3)]
        X, Y, Z = np.meshgrid(ax[0][sel[0]], ax[1][sel[1]], ax[2][sel[2]], indexing="ij")
        d = grid.dist(np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)).reshape(X.shape)
        inside[np.ix_(*sel)] |= d < 0
    # закрытие радиусом CLOSE_R: раздуть, залить замкнутое, сжать обратно — шахта и полости (сообщаются с улицей
    # только щелями уже 2·CLOSE_R) становятся телом, окно скобы (шире) остаётся
    fat = ndimage.distance_transform_edt(~inside, sampling=H) <= CLOSE_R
    fat = ndimage.binary_fill_holes(fat)
    inside |= ndimage.distance_transform_edt(fat, sampling=H) > CLOSE_R
    out = ndimage.distance_transform_edt(~inside, sampling=H)
    inn = ndimage.distance_transform_edt(inside, sampling=H)
    sdf = (out - inn).astype(np.float32)
    sdf -= np.sign(sdf) * (H * 0.5)
    np.savez_compressed(OUT / "whole.npz", sdf=sdf.astype(np.float16), h=H, lo=lo)
    print(f"SDF whole: сетка {tuple(n)}, {time.time() - t:.1f} с", flush=True)
    return dict(lo=lo.round(3).tolist(), shape=[int(v) for v in n], h=H, parts=["static", "slide", "mag", "trigger"])


def main():
    names = sys.argv[1:] or list(GROUPS) + ["whole"]
    man_path = OUT / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    for g in names:
        man[g] = build_whole() if g == "whole" else build(g)
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
