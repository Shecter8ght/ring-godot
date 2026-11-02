@echo off
chcp 65001 >nul
call "%~dp0godot.cmd" --windowed --resolution 1600x900 res://tools/dorm_play.tscn %*
