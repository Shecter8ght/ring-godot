"""Воспроизводимая согласованная таблица v0 относительно снимка ДО внедрения.

    python tools/economy_catalog.py

Цены уже в Balance; эта таблица остаётся эталоном первой версии. Вход economy_current.json
зафиксирован до внедрения, новые аудиты пишутся в economy_live.json. Не применять коэффициенты
проекта повторно к новым игровым ценам. Сверка игры — economy_prices_test.tscn.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design"

# Проект покупки: цена преимущества отделена от оценки найденной вещи.
WEAPONS = {
    "wpn_hg_01": 10000, "wpn_hg_02": 60000, "wpn_hg_03": 85000,
    "wpn_sg_03": 35000, "wpn_sg_02": 145000, "wpn_sg_01": 250000,
    "wpn_ar_01": 180000, "wpn_ar_02": 300000, "wpn_ar_03": 500000,
    "wpn_ar_04": 550000, "wpn_ar_05": 1100000,
    "wpn_smg_01": 120000, "wpn_smg_02": 290000, "wpn_smg_03": 450000,
    "wpn_smg_04": 95000, "wpn_smg_05": 220000,
    "wpn_dmr_01": 850000, "wpn_dmr_02": 600000,
    "wpn_sp_01": 620000, "wpn_sp_02": 700000,
    "wpn_sr_01": 1350000, "wpn_sr_02": 2100000,
    "wpn_lmg_01": 1150000, "wpn_lmg_02": 1250000,
}
MAGAZINES = {
    "mag_918_8": 800, "mag_919_17": 1500, "mag_919_33": 4000,
    "mag_45_usp12": 1800, "mag_45_vector13": 1800, "mag_45_vector30": 5000,
    "mag_45_ump25": 2500, "mag_919_vityaz30": 2000,
    "mag_545_30": 2000, "mag_545_45": 3500, "mag_545_60": 5500,
    "mag_556_20": 2000, "mag_556_30": 2500, "mag_556_40": 4500, "mag_556_60": 10000,
    "mag_300_30": 3000, "mag_57_p90_50": 5000,
    "mag_921_sr2_20": 2500, "mag_921_sr2_30": 3500,
    "mag_76251_10": 3500, "mag_76251_20": 5500, "mag_68_spear20": 8000,
    "mag_939_10": 3500, "mag_939_20": 5000,
    "mag_338_awm5": 8000, "mag_50_m82_10": 15000,
    "mag_s12_8": 3500, "mag_s12_20": 20000,
    "mag_m249_100": 5000, "mag_m249_200": 12000,
    "mag_pkm_100": 6000, "mag_pkm_200": 16000,
}
BASIC_MEDICINE = {"bandage": 600, "medkit": 3000, "painkillers": 1200}
PRACTICAL_PRECISION_KIT = {
    "name": "Практичная стрелковая · MK12",
    "lines": [["wpn_dmr_02", 1], ["optic_4x_01", 1], ["bipod_01", 1],
              ["armor_mid", 1], ["plate_steel", 2], ["rig_chest", 1],
              ["helmet_mid", 1], ["headset_active", 1], ["bp_tourist", 1],
              ["mag_556_30", 3], ["ammo_556_std", 90], ["bandage", 3],
              ["medkit", 2], ["painkillers", 1], ["water", 1]],
}
OVERRIDES = {
    "optic_rd_01": 30000, "optic_rd_dt_01": 28000, "optic_holo_01": 80000,
    "optic_rmr_01": 55000, "optic_2x_01": 80000, "optic_pso_01": 100000,
    "optic_4x_01": 150000, "optic_offset_rd_01": 85000,
    "optic_lpvo_01": 350000, "optic_8x_01": 450000, "optic_12x_01": 650000,
    "muzzle_comp_545_01": 30000, "grip_vertical_01": 20000, "tac_flashlight_01": 15000,
    "nvg": 300000, "mag_loader": 35000,
    "bp_daypack": 12000, "bp_tourist": 35000, "bp_raid": 180000,
    "rig_belt": 4500, "rig_chest": 20000, "rig_assault": 75000, "rig_heavy": 180000,
    "armor_mid": 20000, "plate_steel": 35000,
    "helmet_mid": 25000, "headset_active": 30000,
    "grenade": 10000,
    # Рейдовые эксклюзивы сохраняют доступность. Это цена только в тестовом магазине.
    "armor_top": 400000, "armor_top": 500000,
    "plate_perimeter": 350000, "helmet_top": 240000,
    "helmet_perimeter_heavy": 350000, "headset_perimeter": 200000,
    "stock_perimeter_01": 200000,
    "supply_signal": 450000, "signal_launcher": 150000, "laser_head": 60000,
}


def round_price(value: float) -> int:
    step = 10 if value < 1000 else 100 if value < 10000 else 1000
    return int((value + step / 2) // step) * step


def draft_price(row: dict) -> tuple[int, str]:
    ident, cat, old, tier = row["id"], row["definition"]["cat"], row["buy"], row["catalog"]
    if ident in WEAPONS:
        return WEAPONS[ident], "отдельная цена оружия; ПМ/помпа — доступная основа"
    if ident in MAGAZINES:
        return MAGAZINES[ident], "цена по конструкции; доступные запасные магазины для длительного боя"
    if ident in BASIC_MEDICINE:
        return BASIC_MEDICINE[ident], "доступная базовая медицина"
    if ident in OVERRIDES:
        return OVERRIDES[ident], "отдельная цена по роли предмета"
    if tier == 0:
        return round_price(old), "только тестовый магазин; оценку находки пока сохраняем"
    if cat == "mod":
        factor = 2.5 if ident.startswith("muzzle_supp_") else 2
        return round_price(old * factor), "цена удобства и преимущества; глушители дороже"
    if cat == "ammo":
        # Картечь и обычные патроны дают дешёвому оружию боеспособность.
        ap = ident.endswith(("_ap", "_api", "_apslug", "_sp6"))
        return round_price(old * (2.5 if ap else 1)), "бронебойные ×2,5" if ap else "обычные патроны доступны"
    if cat in ["armor", "plate"]:
        return round_price(old * (1 if tier == 1 else 1.25 if tier == 2 else 1.6)), "защита дорожает с возможностями"
    if cat in ["med", "food", "throw", "tools"]:
        return round_price(old), "основные припасы не становятся барьером выхода"
    raise ValueError(f"Нет решения для продаваемого предмета: {ident} ({cat})")


def draft_sell(row: dict, prices: dict[str, int], by_id: dict[str, dict], sell_mult: float) -> int:
    ident = row["id"]
    # Снижаем обе стороны сделки: дешёвый магазин не продаётся обратно по прежней оценке.
    if ident in MAGAZINES:
        return int(prices[ident] * 0.4)
    if ident in BASIC_MEDICINE:
        return int(prices[ident] * 0.45)
    mag_id = row["definition"].get("weapon", {}).get("default_mag", "")
    if mag_id:
        # Таблица показывает новое оружие со штатным магазином; учитываем его переоценку.
        old_mag_sale = by_id[mag_id]["definition"]["value"] * sell_mult
        return int(row["sell_new"] - old_mag_sale + prices[mag_id] * 0.4)
    return row["sell_new"]


def main() -> None:
    snapshot = json.loads((DESIGN / "economy_current.json").read_text(encoding="utf-8"))
    shop = [r for r in snapshot["items"] if r["shop"]]
    assert len({r["id"] for r in shop}) == len(shop)
    assert set(WEAPONS) == {r["id"] for r in shop if r["definition"]["cat"] == "weapon"}
    assert set(MAGAZINES) == {r["id"] for r in shop if r["definition"]["cat"] == "mag"}
    assert set(BASIC_MEDICINE) <= {r["id"] for r in shop}
    assert set(OVERRIDES) <= {r["id"] for r in shop}
    prices: dict[str, int] = {r["id"]: draft_price(r)[0] for r in shop}
    by_id = {r["id"]: r for r in snapshot["items"]}
    # Закрытая упаковка в тестовом магазине стоит столько же, сколько её содержимое.
    for ident, contents in snapshot["loot_packs"].items():
        prices[ident] = sum(prices[content[0]] * content[1] for content in contents)
    with (DESIGN / "economy_prices_v0.tsv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(["id", "название", "категория", "каталог", "доступность", "купить_сейчас",
                         "купить_проект_v0", "продать_новое_сейчас", "продать_новое_проект_v0",
                         "ячеек", "стопка_сейчас", "решение"])
        for row in shop:
            _, reason = draft_price(row)
            price = prices[row["id"]]
            if row["id"] in snapshot["loot_packs"]:
                reason = "тестовый магазин: сумма покупки содержимого, без обхода цены патронов"
            assert price > 0
            sale = draft_sell(row, prices, by_id, snapshot["sell_mult"])
            assert price >= sale >= 0, f"Покупка→продажа приносит прибыль: {row['id']}"
            availability = "каталог" if row["catalog"] else "чит: лут в продаже" if row["loot_only"] else "чит: все товары"
            writer.writerow([row["id"], row["definition"]["name"], row["definition"]["cat"],
                             row["catalog"], availability, row["buy"], price, row["sell_new"],
                             sale, row["cells"], row["stack"], reason])
    # Сумма полной закупки, без использования имеющегося тайника и без скидки комплекта.
    kits = [{"name": k["name"], "current": k["buy_from_empty"],
             "draft": sum(prices[line["id"]] * line["count"] for line in k["lines"])} for k in snapshot["kits"]]
    suggested_kits = [{"name": PRACTICAL_PRECISION_KIT["name"],
                       "draft": sum(prices[ident] * count for ident, count in PRACTICAL_PRECISION_KIT["lines"]),
                       "lines": PRACTICAL_PRECISION_KIT["lines"]}]
    # 5–8 успешных рейдов проверяем с оплатой потерь дешёвого набора между успехами.
    # Это сценарная арифметика, а не измерение игроков; все предположения выводим рядом.
    scenarios = []
    good_kit = next(k["draft"] for k in kits if k["name"] == "Патрульный")
    for pocket_income in [0, 10000, 25000, 50000]:
        for survival in [0.3, 0.4, 0.5, 0.6, 0.75]:
            win_net, cheap_loss = 120000, 25000
            # Только новая добыча неудачной попытки; взятые из убежища вещи не являются доходом.
            loss_per_win = (1 - survival) / survival * (cheap_loss - pocket_income)
            savings_per_win = win_net - loss_per_win
            scenarios.append({"survival": survival, "net_success": win_net, "cheap_loss": cheap_loss,
                              "new_pocket_income_on_failure": pocket_income,
                              "savings_per_success_after_failures": round(savings_per_win),
                              "wins_to_patrol": round(good_kit / savings_per_win, 1),
                              "attempts_to_patrol": round(good_kit / savings_per_win / survival, 1)})
    timing = []
    for kit in kits + suggested_kits:
        for survival in [0.5, 0.6]:
            for pocket_income in [0, 10000]:
                net_per_success = 120000 - (1 - survival) / survival * (25000 - pocket_income)
                wins = kit["draft"] / net_per_success
                attempts = wins / survival
                timing.append({"kit": kit["name"], "survival": survival,
                               "new_pocket_income_on_failure": pocket_income,
                               "wins": round(wins, 1), "attempts": round(attempts, 1),
                               "hours_20_min_cycle": round(attempts * 20 / 60, 1),
                               "hours_25_min_cycle": round(attempts * 25 / 60, 1),
                               "hours_30_min_cycle": round(attempts * 30 / 60, 1)})
    output = {"status": "v0_prices_implemented; income_and_timing_are_scenarios", "shop_items": len(shop), "catalog_items": sum(r["catalog"] > 0 for r in shop),
              "hidden_items": sum(r["catalog"] == 0 for r in shop),
              "categories": dict(Counter(r["definition"]["cat"] for r in shop)),
              "pocket_rule": "unchanged; balance prices and rarity, not capacity or item restrictions",
              "scenario_note": "Assumptions only: pocket income is the sale equivalent of newly found items on failed raids, not measured player income.",
              "kits": kits, "suggested_kits": suggested_kits, "scenarios": scenarios,
              "time_assumptions": {"net_success": 120000, "cheap_loss": 25000,
                                   "cycle_minutes": [20, 25, 30],
                                   "note": "Time to save cash for one complete purchase from zero; raid plus preparation. Excludes trust/module gates and use/loss of the target kit. Scenario assumptions, not a playtest measurement."},
              "timing": timing}
    (DESIGN / "economy_targets_v0.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
