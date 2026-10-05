"""Сводка проверок убежища из локальных stdout/stderr без скрытия предупреждений."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "docs/shelter/validation"
CASES = {
    "solo_acceptance": ("acceptance-final", "SHELTER_ACCEPTANCE failures=0"),
    "compile": ("compile_check-final", "compile_check: не собралось 0"),
    "cart_regression": ("cart-regression", "cart_test: провалено 0"),
    "loadout_raid_return": ("loadout", "loadout_test: провалено 0"),
    **{f"coop_{role}": (f"net-{role}", f"SHELTER_NET {role} failures=0") for role in ["host", "c1", "c2"]},
    **{f"raid_regression_{role}": (f"coop-raid-{role}", f"coop_raid[{role}]: провалено 0") for role in ["host", "c1", "c2"]},
    "events_regression": ("events_test-final", "events_test: провалено"),
    "weather_regression": ("weather_test-final", "weather_test: провалено"),
    "events_baseline": ("events_test-baseline", "events_test: провалено"),
    "weather_baseline": ("weather_test-baseline", "weather_test: провалено"),
    "events_initial": ("events_test-initial", "events_test: провалено"),
    "weather_initial": ("weather_test-initial", "weather_test: провалено"),
    "revision_jump": ("jump_test", "JUMP_TEST checks=30 failures=0"),
    "revision_compile": ("visual_revision_compile", "compile_check: не собралось 0"),
    "revision_acceptance": ("visual_revision_acceptance", "SHELTER_ACCEPTANCE failures=0"),
    "revision_cart": ("visual_revision_cart", "cart_test: провалено 0"),
    "revision_settings": ("visual_revision_settings", "settings_test: провалено 0"),
    "revision_animation": ("visual_revision_anim", "anim_test: провалено 0"),
    **{f"revision_coop_{role}": (f"visual_revision_net_{role}", f"SHELTER_NET {role} failures=0") for role in ["host", "c1", "c2"]},
}


def read_log(path: Path) -> str:
    data = path.read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return data.decode(encoding, errors="replace")


def read_case(stem: str, terminator: str) -> dict:
    output = read_log(LOGS / f"{stem}.log")
    errors_path = LOGS / f"{stem}.errors.log"
    if not errors_path.exists():
        errors_path = LOGS / f"{stem}.err.log"
    errors = read_log(errors_path) if errors_path.exists() else ""
    # Некоторые прежние прогоны сохраняли stderr вместе с stdout.
    lines = (output + "\n" + errors).splitlines()
    evidence = [line for line in lines if re.search(r"\[(ok|FAIL)\]", line) or terminator in line]
    warnings = sorted(set(line for line in lines if line.startswith("WARNING:")))
    engine_errors = sorted(set(line for line in lines if line.startswith(("ERROR:", "SCRIPT ERROR:"))))
    return {
        "completed": terminator in output,
        "checks_passed": sum("[ok]" in line for line in lines),
        "checks_failed": sum("[FAIL]" in line for line in lines),
        "evidence": evidence,
        "warnings": warnings,
        "engine_errors": engine_errors,
        "source_logs": [f"{stem}.log"] + ([errors_path.name] if errors_path.exists() else []),
    }


def main() -> None:
    result = {name: read_case(*case) for name, case in CASES.items()}
    for name, case in result.items():
        if not case["completed"]:
            raise RuntimeError(f"Незавершённый прогон: {name}")
        if not name.endswith(("_initial", "_baseline")):
            if case["checks_failed"]:
                raise RuntimeError(f"Провалена финальная проверка: {name}")
            unexpected = [line for line in case["engine_errors"] if line != 'ERROR: Parameter "material" is null.']
            if unexpected:
                raise RuntimeError(f"Ошибка движка {name}: {unexpected}")
    result["baseline_control"] = json.loads((LOGS / "baseline_regression.json").read_text(encoding="utf-8"))
    (LOGS / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, case in result.items():
        if "checks_passed" in case:
            print(f"{name}: {case['checks_passed']} passed, {case['checks_failed']} failed, {len(case['engine_errors'])} engine error kinds")


if __name__ == "__main__":
    main()
