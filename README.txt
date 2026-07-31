Gear Icon Atlas — repaired 2x edition

Drop-in files for GitHub:
  gear_icons_atlas.png
  gear_icons_manifest.json

Cell: 128x128px (2x source for a 64x64 logical UI cell)
Grid: 10 columns x 150 rows
Canvas: 1280x19200px
Icons: 1118 (3 upgrade badges + 1115 gear items)
Background: transparent RGBA
Order: left-to-right, top-to-bottom; exact coordinates are in CSV/JSON.
Repair: source objects were isolated by connected silhouettes, preventing
neighbour fragments, clipping, and cell bleed from equal-grid cropping.
Compatibility: replace both the atlas PNG and manifest JSON together.

GitHub update:
1. In idleWorlds-game-sprites-BC, replace gear_icons_atlas.png.
2. Replace gear_icons_manifest.json in the same commit.
3. The batch PNGs are optional reference sheets; the game loads the atlas.
4. Use the included v44.10 HTML if the browser keeps showing cached old files.
