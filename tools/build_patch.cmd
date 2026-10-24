@echo off
chcp 65001 >nul
rem Обновление для друзей патчем вместо полного архива: в патче только файлы, изменённые с основы (--export-patch).
rem Основа — последний полный выпуск tools/build_release.cmd (он же должен быть у друзей).
rem Патчи накопительные: каждый несёт все изменения от основы, друзьям нужен только последний.
rem Итог: export\patches\RING_patch_<N>_<метка основы>.pck — положить в папку patches рядом с RING.exe.
rem Изменились project.godot или загрузчик src\core\release_patch.gd — патч не соберётся: игра читает
rem их до подключения патча, нужен полный выпуск.
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
python -X utf8 "%~dp0release_patch.py" check || exit /b 1
if not exist "%ROOT%\export\patches" mkdir "%ROOT%\export\patches"
if exist "%ROOT%\export\patches\next.pck" del /q "%ROOT%\export\patches\next.pck"
call "%~dp0godot.cmd" --headless --export-patch "Windows Desktop" "%ROOT%\export\patches\next.pck" --patches "%ROOT%\export\RING\RING.pck" || exit /b 1
python -X utf8 "%~dp0release_patch.py" pack "%ROOT%\export\patches\next.pck" || exit /b 1
