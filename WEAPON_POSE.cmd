@echo off
chcp 65001 >nul
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://scenes/debug/weapon_pose_lab.tscn %*
