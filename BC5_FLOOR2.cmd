@echo off
setlocal
echo Opening Prospekt 5, Floor 2...
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://tools/bc5_route203/route203.tscn %*
set "bc5_floor2_exit=%errorlevel%"
if "%bc5_floor2_exit%"=="0" exit /b 0
echo Godot exited with code %bc5_floor2_exit%.
if "%~1"=="" pause
exit /b %bc5_floor2_exit%
