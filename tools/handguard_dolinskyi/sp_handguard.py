# Цевьё Dolinskyi в Substance Painter 12.1 (выполняется внутри Painter через мост tools/vss_m_v8/sp_bridge):
# проект на шаблоне «PBR - Specular Glossiness» (автор ролика работает в Diffuse / Specular / Glossiness), набор 2048,
# запекание с high-poly, вид как в ролике 0:25 (Studio Tomoco, Camera, Linear). Стек слоёв — sp_stack.py.
#   FINISH_SP_JOBS=_asset_src/handguard_dolinskyi/sp_jobs python -X utf8 tools/asset_kit/finish/sp_run.py -c
#     "import sp_handguard as H; print(H.create())"   (папку tools/handguard_dolinskyi добавляет HEADER ниже)
import os

import substance_painter.baking as B
import substance_painter.display as D
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.resource as R
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

ROOT = "E:/Games/RING-godot"
SP_DIR = ROOT + "/_asset_src/handguard_dolinskyi/sp"
LOW = SP_DIR + "/handguard_low.fbx"
HIGH = SP_DIR + "/handguard_high.fbx"
OUT_DIR = "E:/Models Blender/WEAPONS/Цевьё — Dolinskyi, анодирование 2026-11-01"
PROJECT = OUT_DIR + "/Цевьё_Dolinskyi_v01.spp"
PAINTER = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter"
TEMPLATE = PAINTER + "/resources/starter_assets/templates/PBR - Specular Glossiness.spt"
OCIO = PAINTER + "/resources/ocio/substance/config.ocio"
RES_LOG2 = 11


def mark(name, text="OK"):
    with open(os.path.join(os.environ.get("SP_BRIDGE_DIR", ""), name), "w", encoding="utf-8") as f:
        f.write(text)


def unmark(name):
    p = os.path.join(os.environ.get("SP_BRIDGE_DIR", ""), name)
    if os.path.exists(p):
        os.remove(p)


_handlers = {}


def _connect(event, fn, key):
    old = _handlers.get(key)
    if old is not None:
        try:
            E.DISPATCHER.disconnect(event, old)
        except Exception:
            pass
    _handlers[key] = fn
    E.DISPATCHER.connect_strong(event, fn)


def create():
    """Новый проект Spec/Gloss из low-poly; метка _project_ready.txt."""
    os.environ["OCIO"] = OCIO
    unmark("_project_ready.txt")
    if P.is_open():
        P.close()

    def ready(e):
        # окружение здесь не меняем: смена окружения сразу после создания проекта роняла Painter в nvoglv64.dll
        # (2026-11-01, дважды) — view() отдельным заданием, когда проект досчитан
        mark("_project_ready.txt", "OK " + " ".join(t.name() for t in TS.all_texture_sets()))
    _connect(E.ProjectEditionEntered, ready, "ready")
    s = P.Settings(default_texture_resolution=2 ** RES_LOG2, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerFragment)
    P.create(LOW, template_file_path=TEMPLATE, settings=s)
    return "creating"


def open_project():
    os.environ["OCIO"] = OCIO
    unmark("_project_ready.txt")
    if P.is_open():
        P.close()

    def ready(e):
        mark("_project_ready.txt", "OK")
    _connect(E.ProjectEditionEntered, ready, "ready")
    P.open(PROJECT)
    return "opening"


def view():
    """Вид в окне Painter как у автора (0:25–1:00): Studio Tomoco, тонкривая Linear. Blur 35, поворот 234,
    выравнивание Camera и TAA 32 API не задаёт — их владелец ставит в Display Settings руками (числа — в справке)."""
    for r in R.search("u:environment"):
        if r.identifier().name.lower().replace(" ", "") in ("studiotomoco", "studio_tomoco"):
            D.set_environment_resource(r.identifier())
            break
    try:
        D.set_tone_mapping(D.ToneMappingFunction.Linear)
    except Exception as e:      # noqa: BLE001 — в 12.1 имя функции тонкривой может отличаться
        print("tone mapping:", e)


def bake():
    """Карты сетки с high-poly: нормаль, нормаль в мире, ID, AO, кривизна, положение, толщина (у автора в фильтрах
    видны handguard_position и handguard_normalobj). Луч — 1 % габарита вперёд и назад: фаски high-poly 0.4 мм."""
    unmark("_bake_done.txt")
    t = TS.all_texture_sets()[0]
    bp = B.BakingParameters.from_texture_set(t)
    bp.set_enabled_bakers([U.Normal, U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
    c = bp.common()
    vals = {c["OutputSize"]: (RES_LOG2, RES_LOG2), c["LowAsHigh"]: False, c["HipolyMesh"]: "file:///" + HIGH,
            c["SubSampling"]: 2, c["RelativeScale"]: True, c["MaxHeight"]: 0.01, c["MaxDepth"]: 0.01,
            c["IgnoreBackface"]: True}
    vals[bp.baker(U.ID)["ColorSource"]] = 3
    B.BakingParameters.set(vals)

    def done(e):
        # сохранить сразу, когда Painter досчитает: 2026-11-01 он падал через секунды после конца запекания,
        # и карты пропадали вместе с несохранённым проектом
        def save_now():
            try:
                P.save()
                mark("_bake_done.txt", str(e.status) + " saved")
            except Exception as ex:      # noqa: BLE001
                mark("_bake_done.txt", str(e.status) + " save error " + str(ex))
        P.execute_when_not_busy(save_now)
    _connect(E.BakingProcessEnded, done, "bake")
    B.bake_async(t)
    return "baking " + t.name()


def save():
    os.makedirs(OUT_DIR, exist_ok=True)
    P.save_as(PROJECT)
    return PROJECT


def export(out_dir, preset="Document channels + Normal + AO (No Alpha)"):
    """Карты набора в PNG (8 бит) — для просмотра в Blender: Diffuse, Specular, Glossiness, Height, Normal (OpenGL), AO.
    Сохранение и выгрузка — когда Painter досчитает стек; итог — метка _export_done.txt."""
    import substance_painter.export as X
    unmark("_export_done.txt")
    os.makedirs(out_dir, exist_ok=True)

    def run():
        try:
            P.save()
            pr = [p for p in X.list_predefined_export_presets() if p.name == preset][0]
            t = TS.all_texture_sets()[0].name()
            cfg = {"exportShaderParams": False, "exportPath": out_dir, "defaultExportPreset": pr.url,
                   "exportList": [{"rootPath": t}],
                   "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8",
                                                        "paddingAlgorithm": "infinite", "dithering": False}}]}
            r = X.export_project_textures(cfg)
            files = [os.path.basename(f) for v in r.textures.values() for f in v]
            mark("_export_done.txt", f"{r.status} {' '.join(files)}")
        except Exception as e:      # noqa: BLE001
            mark("_export_done.txt", "ERROR " + repr(e))
    P.execute_when_not_busy(run)
    return "export queued"


def find(name):
    """Узел стека по имени (поиск в глубину)."""
    import substance_painter.layerstack as L
    st = TS.all_texture_sets()[0].get_stack()

    def walk(nodes):
        for n in nodes:
            if n.get_name() == name:
                return n
            if hasattr(n, "sub_layers"):
                r = walk(n.sub_layers())
                if r is not None:
                    return r
        return None
    return walk(L.get_root_layer_nodes(st))
