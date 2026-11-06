"""Package only application sources; never include caches, projects or test media."""
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
destination = Path(sys.argv[1]) if len(sys.argv) > 1 else root/'dist'/'Sonora-Studio-source.zip'
destination.parent.mkdir(parents=True, exist_ok=True)
names = ['package.json', 'package-lock.json', 'README.ru.md', 'THIRD-PARTY-NOTICES.md', 'LICENSE.txt', '.gitignore']
files = [root/name for name in names]
files.extend([root/'Инструменты для звуков Ring.md',root/'Новое в Sonora 1.1.md',root/'Новое в Sonora 1.2.md',root/'Новое в Sonora 1.3.md',root/'Новое в Sonora 1.4.md',root/'Новое в Sonora 1.5.md',root/'Новое в Sonora 1.6.md'])
for name in ['src', 'ui', 'assets', 'tools', 'tests', 'scripts', 'examples']:
    files.extend(p for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend([root/'vendor'/'FFmpeg-LICENSE.txt', root/'vendor'/'FFmpeg-BUILD-CONFIGURATION.txt'])
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for source in files:
        archive.write(source, Path('Sonora-Studio-source')/source.relative_to(root))
print(f'{destination.name}: {destination.stat().st_size:,} bytes, {len(files)} files')
