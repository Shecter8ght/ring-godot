@echo off
chcp 65001 >nul
rem Тир: полигон с мишенями-попперами, без сети.
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe" --path "%~dp0." res://scenes/levels/test_range.tscn
