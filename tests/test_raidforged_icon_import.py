"""Independent expansion rebuilds preserve source provenance and shared files."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from atomic_write import replace_atomically
from import_raid_icons import png_bytes
from import_raidforged_icons import GROUPS, import_artwork


class ExpansionImport(unittest.TestCase):
    def test_clean_checkout_rebuild_is_isolated_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items, records = [], []
            for group, ids in GROUPS.items():
                gear = group != 'october-items'
                folder = root/('assets/raidforged' if gear else 'assets/item-expansions')/group
                folder.mkdir(parents=True)
                for item_id in ids:
                    image = Image.new('RGBA', (128, 128))
                    image.paste((100, 200, 250, 255), (8, 8, 120, 120))
                    path = folder/(item_id+'.png')
                    replace_atomically(path, png_bytes(image))
                    items.append(dict(item_id=item_id, name=item_id, category='Equipment' if gear else 'Consumable'))
                    records.append(dict(item_id=item_id, prompt='fixture', source_path='output/raidforged-artwork/'+group+'/'+item_id+'.png', source_sha256_png='a'*64))
            shared = ['gear_icons_atlas.png', 'item_icons_atlas.png', 'gear_icons_manifest.json']
            for name in shared:
                replace_atomically(root/name, b'untouched fixture')
            replace_atomically(root/'index.html', ('<script id="iw-embedded-items">'+json.dumps(dict(items=items))+'</script>').encode())
            replace_atomically(root/'raidforged_artwork_manifest.json', json.dumps(dict(items=records)).encode())
            before = {name: (root/name).read_bytes() for name in shared}
            result = import_artwork(root)
            self.assertEqual(before, {name: (root/name).read_bytes() for name in shared})
            self.assertEqual(len(result['items']), 32)
            self.assertEqual(len(result['atlases']), 5)
            self.assertEqual({r['source_sha256_png'] for r in result['items']}, {'a'*64})
            self.assertFalse((root/'output/raidforged-artwork').exists())
            for meta in result['atlases'].values():
                self.assertEqual(hashlib.sha256((root/meta['path']).read_bytes()).hexdigest(), meta['sha256_png'])


if __name__ == '__main__':
    unittest.main()
