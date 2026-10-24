"""Daily solar, weather, bedtime, and override behavior with deterministic inputs."""
import json,math,hashlib
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace as NS
from jinja2.nativetypes import NativeEnvironment
import unittest,yaml
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=yaml.safe_load((R/'scripts/daily_lighting_controller.yaml').read_text())
LOOP=D['sequence'][1]['repeat']['sequence']
PLAN=LOOP[0]['variables']['plan']
COMMANDS=next(x['variables']['commands'] for x in LOOP if 'commands' in x.get('variables',{}))
class States:
 def __init__(self,weather,clock,lights=(),helper=''):
  self.weather=weather;self.clock=clock;self.light=lights;self.helper=helper
 def __call__(self,e):
  if e=='weather.home':return self.weather.state
  if e=='input_text.lighting_schedule_clock':return json.dumps(self.clock)
  if e=='input_text.lighting_manual_off':return self.helper
  return 'off'
 def __getitem__(self,e):return self.weather if e=='weather.home' else None
class DailySchedule(unittest.TestCase):
 def setUp(self):
  self.tz=ZoneInfo('America/Los_Angeles');self.now=datetime(2026,10,24,7,44,tzinfo=self.tz)
  self.weather=NS(state='partlycloudy',last_changed=self.now-timedelta(hours=1),last_updated=self.now,attributes={'temperature':42,'temperature_unit':'°F','cloud_coverage':54,'wind_speed':5,'wind_speed_unit':'mph','dew_point':35})
  self.clock={'date':'2026-10-24','rise':self.now.timestamp(),'set':self.now.replace(hour=18,minute=2).timestamp()}
  self.states=States(self.weather,self.clock)
  self.env=NativeEnvironment();self.env.filters.update(from_json=lambda s,default={}:json.loads(s) if s else default,to_json=json.dumps,sha256=lambda s:hashlib.sha256(s.encode()).hexdigest())
  self.env.globals.update(states=self.states,now=lambda:self.now,as_timestamp=lambda d:d.timestamp(),state_attr=lambda e,a:self.weather.attributes.get(a),today_at=lambda s:self.now.replace(hour=int(s.split(':')[0]),minute=int(s.split(':')[1]),second=0),sin=math.sin,is_state=lambda e,s:False)
 def at(self,h,m=0):
  self.now=self.now.replace(hour=h,minute=m,second=0);self.weather.last_updated=self.now
  return self.env.from_string(PLAN).render(weather_entity='weather.home')
 def test_sunrise_ramp_and_daylight_cutoff(self):
  self.assertEqual(self.at(7,43)['inside'],0)
  self.assertEqual(self.at(7,44)['inside'],0)
  self.assertGreater(self.at(8)['inside'],0)
  self.assertEqual(self.at(8,29)['inside'],80)
  self.assertEqual(self.at(9,29)['inside'],80)
  self.assertLess(self.at(10,30)['inside'],80)
  self.assertEqual(self.at(11,30)['inside'],0)
 def test_candlelight_at_1930_and_off_at_2200(self):
  self.assertEqual(self.at(19,29)['phase'],'evening')
  self.assertEqual(self.at(19,30)['phase'],'candlelight')
  self.assertEqual(self.at(20)['ceiling'],35)
  self.assertEqual(self.at(21)['ceiling'],15)
  self.assertEqual(self.at(22)['inside'],0)
  self.assertEqual(self.at(4)['inside'],0)
 def test_cold_is_already_warmest_and_cool_is_for_hot_days(self):
  self.assertEqual(self.at(9)['kelvin'],2000)
  self.assertEqual(self.at(20)['kelvin'],2000)
  for temp,k in [(50,2000),(65,2700),(75,3500),(85,4500),(90,5000),(100,5000)]:
   self.weather.attributes['temperature']=temp;self.assertEqual(self.at(9)['kelvin'],k)
  self.assertEqual(self.at(20)['kelvin'],2700)
  self.assertEqual(self.at(22)['kelvin'],2000)
 def test_celsius_conversion_and_stale_weather_fallback(self):
  self.weather.attributes.update(temperature=10,temperature_unit='°C');self.assertEqual(self.at(9)['kelvin'],2000)
  self.weather.attributes.update(temperature=30,temperature_unit='°C');self.assertGreater(self.at(9)['kelvin'],4500)
  self.weather.last_updated=self.now-timedelta(hours=3)
  p=self.env.from_string(PLAN).render(weather_entity='weather.home');self.assertEqual(p['kelvin'],2000);self.assertFalse(p['motif'])
 def test_outdoor_dawn_and_sunset_are_independent(self):
  self.assertEqual(self.at(6)['outside'],18)
  self.assertEqual(self.at(6,59)['outside'],18)
  self.assertGreater(self.at(7,14)['outside'],0)
  self.assertEqual(self.at(7,29)['outside'],0)
  self.assertEqual(self.at(18,2)['outside'],0)
  self.assertEqual(self.at(18,32)['outside'],50)
  self.assertEqual(self.at(22)['outside'],25)
 def test_dark_day_support_and_frost_is_only_risk(self):
  self.weather.state='rainy';p=self.at(12);self.assertEqual(p['inside'],25);self.assertEqual(p['weather'],'rain')
  self.weather.state='clear-night';self.weather.attributes.update(temperature=34,dew_point=33,cloud_coverage=0)
  self.assertEqual(self.at(6)['weather'],'frost_risk')
 def test_weather_motif_requires_ten_minutes_stable_condition(self):
  self.weather.state='rainy';self.weather.last_changed=self.now.replace(hour=12,minute=0)
  self.assertFalse(self.at(12,1)['motif'])
  self.assertTrue(self.at(12,10)['motif'])
  self.assertFalse(self.at(12,20)['motif'])
  self.assertTrue(self.at(12,30)['motif'])
 def test_missing_clock_never_turns_lights_on(self):
  self.clock.clear();p=self.at(9);self.assertEqual(p['inside'],0);self.assertEqual(p['outside'],0)
 def test_manual_hold_and_absent_children_generate_no_commands(self):
  lights=[NS(entity_id='light.a',state='on',attributes={'supported_color_modes':['color_temp'],'brightness':200}),NS(entity_id='light.kid',state='off',attributes={'supported_color_modes':['color_temp']})]
  self.states.light=lights
  args=dict(plan=self.at(9),held=NS(value='h:'+hashlib.sha256(b'light.a').hexdigest()[:8]),preview=False,excluded_lights=[],outdoor_lights=[],bedroom_lights=['light.kid'],morning_bright_lights=[],circulation_lights=[],alternating_week_lights=['light.kid'],present=False,last_sent={})
  self.assertEqual(self.env.from_string(COMMANDS).render(**args),[])
 def test_off_phase_cannot_produce_a_light_on_command(self):
  self.states.light=[NS(entity_id='light.a',state='on',attributes={'supported_color_modes':['color_temp'],'brightness':200})]
  args=dict(plan=self.at(22),held=NS(value='h:'),preview=False,excluded_lights=[],outdoor_lights=[],bedroom_lights=[],morning_bright_lights=[],circulation_lights=[],alternating_week_lights=[],present=True,last_sent={})
  cmds=self.env.from_string(COMMANDS).render(**args);self.assertEqual(len(cmds),1);self.assertEqual(cmds[0]['b'],0)
 def test_scheduled_candlelight_scales_peaks_and_preserves_warm_white(self):
  main=yaml.safe_load((R/'scripts/natural_candlelight.yaml').read_text())
  def walk(v):
   if isinstance(v,dict):
    if v.get('action')=='light.turn_on':yield v
    for x in v.values():yield from walk(x)
   elif isinstance(v,list):
    for x in v:yield from walk(x)
  action=next(x for x in walk(main) if x.get('target',{}).get('entity_id')=="{{ cohort | select('is_state', 'on') | list }}")
  self.env.tests['is_state']=lambda e,s:True
  self.env.globals['states']=lambda e:json.dumps({'ceiling':15,'kelvin':2000})
  self.env.globals['state_attr']=lambda e,a:{'supported_color_modes':['color_temp'],'min_color_temp_kelvin':2000,'max_color_temp_kelvin':6500}.get(a)
  self.env.filters['bool']=bool
  cmd=self.env.from_string(action['data']).render(cohort=['light.a'],level=100,scheduled_run=True)
  self.assertEqual(cmd['brightness_pct'],15);self.assertEqual(cmd['color_temp_kelvin'],2000)
if __name__=='__main__':unittest.main()
