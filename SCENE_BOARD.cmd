@echo off
chcp 65001 >nul
rem Доска сцен: все сцены, стенды и уровни RING на одной странице — запустить, посмотреть, убрать в карантин и вернуть.
rem Страница откроется сама (http://localhost:8767/). Окно не закрывать, пока пользуетесь доской.
rem С телефона в домашней сети, только смотреть: SCENE_BOARD.cmd --lan
cd /d "%~dp0"
python -X utf8 tools\scene_board\server.py --open %*
pause
