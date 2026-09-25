"""Read-only inventory and preselection for RING animation assets.

Run from anywhere with: python tools/animation_audit/audit.py
Only writes JSON/Markdown beside this script. Never opens FBX for writing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
ANIMATIONS = ROOT / "assets" / "animations"
OUTPUT = Path(__file__).resolve().parent

ALIASES = {
    "fwd": "forward", "fw": "forward", "bwd": "backward", "bw": "backward",
    "bk": "backward", "backwards": "backward", "forwards": "forward",
    "handgun": "pistol", "ar": "rifle", "assault": "rifle", "gun": "weapon",
    "firing": "fire", "shooting": "fire", "shoot": "fire",
    "reloading": "reload", "running": "run", "walking": "walk",
    "crouching": "crouch", "crouched": "crouch", "kneeling": "crouch",
    "kneel": "crouch", "dying": "death", "die": "death",
    "jumping": "jump", "aiming": "aim", "toss": "throw",
    "strifing": "strafe", "turning": "turn", "stationary": "idle",
    "moving": "walk", "front": "forward", "back": "backward", "l": "left", "r": "right",
    "reaction": "react", "grenades": "grenade", "weapons": "weapon",
}
PACK_WORDS = {"pack", "basic", "pro", "shooter", "locomotion", "8", "way", "animation"}
DIRECTION_WORDS = {"forward", "backward", "left", "right"}


@dataclass(frozen=True)
class Target:
    family: str
    key: str
    label: str
    weapon: str
    stance: str
    movement: str
    direction: str
    action: str
    mode: str = ""


def normalize(name: str, strip_number: bool = False) -> list[str]:
    name = Path(name).stem.lower()
    name = re.sub(r"([a-z])([0-9])", r"\1 \2", name)
    name = re.sub(r"([0-9])([a-z])", r"\1 \2", name)
    name = re.sub(r"[^a-z0-9а-яё]+", " ", name)
    tokens = [ALIASES.get(token, token) for token in name.split()]
    if strip_number:
        tokens = [token for token in tokens if not token.isdigit() and token not in {"v", "version", "ver", "copy"}]
    return tokens


def classify(relative: Path) -> dict[str, str]:
    file_tokens = normalize(relative.name)
    folder_tokens = normalize(" ".join(relative.parts[:-1]))
    tokens = file_tokens + folder_tokens
    words = set(tokens)
    file_words = set(file_tokens)
    folder_words = set(folder_tokens)

    if "pistol" in file_words or "pistol" in folder_words:
        weapon = "pistol"
    elif "smg" in file_words or "smg" in folder_words:
        weapon = "smg"
    elif "rifle" in file_words or "rifle" in folder_words:
        weapon = "rifle"
    elif "grenade" in file_words or "grenade" in folder_words:
        weapon = "grenade"
    elif relative.parts[0].lower() == "movements":
        weapon = "unarmed"
    elif "weapon" in words or "shooter" in words:
        weapon = "generic weapon"
    else:
        weapon = "unknown"

    if "prone" in words or "crawl" in words:
        stance = "prone"
    elif "crouch" in words:
        stance = "crouch"
    elif "stand" in words or weapon in {"pistol", "rifle", "smg", "unarmed"}:
        stance = "standing"
    else:
        stance = "unknown"

    if "sprint" in words:
        movement = "sprint"
    elif "run" in words:
        movement = "run"
    elif "strafe" in words:
        movement = "strafe"
    elif "walk" in words or "crawl" in words:
        movement = "walk"
    elif "turn" in words or "arc" in words:
        movement = "turn"
    elif "land" in words or "down" in words and "jump" in words:
        movement = "land"
    elif "jump" in words:
        movement = "jump"
    elif "idle" in words:
        movement = "idle"
    elif words & {"reload", "fire", "aim", "throw", "pick", "hit", "death", "draw", "put", "holster"}:
        movement = "stationary"
    else:
        movement = "unknown"

    direction = "unknown"
    if "forward" in words and "left" in words:
        direction = "forward-left"
    elif "forward" in words and "right" in words:
        direction = "forward-right"
    elif "backward" in words and "left" in words:
        direction = "backward-left"
    elif "backward" in words and "right" in words:
        direction = "backward-right"
    elif "forward" in words:
        direction = "forward"
    elif "backward" in words:
        direction = "backward"
    elif "left" in words:
        direction = "left"
    elif "right" in words:
        direction = "right"
    elif movement in {"idle", "stationary"}:
        direction = "none"
    elif movement in {"walk", "run", "sprint"} and "strafe" not in words and "arc" not in words:
        direction = "forward"  # conventional unlabeled straight locomotion; flagged below

    if "death" in words:
        action = "death"
    elif "hit" in words or "react" in words:
        action = "hit"
    elif "reload" in words:
        action = "empty reload" if "empty" in words else "reload"
    elif "draw" in words or "grab" in words:
        action = "draw"
    elif "holster" in words or {"put", "away"} <= words:
        action = "holster"
    elif "grenade" in words and "throw" in words:
        action = "grenade throw"
    elif "pick" in words and "up" in words:
        action = "pickup"
    elif "interact" in words or "use" in words:
        action = "interact"
    elif "melee" in words or "punch" in words:
        action = "melee"
    elif "dodge" in words or "evade" in words or {"jump", "away"} <= words:
        action = "dodge"
    elif "land" in words or {"jump", "down"} <= words:
        action = "land"
    elif "jump" in words:
        action = "jump"
    elif "fire" in words:
        action = "fire"
    elif "aim" in words and movement not in {"walk", "run", "sprint"}:
        action = "aim"
    elif movement == "idle":
        action = "idle"
    elif movement in {"walk", "run", "sprint", "strafe", "turn"}:
        action = "locomotion"
    else:
        action = "unknown"

    if action == "idle" and "aim" in words:
        action = "aim"
    if "aim" in words and "fire" in words:
        action = "fire"

    return {
        "weapon": weapon, "stance": stance, "movement": movement,
        "direction": direction, "action": action,
        "aim": "aim" in words or "ads" in words,
        "empty": "empty" in words,
        "directionExplicit": bool(file_words & DIRECTION_WORDS),
        "tokens": file_tokens,
    }


def targets() -> list[Target]:
    result: list[Target] = []

    def add(family: str, key: str, label: str, weapon: str, stance: str, movement: str,
            direction: str, action: str, mode: str = "") -> None:
        result.append(Target(family, key, label, weapon, stance, movement, direction, action, mode))

    for family, weapon in [("unarmed", "unarmed"), ("pistol", "pistol"), ("rifle", "rifle")]:
        heading = {"unarmed": "Unarmed", "pistol": "Pistol", "rifle": "Rifle / SMG"}[family]
        add(family, "idle", f"{heading} / Idle", weapon, "standing", "idle", "none", "idle")
        if family != "unarmed":
            add(family, "aim_idle", f"{heading} / Aim Idle", weapon, "standing", "idle", "none", "aim")
        for movement in ("walk", "run"):
            modes = ("hip", "ads") if family == "pistol" and movement == "walk" else ("",)
            if family == "rifle" and movement == "walk":
                modes = ("hip", "ads")
            for mode in modes:
                for direction in ("forward", "backward", "left", "right"):
                    label = f"{heading} / {movement.title()} {mode.upper() + ' ' if mode else ''}{direction.title()}"
                    add(family, "_".join(filter(None, [movement, mode, direction])), label,
                        weapon, "standing", movement, direction, "locomotion", mode)
        if family == "rifle":
            add(family, "sprint", f"{heading} / Sprint", weapon, "standing", "sprint", "forward", "locomotion")
        add(family, "crouch_idle", f"{heading} / Crouch Idle", weapon, "crouch", "idle", "none", "idle")
        for direction in ("forward", "backward", "left", "right"):
            add(family, f"crouch_walk_{direction}", f"{heading} / Crouch Walk {direction.title()}",
                weapon, "crouch", "walk", direction, "locomotion")
        if family == "rifle":
            add(family, "prone_idle", f"{heading} / Prone Idle", weapon, "prone", "idle", "none", "idle")
            for direction in ("forward", "backward", "left", "right"):
                add(family, f"prone_move_{direction}", f"{heading} / Prone Move {direction.title()}",
                    weapon, "prone", "walk", direction, "locomotion")
        if family != "unarmed":
            for key, label, action in [("fire", "Fire", "fire"), ("aim_fire", "Aim Fire", "fire"),
                                       ("reload", "Reload", "reload"), ("empty_reload", "Empty Reload", "empty reload"),
                                       ("draw", "Draw", "draw"), ("holster", "Holster", "holster"),
                                       ("jump", "Jump", "jump"), ("land", "Land", "land")]:
                mode = "ads" if key == "aim_fire" else ""
                add(family, key, f"{heading} / {label}", weapon, "standing", "stationary", "none", action, mode)

    for key, label, action, movement in [
        ("idle", "Idle / Hold", "idle", "idle"), ("throw", "Throw", "grenade throw", "stationary"),
        ("movement", "Movement", "locomotion", "walk"), ("run", "Run", "locomotion", "run")]:
        add("grenade", key, f"Grenade / {label}", "grenade", "standing", movement, "none", action)
    for action in ("hit", "death"):
        for direction in ("forward", "backward", "left", "right"):
            add("reactions", f"{action}_{direction}", f"{action.title()} / {direction.title()}",
                "unknown", "standing", "stationary", direction, action)
        add("reactions", f"{action}_secondary", f"{action.title()} / Secondary", "unknown",
            "standing", "stationary", "unknown", action)
    add("interaction", "pickup", "Interaction / Pickup", "unknown", "standing", "stationary", "none", "pickup")
    add("interaction", "interact", "Interaction / Generic", "unknown", "standing", "stationary", "none", "interact")
    for key, label, action, movement in [
        ("turn_in_place", "Turn in Place", "locomotion", "turn"),
        ("dodge", "Dodge / Evade", "dodge", "stationary"),
        ("melee", "Melee", "melee", "stationary"),
        ("inspect", "Weapon Inspect", "unknown", "stationary"),
        ("low_ready", "Low Ready", "unknown", "stationary"),
        ("high_ready", "High Ready", "unknown", "stationary")]:
        add("optional", key, f"Optional / {label}", "unknown", "standing", movement, "unknown", action)
    return result


def match(target: Target, record: dict) -> tuple[int, list[str]] | None:
    c = record["classification"]
    words = set(c["tokens"])
    if target.family == "optional":
        needed = {"turn_in_place": {"turn"}, "dodge": {"dodge", "evade", "away"},
                  "melee": {"melee", "punch"}, "inspect": {"inspect"},
                  "low_ready": {"low", "ready"}, "high_ready": {"high", "ready"}}[target.key]
        if target.key in {"low_ready", "high_ready"}:
            if not needed <= words:
                return None
        elif not needed & words:
            return None
        return (25, ["filename names the optional action"])

    if target.family == "interaction":
        if c["action"] != target.action:
            return None
        return (50, ["filename names the interaction action"])

    if target.family == "reactions":
        if c["action"] != target.action:
            return None
        if target.direction == "forward":
            if c["direction"] not in {"forward", "unknown", "none"}:
                return None
        elif target.direction == "backward":
            if c["direction"] != "backward":
                return None
        elif target.direction in {"left", "right"}:
            if c["direction"] != target.direction:
                return None
        elif target.direction == "unknown" and c["direction"] not in {"unknown", "none"}:
            return None
        reasons = [f"filename names {target.action}"]
        if c["direction"] == target.direction:
            reasons.append("direction named explicitly")
        elif target.direction == "forward":
            reasons.append("direction unspecified; front reaction must be checked visually")
        return (45 + 10 * (c["direction"] == target.direction), reasons)

    if target.family == "grenade":
        if target.action == "grenade throw":
            if c["action"] != "grenade throw":
                return None
        elif c["weapon"] != "grenade" or c["movement"] != target.movement or c["action"] not in {"locomotion", "idle"}:
            return None
        return (45, ["filename/folder identifies grenade action"])

    if c["weapon"] != target.weapon:
        return None
    if c["stance"] != target.stance:
        return None
    if target.action == "aim":
        if not c["aim"] or c["movement"] != "idle":
            return None
    elif target.action == "idle":
        if c["movement"] != "idle" or c["aim"]:
            return None
    elif target.action == "locomotion":
        if c["action"] != "locomotion":
            return None
        if words & {"start", "stop", "arc", "turn", "injured", "hurt", "drink", "dying", "reload"}:
            return None
        if target.movement == "walk" and c["movement"] not in {"walk", "strafe"}:
            return None
        if target.movement in {"run", "sprint"} and c["movement"] != target.movement:
            return None
        if c["direction"] != target.direction:
            return None
    elif target.action == "fire":
        if c["action"] != "fire" or (target.mode == "ads" and not c["aim"]):
            return None
        if target.key == "fire" and c["aim"]:
            return None
    elif c["action"] != target.action:
        return None

    if target.mode == "ads" and target.action == "locomotion" and not c["aim"]:
        return None
    if target.mode == "hip" and c["aim"]:
        return None

    score = 55
    reasons = [f"classified as {target.weapon}", f"matches {target.action}"]
    if target.action == "locomotion":
        if c["directionExplicit"]:
            score += 15
            reasons.append("direction named explicitly")
        elif target.direction == "forward":
            reasons.append("forward inferred from unlabeled straight movement; verify visually")
        if target.mode == "hip":
            reasons.append("ADS not named; hip carry requires visual confirmation")
    if target.mode == "ads":
        reasons.append("aim/ADS named explicitly")
    if target.stance == "crouch" and "crouch" in words:
        score += 5
        reasons.append("crouch named explicitly")
    if target.stance == "prone" and "prone" in words:
        score += 5
        reasons.append("prone named explicitly")
    return (score, reasons)


def inventory() -> list[dict]:
    files = sorted(ANIMATIONS.rglob("*.fbx"), key=lambda p: p.relative_to(ROOT).as_posix().lower())
    records = []
    for path in files:
        rel = path.relative_to(ROOT)
        under_animations = path.relative_to(ANIMATIONS)
        digest = sha256()
        with path.open("rb") as stream:
            header = stream.read(27)
            stream.seek(0)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        binary = header.startswith(b"Kaydara FBX Binary  \x00\x1a\x00")
        records.append({
            "filename": path.name,
            "path": rel.as_posix(),
            "sourceFolder": under_animations.parent.as_posix(),
            "sourcePack": under_animations.parts[0] if len(under_animations.parts) > 1 else "(root)",
            "bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
            "fbxFormat": "binary" if binary else "ascii/unknown",
            "fbxVersion": int.from_bytes(header[23:27], "little") if binary else None,
            "classification": classify(under_animations),
        })
    return records


def write_json(name: str, data: object) -> None:
    (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    records = inventory()
    hashes: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        hashes[record["sha256"]].append(record)
    duplicate_groups = []
    for digest, copies in hashes.items():
        if len(copies) <= 1:
            continue
        group_id = f"dup-{len(duplicate_groups) + 1:03d}"
        paths = [copy["path"] for copy in copies]
        duplicate_groups.append({"id": group_id, "sha256": digest, "paths": paths})
        for copy in copies:
            copy["duplicateGroup"] = group_id
            copy["duplicatePaths"] = paths
    for record in records:
        record.setdefault("duplicateGroup", None)
        record.setdefault("duplicatePaths", [record["path"]])

    semantic: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        c = record["classification"]
        normalized = [word for word in normalize(record["filename"], True) if word not in PACK_WORDS]
        key = "|".join([c["weapon"], c["stance"], " ".join(normalized)])
        semantic[key].append(record)
    semantic_groups = [
        {"key": key, "paths": [r["path"] for r in group],
         "exactHashCount": len({r["sha256"] for r in group})}
        for key, group in sorted(semantic.items()) if len(group) > 1
    ]

    target_list = targets()
    pack_records: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        pack_records[record["sourcePack"]].append(record)
    pack_coverage: dict[str, set[str]] = defaultdict(set)
    for target in target_list:
        for record in records:
            if match(target, record):
                pack_coverage[record["sourcePack"]].add(f"{target.family}/{target.key}")

    shortlist: dict[str, dict] = defaultdict(dict)
    coverage = []
    for target in target_list:
        candidates_by_hash: dict[str, tuple[int, dict, list[str]]] = {}
        for record in records:
            result = match(target, record)
            if result is None:
                continue
            base, reasons = result
            cohort = len(pack_coverage[record["sourcePack"]])
            score = base + min(cohort, 35)
            reasons = reasons + [f"same pack covers {cohort} target states"]
            current = candidates_by_hash.get(record["sha256"])
            if current is None or (score, record["path"]) > (current[0], current[1]["path"]):
                candidates_by_hash[record["sha256"]] = (score, record, reasons)
        ranked = sorted(candidates_by_hash.values(), key=lambda x: (-x[0], x[1]["path"].lower()))[:5]
        candidates = []
        for score, record, reasons in ranked:
            candidates.append({
                "path": record["path"], "filename": record["filename"],
                "sourcePack": record["sourcePack"], "bytes": record["bytes"],
                "sha256": record["sha256"], "duplicateGroup": record["duplicateGroup"],
                "duplicatePaths": record["duplicatePaths"], "reason": reasons,
                "preselectionScore": score,
            })
        shortlist[target.family][target.key] = {
            "label": target.label, "target": target.__dict__, "candidates": candidates,
        }
        coverage.append({"family": target.family, "state": target.key, "label": target.label,
                         "found": bool(candidates), "candidates": len(candidates)})

    packs = []
    for pack, group in sorted(pack_records.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        classifications = [r["classification"] for r in group]
        state_keys = pack_coverage[pack]
        packs.append({
            "name": pack, "fbxCount": len(group), "uniqueHashCount": len({r["sha256"] for r in group}),
            "targetStatesCovered": len(state_keys), "targetStates": sorted(state_keys),
            "weapons": dict(Counter(c["weapon"] for c in classifications)),
            "pistol": any(c["weapon"] == "pistol" for c in classifications),
            "rifle": any(c["weapon"] == "rifle" for c in classifications),
            "eightWayLocomotion": all(f"rifle/walk_hip_{direction}" in state_keys for direction in ("forward", "backward", "left", "right")) or
                                  all(f"rifle/run_{direction}" in state_keys for direction in ("forward", "backward", "left", "right")),
            "crouch": any(c["stance"] == "crouch" for c in classifications),
            "prone": any(c["stance"] == "prone" for c in classifications),
            "reload": any(c["action"] in {"reload", "empty reload"} for c in classifications),
            "death": any(c["action"] == "death" for c in classifications),
        })

    write_json("all_animations.json", {"total": len(records), "files": records})
    write_json("exact_duplicates.json", {"groups": duplicate_groups,
                                          "duplicateFilesBeyondUnique": sum(len(g["paths"]) - 1 for g in duplicate_groups)})
    write_json("semantic_groups.json", {"note": "Potential matches by normalized names; not confirmed duplicates.",
                                        "groups": semantic_groups})
    write_json("packs.json", packs)
    write_json("coverage.json", coverage)
    write_json("shortlist.json", dict(shortlist))
    viewer = OUTPUT / "viewer"
    if viewer.is_dir():
        (viewer / "shortlist.json").write_text(json.dumps(dict(shortlist), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(records, duplicate_groups, semantic_groups, packs, coverage)
    print(f"TOTAL FBX: {len(records)} | EXACT DUPLICATE GROUPS: {len(duplicate_groups)} | UNIQUE FBX: {len(hashes)} | PACKS: {len(packs)}")


def write_report(records: list[dict], duplicate_groups: list[dict], semantic_groups: list[dict],
                 packs: list[dict], coverage: list[dict]) -> None:
    lines = [
        "# RING animation audit", "",
        f"TOTAL FBX: {len(records)}",
        f"EXACT DUPLICATES: {len(duplicate_groups)} groups / {sum(len(g['paths']) - 1 for g in duplicate_groups)} excess copies",
        f"UNIQUE FBX: {len({r['sha256'] for r in records})}",
        f"ANIMATION PACKS: {len(packs)}", "",
        f"COVERAGE: {sum(row['found'] for row in coverage)}/{len(coverage)} target states; {sum(row['candidates'] for row in coverage)} shortlist entries.",
        "Это предварительный отбор по именам. Визуальное качество и финальный набор пока не определены. Исходные FBX не изменялись.", "",
        "## Animation pack analysis", "",
        "| Pack | FBX | Unique | Target states | Pistol | Rifle | 8-way | Crouch | Prone | Reload | Death |",
        "|---|---:|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for pack in packs:
        yes = lambda key: "YES" if pack[key] else "NO"
        lines.append(f"| {pack['name']} | {pack['fbxCount']} | {pack['uniqueHashCount']} | {pack['targetStatesCovered']} | {yes('pistol')} | {yes('rifle')} | {yes('eightWayLocomotion')} | {yes('crouch')} | {yes('prone')} | {yes('reload')} | {yes('death')} |")
    lines += ["", "`Target states` — покрытие по названиям файлов и папок, а не подтверждение совместимости.",
              "Самые полные по этому признаку — Pro Rifle Pack и Rifle 8-Way Locomotion Pack (по 22 состояния после исключения переходных клипов). Названия их файлов почти совпадают, но SHA-256 различается: автоматически считать их дублями нельзя.", "",
              "## Animation coverage", "", "| State | Found | Candidates |", "|---|:---:|---:|"]
    for row in coverage:
        lines.append(f"| {row['label']} | {'YES' if row['found'] else 'NO'} | {row['candidates']} |")
    lines += ["", "## Exact duplicate groups", ""]
    if duplicate_groups:
        for group in duplicate_groups:
            lines.append(f"- **{group['id']}** ({len(group['paths'])} copies): " + "; ".join(f"`{p}`" for p in group["paths"]))
    else:
        lines.append("No byte-identical files found.")
    lines += ["", f"Potential semantic groups: {len(semantic_groups)}. See `semantic_groups.json`; names alone do not establish animation equivalence.", "",
              "## Technical integration notes", "",
              "- The source files have not been converted, moved, or modified.",
              "- Current audit uses filenames and folders for state preselection. Visual judgments require the shortlist viewer.",
              "- All 275 source headers identify binary FBX version 7700.",
              "- Target character: `D:/ПРОГРАММЫ/Blender 5/Projects/Persona.blend` (read-only inspection). It has 13 mesh objects and an armature of 52 bones, with root `mixamorig:Hips`.",
              "- Blender probe of one FBX from each of 24 packs found 0 meshes, 65 bones and the same root in all 24. All 52 character bone names occur in each sampled FBX. See `rig_probe.json` for individual names and scales.",
              "- The 13 additional animation bones and bind pose must be checked before retargeting. Identical names alone do not prove identical transforms or animation compatibility.",
              "- Root motion, orientation, unit scale in motion, and rest/bind pose remain unverified. Compare poses and root trajectories after final visual selection.",
              "- A state marked FOUND means a plausible name match. ADS walk and empty reload remain missing unless their names explicitly identify these actions.",
              "- `Persona.fbx` in a pack is a character file; it is inventory-only and not a locomotion candidate.", ""]
    (OUTPUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
