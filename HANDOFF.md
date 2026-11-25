# TimeSplitters 2 — sniper scope handoff

## Current state

- Repo: `/tmp/split2-engine-audit`
- Branch: `fix/comprehensive-engine-audit`
- Current branch tip: this documentation/tooling commit
- Last gameplay commit: `903bde1` (`Keep the sniper ammo outline with its count`)
- `xboxrecomp` pin: `c9fd93a` on local branch `fix/two-d-side-centre-band`
- Toolchain checkpoints: `checkpoint/vintage-scope-done` (`2996cfb`) and
  `checkpoint/vintage-scope-stretched-covered`
- The Release build at `build/Release/split2_recomp` was rebuilt after the
  successful ammo fixes.
- The toolkit regression suite passed 31/31 from
  `/tmp/split2-xboxrecomp-tests`.
- The working tree should contain no gameplay changes after this handoff is
  committed. The pre-existing untracked `replay000.bmp` is user data; leave it
  alone.

The remaining issue is only the sniper scope's mask at extreme horizontal aim.
The HUD/readout defects described below are fixed and must not regress.

## Symptom, reproduction and expected behaviour

### Symptom

When the sniper scope approaches the left or right screen edge, part of the
scope mask stops forming the expected lens shape. A large clear area becomes a
rectangle with a hard vertical boundary and horizontal top/bottom edges. The
world is visible inside that rectangle while the surrounding shade is opaque.

This occurs while holding the scoped view and panning horizontally. It is not
the ammo readout drifting and it is not the dark duplicate `10`; both of those
are fixed.

The latest symptom images are:

- `build/engine-audit/scope-border-handoff/left-edge-symptom.jpg`
- `build/engine-audit/scope-border-handoff/right-edge-symptom.jpg`

### Reproduction

1. Launch the US audit build in 16:9 with site tagging:

   ```bash
   cd /tmp/split2-engine-audit/build/Release
   RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
   RECOMP_USER_DIR=/tmp/split2-scope-live.xdrDlk/profile \
   RECOMP_MUTE=1 RECOMP_FPS_CAP=60 RECOMP_RES_SCALE=1 \
   RECOMP_WIDESCREEN=1 RECOMP_ASPECT_RATIO=16:9 \
   RECOMP_TS2_UI_SITES=1 ./split2_recomp
   ```

2. Load the Siberia sniper checkpoint.
3. Aim through the scope and pan slowly to the far left, then the far right.
4. Press F11 at a broken edge. Keep `RECOMP_TS2_UI_SITES=1` so the resulting
   `.d3dcap` has call-site tags and forced batch boundaries.

The runtime paths above are an isolated copy. Do not run a test against the
user's normal save.

### Expected

The opaque shade should remain continuous around the circular/rounded lens as
the lens approaches an edge. A partly off-screen lens is acceptable if its
visible boundary remains circular/rounded. A rectangular exposed band is not.

## Fixed and verified: sniper ammo readout

The following fixes are successful and must be preserved.

### Cartridge strip

The five gold cartridge glyphs are the 128x32 texture strip drawn through site
`0x000BEDE7`.

The normal hip-fire strip and the scope strip share the site, so a global
placement change is wrong. At one scope position the strip's midpoint was 178
of 640 pixels (27.8%). The old `SIDE` heuristic treated that as left-edge HUD
and moved the strip about 80 pixels away from the count.

Toolkit commit `c9fd93a` reduces only the left `SIDE` band from one third to one
quarter of the screen. The right boundary remains at two thirds so the normal
hip-fire row, whose midpoint can be about 67%, remains right-anchored.

Relevant file:

- `xboxrecomp/src/d3d/d3d8_device.c`, `two_d_side_anchor()`

Replay evidence:

- Before: cartridge row occupied x=117..149.
- After: row occupied x=197..229, leaving 16 pixels before the count.
- Hip-fire replay was pixel-identical.

### Scope grouping

The white ammo number is drawn through `0x000BE5FC`, not the small icon/range
site `0x000C37BA`. The number and cartridge strip can cross the right `SIDE`
boundary at different aim positions.

The US project now sets `g_ts2_scope_active` for the rest of a frame after
either `0x001C7EFF` (scope renderer) or `0x000CA58E` (shade) draws. While that
flag is set, these shared HUD sites use `TS2_UI_CENTRE`:

- `0x000BE5CF` — black font/outline layer
- `0x000BE5FC` — white ammo number
- `0x000BEDE7` — cartridge strip

Outside scope frames they remain the normal `SIDE` layout. The frame-local flag
is reset by `ts2_present()`.

Relevant files and lines:

- `src/recomp_manual.c`: `g_ts2_scope_active`, `ts2_present()`,
  `ts2_ui_scope_marker()`, `ts2_ui_scope_place()`, `ts2_ui_reserve()`
- `config/us/overrides.inc`: `ts2_ui_scope_marker()`,
  `ts2_ui_scope_place()` and the two-dimensional placement table

Commits:

- `a6a6676` — quarter-width left `SIDE` band
- `d1318eb` — scope grouping for white count and cartridge strip
- `903bde1` — scope grouping for the black outline

Verification:

- `scope-grouping-live-a.jpg` and `scope-grouping-live-b.jpg` show the count
  and cartridge strip together at two live aim positions.
- The black shadow/duplicate `10` was isolated to `0x000BE5CF`. Centring it
  removed that draw in `verified-ammo-outline-fix.jpg`; a subsequent live
  capture also showed the dark `10` on the crate gone.

## Remaining issue: sniper mask at horizontal aim limits

### What is established

This section is experimentally verified unless explicitly marked otherwise.

The sniper mask is not the same renderer as the vintage rifle mask.

The shared mask draw is wrapped at US `sub_001B54D0` (PAL `0x001B58E0`).
Its real body is `sub_001B54D0_gen`. The wrapper currently calls
`ts2_scope_mask_quad(site)` only when:

- the site is in `0x000C2F37..0x000C3050`, or
- the site is in `0x000C3AFA..0x000C3C13`, and
- `g_ts2_depth == 1`, and
- widescreen display is active.

`ts2_scope_mask_quad()` scales only the inner X endpoints by
`(guest_width * aspect_h) / (guest_height * aspect_w)`, normally 0.75.
Endpoints equal to the viewport's left/right edge are left alone. The function
then calls `sub_001B54D0_gen` and restores the original arguments.

Relevant implementation:

- `config/us/overrides.inc`, starting around `ts2_scope_mask_quad()`.

### The eight mask pieces

The first visible mask pass has eight untextured triangle-list quads. Sites,
geometry at a centred scope, and role:

| Site | Vertices at centred aim | Role |
| --- | --- | --- |
| `0x000C2F37` | x=0..185.75, y=0..106 | top-left |
| `0x000C2F62` | x=454.25..639, y=0..106 | top-right |
| `0x000C2F88` | x=0..185.75, y=106..374 | left |
| `0x000C2FAF` | x=185.75..454.25, y=0..106 | top cap |
| `0x000C2FD6` | x=454.25..639, y=106..374 | right |
| `0x000C2FFD` | x=185.75..454.25, y=374..479 | bottom cap |
| `0x000C3025` | x=0..185.75, y=374..479 | bottom-left |
| `0x000C3050` | x=454.25..639, y=374..479 | bottom-right |

At the centred position the lens is roughly x=185.75..454.25 and
y=106..374, approximately 268.5 by 268 guest pixels.

All eight sites are currently `TS2_UI_STRETCH`.

The mask is drawn twice in the captured scope:

- first pass: `colorwrite=0x7`
- second pass: `colorwrite=0x8`

Each pass contains the same eight site IDs and geometry. In the tagged
right-edge capture they are draws 17-24 and 30-37.

Draw state for the untextured pieces:

- primitive: 4 (triangle list)
- primitive count: 2
- stride: 16 bytes (position plus vertex colour)
- vertex shader: `0x10001` in the capture/replay, two instructions
- blend: `1 5>6`
- no texture bound

### Rounded corners and alpha rectangle

The mask corners use a 64x64 texture, reported as format code `0x06` and
runtime texture ID 17 in `right-edge-tagged.d3dcap`:

| Site | Role |
| --- | --- |
| `0x000C3096` | top-left corner |
| `0x000C30BF` | bottom-left corner |
| `0x000C30E8` | top-right corner |
| `0x000C3182` | bottom-right corner |

These corner draws use:

- primitive 4
- two primitives per corner
- stride 24 bytes
- vertex shader `0x10000`
- the same blend state as the mask

`0x000C2F03` is an untextured alpha rectangle inside the mask. In the
right-edge capture it is x=396..640, y=106..375; in the left-edge capture it
is x=0..248, y=106..375. The right-edge capture was taken during the temporary
corner/alpha `STRETCH` experiment, so use its gradient geometry as evidence
but do not treat its corner/alpha placement chunks as the current table.

The corner and alpha sites are currently `TS2_UI_CENTRE`. Leaving them there is
part of the last known-good state.

Other scope-inside markings use the remaining `0x000C31xx`,
`0x000C32xx`, `0x000C34xx`, `0x000C35xx` and `0x000C36xx` sites listed in the
placement table. Most are `TS2_UI_CENTRE`; `0x000C31F3` is `TS2_UI_STRETCH`.

### Geometry at the broken edge

The tagged right-edge capture contains:

- inner lens left: x=377.0
- inner lens right: x=645.5
- lens top: y=106
- lens bottom: y=374

The right inner endpoint is 6.5 pixels beyond the 640-pixel viewport. The left
side pieces span x=0..377, while the central band remains x=377..645.5. This
produces the observed rectangular clear band from x=377 to the right edge.

The untagged left-edge capture shows the mirror case:

- inner lens left: -3.25
- inner lens right: 265.25
- the clear band is x=0..265.25

The left-side mask pieces become degenerate or lie off-screen:

- top-left: x=0..-3.25
- left: x=0..-3.25, y=106..374
- bottom-left: x=0..-3.25

The important distinction is that this is not the renderer clipping the mask
to the old 4:3 viewport. The captured mask draws run under:

- viewport: 0,0 to 640x480
- scissor: 0,0-639,479

The full-screen scissor and viewport mean the rectangular edge is in the guest
mask geometry, not host-side scissor clipping.

### Why this differs from the vintage scope

The successful vintage-rifle fix in commits `e9ff711` through `2996cfb` was
needed because:

1. The vintage mask is four textured quads using `oldscopeedge.xbt`; its
   circular hole is baked into the texture.
2. The quads moved with aim, but their outer edges stopped at the 4:3 picture.
3. The mask quadrants were `CENTRE`, so the host also applied a 4:3 viewport
   and scissor to them.
4. The fix extends the outer edge to +/-2000, compensates the gradient UVs, and
   changes the movable quadrants to `STRETCH`.

Useful failed steps from that investigation:

- `d82f075` and `4bceb24` added static black side strips. They failed because
  the vintage overlay itself moves with aim; the strips covered the lens at one
  side while leaving gaps at the other. Reverted by `7efd0d8`.
- `3fc0ddb` extended the textured mask outward but stretched its gradient.
  `974a406` corrected that by scaling the texture coordinate with the edge.
- Initial quadrant placement stayed `CENTRE`; that kept the host scissor at
  4:3 and clipped the extended mask. `1b935c2` changed those quadrants to
  `STRETCH`.
- `90c5c9c`, `1d47f7e`, and `2996cfb` then corrected the circular fade,
  vertical crosshair, and lens position relative to the aiming ray.

That solution cannot be applied unchanged to the sniper scope:

- The sniper mask's clear inner boundary is real geometry, not a texture hole.
- Its eight gradient sites are already `STRETCH`.
- Its outer endpoints already coincide with the full 640-pixel viewport.
- Its scissor is already full-screen.

Extending the sniper mask's outer endpoints to +/-2000 was tested against the
left-edge capture and changed exactly zero pixels. See
`attempt-outer-edge-extension.jpg`.

## Attempts and results

### Verified successful

- `c9fd93a`: changed only the left `SIDE` threshold from one-third to
  one-quarter. Fixed the cartridge strip jumping to the left anchor.
- `d1318eb`: made the white ammo count and cartridge strip use `CENTRE`
  whenever a scope marker has appeared in the current frame.
- `903bde1`: added the black outline site `0x000BE5CF` to that scope-only
  grouping. Fixed the dark duplicate `10`.

### Tested and unsuccessful

1. **Pin the shared camera matrix `c64` around the readout reserve**
   (`1d6e91c`)
   - Reserve occurs too early; the actual batched draw happens later.
   - Reverted by `f7e8178`/the corresponding revert sequence.

2. **Pin `c64` around the flush using batch-site tracking** (`d424e00`)
   - Site tracking was stale across the mixed 3D batch and froze parts of the
     first-person viewmodel.
   - Reverted by `91d50a4`.

3. **Extend the sniper mask's outer X endpoints beyond the viewport**
   - Tested by modifying the captured vertices offline.
   - Result: zero changed pixels because the outer edges already meet the
     viewport.
   - Reverted; no code change kept.
   - Evidence: `attempt-outer-edge-extension.jpg`.

4. **Move the corner and alpha sites `0x000C3096`, `0x000C30BF`,
   `0x000C30E8`, `0x000C3182`, and `0x000C2F03` from `CENTRE` to
   `STRETCH`**
   - Tested in the live build at the right edge.
   - It changed the corner gradients over approximately
     x=377..420, y=139..340, but the rectangular clear band remained.
   - It can move the corner texture away from the geometry it is meant to
     soften.
   - Reverted; current table has all five at `CENTRE`.
   - Evidence: `attempt-corner-placement.jpg`.

5. **Shift the whole lens inward by 55.5 pixels**
   - Tested offline by editing mask/corner/alpha vertices in
     `left-edge-untagged.d3dcap`.
   - The lens moved inward, but the rectangular band remained.
   - This disproves the narrow hypothesis that a simple travel clamp alone
     fixes the shape.
   - Reverted; no code change kept.
   - Evidence: `attempt-lens-shift.jpg` and
     `attempt-lens-shift.d3dcap`.

### Important tagging warning

Without `RECOMP_TS2_UI_SITES=1`, captures can contain many draws under tag
`00000000`. Tags also persist across more than one draw until the next
placement chunk. Do not assume a tag identifies exactly one draw.

When isolating contributions:

- use `RECOMP_TS2_UI_SITES=1`;
- prefer `--no-scene` when comparing hidden/solo draws;
- use `--draws N --dump-drawn --dump-target` to inspect one mask pass;
- verify against captured vertices, not only `--hide-tag`.

## Preserved captures, logs and analysis tools

The stable artifact directory is:

`/tmp/split2-engine-audit/build/engine-audit/scope-border-handoff`

This directory is under ignored `build/` because captures contain game data.

### Captures and images

- `right-edge-tagged.d3dcap` — tagged right-edge failure, 4.0 MiB. It was
  captured with the temporary corner/alpha `STRETCH` experiment; the gradient
  geometry and symptoms are useful, while the tag/placement log must be read
  with that caveat.
- `right-edge-tagged.bmp` — corresponding live frame, 640x480.
- `right-edge-symptom.jpg` — compressed viewing copy.
- `left-edge-untagged.d3dcap` — left-edge failure, 46 MiB, useful for exact
  mask geometry but without site tags.
- `left-edge-untagged.bmp` and `left-edge-symptom.jpg`.
- `scope-readout-grouping-tagged.d3dcap` — tagged scope/readout reference,
  5.1 MiB.
- `scope-readout-grouping-tagged.bmp` and `scope-readout-grouping.jpg`.
- `scope-pre-grouping-tagged.d3dcap` — earlier tagged scope capture showing the
  pre-fix readout jump; 4.9 MiB.
- `scope-pre-grouping-tagged.bmp`.
- `scope-grouping-live-a.d3dcap` / `.bmp` and `.jpg`.
- `scope-grouping-live-b.d3dcap` / `.bmp` and `.jpg`.
- `hip-tagged.d3dcap` / `.bmp` — normal hip-fire HUD reference.
- `verified-ammo-outline-fix.jpg` — before/after evidence for `0x000BE5CF`.
- `attempt-outer-edge-extension.jpg`.
- `attempt-outer-edge-extension.d3dcap` — offline outer-edge test capture.
- `attempt-corner-placement.jpg`.
- `attempt-lens-shift.d3dcap` and `attempt-lens-shift.jpg`.

### Draw listings and run logs

- `right-edge-tagged-draws.log`
- `left-edge-untagged-draws.log`
- `scope-readout-grouping-tagged-draws.log`
- `hip-tagged-draws.log`
- `right-edge-tagged-run.log` — `[TS2-UI]` site chains and live run state.
- `scope-grouping-run.log` — successful scope grouping run.

Original working copies also remain under
`/tmp/split2-scope-live.xdrDlk/`. The build directory is the safer reference
because it is stable for this workspace.

### Capture probe

`tools/scope_capture_probe.py` parses a `.d3dcap` without a GPU and prints draw
metadata plus vertices. Its draw numbering matches `d3d8_replay --list-draws`.

Examples:

```bash
cd /tmp/split2-engine-audit

# Exact left-edge mask vertices.
python3 tools/scope_capture_probe.py \
  build/engine-audit/scope-border-handoff/left-edge-untagged.d3dcap \
  --draws 12-16 --vertices -1

# Tagged right-edge mask vertices.
python3 tools/scope_capture_probe.py \
  build/engine-audit/scope-border-handoff/right-edge-tagged.d3dcap \
  --sites 000C2F37,000C2F62,000C2F88,000C2FAF,000C2FD6,000C2FFD,000C3025,000C3050 \
  --vertices -1
```

## Build, run and replay

### Release build

```bash
cmake --build /tmp/split2-engine-audit/build/Release -j6
```

The game executable is:

`/tmp/split2-engine-audit/build/Release/split2_recomp`

The replay executable is:

`/tmp/split2-engine-audit/build/Release/xboxrecomp/src/replay/d3d8_replay`

### Run with logging and site tags

```bash
cd /tmp/split2-engine-audit/build/Release
RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
RECOMP_USER_DIR=/tmp/split2-scope-live.xdrDlk/profile \
RECOMP_MUTE=1 RECOMP_FPS_CAP=60 RECOMP_RES_SCALE=1 \
RECOMP_WIDESCREEN=1 RECOMP_ASPECT_RATIO=16:9 \
RECOMP_TS2_UI_SITES=1 ./split2_recomp \
  > /tmp/split2-scope-investigation.log 2>&1
```

F11 writes `frameNNN.bmp` and `frameNNN.d3dcap` beside the executable.

### Replay

Render the right-edge failure:

```bash
cd /tmp/split2-engine-audit
RECOMP_WIDESCREEN=1 RECOMP_RES_SCALE=1 \
  build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/right-edge-tagged.d3dcap \
  --no-scene --present --out /tmp/scope-right-replay --quiet
```

List every draw and state:

```bash
build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/right-edge-tagged.d3dcap \
  --no-scene --list-draws --quiet \
  > /tmp/scope-right-draws.log 2>&1
```

Render only the first mask pass:

```bash
build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/left-edge-untagged.d3dcap \
  --no-scene --draws 13 --dump-drawn --dump-target --present \
  --out /tmp/scope-mask-pass --quiet
```

Skip the geometric mask:

```bash
build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/left-edge-untagged.d3dcap \
  --no-scene --skip-draw 12 --present \
  --out /tmp/scope-no-mask --quiet
```

Skipping draw 12 removes the rectangular shade. That is direct evidence that
the eight-piece mask pass, not the scene copy or scissor, creates the cutoff.

### Replay placement overrides

`--place` is useful for tagged captures but can affect every draw carrying the
tag until the next placement chunk. Use one `--place` per site:

```bash
build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/right-edge-tagged.d3dcap \
  --place 000C2F37=stretch --place 000C2F62=stretch \
  --place 000C2F88=stretch --place 000C2FAF=stretch \
  --place 000C2FD6=stretch --place 000C2FFD=stretch \
  --place 000C3025=stretch --place 000C3050=stretch \
  --no-scene --present --out /tmp/scope-placement-test --quiet
```

### Toolkit tests

The standalone toolkit build used for tests is already configured at
`/tmp/split2-xboxrecomp-tests`:

```bash
cmake --build /tmp/split2-xboxrecomp-tests -j6
ctest --test-dir /tmp/split2-xboxrecomp-tests --output-on-failure -j6
```

To recreate it:

```bash
cmake -S /tmp/split2-engine-audit/xboxrecomp \
  -B /tmp/split2-xboxrecomp-tests -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DXBOXRECOMP_EXTERNAL_SDL=ON \
  -DXBOXRECOMP_DXC_INCLUDE=/tmp/split2-engine-audit/xboxrecomp/third_party/dxc/include/dxc \
  -DXBOXRECOMP_DXC_LIBRARY=/tmp/split2-engine-audit/xboxrecomp/third_party/dxc/lib/libdxcompiler.so
```

## Relevant guest addresses and call chains

All addresses below are US unless marked PAL.

### Text and HUD shared paths

- `0x001C8E35` / `sub_001C8E35_gen` — shared vertex reserve.
- `0x001C98AF` / `sub_001C98AF_gen` — shared batch flush.
- `0x001B75F0` / `sub_001B75F0_gen` — PAL `0x001B7A00`; wrapped text/number
  drawing path.
- `0x001B5E80` / `sub_001B5E80_gen` — PAL `0x001B6290`; shared text/quad path.
- `0x001B5F01` — inner reserve return used by number and outline chains.
- `0x001B75E0` — inner return used by the number/outline chain.

Observed site chains:

- `0x000BE5CF`: `001ACD63 -> 001AC65F -> 001AB3FA -> 001B5F01 -> reserve`
- `0x000BE5FC`: `001ACAAF -> 001AC65F -> 001AB3FA -> 001B5F01 -> reserve`
- `0x000BEDE7`: `001B75E0 -> 001B5F01 -> reserve`

Earlier addresses that were investigated but are not the final HUD sites:

- `0x0014C723` — reserve return in the width-scaled/3D-projected ammo path.
- `0x001B0A52` — caller into `sub_001B75F0`.
- `0x000C37BA` — small in-lens icon/range/marker, already `CENTRE`.

Do not base the readout fix on `0014C723`/`001B0A52`; batching carried those
tags across unrelated geometry and produced the wrong initial diagnosis.

### Scope marker, shade and mask

- `0x001C7EFF` — scope renderer site used as the frame-local scope marker.
- `0x000CA58E` — full-screen scope shade site; also marks the frame as scoped.
- `0x000CA705` — scope postprocess site skipped at raised render scale.
- `0x000CA261`, `0x000C9FCA` — additional low-resolution postprocess sites.
- `0x001B54D0` — US wrapper around the shared mask draw; PAL `0x001B58E0`.
- `0x001B54D0_gen` — real mask draw body.
- `0x001B5530` — return-chain entry observed for mask gradients.
- `0x001B5E80` chain — used by the mask corner texture draws.
- `0x001B7501 -> 0x001B52E9` chain — used by the alpha rectangle.

### Vintage-only path

- `0x001B75A0` — US vintage mask wrapper; PAL `0x001B79B0`.
- `0x001B75A0_gen` — real vintage mask draw.
- The vintage mask is a textured hole, not the sniper's geometric ring.

## Viewport, scissor and renderer placement

Current renderer semantics:

- `TS2_UI_STRETCH` disables the 2D squeeze and lets a screen-space draw span
  the whole 16:9 frame.
- `TS2_UI_CENTRE` keeps the title's 4:3 shape, applies a centred horizontal
  squeeze, and narrows the viewport/scissor to the 4:3 region.
- `SIDE` chooses left/right/centre from the draw extent.
- `AUTO` falls back to the renderer's extent test.

The renderer's `SIDE` thresholds are in
`xboxrecomp/src/d3d/d3d8_device.c`:

- x `< 25%` chooses LEFT;
- x `> 66.67%` chooses RIGHT;
- otherwise CENTRE.

The left-quarter threshold is a successful TS2 HUD fix. Do not restore the
one-third threshold without replaying the cartridge-strip and hip-fire cases.

The mask capture reports:

- viewport: `0,0 640x480 z 0..1`
- scissor during mask draws: `0,0-639,479`

An earlier scissor `0,0-638,478` belongs to the scene target setup and is not
the mask clip.

## Textures and render state

- Eight sniper mask gradients: no texture; stride 16; two triangle-list
  primitives; vertex shader `0x10001`; blend `1 5>6`; first pass
  `colorwrite=0x7`, second pass `colorwrite=0x8`.
- Four rounded corners: 64x64 texture, captured as runtime texture 17, format
  code `0x06`; stride 24; vertex shader `0x10000`.
- Alpha rectangle: no texture; stride 16; `colorwrite=0x8`.
- Ammo cartridge strip: 128x32 texture, format code `0x0E`; site
  `0x000BEDE7`.
- Ammo glyphs/outlines: glyph atlas textures around 256x256 or 512x512,
  format code `0x0E`; sites `0x000BE5CF` and `0x000BE5FC`.
- Scope screen copy: 640x480 texture, format code `0x12`, followed by a
  full-screen triangle-list draw. This is related to the separately deferred
  low-resolution scope blur.

Runtime texture IDs (`tex 17`, `tex 89`, etc.) are local to a capture. Prefer
the site tag plus dimensions/format when identifying resources.

## Verified findings versus untested hypotheses

### Verified

- The hard rectangular boundary is created by mask draw 12 in
  `left-edge-untagged.d3dcap`; skipping that draw removes it.
- The eight mask pieces leave the rectangular band when the lens centre
  crosses the viewport.
- The host scissor is full-screen during these draws.
- Extending only the outer mask endpoints has no visible effect.
- Changing the five corner/alpha sites to `STRETCH` does not remove the band.
- Shifting the whole mask inward by 55.5 pixels does not remove the band.
- The vintage outer-edge/UV fix addresses a different mask representation.
- The ammo readout fixes are successful and independent of this mask issue.

### Untested hypotheses

- Whether the original Xbox behaves the same at a true extreme aim or whether
  the game normally limits scope travel before the mask reaches this state.
- Whether the intended lens is always circular at a screen edge or uses a
  different clipped shape.
- Whether a uniform mask clamp can be made acceptable if all dependent
  geometry (corners, reticle, markings, readout) is shifted with it.
- Whether the guest computes a lens centre/radius value elsewhere that can be
  reused to generate correct edge geometry.
- Whether replacing only the clipped half with extra geometry can avoid a
  full-screen shader pass.

## Candidate approaches for Astra

These are alternatives, not a prescribed single solution.

### 1. Coordinate clamp for the entire scope overlay

Find the guest value that positions the lens centre. Clamp its effective X
used by the mask to keep the full circular lens within a screen margin, and
apply the same offset to the reticle, markings, ammo group and readout.

Advantages:

- Smallest rendering change.
- Keeps the existing texture/state pipeline.
- Easy to verify at one left and one right endpoint.

Drawbacks:

- The current mask geometry is still eight axis-aligned pieces.
- A mask-only clamp detaches the lens from the reticle.
- Clamping aim itself changes gameplay reach.
- The 55.5-pixel test shows a simple mask-only shift is insufficient.

### 2. Add edge-specific mask geometry

Keep the current eight pieces for the normal case. When an inner edge leaves
the viewport, add triangles or corner quads that form the partial circle
against the screen edge.

Advantages:

- Localized to the edge case.
- Avoids a toolkit-wide shader change.
- Can preserve the current centre/lens mapping.

Drawbacks:

- Needs correct triangulation and blending at the join.
- Must be built through the guest's reserve/batch path or a reliable renderer
  override.
- Multiple lens sizes or both scope renderers may need separate handling.

### 3. Tessellated circular ring

Replace the eight rectangular pieces with a triangle strip/fan sampled around
the lens circle, clipped against the viewport.

Advantages:

- Mathematically handles full and partial lens shapes.
- Can preserve a moving lens centre.
- No per-pixel shader state.

Drawbacks:

- More geometry and a larger replacement of lifted draw behavior.
- Blend state, vertex colour order and draw order must match exactly.
- Needs careful capture/replay verification.

### 4. Procedural screen-space circular mask

Skip the guest mask pieces and run a Toolkit postprocess that computes alpha
from the lens centre/radius.

Advantages:

- Exact circular/soft edge at any position.
- Avoids geometric approximation.
- Could expose a clean title-level API for scope masks.

Drawbacks:

- Requires Toolkit renderer/shader and capture/replay support.
- Ordering matters because trailing in-game markers and HUD must remain above
  the mask.
- Needs offscreen-target and render-scale behavior.
- Must be regression-tested across other titles.

This is one viable route, not the only viable fix.

### 5. Re-verify 4:3 and hardware behavior

Capture the same aim angle in a true 4:3 run or against hardware/xemu before
choosing a shape. This determines whether the rectangle is an original-game
edge case exposed by widescreen or a recompilation-only artifact.

This should be done before a large mask rewrite if access is available.

## Regression checklist

After any mask change, verify:

1. Centre-aim scope:
   - lens remains circular/rounded;
   - crosshair/markings remain aligned;
   - cartridge strip, white count, and black outline stay together.
2. Left extreme:
   - no rectangular exposed band;
   - shade still covers the whole left and right sides;
   - bullets still travel through the reticle.
3. Right extreme:
   - mirror behaviour of the left extreme.
4. Hip-fire:
   - cartridge row and number are in their normal HUD positions;
   - no dark duplicate `10` on the scene;
   - no viewmodel clipping.
5. Vintage rifle:
   - circular lens and full coverage remain intact.
6. `RECOMP_WIDESCREEN=0`:
   - original 4:3 HUD/scope behavior remains unchanged.
7. Toolkit suite:
   - all 31 tests still pass.

## Non-negotiable rollback points

- Do not regress the vintage scope: `checkpoint/vintage-scope-done`.
- Do not regress the stretched-covered vintage checkpoint:
  `checkpoint/vintage-scope-stretched-covered`.
- Ammo readout fixes: `a6a6676`, `d1318eb`, `903bde1`.
- Toolkit `SIDE` fix: `c9fd93a`.

No gameplay change was made for the edge-mask investigation. The only retained
changes added by this handoff are this document and
`tools/scope_capture_probe.py`.
