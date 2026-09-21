@echo off
chcp 65001 >nul
rem Единственное место, где записан путь к Godot (кроме RING.cmd/EDITOR.cmd в корне).
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64_console.exe" --path "%~dp0.." %*
