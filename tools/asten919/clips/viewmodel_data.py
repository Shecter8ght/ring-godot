"""АСТЕН-919 (wpn_hg_02): данные игры по выведенным клипам рук (отчёт assets/models/weapons/asten919/asten919_viewmodel.json,
его пишет tools/asten919/clips/export_viewmodel.py) → data/weapons.json:

  weapon.viewmodel — сцена рук с клипами, роли клипов (ViewmodelClips), кадры фаз из меток владельца: подмена магазина
    (swap_frame — mag_hidden; у быстрой — с начала: новый магазин уже в левой), сброс старого (drop_frame — mag_out),
    удержание проверки (check_hold — hold_start…hold_end), затвор остаётся на задержке после последнего выстрела
    (shot_slide_back — slide_back клипа Fire), кадры остановки осмотра (inspect_hold — левый и правый бок);
  weapon.rig.reload / rig.reload_empty — доли фаз модели в руках персонажа и звуков перезарядки по умолчанию: у неполной —
    по Reload_Tactical, у полной — по Reload_Full (рычаг задержки — charge).

  weapon.stats.reload / reload_empty — время перезарядки = длина клипов Reload_Tactical / Reload_Full, делённая на
    RELOAD_SPEED (владелец 2026-11-14: сначала «по клипам», затем «клип слишком медлительный» — клип идёт быстрее
    записи во столько раз; стресс и магазин из рюкзака удлиняют как раньше).
  Затвор после последнего патрона всегда встаёт на задержку (и без магазина — решение владельца) и держится на ней
  во всех клипах до кадра slide_release (рычаг отпускает); пистолет на задержке убрали или сменили — затвор отпущен
  на пустой патронник, полная перезарядка — Reload_Full_Rack (вставить и передёрнуть, stats.reload_empty_rack).

python -X utf8 tools/asten919/clips/viewmodel_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEAPONS = ROOT / "data/weapons.json"
REPORT = ROOT / "assets/models/weapons/asten919/asten919_viewmodel.json"
WID = "wpn_hg_02"
ROLES = {"idle": "idle", "reload": "reload_tactical", "reload_empty": "reload_full", "reload_fast": "reload_fast",
         "reload_fast_empty": "reload_fast_full", "check": "mag_check", "clear": "jam_clear", "inspect": "inspect",
         "shot": "fire", "reload_empty_rack": "reload_full_rack"}
# выведены, но у игры для них нет случая (см. docs/STATUS.md): передёрнуть отдельно, палец на спуск
SPARE = ["slide_rack", "finger_to_trigger"]
RELOAD_SPEED = 1.4         # перезарядка в игре быстрее записи клипов во столько раз (владелец 2026-11-14: «слишком медлительный»)
SHOT_FAST_K = 3.0          # ход затвора и вылет гильзы в клипе выстрела — во столько раз быстрее записи (владелец 2026-11-14)
INSPECT_HOLD = [35, 126]   # ракурсы в выгруженном клипе; старые метки правого бока остались у начала поворота


def phases(clip, charge=None):
    n = float(clip["frames"])
    m = clip["marks"]
    out = {k: round(m[k] / n, 3) for k in ("catch", "mag_out", "mag_hidden", "mag_new", "mag_in") if k in m}
    if charge is not None:
        out["charge"] = round(charge / n, 3)
        out["charge_end"] = round(min(charge + 3, n) / n, 3)
    return out


def main():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    clips = rep["clips"]
    d = json.loads(WEAPONS.read_text(encoding="utf-8"))
    w = d["weapons"][WID]["weapon"]
    tac, full = clips["reload_tactical"], clips["reload_full"]
    fast, fast_full = clips["reload_fast"], clips["reload_fast_full"]
    rack = clips["reload_full_rack"]
    fire = clips["fire"]["marks"]
    case = rep.get("fire_case_frames", [])
    check = clips["mag_check"]["marks"]
    vm = {
        "scene": "res://assets/models/weapons/asten919/asten919_viewmodel.gltf",
        "fps": rep["fps"],
        "clips": ROLES,
        "check_hold": [check["hold_start"], check["hold_end"]],
        "swap_frame": {"reload_tactical": tac["marks"]["mag_hidden"], "reload_full": full["marks"]["mag_hidden"],
                       "reload_full_rack": rack["marks"]["mag_hidden"], "reload_fast": 0, "reload_fast_full": 0},
        "slide_release": {"reload_full": full["marks"]["slide_release"],
                          "reload_fast_full": fast_full["marks"]["slide_release"]},
        "drop_frame": {"reload_fast": fast["marks"]["mag_out"], "reload_fast_full": fast_full["marks"]["mag_out"]},
        "jam_open": rep.get("jam_open", 0.3),
        "inspect_hold": INSPECT_HOLD,
        "hold_open": True,
        "hands_fixed": True,
        "muzzle_own": True,
        "shot_slide_back": fire.get("slide_back", 0),
        "shot_start": fire.get("press", 0),
        "shot_fast": [fire.get("press", 0), max(fire.get("reset", 0), case[-1] if case else 0), SHOT_FAST_K],
        "ads_from_pose": True,
        "ads_z": (w.get("viewmodel", {}) or {}).get("ads_z", 0.36),
        "hip_offset": (w.get("viewmodel", {}) or {}).get("hip_offset", [0, 0, 0]),
        "spare_clips": SPARE,
    }
    w["viewmodel"] = vm
    rig = w.setdefault("rig", {})
    slide_full = full["marks"].get("slide_release", full["frames"] - 10)
    rig["reload"] = dict(phases(tac), **{k: v for k, v in phases(full, slide_full).items() if k.startswith("charge")})
    rig["reload_empty"] = phases(full, slide_full)
    stats = w["stats"]
    stats["reload"] = round(tac["seconds"] / RELOAD_SPEED, 2)
    stats["reload_empty"] = round(full["seconds"] / RELOAD_SPEED, 2)
    stats["reload_empty_rack"] = round(rack["seconds"] / RELOAD_SPEED, 2)
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ASTEN919_VM_DATA", json.dumps({"viewmodel": vm, "reload": rig["reload"], "reload_empty": rig["reload_empty"]},
                                         ensure_ascii=False))


if __name__ == "__main__":
    main()
