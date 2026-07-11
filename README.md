# FLATBED S-1200

A mobile web app that simulates a flatbed scanner — and invites you to abuse it.

A real scanner captures one row of pixels at a time as the head moves down the
glass. This app does exactly that: while the lamp line sweeps the platen, only
the strip of pixels directly under it is committed to the output. Everything
below the line is still live — so if you drag, pinch, or rotate the photo
mid-scan, the captured rows come from different positions and you get authentic
photocopier-glitch artifacts: stretches, compressions, duplicated features,
smears, and wavy shears. Nothing is faked with filters; the artifacts fall out
of the slit-scan mechanic, just like moving paper on a copier.

## Use it

Open `index.html` in a browser — it is a single self-contained file with no
dependencies and no build step. Best on a phone.

1. **LOAD** a photo (or play with the built-in calibration target).
2. Position it: one finger pans, two fingers pinch-zoom and rotate.
3. Press **SCAN** and keep moving the photo while the lamp sweeps.
4. **SAVE** the result, or **RE-FEED** it back in as the new original and scan
   again — artifacts compound with every pass.

The **RES** setting is real: higher DPI means a slower scan head, which means
more time to manipulate the original.

Desktop fallback: drag pans, wheel zooms, shift+wheel rotates.

## Technique cheatsheet

- Drag **down with the line** at its speed → the same strip repeats forever.
- Drag **up against the line** → the image compresses.
- Hold still, then **yank sideways** → a clean horizontal shear.
- **Rotate slowly** → wavy, melted geometry.
- **RE-FEED** a few passes → deep-fried generational decay.
