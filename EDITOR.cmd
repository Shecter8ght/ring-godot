@echo off
chcp 65001 >nul
rem Открыть проект в редакторе Godot.
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe" --path "%~dp0." --editor
