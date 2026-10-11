"""Deliver the Codex authoring files and reviews without overwriting worn_v01."""
import hashlib
import html
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"_asset_src/flare_pistol_codex"
WORK=RAW/"integration"
OUT=ROOT/"assets/models/weapons/flare_pistol_codex"
LIB=Path("E:/Models Blender/Ракетница — Codex")
DEST=LIB/"game_codex"
SOURCE_HASH="4B8F4BA3965D5C2B1B7554682133F0B2D27411C914D885613B83AD1ABD4F77D5"

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest().upper()

assert sha(LIB/"models/launcher/flare_pistol_codex_ucupaint_worn_v01.blend")==SOURCE_HASH
assert sha(RAW/"models/launcher/flare_pistol_codex_ucupaint_worn_v01.blend")==SOURCE_HASH
previous_manifest=DEST/"manifest.json"
if previous_manifest.exists():
    previous=json.loads(previous_manifest.read_text(encoding="utf-8"))
    for entry in previous["files"]:
        if entry["file"].endswith(".blend"):
            edited=LIB/entry["file"]
            if edited.exists() and sha(edited)!=entry["sha256"]:
                raise RuntimeError(f"Owner's edited Blender source must be preserved: {edited}")
records=[]

def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    expected=sha(source)
    assert sha(target)==expected
    records.append({"file":str(target.relative_to(LIB)).replace("\\","/"),"sha256":expected,"bytes":target.stat().st_size})

for name in ["flare_pistol_codex_fps_animations.blend","flare_pistol_codex_fps_export.blend",
             "flare_pistol_codex_lowpoly.blend","flare_pistol_codex_world.blend"]:
    copy(WORK/name,DEST/"source"/name)
for revision in ["v02","v03"]:
    name="flare_pistol_codex_ucupaint_worn_"+revision+".blend"
    copy(RAW/"models/launcher"/name,LIB/"models/launcher"/name)
for source in sorted(OUT.glob("*.glb")): copy(source,DEST/"exports"/source.name)
for source in sorted((OUT/"textures").glob("*.png")): copy(source,DEST/"exports/textures"/source.name)
for name in ["glb_audit.json","asset_report.json","clearance_boxes.json"]: copy(OUT/name,DEST/"exports"/name)
for name in ["animation_audit.json","editable_animation_audit.json","bake_audit.json","clearance_audit.json","lowpoly_audit.json",
             "flare_test.log","flare_net_host.log","flare_net_client.log","compile_check.log","ammo_mix_test.log",
             "reload_fast_test.log","veras_hand_test.log","valuable_loot_test.log","editable_verify.log","pm_test.log","pm_baseline.log"]:
    copy(WORK/name,DEST/"checks"/name)
copy(ROOT/"docs/assets/flare_pistol_codex_hand_edit.md",DEST/"README_HAND_EDIT.md")
for name in ["prepare_flare_pistol_codex","animate_flare_pistol_codex","verify_flare_pistol_codex",
             "audit_flare_pistol_codex","register_flare_pistol_codex","package_flare_pistol_codex"]:
    copy(ROOT/"tools"/(name+".py"),DEST/"source/tools"/(name+".py"))
for source in sorted((WORK/"previews").glob("*.png")): copy(source,DEST/"previews"/source.name)
shots=json.loads((ROOT/"docs/screens/flare_codex_manifest.json").read_text(encoding="utf-8"))
assert shots["failures"]==0
for name in shots["captures"]:
    source=ROOT/name.removeprefix("res://")
    copy(source,DEST/"previews"/source.name)
copy(ROOT/"docs/screens/flare_codex_manifest.json",DEST/"checks/game_shots.json")

poses=[("01_grooves_overview.png","Металл, износ и скруглённая рукоять"),
       ("14_breech_firing_pin.png","Боёк в казённом щитке"),
       ("15_hammer_impact_pad.png","Ударная площадка со стороны курка"),
       ("05_lowpoly_baked.png","Игровая сетка с запечёнными картами")]
stages=[("idle_right_only","Стойка — только правая рука"),("barrel_open","Левая раскрывает ствол"),
        ("chamber_down","Правая поворачивает казённый срез вниз"),("shake_1","Первое встряхивание"),
        ("shake_2","Второе встряхивание — гильза выходит"),("upright","Возврат для заряжания"),
        ("green_round_align","Левая совмещает зелёный патрон со стволом"),("round_seated","Патрон вставлен"),
        ("snap_close","Рывок правой кисти для закрытия"),("barrel_closed","Ствол закрыт"),
        ("hammer_cocked","Взведение правым большим пальцем"),("reload_complete_right_only","Готовность — правая рука")]
samples={s["stage"]:s for s in shots["samples"]}

def figure(file,caption):
    link="game_codex/previews/"+file
    return f'<figure><a href="{link}"><img loading="lazy" src="{link}" alt="{html.escape(caption)}"></a><figcaption>{html.escape(caption)}</figcaption></figure>'

section='''<section id="game-codex">
<div class="tag">RING · Codex · игровая версия и редактируемые руки</div>
<h1>Переломная ракетница — руки и перезарядка</h1>
<p>Левая открывает ствол. Правая переворачивает казённый срез вниз, двумя встряхиваниями
вытряхивает гильзу и возвращает пистолет. Левая вставляет патрон, правая рывком закрывает
ствол и взводит курок. В стойке и при выстреле пистолет остаётся в правой руке.</p>
<div class="links">
<a href="game_codex/source/flare_pistol_codex_fps_animations.blend">Blender: редактировать руки и ключи</a>
<a href="game_codex/README_HAND_EDIT.md">Кости, кадры и экспорт</a>
<a href="models/launcher/flare_pistol_codex_ucupaint_worn_v03.blend">High-poly + UCUPaint v03</a>
<a href="game_codex/exports/flare_pistol_codex_viewmodel.glb">FPS GLB</a>
<a href="game_codex/exports/flare_pistol_codex.glb">Мировая GLB</a>
<a href="gallery_worn_v01.html">Текстурная версия worn_v01</a>
</div>
<p class="note">Руки взяты из ВЕРАС-54. Пальцы и обхват — заготовка для ручной доводки.
Арматура FPS_ArmsRig, контролы ik_hand.R / ik_hand.L. Главный клип Flare_Codex_reload_empty,
30 кадров/с, кадры 1–156. Два встряхивания: 48 и 56; вставка: 110; закрытие: 128; взведение: 144.
Патроны: красный — освещение, зелёный — airdrop. Исходная worn_v01 сохранена.</p>
<h2>Геометрия, боёк и bake</h2><div class="grid">'''
section+="".join(figure(name,caption) for name,caption in poses)+"</div><h2>Кадры реальной игровой камеры</h2><div class=\"grid\">"
for stage,caption in stages:
    sample=samples[stage]
    section+=figure("flare_codex_"+stage+".png",caption+f' · {sample["clip"]}, кадр {sample["frame"]:.1f}')
section+='''</div><p>Проверки: игровая логика 61/61, ENet хост и клиент, импорт 12 клипов,
свежее открытие 17 поз Blender, GLB и нормали. Команды проверки и отчёты — в game_codex/checks.</p></section><hr><h2>Прежняя текстурная выдача</h2>'''
gallery=LIB/"gallery.html"
archive=LIB/"gallery_worn_v01.html"
if not archive.exists(): shutil.copy2(gallery,archive)
old=archive.read_text(encoding="utf-8")
new=old.replace("<title>Ракетница — Codex · UCUPaint worn_v01</title>","<title>Ракетница — Codex · руки и игровая версия</title>")
new=new.replace("<main>","<main>\n"+section,1)
gallery.write_text(new,encoding="utf-8")
update="""\n\n## Игровая выдача Codex, 2026-10-11

Актуальный high-poly с нативным UCUPaint — `models/launcher/flare_pistol_codex_ucupaint_worn_v03.blend`.
Редактируемые руки ВЕРАС-54 и ключи — `game_codex/source/flare_pistol_codex_fps_animations.blend`.
Кости, кадры, файлы и экспорт — `game_codex/README_HAND_EDIT.md`. Правый хват и пальцы ждут
ручной доводки владельцем. В стойке правая рука; левая участвует в открытии и заряжании.
Срез вниз, два встряхивания, вставка патрона левой, закрытие рывком правой, взведение правым
большим пальцем. Игровые GLB/PBR, превью и проверки — в `game_codex/`.
Оригинальная worn_v01 сохранена побайтно. У мирового ствола 12 348 треугольников; карта нормалей
и материалы запечены в уникальную GameUV. Красный патрон освещает, зелёный вызывает снабжение.
Ракетница встроена в RING во вторичный слот: B — следующий тип патрона, R — заряжание, ЛКМ — выстрел.
\n"""
for name in ["asset-state.md","00_НАЧНИ_ЗДЕСЬ.md"]:
    path=LIB/name
    text=path.read_text(encoding="utf-8")
    if "## Игровая выдача Codex, 2026-10-11" not in text: path.write_text(text+update,encoding="utf-8")
(DEST/"manifest.json").write_text(json.dumps({"author":"Codex","preserved_worn_v01_sha256":SOURCE_HASH,
    "files":records,"hand_editing":"source/flare_pistol_codex_fps_animations.blend"},ensure_ascii=False,indent=2),encoding="utf-8")
assert sha(LIB/"models/launcher/flare_pistol_codex_ucupaint_worn_v01.blend")==SOURCE_HASH
print("FLARE_PACKAGE_PASS",len(records),"copied files",DEST)
