import type { MetaProgress } from "@/core/MetaProgress";
import { UPGRADE_NAMES, upgradeMaxLevel, type UpgradeKey } from "@/core/Hideout";
import { itemDef } from "@/inventory/Items";

/** Как выходы называются на экране итогов (карта в core не читается). */
const EXIT_NAMES: Record<string, string> = {
  ext_parking: "подземная парковка",
  ext_supply_truck: "машина снабжения",
  ext_service_gate: "служебные ворота",
  ext_loading_dock: "роллета погрузочного дока",
};

/**
 * Контракты — причина идти в рейд не только за ₽. Перед рейдом даётся несколько
 * предложений, игрок берёт один. Хорошее задание использует системы уровня (питание,
 * замки, терминалы, конкретные помещения), а не «убей 14 мародёров». Награда — не
 * «+450 ₽ и два бинта», а доступ: товар у трейдера, ключ, знание выхода, разведданные,
 * репутация, шаг апгрейда убежища.
 */
export type ContractKind = "ledger" | "download" | "safe" | "bug" | "missing" | "weapon" | "inspect" | "parcel";

export interface ContractReward {
  reputation: number;
  money?: number;
  /** Позиция каталога трейдера становится доступна независимо от репутации. */
  unlockItem?: string;
  /** Предмет ложится на склад (ключ, карта). */
  grantItem?: string;
  /** Выход известен с брифинга во всех следующих рейдах. */
  knownExit?: string;
  /** Разведданные на следующий рейд (см. Intel). */
  intel?: "power" | "gate" | "raiders" | "cargo";
  /** Один шаг апгрейда убежища бесплатно (без денег и деталей). */
  upgradeStep?: UpgradeKey;
}

export interface ContractDef {
  id: string;
  kind: ContractKind;
  title: string;
  /** Что и где — как это сказал бы заказчик. */
  brief: string;
  /** Что должно лежать в рюкзаке при эвакуации. */
  requiredItem?: string;
  /** Где и в чём предмет спрятан (предмет подкладывается в контейнер одного из помещений). */
  plant?: { itemId: string; roomIds: string[] };
  /** Точка на уровне: удержать E столько-то секунд. */
  spot?: { roomIds: string[]; label: string; holdSec: number; requiresCircuit?: "service" | "retail" | "security"; loud?: boolean };
  /** Помеченный мародёр: с этим оружием, в этих помещениях; убить и вынести его ствол. */
  marked?: { weaponId: "svd_marksman" | "pump_shotgun"; requiredItem: string };
  /** Нужно ли выйти живым, чтобы контракт засчитался (всегда да, кроме чистой «прослушки»). */
  requiresExtraction: boolean;
  reward: ContractReward;
  repRequired: number;
}

export const CONTRACTS: ContractDef[] = [
  {
    id: "c_ledger",
    kind: "ledger",
    title: "Бухгалтерия «Кольца»",
    brief: "В офисах остались книги учёта — банк, администрация или спортивный. Найди папку с отчётностью и вынеси. Заказчику важно, чтобы её не видели другие.",
    requiredItem: "d_ledger_ring",
    plant: { itemId: "d_ledger_ring", roomIds: ["bank_office", "office_admin", "sport_office"] },
    requiresExtraction: true,
    reward: { reputation: 2, money: 600, unlockItem: "r_reddot" },
    repRequired: 0,
  },
  {
    id: "c_download",
    kind: "download",
    title: "Данные с поста",
    brief: "На посту видеонаблюдения стоит регистратор. Его надо запитать — охранный контур на щите — и слить архив: 35 секунд у терминала. Смена света в крыле кого-нибудь да привлечёт.",
    spot: { roomIds: ["security_control"], label: "Слить архив регистратора", holdSec: 35, requiresCircuit: "security" },
    requiresExtraction: true,
    reward: { reputation: 3, money: 900, knownExit: "ext_parking", intel: "power" },
    repRequired: 1,
  },
  {
    id: "c_safe",
    kind: "safe",
    title: "Сейф охраны",
    brief: "В сейфе поста охраны лежит досье. Пост под магнитными замками: карта доступа или обесточить охранный контур. Досье — мне, остальное из сейфа — тебе.",
    requiredItem: "d_dossier",
    plant: { itemId: "d_dossier", roomIds: ["security_post", "security_control"] },
    requiresExtraction: true,
    reward: { reputation: 2, grantItem: "k_service_gate", intel: "gate" },
    repRequired: 1,
  },
  {
    id: "c_bug",
    kind: "bug",
    title: "Прослушка",
    brief: "Мародёры собираются в комнате персонала и в банке. Поставь закладку под столом — восемь секунд, лучше без свидетелей — и уходи.",
    spot: { roomIds: ["staff_room", "bank_office"], label: "Установить закладку", holdSec: 8 },
    requiresExtraction: true,
    reward: { reputation: 2, intel: "raiders", unlockItem: "r_suppressor" },
    repRequired: 2,
  },
  {
    id: "c_missing",
    kind: "missing",
    title: "Пропавший",
    brief: "Кириллов не вернулся из сектора. Последний раз выходил на связь из кафе у входа. Найди его — или то, что осталось — и принеси жетон.",
    requiredItem: "d_tag_kirillov",
    plant: { itemId: "d_tag_kirillov", roomIds: ["cafe", "food_court", "kitchen"] },
    requiresExtraction: true,
    reward: { reputation: 2, money: 800, upgradeStep: "medicalModule" },
    repRequired: 0,
  },
  {
    id: "c_weapon",
    kind: "weapon",
    title: "Ствол стрелка",
    brief: "У одного из них марксманка, и он не расстаётся с ней. Сними его и принеси винтовку: у нас на неё покупатель.",
    marked: { weaponId: "svd_marksman", requiredItem: "w_marksman" },
    requiredItem: "w_marksman",
    requiresExtraction: true,
    reward: { reputation: 3, unlockItem: "w_marksman" },
    repRequired: 2,
  },
  {
    id: "c_inspect",
    kind: "inspect",
    title: "Осмотр дока",
    brief: "Нужно понять, работает ли восточный погрузочный двор: осмотри роллету склада изнутри и ворота. Пять секунд у роллеты — и фото у тебя в голове.",
    spot: { roomIds: ["warehouse"], label: "Осмотреть роллету и двор", holdSec: 5 },
    requiresExtraction: true,
    reward: { reputation: 1, knownExit: "ext_supply_truck", intel: "cargo" },
    repRequired: 0,
  },
  {
    id: "c_parcel",
    kind: "parcel",
    title: "Посылка",
    brief: "В холодильниках или на складе оставили посылку — коробка в четыре кило, не вскрывать. Забрать и вынести. За неё платят как за хороший рейд.",
    requiredItem: "d_parcel",
    plant: { itemId: "d_parcel", roomIds: ["freezer", "warehouse", "archive"] },
    requiresExtraction: true,
    reward: { reputation: 2, money: 1200, unlockItem: "ar_heavy_vest" },
    repRequired: 1,
  },
];

export function contractById(id: string | null | undefined): ContractDef | null {
  if (!id) return null;
  return CONTRACTS.find((c) => c.id === id) ?? null;
}

/** Три предложения на рейд: доступные по репутации, ещё не выполненные; порядок — от номера рейда. */
export function offerContracts(progress: MetaProgress): ContractDef[] {
  const done = new Set(progress.completedContracts);
  const pool = CONTRACTS.filter((c) => !done.has(c.id) && progress.reputation >= c.repRequired);
  const start = (progress.raidsCompleted + progress.raidsFailed) % Math.max(1, pool.length);
  const out: ContractDef[] = [];
  for (let i = 0; i < pool.length && out.length < 3; i++) out.push(pool[(start + i) % pool.length]);
  return out;
}

/** Награда — в прогресс. Возвращает строки для экрана итогов. */
export function applyReward(progress: MetaProgress, c: ContractDef): string[] {
  const lines: string[] = [];
  const r = c.reward;
  progress.reputation += r.reputation;
  lines.push(`репутация +${r.reputation}`);
  if (r.money) {
    progress.money += r.money;
    lines.push(`${r.money} ₽`);
  }
  if (r.unlockItem && !progress.unlockedItems.includes(r.unlockItem)) {
    progress.unlockedItems.push(r.unlockItem);
    lines.push(`у трейдера появилось: ${itemDef(r.unlockItem).name}`);
  }
  if (r.grantItem) {
    progress.stash.push({ itemId: r.grantItem, count: 1 });
    lines.push(`на склад: ${itemDef(r.grantItem).name}`);
  }
  if (r.knownExit && !progress.knownExits.includes(r.knownExit)) {
    progress.knownExits.push(r.knownExit);
    lines.push(`выход известен с брифинга: ${EXIT_NAMES[r.knownExit] ?? r.knownExit}`);
  }
  if (r.intel && !progress.intel.includes(r.intel)) {
    progress.intel.push(r.intel);
    lines.push("разведданные на следующий рейд");
  }
  if (r.upgradeStep) {
    // Шаг апгрейда — бесплатный уровень, но не выше потолка модуля.
    if (progress.upgrades[r.upgradeStep] < upgradeMaxLevel(r.upgradeStep)) {
      progress.upgrades[r.upgradeStep] += 1;
      lines.push(`убежище: ${UPGRADE_NAMES[r.upgradeStep]} +1 уровень`);
    } else {
      lines.push(`убежище: ${UPGRADE_NAMES[r.upgradeStep]} уже на максимуме`);
    }
  }
  if (!progress.completedContracts.includes(c.id)) progress.completedContracts.push(c.id);
  return lines;
}
