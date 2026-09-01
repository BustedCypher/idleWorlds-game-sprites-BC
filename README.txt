IdleWorlds Toolkit — demand-loaded icon chunks

Runtime files:
  index.html
  assets/icon-sprites-v2.js
  assets/icons/v2/icon-manifest.<hash>.json
  assets/icons/v2/*.png

The legacy atlases remain deterministic build and rollback sources, but the
browser now fetches the compact manifest and only the gear-slot or item-category
chunks approaching the viewport. Hashed chunks are immutable and each is
decoded once. Failed or missing assets keep the existing visible fallback.

Build: python tools/build_icon_chunks.py
Validate: python tools/verify_icon_migration.py
          node --test tests/icon-sprites-v2.test.js
          node tools/check-inline-scripts.js index.html
