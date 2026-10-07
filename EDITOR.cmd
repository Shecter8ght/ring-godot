@echo off
chcp 65001 >nul
rem Открыть проект в редакторе Godot.
rem Опрос геймпадов через DirectInput на этом ПК висит ~40 с при старте (какое-то устройство
rem не отвечает) — игре геймпад не нужен, выключаем (XInput/RawInput остаются).
set SDL_JOYSTICK_DIRECTINPUT=0
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" --path "%~dp0." --editor
