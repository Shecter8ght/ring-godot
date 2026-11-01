"""Глушитель ГРАНЬ-15: запечённые карты (supp_game.py bake) → карты обвеса-модели игры.

python -X utf8 tools/ar15/supp_pack.py
Источник — _asset_src/ar15/game/supp/raw/Supp_{color,rough,metal,normal,ao}.png.
→ assets/models/attachments/supp_gran/supp_gran_100_{base_color,roughness,metallic,normal}.png — как у прочих обвесов-моделей
(WeaponMods._model_material: шероховатость и металл — отдельными картами, канал R; вид один при любой прочности).
Слота затенения у материала обвеса нет — затенение самой игровой сетки (щели у рычага защёлки, между рёбрами) ложится
в цвет вполсилы. Поля островов добираются тем же «push-pull», что у ствола (game_pack.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ar15'))
import game_pack  # noqa: E402

RAW = ROOT / '_asset_src/ar15/game/supp/raw'
OUT = ROOT / 'assets/models/attachments/supp_gran'
TAG = 'supp_gran_100'
AO_IN_COLOR = 0.5


def main() -> None:
    read = lambda ch: game_pack.read(RAW / f'Supp_{ch}.png')
    color, rough, metal, normal, ao = (read(c) for c in ('color', 'rough', 'metal', 'normal', 'ao'))
    g = lambda x: x[..., 0] if x.ndim == 3 else x
    mask = ((g(ao) > 0) | (g(rough) > 0) | (g(metal) > 0) | (color.max(-1) > 0)).astype(np.float32)
    shade = 1.0 - AO_IN_COLOR * (1.0 - g(ao))
    OUT.mkdir(parents=True, exist_ok=True)
    game_pack.write(OUT / f'{TAG}_base_color.png', game_pack.push_pull(color * shade[..., None], mask))
    game_pack.write(OUT / f'{TAG}_roughness.png', game_pack.push_pull(g(rough), mask))
    game_pack.write(OUT / f'{TAG}_metallic.png', game_pack.push_pull(g(metal), mask))
    n = game_pack.push_pull(normal, mask)
    v = n * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
    game_pack.write(OUT / f'{TAG}_normal.png', v * 0.5 + 0.5)
    print('SUPP_PACK запечено', round(float(mask.mean()), 3), 'металл средний', round(float(g(metal)[mask > 0].mean()), 3),
          'шероховатость средняя', round(float(g(rough)[mask > 0].mean()), 3), flush=True)


main()
