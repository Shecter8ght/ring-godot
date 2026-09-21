@echo off
chcp 65001 >nul
rem Дымовая проверка: запускает сцену, делает скриншот в docs/screens и выходит.
rem tools\smoke.cmd [res://scenes/levels/xxx.tscn] [кадров] [overview]
set SCENE=%1
if "%SCENE%"=="" set SCENE=res://scenes/levels/f1_market.tscn
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64_console.exe" --path "%~dp0.." --script res://tools/smoke.gd -- %SCENE% %2 %3
