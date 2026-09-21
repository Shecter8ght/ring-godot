@echo off
chcp 65001 >nul
rem Запуск игры без редактора (главная сцена из project.godot).
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe" --path "%~dp0." %*
