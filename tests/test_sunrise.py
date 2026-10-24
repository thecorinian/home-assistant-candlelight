"""Verify sunrise fade timing, monotonic output, and off-light preservation."""
import unittest
from types import SimpleNamespace as NS
import yaml
import test_templates

FADE=yaml.safe_load((test_templates.ROOT/'scripts/sunrise_fade_off.yaml').read_text())
SEQUENCE=FADE['sequence']
LOOP=next(a['repeat'] for a in SEQUENCE if 'while' in a.get('repeat',{}))
PER_LIGHT=LOOP['sequence'][0]['repeat']['sequence'][0]
LEVEL=PER_LIGHT['then'][0]['variables']['level']
SELECT=next(a['variables']['bulbs'] for a in SEQUENCE if 'bulbs' in a.get('variables',{}))
DURATION=next(a['variables']['fade_seconds'] for a in SEQUENCE if 'fade_seconds' in a.get('variables',{}))

class Sunrise(unittest.TestCase):
 setUp=test_templates.Templates.setUp
 render=test_templates.Templates.render
 def test_duration_defaults_to_thirty_minutes_and_is_bounded(self):
  self.assertEqual(self.render(DURATION),1800)
  for supplied,expected in [(1,60),(0,60),(-5,60),(30,1800),(200,7200)]:
   self.assertEqual(self.render(DURATION,minutes=supplied),expected)
 def test_selection_skips_off_unavailable_onoff_and_excluded(self):
  self.assertEqual(self.render(SELECT,requested=[],excluded_lights=[]),['light.a'])
  self.assertEqual(self.render(SELECT,requested=[],excluded_lights=['light.a']),[])
  self.assertEqual(self.render(SELECT,requested=['light.b'],excluded_lights=[]),[])
 def test_fade_is_smooth_monotonic_and_uses_each_initial_brightness(self):
  for initial in [50,128,255]:
   values=[]
   current=initial
   self.env.globals['state_attr']=lambda entity,attribute:current
   for t in range(0,1801,15):
    self.env.globals['now']=lambda:t
    current=self.render(LEVEL,started=0,fade_seconds=1800,initial_levels={'light.a':initial},repeat=NS(item='light.a'))
    values.append(current)
   self.assertEqual(values[0],initial)
   self.assertEqual(values[-1],1)
   self.assertEqual(values,sorted(values,reverse=True))
   self.assertLessEqual(max(a-b for a,b in zip(values,values[1:])),4)
   self.assertAlmostEqual(values[60],initial/2,delta=1)
 def test_manual_dim_is_not_brightened_by_the_fade(self):
  self.env.globals['state_attr']=lambda entity,attribute:20
  self.env.globals['now']=lambda:60
  self.assertEqual(self.render(LEVEL,started=0,fade_seconds=1800,initial_levels={'light.a':255},repeat=NS(item='light.a')),20)
 def test_off_lights_are_never_dispatched_and_final_targets_are_filtered(self):
  self.env.globals['is_state']=lambda entity,state:entity=='light.a' and state=='on'
  self.env.tests['is_state']=self.env.globals['is_state']
  self.assertFalse(self.render(PER_LIGHT['if'][0]['value_template'],repeat=NS(item='light.b')))
  final=next(a['repeat'] for a in SEQUENCE if a.get('repeat',{}).get('count')==3)
  self.assertEqual(self.render(final['sequence'][0]['variables']['remaining_lights'],bulbs=['light.a','light.b']),['light.a'])
  self.assertEqual(final['sequence'][1]['then'][0]['action'],'light.turn_off')
 def test_fade_stops_controller_before_snapshot_without_steady_80_action(self):
  self.assertEqual(SEQUENCE[1]['then'][0]['action'],'script.turn_off')
  self.assertNotIn('script.stop_natural_candlelight',str(FADE))
  self.assertEqual(SEQUENCE[2]['action'],'input_boolean.turn_off')
 def test_sunrise_starts_fade_and_nightly_check_respects_active_fade(self):
  automation=yaml.safe_load((test_templates.ROOT/'automations/nightly_natural_candlelight.yaml').read_text())
  sunrise=automation['actions'][0]['choose'][0]['sequence'][0]
  self.assertEqual(sunrise['target']['entity_id'],'script.sunrise_fade_off')
  self.assertEqual(sunrise['data']['variables']['minutes'],30)
  guard=automation['actions'][0]['default'][2]['value_template']
  self.env.globals['is_state']=lambda entity,state:True
  self.assertFalse(self.render(guard))
  self.env.globals['is_state']=lambda entity,state:False
  self.assertTrue(self.render(guard))

if __name__=='__main__':unittest.main()
