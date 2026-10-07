@echo off
chcp 65001 >nul
rem Тир: полигон с мишенями-попперами, без сети.
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" --path "%~dp0." res://scenes/levels/test_range.tscn
