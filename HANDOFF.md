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
