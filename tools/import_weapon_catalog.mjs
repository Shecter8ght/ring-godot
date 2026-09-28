#!/usr/bin/env node
// Переносит утверждённую линейку и встроенные PNG из дизайн-документа в игровые данные.
// ВСС добавлен владельцем отдельно; его собственная иконка хранится в проекте и не перезаписывается.
// Запускать из корня проекта: node tools/import_weapon_catalog.mjs

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const htmlPath = path.resolve(process.argv[2] ?? path.join(root, "docs", "RING_weapon_design_doc_v9_final_cut.html"));
const weaponsPath = path.join(root, "data", "weapons.json");
const traderPath = path.join(root, "data", "trader.json");
const iconsDir = path.join(root, "assets", "icons");

function readConst(source, name) {
  const marker = `const ${name}`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`В HTML нет ${marker}`);
  const valueStart = source.indexOf("=", start) + 1;
  const lineEnd = source.indexOf("\n", valueStart);
  let raw = source.slice(valueStart, lineEnd).trim();
  if (raw.endsWith(";")) raw = raw.slice(0, -1);
  return JSON.parse(raw);
}

const source = fs.readFileSync(htmlPath, "utf8");
const iconData = readConst(source, "weaponIcons");
const designRows = readConst(source, "data");
const old = JSON.parse(fs.readFileSync(weaponsPath, "utf8"));
const oldPresets = structuredClone(old.presets);

const rarity = ["common", "common", "uncommon", "rare", "legendary"];
const fullRail = {
  optic_primary: "RAIL_TOP", optic_offset: "OFFSET_45", side_left: "RAIL_SIDE",
  side_right: "RAIL_SIDE", underbarrel: "RAIL_BOTTOM",
};

function weaponItem(name, code, value, weight, tier, tags, desc, spec, size = [4, 2]) {
  return {
    name, cat: "weapon", size, value, stack: 1, weight, tier, rarity: rarity[tier], tags,
    code, desc, weapon: spec,
  };
}

function weaponSpec(slot, klass, caliber, model, length, stats, mounts, feed = {}, extra = {}) {
  return {
    slot, class: klass, caliber, model, scale: model === "pistol" ? 1.0 : Math.min(1.15, Math.max(0.68, length / 0.9)), length,
    stats: {
      spread: 2.0, ads_spread: 0.35, ads_fov: 58.0, kick: 0.025, kick_h: 0.012,
      kick_bias: 0.3, recover: 0.4, shake: 0.09, ergo: 50, rpm: 600,
      auto: false, reload: 2.4, range: 100, noise: 80, reliability: 0.98, wear: 0.02,
      ...stats,
    },
    mounts, ...feed, sound: extra.sound ?? "shot_rifle",
    reload_sound: extra.reload_sound ?? (model === "pistol" ? "reload_pistol" : "reload_rifle"),
    cycle_sound: extra.cycle_sound ?? "", ...(extra.integral ? { integral: extra.integral } : {}),
    ...(extra.action ? { action: extra.action } : {}),
  };
}

const weapons = {
  wpn_hg_01: weaponItem("ПМ", "PM", 8000, 0.73, 1, ["CIVILIAN", "POLICE", "SCAV"],
    "Надёжный резервный пистолет. Компактный, но слабый патрон и почти нет места для обвеса.",
    weaponSpec("secondary", "PISTOL", "9x18", "pistol", 0.161,
      { spread: 1.8, ads_spread: 0.5, ads_fov: 62, kick: 0.055, kick_h: 0.015, kick_bias: 0.2, recover: 0.8, shake: 0.12, ergo: 70, rpm: 360, reload: 1.8, range: 45, noise: 55, reliability: 0.965 },
      {}, { mag_if: "MAG_PM", default_mag: "mag_918_8" }, { sound: "shot_hg_01" }), [2, 1]),
  wpn_hg_02: weaponItem("Glock 17 Gen5", "G17", 28000, 0.63, 2, ["CIVILIAN", "POLICE", "MILITARY"],
    "Универсальный полноразмерный пистолет: лёгкий, надёжный и хорошо принимает современный обвес.",
    weaponSpec("secondary", "PISTOL", "9x19", "pistol", 0.202,
      { spread: 1.35, ads_spread: 0.46, ads_fov: 62, kick: 0.047, kick_h: 0.013, kick_bias: 0.2, recover: 0.82, shake: 0.11, ergo: 78, rpm: 420, reload: 1.6, range: 60, noise: 60, reliability: 0.985 },
      { optic_primary: "SLIDE_RMR", underbarrel: "PISTOL_RAIL", muzzle: "THREAD_9" },
      { mag_if: "MAG_GLOCK9", default_mag: "mag_919_17" }, { sound: "shot_hg_02" }), [2, 1]),
  wpn_hg_03: weaponItem("HK USP .45", "USP45", 38000, 0.89, 2, ["POLICE", "MILITARY"],
    "Тяжёлый служебный пистолет .45 ACP. Сильнее бьёт по мягкой цели и особенно хорош с глушителем.",
    weaponSpec("secondary", "PISTOL", "45acp", "pistol", 0.24,
      { spread: 1.45, ads_spread: 0.47, ads_fov: 62, kick: 0.063, kick_h: 0.016, kick_bias: 0.2, recover: 0.74, shake: 0.15, ergo: 67, rpm: 360, reload: 1.75, range: 55, noise: 64, reliability: 0.985 },
      { optic_primary: "SLIDE_RMR", underbarrel: "PISTOL_RAIL", muzzle: "THREAD_45" },
      { mag_if: "MAG_USP45", default_mag: "mag_45_usp12" }, { sound: "shot_hg_03" }), [2, 1]),

  wpn_smg_01: weaponItem("HK UMP45", "UMP45", 55000, 2.3, 2, ["POLICE", "MILITARY"],
    "Неторопливый и легко контролируемый пистолет-пулемёт под тяжёлый .45 ACP.",
    weaponSpec("primary", "SMG", "45acp", "rifle", 0.69,
      { spread: 2.15, ads_spread: 0.4, kick: 0.026, kick_h: 0.013, recover: 0.43, shake: 0.08, ergo: 63, rpm: 600, auto: true, reload: 2.15, range: 65, noise: 68, reliability: 0.98 },
      { ...fullRail, muzzle: "THREAD_45", stock: "STOCK_SMG" },
      { mag_if: "MAG_UMP45", default_mag: "mag_45_ump25" }, { sound: "shot_smg" }), [3, 2]),
  wpn_smg_02: weaponItem("FN P90", "P90", 95000, 2.6, 3, ["POLICE", "MILITARY", "RARE"],
    "Компактный PDW с магазином на 50 патронов и настильным малокалиберным боеприпасом.",
    weaponSpec("primary", "PDW", "57x28", "rifle", 0.505,
      { spread: 2.0, ads_spread: 0.36, kick: 0.014, kick_h: 0.009, recover: 0.48, shake: 0.06, ergo: 70, rpm: 900, auto: true, reload: 2.45, range: 80, noise: 64, reliability: 0.98 },
      { optic_primary: "RAIL_TOP", side_left: "RAIL_SIDE", side_right: "RAIL_SIDE", muzzle: "THREAD_57" },
      { mag_if: "MAG_P90", default_mag: "mag_57_p90_50" }, { sound: "shot_smg" }), [3, 2]),
  wpn_smg_03: weaponItem("KRISS Vector", "VECTOR45", 115000, 3.3, 3, ["POLICE", "MILITARY", "RARE"],
    "Очень скорострельный .45 ACP с необычной схемой, которая удерживает очередь на цели.",
    weaponSpec("primary", "SMG", "45acp", "rifle", 0.70,
      { spread: 2.0, ads_spread: 0.36, kick: 0.017, kick_h: 0.009, recover: 0.5, shake: 0.065, ergo: 58, rpm: 1100, auto: true, reload: 2.2, range: 65, noise: 68, reliability: 0.97 },
      { ...fullRail, muzzle: "THREAD_45", stock: "STOCK_SMG" },
      { mag_if: "MAG_GLOCK45", default_mag: "mag_45_vector13" }, { sound: "shot_smg" }), [3, 2]),
  wpn_smg_04: weaponItem("PP-19-01 Vityaz", "VITYAZ", 45000, 2.9, 2, ["POLICE", "MILITARY"],
    "Российский модульный ПП: привычная эргономика АК, умеренный темп и магазин на 30.",
    weaponSpec("primary", "SMG", "9x19", "rifle", 0.698,
      { spread: 2.25, ads_spread: 0.39, kick: 0.02, kick_h: 0.011, recover: 0.44, shake: 0.07, ergo: 61, rpm: 700, auto: true, reload: 2.25, range: 65, noise: 62, reliability: 0.98 },
      { ...fullRail, muzzle: "THREAD_9", stock: "STOCK_AK" },
      { mag_if: "MAG_VITYAZ", default_mag: "mag_919_vityaz30" }, { sound: "shot_smg" }), [3, 2]),
  wpn_smg_05: weaponItem("SR-2M Veresk", "SR2M", 65000, 1.73, 3, ["POLICE", "MILITARY"],
    "Лёгкий бронепробивающий PDW под 9×21. Резкий темп компенсируется малой массой.",
    weaponSpec("primary", "PDW", "9x21", "rifle", 0.603,
      { spread: 2.2, ads_spread: 0.38, kick: 0.022, kick_h: 0.013, recover: 0.44, shake: 0.075, ergo: 72, rpm: 900, auto: true, reload: 2.0, range: 75, noise: 66, reliability: 0.975 },
      { optic_primary: "RAIL_TOP", side_right: "RAIL_SIDE", muzzle: "THREAD_9" },
      { mag_if: "MAG_SR2", default_mag: "mag_921_sr2_30" }, { sound: "shot_smg" }), [3, 2]),

  wpn_ar_01: weaponItem("AK-12", "AK12", 75000, 3.6, 2, ["MILITARY", "SCAV"],
    "Современный 5.45-мм автомат: предсказуемая отдача, надёжность и полный набор планок.",
    weaponSpec("primary", "ASSAULT_RIFLE", "545x39", "rifle", 0.93,
      { spread: 1.85, ads_spread: 0.33, kick: 0.019, kick_h: 0.01, recover: 0.4, shake: 0.085, ergo: 54, rpm: 700, auto: true, reload: 2.3, range: 105, noise: 80, reliability: 0.988 },
      { ...fullRail, muzzle: "THREAD_545", stock: "STOCK_AK" },
      { mag_if: "MAG_AK545", default_mag: "mag_545_30" })),
  wpn_sp_01: weaponItem("AS VAL", "ASVAL", 160000, 2.6, 4, ["MILITARY", "PERIMETER", "RARE"],
    "Специальный автомат со встроенным глушителем. Тихий и тяжёлый патрон, но небольшая дальность.",
    weaponSpec("primary", "SPECIAL", "9x39", "rifle", 0.875,
      { spread: 1.9, ads_spread: 0.34, kick: 0.024, kick_h: 0.012, recover: 0.42, shake: 0.08, ergo: 58, rpm: 800, auto: true, reload: 2.2, range: 75, noise: 28, reliability: 0.975 },
      { optic_primary: "RAIL_TOP", side_left: "RAIL_SIDE", side_right: "RAIL_SIDE", underbarrel: "RAIL_BOTTOM" },
      { mag_if: "MAG_VSS", default_mag: "mag_939_20" }, { sound: "shot_sup939", integral: { suppressed: true, db: -14 } })),
  wpn_sp_02: weaponItem("VSS Vintorez", "VSS", 175000, 2.6, 4, ["MILITARY", "PERIMETER", "RARE", "PRECISION"],
    "Бесшумная снайперская винтовка под 9×39. Точная и скрытная на средних дистанциях, но требовательна к выбору позиции.",
    weaponSpec("primary", "DMR", "9x39", "rifle", 0.894,
      { spread: 1.35, ads_spread: 0.16, ads_fov: 45, kick: 0.027, kick_h: 0.01, recover: 0.5, shake: 0.11, ergo: 49, rpm: 600, auto: true, reload: 2.35, range: 95, noise: 25, reliability: 0.98 },
      { optic_primary: "DOVETAIL" },
      { mag_if: "MAG_VSS", default_mag: "mag_939_10" }, { sound: "shot_sup939", integral: { suppressed: true, db: -15 } })),
  wpn_ar_02: weaponItem("M4A1", "M4A1", 90000, 2.9, 3, ["MILITARY", "POLICE"],
    "Лёгкий универсальный карабин 5.56: быстрый, удобный и совместим с распространёнными магазинами STANAG.",
    weaponSpec("primary", "CARBINE", "556x45", "rifle", 0.84,
      { spread: 1.65, ads_spread: 0.32, kick: 0.017, kick_h: 0.009, recover: 0.43, shake: 0.08, ergo: 61, rpm: 800, auto: true, reload: 2.15, range: 105, noise: 80, reliability: 0.977 },
      { ...fullRail, muzzle: "THREAD_556", stock: "STOCK_AR" },
      { mag_if: "MAG_STANAG", default_mag: "mag_556_30" })),
  wpn_ar_03: weaponItem("SIG MCX Virtus", "MCXV", 125000, 3.4, 3, ["MILITARY", "POLICE", "RARE"],
    "Модульный карабин .300 Blackout. Тяжёлый патрон эффективен из короткого ствола и с глушителем.",
    weaponSpec("primary", "CARBINE", "300blk", "rifle", 0.83,
      { spread: 1.7, ads_spread: 0.32, kick: 0.024, kick_h: 0.011, recover: 0.41, shake: 0.09, ergo: 58, rpm: 800, auto: true, reload: 2.2, range: 100, noise: 82, reliability: 0.98 },
      { ...fullRail, muzzle: "THREAD_300", stock: "STOCK_MCX" },
      { mag_if: "MAG_STANAG_300", default_mag: "mag_300_30" })),
  wpn_ar_04: weaponItem("FN SCAR-L", "SCARL", 135000, 3.6, 3, ["MILITARY", "RARE"],
    "Тяжелее M4, зато мягче в очереди и надёжен. Использует обычные магазины 5.56 STANAG.",
    weaponSpec("primary", "ASSAULT_RIFLE", "556x45", "rifle", 0.90,
      { spread: 1.55, ads_spread: 0.31, kick: 0.016, kick_h: 0.0085, recover: 0.44, shake: 0.075, ergo: 54, rpm: 625, auto: true, reload: 2.25, range: 110, noise: 80, reliability: 0.985 },
      { ...fullRail, muzzle: "THREAD_556", stock: "STOCK_SCAR" },
      { mag_if: "MAG_STANAG", default_mag: "mag_556_30" })),
  wpn_ar_05: weaponItem("SIG MCX Spear", "SPEAR", 210000, 3.8, 4, ["MILITARY", "PERIMETER", "RARE"],
    "Современная тяжёлая винтовка 6.8×51: высокая пробиваемость ценой отдачи, массы и дорогих патронов.",
    weaponSpec("primary", "BATTLE_RIFLE", "68x51", "rifle", 0.87,
      { spread: 1.55, ads_spread: 0.28, kick: 0.032, kick_h: 0.014, recover: 0.38, shake: 0.12, ergo: 47, rpm: 700, auto: true, reload: 2.45, range: 150, noise: 102, reliability: 0.985 },
      { ...fullRail, muzzle: "THREAD_68", stock: "STOCK_MCX" },
      { mag_if: "MAG_SPEAR68", default_mag: "mag_68_spear20" }, { sound: "shot_battle" })),

  wpn_dmr_01: weaponItem("HK MR762", "MR762", 155000, 4.5, 3, ["CIVILIAN", "PRECISION", "RARE"],
    "Точная самозарядная винтовка 7.62×51. Мощная, тяжёлая и удобная для средней и дальней дистанции.",
    weaponSpec("primary", "DMR", "762x51", "rifle", 1.0,
      { spread: 1.2, ads_spread: 0.12, ads_fov: 50, kick: 0.044, kick_h: 0.012, kick_bias: 0.2, recover: 0.56, shake: 0.2, ergo: 41, rpm: 260, reload: 2.55, range: 175, noise: 110, reliability: 0.985 },
      { ...fullRail, muzzle: "THREAD_762", stock: "STOCK_AR" },
      { mag_if: "MAG_SR25", default_mag: "mag_76251_20" }, { sound: "shot_battle" })),
  wpn_dmr_02: weaponItem("BCM MK12", "MK12", 135000, 4.0, 3, ["MILITARY", "PRECISION", "RARE"],
    "Марксманская 5.56 с длинным стволом: точнее карабина и легче тяжёлых 7.62-мм систем.",
    weaponSpec("primary", "DMR", "556x45", "rifle", 1.0,
      { spread: 1.15, ads_spread: 0.1, ads_fov: 50, kick: 0.018, kick_h: 0.008, kick_bias: 0.15, recover: 0.56, shake: 0.11, ergo: 45, rpm: 300, reload: 2.45, range: 155, noise: 88, reliability: 0.982 },
      { ...fullRail, muzzle: "THREAD_556", stock: "STOCK_AR" },
      { mag_if: "MAG_STANAG", default_mag: "mag_556_20" }, { sound: "shot_rifle" })),
  wpn_sr_01: weaponItem("Accuracy International AWM", "AWM", 260000, 6.8, 4, ["PRECISION", "PERIMETER", "RARE"],
    "Болтовая .338 Lapua для очень дальней дистанции. Исключительная точность, масса и цена.",
    weaponSpec("primary", "SNIPER", "338lm", "bolt", 1.27,
      { spread: 1.1, ads_spread: 0.02, ads_fov: 14, kick: 0.085, kick_h: 0.012, kick_bias: 0, recover: 0.8, shake: 0.36, ergo: 25, rpm: 45, reload: 3.2, range: 230, noise: 125, reliability: 0.995 },
      { muzzle: "THREAD_338", underbarrel: "BIPOD_CLAMP" },
      { mag_if: "MAG_AWM338", default_mag: "mag_338_awm5" }, { sound: "shot_bolt", cycle_sound: "bolt", integral: { zoom: 8 } }), [5, 2]),
  wpn_sr_02: weaponItem("Barrett M82A1", "M82A1", 420000, 13.5, 4, ["PRECISION", "PERIMETER", "RARE"],
    "Полуавтоматическая антиматериальная винтовка .50 BMG. Огромная мощность и почти неподъёмная масса.",
    weaponSpec("primary", "SNIPER", "50bmg", "bolt", 1.45,
      { spread: 1.25, ads_spread: 0.025, ads_fov: 14, kick: 0.11, kick_h: 0.016, kick_bias: 0, recover: 0.7, shake: 0.48, ergo: 10, rpm: 90, reload: 3.4, range: 260, noise: 140, reliability: 0.985 },
      { underbarrel: "BIPOD_CLAMP" },
      { mag_if: "MAG_M82", default_mag: "mag_50_m82_10" }, { sound: "shot_bolt", integral: { zoom: 10 } }), [5, 2]),

  wpn_sg_01: weaponItem("Benelli M4", "BENELLIM4", 75000, 3.5, 3, ["POLICE", "MILITARY"],
    "Премиальный полуавтоматический дробовик с трубчатым магазином. Быстр, надёжен и мягок в работе.",
    weaponSpec("primary", "SHOTGUN", "12x76", "shotgun", 1.01,
      { spread: 5.0, ads_spread: 0.8, ads_fov: 62, kick: 0.085, kick_h: 0.02, kick_bias: 0.1, recover: 0.62, shake: 0.3, ergo: 49, rpm: 300, reload: 3.2, range: 40, noise: 78, reliability: 0.985 },
      { optic_primary: "RAIL_TOP", side_right: "RAIL_SIDE", muzzle: "THREAD_12", stock: "STOCK_SG" },
      { internal_mag: 5 }, { sound: "shot_shotgun", reload_sound: "reload_shotgun" })),
  wpn_sg_02: weaponItem("Saiga-12K", "SAIGA12", 62000, 3.7, 3, ["CIVILIAN", "POLICE", "MILITARY"],
    "Магазинный полуавтомат 12/76. Самая гибкая платформа среди дробовиков, но тяжела и капризна с барабаном.",
    weaponSpec("primary", "SHOTGUN", "12x76", "shotgun", 0.91,
      { spread: 4.9, ads_spread: 0.79, ads_fov: 62, kick: 0.082, kick_h: 0.02, kick_bias: 0.1, recover: 0.62, shake: 0.3, ergo: 51, rpm: 300, reload: 2.65, range: 40, noise: 78, reliability: 0.975 },
      { ...fullRail, muzzle: "THREAD_12", stock: "STOCK_AK" },
      { mag_if: "MAG_S12", default_mag: "mag_s12_8" }, { sound: "shot_shotgun", reload_sound: "reload_shotgun" })),
  wpn_sg_03: weaponItem("Mossberg 590A1", "M590A1", 32000, 3.2, 2, ["CIVILIAN", "POLICE", "MILITARY"],
    "Простой тактический помповик. Медленнее полуавтоматов, зато дёшев, надёжен и всеяден.",
    weaponSpec("primary", "SHOTGUN", "12x76", "shotgun", 1.0,
      { spread: 5.4, ads_spread: 0.84, ads_fov: 62, kick: 0.092, kick_h: 0.022, kick_bias: 0.1, recover: 0.6, shake: 0.33, ergo: 42, rpm: 75, reload: 3.1, range: 37, noise: 78, reliability: 0.995 },
      { optic_primary: "RAIL_TOP", side_right: "RAIL_SIDE", muzzle: "THREAD_12", stock: "STOCK_SG" },
      { internal_mag: 7 }, { sound: "shot_shotgun", reload_sound: "reload_shotgun", cycle_sound: "reload_shotgun", action: "pump" })),

  wpn_lmg_01: weaponItem("PKM", "PKM", 230000, 8.5, 4, ["MILITARY", "PERIMETER", "RARE"],
    "Единый пулемёт 7.62×54R. Сокрушительный огонь и ленты на сотни патронов ценой массы и эргономики.",
    weaponSpec("primary", "LMG", "762x54r", "rifle", 1.17,
      { spread: 2.4, ads_spread: 0.42, kick: 0.046, kick_h: 0.018, recover: 0.3, shake: 0.17, ergo: 12, rpm: 700, auto: true, reload: 5.8, range: 160, noise: 118, reliability: 0.985 },
      { optic_primary: "RAIL_TOP", side_right: "RAIL_SIDE", underbarrel: "BIPOD_CLAMP" },
      { mag_if: "MAG_PKM", default_mag: "mag_pkm_100" }, { sound: "shot_battle" }), [5, 2]),
  wpn_lmg_02: weaponItem("M249 SAW", "M249", 250000, 8.0, 4, ["MILITARY", "PERIMETER", "RARE"],
    "Модульный ручной пулемёт 5.56. Легче контролировать, много обвеса и ленты на 100 или 200 патронов.",
    weaponSpec("primary", "LMG", "556x45", "rifle", 1.04,
      { spread: 2.2, ads_spread: 0.38, kick: 0.024, kick_h: 0.012, recover: 0.33, shake: 0.11, ergo: 18, rpm: 800, auto: true, reload: 5.2, range: 135, noise: 94, reliability: 0.98 },
      { ...fullRail, muzzle: "THREAD_556", stock: "STOCK_LMG" },
      { mag_if: "MAG_M249", default_mag: "mag_m249_100" }), [5, 2]),
};

// Отдельная фраза «В деле» не дублирует ТТХ: это короткая подсказка о роли и цене ошибки.
const weaponFlavor = {
  wpn_hg_01: "Когда основной ствол опустел, восемь патронов ПМ внезапно становятся очень убедительными.",
  wpn_hg_02: "Не самый редкий трофей, зато тот, который почти никогда не подводит в дверном проёме.",
  wpn_hg_03: "Тяжёлая пуля прощает неточный выстрел по цели без брони, но не торопливый палец.",
  wpn_smg_01: "Спокойный темп помогает держать очередь в силуэте, пока противник пытается пережить .45 ACP.",
  wpn_smg_02: "Пятьдесят лёгких патронов позволяют зачистить тесный магазин, не считая каждую короткую очередь.",
  wpn_smg_03: "Нажал слишком долго — магазин уже пуст; удержал очередь — коридор тоже.",
  wpn_smg_04: "Привычная логика АК и дешёвый патрон делают его рабочей лошадью ближнего рейда.",
  wpn_smg_05: "Лёгкий, злой и быстрый: хорош для первого номера, которому нельзя задерживаться на углу.",
  wpn_ar_01: "Ствол на каждый день: не лучший ни в одной крайности, зато почти везде уместен.",
  wpn_sp_01: "Если всё сделано правильно, соседний отряд поймёт, что бой начался, только по телам.",
  wpn_sp_02: "Выбирай голову и дистанцию: тихая точность ВСС важнее возможности удерживать спуск.",
  wpn_ar_02: "Лёгкость и обвесы поощряют движение; стоять с ним на месте — терять главное преимущество.",
  wpn_ar_03: "С дозвуком и глушителем превращает короткие дистанции в очень тихую одностороннюю беседу.",
  wpn_ar_04: "Тяжелее карабина, зато длинная очередь меньше спорит с тем, куда смотрит прицел.",
  wpn_ar_05: "Броня перестаёт быть гарантией, но каждый промах буквально выбрасывает деньги из ствола.",
  wpn_dmr_01: "Держи дистанцию и ритм: второй точный выстрел приходит раньше, чем цель успевает спрятаться.",
  wpn_dmr_02: "Хорошая позиция превращает мягкую отдачу в серию быстрых и очень неприятных поправок.",
  wpn_sr_01: "Один спокойный вдох экономит второй дорогой патрон и долгую работу затвора.",
  wpn_sr_02: "Это не оружие для обхода комнат — это способ отменить укрытие на другом конце галереи.",
  wpn_sg_01: "Пять зарядов требуют дисциплины, зато автоматика оставляет время исправить первый промах.",
  wpn_sg_02: "С барабаном можно задавить проход огнём, если вес не задавит тебя раньше.",
  wpn_sg_03: "Помпа не спешит, поэтому каждый выстрел лучше заранее назначить кому-то конкретному.",
  wpn_lmg_01: "Выбери проход, разложись и сделай так, чтобы противник пожалел о самом намерении его пересечь.",
  wpn_lmg_02: "Лента покупает отряду время для манёвра, а стрелку — обязанность не отстать с восемью килограммами.",
};
for (const [id, phrase] of Object.entries(weaponFlavor)) weapons[id].flavor = phrase;

const calibers = {
  "9x18": { name: "9×18" },
  "9x19": { name: "9×19" },
  "45acp": { name: ".45 ACP" },
  "57x28": { name: "5.7×28" },
  "9x21": { name: "9×21" },
  "545x39": { name: "5.45×39" },
  "9x39": { name: "9×39" },
  "556x45": { name: "5.56×45" },
  "300blk": { name: ".300 AAC Blackout" },
  "68x51": { name: "6.8×51" },
  "762x51": { name: "7.62×51" },
  "338lm": { name: ".338 Lapua Magnum" },
  "50bmg": { name: ".50 BMG" },
  "12x76": { name: "12/76" },
  "762x54r": { name: "7.62×54R" },
};

function ammoItem(name, short, caliber, value, weight, tier, tags, ballistics, stack = 50, desc = "") {
  const item = {
    name, cat: "ammo", size: [1, 1], value, stack, weight, tier, rarity: rarity[tier], tags, short,
    ammo: {
      caliber, pellets: 1, range_k: 1.0, accuracy: 1.0, ricochet: 0.1, frag: 0.0,
      ...ballistics,
    },
  };
  if (desc) item.desc = desc;
  return item;
}

const ammo = {
  ammo_918_pst: ammoItem("Патроны 9×18 ПСт", "9×18", "9x18", 45, 0.01, 1, ["CIVILIAN", "SCAV", "POLICE"], { damage: 26, pen: 10, armor_dmg: 14, velocity: 315 }),
  ammo_918_ap: ammoItem("Патроны 9×18 бронебойные", "9×18 БП", "9x18", 110, 0.01, 2, ["MILITARY"], { damage: 22, pen: 24, armor_dmg: 20, velocity: 330 }),
  ammo_919_exp: ammoItem("Патроны 9×19 экспансивные", "9×19 ЭКС", "9x19", 70, 0.012, 1, ["CIVILIAN", "POLICE"], { damage: 36, pen: 4, armor_dmg: 8, velocity: 360 }, 50, "Тяжело ранит незащищённого, броню почти не берёт."),
  ammo_919_fmj: ammoItem("Патроны 9×19 FMJ", "9×19", "9x19", 60, 0.012, 1, ["SCAV", "POLICE", "MILITARY"], { damage: 30, pen: 15, armor_dmg: 14, velocity: 370 }),
  ammo_919_ap: ammoItem("Патроны 9×19 бронебойные", "9×19 БП", "9x19", 160, 0.012, 3, ["MILITARY", "PERIMETER"], { damage: 26, pen: 30, armor_dmg: 22, velocity: 440 }),
  ammo_45_fmj: ammoItem("Патроны .45 ACP FMJ", ".45 FMJ", "45acp", 90, 0.021, 1, ["CIVILIAN", "POLICE", "MILITARY"], { damage: 42, pen: 14, armor_dmg: 16, velocity: 285 }),
  ammo_45_jhp: ammoItem("Патроны .45 ACP JHP", ".45 JHP", "45acp", 130, 0.021, 2, ["CIVILIAN", "POLICE"], { damage: 52, pen: 7, armor_dmg: 10, velocity: 270 }, 50, "Высокая останавливающая способность по незащищённой цели."),
  ammo_45_ap: ammoItem("Патроны .45 ACP бронебойные", ".45 БП", "45acp", 240, 0.021, 3, ["MILITARY", "PERIMETER"], { damage: 36, pen: 32, armor_dmg: 28, velocity: 340 }),
  ammo_57_std: ammoItem("Патроны 5.7×28", "5.7", "57x28", 130, 0.007, 2, ["POLICE", "MILITARY"], { damage: 26, pen: 23, armor_dmg: 20, velocity: 650 }),
  ammo_57_ap: ammoItem("Патроны 5.7×28 бронебойные", "5.7 БП", "57x28", 300, 0.007, 3, ["MILITARY", "PERIMETER"], { damage: 24, pen: 35, armor_dmg: 28, velocity: 715 }),
  ammo_921_std: ammoItem("Патроны 9×21", "9×21", "9x21", 130, 0.013, 2, ["POLICE", "MILITARY"], { damage: 34, pen: 20, armor_dmg: 20, velocity: 410 }),
  ammo_921_ap: ammoItem("Патроны 9×21 бронебойные", "9×21 БП", "9x21", 280, 0.013, 3, ["MILITARY", "PERIMETER"], { damage: 30, pen: 36, armor_dmg: 30, velocity: 430 }),
  ammo_545_old: ammoItem("Патроны 5.45×39 старые", "5.45 ст.", "545x39", 60, 0.011, 1, ["SCAV", "MILITARY"], { damage: 36, pen: 24, armor_dmg: 22, velocity: 880 }, 60, "Со складов: дешёвые, пробивают хуже."),
  ammo_545_std: ammoItem("Патроны 5.45×39", "5.45", "545x39", 90, 0.011, 2, ["SCAV", "MILITARY", "PERIMETER"], { damage: 38, pen: 32, armor_dmg: 28, velocity: 900 }, 60),
  ammo_545_ap: ammoItem("Патроны 5.45×39 бронебойные", "5.45 БП", "545x39", 260, 0.011, 3, ["MILITARY", "PERIMETER"], { damage: 34, pen: 48, armor_dmg: 38, velocity: 890 }, 60),
  ammo_939_sp5: ammoItem("Патроны 9×39 СП-5", "9×39 СП-5", "9x39", 240, 0.023, 3, ["MILITARY"], { damage: 48, pen: 30, armor_dmg: 30, velocity: 290, range_k: 0.8, accuracy: 0.85 }, 40),
  ammo_939_sp6: ammoItem("Патроны 9×39 СП-6", "9×39 СП-6", "9x39", 420, 0.023, 4, ["MILITARY", "PERIMETER"], { damage: 44, pen: 46, armor_dmg: 40, velocity: 300, range_k: 0.8 }, 40),
  ammo_556_civ: ammoItem("Патроны 5.56×45 гражданские", "5.56 гр.", "556x45", 80, 0.012, 1, ["CIVILIAN", "HUNTING"], { damage: 42, pen: 18, armor_dmg: 18, velocity: 920 }, 60),
  ammo_556_std: ammoItem("Патроны 5.56×45", "5.56", "556x45", 100, 0.012, 2, ["MILITARY", "PERIMETER", "POLICE"], { damage: 38, pen: 33, armor_dmg: 28, velocity: 940 }, 60),
  ammo_556_ap: ammoItem("Патроны 5.56×45 бронебойные", "5.56 БП", "556x45", 300, 0.012, 3, ["MILITARY", "PERIMETER"], { damage: 34, pen: 50, armor_dmg: 38, velocity: 960 }, 60),
  ammo_300_sup: ammoItem("Патроны .300 BLK", ".300", "300blk", 180, 0.016, 3, ["MILITARY", "POLICE"], { damage: 52, pen: 36, armor_dmg: 32, velocity: 650 }, 40),
  ammo_300_sub: ammoItem("Патроны .300 BLK дозвуковые", ".300 SUB", "300blk", 240, 0.019, 3, ["MILITARY", "PERIMETER"], { damage: 58, pen: 24, armor_dmg: 28, velocity: 320, range_k: 0.75 }, 40, "Тихие с глушителем, но быстро теряют силу на дальности."),
  ammo_68_std: ammoItem("Патроны 6.8×51", "6.8", "68x51", 320, 0.024, 4, ["MILITARY", "PERIMETER"], { damage: 62, pen: 47, armor_dmg: 44, velocity: 900 }, 40),
  ammo_68_ap: ammoItem("Патроны 6.8×51 бронебойные", "6.8 БП", "68x51", 620, 0.024, 4, ["PERIMETER", "RARE"], { damage: 58, pen: 62, armor_dmg: 54, velocity: 915 }, 40),
  ammo_76251_std: ammoItem("Патроны 7.62×51", "7.62×51", "762x51", 180, 0.025, 3, ["MILITARY", "PERIMETER"], { damage: 56, pen: 42, armor_dmg: 40, velocity: 830 }, 40),
  ammo_76251_match: ammoItem("Патроны 7.62×51 снайперские", "7.62 сн.", "762x51", 260, 0.025, 3, ["PERIMETER", "RARE"], { damage: 58, pen: 44, armor_dmg: 40, velocity: 820, range_k: 1.25, accuracy: 0.7 }, 40),
  ammo_76251_ap: ammoItem("Патроны 7.62×51 бронебойные", "7.62×51 БП", "762x51", 480, 0.025, 4, ["PERIMETER", "RARE"], { damage: 50, pen: 58, armor_dmg: 50, velocity: 850 }, 40),
  ammo_338_match: ammoItem("Патроны .338 Lapua Match", ".338 Match", "338lm", 650, 0.045, 4, ["PRECISION", "PERIMETER", "RARE"], { damage: 85, pen: 58, armor_dmg: 54, velocity: 900, range_k: 1.35, accuracy: 0.65 }, 20),
  ammo_338_ap: ammoItem("Патроны .338 Lapua бронебойные", ".338 БП", "338lm", 1100, 0.045, 4, ["PERIMETER", "RARE"], { damage: 80, pen: 75, armor_dmg: 68, velocity: 915, range_k: 1.25 }, 20),
  ammo_50_ball: ammoItem("Патроны .50 BMG", ".50", "50bmg", 1400, 0.115, 4, ["MILITARY", "PERIMETER", "RARE"], { damage: 130, pen: 80, armor_dmg: 80, velocity: 880, range_k: 1.4 }, 10),
  ammo_50_api: ammoItem("Патроны .50 BMG API", ".50 API", "50bmg", 2200, 0.115, 4, ["PERIMETER", "RARE"], { damage: 125, pen: 95, armor_dmg: 92, velocity: 890, range_k: 1.35 }, 10),
  ammo_12_buck: ammoItem("Картечь 12/76", "12 карт.", "12x76", 90, 0.045, 1, ["CIVILIAN", "HUNTING", "SCAV", "POLICE"], { damage: 12, pen: 4, armor_dmg: 5, pellets: 8, velocity: 400 }, 30, "Восемь картечин: страшно вблизи, бесполезно по броне."),
  ammo_12_hbuck: ammoItem("Картечь крупная 12/76", "12 кр.карт.", "12x76", 130, 0.045, 2, ["HUNTING", "POLICE"], { damage: 16, pen: 7, armor_dmg: 7, pellets: 6, velocity: 410 }, 30),
  ammo_12_slug: ammoItem("Пуля 12/76", "12 пуля", "12x76", 165, 0.045, 2, ["HUNTING", "POLICE"], { damage: 75, pen: 18, armor_dmg: 34, velocity: 430, accuracy: 0.6 }, 30),
  ammo_12_apslug: ammoItem("Пуля бронебойная 12/76", "12 БП", "12x76", 400, 0.045, 3, ["MILITARY", "PERIMETER"], { damage: 62, pen: 34, armor_dmg: 40, velocity: 470, accuracy: 0.6 }, 30),
  ammo_76254_std: ammoItem("Патроны 7.62×54R", "7.62R", "762x54r", 140, 0.022, 2, ["HUNTING", "SCAV", "MILITARY"], { damage: 58, pen: 42, armor_dmg: 42, velocity: 830 }, 40),
  ammo_76254_ap: ammoItem("Патроны 7.62×54R бронебойные", "7.62R БП", "762x54r", 420, 0.022, 4, ["MILITARY", "PERIMETER"], { damage: 52, pen: 56, armor_dmg: 50, velocity: 840 }, 40),
};

const ammoFlavor = {
  ammo_918_pst: "Дешёвый способ напомнить безбронной цели, что запасной пистолет всё ещё оружие.",
  ammo_918_ap: "ПМ не станет автоматом, но хотя бы перестанет совсем пасовать перед лёгкой бронёй.",
  ammo_919_exp: "Выбирай мягкую цель и не спорь с плитами — у этого патрона другая работа.",
  ammo_919_fmj: "Нормальный патрон для нормальной драки: доступный, предсказуемый, без чудес.",
  ammo_919_ap: "Дорого для очереди, зато бронежилет уже не даёт противнику чувства полной безопасности.",
  ammo_45_fmj: "Медленная тяжёлая пуля лучше всего объясняет свою ценность на короткой дистанции.",
  ammo_45_jhp: "По открытой цели действует убедительно; по плите оставляет в основном плохое настроение.",
  ammo_45_ap: "Редкий случай, когда тяжёлый пистолетный калибр может всерьёз поговорить с бронёй.",
  ammo_57_std: "Малая отдача и высокая скорость любят короткие контролируемые очереди.",
  ammo_57_ap: "Пятьдесят шансов быстро разобрать лёгкую броню — если не растратить их в потолок.",
  ammo_921_std: "Резкий патрон для резкого оружия: держи темп, иначе магазин исчезнет мгновенно.",
  ammo_921_ap: "Компактный ПП с такими патронами опасен даже там, где ждут только винтовку.",
  ammo_545_old: "Для дешёвого рейда сойдёт; против серьёзной плиты лучше сэкономить не на патронах.",
  ammo_545_std: "Рабочая середина АК-12: хватает и на мародёров, и на разумную цену очереди.",
  ammo_545_ap: "Береги для бронированных целей — стрелять ими по пустым банкам слишком расточительно.",
  ammo_939_sp5: "Тихий выстрел ценнее громкой победы, пока дистанция остаётся короткой.",
  ammo_939_sp6: "Когда скрытность уже нарушена, этот тяжёлый дозвук помогает закончить разговор через броню.",
  ammo_556_civ: "Метко бьёт по мягкой цели, но не рассчитывай остановить им хорошо экипированного бойца.",
  ammo_556_std: "Универсальная пачка для длинного рейда: достаточно серьёзная и ещё не разорительная.",
  ammo_556_ap: "Короткие очереди окупаются лучше: каждый потерянный патрон стоил как небольшой трофей.",
  ammo_300_sup: "Сильный удар из короткого ствола — полезно там, где длинная винтовка цепляется за стены.",
  ammo_300_sub: "С глушителем слышно мало; на дальней дистанции от его энергии тоже остаётся немного.",
  ammo_68_std: "Тяжёлая винтовка получает смысл, когда обычный автомат уже не уверен в броне цели.",
  ammo_68_ap: "Патрон для самой неприятной брони и самого неприятного счёта после рейда.",
  ammo_76251_std: "Один точный выстрел обычно полезнее трёх быстрых — отдача сама подсказывает этот ритм.",
  ammo_76251_match: "Хорошая оптика и спокойный спуск превращают его цену в дистанционное преимущество.",
  ammo_76251_ap: "Оставь для плит высокого класса: по безбронной цели его возможности пропадают зря.",
  ammo_338_match: "Промах слышит весь сектор, попадание — обычно только тот, кто уже ничего не расскажет.",
  ammo_338_ap: "Редкая цель действительно требует такой пробиваемости; ещё реже она переживает попадание.",
  ammo_50_ball: "Каждый выстрел меняет бой и положение стрелка — скрытность после него заканчивается.",
  ammo_50_api: "Если обычный .50 кажется недостаточным, проблема, вероятно, уже больше человека.",
  ammo_12_buck: "Подпусти ближе: восемь картечин не любят расстояние, зато очень любят дверные проёмы.",
  ammo_12_hbuck: "Меньше дробин, больше уверенности в каждой — держи центр осыпи на цели.",
  ammo_12_slug: "Превращает дробовик в грубую винтовку, но промах всё равно остаётся единственным снарядом.",
  ammo_12_apslug: "Шанс удивить броню из гладкого ствола; отдача и цена не дадут забыть о выборе.",
  ammo_76254_std: "Пулемётная лента быстро превращает разумную цену одного патрона в крупную сумму.",
  ammo_76254_ap: "Клади в начало ленты, если ожидаешь броню, и не поливай ими пустой коридор.",
};
for (const [id, phrase] of Object.entries(ammoFlavor)) ammo[id].flavor = phrase;

function magItem(name, short, iface, capacity, value, weight, tier, tags, size = [1, 2], reloadK = 1.0, ergo = 0, reliability = 1.0, look = "") {
  const mag = { if: iface, capacity, reload_k: reloadK, ergo, reliability };
  if (look) mag.look = look;
  return { name, cat: "mag", size, value, stack: 1, weight, tier, rarity: rarity[tier], tags, short, mag };
}

const magazines = {
  mag_918_8: magItem("Магазин ПМ на 8", "8", "MAG_PM", 8, 800, 0.08, 1, ["CIVILIAN", "POLICE", "SCAV"], [1, 1]),
  mag_919_17: magItem("Магазин Glock 9×19 на 17", "17", "MAG_GLOCK9", 17, 1400, 0.1, 1, ["POLICE", "MILITARY", "SCAV"], [1, 1]),
  mag_919_33: magItem("Магазин Glock 9×19 на 33", "33", "MAG_GLOCK9", 33, 5200, 0.2, 2, ["POLICE", "MILITARY"], [1, 2], 1.15, -4, 0.97, "mag_pistol_ext"),
  mag_45_usp12: magItem("Магазин HK USP .45 на 12", "12", "MAG_USP45", 12, 2200, 0.14, 2, ["POLICE", "MILITARY"], [1, 1]),
  mag_45_ump25: magItem("Магазин UMP45 на 25", "25", "MAG_UMP45", 25, 3200, 0.28, 2, ["POLICE", "MILITARY"]),
  mag_57_p90_50: magItem("Магазин P90 на 50", "50", "MAG_P90", 50, 6500, 0.28, 3, ["POLICE", "MILITARY", "RARE"], [2, 1], 1.12, -3, 0.98),
  mag_45_vector13: magItem("Магазин Vector .45 на 13", "13", "MAG_GLOCK45", 13, 2400, 0.15, 2, ["POLICE", "MILITARY"], [1, 1]),
  mag_45_vector30: magItem("Магазин Vector .45 на 30", "30", "MAG_GLOCK45", 30, 7800, 0.32, 3, ["MILITARY", "RARE"], [1, 2], 1.18, -5, 0.97, "mag_pistol_ext"),
  mag_919_vityaz30: magItem("Магазин Vityaz на 30", "30", "MAG_VITYAZ", 30, 2400, 0.22, 2, ["POLICE", "MILITARY", "SCAV"]),
  mag_921_sr2_20: magItem("Магазин Veresk на 20", "20", "MAG_SR2", 20, 2800, 0.16, 2, ["POLICE", "MILITARY"], [1, 1]),
  mag_921_sr2_30: magItem("Магазин Veresk на 30", "30", "MAG_SR2", 30, 4400, 0.22, 3, ["POLICE", "MILITARY"]),
  mag_545_30: magItem("Магазин 5.45×39 на 30", "30", "MAG_AK545", 30, 2000, 0.23, 1, ["SCAV", "MILITARY", "PERIMETER"]),
  mag_545_45: magItem("Магазин 5.45×39 на 45", "45", "MAG_AK545", 45, 9000, 0.36, 2, ["SCAV", "MILITARY"], [1, 2], 1.15, -7, 0.98, "mag_ak45"),
  mag_545_60: magItem("Магазин 5.45×39 на 60", "60", "MAG_AK545", 60, 16000, 0.52, 3, ["MILITARY"], [1, 2], 1.3, -11, 0.95, "mag_ak45"),
  mag_939_10: magItem("Магазин ВСС / АС ВАЛ на 10", "10", "MAG_VSS", 10, 5000, 0.12, 3, ["MILITARY", "PERIMETER"], [1, 1]),
  mag_939_20: magItem("Магазин ВСС / АС ВАЛ на 20", "20", "MAG_VSS", 20, 9000, 0.2, 3, ["MILITARY", "PERIMETER"], [1, 2], 1.1, -3),
  mag_556_20: magItem("Магазин STANAG 5.56 на 20", "20", "MAG_STANAG", 20, 2200, 0.13, 2, ["MILITARY", "POLICE"], [1, 1]),
  mag_556_30: magItem("Магазин STANAG 5.56 на 30", "30", "MAG_STANAG", 30, 2500, 0.16, 2, ["MILITARY", "PERIMETER", "POLICE"]),
  mag_556_40: magItem("Магазин STANAG 5.56 на 40", "40", "MAG_STANAG", 40, 8000, 0.23, 3, ["MILITARY", "PERIMETER"], [1, 2], 1.12, -5, 0.98, "mag_ak45"),
  mag_556_60: magItem("Магазин STANAG 5.56 на 60", "60", "MAG_STANAG", 60, 18000, 0.5, 3, ["PERIMETER", "RARE"], [1, 2], 1.3, -10, 0.95, "mag_ak45"),
  mag_300_30: magItem("Магазин .300 BLK на 30", "30", "MAG_STANAG_300", 30, 3200, 0.18, 3, ["MILITARY", "POLICE"]),
  mag_68_spear20: magItem("Магазин MCX Spear на 20", "20", "MAG_SPEAR68", 20, 8500, 0.32, 4, ["MILITARY", "PERIMETER", "RARE"]),
  mag_76251_10: magItem("Магазин 7.62×51 на 10", "10", "MAG_SR25", 10, 4000, 0.18, 3, ["MILITARY", "PERIMETER"], [1, 1]),
  mag_76251_20: magItem("Магазин 7.62×51 на 20", "20", "MAG_SR25", 20, 7000, 0.28, 3, ["MILITARY", "PERIMETER"], [1, 2], 1.1, -3),
  mag_338_awm5: magItem("Магазин AWM .338 на 5", "5", "MAG_AWM338", 5, 11000, 0.22, 4, ["PRECISION", "PERIMETER", "RARE"], [1, 1]),
  mag_50_m82_10: magItem("Магазин M82A1 на 10", "10", "MAG_M82", 10, 24000, 1.2, 4, ["PERIMETER", "RARE"], [2, 2], 1.2, -8),
  mag_s12_8: magItem("Магазин Saiga-12 12/76 на 8", "8", "MAG_S12", 8, 3800, 0.34, 2, ["MILITARY", "POLICE"], [1, 2]),
  mag_s12_20: magItem("Барабан Saiga-12 12/76 на 20", "20", "MAG_S12", 20, 14500, 1.1, 3, ["PERIMETER", "RARE"], [2, 2], 1.35, -12, 0.95),
  mag_pkm_100: magItem("Короб PKM с лентой на 100", "100", "MAG_PKM", 100, 18000, 4.0, 4, ["MILITARY", "PERIMETER"], [2, 2], 1.0, -10),
  mag_pkm_200: magItem("Короб PKM с лентой на 200", "200", "MAG_PKM", 200, 32000, 8.0, 4, ["PERIMETER", "RARE"], [3, 2], 1.35, -20, 0.96),
  mag_m249_100: magItem("Мягкий короб M249 с лентой на 100", "100", "MAG_M249", 100, 16000, 2.5, 4, ["MILITARY", "PERIMETER"], [2, 2], 1.0, -8),
  mag_m249_200: magItem("Короб M249 с лентой на 200", "200", "MAG_M249", 200, 30000, 5.0, 4, ["PERIMETER", "RARE"], [3, 2], 1.3, -18, 0.97),
};

function magazineFlavorText(item) {
  const m = item.mag;
  if (m.capacity >= 200) return "Двести выстрелов закрывают проход надолго, но такой короб сам просится в отдельный рюкзак.";
  if (m.capacity >= 100) return "Можно вести бой, а не считать остаток, пока вес ленты не заставит остановиться.";
  if (m.capacity >= 50) return "Редко требует перезарядки в бою, зато заметно утяжеляет оружие и ошибки обращения.";
  if (m.reload_k >= 1.25) return "Боезапас впечатляет до первой долгой перезарядки; меняй его только из укрытия.";
  if (m.ergo <= -6) return "Дополнительные патроны полезны, но торчащий магазин делает оружие менее послушным.";
  if (m.capacity <= 10) return "Малый запас дисциплинирует: считай выстрелы и держи ещё один магазин рядом.";
  if (m.capacity <= 20) return "Компактный и удобный запасной магазин для тех, кто предпочитает чаще менять, чем дольше целиться.";
  return "Рабочая ёмкость без крайностей: достаточно для схватки и ещё не мешает управлять оружием.";
}
for (const item of Object.values(magazines)) item.flavor = magazineFlavorText(item);

function modItem(name, value, tier, tags, attach, size = [1, 1], weight = 0.2) {
  return { name, cat: "mod", size, value, stack: 1, weight, tier, rarity: rarity[tier], tags, attach };
}

const attachments = structuredClone(old.attachments);
attachments.muzzle_comp_9_01 = modItem("Компенсатор 9 мм", 6500, 2, ["POLICE", "MILITARY"], {
  type: "COMPENSATOR", fits: ["THREAD_9"], look: "compensator",
  fx: { kick: 0.78, kick_h: 0.86, shake: 0.84, noise: 1.1, ergo: -2 },
});
attachments.muzzle_supp_45_01 = modItem("Глушитель .45 ACP", 22000, 3, ["POLICE", "MILITARY"], {
  type: "SUPPRESSOR", fits: ["THREAD_45"], look: "suppressor",
  fx: { noise: 0.38, db: -13, damage: 0.97, suppressed: true, ergo: -7, kick: 0.9, flash: 0 }, size_m: [0.019, 0.16],
}, [1, 2], 0.42);
attachments.muzzle_supp_57_01 = modItem("Глушитель 5.7", 26000, 3, ["MILITARY", "RARE"], {
  type: "SUPPRESSOR", fits: ["THREAD_57"], look: "suppressor",
  fx: { noise: 0.36, db: -14, damage: 0.96, suppressed: true, ergo: -7, kick: 0.9, flash: 0 }, size_m: [0.018, 0.16],
}, [1, 2], 0.38);
attachments.muzzle_supp_300_01 = modItem("Глушитель .300 BLK", 32000, 3, ["MILITARY", "PERIMETER"], {
  type: "SUPPRESSOR", fits: ["THREAD_300"], look: "suppressor",
  fx: { noise: 0.32, db: -16, damage: 0.97, suppressed: true, ergo: -9, kick: 0.86, flash: 0 }, size_m: [0.021, 0.19],
}, [1, 2], 0.52);
attachments.muzzle_brake_68_01 = modItem("Дульный тормоз 6.8", 16000, 4, ["PERIMETER", "RARE"], {
  type: "MUZZLE_BRAKE", fits: ["THREAD_68"], look: "compensator",
  fx: { kick: 0.67, kick_h: 0.86, shake: 0.76, noise: 1.22, ergo: -4 },
}, [1, 1], 0.24);
attachments.muzzle_supp_68_01 = modItem("Глушитель 6.8", 52000, 4, ["PERIMETER", "RARE"], {
  type: "SUPPRESSOR", fits: ["THREAD_68"], look: "suppressor",
  fx: { noise: 0.42, db: -12, damage: 0.97, suppressed: true, ergo: -12, kick: 0.84, flash: 0 }, size_m: [0.024, 0.21],
}, [1, 2], 0.7);
attachments.muzzle_brake_338_01 = modItem("Дульный тормоз .338", 24000, 4, ["PRECISION", "PERIMETER"], {
  type: "MUZZLE_BRAKE", fits: ["THREAD_338"], look: "compensator",
  fx: { kick: 0.64, kick_h: 0.86, shake: 0.72, noise: 1.25, ergo: -5 },
}, [1, 1], 0.32);
attachments.muzzle_supp_338_01 = modItem("Глушитель .338", 72000, 4, ["PRECISION", "PERIMETER", "RARE"], {
  type: "SUPPRESSOR", fits: ["THREAD_338"], look: "suppressor",
  fx: { noise: 0.45, db: -10, damage: 0.97, suppressed: true, ergo: -15, kick: 0.82, flash: 0 }, size_m: [0.027, 0.24],
}, [1, 2], 0.9);

// Универсальные процедурные приклады изображают адаптеры разных современных платформ.
for (const id of ["stock_tele_ar_01", "stock_perimeter_01"]) {
  const fits = attachments[id].attach.fits;
  for (const iface of ["STOCK_SMG", "STOCK_MCX", "STOCK_SCAR", "STOCK_LMG"]) {
    if (!fits.includes(iface)) fits.push(iface);
  }
}

const attachmentFlavorByType = {
  OPTIC_RED_DOT: "Точка экономит доли секунды вблизи — обычно именно их и не хватает в дверях.",
  OFFSET_RED_DOT: "Наклони оружие вместо смены прицела: дальняя оптика останется на месте, а ближняя цель — нет.",
  OPTIC_HOLOGRAPHIC: "Большое окно помогает поймать цель на ходу, когда идеальная вкладка невозможна.",
  OPTIC_2X: "Достаточно приближает дальний конец магазина и ещё не превращает ближний бой в туннель.",
  OPTIC_4X: "На открытой галерее даёт преимущество; в тесной подсобке просит запасной прицел.",
  OPTIC_LPVO: "Один прицел закрывает почти все дистанции, если успеваешь выбрать нужную кратность заранее.",
  OPTIC_8X: "Хорошая позиция становится опаснее, плохая — просто показывает поражение крупнее.",
  OPTIC_12X: "Видит далеко, весит много и не прощает попытку искать цель в соседней комнате.",
  FLASH_HIDER: "Ночью первая очередь выдаёт меньше, а второй шанс сменить позицию становится реальнее.",
  COMPENSATOR: "Очередь собирается плотнее, но противник быстрее понимает, откуда раздался громкий ответ.",
  MUZZLE_BRAKE: "Удерживает тяжёлый ствол на цели ценой звука, который услышит половина сектора.",
  SUPPRESSOR: "Не делает выстрел бесшумным — только оставляет соседним отрядам меньше подсказок.",
  VERTICAL_GRIP: "Полезна тому, кто ведёт цель очередью и не хочет ловить прицел после каждого выстрела.",
  ANGLED_GRIP: "Хороша для первого номера: быстрее поднял оружие — раньше решил исход встречи.",
  COMPACT_GRIP: "Небольшая помощь без большого штрафа; свободное место иногда важнее максимальных процентов.",
  HEAVY_GRIP: "Ствол спорит с отдачей меньше, зато с руками стрелка — заметно больше.",
  HAND_STOP: "Не творит чудес, но делает лёгкий карабин ещё быстрее в коротких переносах.",
  BIPOD: "Разложись до выстрела: с упора оружие становится точнее, но отходить придётся не мгновенно.",
  FIXED_HEAVY: "Стабильность для того, кто готов принести лишний вес на хорошую огневую позицию.",
  FIXED_LIGHT: "Быстрее разворачивает оружие в тесноте, но длинная очередь сильнее напоминает о компромиссе.",
  TELESCOPIC: "Универсальный выбор без яркого таланта — зато и без неприятного сюрприза в бою.",
  FOLDING: "Удобен в узких проходах и на бегу, пока не потребуется удержать длинную очередь.",
  PERIMETER_TACTICAL: "Дорогой способ сделать тяжёлое оружие послушнее; трофей, который стоит снять первым.",
  FLASHLIGHT: "Луч находит цель в темноте и одновременно рисует противнику направление к тебе.",
  LASER: "Помогает стрелять от бедра, но красная точка одинаково понятна обеим сторонам.",
  FLASHLIGHT_LASER_COMBO: "Две возможности занимают одну планку — и требуют помнить, что именно сейчас включено.",
};
for (const [id, item] of Object.entries(attachments)) {
  const phrase = attachmentFlavorByType[item.attach.type];
  if (!phrase) throw new Error(`Нет игровой фразы для обвеса ${id} (${item.attach.type})`);
  item.flavor = phrase;
}

const legacyWeaponMap = {
  wpn_hg_04: "wpn_hg_02", wpn_sg_04: "wpn_sg_02", wpn_ar_06: "wpn_ar_01",
  wpn_ar_07: "wpn_ar_02", wpn_ar_08: "wpn_ar_05", wpn_dmr_03: "wpn_dmr_01",
};
const defaultAmmo = {
  "9x18": "ammo_918_pst", "9x19": "ammo_919_fmj", "45acp": "ammo_45_fmj",
  "57x28": "ammo_57_std", "9x21": "ammo_921_std", "545x39": "ammo_545_std",
  "9x39": "ammo_939_sp5", "556x45": "ammo_556_std", "300blk": "ammo_300_sup",
  "68x51": "ammo_68_std", "762x51": "ammo_76251_std", "338lm": "ammo_338_match",
  "50bmg": "ammo_50_ball", "12x76": "ammo_12_buck", "762x54r": "ammo_76254_std",
};

function basePreset(weaponId, durability = [60, 95]) {
  const w = weapons[weaponId].weapon;
  const p = { weapon: weaponId, mods: {}, ammo: [[defaultAmmo[w.caliber], 1]], dur: durability, sight: "primary" };
  if (w.mag_if) p.mag = w.default_mag;
  return p;
}

function sanitizePreset(input) {
  const weaponId = legacyWeaponMap[input.weapon] ?? input.weapon;
  if (!weapons[weaponId]) return null;
  const spec = weapons[weaponId].weapon;
  const p = basePreset(weaponId, input.dur ?? [50, 90]);
  p.sight = input.sight ?? "primary";
  p.mods = {};
  for (const [mount, attachmentId] of Object.entries(input.mods ?? {})) {
    const iface = spec.mounts[mount];
    const a = attachments[attachmentId]?.attach;
    if (iface && a?.fits?.includes(iface)) p.mods[mount] = attachmentId;
  }
  const compatibleAmmo = (input.ammo ?? []).filter(([id]) => ammo[id]?.ammo.caliber === spec.caliber);
  if (compatibleAmmo.length) p.ammo = compatibleAmmo;
  return p;
}

const presets = {};
for (const [id, preset] of Object.entries(oldPresets)) {
  const cleaned = sanitizePreset(preset);
  if (cleaned) presets[id] = cleaned;
}

const catalogPresets = {
  PM_BASE: "wpn_hg_01", GLOCK17_BASE: "wpn_hg_02", USP45_BASE: "wpn_hg_03",
  UMP45_BASE: "wpn_smg_01", P90_BASE: "wpn_smg_02", VECTOR45_BASE: "wpn_smg_03",
  VITYAZ_BASE: "wpn_smg_04", VERESK_BASE: "wpn_smg_05", AK12_BASE: "wpn_ar_01",
  ASVAL_BASE: "wpn_sp_01", VSS_BASE: "wpn_sp_02", M4A1_BASE: "wpn_ar_02", MCXV_BASE: "wpn_ar_03",
  SCARL_BASE: "wpn_ar_04", SPEAR_BASE: "wpn_ar_05", MR762_BASE: "wpn_dmr_01",
  MK12_BASE: "wpn_dmr_02", AWM_BASE: "wpn_sr_01", M82A1_BASE: "wpn_sr_02",
  BENELLI_M4_BASE: "wpn_sg_01", SAIGA12_BASE: "wpn_sg_02", M590A1_BASE: "wpn_sg_03",
  PKM_BASE: "wpn_lmg_01", M249_BASE: "wpn_lmg_02",
};
for (const [id, weaponId] of Object.entries(catalogPresets)) presets[id] = basePreset(weaponId, [70, 100]);

const aliases = {
  ...old.aliases,
  w_pistol: "wpn_hg_02", w_rifle: "wpn_ar_01", w_shotgun: "wpn_sg_03", w_bolt: "wpn_sr_01",
  wpn_hg_04: "wpn_hg_02", wpn_sg_04: "wpn_sg_02", wpn_ar_06: "wpn_ar_01",
  wpn_ar_07: "wpn_ar_02", wpn_ar_08: "wpn_ar_05", wpn_dmr_03: "wpn_dmr_01",
  ammo_76239_std: "ammo_545_old", ammo_76239_hvy: "ammo_545_std", ammo_76239_ap: "ammo_545_ap",
  mag_762_30: "mag_545_30", mag_762_40: "mag_545_45", mag_smg9_30: "mag_919_vityaz30",
  mag_smg9_50: "mag_919_vityaz30", mag_svd_10: "mag_pkm_100",
};

for (const [groupName, group] of Object.entries({ weapons, ammo, magazines, attachments })) {
  for (const [id, item] of Object.entries(group)) {
    if (!String(item.flavor ?? "").trim()) throw new Error(`Нет игровой фразы: ${groupName}.${id}`);
  }
}

const result = {
  _comment: "Арсенал из docs/RING_weapon_design_doc_v9_final_cut.html: 23 реальные платформы плюс отдельно добавленный владельцем VSS Vintorez. Иконки основной линейки извлекаются tools/import_weapon_catalog.mjs; собственная иконка ВСС хранится в проекте. Процедурные 3D-основы временно сохранены. Вместимости магазинов и ключевые параметры сверены с материалами производителей; игровой баланс намеренно не является симулятором.",
  calibers, models: old.models, weapons, ammo, magazines, attachments, presets,
  // Горячие клавиши песочницы рассчитаны на четыре слота; полный каталог доступен через консоль и админ-магазин.
  sandbox: ["GLOCK17_BASE", "AK12_BASE", "SAIGA12_BASE", "AWM_BASE"], aliases,
};
fs.writeFileSync(weaponsPath, `${JSON.stringify(result, null, 1)}\n`, "utf8");

const trader = JSON.parse(fs.readFileSync(traderPath, "utf8"));
const oldArsenalIds = new Set([
  ...Object.keys(old.weapons), ...Object.keys(old.ammo), ...Object.keys(old.magazines), ...Object.keys(old.attachments),
]);
const nonArsenalStock = trader.stock.filter((id) => !oldArsenalIds.has(id));
const regularWeapons = Object.keys(weapons).filter((id) => weapons[id].tier <= 3);
const regularAmmo = Object.keys(ammo).filter((id) => ammo[id].tier <= 3);
const regularMags = Object.keys(magazines).filter((id) => magazines[id].tier <= 3);
const regularAttachments = Object.keys(attachments).filter((id) => attachments[id].tier <= 3);
trader._comment = "Михалыч продаёт 23 платформы из финального дизайн-документа и отдельно добавленный ВСС: T1 сразу, T2 с доверием 2, T3 с доверием 3. T4 появляется только при админском чите «Любое оружие».";
trader.stock = [...regularWeapons, ...regularAmmo, ...regularMags, ...regularAttachments, ...nonArsenalStock];
const trust = {};
for (const [id, level] of Object.entries(trader.trust)) {
  if (!oldArsenalIds.has(id)) trust[id] = level;
}
for (const section of [weapons, ammo, magazines, attachments]) {
  for (const [id, item] of Object.entries(section)) {
    if (item.tier > 1) trust[id] = item.tier;
  }
}
trader.trust = trust;
fs.writeFileSync(traderPath, `${JSON.stringify(trader, null, 1)}\n`, "utf8");

const iconNames = {
  "ПМ": "wpn_hg_01", "Glock 17 Gen5": "wpn_hg_02", "HK USP .45": "wpn_hg_03",
  // В HTML эти три ключа циклически перепутаны; здесь силуэты возвращены своим моделям.
  "FN P90": "wpn_smg_01", "PP-19-01 Vityaz": "wpn_smg_02", "KRISS Vector": "wpn_smg_03",
  "HK UMP45": "wpn_smg_04", "SR-2M Veresk": "wpn_smg_05", "AK-12": "wpn_ar_01",
  "AS VAL": "wpn_sp_01", "M4A1": "wpn_ar_02", "SIG MCX Virtus": "wpn_ar_03",
  "FN SCAR-L": "wpn_ar_04", "SIG MCX Spear": "wpn_ar_05", "HK MR762": "wpn_dmr_01",
  "BCM MK12": "wpn_dmr_02", "Accuracy International AWM": "wpn_sr_01", "Barrett M82A1": "wpn_sr_02",
  "Benelli M4": "wpn_sg_01", "Saiga-12K": "wpn_sg_02", "Mossberg 590A1": "wpn_sg_03",
  "PKM": "wpn_lmg_01", "M249 SAW": "wpn_lmg_02",
};
const designNames = new Set(designRows.map((row) => row["Оружие"]));
fs.mkdirSync(iconsDir, { recursive: true });
for (const [name, id] of Object.entries(iconNames)) {
  if (!designNames.has(name) || !iconData[name]) throw new Error(`Нет строки или иконки для ${name}`);
  const [, encoded] = iconData[name].split(",", 2);
  fs.writeFileSync(path.join(iconsDir, `${id}.png`), Buffer.from(encoded, "base64"));
}

const vssIconPath = path.join(iconsDir, "wpn_sp_02.png");
if (!fs.existsSync(vssIconPath)) throw new Error("Нет собственной иконки VSS Vintorez: assets/icons/wpn_sp_02.png");

console.log(`Готово: ${Object.keys(weapons).length} оружия, ${Object.keys(calibers).length} калибров, ${Object.keys(magazines).length} магазинов, ${Object.keys(iconNames).length + 1} PNG.`);
