@echo off
chcp 65001 >nul
rem Запуск игры без редактора (главная сцена из project.godot).
rem Опрос геймпадов через DirectInput на этом ПК висит ~40 с при старте (какое-то устройство
rem не отвечает) — игре геймпад не нужен, выключаем (XInput/RawInput остаются).
set SDL_JOYSTICK_DIRECTINPUT=0
rem Неявные Vulkan-слои оверлеев (RivaTuner, Steam и его кэш шейдеров, Epic) и вывод кадра NVIDIA через
rem DXGI (слой VK_LAYER_NV_present — «Vulkan/OpenGL present method» в панели NVIDIA). 2026-10-18 игра из
rem редактора встала посреди рейда: главный поток ждал кадр внутри этого вывода, видеокарта простаивала.
rem Для разработки они не нужны — выключаем слои (сами программы не трогаем). Вернуть — убрать две строки.
set VK_LOADER_LAYERS_DISABLE=VK_LAYER_RTSS,VK_LAYER_VALVE_steam_overlay,VK_LAYER_VALVE_steam_fossilize,VK_LAYER_EOS_Overlay
set DISABLE_LAYER_NV_PRESENT_1=1
"D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe" --path "%~dp0." %*
