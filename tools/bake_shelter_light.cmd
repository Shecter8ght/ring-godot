@echo off
chcp 65001 >nul
rem Запекание света убежища (LightmapGI): редактор открывает сцену, плагин addons/ring_tools жмёт
rem «Bake Lightmaps» по всем вариантам погоды и питания (ShelterWeather, ~15 мин) и закрывается.
rem Перед ним — tools/author_shelter_light.tscn (он пишет список вариантов).
set SDL_JOYSTICK_DIRECTINPUT=0
set RING_BAKE_LIGHTMAP=@res://levels/shelter/lightmap/variants.txt
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" -e --path "%~dp0.."
set RING_BAKE_LIGHTMAP=
