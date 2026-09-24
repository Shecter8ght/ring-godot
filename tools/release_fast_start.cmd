@echo off
rem Если RING.exe запускается минуту и дольше — на ПК какое-то устройство не отвечает на
rem опрос геймпадов (DirectInput). Этот запуск его пропускает; геймпад игре не нужен.
set SDL_JOYSTICK_DIRECTINPUT=0
start "" "%~dp0RING.exe" %*
