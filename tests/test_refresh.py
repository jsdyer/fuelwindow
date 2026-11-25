import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import ROOT,ns_html,pei_html,collect,validate
FIX=Path(__file__).parent/'fixtures'
class RefreshTests(unittest.TestCase):
 def setUp(self):
  self.config=json.loads((ROOT/'config/sources.json').read_text());self.bodies={'ns':(FIX/'ns.html').read_bytes(),'pei':(FIX/'pei.html').read_bytes()};self.fetch=lambda url:self.bodies['ns' if 'nserbt' in url else 'pei']
 def test_real_source_excerpts_parse_all_zones_and_units(self):
  ns=ns_html(self.bodies['ns'].decode());pei=pei_html(self.bodies['pei'].decode());validate(ns,12);validate(pei,9)
  self.assertEqual(len({r['zone'] for r in ns}),6);self.assertEqual(ns[0]['min'],156);self.assertEqual(ns[-1]['max'],230.8)
  oil=next(r for r in pei if r['fuel']=='furnace');self.assertEqual(oil['max'],179.1);self.assertIsNone(oil['min']);self.assertEqual(oil['effective_date'],'2026-11-24')
  regular=next(r for r in pei if r['fuel']=='regular' and r['service']=='self');self.assertEqual(regular['published_change'],-3.5);self.assertEqual(regular['change_basis'],'minimum')
 def test_partial_failure_preserves_prices_and_check_time(self):
  old,_=collect(self.config,fetch=self.fetch,now='2026-11-24T12:00:00+00:00')
  self.bodies['pei']=b'<h1>Temporarily unavailable</h1>'
  new,failed=collect(self.config,old,self.fetch,now='2026-11-25T12:00:00+00:00')
  self.assertEqual(failed,['pei']);self.assertEqual(new['sources'][1]['checked_at'],old['sources'][1]['checked_at']);self.assertEqual(new['sources'][1]['prices'],old['sources'][1]['prices']);self.assertEqual(new['sources'][1]['status'],'retained');self.assertEqual(new['sources'][0]['checked_at'],'2026-11-25T12:00:00+00:00')
 def test_initial_failure_rejects_and_same_edition_does_not_duplicate_history(self):
  with self.assertRaises(RuntimeError):collect(self.config,fetch=lambda url:b'404')
  old,_=collect(self.config,fetch=self.fetch);new,_=collect(self.config,old,self.fetch);self.assertEqual(len(new['history']),2)
 def test_missing_zone_and_bad_price_are_rejected(self):
  with self.assertRaises(ValueError):ns_html(self.bodies['ns'].decode().replace('Zone 6','Zone 7'))
  rows=ns_html(self.bodies['ns'].decode());rows[0]['min']=999
  with self.assertRaises(ValueError):validate(rows,12)
 def test_history_keeps_earlier_coverage_and_bounds_each_source(self):
  cfg=copy.deepcopy(self.config);cfg['history_limit']=2
  old,_=collect(cfg,fetch=self.fetch)
  for day in [25,26,27]:
   self.bodies['ns']=self.bodies['ns'].replace(f'November {day-1},'.encode(),f'November {day},'.encode())
   old,_=collect(cfg,old,self.fetch)
  self.assertEqual(len([h for h in old['history'] if h['source']=='ns']),2);self.assertEqual(len([h for h in old['history'] if h['source']=='pei']),1)
 def test_published_snapshot_row_counts_are_honest(self):
  s=json.loads((ROOT/'web/data/prices.json').read_text());self.assertEqual(s['row_count'],sum(len(x['prices']) for x in s['sources']))
if __name__=='__main__':unittest.main()
