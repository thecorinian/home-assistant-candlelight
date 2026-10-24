"""Manual off survives stale on feedback, controller restarts, and paired bulbs."""
import hashlib
from types import SimpleNamespace as NS
import unittest,yaml
import test_templates as base
AUTO=yaml.safe_load((base.ROOT/'automations/lighting_off_wins.yaml').read_text())
SCRIPT=yaml.safe_load((base.ROOT/'scripts/lighting_off_priority.yaml').read_text())
REGISTRY=yaml.safe_load((base.ROOT/'scripts/lighting_manual_off_registry.yaml').read_text())
class OffPriority(unittest.TestCase):
 render=base.Templates.render
 def setUp(self):
  base.Templates.setUp(self)
  self.env.globals['is_state']=lambda e,s:False
 def operation(self,old,new,age=60,parent=None):
  trigger=NS(id='state_change',event=NS(data=NS(entity_id='light.a',old_state=NS(state=old,last_changed=100),new_state=NS(state=new,last_changed=100+age,context=NS(parent_id=parent)))))
  return self.env.from_string(AUTO['variables']['operation']).render(trigger=trigger).strip()
 def test_off_is_held_and_late_immediate_on_does_not_release(self):
  self.assertEqual(self.operation('on','off'),'hold')
  self.assertEqual(self.operation('off','on',2),'ignore')
  self.assertEqual(self.operation('off','on',29),'ignore')
  self.assertEqual(self.operation('off','on',30),'release')
  self.assertEqual(self.operation('on','off',parent='effect'),'ignore')
 def test_direct_off_and_on_but_not_effect_services(self):
  for service,parent,expected in [('turn_off',None,'hold'),('turn_on',None,'release'),('turn_off','effect','ignore'),('turn_on','effect','ignore')]:
   t=NS(id='service_change',event=NS(context=NS(parent_id=parent),data=NS(domain='light',service=service)))
   self.assertEqual(self.env.from_string(AUTO['variables']['operation']).render(trigger=t).strip(),expected)
 def test_daily_direct_on_and_color_commands_create_manual_hold(self):
  self.env.globals['is_state']=lambda e,s:e=='input_boolean.daily_lighting_schedule_active'
  for svc,expected in [('turn_on','manual_on'),('turn_off','hold')]:
   t=NS(id='service_change',event=NS(context=NS(parent_id=None),data=NS(domain='light',service=svc)))
   self.assertEqual(self.env.from_string(AUTO['variables']['operation']).render(trigger=t).strip(),expected)
 def test_daily_expected_power_acknowledgments_are_not_manual_overrides(self):
  self.env.globals['is_state']=lambda e,s:e=='input_boolean.daily_lighting_schedule_active'
  token=hashlib.sha256(b'light.a').hexdigest()[:8]
  class Markers:
   def __call__(self,e):return token
   def __getitem__(self,e):return NS(last_changed=0)
  self.env.globals['states']=Markers()
  self.env.globals['now']=lambda:10
  self.assertEqual(self.operation('on','off'),'ignore')
  self.assertEqual(self.operation('off','on',2),'ignore')
  self.env.globals['now']=lambda:31
  self.assertEqual(self.operation('on','off'),'hold')
  self.assertEqual(self.operation('off','on',2),'manual_on')
 def update(self,stored,ids,op='hold'):
  return self.env.from_string(REGISTRY['sequence'][1]['variables']['updated']).render(stored=NS(value=stored),ids=ids,op=op).strip()
 def test_registry_adds_releases_and_preserves_previous_holds(self):
  a=self.update('',['light.a']);self.assertEqual(a,'h:'+hashlib.sha256(b'light.a').hexdigest()[:8])
  both=self.update(a,['light.b']);self.assertEqual(len(both),18)
  self.assertEqual(self.update(both,['light.b'],'release'),a)
  self.assertEqual(self.update('*',[],'clear_all'),'h:')
  self.assertEqual(self.update('*',['light.a'],'release'),'*')
 def test_numeric_looking_tokens_remain_strings(self):
  for value in ['12345678','00000000','']:
   self.env.globals['states']=lambda entity:value
   rendered=self.env.from_string(REGISTRY['sequence'][0]['variables']['stored']).render()
   self.assertEqual(rendered,{'value':value})
   command=self.env.from_string(REGISTRY['sequence'][-1]['data']['value']).render(updated='h:'+value)
   self.assertIsInstance(command,str)
   self.assertEqual(command,'h:'+value)
 def test_capacity_invalid_state_and_collisions_fail_closed(self):
  self.assertEqual(self.update('',['light.x'+str(i) for i in range(32)]),'*')
  self.assertEqual(self.update('unknown',['light.a']),'*')
  self.env.filters['sha256']=lambda s:'0'*64
  self.assertEqual(self.update('',['light.a']),'*')
 def test_held_bulb_is_excluded_even_when_it_reports_on(self):
  held=hashlib.sha256(b'light.a').hexdigest()[:8]
  class Held(base.StateStore):
   def __call__(self,e):return held
  self.env.globals['states']=Held(light=self.lights)
  self.assertEqual(self.render(base.FILTER,requested=[],only_lit=True,excluded_lights=[]),[])
 def test_off_guard_never_sends_light_on_and_recovery_is_on_only(self):
  def actions(v):
   if isinstance(v,dict):
    if 'action' in v:yield v
    for x in v.values():yield from actions(x)
   elif isinstance(v,list):
    for x in v:yield from actions(x)
  cmds=list(actions(SCRIPT))
  self.assertFalse(any(x['action']=='light.turn_on' for x in cmds))
  restart=next(x for x in cmds if x['action']=='script.turn_on')
  self.assertTrue(restart['data']['variables']['only_on'])
  self.assertTrue(restart['data']['variables']['preserve_brightness'])
 def test_fixture_pair_hold_does_not_expand_the_actual_off_command(self):
  hold=next(x['variables']['hold_bulbs'] for x in SCRIPT['sequence'] if 'hold_bulbs' in x.get('variables',{}))
  self.assertEqual(self.render(hold,off_bulbs=['light.a'],coupled_fixtures=[['light.a','light.b']]),['light.a','light.b'])
  off=next(x for x in SCRIPT['sequence'] if x.get('repeat',{}).get('count')==4)['repeat']['sequence'][0]
  self.assertEqual(off['target']['entity_id'],'{{ off_bulbs }}')
if __name__=='__main__':unittest.main()
