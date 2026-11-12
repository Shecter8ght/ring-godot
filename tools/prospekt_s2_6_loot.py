"""«Ярус», редакция 3: подгонка новых мест ящиков по физике и навигации (tools/prospekt_loot_snap.tscn).

  python -X utf8 tools/prospekt_s2_6_loot.py cands <кандидаты.json>      — список точек для prospekt_loot_snap
  python -X utf8 tools/prospekt_s2_6_loot.py apply <подогнанные.json>    — пишет tools/prospekt_s2_6_loot.json {ящик: [x, z, пол]}
После — python -X utf8 tools/prospekt_patch.py s2_6_yarus_r3 (сдвинет ящики в плане и сцене).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospekt_s2_6_data as D  # noqa: E402

names = list(D.LOOT_MOVES)
if sys.argv[1] == "cands":
    out = [{"id": i, "x": D.LOOT_MOVES[n][1][0], "z": D.LOOT_MOVES[n][1][1], "y": D.LOOT_MOVES[n][1][2]} for i, n in enumerate(names)]
    Path(sys.argv[2]).write_text(json.dumps(out), encoding="utf-8")
    print(len(out), "кандидатов")
else:
    snapped = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    res = {}
    for s in snapped:
        n = names[int(s["id"])]
        if not s["ok"]:
            print("НЕ ПОДОШЛО", n, s["why"], D.LOOT_MOVES[n][1])
            continue
        res[n] = [round(float(s["x"]), 3), round(float(s["z"]), 3), round(float(s["y"]), 3)]
        if float(s.get("moved", 0)) > 0:
            print("сдвинут", n, D.LOOT_MOVES[n][1][:2], "->", res[n], s.get("why"))
    D.SNAP.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("записано", len(res), "из", len(names))
