#!/usr/bin/env python3
"""Fold the v5.4 Woodcutting & Construction art pack into the legacy item atlas.

The atlas plus item_icons_cells.csv / item_icons_index.csv are the deterministic
build source that tools/build_icon_chunks.py reads; this importer is what puts
new art into that source. It is idempotent: item_ids already carried by the
index are skipped, so a re-run on a finished tree is a no-op.

Normalisation matches the convention the existing 375 cells already follow —
alpha-trim the supplied artwork, scale it to fit a 112x112 box, centre it on a
transparent 128x128 cell.

Usage:  python tools/import_construction_icons.py <art-pack-dir>

<art-pack-dir> holds construction_icon_manifest.json and the New Logs / New
Parts / New Buildings folders it names. That pack is ~390 MB of 1.5k-square
source PNGs and deliberately does NOT live in this repo — the normalised
128 px cells in item_icons_atlas.png are what the build reads. A copy of the
manifest alone is kept at the repo root as provenance for what went where.
"""
from __future__ import annotations
import csv, hashlib, io, json, os, re, sys
from pathlib import Path
from PIL import Image
from atomic_write import replace_atomically


CELL = 128
CONTENT = 112
COLUMNS = 10
ART_SOURCE = 'supplied construction art pack 2026-09-04'
GROUPS = {
    'timber': 'resources.wood',
    'building_parts': 'processed.building_parts',
    'building': 'trade.village_addon',
}
FAMILY_ORDER = ['timber', 'building_parts', 'building']

CELL_FIELDS = ['index', 'row', 'column', 'x', 'y', 'width', 'height', 'icon_key',
               'name', 'group', 'shared', 'usage_count', 'art_source', 'sha256_rgba']
INDEX_FIELDS = ['item_id', 'name', 'category', 'subcategory', 'tier', 'group',
                'art_source', 'shared_icon_key', 'index', 'row', 'column', 'x', 'y',
                'width', 'height', 'original_r3_index', 'original_r2_index']


def normalise(path: Path) -> Image.Image:
    """One supplied PNG -> one 128x128 transparent, centred cell."""
    with Image.open(path) as raw:
        art = raw.convert('RGBA')
        box = art.split()[3].getbbox()
        if box is None:
            raise ValueError('fully transparent source ' + str(path))
        art = art.crop(box)
        scale = CONTENT / max(art.width, art.height)
        size = (max(1, round(art.width * scale)), max(1, round(art.height * scale)))
        art = art.resize(size, Image.LANCZOS)
        cell = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
        cell.paste(art, ((CELL - art.width) // 2, (CELL - art.height) // 2))
        return cell


def read_csv(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    """CRLF deliberately: the two atlas CSVs already ship that way, and
    rewriting 1,167 untouched rows to LF turns a 102-row addition into a
    whole-file diff (and trips git's autocrlf warning on every later touch).

    Serialised in memory first, so an encoding failure raises with the target
    still untouched — see replace_atomically."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    replace_atomically(path, buffer.getvalue().encode('utf-8'))


def import_construction_icons(repo_root: Path, source_root: Path) -> dict:
    root = Path(repo_root).resolve()
    art = Path(source_root).resolve()
    manifest = json.loads((art / 'construction_icon_manifest.json').read_text(encoding='utf-8'))
    index_rows = read_csv(root / 'item_icons_index.csv')
    cell_rows = read_csv(root / 'item_icons_cells.csv')
    known = {r['item_id'] for r in index_rows}

    pending = [i for i in manifest['items'] if i['item_id'] not in known]
    pending.sort(key=lambda i: (FAMILY_ORDER.index(i['family']), int(i['tier'])))
    if not pending:
        return {'added': 0, 'cells': len(cell_rows), 'index_rows': len(index_rows)}

    html = (root / 'index.html').read_text(encoding='utf-8')
    tag = re.search(r"""<script[^>]*id=["']iw-embedded-items["'][^>]*>([\s\S]*?)</script>""", html, re.I)
    embedded = json.loads(tag.group(1))
    embedded = embedded if isinstance(embedded, list) else embedded['items']
    by_id = {str(i.get('item_id', '')): i for i in embedded}

    next_index = max(int(r['index']) for r in cell_rows) + 1
    total = next_index + len(pending)
    rows_needed = -(-total // COLUMNS)
    atlas_path = root / 'item_icons_atlas.png'
    with Image.open(atlas_path) as raw:
        old = raw.convert('RGBA')
        atlas = Image.new('RGBA', (COLUMNS * CELL, rows_needed * CELL), (0, 0, 0, 0))
        atlas.paste(old, (0, 0))

    for offset, item in enumerate(pending):
        ix = next_index + offset
        row, column = divmod(ix, COLUMNS)
        x, y = column * CELL, row * CELL
        cell = normalise(art / item['source']['path'])
        atlas.paste(cell, (x, y))
        record = by_id[item['item_id']]
        geometry = dict(index=ix, row=row, column=column, x=x, y=y, width=CELL, height=CELL)
        cell_rows.append(dict(geometry, icon_key='item.' + item['item_id'],
                              name=item['name'], group=GROUPS[item['family']],
                              shared='False', usage_count='1', art_source=ART_SOURCE,
                              sha256_rgba=hashlib.sha256(cell.tobytes()).hexdigest()))
        index_rows.append(dict(geometry, item_id=item['item_id'], name=item['name'],
                               category=record['category'],
                               subcategory=record.get('subcategory', ''),
                               tier=record.get('tier', ''), group=GROUPS[item['family']],
                               art_source=ART_SOURCE, shared_icon_key='',
                               original_r3_index='', original_r2_index=''))

    # Encode to memory first: PIL writing straight to atlas_path would truncate
    # the only copy of the atlas before it started, and a failure mid-encode
    # would leave a corrupt PNG behind.
    encoded = io.BytesIO()
    atlas.save(encoded, format='PNG', compress_level=9, optimize=False)
    replace_atomically(atlas_path, encoded.getvalue())
    write_csv(root / 'item_icons_cells.csv', CELL_FIELDS, cell_rows)
    write_csv(root / 'item_icons_index.csv', INDEX_FIELDS, index_rows)
    return {'added': len(pending), 'cells': len(cell_rows), 'index_rows': len(index_rows),
            'atlas': [atlas.width, atlas.height]}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: python tools/import_construction_icons.py <art-pack-dir>')
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(import_construction_icons(root, Path(sys.argv[1])), indent=2))
