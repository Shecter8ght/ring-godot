@echo off
chcp 65001 >nul
setlocal
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_grass_probe.tscn %*
set "grass_probe_exit=%errorlevel%"
if "%grass_probe_exit%"=="0" exit /b 0
echo Godot exited with code %grass_probe_exit%.
if "%~1"=="" pause
exit /b %grass_probe_exit%
