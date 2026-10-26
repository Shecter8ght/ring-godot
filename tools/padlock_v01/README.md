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

## Varnish and mixed contact wear v04

- `masks_v04_png.py prepare` records v03/master hashes and copies the owner's chip/dust alphas.
- Run `masks_v04.py` in Blender, then `masks_v04_png.py png` in dependency Python.
  The shared `uv_mask_raster.py` evaluates millimetre positions on existing UV triangles;
  it rejects nonfinite fields and does not edit geometry. Contacts include interrupted axial
  steel among blue paint/rust, roughness and fine scoring, larger edge chips, irregular key
  impacts/scratches, and sheltered rivet/seam/socket deposits.
- Launch the isolated Painter and open with `--revision v04`; a missing v04 starts from v03.
  Wait for `_reopened_v04.txt` before modifying the stack. `painter.py` gives only this child
  process an E: temporary directory, avoiding the nearly-full C: cache warning.
- Run `sp_refine_v04.py` with `--revision v04 --wait-for _v04_saved.txt`.
  It preserves the original 25 layers, hides the five replaced v03 finish/contact layers,
  and adds 12 editable fills (37 total). V03 shackle oxide detail remains enabled.
  OpenPBR Coat is enabled: coat weight/roughness and a separate neutral tangent normal
  let the surviving varnish reflect without inheriting all of the oxide's gritty normal.
  Close/reopen the saved SPP, then run `sp_export_v04.py` with `--wait-for _v04_ready.txt`.
  Export is separate from stack rebuilding; a successful staged set is published together.
  This avoids delivering partial maps if Painter crashes during export.
- Export five 4K PNGs: baseColor, ORM, Normal_OpenGL, coat (R weight / G roughness),
  coatNormal. Both normal maps are 16 bit. `sp_verify.py --revision v04` checks an actual
  reopened SPP, including the enabled shader and coat channels, then closes without saving.
- Save with `preview_textured.py -- --revision v04 --save-only`; reopen/check with
  `verify_textured.py -- --revision v04`. `check_refinement_v04.py` checks preserved sources,
  protected rust color and nonuniform coat/contact roughness in the exported maps.
- Build/render/verify the same studio with `studio.py -- <mode> --revision v04`.
  Lights, cameras and exposure match v03; only the source material changes.
- Deliver with `deliver.py --revision v04`; all earlier source revisions remain intact.

`sp_probe_coat.py` / `sp_ui_probe.py` are read-only native API/modal diagnostics.
`probe_gloss.py` is an unsaved look-development probe; its PNG is excluded from delivery.
