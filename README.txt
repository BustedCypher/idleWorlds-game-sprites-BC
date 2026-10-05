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

Safety: tools/atomic_write.py is the only sanctioned way to overwrite a file
        here. A tripwire (tools/guard_working_files.py, wired to hooks in
        .claude/settings.json) checks index.html and the atlases after every
        tool call and keeps rolling backups in .claude/backups/.
          python tools/guard_working_files.py --check      report integrity
          python tools/guard_working_files.py --restore    undo a bad write
          python tools/guard_working_files.py --self-test  prove it detects

Add art: python tools/import_construction_icons.py <art-pack-dir>
         (folds supplied per-item PNGs into item_icons_atlas.png and the two
          CSVs; idempotent. The art pack lives outside this repo.)
Raid art: assets/raids/<raid>/index.json indexes seven icons per raid.
          raid_artwork_manifest.json records all 35 names, IDs, prompts,
          hashes, source paths and atlas coordinates. Each standalone sprite
          is transparent 128 px, with up to 120 px of artwork for a larger
          raid-unique silhouette. Full-size originals and the preview sheet
          are kept locally under output/raid-artwork/ and output/.
          python tools/import_raid_icons.py updates the legacy atlas sources;
          python tools/sync_gear_manifest_csv.py synchronises the gear CSV.
Build: python tools/build_icon_chunks.py
       Then re-pin manifestUrl in index.html to the hash it prints — the
       rebuild renames every chunk.
Validate: python tools/verify_icon_migration.py
          python -m unittest discover -s tests
          node --test tests/icon-sprites-v2.test.js
          node tools/check-inline-scripts.js index.html
