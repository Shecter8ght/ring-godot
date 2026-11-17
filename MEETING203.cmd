@echo off
setlocal
echo Opening Meeting Room 203...
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://tools/bc5_meeting203/meeting203.tscn %*
set "meeting203_exit=%errorlevel%"
if "%meeting203_exit%"=="0" exit /b 0
echo Godot exited with code %meeting203_exit%.
if "%~1"=="" pause
exit /b %meeting203_exit%
