"""Import the 28 Raidforged icons and four October items into separate atlases."""
from __future__ import annotations
import argparse
import hashlib
import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from atomic_write import replace_atomically
from build_icon_chunks import items_from
from import_raid_icons import normalise, png_bytes

ROOT = Path(__file__).resolve().parents[1]
SETS = ['cinderforged', 'stormforged', 'hollowforged', 'anchorforged']
SLOTS = ['blade', 'bulwark', 'helm', 'breastplate', 'gauntlets', 'greaves', 'sabatons']
OTHER = ['welcome_back_xp_potion', 'premium_token', 'hollow_candy', 'hollow_scroll']
GROUPS = {group: [group+'_'+slot for slot in SLOTS] for group in SETS}
GROUPS['october-items'] = OTHER
EXPECTED = {item_id for ids in GROUPS.values() for item_id in ids}


def save_json(path, value):
    replace_atomically(path, (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))


def preview(root, records):
    sheet = Image.new('RGBA', (1260, 1050), '#171c24')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=13)
    title = ImageFont.load_default(size=17)
    for row, group in enumerate(GROUPS):
        top = row*210
        draw.text((12, top+5), group.upper(), font=title, fill='#d4dce8')
        for col, record in enumerate(r for r in records if r['group']==group):
            with Image.open(root/record['path']) as icon:
                sheet.alpha_composite(icon.convert('RGBA'), (col*180+26, top+33))
            draw.multiline_text((col*180+7, top+166), '\n'.join(textwrap.wrap(record['name'], 23)), font=font, fill='#e4e8f0')
    (root/'output').mkdir(exist_ok=True)
    replace_atomically(root/'output/raidforged-artwork-preview.png', png_bytes(sheet))


def import_artwork(root=ROOT):
    root = Path(root)
    manifest_path = root/'raidforged_artwork_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'items': []}
    prior = {r['item_id']: r for r in previous['items']}
    pending = {}
    for path in sorted((root/'tmp/raidforged-generated').glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record['id'] in EXPECTED:
            pending[record['id']] = record
    if set(prior) | set(pending) != EXPECTED:
        raise ValueError('Missing artwork: '+', '.join(sorted(EXPECTED-set(prior)-set(pending))))
    items = {i['item_id']: i for i in items_from((root/'index.html').read_text(encoding='utf-8'))}
    if not EXPECTED.issubset(items):
        raise ValueError('Artwork item IDs do not match the embedded database')
    records, atlases, indexes = [], {}, {}
    for group, ids in GROUPS.items():
        gear = group in SETS
        chunk = ('raidforged:' if gear else 'expansion:')+group
        folder = root/('assets/raidforged' if gear else 'assets/item-expansions')/group
        folder.mkdir(parents=True, exist_ok=True)
        sheet = Image.new('RGBA', (len(ids)*128, 128))
        group_records = []
        for index, item_id in enumerate(ids):
            item = items[item_id]
            source = root/'output/raidforged-artwork'/group/(item_id+'.png')
            target = folder/(item_id+'.png')
            old = prior.get(item_id)
            job = pending.get(item_id)
            if job:
                generated = Path(job['generated_path'])
                source.parent.mkdir(parents=True, exist_ok=True)
                replace_atomically(source, generated.read_bytes())
            if source.exists():
                cell = normalise(source)
                source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                source_path = source.relative_to(root).as_posix()
            elif old:
                with Image.open(target) as raw:
                    cell = raw.convert('RGBA')
                if cell.size != (128, 128) or cell.getchannel('A').getextrema()[0] == 255:
                    raise ValueError('Invalid normalized sprite: '+item_id)
                source_hash, source_path = old['source_sha256_png'], old['source_path']
            else:
                raise ValueError('Missing original: '+item_id)
            encoded = png_bytes(cell)
            replace_atomically(target, encoded)
            sheet.paste(cell, (index*128, 0))
            record = dict(item_id=item_id, name=item['name'], group=group,
                category=item['category'], subcategory=item.get('subcategory', ''),
                path=target.relative_to(root).as_posix(), source_path=source_path,
                source_sha256_png=source_hash, sha256_png=hashlib.sha256(encoded).hexdigest(),
                atlas=chunk, index=index, row=0, column=index, x=index*128, y=0,
                width=128, height=128, prompt=job['prompt'] if job else old['prompt'])
            group_records.append(record)
        data = png_bytes(sheet)
        digest = hashlib.sha256(data).hexdigest()
        atlas = folder/('atlas.'+digest[:12]+'.png')
        replace_atomically(atlas, data)
        meta = dict(path=atlas.relative_to(root).as_posix(), sha256_png=digest,
            width=sheet.width, height=128, columns=len(ids), rows=1, cell_count=len(ids))
        for record in group_records:
            record['atlas_path'] = meta['path']
        index_path = folder/'index.json'
        save_json(index_path, dict(version=1, group=group, atlas=meta, items=group_records))
        atlases[chunk] = meta
        indexes[chunk] = index_path.relative_to(root).as_posix()
        records.extend(group_records)
    payload = dict(version=1, generated_at='2026-10-15', generator='built-in image_gen',
        cell_size=128, content_size=120, atlases=atlases, indexes=indexes, items=records)
    save_json(manifest_path, payload)
    preview(root, records)
    print(json.dumps(dict(items=len(records), atlases=len(atlases))))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    import_artwork(parser.parse_args().root)
