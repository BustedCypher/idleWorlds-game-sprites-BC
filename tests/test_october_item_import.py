"""A clean checkout can append the new sprites without moving existing art."""
import contextlib
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from atomic_write import replace_atomically
from import_construction_icons import read_csv, write_csv, CELL_FIELDS, INDEX_FIELDS
from import_october_item_icons import import_icons, FOLDER, GEAR_IDS, KEY_ID


def cell_hashes(path, records):
    with Image.open(path) as raw:
        image = raw.convert('RGBA')
        return [hashlib.sha256(image.crop((int(row['x']), int(row['y']),
                int(row['x'])+128, int(row['y'])+128)).tobytes()).hexdigest() for row in records]


class OctoberItemImport(unittest.TestCase):
    def test_clean_rebuild_preserves_old_cells_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['gear_icons_atlas.png', 'gear_icons_manifest.json', 'gear_icons_manifest.csv',
                         'item_icons_atlas.png', 'item_icons_cells.csv', 'item_icons_index.csv',
                         'october_item_artwork_manifest.json']:
                shutil.copy2(ROOT/name, root/name)
            shutil.copytree(ROOT/FOLDER, root/FOLDER)
            additions = json.loads((root/FOLDER/'items.json').read_text(encoding='utf-8'))
            new_names = {item['name'] for item in additions['items'] if item['item_id'] in GEAR_IDS}
            gear = json.loads((root/'gear_icons_manifest.json').read_text(encoding='utf-8'))
            gear['icons'] = [row for row in gear['icons'] if row['name'] not in new_names]
            replace_atomically(root/'gear_icons_manifest.json', json.dumps(gear).encode('utf-8'))
            mappings = [row for row in read_csv(root/'item_icons_index.csv') if row['item_id']!=KEY_ID]
            cells = [row for row in read_csv(root/'item_icons_cells.csv') if row['icon_key']!='item.'+KEY_ID]
            write_csv(root/'item_icons_index.csv', INDEX_FIELDS, mappings)
            write_csv(root/'item_icons_cells.csv', CELL_FIELDS, cells)
            old_gear = cell_hashes(root/'gear_icons_atlas.png', gear['icons'])
            old_items = cell_hashes(root/'item_icons_atlas.png', cells)
            result = import_icons(root)
            self.assertEqual(result['gear_icons'], len(gear['icons'])+9)
            self.assertEqual(result['item_cells'], len(cells)+1)
            self.assertEqual(cell_hashes(root/'gear_icons_atlas.png', gear['icons']), old_gear)
            self.assertEqual(cell_hashes(root/'item_icons_atlas.png', cells), old_items)
            before = {path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in root.rglob('*') if path.is_file()}
            self.assertEqual(import_icons(root), result)
            after = {path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in root.rglob('*') if path.is_file()}
            self.assertEqual(after, before)
            # The documented CLI form is relative to the invocation directory.
            originals = root/'originals'
            originals.mkdir()
            manifest = json.loads((root/'october_item_artwork_manifest.json').read_text(encoding='utf-8'))
            jobs = []
            for item in manifest['items']:
                shutil.copy2(root/item['path'], originals/(item['item_id']+'.png'))
                jobs.append({'id': item['item_id'], 'prompt': item['prompt']})
            replace_atomically(originals/'generation.json', json.dumps(jobs).encode('utf-8'))
            with contextlib.chdir(root):
                self.assertEqual(import_icons(root, Path('originals')), result)
            self.assertEqual(cell_hashes(root/'gear_icons_atlas.png', gear['icons']), old_gear)
            self.assertEqual(cell_hashes(root/'item_icons_atlas.png', cells), old_items)


if __name__=='__main__':
    unittest.main()
