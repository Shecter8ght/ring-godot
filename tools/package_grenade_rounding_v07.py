"""Выдача скруглённой геометрии гранаты v07 и сравнений до/после."""
import json,hashlib,shutil,re,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"_asset_src/grenade_codex/geometry_review_v07"
TARGET=Path("E:/Models Blender/From Scenario/Grenade/Codex_Geometry_v07")
FILE="Grenade_MkII_geometry_review_v07.blend"
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def manifest(folder):
    rows=[{"file":p.relative_to(folder).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(folder.rglob("*")) if p.is_file() and p.name!="delivery_manifest.json"]
    (folder/"delivery_manifest.json").write_text(json.dumps({"version":"geometry_v07","files":rows},indent=2),encoding="utf8")
def validate(folder):
    m=json.loads((folder/"delivery_manifest.json").read_text(encoding="utf8"))
    for row in m["files"]:
        p=folder/row["file"];assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
    html=(folder/"gallery.html").read_text(encoding="utf8")
    for link in re.findall(r'(?:src|href)="([^"]+)"',html):
        if not link.startswith(("https:","http:","#","data:")):assert (folder/link).is_file(),link
    print("V07_PACKAGE_VALIDATED",folder,len(m["files"]),flush=True)
def package():
    report=json.loads((OUT/"audit.json").read_text(encoding="utf8"));assert report["pass"]
    font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf",30)
    for name in ["01_overall","02_cast_macro","05_cast_shoulder"]:
        ims=[Image.open(OUT/"previews"/(tag+"_"+name+".png")).convert("RGB") for tag in ["before","after"]]
        sheet=Image.new("RGB",(1800,960),(23,29,35));draw=ImageDraw.Draw(sheet)
        for i,im in enumerate(ims):
            im=im.resize((900,900),Image.Resampling.LANCZOS);sheet.paste(im,(i*900,60));draw.text((i*900+25,14),"До" if i==0 else "После",font=font,fill=(235,237,240))
        sheet.save(OUT/"previews"/("compare_"+name+".jpg"),quality=96,subsampling=0)
    ref=Path("C:/Users/Schecter_8ght/.codex/codex-remote-attachments/01a13159-559d-7862-ae98-fbaf3bb01041/21224310-31D6-43F9-A0C1-AE9D887578E1")
    (OUT/"references").mkdir(exist_ok=True)
    for i in [5,6,7]:shutil.copy2(ref/f"{i}-Фото-{i}.jpg",OUT/"references"/f"owner_reference_{i}.jpg")
    (OUT/"scripts").mkdir(exist_ok=True)
    for name in ["round_grenade_codex_body.py","package_grenade_rounding_v07.py","grenade_codex_blender.py"]:shutil.copy2(ROOT/"tools"/name,OUT/"scripts"/name)
    readme=f"""# Скруглённый корпус гранаты — геометрия v07 на проверку

Открыть {FILE}. Нейтральный материал показывает форму без рельефа текстур.
gallery.html — сравнения до/после и затронутые ракурсы.

Кромки выступов и их сопряжения с оболочкой корпуса стали плавными.
Сохранены расположение секторов и наружный профиль; максимальное радиальное
отличие от v05 0,472 мм. Сглаживание поля 0,45 мм — параметр обработки,
а не утверждение об измеренном круговом радиусе каждой кромки.
Корпус Ø{report['body_dimensions_mm'][0]:.2f} × 86,00 мм, сборка
{report['closed_dimensions_mm'][0]:.2f} × {report['closed_dimensions_mm'][1]:.2f} × {report['closed_dimensions_mm'][2]:.2f} мм.
1 единица = 1 метр, отображение в миллиметрах.

328 193 вершины, 328 192 грани корпуса; ровная связная поверхность.
512 граничных рёбер находятся только в скрытой верхней горловине.
Шесть других деталей, чека, настоящее отверстие, раздвоенные концы и риг сохранены.
13 проверенных поз без пересечения корпуса и рычага; UV исходного корпуса
сохранена в mesh-архиве ARCHIVE • Body v05 with original UV.
У нового корпуса производственная UV ещё не создавалась.
CTRL_Grenade: pin_pull / lever_open. Action 1–96, 24 fps; ручные ползунки —
после отвязки Action от корня. Это внешняя визуальная анимация.

v05 геометрии и v06 с UCUPaint/картами не перезаписаны.
Текстуры v06 остаются отдельным исходником и требуют нового прохода после
принятия формы. Эта выдача не объявляет фотографический реализм материала.
Фото владельца — только референсы; старые изображения Scenario сохранены
как архив и не используются нейтральным материалом.
"""
    (OUT/"00_НАЧНИ_ЗДЕСЬ.md").write_text(readme,encoding="utf8")
    (OUT/"asset-state.md").write_text(readme,encoding="utf8")
    state={"geometry":"v07 pending owner review","approved_previous_geometry":"v05","textures":"existing v06 retained separately; revised UV/texturing after geometry review","body_radial_change_max_mm":.471753052443076,"sigma_mm":.45,"body_vertices":328193,"body_faces":328192,"six_other_meshes_preserved":True,"body_uv_source_preserved_in_archive":True}
    (OUT/"asset-state.json").write_text(json.dumps(state,indent=2),encoding="utf8")
    comparisons="".join(f'<figure><a href="previews/compare_{n}.jpg"><img src="previews/compare_{n}.jpg"></a><figcaption>{t}</figcaption></figure>' for n,t in [("01_overall","Общий вид"),("02_cast_macro","Кромки и примыкания"),("05_cast_shoulder","Переходы у плеча корпуса")])
    cards="".join(f'<figure><a href="previews/after_{n}.png"><img loading="lazy" src="previews/after_{n}.png"></a><figcaption>{t}</figcaption></figure>' for n,t in [("02_cast_macro","Скруглённые сектора"),("03_cast_reverse","Обратная сторона"),("04_cast_low","Низкий ракурс"),("05_cast_shoulder","Плечо"),("06_motion","Подвижные детали")])
    html=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Граната · скругления v07</title><style>body{{margin:0;background:#151b20;color:#e7e9eb;font:17px/1.5 Arial}}main{{max-width:1500px;margin:auto;padding:30px}}a{{color:#eed6a0}}figure{{margin:0 0 24px;background:#222a32}}img{{width:100%;display:block}}figcaption{{padding:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:22px}}</style><main><h1>Граната · скруглённый корпус v07</h1><p>Геометрия на проверку: мягкие кромки и плавные сопряжения. Одинаковый нейтральный материал и свет до/после.</p><p><a href="{FILE}">Открыть Blender</a> · <a href="00_НАЧНИ_ЗДЕСЬ.md">Памятка</a> · <a href="audit.json">Проверки</a></p>{comparisons}<div class="grid">{cards}</div><p>Исходная v05 и текстуры v06 сохранены отдельно. Новая производственная UV и текстурирование — после просмотра формы.</p></main></html>'''
    (OUT/"gallery.html").write_text(html,encoding="utf8")
    manifest(OUT);validate(OUT)
    assert not TARGET.exists(),"New review directory already exists; inspect before overwriting"
    shutil.copytree(OUT,TARGET);validate(TARGET)
def seal():
    receipt=json.loads((OUT/"delivered_audit.json").read_text(encoding="utf8"))
    assert receipt["pass"] and Path(receipt["candidate"]).parent==TARGET
    shutil.copy2(OUT/"delivered_audit.json",TARGET/"delivered_audit.json")
    for folder in [OUT,TARGET]:manifest(folder);validate(folder)
if __name__=="__main__":
    {"package":package,"seal":seal}[sys.argv[1] if len(sys.argv)>1 else "package"]()

