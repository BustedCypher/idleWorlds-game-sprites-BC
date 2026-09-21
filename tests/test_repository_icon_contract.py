import csv,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Contract(unittest.TestCase):
 def test_csv(self):
  icons=json.loads((ROOT/'gear_icons_manifest.json').read_text(encoding='utf-8'))['icons']
  with (ROOT/'gear_icons_manifest.csv').open(newline='',encoding='utf8') as handle:rows=list(csv.DictReader(handle))
  self.assertEqual(len(rows),1160);self.assertEqual([r['name'] for r in rows],[r['name'] for r in icons])
 def test_rimewrought_drop_pool_has_data_and_artwork(self):
  expected={"Rimewrought Greatblade","Glacial Bulwark","Sentinel's Frosted Plate","Coronet of the Rime Court","Frostforge Gauntlets","Band of the Unbroken Frost","Wanderer's Frozen Pendant","Glacier's Last Gasp"}
  h=(ROOT/'index.html').read_text(encoding='utf-8')
  embedded=json.loads(re.search(r'<script[^>]*id=["\']iw-embedded-items["\'][^>]*>([\s\S]*?)</script>',h,re.I).group(1))
  items=embedded if isinstance(embedded,list) else embedded['items']
  icons=json.loads((ROOT/'gear_icons_manifest.json').read_text(encoding='utf-8'))['icons']
  self.assertEqual(len(items),4466)
  self.assertEqual({i['name'] for i in items if i.get('item_id') in {'rimewrought_greatblade','glacial_bulwark','sentinels_frosted_plate','coronet_of_the_rime_court','frostforge_gauntlets','band_of_the_unbroken_frost','wanderers_frozen_pendant','glaciers_last_gasp'}},expected)
  self.assertTrue(expected.issubset({i['name'] for i in icons}))
 def test_runtime(self):
  h=(ROOT/'index.html').read_text(encoding='utf-8');self.assertNotIn('gear_icons_atlas.png?v=',h);self.assertNotIn('item_icons_atlas.png?v=',h);self.assertRegex(h,r'icon-manifest\.[0-9a-f]{12}\.json')
 def test_headers(self):
  h=(ROOT/'_headers').read_text(encoding='utf-8');self.assertIn('max-age=31536000, immutable',h);self.assertIn('Cache-Control: no-cache',h)
if __name__=='__main__':unittest.main()
