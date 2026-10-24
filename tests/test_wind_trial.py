"""Verify the optional wind model without operating any real bulbs."""
from types import SimpleNamespace as NS
import yaml
import unittest
import test_templates
ROOT=test_templates.ROOT

TRIAL=yaml.safe_load((ROOT/'experiments/candlelight_wind_trial.yaml').read_text())
INIT=next(a['variables'] for a in TRIAL['sequence'] if 'wind_next' in a.get('variables',{}))
LOOP=next(a['repeat'] for a in TRIAL['sequence'] if 'repeat' in a and 'while' in a['repeat'])
BURST=next(a['then'] for a in LOOP['sequence'] if 'burst_baseline' in a.get('then',[{}])[0].get('variables',{}))
PULSE=BURST[2]['repeat']['sequence']
INNER=next(a['repeat']['sequence'][0]['then'] for a in LOOP['sequence'] if 'repeat' in a)
RAW=next(a['variables']['raw_level'] for a in INNER if 'raw_level' in a.get('variables',{}))
SMOOTH=next(a['variables']['level'] for a in INNER if 'level' in a.get('variables',{}))
CACHE=next(a['variables']['last_levels'] for a in INNER if 'last_levels' in a.get('variables',{}))

class Wind(unittest.TestCase):
 setUp=test_templates.Templates.setUp
 render=test_templates.Templates.render
 def test_wind_schedule_leaves_long_variable_quiet_gaps(self):
  rng=test_templates.random.Random(91)
  self.env.filters['random']=test_templates.pass_context(lambda context,seq:rng.choice(list(seq)))
  self.env.globals['now']=lambda:200
  gaps=[]
  for _ in range(1000):
   opening=self.render(INIT['wind_next'])
   self.assertTrue(8<=opening<=14)
   gaps.append(self.render(BURST[3]['variables']['wind_next'],started=0)-200)
  self.assertTrue(all(45<=gap<=150 for gap in gaps))
  self.assertGreater(len(set(gaps)),90)
  self.assertGreater(sum(gaps)/len(gaps),90)
 def test_triplets_have_soft_edges_and_varied_bounded_depths(self):
  rng=test_templates.random.Random(121)
  self.env.filters['random']=test_templates.pass_context(lambda context,seq:rng.choice(list(seq)))
  self.assertEqual(BURST[2]['repeat']['count'],3)
  depths=[]
  for baseline in [50,70,80]:
   previous=baseline
   for _ in range(100):
    dip=self.render(PULSE[0]['variables']['dip_level'],burst_baseline=baseline)
    recovery=self.render(PULSE[0]['variables']['recovery_level'],burst_baseline=baseline)
    frames=self.render(PULSE[1]['repeat']['for_each'],burst_level=previous,dip_level=dip,recovery_level=recovery)
    self.assertTrue(all(20<=level<=100 for level in frames))
    self.assertTrue(previous>frames[0]>frames[1]<frames[2]<frames[3])
    self.assertLessEqual(abs(frames[0]-previous),25)
    depths.append(baseline-dip)
    previous=recovery
  self.assertGreater(len(set(depths)),15)
 def test_calm_and_damped_tail_stay_bounded(self):
  ctx=dict(started=0,seed=.7,repeat=NS(item='light.a'),gust_events=[],baseline=70)
  for baseline in [50,70,80]:
   for t in [i*.1 for i in range(200)]:
    self.env.globals['now']=lambda:t
    calm=self.render(RAW,**dict(ctx,baseline=baseline))
    self.assertLessEqual(abs(calm-baseline),5)
    value=self.render(RAW,**dict(ctx,baseline=baseline,gust_events=[[5,50,2.3,0]]))
    self.assertGreaterEqual(value,20)
    self.assertLessEqual(value,100)
 def test_thermal_filter_moves_gradually_without_overshoot(self):
  levels={'light.a':80}
  last={'light.a':0}
  outputs=[]
  for step in range(1,16):
   t=step*.2
   self.env.globals['now']=lambda:t
   level=self.render(SMOOTH,started=0,repeat=NS(item='light.a'),raw_level=30,last_levels=levels,last_times=last)
   outputs.append(level)
   levels=self.render(CACHE,last_levels=levels,repeat=NS(item='light.a'),level=level)
   last={'light.a':t}
  self.assertGreater(outputs[0],30)
  self.assertLess(outputs[0],80)
  self.assertEqual(outputs,sorted(outputs,reverse=True))
  self.assertGreaterEqual(outputs[-1],30)
  self.assertLess(outputs[-1],40)
