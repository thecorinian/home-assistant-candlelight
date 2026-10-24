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
FILTER = SCRIPT['sequence'][1]['variables']['bulbs']
TRIAL = yaml.safe_load((ROOT / 'experiments/candlelight_wind_trial.yaml').read_text())

def bulb(name,state='on',modes=('color_temp',)):
 return NS(entity_id='light.'+name, domain='light',state=state,attributes={'supported_color_modes':list(modes)})

class Templates(unittest.TestCase):
 def setUp(self):
  self.lights=[bulb('a'),bulb('b','off'),bulb('dead','unavailable'),bulb('switch',modes=['onoff'])]
  self.env=NativeEnvironment()
  self.env.filters['bool']=lambda value: str(value).lower() in ('true','on','yes','1','enable')
  self.compiled={}
  self.env.globals.update(sin=math.sin,log=math.log,states=NS(light=self.lights),as_timestamp=lambda x:x,now=lambda:0,
   expand=lambda ids:[x for x in self.lights if x.entity_id in ids])
 def render(self,t,**kw):
  if t not in self.compiled: self.compiled[t]=self.env.from_string(t)
  kw.setdefault('baseline',80)
  kw.setdefault('baseline_blend_seconds',20)
  result=self.compiled[t].render(**kw)
  return ast.literal_eval(result.strip()) if isinstance(result,str) else result
 def test_handoff_preserves_brightness_and_default_still_starts_at_fifty(self):
  init=next(a['variables'] for a in SCRIPT['sequence'] if 'prepared_bulbs' in a.get('variables',{}))
  self.env.globals['state_attr']=lambda entity,attr:102 if entity=='light.b' else 204
  args=dict(preserve_start=True,bulbs=['light.a','light.b'],handoff_levels={'light.a':80})
  self.assertEqual(self.render(init['last_levels'],**args),{'light.a':80,'light.b':40})
  self.assertEqual(self.render(init['baseline_target'],preserve_start=True),80)
  self.assertEqual(self.render(init['baseline_target'],preserve_start=False),50)
  self.assertEqual(self.render(init['last_levels'],preserve_start=False),{})

 def test_brightness_updates_explicitly_keep_supported_warm_white(self):
  commands=[]
  def collect(node):
   if isinstance(node,dict):
    if node.get('action')=='light.turn_on' and node.get('target',{}).get('entity_id')=="{{ cohort | select('is_state', 'on') | list }}":commands.append(node)
    for v in node.values():collect(v)
   elif isinstance(node,list):
    for v in node:collect(v)
  collect(SCRIPT)
  self.assertEqual(len(commands),1)
  self.env.tests['is_state']=lambda entity,state:True
  attrs={'supported_color_modes':['hs','color_temp'],'min_color_temp_kelvin':2200,'max_color_temp_kelvin':6500}
  self.env.globals['state_attr']=lambda entity,attr:attrs.get(attr)
  data=commands[0]['data']
  self.assertEqual(self.render(data,cohort=['light.a'],level=80),{'brightness_pct':80,'color_temp_kelvin':2200})
  attrs['supported_color_modes']=['brightness']
  self.assertEqual(self.render(data,cohort=['light.a'],level=80),{'brightness_pct':80})

 def test_only_on_never_selects_off_or_unavailable(self):
  self.assertEqual(self.render(FILTER,requested=[],only_lit=True,excluded_lights=[]),['light.a'])
  self.assertEqual(self.render(FILTER,requested=[],only_lit=True,excluded_lights=['light.a']),[])
 def test_manual_selection_and_dimming_filter(self):
  self.assertEqual(self.render(FILTER,requested=[],only_lit=False,excluded_lights=[]),['light.a','light.b'])
  self.assertEqual(self.render(FILTER,requested=['light.b'],only_lit=False,excluded_lights=[]),['light.b'])
 def test_default_run_is_unlimited_and_preserves_off_bulbs(self):
  init=SCRIPT['sequence'][0]['variables']
  self.assertTrue(self.render(init['only_lit']))
  self.assertFalse(self.render(init['only_lit'],only_on=False))
  for supplied,expected in [(None,0),(0,0),(20,20),(-5,0),(300,240)]:
   args={} if supplied is None else {'minutes':supplied}
   self.assertEqual(self.render(init['run_minutes'],**args),expected)
 def test_all_flame_dispatch_guards_allow_unlimited_and_stop_on_request(self):
  def guards(value):
   if isinstance(value,dict):
    for k,v in value.items():
     if k=='value_template' and isinstance(v,str) and 'input_boolean.natural_candlelight_active' in v:
      yield v
     else: yield from guards(v)
   elif isinstance(value,list):
    for v in value: yield from guards(v)
  templates=list(guards(LOOP))
  self.assertGreaterEqual(len(templates),5)
  enabled=True
  def is_state(entity,state):
   if entity=='input_boolean.natural_candlelight_active': return enabled
   return entity=='light.a' and state=='on'
  self.env.globals['is_state']=is_state
  self.env.tests['is_state']=is_state
  args=dict(started=0,run_minutes=0,bulbs=['light.a'],cohort=['light.a'],repeat=NS(item='light.a'))
  self.env.globals['now']=lambda:12*3600
  for t in templates:
   self.assertTrue(self.render(t,**args))
   self.assertFalse(self.render(t,**dict(args,run_minutes=20)))
  enabled=False
  for t in templates: self.assertFalse(self.render(t,**args))
 def test_approved_model_is_preserved_in_default_controller(self):
  def model_vars(value):
   result={}
   if isinstance(value,dict):
    for k,v in value.items():
     if k=='variables':
      for name,template in v.items():
       if name in ['raw_level','level','baseline','dip_level','recovery_level','pulse_count','baseline_target','baseline_blend_seconds','wind_next']:
        result.setdefault(name,[]).append(template)
     result.update({name: result.get(name,[])+items for name,items in model_vars(v).items()})
   elif isinstance(value,list):
    for v in value:
     for name,items in model_vars(v).items():result.setdefault(name,[]).extend(items)
   return result
  trial_loop=next(a['repeat'] for a in TRIAL['sequence'] if 'while' in a.get('repeat',{}))
  self.assertEqual(model_vars(LOOP),model_vars(trial_loop))
 def test_added_bulbs_are_included_in_the_next_grouping_pass(self):
  ordering=LOOP['sequence'][0]['variables']['flame_order']
  before=self.render(ordering)
  self.lights.append(bulb('new'))
  after=self.render(ordering)
  self.assertNotIn('light.new',before)
  self.assertIn('light.new',after)
 def test_default_controller_has_no_trial_handover_or_self_start(self):
  def actions(value):
   if isinstance(value,dict):
    if 'action' in value: yield value
    for v in value.values(): yield from actions(v)
   elif isinstance(value,list):
    for v in value: yield from actions(v)
  self.assertFalse(any(a['action'].startswith('script.') for a in actions(SCRIPT['sequence'])))
  self.assertTrue(all(a.get('continue_on_error') is True for a in actions(SCRIPT['sequence']) if a['action']=='light.turn_on'))
  self.assertNotIn('trial_script_entity',str(SCRIPT))
  self.assertEqual(SCRIPT['sequence'][-1]['action'],'input_boolean.turn_off')
 def test_optional_trial_blocks_the_nightly_restart(self):
  automation=yaml.safe_load((ROOT/'automations/nightly_natural_candlelight.yaml').read_text())
  guard=automation['actions'][0]['default'][1]['value_template']
  self.env.globals['is_state']=lambda entity,state:True
  self.assertFalse(self.render(guard))
  self.env.globals['is_state']=lambda entity,state:False
  self.assertTrue(self.render(guard))

if __name__=='__main__': unittest.main()
