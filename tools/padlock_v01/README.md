# Padlock source workflow

Geometry was accepted on 2026-10-26; the Painter texture candidate is ready for visual review.
Do not regenerate or replace the accepted geometry master to make texture changes.
User deliverables: `E:/Models Blender/PROPS/Padlock_01/`.
Working source: `_asset_src/padlock_v01/` (ignored by Git).

- `build.py` builds the parametric geometry; `audit.py` adapts the skill audit's small-polygon tessellation calculation.
- `prepare_texture.py` copies the accepted evaluated surface, unwraps it and exports the Painter FBX.
- `mask_assets.py` creates placement fields from owner alphas; `bake_coverage.py` bakes those fields to the UV atlas.
- `painter.py launch` starts a separate Painter instance and queue. The bridge and generic helpers are in `tools/vss_m_v8`.
- `painter.py tools/padlock_v01/sp_open.py` reopens the saved padlock; wait for `sp_jobs/_reopened.txt`.
- `sp_create.py` and `sp_bake.py` are first-creation steps, not needed to change the layer recipe.
- `sp_layers.py` is the native editable layer recipe; run `sp_apply.py` through the task's bridge to save SPP and export three PNG maps.
- `sp_verify.py` checks a reopened SPP and closes its project; `sp_quit.py` then quits the empty task instance.
- Run `preview_textured.py -- --save-only` in background Blender to save the textured candidate.
- Run `verify_textured.py` in background Blender to reopen the actual saved file, compare with the master and render review views.
- `verify_textured.py -- --side-light --views front_34,keyhole_close` checks another light direction.
- `deliver.py` copies a whitelist and verifies every SHA-256; `--verify-only` performs no writes.

Blender: `D:/ПРОГРАММЫ/Blender 5/blender.exe`, 5.2.2 LTS.
Painter: `D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/Adobe Substance 3D Painter.exe`, 12.1.0.
Python mask scripts require NumPy and Pillow, available in the bundled Codex dependency Python.
Use sequential Painter, bake and render phases to avoid exhausting RAM/VRAM in a shared workstation.

The dense UV copy is not a low-poly game export. Texture appearance is a review candidate;
the stamp is an intentionally non-verbal approximation of an illegible reference.
