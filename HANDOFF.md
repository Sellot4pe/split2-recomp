# TimeSplitters 2 — engine audit handoff

## State

- Repo: `/tmp/split2-engine-audit`
- Branch: `fix/comprehensive-engine-audit`
- HEAD: branch tip containing this handoff update
- Submodule `xboxrecomp`: pinned at `c9fd93a`
  (`fix/two-d-side-centre-band`)
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
- Sniper scope cartridge row and ammo count stay together while aiming
  (toolkit `c9fd93a`, scope grouping in this commit)

## Fixed: sniper scope cartridge row sway

The visible drift is the 128x32 cartridge strip, drawn as a screen-space
quad through the shared ammo-HUD site `0x000BEDE7`. The numeric count uses
the neighbouring shared HUD site `0x000BE5FC`, not the scope-specific
`0x000C37BA` draw. The earlier `0x14C723`/`0x1B0A52` diagnosis was
misleading because batching carried those tags across unrelated geometry.

`SIDE` placement chose the right edge for the normal hip-fire row, but chose
the left edge for the scope row while its midpoint was between 25% and 33%
of the screen. The left-anchored widescreen squeeze then moved the cartridge
strip about 80 pixels away from the count. The toolkit now keeps SIDE draws
in the centre from 25% up to the existing right-side boundary
(`xboxrecomp/src/d3d/d3d8_device.c`, `two_d_side_anchor`). The right-side
threshold is unchanged because the hip-fire row can sit just inside the
right third.

The cartridge strip and count can still cross that right-side boundary at
different aim positions. When the scope renderer at `0x001C7EFF` or its
shade at `0x000CA58E` has drawn in the current frame, both shared HUD sites
are explicitly kept in the centred layout. Outside the scope they remain
`SIDE`, so the ordinary hip-fire HUD is unchanged.

Verified by replaying the saved scope capture: the row moved from x=117..149
to x=197..229, leaving a 16-pixel gap before the count. The hip-fire capture
was pixel-identical. Two live F11 captures with the patched build showed the
row aligned with the count at both scope positions. After adding the
scope-only grouping rule, three more live F11 captures at different aims
kept the strip and count together. All 31 toolkit tests pass.

The earlier attempts to pin `c64` around the reserve (`1d6e91c`) and flush
(`d424e00`) targeted the wrong layer and were correctly reverted.

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
