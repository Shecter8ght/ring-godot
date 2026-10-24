@echo off
chcp 65001 >nul
rem Сборка для друзей без шаблонов экспорта: данные игры — export\RING\RING.pck (--export-pack),
rem запускалка — официальный Godot 4.7.2 (не Steam — тот тянет steam_api64.dll) под именем RING.exe (видит RING.pck рядом и запускает игру).
rem Итог: export\RING.zip — распаковать и запустить RING.exe.
setlocal
set "ROOT=%~dp0.."
set "GODOT_DIR=D:\ПРОГРАММЫ\Godot_v4.7.2-stable_win64.exe"
if not exist "%ROOT%\export\RING" mkdir "%ROOT%\export\RING"
call "%~dp0godot.cmd" --headless --export-pack "Windows Desktop" export/RING/RING.pck || exit /b 1
copy /y "%GODOT_DIR%\Godot_v4.7.2-stable_win64.exe" "%ROOT%\export\RING\RING.exe" >nul || exit /b 1
copy /y "%~dp0release_readme.txt" "%ROOT%\export\RING\КАК ИГРАТЬ.txt" >nul || exit /b 1
copy /y "%~dp0release_fast_start.cmd" "%ROOT%\export\RING\RING (если долго запускается).cmd" >nul || exit /b 1
rem Метка основы для патчей (tools/build_patch.cmd): export\RING\patches\base.txt уходит друзьям в архиве.
python -X utf8 "%~dp0release_patch.py" base || exit /b 1
rem ZIP64: потоковая упаковка поддерживает RING.pck больше 2 ГБ; Python нужен только для сборки.
python "%~dp0zip_release.py" "%ROOT%\export\RING" "%ROOT%\export\RING.zip" || exit /b 1
echo Готово: export\RING.zip
