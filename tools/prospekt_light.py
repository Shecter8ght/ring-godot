# -*- coding: utf-8 -*-
"""Свет «Проспекта» — один на блокаут и рейд (AGENTS.md п. 10). Владелец 2026-10-26 выбрал на стенде
(tools/prospekt_light_variants.gd, docs/screens/prospekt/light_stand_*.jpg) вариант «всё вместе» — черты освещения EFT
поверх умолчаний Godot: перепад (солнце сильнее, рассеянный слабее), бирюзовый холод (небо голубее, тени в холодную
зелень, солнце тёплое), дымка по расстоянию, тени в углах (SSAO), тёмные помещения (SDFGI). Резкость поверх кадра
(слой screen_sharpen, сила 1,8) убрана по слову владельца 2026-10-29: «свет хорош, резкость убрать».

Окружение — scenes/levels/prospekt/prospekt_environment.tres (пишет tools/build_prospekt.py, ссылаются обе сцены).
В рейде силу солнца, рассеянный и выдержку по времени суток задаёт RaidAtmosphere, дымку по погоде — RaidWeather:
поправки карты — LIGHT_KEYS и DEPTH_FOG в данных сектора (tools/build_prospekt_raid.py).
"""

ENV_PATH = "res://scenes/levels/prospekt/prospekt_environment.tres"

# окружение (.tres): небо, рассеянный, тонмаппинг, свечение, SSAO, SDFGI, дымка, цветокоррекция
ENV_TRES = "\n".join([
    '[gd_resource type="Environment" load_steps=5 format=3]',
    '',
    '[sub_resource type="ProceduralSkyMaterial" id="SkyMat"]',
    'sky_top_color = Color(0.24, 0.4, 0.56, 1)', 'sky_horizon_color = Color(0.6, 0.68, 0.74, 1)',
    'ground_bottom_color = Color(0.16, 0.18, 0.16, 1)', 'ground_horizon_color = Color(0.5, 0.56, 0.55, 1)',
    '',
    '[sub_resource type="Sky" id="Sky"]', 'sky_material = SubResource("SkyMat")',
    '',
    # кривые по каналам: красный чуть ниже в середине, зелёный и синий выше — холодная бирюза, света почти белые
    '[sub_resource type="Gradient" id="TealCurve"]',
    'offsets = PackedFloat32Array(0, 0.25, 0.5, 0.75, 1)',
    'colors = PackedColorArray(0, 0.01, 0.018, 1, 0.225, 0.255, 0.265, 1, 0.47, 0.505, 0.52, 1, 0.735, 0.76, 0.77, 1, 0.985, 1, 1, 1)',
    '',
    '[sub_resource type="GradientTexture1D" id="TealLUT"]', 'gradient = SubResource("TealCurve")', 'width = 256',
    '',
    '[resource]',
    'background_mode = 2', 'background_energy_multiplier = 1.15', 'sky = SubResource("Sky")',
    'ambient_light_energy = 0.25',
    'tonemap_mode = 2', 'tonemap_exposure = 0.8',
    'ssao_enabled = true', 'ssao_radius = 2.5', 'ssao_intensity = 4.0', 'ssao_power = 2.0', 'ssao_light_affect = 0.3',
    'sdfgi_enabled = true', 'sdfgi_use_occlusion = true', 'sdfgi_min_cell_size = 0.25',
    'glow_enabled = true',
    'fog_enabled = true', 'fog_mode = 1', 'fog_light_color = Color(0.7, 0.77, 0.82, 1)', 'fog_sun_scatter = 0.15',
    'fog_density = 0.55', 'fog_aerial_perspective = 0.5', 'fog_sky_affect = 0.1',
    'fog_depth_curve = 0.6', 'fog_depth_begin = 50.0', 'fog_depth_end = 900.0',
    'adjustment_enabled = true', 'adjustment_saturation = 0.9', 'adjustment_color_correction = SubResource("TealLUT")',
    # свечение и отскоки SDFGI — как задано здесь (Settings._apply_env их не переделывает)
    'metadata/authored_lighting = true',
    '',
])

# солнце: направление — как у кнопки редактора «Добавить солнце» (60° над горизонтом), сила 2, тёплое, с тенями
SUN_PROPS = [
    'transform = Transform3D(-0.866023, -0.433016, 0.250001, 0, 0.499998, 0.866027, -0.500003, 0.75, -0.43301, 0, 0, 0)',
    'light_color = Color(1, 0.9, 0.76, 1)', 'light_energy = 2.0', 'shadow_enabled = true',
]


# рейд: RaidAtmosphere ставит солнце t.sun_energy × sun_k, рассеянный 0,8 × t.ambient × ambient_k, выдержку t.exposure.
# Днём (солнце 2,2, выдержка 0,9) это даёт то же, что в блокауте: солнце 2 × 0,8, рассеянный 0,25 × 0,8.
# Ночью, в дождь и пасмурно солнца нет или оно слабое — рассеянный режется меньше, ночью он как у других карт
# (0,15–0,18); подобрано снимками tools/prospekt_raid_shots.tscn.
LIGHT_KEYS = {"sun_k": 0.81, "ambient_k": 0.28, "ambient_k_night": 1.8,
              "ambient_k_day_rain": 0.8, "ambient_k_dusk_rain": 0.8, "ambient_k_night_rain": 3.2,
              "ambient_k_day_overcast": 0.5, "ambient_k_dusk_overcast": 0.5, "ambient_k_night_overcast": 2.6}
# привыкание глаза камеры игрока (CameraLook, общее — Balance.LOOK: цель 0,9, светлее до ×5 на улице и ×12 в здании)
# вытягивало тёмный свет карты почти до белого и высветляло помещения в 3 раза (владелец 2026-10-26: «слишком
# выбелено»). Своё у карты: цель ниже, на улице светлее не больше ×2, в здании ×2,5 — помещения остаются тёмными.
LOOK = {"exposure_scale_raid": 0.35, "adapt_up": 2.0, "adapt_up_indoor": 2.5}
# дымка карты в ясную погоду (RaidWeather: иначе — общая Balance.DEPTH_FOG): чисто до 50 м, к 900 м — 0,55
DEPTH_FOG = {"clear": {"begin": 50.0, "end": 900.0, "density": 0.55, "curve": 0.6, "sky": 0.1}}
