"""Import raid artwork, preserving per-raid indexes and deterministic atlas sources."""
from __future__ import annotations
import hashlib
import io
import json
import math
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from atomic_write import replace_atomically
from build_icon_chunks import items_from
from import_construction_icons import read_csv, write_csv, CELL_FIELDS, INDEX_FIELDS
from sync_gear_manifest_csv import sync

ROOT = Path(__file__).resolve().parents[1]
RAIDS = ['ashmaw', 'thessaly', 'morwenna', 'grimjaw', 'skarth']


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=False, compress_level=9)
    return buffer.getvalue()


def normalise(source):
    with Image.open(source) as raw:
        image = raw.convert('RGBA')
        alpha = image.getchannel('A')
        if alpha.getextrema()[0] == 255:
            raise ValueError('Artwork must have transparency: ' + str(source))
        box = alpha.getbbox()
        if box is None:
            raise ValueError('Empty artwork: ' + str(source))
        image = image.crop(box)
        image.thumbnail((120, 120), Image.Resampling.LANCZOS)
        cell = Image.new('RGBA', (128, 128))
        cell.paste(image, ((128-image.width)//2, (128-image.height)//2))
        return cell


def expanded_atlas(path, count):
    with Image.open(path) as old:
        image = Image.new('RGBA', (1280, max(old.height, math.ceil(count/10)*128)))
        image.paste(old.convert('RGBA'), (0, 0))
        return image


def contact_sheet(records):
    (ROOT/'output').mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGBA', (1260, 1050), '#171c24')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=13)
    title_font = ImageFont.load_default(size=17)
    for row, raid in enumerate(RAIDS):
        top = row*210
        draw.text((12, top+5), raid.upper(), font=title_font, fill='#d4dce8')
        for column, record in enumerate(r for r in records if r['raid']==raid):
            left = column*180
            with Image.open(ROOT/record['path']) as icon:
                sheet.alpha_composite(icon.convert('RGBA'), (left+26, top+33))
            label = '\n'.join(textwrap.wrap(record['name'], width=23))
            draw.multiline_text((left+7, top+166), label, font=font, fill='#e4e8f0', spacing=2)
    replace_atomically(ROOT/'output/raid-artwork-preview.png', png_bytes(sheet))


def import_raids():
    manifest_path = ROOT/'raid_artwork_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'items': []}
    previous_by_id = {r['item_id']: r for r in previous['items']}
    record_path = ROOT/'tmp/raid-generation-records.json'
    if record_path.exists():
        records = json.loads(record_path.read_text(encoding='utf-8'))
    else:
        records = previous['items']
    prompts = {r.get('id', r.get('item_id')): r['prompt'] for r in records}
    raid_by_id = {r.get('id', r.get('item_id')): r['raid'] for r in records}
    items = [i for i in items_from((ROOT/'index.html').read_text(encoding='utf-8')) if i.get('item_id') in prompts]
    if len(items) != 35 or any(sum(raid_by_id[i['item_id']] == raid for i in items) != 7 for raid in RAIDS):
        raise ValueError('Expected 35 explicit raid item IDs, seven per raid')
    gear = json.loads((ROOT/'gear_icons_manifest.json').read_text(encoding='utf-8'))
    index = read_csv(ROOT/'item_icons_index.csv')
    cells = read_csv(ROOT/'item_icons_cells.csv')
    gear_names = {r['name'] for r in gear['icons']}
    item_ids = {r['item_id'] for r in index}
    next_gear = max(r['index'] for r in gear['icons']) + 1
    next_item = max(int(r['index']) for r in cells) + 1
    ga = expanded_atlas(ROOT/'gear_icons_atlas.png', next_gear + sum(i['category']=='Equipment' and i['name'] not in gear_names for i in items))
    ia = expanded_atlas(ROOT/'item_icons_atlas.png', next_item + sum(i['category']!='Equipment' and i['item_id'] not in item_ids for i in items))
    all_records = []
    for item in items:
        raid = raid_by_id[item['item_id']]
        relative = 'assets/raids/' + raid + '/' + item['item_id'] + '.png'
        source = ROOT/relative
        original = ROOT/'output/raid-artwork'/raid/source.name
        prior = previous_by_id.get(item['item_id'])
        if not original.exists() and prior:
            # A clean checkout carries the normalized art and provenance, but
            # not local full-size originals. Do not fabricate new originals.
            with Image.open(source) as raw:
                cell = raw.convert('RGBA')
                if cell.size != (128, 128) or cell.getchannel('A').getextrema()[0] == 255:
                    raise ValueError('Invalid normalized raid sprite: ' + relative)
            source_hash = prior['source_sha256_png']
            source_path = prior['source_path']
        else:
            original.parent.mkdir(parents=True, exist_ok=True)
            if not original.exists():
                replace_atomically(original, source.read_bytes())
            cell = normalise(original)
            source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
            source_path = original.relative_to(ROOT).as_posix()
        encoded = png_bytes(cell)
        replace_atomically(source, encoded)
        is_gear = item['category'] == 'Equipment'
        existing = next((r for r in gear['icons'] if r['name']==item['name']), None) if is_gear else next((r for r in index if r['item_id']==item['item_id']), None)
        ix = int(existing['index']) if existing else (next_gear if is_gear else next_item)
        row, column = divmod(ix, 10)
        geometry = dict(index=ix, row=row, column=column, x=column*128, y=row*128, width=128, height=128)
        if is_gear:
            ga.paste(cell, (geometry['x'], geometry['y']))
            if not existing:
                gear['icons'].append(dict(name=item['name'], **geometry))
                next_gear += 1
        else:
            ia.paste(cell, (geometry['x'], geometry['y']))
            art_source = 'generated raid unique 2026-10-05'
            if not existing:
                cells.append(dict(geometry, icon_key='item.'+item['item_id'], name=item['name'], group='trade.raid.'+raid, shared='False', usage_count='1', art_source=art_source, sha256_rgba=hashlib.sha256(cell.tobytes()).hexdigest()))
                index.append(dict(geometry, item_id=item['item_id'], name=item['name'], category=item['category'], subcategory=item.get('subcategory',''), tier=item.get('tier',''), group='trade.raid.'+raid, art_source=art_source, shared_icon_key='', original_r3_index='', original_r2_index=''))
                next_item += 1
            else:
                next(r for r in cells if int(r['index']) == ix)['sha256_rgba'] = hashlib.sha256(cell.tobytes()).hexdigest()
        all_records.append(dict(item_id=item['item_id'], name=item['name'], raid=raid, category=item['category'], subcategory=item.get('subcategory',''), path=relative, source_path=source_path, sha256_png=hashlib.sha256(encoded).hexdigest(), source_sha256_png=source_hash, atlas='gear' if is_gear else 'items', **geometry, prompt=prompts[item['item_id']]))
    gear['rows'] = ga.height//128
    gear['version'] = 10
    replace_atomically(ROOT/'gear_icons_atlas.png', png_bytes(ga))
    replace_atomically(ROOT/'item_icons_atlas.png', png_bytes(ia))
    replace_atomically(ROOT/'gear_icons_manifest.json', (json.dumps(gear, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    sync(ROOT)
    write_csv(ROOT/'item_icons_cells.csv', CELL_FIELDS, cells)
    write_csv(ROOT/'item_icons_index.csv', INDEX_FIELDS, index)
    for raid in RAIDS:
        payload = dict(version=1, raid=raid, items=[r for r in all_records if r['raid']==raid])
        replace_atomically(ROOT/'assets/raids'/raid/'index.json', (json.dumps(payload, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    manifest = dict(version=1, generated_at='2026-10-05', generator='built-in image_gen', item_data_source='https://idleworlds.com/items.json', item_data_generated_at='2026-10-05T03:26:31.108Z', cell_size=128, content_size=120, style='Painted fantasy gear with extravagant raid-unique silhouettes and contained elemental magic', raids={raid:'assets/raids/'+raid+'/index.json' for raid in RAIDS}, items=all_records)
    replace_atomically(ROOT/'raid_artwork_manifest.json', (json.dumps(manifest, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    contact_sheet(all_records)
    print(json.dumps(dict(raid_items=len(all_records), gear_icons=len(gear['icons']), item_cells=len(cells))))


if __name__ == '__main__':
    import_raids()
