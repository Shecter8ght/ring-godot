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

## Contact/finish revision v03

- `contact_masks_png.py prepare` preserves baseline hashes and copies the owner's edge alpha.
- Run `contact_masks.py` in Blender, then `contact_masks_png.py png` in NumPy/Pillow Python.
- Open the project with `painter.py .../sp_open.py --revision v03`; a missing v03 starts from v02.
- Run `sp_refine_v03.py` through the bridge with `--revision v03 --wait-for _v03_ready.txt`.
  It preserves the 18 original layers, replaces only its own seven additions and saves a separate SPP/maps.
- Reopen and verify with `sp_verify.py --revision v03`, then quit the task instance before rendering.
- `preview_textured.py -- --revision v03 --save-only` saves the candidate; `verify_textured.py -- --revision v03` checks/renders it.
- `--lighting gloss` on the preview script supplies a strip light for checking the paint finish.
- `sp_roundtrip_v02.py` is a read-only color baseline export, and `check_refinement.py` reports preservation and roughness.
- Deliver with `deliver.py --revision v03`. The prior .blend/SPP/maps remain intact.

## Owner-requested studio

Run `studio.py -- build` in Blender to create `models/padlock_v03_studio.blend`.
The saved file uses EEVEE/Rendered view and a light-only sweep on frames 1–240 (24 fps).
`studio.py -- render --frame 74` renders the hero still with Cycles; `--eevee-check` verifies live-view rendering.
`studio.py -- verify` compares the prop geometry/material with v03 and checks light motion and dependencies.
Four cameras and a Russian embedded Text note are included. No video is produced.
