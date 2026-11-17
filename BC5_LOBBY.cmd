@echo off
setlocal
echo Opening Prospekt 5, street to Meeting Room 203...
call "%~dp0tools\godot.cmd" --windowed --resolution 1600x900 res://tools/bc5_lobby203/lobby203.tscn %*
set "bc5_lobby_exit=%errorlevel%"
if "%bc5_lobby_exit%"=="0" exit /b 0
echo Godot exited with code %bc5_lobby_exit%.
if "%~1"=="" pause
exit /b %bc5_lobby_exit%
