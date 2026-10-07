@echo off
chcp 65001 >nul
rem Чистовое запекание света убежища (LightmapGI) — перед сборкой игры, ~10-15 мин на все 12 вариантов.
rem Редактор открывается, плагин addons/ring_tools жмёт «Bake Lightmaps» по вариантам погоды и питания
rem (ShelterWeather) и закрывается. Перед ним — tools/author_shelter_light.tscn (он пишет список вариантов).
rem Только нужные варианты: bake_shelter_light.cmd day_sun night_grey  (вид: day/dusk/night + _sun/_grey, + _off без генератора)
rem Быстро для проверки правок — bake_shelter_light_draft.cmd.
set SDL_JOYSTICK_DIRECTINPUT=0
set RING_BAKE_LIGHTMAP=@res://levels/shelter/lightmap/variants.txt
set RING_BAKE_QUALITY=final
set RING_BAKE_ONLY=%*
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" -e --path "%~dp0.."
set RING_BAKE_LIGHTMAP=
set RING_BAKE_QUALITY=
set RING_BAKE_ONLY=
