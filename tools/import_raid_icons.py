"""Import raid artwork, preserving per-raid indexes and deterministic atlas sources."""
from __future__ import annotations
import hashlib
import io
import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from atomic_write import replace_atomically
from build_icon_chunks import items_from

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
        ix = sum(r['raid'] == raid for r in all_records)
        row, column = divmod(ix, 7)
        geometry = dict(index=ix, row=row, column=column, x=column*128, y=row*128, width=128, height=128)
        all_records.append(dict(item_id=item['item_id'], name=item['name'], raid=raid, category=item['category'], subcategory=item.get('subcategory',''), path=relative, source_path=source_path, sha256_png=hashlib.sha256(encoded).hexdigest(), source_sha256_png=source_hash, atlas='raid:'+raid, **geometry, prompt=prompts[item['item_id']]))
    atlases = {}
    for raid in RAIDS:
        records = [r for r in all_records if r['raid']==raid]
        sheet = Image.new('RGBA', (896, 128))
        for record in records:
            with Image.open(ROOT/record['path']) as icon:
                sheet.paste(icon.convert('RGBA'), (record['x'], record['y']))
        data = png_bytes(sheet)
        digest = hashlib.sha256(data).hexdigest()
        relative = 'assets/raids/'+raid+'/atlas.'+digest[:12]+'.png'
        replace_atomically(ROOT/relative, data)
        atlases[raid] = dict(path=relative, sha256_png=digest, width=896, height=128, columns=7, rows=1, cell_count=7)
        for record in records:
            record['atlas_path'] = relative
        payload = dict(version=2, raid=raid, atlas=atlases[raid], items=records)
        replace_atomically(ROOT/'assets/raids'/raid/'index.json', (json.dumps(payload, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    manifest = dict(version=1, generated_at='2026-10-05', generator='built-in image_gen', item_data_source='https://idleworlds.com/items.json', item_data_generated_at='2026-10-05T03:26:31.108Z', cell_size=128, content_size=120, style='Painted fantasy gear with extravagant raid-unique silhouettes and contained elemental magic', raids={raid:'assets/raids/'+raid+'/index.json' for raid in RAIDS}, items=all_records)
    manifest.update(version=2, atlases=atlases)
    replace_atomically(ROOT/'raid_artwork_manifest.json', (json.dumps(manifest, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    contact_sheet(all_records)
    print(json.dumps(dict(raid_items=len(all_records), raid_atlases=len(atlases))))


if __name__ == '__main__':
    import_raids()
