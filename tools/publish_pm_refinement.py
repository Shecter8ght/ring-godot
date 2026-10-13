"""Copy only the reviewed PM manifest files, then verify hashes and gallery links."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import argparse
import hashlib
import json
import shutil

PROJECT = Path(__file__).resolve().parents[1]
LIBRARY = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
MANIFEST = Path('Проверки/package_manifest.json')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def inside(path, root):
    path.resolve().relative_to(root.resolve())
    return path


def relative(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Invalid manifest path: {name}')
    return path


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key not in {'href', 'src', 'data-src'} or not value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                raise ValueError(f'Unexpected remote gallery resource: {value}')
            if parsed.path:
                self.paths.add(unquote(parsed.path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['publish', 'check'])
    parser.add_argument('--revision',default='v06',choices=['v06','v07','v08','v09'])
    args = parser.parse_args()
    STAGE = PROJECT / ('_asset_src/pm_refinement/review_'+args.revision)
    DEST = LIBRARY / {'v06':'08_Доработка_v6_на_проверку','v07':'09_Доработка_v7_на_проверку','v08':'10_Доработка_v8_ЗОРИН_на_проверку','v09':'11_Доработка_v9_Гравировка_на_проверку'}[args.revision]
    manifest = json.loads((STAGE / MANIFEST).read_text(encoding='utf-8'))
    if Path(manifest['source']).resolve() != STAGE.resolve():
        raise ValueError('Unexpected source folder')
    if Path(manifest['destination']).resolve() != DEST.resolve():
        raise ValueError('Unexpected destination folder')
    if DEST.resolve().parent != LIBRARY.resolve():
        raise ValueError('Destination must stay directly inside the requested library')

    # Validate every path and source before making any change in the library.
    pairs = []
    for row in manifest['files']:
        path = relative(row['path'])
        source = inside(STAGE / path, STAGE)
        target = inside(DEST / path, DEST)
        if source.stat().st_size != row['bytes'] or digest(source) != row['sha256']:
            raise ValueError(f'Stage file differs from reviewed manifest: {path}')
        if args.mode == 'publish' and target.exists() and digest(target) != row['sha256']:
            raise FileExistsError(f'Preserving a different existing library file: {target}')
        pairs.append((source, target, row))
    manifest_target = inside(DEST / MANIFEST, DEST)
    if args.mode == 'publish':
        DEST.mkdir(exist_ok=True)
        for source, target, row in pairs:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        if manifest_target.exists() and digest(manifest_target) != digest(STAGE / MANIFEST):
            raise FileExistsError(f'Preserving a different existing manifest: {manifest_target}')
        shutil.copy2(STAGE / MANIFEST, manifest_target)

    verified = []
    for _, target, row in pairs:
        if not target.is_file() or target.stat().st_size != row['bytes'] or digest(target) != row['sha256']:
            raise ValueError(f'Delivered file failed verification: {target}')
        verified.append(row['path'])
    if digest(manifest_target) != digest(STAGE / MANIFEST):
        raise ValueError('Delivered manifest differs')
    links = Links()
    links.feed((DEST / 'gallery.html').read_text(encoding='utf-8'))
    for name in links.paths:
        target = inside(DEST / relative(name), DEST)
        if not target.is_file():
            raise FileNotFoundError(f'Broken gallery link: {target}')
    report = dict(destination=str(DEST), files=len(verified),
                  bytes=sum(r['bytes'] for _, _, r in pairs),
                  manifest_identical=True, hashes_pass=True,
                  gallery_links=len(links.paths), gallery_pass=True)
    (PROJECT / f'_asset_src/pm_refinement/work/published_check_{args.revision}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PM_PUBLISHED_PASS', json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
