"""Exercise the shipped Jinja templates without connecting to any lights."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import yaml
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = yaml.safe_load((ROOT / 'scripts/natural_candlelight.yaml').read_text())
LOOP = next(a['repeat'] for a in SCRIPT['sequence'] if 'repeat' in a and 'while' in a['repeat'])
LEVEL = LOOP['sequence'][4]['repeat']['sequence'][0]['then'][1]['variables']['level']
GUSTS = LOOP['sequence'][3]['then'][0]['variables']['gust_events']
FILTER = SCRIPT['sequence'][1]['variables']['bulbs']

def bulb(name,state='on',modes=('color_temp',)):
 return NS(entity_id='light.'+name, domain='light',state=state,attributes={'supported_color_modes':list(modes)})

class Templates(unittest.TestCase):
 def setUp(self):
  self.lights=[bulb('a'),bulb('b','off'),bulb('dead','unavailable'),bulb('switch',modes=['onoff'])]
  self.env=NativeEnvironment()
  self.env.globals.update(sin=math.sin,log=math.log,states=NS(light=self.lights),as_timestamp=lambda x:x,now=lambda:0,
   expand=lambda ids:[x for x in self.lights if x.entity_id in ids])
 def render(self,t,**kw):
  result=self.env.from_string(t).render(**kw)
  return ast.literal_eval(result.strip()) if isinstance(result,str) else result
 def test_only_on_never_selects_off_or_unavailable(self):
  self.assertEqual(self.render(FILTER,requested=[],only_lit=True,excluded_lights=[]),['light.a'])
  self.assertEqual(self.render(FILTER,requested=[],only_lit=True,excluded_lights=['light.a']),[])
 def test_manual_selection_and_dimming_filter(self):
  self.assertEqual(self.render(FILTER,requested=[],only_lit=False,excluded_lights=[]),['light.a','light.b'])
  self.assertEqual(self.render(FILTER,requested=['light.b'],only_lit=False,excluded_lights=[]),['light.b'])
 def test_extending_schedule_retains_active_tails_and_event_identity(self):
  events=[[95,70,2,11],[105,80,2.7,12]]
  result=self.render(GUSTS,elapsed=100,gust_events=events)
  self.assertEqual(result[:2],events)
  self.assertEqual(result[2][3],13)
  self.assertTrue(all(b[0]-a[0]>4 for a,b in zip(result,result[1:])))
  self.assertTrue(all(55<=e[1]<=100 and 1.7<=e[2]<=2.9 for e in result))
 def test_rolling_schedule_prunes_expired_events(self):
  result=self.render(GUSTS,elapsed=500,gust_events=[[0,70,2,0],[495,70,2,1],[505,70,2,2]])
  self.assertNotIn([0,70,2,0],result)
  self.assertEqual(result[0][3],1)
 def test_brightness_bounds_and_distinct_flames(self):
  events=[[t,100,2.3,i] for i,t in enumerate(range(5,300,9))]
  values=[]
  for t in [x*.2 for x in range(1500)]:
   self.env.globals['now']=lambda:t
   values.append(self.render(LEVEL,started=0,seed=.7,repeat=NS(item='light.a'),gust_events=events))
  self.assertGreaterEqual(min(values),25)
  self.assertLessEqual(max(values),100)
  self.assertLess(min(values),45)
  self.assertEqual(max(values),100)
  self.assertGreater(sum(values)/len(values),60)
  self.assertLess(sum(values)/len(values),85)
  self.env.globals['now']=lambda:10
  a=self.render(LEVEL,started=0,seed=.7,repeat=NS(item='light.a'),gust_events=events)
  b=self.render(LEVEL,started=0,seed=.7,repeat=NS(item='light.b'),gust_events=events)
  self.assertNotEqual(a,b)

if __name__=='__main__': unittest.main()
