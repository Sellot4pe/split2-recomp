# TimeSplitters 2 — comprehensive US engine audit handoff

## Status

The modern sniper scope edge issue is fixed in commit:

```text
2e30a55 Align the sniper scope before widescreen clipping
```

The uncapped minigun spin-up issue is fixed in the latest commit:

```text
f176093 Restore minigun spin-up in uncapped gameplay
```

The fix preserves the game's original eight-piece scope mask, four textured
corners, alpha rectangle, reticle and readout. It does **not** replace the mask
with procedural or tessellated geometry.

The implementation was independently inspected against the generated guest
code, rebuilt, and checked against tagged 4:3/16:9 captures and synthetic
native-mask replays. The user also visually confirmed the final right-edge and
bullet-impact frames. The uncapped minigun reaches its full spin rate in
0.901 seconds, within 0.001 seconds of the 60 FPS reference.

No unresolved fundamental rendering problem is known. Three separate uncapped
follow-ups remain:

- minigun overheat occurs after about 64 rounds at uncapped rates versus about
  100 rounds at 60 FPS;
- player knockback appears much stronger while uncapped;
- the sci-fi pistol weapon bob appears jerky while uncapped.

Those are documented below and should not be conflated with the completed
scope or minigun spin fixes. Direct 4:3, vintage-rifle and hip-fire regression
captures remain routine PR work.

## Current repository state

Repository:

```text
/tmp/split2-engine-audit
```

Branch and commits:

```text
fix/comprehensive-engine-audit
Handoff commit: this documentation commit (`git log -1`)
f176093  Restore minigun spin-up in uncapped gameplay
2e30a55  Align the sniper scope before widescreen clipping
e26b0fb  Document the remaining sniper scope mask investigation
903bde1  Keep the sniper ammo outline with its count
d1318eb  Keep sniper scope ammo groups together
a6a6676  Keep the sniper cartridge row beside its ammo count
```

Successful vintage-rifle commits and checkpoints:

```text
d82f075  Widen the vintage scope side strips in widescreen
4bceb24  Meet the vintage scope strips to the inset lens quadrants
7efd0d8  Revert the vintage scope strip widening
3fc0ddb  Extend the vintage scope mask past the screen
974a406  Keep the vintage scope gradient 1:1 when extending the mask
1b935c2  Stretch the vintage scope mask quadrants
checkpoint/vintage-scope-stretched-covered = 1b935c2
90c5c9c  Make the vintage scope fade circular in widescreen
1d47f7e  Stretch the vintage scope vertical crosshair
2996cfb  Align the vintage scope lens with the aiming ray
checkpoint/vintage-scope-done = 2996cfb
```

Toolkit submodule:

```text
xboxrecomp c9fd93a
Keep drifting centre-side HUD rows centred
```

The submodule is clean. Its commit is the preserved `SIDE` threshold change
used by the ammunition readout and must not be reverted.

The only untracked root-level file is the pre-existing:

```text
replay000.bmp
```

Treat it as user data and leave it untouched.

The current Release executable is:

```text
build/Release/split2_recomp
sha256 3e41a53fc9325057c61625627a45eec213e0e35b38c433a53031c1fdbcb38b91
```

The branch is 49 commits ahead of upstream `main` at `7a3345f`. Open upstream
PRs #52 through #55 cover smaller subsets of the same audit. The comprehensive
branch should be opened as a **draft** until its known uncapped follow-ups are
resolved and the maintainer decides whether to prefer the combined branch or
the smaller PRs.

## Latest uncapped minigun work

### Symptom and reproduction

At frame caps above 60 FPS, the minigun barrels accelerated far more slowly
than at 60 FPS. A full spin that should complete in about 0.9 seconds took
several seconds at uncapped rates. The same save/scene and burst at 60 FPS was
the reference.

Reproduction:

```bash
cd /tmp/split2-engine-audit/build/Release

RECOMP_USER_DIR=/tmp/split2-minigun-debug/profile \
RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
RECOMP_MUTE=1 RECOMP_FPS_CAP=0 RECOMP_RES_SCALE=1 \
RECOMP_WIDESCREEN=1 RECOMP_ASPECT_RATIO=16:9 \
./split2_recomp
```

Load the isolated minigun scene, hold primary fire for about three seconds,
then repeat with the cap at 60 FPS.

### Root cause

The held-weapon animation update is US `0x000B3E10`. It consumes two action
fields:

```text
action + 0x4C  persistent trigger-held state
action + 0x50  firing pulse
```

The firing pulse is rebuilt only on whole simulation ticks. At 60 FPS one
whole tick occurs each rendered frame, so spin-up advances normally. Above
60 FPS most rendered frames have `game_step == 0`; the pulse is absent, and
the type-5 minigun path runs its decay branch instead of accelerating.

Relevant state:

```text
player                  0x00497100
primary action record   player + 0x528
held weapon block       actor + 0x408
minigun animation type  held + 0x30 == 5
spin phase              action + 0x70
spin rate               action + 0x74
spin-rate limit         24.0 for this action/type
```

The selected `action` pointer is the guest `ESI` value at entry to
`sub_000B3E10`.

### Implementation

[`config/us/overrides.inc`](config/us/overrides.inc) wraps
`sub_000B3E10_gen`.

On a fractional frame with:

- `g_ts2_us_free_step` active;
- held animation type `5`;
- persistent trigger state `action+0x4C != 0`;

the wrapper temporarily supplies `action+0x50 = 1` for this one animation
update and restores the saved pulse afterwards. The action pointer is copied
locally before the call because the generated function may change guest `ESI`.

The guest action state seen by other subsystems is unchanged. This fix covers
both spin and the heat update that shares the firing-pose branch.

### Verification

The telemetry compared the action-0x74 spin-rate ramp directly:

```text
60 FPS reference:  reaches 24.0 at 0.900 s
uncapped fixed:    reaches 24.0 at 0.901 s
```

The user visually confirmed the uncapped burst. A subsequent three-second
capture completed without corruption. Normal adaptive play and the 31-test
suite remained clean.

### Remaining overheat issue

The shared firing branch also updates heat. With the committed fix, the user
observed approximately:

```text
60 FPS:    100 rounds before overheat
uncapped:  64 rounds before overheat
```

Removing the fractional-frame pulse made the gun take more than 200 rounds and
effectively never overheat before ammunition ran out. A hybrid that preserved
`held+0xCC` between ticks and ran firing updates with a whole-tick float also
failed to overheat correctly. Those experiments were reverted completely.

Do not restore any of the experimental hybrid code. The next investigation
should identify the exact heat accumulator and complete state-machine
consequences before changing this wrapper.

Evidence and exact experiment logs:

```text
build/engine-audit/minigun-investigation/OBSERVATIONS.md
build/engine-audit/minigun-investigation/overheat-pulse-every-frame.log
build/engine-audit/minigun-investigation/overheat-no-pulse-fractional-frames.log
build/engine-audit/minigun-investigation/overheat-committed-spin-fix.log
build/engine-audit/minigun-investigation/overheat-hybrid-experiment.log
```

### Deferred uncapped observations

The following were intentionally left unchanged:

- Excessive-looking player knockback after taking damage. The uncapped trace
  contains movement spikes up to roughly 97 units/second, but it was not
  established whether the hit itself was vanilla-strength.
- Jerky weapon bob with the sci-fi pistol.

Pinned trace and notes:

```text
build/engine-audit/minigun-investigation/inertia-and-sci-fi-pistol-bob-uncapped.log
build/engine-audit/minigun-investigation/OBSERVATIONS.md
```

## Symptom and expected behaviour

### Historical symptom

Holding the modern sniper rifle in Siberia, especially the saved sniper
checkpoint, and panning to the left or right edge caused part of the scope
overlay to stop at the old 4:3 clipping boundary. Depending on the
intermediate patch state this appeared as:

- a hard rectangular boundary where the rounded lens should continue;
- missing or incorrectly placed rounded-corner arcs at a screen edge;
- a detached/dark duplicate ammunition outline;
- scope coordinates or the reticle stopping before the visible widescreen
  edge.

The earlier duplicate `10`, grouped ammunition row and initial left/right
placement problems were separate fixes and are preserved.

### Final fixed symptom

At an extreme aim position, the clear aperture is allowed to extend beyond the
physical screen. The visible portion now keeps the original rounded/faded
transition, the opaque shade covers both sides continuously, and the reticle
can reach the screen edge.

The final hand-tested frame is:

```text
build/engine-audit/scope-border-validation/fixed-169/last.png
```

A numerically cropped, small viewing copy is:

```text
build/engine-audit/scope-border-validation/last-reticle-crop.png
```

It shows the bullet impact at the reticle.

### Reproduction

Run the isolated copy, not the user's normal save:

```bash
cd /tmp/split2-engine-audit/build/Release

RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
RECOMP_USER_DIR=/tmp/split2-scope-live.xdrDlk/profile \
RECOMP_MUTE=1 RECOMP_FPS_CAP=60 RECOMP_RES_SCALE=1 \
RECOMP_WIDESCREEN=1 RECOMP_ASPECT_RATIO=16:9 \
RECOMP_TS2_UI_SITES=1 ./split2_recomp
```

Load the Siberia sniper save, equip the modern sniper, aim through the scope,
and pan to full left/right. Press F11 to capture a tagged frame.

For a reproducible bounded run:

```bash
cd /tmp/split2-engine-audit

python3 build/engine-audit/scope-border-validation/run-game.py \
  check-169 --ratio 16:9 \
  --sequence build/engine-audit/scope-border-validation/siberia-c.seq \
  --duration 53 --captures 1730 90 14
```

The script uses the isolated profile/game directories under
`build/engine-audit/scope-border-validation`.

## Root cause

This is a coordinate-space ordering bug, not a defect in the original scope
geometry.

The modern sniper renderer at US `0x000C2CB0` lays out the optic in the guest's
640×480/4:3 coordinate system. Its one caller is:

```text
src/recomp/gen/recomp_0019.c:13078
0x000C8C76 -> sub_000C2CB0
```

The caller pushes four arguments in the order observed on the guest stack:

```text
edi, eax, 1.0f, 1
```

The fourth argument, `TS2_MEM32(g_esp + 16u)`, is the modern-scope mode used
by the fix. `sub_000C2CB0` has no other generated call site.

Inside `sub_000C2CB0_gen`, the lens, mask, alpha rectangle, corners, reticle,
markings, font glyphs and cartridge strip are calculated and clipped in that
640×480 space. The old host path then applied the widescreen `CENTRE`
placement, which squeezes X by the 4:3/16:9 correction factor (normally
`0.75`) and narrows the GPU viewport/scissor **after** guest clipping and
glyph culling had already occurred.

The renderer cannot recover geometry or glyphs that the guest discarded at
the old 640-pixel boundary. Moving the surviving vertices with `CENTRE` also
put their rounded transitions in a different coordinate space from the
already-positioned shade.

The correction therefore has to move the modern scope's X coordinates into
display space **before** the guest's culling and clipping, then submit those
draws through a full-width `STRETCH` viewport.

## Exact coordinate evidence

The native 4:3 reference lens is 358 pixels wide:

```text
centred aperture: x=141..499, y=106..374
```

The equivalent 16:9 placement uses:

```text
x' = 320 + (x - 320) * 0.75
```

giving:

```text
centred fixed aperture: x=185.75..454.25, y=106..374
```

At the tagged right-side aim:

```text
guest aim x=575
4:3 aperture x=396..754
translated aperture x=377..645.5
display aperture is clipped by the physical viewport to x=377..639
```

That partial aperture touching the right edge is intentional. The shade's
viewport-side vertices remain pinned at `0` and `639`.

At the tagged left-side aim:

```text
guest aim x=69
translated aperture begins slightly left of x=0
visible aperture ends near x=266
```

The synthetic native/fixed raster comparison proves the distinction:

```text
centre fixed: 0 differing RGB pixels
left   fixed: 0 differing RGB pixels
left   old:   316 differing pixels, bbox x=0..265,   y=106..373
right  fixed: 0 differing RGB pixels
right  old:   185 differing pixels, bbox x=378..638, y=106..373
3x right: pixel-identical, 1920x1440
```

The small old differences are concentrated in the rounded corner transitions
at the edge. They are not a reason to replace the mask. The difference image
is:

```text
build/engine-audit/scope-border-validation/flat/difference-contact.jpg
```

The earlier hypothesis that the eight axis-aligned pieces alone required
replacement was incomplete. They are the original shade construction around a
geometric clear aperture. Once their inner X endpoints and all dependent
overlay pieces are placed in the same coordinate space before guest clipping,
the original shape is correct.

## Original eight-piece mask

The first sniper shade pass contains these eight untextured triangle-list
quads. The second pass repeats the same geometry with a different colour-write
mask.

| US site | 4:3 centred span | Role |
| --- | --- | --- |
| `0x000C2F37` | x=0..141, y=0..106 | top-left |
| `0x000C2F62` | x=499..639, y=0..106 | top-right |
| `0x000C2F88` | x=0..141, y=106..374 | left |
| `0x000C2FAF` | x=141..499, y=0..106 | top cap |
| `0x000C2FD6` | x=499..639, y=106..374 | right |
| `0x000C2FFD` | x=141..499, y=374..479 | bottom cap |
| `0x000C3025` | x=0..141, y=374..479 | bottom-left |
| `0x000C3050` | x=499..639, y=374..479 | bottom-right |

At the final 16:9 centre position the inner endpoints are `185.75` and
`454.25`; the outer viewport endpoints remain `0` and `639`.

Draw state:

- primitive `4` (triangle list);
- two primitives per piece;
- stride `16` (position plus packed colour);
- vertex shader `0x10001`;
- no texture bound;
- blend `1 5>6`;
- first pass `colorwrite=0x7`;
- second pass `colorwrite=0x8`.

The mask call chain is:

```text
000C2F37..000C3050 -> 001B5530 -> reserve
```

## Corner, alpha and screen state

The four rounded corners are:

| US site | Role |
| --- | --- |
| `0x000C3096` | top-left |
| `0x000C30BF` | bottom-left |
| `0x000C30E8` | top-right |
| `0x000C3182` | bottom-right |

They use a 64×64 texture. In the failure capture it is runtime texture 17,
format code `0x06`, stride `24`, vertex shader `0x10000`, two triangle-list
primitives and the same blend state as the shade.

The alpha rectangle is:

```text
0x000C2F03
```

It is a two-triangle, stride-16, untextured draw with `colorwrite=0x8`. Its
call chain is:

```text
000C2F03 -> 001B7501 -> 001B52E9 -> reserve
```

The captured mask runs with:

```text
viewport 0,0 640x480 z=0..1
scissor  0,0..639,479
```

The earlier `0,0..638,478` scissor belongs to scene-target setup and is not the
scope mask clip.

Placement values in a capture:

```text
1 = STRETCH
2 = CENTRE
```

The fixed mask, corners, alpha and reticle are all recorded as placement `1`
during the modern-scope draw. The native 4:3 reference records its proportioned
pieces as `2`; with a 4:3 display that does not introduce a widescreen squeeze.

## Implementation

All gameplay changes are in:

```text
config/us/overrides.inc
```

`config/us/overrides.inc` is included into `src/recomp_manual.c` during the
relift. Generated guest source is not edited.

### Modern-renderer activation

Added:

```c
typedef struct { float centre, scale; } Ts2SniperLayout;
static RECOMP_MANUAL_TLS Ts2SniperLayout g_ts2_sniper;
```

`sub_000C2CB0()` now wraps `sub_000C2CB0_gen()` and saves/restores the TLS
layout state around the call.

It enables the transform only when all of the following hold:

- the fourth argument is nonzero (the modern-scope mode);
- `d3d8_display_wide_now()` is true;
- guest width, height, aspect numerator and denominator are valid;
- the guest viewport starts at X=0 and ends at guest width−1;
- the aspect correction is not exactly `1.0`.

The scale is:

```c
((float)guest_w * aspect_h) / ((float)guest_h * aspect_w)
```

and the centre is `guest_w / 2`.

### Shared float-X wrapper

```c
static float ts2_sniper_x(float x)
{
    return g_ts2_sniper.centre +
           (x - g_ts2_sniper.centre) * g_ts2_sniper.scale;
}
```

`ts2_sniper_places_quad()` requires:

- active sniper layout;
- an active UI-wrapper nesting depth;
- the outermost draw site mapped to `TS2_UI_STRETCH`.

`ts2_sniper_float_quad()` transforms float arguments at `g_esp+4` and
`g_esp+12`, runs the generated function, then restores the original words.

### Glyph and textured-quad paths

`sub_001AB380()` performs the X transform before calling
`sub_001AB380_gen()` so the helper's 640-pixel visibility test sees display
coordinates.

`sub_001B5E80()` applies the same transform to eligible textured quads. It
excludes:

- `0x001AB3FA`: a glyph draw whose X coordinates were already transformed at
  `sub_001AB380`, avoiding a double scale;
- `0x000C31F3`: the viewport-sized tint, which must remain full-screen.

The other textured quads include the authored corner quads and cartridge
strip.

### Mask endpoint correction

`sub_001B54D0()` already had the successful pre-Astra correction for the
normal widescreen scope: scale interior mask endpoints around the guest
centre and leave viewport-side endpoints alone.

The final fix makes endpoint roles explicit while the modern renderer is
active, because an interior endpoint can equal `0` or `639` at one aim value:

- pin `x0` for `0x000C2F37`, `0x000C2F88`, `0x000C3025`;
- pin `x1` for `0x000C2F62`, `0x000C2FD6`, `0x000C3050`;
- transform the other endpoints.

This avoids relying on a coordinate value to infer which side of the aperture
the endpoint belongs to.

### Inclusive integer rectangle clipping

`sub_001B7450()` normally clips an inclusive integer rectangle to the guest
viewport and hands four floats to `sub_001B52C0()`.

During the modern-scope layout it:

1. sorts the original X endpoints;
2. transforms the inclusive pixel span;
3. passes rounded inclusive display-pixel bounds to the original clipper;
4. retains the exact float span in `g_ts2_sniper_span`;
5. lets the original guest code continue to sort/clip Y and reject wholly
   off-screen rectangles.

When the original clipper reaches `sub_001B52C0()` through return address
`0x001B7501`, the float writer intersects its arguments with the exact span.
The writer adds one to `x1`, so the wrapper compensates for that convention.
This keeps the reticle, alpha clear and meter at their original subpixel
positions.

### Placement

While `g_ts2_sniper.scale` is active, `ts2_ui_scope_place()` returns
`TS2_UI_STRETCH` for every draw in the modern scope call tree.

Outside that call tree, the previous successful scope/HUD grouping remains:

- `0x000BE5CF`;
- `0x000BE5FC`;
- `0x000BEDE7`.

Those sites still use `TS2_UI_CENTRE` while a scope marker is active in the
frame.

## Guest call sites and wrappers

All addresses are US unless marked PAL.

### Modern sniper renderer

- `0x000C2CB0` / `sub_000C2CB0_gen`: modern scope renderer.
- `0x000C8C76`: sole caller of `sub_000C2CB0`.
- `0x000C2F37`..`0x000C3050`: eight shade pieces.
- `0x000C3096`, `0x000C30BF`, `0x000C30E8`, `0x000C3182`: rounded corners.
- `0x000C2F03`: alpha-clear rectangle.
- `0x000C31F3`: full-screen tint, excluded from quad transformation.
- `0x000C34D2`: vertical reticle line.
- `0x000C34E7`: horizontal reticle line.
- `0x000C3503`, `0x000C3520`, `0x000C353B`, `0x000C354E`: remaining
  reticle pieces.

### Shared drawing wrappers

- `0x001B5E80` / PAL `0x001B6290`: textured quad helper.
- `0x001B54D0` / PAL `0x001B58E0`: mask gradient helper.
- `0x001B5530`: mask gradient return-chain entry.
- `0x001B7450` / PAL `0x001B7860`: inclusive integer rectangle clipper.
- `0x001B7501 -> 0x001B52E9`: alpha/reticle writer chain.
- `0x001B52C0` / PAL `0x001B56D0`: float rectangle writer.
- `0x001AB380` / PAL `0x001AB7C0`: glyph visibility/quad helper.
- `0x001AB3FA`: return into `sub_001B5E80`, excluded from a second transform.
- `0x001C8E35`: shared vertex reserve.
- `0x001C98AF`: shared batch flush.

Observed tagged call chains:

```text
000C2F37 -> 001B5530 -> reserve
000C3096 -> 001B75E0 -> 001B5F01 -> reserve
000C2F03 -> 001B7501 -> 001B52E9 -> reserve
000C34D2 -> 001B7501 -> 001B52E9 -> reserve
000BE5CF -> 001ACD63 -> 001AC65F -> 001AB3FA -> 001B5F01 -> reserve
000BE5FC -> 001ACAAF -> 001AC65F -> 001AB3FA -> 001B5F01 -> reserve
000BEDE7 -> 001B75E0 -> 001B5F01 -> reserve
```

### Vintage rifle

- `0x001B75A0` / PAL `0x001B79B0`: vintage mask wrapper.
- `0x001B75A0_gen`: vintage mask body.
- `0x000C2B81`, `0x000C2B9E`, `0x000C2BC4`, `0x000C2BE1`: four movable
  vintage quadrants.

The modern renderer state can only become active from `sub_000C2CB0`; the
vintage path does not call it, so the new transform is inert when rendering
the vintage scope.

## Why the vintage fix was not sufficient

The successful vintage fix established two important principles:

1. UI geometry that must cover the wide screen has to use `STRETCH`, because
   `CENTRE` applies a narrowed host viewport/scissor.
2. Geometry that would otherwise end at the old 4:3 picture can be extended
   beyond the physical viewport and clipped by the rasteriser.

The vintage mask is four textured quads with the circular hole baked into its
texture. Extending its outer edges to `±2000`, compensating the gradient UVs,
and changing the quadrants to `STRETCH` fixes that representation.

That approach alone did not fix the modern sniper because:

- the modern aperture boundary is real untextured geometry;
- its outer shade endpoints already reached the full guest viewport;
- extending only those outer endpoints changed zero pixels;
- its mask sites were already `STRETCH`;
- the guest had already clipped/culled the moving corners, alpha rectangle and
  reticle in the wrong coordinate system.

The missing operation was the pre-clip X placement shared by the whole modern
scope call tree.

## Attempts, results and disposition

Successful and retained:

- `a6a6676`, `d1318eb`, `903bde1`: keep the cartridge row, white count and
  black outline grouped in the scope.
- toolkit `c9fd93a`: quarter-width left `SIDE` band; preserves hip-fire
  placement.
- `2e30a55`: pre-clip modern-scope X transform and full-width placement.

Tested and rejected/reverted:

1. **Extend only the modern mask outer X endpoints beyond the viewport**
   - Offline replay changed zero pixels because those endpoints already met
     the viewport.
   - No code kept.
   - Evidence: `build/engine-audit/scope-border-handoff/attempt-outer-edge-extension.jpg`.

2. **Move only the corner and alpha sites to `STRETCH`**
   - Changed the corner gradients but left the rectangular/old-boundary
     behaviour.
   - Reverted.
   - Evidence: `attempt-corner-placement.jpg`.

3. **Shift the entire lens inward by 55.5 pixels**
   - Moved the aperture but did not remove the old-boundary failure.
   - Offline only; no code kept.
   - Evidence: `attempt-lens-shift.d3dcap`, `attempt-lens-shift.jpg`.

4. **Pin the shared camera matrix during readout reserve**
   - The reserve happened before the later batched draw.
   - Reverted by `f7e8178`.

5. **Pin the model-view matrix at batch flush**
   - Site tracking leaked across a mixed 3D batch and froze the viewmodel.
   - Reverted by `91d50a4`.

6. **Static black side strips for the vintage scope**
   - Covered or exposed the moving lens at different aim positions.
   - Reverted by `7efd0d8`.

No procedural mask, tessellated replacement, shader mask or texture rewrite was
adopted. The current evidence does not justify any of those.

## Verification completed

### Geometry/reference comparison

The committed regression tool is:

```text
tools/regression/test_us_scope.py
```

It compares a tagged native 4:3 centred reference with display-space tagged
captures. It checks:

- both mask passes and their order;
- every shade and corner vertex;
- corner texture coordinates;
- alpha rectangle clipping;
- both reticle lines and all visible reticle pieces;
- `STRETCH` placement on 16:9 captures;
- the recovered guest aim.

All ten tagged 16:9 captures passed:

```text
frame000  guest aim (320, 240)
frame001  guest aim (69, 240)
frame002  guest aim (575, 240)
frame003  guest aim (575, 240)
frame004  guest aim (575, 240)
frame005  guest aim (575, 240)
frame006  guest aim (575, 240)
frame007  guest aim (459, 240)
frame008  guest aim (434, 240)
frame009  guest aim (455, 240)
```

Frames 002–006 intentionally repeat the right aim; they are separate
F11 captures, not six distinct aim positions.

The 4:3 vertical comparison captures also passed:

```text
reference frame003: guest aim (320, 429)
reference frame004: guest aim (320, 49)
```

Important capture caveat: `fixed-169/frameNNN.bmp` files are periodic shadow
frames, while `fixed-169/frameNNN.d3dcap` files are later F11 captures. A BMP
and a `.d3dcap` with the same number are **not paired frames**. Use the
`.d3dcap` for geometry and the separately named final screenshots for visual
evidence.

### Pixel-level mask replay

Synthetic flat-background recordings contain the native modern mask translated
to known left/right aim positions. Replaying the fixed output reproduces the
native artwork exactly:

```text
centre fixed: 0 differing RGB pixels
left   fixed: 0 differing RGB pixels
left   old:   316 differing RGB pixels, bbox (0, 106)-(265, 373)
right  fixed: 0 differing RGB pixels
right  old:   185 differing RGB pixels, bbox (378, 106)-(638, 373)
right at 3x:  pixel-identical 1920x1440
```

The small viewing/difference artifacts are:

```text
build/engine-audit/scope-border-validation/flat/difference-contact.jpg
build/engine-audit/scope-border-validation/review-contact.jpg
```

### Readout and duplicate outline

At the fixed centre frame, the native row/count positions map as expected:

```text
4:3 cartridge strip x=405..453
4:3 white count x=463..468.36
4:3 black outline x=465..470.36

16:9 fixed strip x=383.75..419.75
16:9 fixed white count x=427.25..431.27
16:9 fixed black outline x=428.75..432.77
```

The black outline remains 1.5 display pixels to the right of the white glyph
and stays with the count, so the duplicate dark `10` does not reappear.

At right-edge aim the count remains visible at approximately `x=618.5..630.05`
instead of being detached or culled at the old centre boundary.

### Aiming and bullet decal

The final user frame shows a bullet impact centred on the reticle at the right
side of the scope. The small crop is `last-reticle-crop.png`; the bright impact
effect and dark bullet hole surround the horizontal/vertical reticle
intersection. This confirms the visual fix did not separate the aiming point
from the rendered reticle.

The user reviewed the final frame and reported that it lines up perfectly.

### 4:3 behaviour

The transform is guarded by:

```c
d3d8_display_wide_now()
```

and by a non-unit aspect scale. With widescreen disabled it does not run.

Native 4:3 scope references retain the original spans:

```text
centre aperture x=141..499
left aperture   starts at x=-111 and ends at x=247
right aperture  x=396..754
```

Current and saved-baseline deterministic 4:3 Siberia runs both completed
successfully. Those runs do not reach the modern scope at the sampled swap
counts, so a direct post-final-change 4:3 scope F11 capture remains a routine
regression test rather than an already captured artifact.

### Vintage and hip-fire

The vintage visual replay remains fully covered on both sides:

```text
build/engine-audit/scope-border-validation/replay-vintage000.bmp
```

The current build's periodic hip-fire frame:

```text
build/engine-audit/scope-border-validation/fixed-169/frame008.bmp
```

shows the normal rifle/viewmodel and ammunition HUD without scope placement.
It is a periodic frame and must not be paired with `frame008.d3dcap`.

Direct live vintage-scope and hip-fire F11 captures on the final commit remain
recommended before PR merge.

### Build and test suite

The Release build completed without warnings. Final reruns:

```text
31/31 toolkit tests passed
timing test passed at 30, 60, 120, 144, 317 and 719 FPS
uncapped minigun spin reaches 24.0 at 0.901 s vs 0.900 s at 60 FPS
committed uncapped overheat: about 64 rounds vs 100 at 60 FPS (known issue)
python -m py_compile passed for the capture probe and scope regression tool
git diff --check passed
```

Logs:

```text
build/engine-audit/scope-border-validation/build-rerun.log
build/engine-audit/scope-border-validation/ctest-rerun.log
build/engine-audit/scope-border-validation/timing-rerun.log
build/engine-audit/scope-border-validation/pixels-rerun.log
```

## Exact verification commands

Run from `/tmp/split2-engine-audit`.

Build:

```bash
cmake --build build/Release -j6
```

If `config/us/overrides.inc` is changed, relift before building:

```bash
/home/conor/.venvs/recomp/bin/python scripts/build.py \
  --region us --relift --from lift --no-build
cmake --build build/Release -j6
```

Check the native 4:3 reference against itself:

```bash
python3 tools/regression/test_us_scope.py \
  build/engine-audit/scope-border-validation/reference-43/frame000.d3dcap \
  build/engine-audit/scope-border-validation/reference-43/frame000.d3dcap \
  --aspect 4:3
```

Check vertical aim in the native reference:

```bash
python3 tools/regression/test_us_scope.py \
  build/engine-audit/scope-border-validation/reference-43/frame000.d3dcap \
  build/engine-audit/scope-border-validation/reference-43/frame003.d3dcap \
  build/engine-audit/scope-border-validation/reference-43/frame004.d3dcap \
  --aspect 4:3
```

Check every fixed 16:9 capture:

```bash
python3 tools/regression/test_us_scope.py \
  build/engine-audit/scope-border-validation/reference-43/frame000.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame000.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame001.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame002.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame003.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame004.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame005.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame006.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame007.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame008.d3dcap \
  build/engine-audit/scope-border-validation/fixed-169/frame009.d3dcap
```

Run synthetic mask pixel and 3×-scale replay:

```bash
python3 build/engine-audit/scope-border-validation/replay_validation.py \
  > build/engine-audit/scope-border-validation/pixels-final.log
cat build/engine-audit/scope-border-validation/pixels-final.log
```

Run toolkit tests:

```bash
ctest --test-dir /tmp/split2-xboxrecomp-tests --output-on-failure -j6
```

Rebuild the standalone toolkit first if required:

```bash
cmake --build /tmp/split2-xboxrecomp-tests -j6
```

Run timing regression:

```bash
python3 tools/regression/test_us_timing.py \
  > build/engine-audit/scope-border-validation/timing-final.log
```

Run the uncapped minigun check from an isolated save:

```bash
cd /tmp/split2-engine-audit/build/Release

RECOMP_USER_DIR=/tmp/split2-minigun-debug/profile \
RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
RECOMP_MUTE=1 RECOMP_FPS_CAP=0 RECOMP_RES_SCALE=1 \
RECOMP_WIDESCREEN=1 RECOMP_ASPECT_RATIO=16:9 \
./split2_recomp
```

Hold primary fire on the minigun from rest. Confirm the barrels reach full
speed in about 0.9 seconds. Repeat at 60 FPS. The known overheat discrepancy
is a separate unresolved task; do not treat it as a spin-up failure.

Inspect exact reticle/corner/mask geometry:

```bash
python3 tools/scope_capture_probe.py \
  build/engine-audit/scope-border-validation/fixed-169/frame002.d3dcap \
  --sites 000C2F03,000C2F37,000C2F62,000C2F88,000C2FAF,000C2FD6,000C2FFD,000C3025,000C3050,000C3096,000C30BF,000C30E8,000C3182,000C34D2,000C34E7 \
  --vertices -1
```

Replay an old failure with its mask omitted:

```bash
RECOMP_WIDESCREEN=1 RECOMP_RES_SCALE=1 \
  build/Release/xboxrecomp/src/replay/d3d8_replay \
  build/engine-audit/scope-border-handoff/left-edge-untagged.d3dcap \
  --no-scene --skip-draw 12 --present --quiet \
  --out /tmp/scope-no-mask
```

## Artifact inventory

Primary validation directory:

```text
/tmp/split2-engine-audit/build/engine-audit/scope-border-validation
```

Native and fixed captures:

```text
reference-43/frame000.d3dcap  centred native optic
reference-43/frame001.d3dcap  left native optic
reference-43/frame002.d3dcap  right native optic
reference-43/frame003.d3dcap  low vertical aim
reference-43/frame004.d3dcap  high vertical aim

fixed-169/frame000.d3dcap   centred fixed optic
fixed-169/frame001.d3dcap   left aim x=69
fixed-169/frame002..006     right aim x=575, repeated captures
fixed-169/frame007.d3dcap   aim x=459
fixed-169/frame008.d3dcap   aim x=434, shot-check run
fixed-169/frame009.d3dcap   aim x=455, final shot-check run
```

Visual evidence:

```text
fixed-169/last.png
last-reticle-crop.png
fixed-169/contact.jpg
fixed-169/shot-contact.jpg
flat/difference-contact.jpg
review-contact.jpg
replay-vintage000.bmp
fixed-169/frame008.bmp
```

Analysis tools:

```text
tools/regression/test_us_scope.py
tools/scope_capture_probe.py
build/engine-audit/scope-border-validation/flat_masks.py
build/engine-audit/scope-border-validation/replay_validation.py
build/engine-audit/scope-border-validation/run-game.py
build/engine-audit/scope-border-validation/siberia.seq
build/engine-audit/scope-border-validation/siberia-b.seq
build/engine-audit/scope-border-validation/siberia-c.seq
```

Historical failure artifacts:

```text
build/engine-audit/scope-border-handoff/left-edge-symptom.jpg
build/engine-audit/scope-border-handoff/right-edge-symptom.jpg
build/engine-audit/scope-border-handoff/attempt-outer-edge-extension.jpg
build/engine-audit/scope-border-handoff/attempt-corner-placement.jpg
build/engine-audit/scope-border-handoff/attempt-lens-shift.jpg
build/engine-audit/scope-border-handoff/hip-tagged.d3dcap
build/engine-audit/scope-border-handoff/hip-tagged.bmp
```

Minigun and deferred uncapped-motion evidence:

```text
build/engine-audit/minigun-investigation/OBSERVATIONS.md
build/engine-audit/minigun-investigation/inertia-and-sci-fi-pistol-bob-uncapped.log
build/engine-audit/minigun-investigation/overheat-pulse-every-frame.log
build/engine-audit/minigun-investigation/overheat-no-pulse-fractional-frames.log
build/engine-audit/minigun-investigation/overheat-committed-spin-fix.log
build/engine-audit/minigun-investigation/overheat-hybrid-experiment.log
build/engine-audit/minigun-investigation/frames000-023-contact.jpg
build/engine-audit/minigun-investigation/user-minigun-frames.jpg
```

All captures contain game data and are intentionally under ignored `build/`.
Do not add them to Git.

## Remaining advanced work for Astra

These tasks need judgement or further reverse engineering. They are not
required to validate the completed scope fix.

1. **Uncapped minigun overheat timing**

   Current committed behaviour is about 64 rounds to overheat at uncapped
   rates versus 100 rounds at 60 FPS. The shared `0x000B3E10` firing-pulse
   wrapper fixes spin but affects heat as well. Do not simply remove the pulse:
   the tested no-pulse and hybrid variants either nearly prevented overheat or
   broke firing-pose progression.

   Identify the exact heat value and state transitions first. The
   `overheat-*.log` files record action state, shot counter, `held+0xC8`,
   `held+0xCC`, `held+0xD0`, action fields `+0x68/+0x70/+0x74/+0x78/+0xD4`,
   and `game_step`.

2. **Uncapped knockback**

   The uncapped trace contains repeated 60-97 units/second movement spikes,
   while ordinary movement is much lower and fixed pacing has not yet been
   captured for a comparable hit. Determine whether the hit impulse, collision
   resolution, or velocity damping is frame-coupled.

3. **Sci-fi pistol bob jitter**

   The same uncapped trace shows visibly jerky weapon bob. The `[TS2-BOB]`
   records include position, distance, phase and both bob outputs. This is
   likely a distinct weapon-animation timing issue, not the minigun pulse.

## Remaining regression checklist for DeepSeek Flash

These are routine tests. No advanced renderer work is required unless one
fails.

1. Run the build, geometry, synthetic replay, CTest and timing commands above.
2. Launch the final binary with `RECOMP_WIDESCREEN=0`, use an isolated save,
   and press F11 at centred, full-left and full-right modern-sniper aim.
   Confirm the 4:3 aperture is unchanged and the transform does not activate.
3. In 16:9, hold the vintage rifle and capture centred/left/right scopes.
   Confirm both sides remain covered and the lens/crosshair remain aligned.
4. In 16:9 hip-fire, capture the ordinary sniper HUD. Confirm cartridge row,
   white count and black outline stay together in the normal HUD corner.
5. Fire one shot at a flat wall at each horizontal extreme. Confirm the impact
   remains at the rendered reticle after recoil settles.
6. Check render scales 2× and 3×. The synthetic 3× right-edge mask replay is
   already pixel-identical; this step checks the complete live frame.
7. Check the minigun at 60 FPS and uncapped: spin-up must remain about
   0.9 seconds. Record overheat as a known follow-up rather than a regression
   of the spin fix.
8. Re-read `git diff --check`, run the tests once more, and prepare the PR.

Useful manual launch command:

```bash
cd /tmp/split2-engine-audit/build/Release

RECOMP_GAME_DIR=/tmp/split2-scope-live.xdrDlk/game \
RECOMP_USER_DIR=/tmp/split2-scope-live.xdrDlk/profile \
RECOMP_MUTE=1 RECOMP_FPS_CAP=60 RECOMP_RES_SCALE=1 \
RECOMP_WIDESCREEN=0 RECOMP_ASPECT_RATIO=4:3 \
RECOMP_TS2_UI_SITES=1 ./split2_recomp
```

## PR status and preparation

Upstream is `phobos665/split2-recomp`, whose current `main` is `7a3345f`.
Open PRs #52 through #55 cover smaller subsets of this audit:

```text
#52  widescreen aiming, decals and initial scope alignment
#53  US story NPC, canyon door and checkpoint callbacks
#54  ammo rows and candle heat haze
#55  supersampling clarity
```

The comprehensive branch is a 49-commit superset and includes additional US
menu, timing, scope-edge and minigun work. A combined PR is useful for review
visibility, but should be opened as a draft because the minigun overheat
follow-up remains unresolved and the maintainer may prefer the smaller PRs.

Push and open the Draft PR from the repository root:

```bash
git push -u fork fix/comprehensive-engine-audit

gh pr create \
  --repo phobos665/split2-recomp \
  --base main \
  --head Sellot4pe:fix/comprehensive-engine-audit \
  --draft \
  --title "Comprehensive US widescreen and uncapped engine audit" \
  --body-file build/engine-audit/pr-body.md
```

The PR body must explicitly state that it overlaps #52–#55, document the known
minigun overheat follow-up, and avoid claiming the uncapped knockback or
sci-fi pistol bob is resolved.

## Risks and cleanup

The fix deliberately reuses guest call sites and wrappers. It is narrowly
gated to the one modern-sniper renderer invocation and only activates in
widescreen.

Items worth reviewing in the PR:

- The fourth argument is currently tested as nonzero. The only generated call
  site passes exactly `1`; tightening this to `== 1` would make future
  contract changes explicit but is not required for current behaviour.
- `sub_001B5E80` excludes the already-transformed glyph return
  `0x001AB3FA` and the full-screen tint `0x000C31F3`. New drawing paths added
  to the modern renderer would need to be classified.
- The transform moves X only. That is correct for this title's horizontal
  aspect correction and is intentionally independent of Y.
- Dimensions other than 16:9 use the same aspect formula but have not received
  dedicated live captures.
- Captures and synthetic scripts live under ignored `build/`; a fresh clone
  needs the listed artifacts before the capture-based regression tool can run.
- The minigun wrapper is gated to animation type `5`, action state `1` and a
  persistent held-trigger value, but it intentionally restores the transient
  firing pulse after `0x000B3E10` so other subsystems do not observe the
  forced value.
- The minigun spin fix and the known overheat discrepancy share the same
  firing-pose branch. Review them together, but do not regress the measured
  0.900/0.901-second spin ramp.

No code was changed in `xboxrecomp`, and no procedural/tessellated mask work
should be started. If a new edge failure appears, first prove whether its X
coordinates are being transformed before the guest's visibility/clipping tests
and whether all dependent draws are submitted as `STRETCH`. That ordering was
the actual defect.
