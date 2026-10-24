"""Verify the optional wind model without operating any real bulbs."""
from types import SimpleNamespace as NS
import yaml
import unittest
import test_templates
ROOT=test_templates.ROOT

TRIAL=yaml.safe_load((ROOT/'experiments/candlelight_wind_trial.yaml').read_text())
INIT=next(a['variables'] for a in TRIAL['sequence'] if 'wind_pulses' in a.get('variables',{}))
LOOP=next(a['repeat'] for a in TRIAL['sequence'] if 'repeat' in a and 'while' in a['repeat'])
INNER=next(a['repeat']['sequence'][0]['then'] for a in LOOP['sequence'] if 'repeat' in a)
RAW=next(a['variables']['raw_level'] for a in INNER if 'raw_level' in a.get('variables',{}))
SMOOTH=next(a['variables']['level'] for a in INNER if 'level' in a.get('variables',{}))
CACHE=next(a['variables']['last_levels'] for a in INNER if 'last_levels' in a.get('variables',{}))

class Wind(unittest.TestCase):
 setUp=test_templates.Templates.setUp
 render=test_templates.Templates.render
 def test_wind_schedule_has_clusters_and_quiet_gaps(self):
  pulses=self.render(INIT['wind_pulses'])
  self.assertGreaterEqual(len(pulses),60)
  self.assertLessEqual(len(pulses),100)
  gaps=[b[0]-a[0]-a[1] for a,b in zip(pulses,pulses[1:])]
  self.assertEqual(sum(gap>10 for gap in gaps),19)
  self.assertTrue(all(.79<=gap<=31.81 for gap in gaps))
  self.assertTrue(all(2.5<=p[1]<=4.5 and 20<=p[2]<=40 for p in pulses))
 def test_wind_dips_below_ordinary_model_and_stays_bounded(self):
  ctx=dict(started=0,seed=.7,repeat=NS(item='light.a'),gust_events=[],baseline=70)
  self.env.globals['now']=lambda:7
  calm=self.render(RAW,wind_pulses=[],**ctx)
  windy=self.render(RAW,wind_pulses=[[5,4,35]],**ctx)
  self.assertEqual(calm-windy,35)
  for baseline in [50,70,80]:
   for t in [i*.1 for i in range(200)]:
    self.env.globals['now']=lambda:t
    value=self.render(RAW,wind_pulses=[[5,4,40],[7,3,40]],**dict(ctx,baseline=baseline,gust_events=[[5,100,2.3,0]]))
    self.assertGreaterEqual(value,20)
    self.assertLessEqual(value,100)
 def test_thermal_filter_moves_gradually_without_overshoot(self):
  levels={'light.a':80}
  last={'light.a':0}
  outputs=[]
  for step in range(1,11):
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
