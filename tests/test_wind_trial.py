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
BASELINE_CHANGE=next(a['then'] for a in LOOP['sequence'] if 'baseline_target' in a.get('then',[{}])[0].get('variables',{}))
REBOUND=BASELINE_CHANGE[1]['then']

class Wind(unittest.TestCase):
 setUp=test_templates.Templates.setUp
 render=test_templates.Templates.render
 def test_twenty_minute_run_keeps_pulses_active_past_three_minutes(self):
  self.env.globals['is_state']=lambda entity,state: True
  guards=[LOOP['while'][0]['value_template'],
   PULSE[1]['repeat']['sequence'][0]['if'][0]['value_template']]
  for elapsed,expected in [(179,True),(181,True),(1199,True),(1200,False)]:
   self.env.globals['now']=lambda:elapsed
   for guard in guards:
    self.assertEqual(self.render(guard,trial_script_entity='script.test',started=0,run_minutes=20,bulbs=['light.a']),expected)
  duration=next(a['variables']['run_minutes'] for a in TRIAL['sequence'] if 'run_minutes' in a.get('variables',{}))
  for supplied,expected in [(20,20),(-1,1),(100,60)]:
   self.assertEqual(self.render(duration,minutes=supplied),expected)
  self.assertEqual(self.render(duration),3)
 def test_wind_schedule_leaves_long_variable_quiet_gaps(self):
  rng=test_templates.random.Random(91)
  self.env.filters['random']=test_templates.pass_context(lambda context,seq:rng.choice(list(seq)))
  self.env.globals['now']=lambda:200
  gaps=[]
  for _ in range(1000):
   opening=self.render(INIT['wind_next'])
   self.assertTrue(8<=opening<=14)
   gaps.append(self.render(BURST[3]['variables']['wind_next'],started=0)-200)
  self.assertTrue(all(40<=gap<=100 for gap in gaps))
  self.assertGreater(len(set(gaps)),55)
  self.assertGreater(sum(gaps)/len(gaps),65)
 def test_triplets_have_soft_edges_and_varied_bounded_depths(self):
  rng=test_templates.random.Random(121)
  self.env.filters['random']=test_templates.pass_context(lambda context,seq:rng.choice(list(seq)))
  self.assertEqual(self.render(BURST[2]['repeat']['count'],pulse_count=3),3)
  depths=[]
  for baseline in [50,70,80]:
   previous=baseline
   for _ in range(100):
    dip=self.render(PULSE[0]['variables']['dip_level'],burst_baseline=baseline,pulse_count=3)
    recovery=self.render(PULSE[0]['variables']['recovery_level'],burst_baseline=baseline,pulse_count=3)
    frames=self.render(PULSE[1]['repeat']['for_each'],burst_level=previous,dip_level=dip,recovery_level=recovery)
    self.assertTrue(all(20<=level<=100 for level in frames))
    self.assertEqual(len(frames),6)
    self.assertTrue(previous>frames[0]>frames[1]>frames[2]<frames[3]<frames[4]<frames[5])
    self.assertTrue(all(abs(b-a)<=27 for a,b in zip([previous]+frames,frames)))
    depths.append(baseline-dip)
    previous=recovery
  self.assertGreater(len(set(depths)),15)
 def test_single_gust_recovers_near_baseline_without_a_second_tail(self):
  self.assertEqual(self.render(BURST[2]['repeat']['count'],pulse_count=1),1)
  for baseline in [50,70,80]:
   for _ in range(100):
    dip=self.render(PULSE[0]['variables']['dip_level'],burst_baseline=baseline,pulse_count=1)
    recovery=self.render(PULSE[0]['variables']['recovery_level'],burst_baseline=baseline,pulse_count=1)
    self.assertTrue(20<=dip<=max(20,baseline*.4))
    self.assertTrue(baseline-3<=recovery<=baseline+4)
  self.assertEqual(self.render(BURST[3]['variables']['gust_events'],pulse_count=1),[])
 def test_mixed_gusts_and_lower_brightness_weights(self):
  rng=test_templates.random.Random(271)
  self.env.filters['random']=test_templates.pass_context(lambda context,seq:rng.choice(list(seq)))
  baseline_change=next(a['then'][0]['variables'] for a in LOOP['sequence'] if 'baseline_target' in a.get('then',[{}])[0].get('variables',{}))
  counts={50:0,70:0,80:0}
  singles=0
  bright_rebounds=0
  previous=70
  for _ in range(3000):
   target=self.render(baseline_change['baseline_target'],leaving_low=previous==50)
   if previous==50: self.assertIn(target,[70,80])
   counts[target]+=1
   previous=target
   singles+=self.render(BURST[0]['variables']['pulse_count'])==1
   bright_rebounds+=self.render(PULSE[0]['variables']['recovery_level'],burst_baseline=80,pulse_count=3)>=95
  for target,expected in [(80,.3),(70,.4),(50,.3)]:
   self.assertAlmostEqual(counts[target]/3000,expected,delta=.04)
  self.assertAlmostEqual(singles/3000,.5,delta=.04)
  self.assertTrue(.08<bright_rebounds/3000<.22)
 def test_low_hold_always_rebounds_then_settles_smoothly(self):
  change=BASELINE_CHANGE[0]['variables']
  for old in [50,70,80]:
   leaving=self.render(change['leaving_low'],baseline_target=old)
   self.assertEqual(leaving,old==50)
  for _ in range(100):
   peak=self.render(change['rebound_peak'])
   self.assertTrue(90<=peak<=100)
   frames=self.render(REBOUND[0]['repeat']['for_each'],bulbs=['light.a','light.b'],last_levels={'light.a':42,'light.b':50},rebound_peak=peak)
   self.assertEqual(frames,[(46+peak)/2,peak])
   fade=self.render(change['baseline_blend_seconds'],leaving_low=True)
   self.assertTrue(4<=fade<=7)
  baseline=next(a['variables']['baseline'] for a in INNER if 'baseline' in a.get('variables',{}))
  values=[]
  for t in [0,1,2,3,4,5]:
   self.env.globals['now']=lambda:t
   values.append(self.render(baseline,started=0,baseline_changed=0,baseline_from=95,baseline_target=70,baseline_blend_seconds=5))
  self.assertEqual(values[0],95)
  self.assertEqual(values[-1],70)
  self.assertEqual(values,sorted(values,reverse=True))
 def test_rebound_preserves_off_lights_and_duration_guard(self):
  frame=REBOUND[0]['repeat']['sequence'][0]
  target=frame['then'][0]['target']['entity_id']
  self.assertEqual(self.render(target,bulbs=['light.a','light.b','light.dead']),['light.a'])
  self.env.globals['is_state']=lambda entity,state:True
  self.env.globals['now']=lambda:1200
  self.assertFalse(self.render(frame['if'][0]['value_template'],trial_script_entity='script.test',started=0,run_minutes=20,bulbs=['light.a']))
 def test_calm_and_damped_tail_stay_bounded(self):
  ctx=dict(started=0,seed=.7,repeat=NS(item='light.a'),gust_events=[],baseline=70)
  for baseline in [50,70,80]:
   for t in [i*.1 for i in range(200)]:
    self.env.globals['now']=lambda:t
    calm=self.render(RAW,**dict(ctx,baseline=baseline))
    self.assertLessEqual(abs(calm-baseline),15)
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
