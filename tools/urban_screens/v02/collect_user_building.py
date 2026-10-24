"""Сохранить три фотографии владельца без изменения пикселей."""
from pathlib import Path
import hashlib,json,shutil
PROJECT=Path(__file__).resolve().parents[3]
ROOT=PROJECT/'_asset_src/urban_realrefs_v02'
SOURCE=Path('C:/Users/Schecter_8ght/.codex/codex-remote-attachments/01a16e02-5fd3-7b40-91c9-c3c5fba87c79/EFCB65F2-5F22-4F6D-8D81-7D31ED52976B')
folder=ROOT/'references/building_user'; folder.mkdir(parents=True,exist_ok=True)
captions=['Вход, пониженное окно лестничной клетки, козырёк и неровная штукатурка',
          'Крупный план окон, трещин, наплывов и отслоения штукатурки под карнизом',
          'Общий фронтальный вид: два этажа, два входа, ритм окон, карниз и расположение крупных повреждений']
for i,source in enumerate(sorted(SOURCE.glob('*.jpg')),1):
    path=folder/f'ref_{i:02}.jpg'; shutil.copy2(source,path)
    record=dict(file=path.name,origin='user_attachment',original_path=str(source),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),downloaded='2026-10-24',
        purpose='Owner-provided geometry and later texture reference; original pixels preserved',notes=captions[i-1])
    (folder/(path.name+'.source.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SAVED_USER_REFERENCE',path.name,source.name)
