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

Live at https://raagulmanoharan.github.io/tst/ — or open `index.html` locally
(no build step; the PixiJS libraries are vendored in `vendor/`). Best on a
phone.

1. **LOAD** a photo (the native sheet offers Take Photo on mobile), or press
   **CAM** to scan your live camera feed — press it again to flip cameras.
   Or just play with the built-in calibration target.
2. Position it: one finger pans, two fingers pinch-zoom and rotate.
3. Toggle **FX** — RGB split, glitch slices, pixelate, halftone dots, CRT,
   twist. They're rendered live via PixiJS + pixi-filters and stack freely,
   so the scan head captures them baked into the output.
4. Press **SCAN** and keep moving the photo while the lamp sweeps.
5. **SAVE** the result, or **RE-FEED** it back in as the new original and scan
   again — artifacts compound with every pass.

If WebGL is unavailable the app falls back to a plain-canvas pipeline: the
scanner still works, only the FX rack is hidden.

The **RES** setting is real: higher DPI means a slower scan head, which means
more time to manipulate the original.

Desktop fallback: drag pans, wheel zooms, shift+wheel rotates.

## Technique cheatsheet

- Drag **down with the line** at its speed → the same strip repeats forever.
- Drag **up against the line** → the image compresses.
- Hold still, then **yank sideways** → a clean horizontal shear.
- **Rotate slowly** → wavy, melted geometry.
- **RE-FEED** a few passes → deep-fried generational decay.
