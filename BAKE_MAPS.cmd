@echo off
chcp 65001 >nul
rem После ручных правок карт в редакторе (docs/level_editing.md): перепечь навигацию ботов и точки укрытия
rem «Пригорода» и снять заново карту «Плана рейда». Без этого игра печёт навигацию сама при каждой загрузке
rem (дольше), боты прячутся за старыми укрытиями, а на плане рейда — прежняя раскладка. Окно Godot на минуту
rem откроется само (снимок карты сверху) — его не трогать.
echo Навигация ботов...
call "%~dp0tools\godot.cmd" --headless res://tools/bake_zone01_nav.tscn
echo Точки укрытия...
call "%~dp0tools\godot.cmd" --headless res://tools/bake_cover_points.tscn -- zone01_mall
echo Карта плана рейда...
call "%~dp0tools\godot.cmd" --windowed --resolution 1280x720 res://tools/raid_map_bake.tscn -- zone01
call "%~dp0tools\godot.cmd" --headless --import
echo Готово.
pause
