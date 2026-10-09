"""Упаковать сборку потоково в ZIP64: RING.pck уже превышает лимит Compress-Archive."""

from pathlib import Path
import argparse
import os
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    archive = args.archive.resolve()
    if not source.is_dir() or archive.is_relative_to(source):
        parser.error("Нужна папка сборки и архив за её пределами")
    temporary = archive.with_name(archive.name + ".tmp")
    # Старый готовый архив заменяется только после успешной упаковки всех файлов.
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as package:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(source).as_posix())
    os.replace(temporary, archive)
    print(f"ZIP64: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
