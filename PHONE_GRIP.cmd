@echo off
chcp 65001 >nul
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://tools/phone_grip_lab.tscn %*
