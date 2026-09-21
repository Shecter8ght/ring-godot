@echo off
rem Дымовая проверка: запускает сцену (по умолчанию главную), через 2 с делает скриншот в docs/screens и выходит.
rem tools\smoke.cmd [res://scenes/levels/xxx.tscn]
set SCENE=%1
if "%SCENE%"=="" set SCENE=res://scenes/levels/test_range.tscn
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64_console.exe" --path "%~dp0.." --script res://tools/smoke.gd -- %SCENE%
