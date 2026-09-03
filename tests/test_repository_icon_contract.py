import csv,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Contract(unittest.TestCase):
 def test_csv(self):
  icons=json.loads((ROOT/'gear_icons_manifest.json').read_text())['icons']
  with (ROOT/'gear_icons_manifest.csv').open(newline='',encoding='utf8') as handle:rows=list(csv.DictReader(handle))
  self.assertEqual(len(rows),1146);self.assertEqual([r['name'] for r in rows],[r['name'] for r in icons])
 def test_runtime(self):
  h=(ROOT/'index.html').read_text();self.assertNotIn('gear_icons_atlas.png?v=',h);self.assertNotIn('item_icons_atlas.png?v=',h);self.assertRegex(h,r'icon-manifest\.[0-9a-f]{12}\.json')
 def test_headers(self):
  h=(ROOT/'_headers').read_text();self.assertIn('max-age=31536000, immutable',h);self.assertIn('Cache-Control: no-cache',h)
if __name__=='__main__':unittest.main()
