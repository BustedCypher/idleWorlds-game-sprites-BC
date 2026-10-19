"""Append October profession/event sprites to the shared atlas build sources.

Full-size originals and generation.json may be supplied with --source-dir.
A clean checkout rebuilds from the normalized PNGs and saved provenance.
Existing cell coordinates remain stable; rerunning never appends duplicates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from atomic_write import replace_atomically
from import_construction_icons import normalise, read_csv, write_csv, CELL_FIELDS, INDEX_FIELDS
from import_raid_icons import png_bytes
from sync_gear_manifest_csv import sync

ROOT = Path(__file__).resolve().parents[1]
FOLDER = 'assets/item-expansions/october-2026-additions'
GEAR_IDS = ['deepvein_lodestone', 'emberheart_anvilstone', 'rimebloom_satchel',
            'stormwoven_grimoire', 'astral_loupe', 'cinderthread_spindle',
            'rimebark_charm', 'stormset_plumb_line', 'hollow_lantern']
KEY_ID = 'hollow_skeleton_key'


def save_json(path, data):
    replace_atomically(path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def geometry(index, position):
    row, column = divmod(position, 10)
    return dict(index=index, row=row, column=column, x=column*128, y=row*128, width=128, height=128)


def atlas_with_room(path, rows):
    with Image.open(path) as raw:
        image = Image.new('RGBA', (1280, max(raw.height, rows*128)))
        image.paste(raw.convert('RGBA'), (0, 0))
    return image


def import_icons(root=ROOT, source_dir=None):
    root = Path(root).resolve()
    folder = root/FOLDER
    data = json.loads((folder/'items.json').read_text(encoding='utf-8'))
    items = {item['item_id']: item for item in data['items']}
    manifest_path = root/'october_item_artwork_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'items': []}
    prior = {item['item_id']: item for item in previous['items']}
    jobs = {}
    if source_dir:
        source_dir = Path(source_dir).resolve()
        jobs = {job['id']: job for job in json.loads((source_dir/'generation.json').read_text(encoding='utf-8'))}
    gear = json.loads((root/'gear_icons_manifest.json').read_text(encoding='utf-8'))
    gear_by_name = {item['name']: item for item in gear['icons']}
    cells = read_csv(root/'item_icons_cells.csv')
    mappings = read_csv(root/'item_icons_index.csv')
    next_gear_position = max(item['row']*10+item['column'] for item in gear['icons'])+1
    next_gear_index = max(item['index'] for item in gear['icons'])+1
    pending_gear = [item_id for item_id in GEAR_IDS if items[item_id]['name'] not in gear_by_name]
    gear_atlas = atlas_with_room(root/'gear_icons_atlas.png', math.ceil((next_gear_position+len(pending_gear))/10))
    key_mapping = next((item for item in mappings if item['item_id']==KEY_ID), None)
    key_index = int(key_mapping['index']) if key_mapping else max(int(item['index']) for item in cells)+1
    item_atlas = atlas_with_room(root/'item_icons_atlas.png', math.ceil((key_index+1)/10))
    records = []
    for item_id in GEAR_IDS+[KEY_ID]:
        item = items[item_id]
        target = folder/(item_id+'.png')
        old = prior.get(item_id)
        if source_dir:
            source = source_dir/(item_id+'.png')
            cell = normalise(source)
            job = jobs[item_id]
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            source_path = source.relative_to(root).as_posix() if source.is_relative_to(root) else source.as_posix()
            prompt = job['prompt']
        elif old:
            with Image.open(target) as raw:
                cell = raw.convert('RGBA')
            if cell.size!=(128,128) or cell.getchannel('A').getextrema()[0]==255:
                raise ValueError('Invalid normalized sprite: '+item_id)
            source_hash, source_path, prompt = old['source_sha256_png'], old['source_path'], old['prompt']
        else:
            raise ValueError('Missing original or saved provenance: '+item_id)
        if not cell.getchannel('A').getbbox():
            raise ValueError('Empty sprite: '+item_id)
        encoded = png_bytes(cell)
        replace_atomically(target, encoded)
        if item_id in GEAR_IDS:
            entry = gear_by_name.get(item['name'])
            if entry is None:
                entry = dict(name=item['name'], **geometry(next_gear_index, next_gear_position))
                gear['icons'].append(entry)
                next_gear_index += 1
                next_gear_position += 1
            gear_atlas.paste(cell, (entry['x'], entry['y']))
            atlas_name = 'gear_icons_atlas.png'
        else:
            entry = geometry(key_index, key_index)
            item_atlas.paste(cell, (entry['x'], entry['y']))
            atlas_name = 'item_icons_atlas.png'
            cell_row = dict(entry, icon_key='item.'+item_id, name=item['name'], group='trade.hollow_night',
                            shared='False', usage_count='1', art_source='built-in image_gen 2026-10-19',
                            sha256_rgba=hashlib.sha256(cell.tobytes()).hexdigest())
            cells = [row for row in cells if int(row['index'])!=key_index]+[cell_row]
            mapping = dict(entry, item_id=item_id, name=item['name'], category=item['category'],
                           subcategory=item['subcategory'], tier=item['tier'], group='trade.hollow_night',
                           art_source='built-in image_gen 2026-10-19', shared_icon_key='',
                           original_r3_index='', original_r2_index='')
            mappings = [row for row in mappings if row['item_id']!=item_id]+[mapping]
        record = {key: entry[key] for key in ['index','row','column','x','y','width','height']}
        records.append(dict(record, item_id=item_id, name=item['name'], category=item['category'],
                            path=target.relative_to(root).as_posix(), atlas_path=atlas_name,
                            source_path=source_path, source_sha256_png=source_hash,
                            sha256_png=hashlib.sha256(encoded).hexdigest(),
                            sha256_rgba=hashlib.sha256(cell.tobytes()).hexdigest(), prompt=prompt))
    gear.update(version=10, rows=gear_atlas.height//128, asset_version='2x-2026-10-19-profession-hollow-items')
    replace_atomically(root/'gear_icons_atlas.png', png_bytes(gear_atlas))
    replace_atomically(root/'item_icons_atlas.png', png_bytes(item_atlas))
    save_json(root/'gear_icons_manifest.json', gear)
    sync(root)
    write_csv(root/'item_icons_cells.csv', CELL_FIELDS, cells)
    write_csv(root/'item_icons_index.csv', INDEX_FIELDS, mappings)
    shared = [dict(item_id=item['item_id'], name=item['name'], source_item_id='hollow_scroll')
              for item in data['items'] if item['item_id'].startswith('hollow_scroll_')]
    result = dict(version=1, generated_at='2026-10-19', generator='built-in image_gen',
                  cell_size=128, content_size=112, source=data['source'],
                  source_generated_at=data['source_generated_at'], items=records, shared_items=shared)
    save_json(manifest_path, result)
    sheet = Image.new('RGBA', (1000, 410), '#171c24')
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        left, top = index%5*200, index//5*205
        with Image.open(root/record['path']) as image:
            sheet.alpha_composite(image.convert('RGBA'), (left+36, top+15))
        draw.multiline_text((left+10, top+155), '\n'.join(textwrap.wrap(record['name'], 23)),
                            font=ImageFont.load_default(size=13), fill='#e4e8f0')
    (root/'output').mkdir(exist_ok=True)
    replace_atomically(root/'output/october-item-additions-preview.png', png_bytes(sheet))
    return {'gear_icons':len(gear['icons']), 'item_cells':len(cells), 'new_sprites':len(records), 'shared_scrolls':len(shared)}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args()
    print(json.dumps(import_icons(args.root, args.source_dir)))
