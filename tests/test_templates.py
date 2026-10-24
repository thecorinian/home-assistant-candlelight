"""Exercise the shipped Jinja templates without connecting to any lights."""
import ast
import math
import random
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import yaml
from jinja2.nativetypes import NativeEnvironment
from jinja2 import pass_context

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = yaml.safe_load((ROOT / 'scripts/natural_candlelight.yaml').read_text())
LOOP = next(a['repeat'] for a in SCRIPT['sequence'] if 'repeat' in a and 'while' in a['repeat'])
INNER = next(a['repeat']['sequence'][0]['then'] for a in LOOP['sequence'] if 'repeat' in a)
LEVEL = next(a['variables']['level'] for a in INNER if 'level' in a.get('variables', {}))
BASELINE = next(a['variables']['baseline'] for a in INNER if 'baseline' in a.get('variables', {}))
GUSTS = next(a['then'][0]['variables']['gust_events'] for a in LOOP['sequence'] if 'gust_events' in a.get('then', [{}])[0].get('variables', {}))
BASELINE_CHANGE = next(a['then'][0]['variables'] for a in LOOP['sequence'] if 'baseline_target' in a.get('then', [{}])[0].get('variables', {}))
FILTER = SCRIPT['sequence'][1]['variables']['bulbs']

def bulb(name,state='on',modes=('color_temp',)):
 return NS(entity_id='light.'+name, domain='light',state=state,attributes={'supported_color_modes':list(modes)})

class Templates(unittest.TestCase):
 def setUp(self):
  self.lights=[bulb('a'),bulb('b','off'),bulb('dead','unavailable'),bulb('switch',modes=['onoff'])]
  self.env=NativeEnvironment()
  self.compiled={}
  self.env.globals.update(sin=math.sin,log=math.log,states=NS(light=self.lights),as_timestamp=lambda x:x,now=lambda:0,
   expand=lambda ids:[x for x in self.lights if x.entity_id in ids])
 def render(self,t,**kw):
  if t not in self.compiled: self.compiled[t]=self.env.from_string(t)
  kw.setdefault('baseline',80)
  kw.setdefault('baseline_blend_seconds',20)
  result=self.compiled[t].render(**kw)
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

 def test_baseline_blend_is_continuous_and_monotonic(self):
  for old,new in [(80,50),(50,80),(70,50),(80,80)]:
   values=[]
   for t in [0,2.5,5,10,15,17.5,20,40,200]:
    self.env.globals['now']=lambda:t
    values.append(self.render(BASELINE,started=0,baseline_changed=0,baseline_from=old,baseline_target=new))
   self.assertEqual(values[0],old)
   self.assertEqual(values[3],(old+new)/2)
   self.assertEqual(values[-3:],[new,new,new])
   self.assertEqual(values,sorted(values,reverse=new<old))
 def test_weighted_dwell_time_matches_requested_shares(self):
  rng=random.Random(7391)
  self.env.filters['random']=pass_context(lambda context,seq:rng.choice(list(seq)))
  totals={80:0,70:0,50:0}
  for _ in range(10000):
   target=self.render(BASELINE_CHANGE['baseline_target'])
   fade=self.render(BASELINE_CHANGE['baseline_blend_seconds'])
   self.assertGreaterEqual(fade,15)
   self.assertLessEqual(fade,30)
   dwell=self.render(BASELINE_CHANGE['baseline_next'],elapsed=0,baseline_blend_seconds=fade)-fade
   self.assertGreaterEqual(dwell,30)
   self.assertLessEqual(dwell,180)
   totals[target]+=dwell
  total=sum(totals.values())
  for target,expected in [(80,.5),(70,.25),(50,.25)]:
   self.assertAlmostEqual(totals[target]/total,expected,delta=.015)
 def test_low_baselines_preserve_flicker_and_bounds(self):
  levels=[]
  for baseline in [50,70,80]:
   self.env.globals['now']=lambda:0
   levels.append(self.render(LEVEL,started=0,seed=.7,repeat=NS(item='light.a'),gust_events=[],baseline=baseline))
   for t in [5+x*.2 for x in range(100)]:
    self.env.globals['now']=lambda:t
    value=self.render(LEVEL,started=0,seed=.7,repeat=NS(item='light.a'),gust_events=[[5,100,2.3,0]],baseline=baseline)
    self.assertGreaterEqual(value,25)
    self.assertLessEqual(value,100)
  self.assertEqual(levels[1]-levels[0],20)
  self.assertEqual(levels[2]-levels[1],10)

if __name__=='__main__': unittest.main()
