# TimeSplitters 2 — engine audit handoff

## State

- Repo: `/tmp/split2-engine-audit`
- Branch: `fix/comprehensive-engine-audit`
- HEAD: `f7e8178` (working tree clean)
- Submodule `xboxrecomp`: pinned at `6005f19`
- Checkpoints: `checkpoint/vintage-scope-done` (on `2996cfb`),
  `checkpoint/vintage-scope-stretched-covered`
- Full prior session log:
  `~/.codex/sessions/2026/11/22/rollout-2026-11-22T22-37-36-01a20568-6026-7da1-839e-6f9860e041c9.jsonl`

## Build / run / capture

```bash
cmake --build /tmp/split2-engine-audit/build/Release
cd /tmp/split2-engine-audit/build/Release
RECOMP_TS2_UI_SITES=1 RECOMP_WIDESCREEN=1 ./split2_recomp
```

F11 captures land in `build/Release/frame*.d3dcap`. Replay with
`xboxrecomp/src/replay/d3d8_replay` and `RECOMP_WIDESCREEN=1`.

## Done (committed, verified in-game)

- Menu/loading 2x art + launcher option (`a2a3e12`, toolkit `6005f19`)
- Cutscene blur: skip the fourth low-res overlay pass (`31c3ef0`)
- Cutscene/vblank pacing trace (`85ed1ff`)
- Vintage scope fully fixed in widescreen (`e9ff711`..`2996cfb`)
- Sniper scope shade (`5388827`) and text/icon placement (`cf4497a`, `34a3184`)

## Remaining issue: sniper scope ammo readout sways with the scope

Sites: bullet glyphs `0x14C723` -> `sub_001C8E35` (reserve), ammo number
`0x1B0A52` -> `sub_001B75F0`. Both draw in the camera's local space through
the shared view matrix (`c64`-`c67`), which sways with the scope. The Hor+
projection (applied to register `c60` in `xboxrecomp/src/d3d/d3d8_vsh.c`)
amplifies the horizontal component in 16:9, so the readout drifts left with
the aim.

Tried and reverted: pinning `c64` around the reserve (`1d6e91c`) and around
the flush gated on batch site (`d424e00`). The reserve is too early (the real
draw is the later flush), and the flush gate is unreliable across the 3D
batch, so it froze the first-person viewmodel. Both were reverted.

Recommended real fix: give the readout its own fixed transform (screen space)
rather than sharing the view matrix. This is a lift-aware change: patch the
lifted text path and teach the lifter to preserve it, or add a per-draw
transform override with a reliable way to identify only the readout's 2D
batch. Do this in a scoped session with in-game checks after each step.

## Also remaining: low-resolution screen-copy effects

Two cosmetic blur/resolution issues share one renderer root cause and are
best fixed together:

- The **uplink** copies the top-left 128x128 of the scene into a 128x128
  shadow render target (see `hle_d3d8_render_texture` in
  `xboxrecomp/src/hle/hle_d3d8_texture.c` and `d3d8_screencopy.c`), so the
  map is only 128x128 even at 4x/6x render scale.
- The **sniper scope** blends 640x480 screen copies back over the
  supersampled scene in its shade (`0xCA58E`) and tint (`0xC31F3`) passes,
  which is the same softening that made cutscenes blurry (fixed for
  cutscenes by skipping `0xCA099`, but the scope's shade/tint are not
  skippable).

Both need **offscreen render-target scaling**: create shadow render targets
at guest size * render scale and scale the viewport/scissor/screencopy
accordingly. This is the deliberately deferred feature described in
`d3d8_device.c` (`rt_scale_x` currently returns 1 for offscreen targets).
It is a toolkit-wide change and should be done carefully in the submodule
with tests across the other recomp titles.
