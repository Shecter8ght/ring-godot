@echo off
rem Painter для отделки контейнеров v03: своя папка заданий, слои Vulkan оверлеев выключены
set VK_LOADER_LAYERS_DISABLE=~implicit~
set DISABLE_RTSS_LAYER=1
set FINISH_SP_JOBS=E:\Games\RING-godot\_asset_src\loot_containers\sp_jobs_v03
cd /d E:\Games\RING-godot
python -X utf8 tools\asset_kit\finish\sp_run.py start
