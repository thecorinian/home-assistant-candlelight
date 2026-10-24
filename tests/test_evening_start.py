"""Evening fade detection and optional alternating-week eligibility."""
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace as NS
import unittest
import yaml
import test_templates as base

MAIN=yaml.safe_load((base.ROOT/'scripts/natural_candlelight.yaml').read_text())
LOOP=next(a['repeat'] for a in MAIN['sequence'] if 'while' in a.get('repeat',{}))
SELECT=MAIN['sequence'][1]['variables']['bulbs']
NEW=next(a['variables']['new_bulbs'] for a in LOOP['sequence'] if 'new_bulbs' in a.get('variables',{}))
FADE=next(a for a in LOOP['sequence'] if a.get('then',[{}])[0].get('delay')=={'milliseconds':250})
AUTO=yaml.safe_load((base.ROOT/'automations/nightly_natural_candlelight.yaml').read_text())
SUN=yaml.safe_load((base.ROOT/'scripts/sunrise_fade_off.yaml').read_text())
SUN_SELECT=next(a['variables']['bulbs'] for a in SUN['sequence'] if 'bulbs' in a.get('variables',{}))
class EveningStart(unittest.TestCase):
 render=base.Templates.render
 def setUp(self):
  base.Templates.setUp(self)
  self.lights[:]=[base.bulb('ordinary'),base.bulb('scheduled'),base.bulb('off','off'),base.bulb('dead','unavailable')]
  for s in self.lights:s.last_changed=10
  self.env.globals['strptime']=datetime.strptime
  self.env.globals['is_state']=lambda entity,state: entity in ['automation.nightly_natural_candlelight','sun.sun']
  self.env.tests['is_state']=lambda entity,state:any(s.entity_id==entity and s.state==state for s in self.lights)
  self.env.globals['state_attr']=lambda entity,attr: {'supported_color_modes':['color_temp'],'min_color_temp_kelvin':2000,'max_color_temp_kelvin':6500}.get(attr)
 def at(self,date):
  self.env.globals['now']=lambda:datetime.fromisoformat(date).replace(tzinfo=ZoneInfo('America/Los_Angeles'))
 def test_alternating_weeks_use_local_wall_clock_across_dst(self):
  args=dict(requested=[],only_lit=True,excluded_lights=[],alternating_week_lights=['light.scheduled'],alternating_week_start='2018-11-02 16:00:00')
  for date,present in [('2018-11-02T15:59:59',False),('2018-11-02T16:00:00',True),('2018-11-04T02:30:00',True),('2018-11-09T15:59:59',True),('2018-11-09T16:00:00',False),('2018-11-16T16:00:00',True)]:
   self.at(date)
   for template in [SELECT,LOOP['sequence'][0]['variables']['bulbs'],SUN_SELECT]:
    result=self.render(template,**args)
    self.assertIn('light.ordinary',result)
    self.assertEqual('light.scheduled' in result,present,(date,template))
    self.assertNotIn('light.off',result)
    self.assertNotIn('light.dead',result)
 def test_event_gate_respects_presence_and_permanent_exclusions(self):
  s=self.lights[1]
  args=dict(reason='light_on',trigger=NS(event=NS(data=NS(new_state=s))),excluded_lights=[],alternating_week_lights=['light.scheduled'],alternating_week_start='2018-11-02 16:00:00')
  gate=AUTO['conditions'][1]['value_template']
  self.at('2018-11-02T15:00:00');self.assertFalse(self.render(gate,**args))
  self.at('2018-11-02T16:00:00');self.assertTrue(self.render(gate,**args))
  self.assertFalse(self.render(gate,**dict(args,excluded_lights=['light.scheduled'])))
 def test_new_light_or_new_on_cycle_gets_one_fade(self):
  args=dict(bulbs=['light.ordinary','light.scheduled','light.off'],prepared_versions={'light.ordinary':10})
  self.assertEqual(self.render(NEW,**args),['light.scheduled'])
  args['prepared_versions']['light.scheduled']=10
  self.assertEqual(self.render(NEW,**args),[])
  self.lights[0].last_changed=20
  self.assertEqual(self.render(NEW,**args),['light.ordinary'])
 def test_automatic_fade_only_during_enabled_night_window(self):
  gate=FADE['if'][0]['value_template']
  for date,expected in [('2018-11-02T20:59:00',False),('2018-11-02T21:00:00',True),('2018-11-03T01:00:00',True),('2018-11-03T12:00:00',False)]:
   self.at(date);self.assertEqual(self.render(gate),expected)
  self.env.globals['is_state']=lambda entity,state:False
  self.at('2018-11-02T22:00:00');self.assertFalse(self.render(gate))
 def test_fade_keeps_off_bulbs_off_and_finishes_at_eighty(self):
  final=FADE['then'][-2]['then'][0]
  self.assertEqual(self.render(final['target']['entity_id'],fade_bulbs=['light.ordinary','light.off']),['light.ordinary'])
  self.assertEqual(self.render(final['data'],fade_bulbs=['light.ordinary']),{'brightness':204,'color_temp_kelvin':2000})
  self.assertEqual(MAIN['sequence'][0]['variables']['automatic_fade_seconds'],10)

if __name__=='__main__':unittest.main()
