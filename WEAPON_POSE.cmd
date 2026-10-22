@echo off
chcp 65001 >nul
rem Стенд положения оружия: ползунки и сохранение, F6 — обычное управление.
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://scenes/debug/weapon_pose_lab.tscn %*
