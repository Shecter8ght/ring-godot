@echo off
chcp 65001 >nul
rem Сборка для друзей без шаблонов экспорта: данные игры — export\RING\RING.pck (--export-pack),
rem запускалка — сам Godot 4.5.1 под именем RING.exe (видит RING.pck рядом и запускает игру).
rem Итог: export\RING.zip — распаковать и запустить RING.exe.
setlocal
set "ROOT=%~dp0.."
set "GODOT_DIR=D:\ПРОГРАММЫ\Godot_v4.5.1-stable_win64.exe"
if not exist "%ROOT%\export\RING" mkdir "%ROOT%\export\RING"
call "%~dp0godot.cmd" --headless --export-pack "Windows Desktop" export/RING/RING.pck || exit /b 1
copy /y "%GODOT_DIR%\Godot_v4.5.1-stable_win64.exe" "%ROOT%\export\RING\RING.exe" >nul || exit /b 1
copy /y "%~dp0release_readme.txt" "%ROOT%\export\RING\КАК ИГРАТЬ.txt" >nul
copy /y "%~dp0release_fast_start.cmd" "%ROOT%\export\RING\RING (если долго запускается).cmd" >nul
if exist "%ROOT%\export\RING.zip" del "%ROOT%\export\RING.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%ROOT%\export\RING\*' -DestinationPath '%ROOT%\export\RING.zip' -CompressionLevel Optimal" || exit /b 1
echo Готово: export\RING.zip
