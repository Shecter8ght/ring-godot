# RING — первый геймплейный трейлер

Готовый локальный файл: `brag.mp4`. Обложка: `brag.jpg`.
36 с, 1920×1080, 30 fps, H.264 + AAC, русские титры, без диктора.
Подпись для публикации: `share-copy.txt`. Публикация автоматически не выполняется.

## Повторная запись и монтаж

Требуются Godot из `tools/godot.cmd`, Python с numpy/scipy, FFmpeg и Node.js 22+.
Команды из корня игры, PowerShell:

```powershell
New-Item -ItemType Directory -Force export/trailer | Out-Null
tools/godot.cmd --windowed --resolution 1920x1080 --disable-vsync --write-movie export/trailer/raw.avi --fixed-fps 30 res://tools/trailer_capture.tscn
python tools/trailer_build.py
Set-Location brag-output/composition
npx --yes hyperframes@0.8.79 check
npx --yes hyperframes@0.8.79 render --quality delivery --fps 30 --workers 3 --no-best-effort --frames-cache-dir E:/Games/RING-godot/export/trailer/frame-cache --output ../brag-render.mp4
```

Большие файлы записи, промежуточные клипы, аудио, кэши и MP4 исключены из git.
`trailer_build.py` нарезает клипы по маркерам Godot, синтезирует собственную музыку
и при необходимости скачивает шрифты/GSAP с сохранением лицензий.
Ролик можно править в `composition/index.html` или открыть редактор:

```powershell
npx --yes hyperframes@0.8.79 preview --background
```

Для финального файла из `brag-output`:

```powershell
ffmpeg -y -ss 34.2 -i brag-render.mp4 -frames:v 1 -q:v 2 brag.jpg
ffmpeg -y -i brag-render.mp4 -i brag.jpg -filter_complex "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]" -map "[v]" -map 0:a -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -af loudnorm=I=-16:TP=-1.5:LRA=9 -c:a aac -b:a 192k -ar 48000 -t 36 -movflags +faststart brag.mp4
```

## Что снято

Это постановочная автоматическая запись настоящего `f1_ring`, а не ручная игра.
Оператор защищён от гибели; персонажи расставлены перед дублем. Стрельба, AI,
обыск сейфа, кнопка «Взять всё», перенос предметов и эвакуация работают через
существующие игровые системы. Сохранения пользователя не используются.
Титр «В разработке» указывает на текущую стадию проекта и серый блокаут уровня.

## Проверки

Godot: окно обыска открывается, предметы перенесены, `extracted=true`.
Hyperframes: check без ошибок runtime/layout/motion/contrast; 30/30 текстовых
проверок WCAG AA. Семь рекомендаций по разбивке короткой композиции на отдельные
HTML-файлы оставлены: на изображение и воспроизведение они не влияют.
Финальный ролик проверяется после кодирования, а не только по предпросмотру.

## Источники

- Процесс: [brag](https://github.com/latent-spaces/brag), MIT.
- Монтаж и образец появления слов: [Hyperframes](https://github.com/heygen-com/hyperframes), Apache-2.0.
- Шрифты: [Oswald](https://github.com/google/fonts/tree/main/ofl/oswald),
  [Golos Text](https://github.com/google/fonts/tree/main/ofl/golostext), SIL OFL.
- GSAP 3.14.2: https://gsap.com/standard-license/ (зависимость монтажного инструмента).
- Эмблема воспроизводит кольцо и центральную точку из собственного `icon.svg`.
- Музыкальная подложка синтезирована собственным скриптом, внешняя музыка не использована.
