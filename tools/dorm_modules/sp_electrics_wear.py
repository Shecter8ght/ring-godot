"""Электрика общежития, этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост. Работает внутри
Painter (задание electrics_sp.py wear; путь tools/dorm_modules добавляет furniture_sp.py).

Над группой «Этап 1 — заводская отделка» (не меняется) — слой «Печать (этап 1)» и группа «Этап 2 — износ»
(Passthrough) — помощники sp_dorm_wear.py. Интервью 2026-11-01: как в Таркове (долго жили, потом бросили — пыль, грязь,
затёртости заметно, но не в труху); чёрные концы трубок; мухи и пыль в плафонах и рассеивателях; захватанные
выключатели; пожелтевший пластик; закрашены при ремонтах — вперемешку (варианты износа paint="краска" / "побелка"
у настенного); ржавчины нет. Места — карты electrics_wear_zones.py, рисунок — фото-маски CC0 (_asset_src/dorm_clutter/
wear/masks, license.txt) и процедуры полки Painter (в игру — только запечённым). Узоры — под мелкий масштаб электрики.
"""
import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
from sp_dorm_wear import MK, _first_tri, _layer, _new_group, _tri, _zone

PROFILES = {
    "el_tube": dict(tube_ends=True),
    "el_bulb": dict(bulb=True),
    "el_lsp": dict(yellowed=["Светильник_эмаль", "Отражатель_эмаль", "Ламподержатель_пластик"]),
    "el_lpo": dict(yellowed=["Светильник_эмаль", "Ламподержатель_пластик", "Рассеиватель_опал"], flies=True),
    "el_plafond": dict(yellowed=["Плафон_основание"], flies=True),
    "el_pendant": dict(cord=["Шнур_витой"]),
    "el_switch_round": dict(touch=True),
    "el_socket_round": dict(touch=True, soot=True),
    "el_switch_white": dict(touch=True, yellowed=["Пластик_белый"]),
    "el_socket_white": dict(touch=True, soot=True, yellowed=["Пластик_белый"]),
    "el_box": dict(),
    "el_wire_flat": dict(yellowed=["Провод_ПВХ"]),
    "el_wire_twisted": dict(copper=["Медь"], fabric=["Провод_витой_оплётка"]),
}
# закраска при ремонте: (цвет, блеск) — масляная краска нижней панели стены и побелка
PAINT = {"краска": ((0.22, 0.35, 0.29), 0.35), "побелка": ((0.86, 0.85, 0.80), 0.95)}


def _scope(layer, setname, names):
    """Слой только на сетки этих слотов (имя сетки до «__» и «.»)."""
    if not names:
        return
    ts = next(t for t in TS.all_texture_sets() if t.name() == setname)
    ms = [m for m in ts.all_mesh_names() if m.split(".")[0].split("__")[0] in names]
    if ms:
        sp_lib.only_meshes(layer, ms)


def build(setname, base, game, bbox_mm, paint=None):
    p = PROFILES[game]
    pos = _new_group(setname, base, game)
    made = []

    def nxt():
        return L.InsertPosition.above_node(made[-1]) if made else pos

    def add(layer, scope=None):
        _scope(layer, setname, scope)
        made.append(layer)
        return layer

    # 1. грязь в углублениях — генератор Dirt: темнее и матовее (мелкое — узор мельче)
    l1 = add(_layer("Грязь в углублениях", nxt(), color=(0.22, 0.18, 0.14), cop=0.45, rough=0.85, rop=0.4, metal=0.0))
    g = sp_lib.mask_generator(l1, "mg_dirt/mg_dirt", {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.4,
                                                      "Grunge_Scale": 5, "Use_Triplanar": 1})
    _tri(g, f"{MK}/grime.png", 120, bbox_mm, rot=0.4, opacity=0.6)
    # 2. пыль на всём, что смотрит вверх (у потолочного — верх отражателя, трубок, корпуса)
    l2 = add(_layer("Пыль сверху", nxt(), color=(0.58, 0.55, 0.50), cop=0.5, rough=0.92, rop=0.5, metal=0.0))
    m = _first_tri(l2, "grunge_dust_spread/grunge_dust_spread", 300, bbox_mm, rot=0.7, proc=True)
    m = _tri(m, f"{MK}/dust_specks.png", 100, bbox_mm, rot=1.3, blend=L.BlendingMode.Lighten, opacity=0.6)
    _zone(l2, base, game, "up", above=m)
    # 3. пожелтело от света и табака — белое и светлое
    if p.get("yellowed"):
        ly = add(_layer("Пожелтело", nxt(), color=(0.95, 0.87, 0.68), cmode=L.BlendingMode.Multiply, cop=0.75,
                        rough=0.05, rmode="add", rop=0.5), p["yellowed"])
        _first_tri(ly, f"{MK}/cloudy.png", 400, bbox_mm, rot=1.2)
    # 4. трубка: концы колбы почернели (выгорела), сама колба в лёгкой пыли
    if p.get("tube_ends"):
        # полоса сплошная, облачный рисунок только чуть гуляет по ней (самопроверка: рисунком первым выходил мрамор)
        lt = add(_layer("Концы трубки почернели", nxt(), color=(0.035, 0.033, 0.03), cop=1.0, rough=0.4, rop=0.5, metal=0.0))
        m = _zone(lt, base, game, "tube_ends")
        _tri(m, f"{MK}/cloudy.png", 60, bbox_mm, rot=0.4, opacity=0.3)
    # 5. лампа: налёт у цоколя изнутри, пыль на колбе
    if p.get("bulb"):
        lh = add(_layer("Налёт в колбе у цоколя", nxt(), color=(0.48, 0.47, 0.45), cmode=L.BlendingMode.Multiply, cop=0.8,
                        rough=0.0, rmode="add", rop=0.0))
        _zone(lh, base, game, "haze")
    # 6. мухи и пыль на дне рассеивателя и плафона
    if p.get("flies"):
        ld = add(_layer("Пыль на дне", nxt(), color=(0.50, 0.47, 0.42), cop=0.6, rough=0.9, rop=0.6, metal=0.0))
        m = _first_tri(ld, f"{MK}/dust_grain.png", 60, bbox_mm, rot=0.8)
        _zone(ld, base, game, "fly_dust", above=m)
        lf = add(_layer("Дохлые мухи", nxt(), color=(0.035, 0.03, 0.025), cop=1.0, rough=0.6, rop=1.0, metal=0.0))
        _zone(lf, base, game, "flies")
        # снаружи стекла — то же размытой тенью: молочное стекло в игре не показывает свою внутреннюю сторону
        lg = add(_layer("Пыль на дне сквозь стекло", nxt(), color=(0.40, 0.38, 0.35), cmode=L.BlendingMode.Multiply, cop=0.8))
        _zone(lg, base, game, "dust_through")
        lft = add(_layer("Мухи сквозь стекло", nxt(), color=(0.12, 0.11, 0.10), cmode=L.BlendingMode.Multiply, cop=1.0))
        _zone(lft, base, game, "flies_through")
    # 7. выключатели захватаны, у гнёзд розеток — копоть
    if p.get("touch"):
        # руки оставляют серо-бурый жирный налёт, он глушит глянец (самопроверка: со снятым блеском лицо розетки
        # зеркалило студию и выходило светлее корпуса)
        lt = add(_layer("Захватано пальцами", nxt(), color=(0.56, 0.51, 0.45), cmode=L.BlendingMode.Multiply, cop=0.8,
                        rough=0.15, rmode="add", rop=0.7))
        m = _first_tri(lt, f"{MK}/prints_a.png", 40, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)
    if p.get("soot"):
        ls = add(_layer("Копоть у гнёзд", nxt(), color=(0.07, 0.06, 0.055), cop=0.85, rough=0.85, rop=0.6, metal=0.0))
        _zone(ls, base, game, "soot")
    # 8. шнур и оплётка потемнели, медь окислилась
    if p.get("cord") or p.get("fabric"):
        lc = add(_layer("Оплётка засалена и потемнела", nxt(), color=(0.70, 0.66, 0.62), cmode=L.BlendingMode.Multiply,
                        cop=0.7, rough=-0.05, rmode="add", rop=0.5), (p.get("cord") or []) + (p.get("fabric") or []))
        _first_tri(lc, f"{MK}/grime.png", 80, bbox_mm, rot=0.3)
    if p.get("copper"):
        lo = add(_layer("Медь окислилась", nxt(), color=(0.30, 0.36, 0.26), cop=0.55, rough=0.75, rop=0.7, metal=0.3),
                 p["copper"])
        _first_tri(lo, "grunge_rust_fine/grunge_rust_fine", 30, bbox_mm, rot=0.5, proc=True)
    # 9. закрашено при ремонте (вариант износа): краской стены или побелкой — поверх всего
    if paint:
        col, rough = PAINT[paint]
        lp = add(_layer(f"Закрашено: {paint}", nxt(), color=col, cop=1.0, rough=rough, rop=1.0, metal=0.0))
        # место — картой (с пропусками), толщина слоя чуть гуляет
        m = _zone(lp, base, game, "paint")
        _tri(m, f"{MK}/cloudy.png", 150, bbox_mm, rot=0.9, opacity=0.12)
    return f"{game}: {len(made)} слоёв износа{' + ' + paint if paint else ''}"
