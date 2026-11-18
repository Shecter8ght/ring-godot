@echo off
setlocal
echo Opening Unfinished Building...
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://tools/unfinished_building/unfinished_building.tscn %*
set "unfinished_exit=%errorlevel%"
if "%unfinished_exit%"=="0" exit /b 0
echo Godot exited with code %unfinished_exit%.
if "%~1"=="" pause
exit /b %unfinished_exit%
