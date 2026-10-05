"""A rebuild without local originals must retain the recorded provenance."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import import_raid_icons as importer
from atomic_write import replace_atomically
from import_construction_icons import write_csv, CELL_FIELDS, INDEX_FIELDS


class RaidImport(unittest.TestCase):
    def test_rebuild_without_local_originals_preserves_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new('RGBA', (128, 128))
            image.paste((200, 100, 40, 255), (8, 8, 120, 120))
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            sprite = buffer.getvalue()
            items, records = [], []
            for raid in importer.RAIDS:
                folder = root/'assets/raids'/raid
                folder.mkdir(parents=True)
                for number in range(7):
                    item_id = raid + '_' + str(number)
                    relative = 'assets/raids/' + raid + '/' + item_id + '.png'
                    replace_atomically(root/relative, sprite)
                    items.append(dict(item_id=item_id, name=item_id, category='Equipment' if number<6 else 'Trade Good', subcategory='Helmet slot' if number<6 else 'Trade good'))
                    records.append(dict(item_id=item_id, raid=raid, prompt='test fixture', path=relative, source_path='output/raid-artwork/'+raid+'/'+item_id+'.png', source_sha256_png='a'*64))
            replace_atomically(root/'index.html', ('<script id="iw-embedded-items">'+json.dumps(dict(items=items))+'</script>').encode('utf-8'))
            replace_atomically(root/'raid_artwork_manifest.json', json.dumps(dict(items=records)).encode('utf-8'))
            old = dict(name='old', index=0, row=0, column=0, x=0, y=0, width=128, height=128)
            replace_atomically(root/'gear_icons_manifest.json', json.dumps(dict(icons=[old])).encode('utf-8'))
            for filename in ['gear_icons_atlas.png', 'item_icons_atlas.png']:
                replace_atomically(root/filename, importer.png_bytes(Image.new('RGBA', (1280, 128))))
            write_csv(root/'item_icons_cells.csv', CELL_FIELDS, [dict(index=0, row=0, column=0, x=0, y=0, width=128, height=128, icon_key='old')])
            write_csv(root/'item_icons_index.csv', INDEX_FIELDS, [dict(item_id='old', index=0)])
            shared_names = ['gear_icons_atlas.png', 'gear_icons_manifest.json', 'item_icons_atlas.png', 'item_icons_cells.csv', 'item_icons_index.csv']
            shared_before = {name: (root/name).read_bytes() for name in shared_names}
            previous_root = importer.ROOT
            importer.ROOT = root
            try:
                importer.import_raids()
            finally:
                importer.ROOT = previous_root
            rebuilt = json.loads((root/'raid_artwork_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual([r['source_sha256_png'] for r in rebuilt['items']], ['a'*64]*35)
            self.assertFalse((root/'output/raid-artwork').exists(), 'must not fabricate originals from normalized sprites')
            self.assertEqual(shared_before, {name: (root/name).read_bytes() for name in shared_names}, 'raid imports must never change shared atlases')
            self.assertEqual(len(rebuilt['atlases']), 5)


if __name__ == '__main__':
    unittest.main()
