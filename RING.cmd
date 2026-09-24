@echo off
chcp 65001 >nul
rem Запуск игры без редактора (главная сцена из project.godot).
rem Опрос геймпадов через DirectInput на этом ПК висит ~40 с при старте (какое-то устройство
rem не отвечает) — игре геймпад не нужен, выключаем (XInput/RawInput остаются).
set SDL_JOYSTICK_DIRECTINPUT=0
"D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe" --path "%~dp0." %*
