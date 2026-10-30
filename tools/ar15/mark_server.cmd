@echo off
rem AR-15: сервис разметки мест износа — сервер и страница в браузере (окно не закрывать, пока размечаете)
cd /d "%~dp0..\.."
start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://localhost:8766/"
python -X utf8 tools\ar15\mark_server.py
