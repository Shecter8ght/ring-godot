@echo off
chcp 65001 >nul
rem Дымовая проверка: запускает сцену, делает скриншот в docs/screens и выходит.
rem tools\smoke.cmd [res://scenes/levels/xxx.tscn] [кадров] [overview]
set SCENE=%1
if "%SCENE%"=="" set SCENE=res://scenes/levels/f1_ring.tscn
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" --path "%~dp0.." res://tools/smoke.tscn -- %SCENE% %2 %3
