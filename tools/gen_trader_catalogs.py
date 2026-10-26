"""Каталоги Михалыча: data/trader.json из списков ниже (оружие, обвес, броня, расходники явно;
патроны и магазины — по стволам каталога автоматически).

    python tools/gen_trader_catalogs.py

Каталог открывается на ступени доверия (1, 10, 20, 30, 40 — Balance.TRUST_STEPS). Патрон
калибра и обычный магазин — в каталоге первого ствола под них; бронебойные патроны и увеличенные
магазины — каталогом позже. Снаряжение ЧВК «Периметр» не продаётся вовсе — только с их тел.
Правка ассортимента — здесь (или руками в trader.json: поле catalog), потом проверить в игре.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "trader.json"

CATALOGS = [
    {"n": 1, "step": 1, "name": "Гражданское",
     "what": "Пистолет, охотничье ружьё, простые прицелы и приклады, самодельная броня, медицина.",
     "items": ["wpn_hg_01", "wpn_sg_03",
               "optic_rd_01", "optic_rd_dt_01", "muzzle_fh_545_01", "muzzle_fh_556_01", "grip_vertical_01",
               "grip_compact_01", "grip_handstop_01", "stock_fixed_heavy_ak", "stock_fixed_light_ak",
               "stock_fold_ak_01", "tac_flashlight_01", "mount_riser_01", "mount_rail_ext_01",
               "belt_pouches", "armor_poor", "plate_steel_homemade", "helmet_simple", "headset_passive",
               "bandage", "painkillers", "medkit", "water", "canned", "flare", "chemlight", "sunglasses", "bp_daypack",
               "pouch_rifle", "pouch_pistol", "signal_launcher"]},
    {"n": 2, "step": 10, "name": "Полиция и ЧОП",
     "what": "Служебные пистолеты, пистолеты-пулемёты, АК-12, Сайга. Коллиматоры, компенсаторы, полицейская броня.",
     "items": ["wpn_hg_02", "wpn_hg_03", "wpn_smg_01", "wpn_smg_04", "wpn_ar_01", "wpn_sg_02",
               "optic_zorin_k1", "mount_pm_k1", "optic_holo_01", "optic_2x_01", "optic_pso_01", "muzzle_comp_545_01",
               "muzzle_brake_762_01", "muzzle_comp_556_01", "muzzle_comp_9_01", "grip_angled_01", "grip_offset_01", "grip_heavy_01",
               "bipod_01", "stock_tele_ak_01", "stock_tele_ar_01", "tac_laser_01", "mount_offset45_01",
               "armor_mid", "plate_steel", "helmet_mid", "headset_active", "bp_tourist",
               "grenade", "mag_loader", "pouch_big"]},
    {"n": 3, "step": 20, "name": "Армейское",
     "what": "M4A1, Benelli, «Вереск», P90. Оптика 4×, глушители, армейская броня и керамика, ПНВ.",
     "items": ["wpn_ar_02", "wpn_sg_01", "wpn_smg_05", "wpn_smg_02",
               "optic_4x_01", "tac_flashlight_hp_01", "tac_combo_01", "muzzle_supp_9_01",
               "muzzle_supp_pm_01", "muzzle_supp_45_01", "muzzle_supp_545_01", "muzzle_supp_556_01",
               "muzzle_supp_12_01",
               "armor_top", "plate_composite", "plate_ceramic", "helmet_top", "headset_tactical", "bp_raid",
               "nvg"]},
    {"n": 4, "step": 30, "name": "Спецподразделения",
     "what": "Vector, MCX Virtus, SCAR-L, MK12, бесшумные АС «Вал» и «Шорох-9». LPVO, тяжёлые глушители, армейский композит.",
     "items": ["wpn_smg_03", "wpn_ar_03", "wpn_ar_04", "wpn_dmr_02", "wpn_sp_01", "wpn_sp_02",
               "optic_lpvo_01", "mount_adjustable_01", "muzzle_supp_57_01", "muzzle_supp_300_01", "muzzle_supp_762_01",
               "plate_military"]},
    {"n": 5, "step": 40, "name": "Тяжёлое и снайперское",
     "what": "MR762, MCX Spear, AWM, Barrett, ПКМ, M249. Оптика 8× и 12×, тормоза и глушители крупных калибров.",
     "items": ["wpn_dmr_01", "wpn_ar_05", "wpn_sr_01", "wpn_sr_02", "wpn_lmg_01", "wpn_lmg_02",
               "optic_8x_01", "optic_12x_01", "muzzle_brake_68_01", "muzzle_supp_68_01", "muzzle_brake_338_01",
               "muzzle_supp_338_01"]},
]
# Только с тел ЧВК «Периметр» — у Михалыча этого нет; сигнал снабжения (supply_signal) — не продаётся.
NEVER = ["plate_perimeter", "headset_perimeter", "stock_perimeter_01", "supply_signal"]
AP_WORDS = ("бронебой", "API", "СП-6")


def main() -> None:
    w = json.loads((ROOT / "data" / "weapons.json").read_text(encoding="utf-8"))
    catalog: dict[str, int] = {}
    for c in CATALOGS:
        for i in c["items"]:
            if i in catalog:
                raise SystemExit(f"{i} уже в каталоге {catalog[i]}")
            catalog[i] = c["n"]
    weapons = {k: v for k, v in w["weapons"].items() if k not in NEVER}
    for wid in weapons:
        if wid not in catalog and wid not in NEVER:
            raise SystemExit(f"ствол {wid} не попал ни в один каталог")
    # патроны: калибр — с каталога первого ствола под него; бронебойные — на каталог позже
    cal_first: dict[str, int] = {}
    for wid, v in weapons.items():
        cal = v["weapon"]["caliber"]
        cal_first[cal] = min(cal_first.get(cal, 9), catalog[wid])
    for aid, a in w["ammo"].items():
        cal = a["ammo"]["caliber"]
        if cal not in cal_first:
            continue
        n = cal_first[cal] + (1 if any(s in a["name"] for s in AP_WORDS) else 0)
        catalog[aid] = min(n, 5)
    # магазины: интерфейс — с каталога первого ствола; самые малые — сразу, увеличенные — каталогом позже
    if_first: dict[str, int] = {}
    for wid, v in weapons.items():
        mi = v["weapon"].get("mag_if")
        if mi:
            if_first[mi] = min(if_first.get(mi, 9), catalog[wid])
    by_if: dict[str, list] = {}
    for mid, m in w["magazines"].items():
        by_if.setdefault(m["mag"]["if"], []).append((m["mag"]["capacity"], mid))
    for mi, mags in by_if.items():
        if mi not in if_first:
            continue
        mags.sort()
        base = mags[0][0]
        for cap, mid in mags:
            catalog[mid] = min(if_first[mi] + (1 if cap > base * 1.5 else 0), 5)
    for i in NEVER:
        catalog.pop(i, None)
    # порядок витрины: по каталогу, внутри — оружие, патроны, магазины, обвес, броня, остальное
    kind_order = {"weapons": 0, "ammo": 1, "magazines": 2, "attachments": 3}
    def kind(i: str) -> int:
        for sec, k in kind_order.items():
            if i in w[sec]:
                return k
        return 4 if i.startswith(("armor_", "belt_", "pouch_", "plate", "helmet", "headset")) else 5
    stock = sorted(catalog, key=lambda i: (catalog[i], kind(i), i))
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out = {
        "_comment": "Михалыч: пять каталогов, открываются на ступенях доверия (catalogs.step). catalog — в каком "
                    "каталоге предмет. Цена — Balance.TRADER_BUY_PRICES. Снаряжение «Периметра» не "
                    "продаётся. Собирается tools/gen_trader_catalogs.py.",
        "name": old.get("name", "Сергей «Михалыч»"),
        "catalogs": [{k: c[k] for k in ("n", "step", "name", "what")} for c in CATALOGS],
        "stock": stock,
        "catalog": {i: catalog[i] for i in stock},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    counts = {c["n"]: sum(1 for i in stock if catalog[i] == c["n"]) for c in CATALOGS}
    print("каталоги:", counts, "всего", len(stock))


if __name__ == "__main__":
    main()
