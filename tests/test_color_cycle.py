"""Check reusable color selection, stop/timer boundaries and coexistence guards."""
import unittest
from types import SimpleNamespace as NS
import yaml
import test_templates as base

COLOR = yaml.safe_load((base.ROOT/'scripts/synchronized_color_cycle.yaml').read_text())
SEQ = COLOR['sequence']
SELECT = next(a['variables']['bulbs'] for a in SEQ if 'bulbs' in a.get('variables', {}))
LOOP = next(a['repeat'] for a in SEQ if 'while' in a.get('repeat', {}))

class ColorCycle(unittest.TestCase):
    render = base.Templates.render

    def setUp(self):
        base.Templates.setUp(self)
        self.lights[:] = [base.bulb('a', modes=['hs']), base.bulb('b', 'off', ['rgb']),
                         base.bulb('white'), base.bulb('dead', 'unavailable', ['hs'])]
        self.enabled = True
        def is_state(entity, state):
            if entity == 'input_boolean.synchronized_color_cycle_active':
                return self.enabled == (state == 'on')
            return any(s.entity_id == entity and s.state == state for s in self.lights)
        self.env.globals['is_state'] = is_state
        self.env.tests['is_state'] = is_state

    def test_empty_selection_never_becomes_whole_house(self):
        self.assertEqual(self.render(SELECT, requested=[], only_lit=False, excluded_lights=[]), [])

    def test_selected_color_lights_only_and_off_option(self):
        args = dict(requested=[s.entity_id for s in self.lights], excluded_lights=[])
        self.assertEqual(self.render(SELECT, only_lit=False, **args), ['light.a', 'light.b'])
        self.assertEqual(self.render(SELECT, only_lit=True, **args), ['light.a'])
        args['excluded_lights'] = ['light.a']
        self.assertEqual(self.render(SELECT, only_lit=True, **args), [])

    def test_stop_and_deadline_are_checked_before_dispatch(self):
        args = dict(bulbs=['light.a'], active_bulbs=['light.a'], started=0, run_minutes=0)
        self.env.globals['now'] = lambda: 3600
        guards = [LOOP['while'][0]['value_template'], LOOP['sequence'][1]['if'][0]['value_template']]
        for guard in guards:
            self.assertTrue(self.render(guard, **args))
            self.assertFalse(self.render(guard, **dict(args, run_minutes=1)))
            self.enabled = False
            self.assertFalse(self.render(guard, **args))
            self.enabled = True
        self.assertEqual(self.render(LOOP['sequence'][0]['variables']['active_bulbs'], bulbs=['light.a', 'light.b']), ['light.a'])

    def test_shared_color_and_wrap_preserve_approved_settings(self):
        command = LOOP['sequence'][1]['then'][0]
        self.assertEqual(self.render(command['data']['hs_color'], hue=359), [359,85])
        self.assertEqual(command['data']['brightness_pct'], 65)
        self.assertEqual(self.render(LOOP['sequence'][2]['variables']['hue'], hue=359), 0)
        self.assertEqual(LOOP['sequence'][3]['delay']['milliseconds'], 150)

    def test_competitor_paused_only_for_overlap(self):
        template = next(a['variables']['paused_color_scripts'] for a in SEQ if 'paused_color_scripts' in a.get('variables',{}))
        self.env.globals['is_state'] = lambda entity, state: entity == 'script.example'
        item = {'entity_id':'script.example', 'lights':['light.a']}
        self.assertEqual(self.render(template, competing_color_scripts=[item], bulbs=['light.a']), [item])
        self.assertEqual(self.render(template, competing_color_scripts=[item], bulbs=['light.b']), [])

    def test_nightly_waits_and_sunrise_stops_color_before_snapshot(self):
        automation = yaml.safe_load((base.ROOT/'automations/nightly_natural_candlelight.yaml').read_text())
        guard = next(a['value_template'] for a in automation['actions'][0]['default'] if 'script.synchronized_color_cycle' in a.get('value_template',''))
        self.env.globals['is_state'] = lambda entity, state: True
        self.assertFalse(self.render(guard))
        fade = yaml.safe_load((base.ROOT/'scripts/sunrise_fade_off.yaml').read_text())
        self.assertIn('script.synchronized_color_cycle', fade['variables']['controllers'])
        self.assertEqual(fade['sequence'][1]['then'][0]['action'], 'script.turn_off')
        self.assertEqual(fade['sequence'][3]['then'][0]['target']['entity_id'], 'input_boolean.synchronized_color_cycle_active')

if __name__ == '__main__': unittest.main()
