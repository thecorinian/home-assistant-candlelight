"""Validate fixture coordination, bounded frames and stop behavior for all presets."""
import unittest
from types import SimpleNamespace as NS
import yaml
import test_templates as base

SCRIPT = yaml.safe_load((base.ROOT/'scripts/custom_lighting_patterns.yaml').read_text())
SEQ = SCRIPT['sequence']
INIT = next(a['variables'] for a in SEQ if 'cohorts' in a.get('variables',{}))
SELECT = next(a['variables']['bulbs'] for a in SEQ if 'bulbs' in a.get('variables',{}))
LOOP = next(a['repeat'] for a in SEQ if 'while' in a.get('repeat',{}))
DISPATCH = LOOP['sequence'][1]['repeat']['sequence'][0]
FRAME = DISPATCH['then'][0]['data']
PATTERNS = [p['value'] for p in SCRIPT['fields']['pattern']['selector']['select']['options']]

class AmbientPatterns(unittest.TestCase):
    render = base.Templates.render
    def setUp(self):
        base.Templates.setUp(self)
        self.lights[:] = [base.bulb('a',modes=['color_temp','hs']), base.bulb('b',modes=['color_temp','hs']), base.bulb('c',modes=['hs']), base.bulb('white'),base.bulb('off','off',['hs'])]
        self.attrs = {'supported_color_modes':['color_temp','hs'],'min_color_temp_kelvin':2000,'max_color_temp_kelvin':6500}
        self.env.globals['state_attr'] = lambda entity,attr:self.attrs.get(attr)
        self.env.globals['is_state'] = lambda entity,state:state=='on' and entity != 'light.off'
        self.env.tests['is_state'] = self.env.globals['is_state']

    def test_empty_selection_and_capability_filter(self):
        args=dict(requested=[],only_lit=True,excluded_lights=[],selected_pattern='aurora')
        self.assertEqual(self.render(SELECT,**args),[])
        args['requested']=['light.white','light.off','light.a']
        self.assertEqual(self.render(SELECT,**args),['light.a'])
        args['selected_pattern']='cloudlight'
        self.assertEqual(self.render(SELECT,**args),['light.white','light.a'])

    def test_fixture_pairs_share_position_and_optional_aurora_tint(self):
        args=dict(bulbs=['light.a','light.c','light.b'],ordered_ids=['light.c'],linked_pairs=[['light.a','light.b']],echo_tail_lights=[],selected_pattern='aurora',tint_spread=8)
        groups=self.render(INIT['cohorts'],**args)
        self.assertEqual([g['lights'] for g in groups],[['light.c'],['light.a'],['light.b']])
        self.assertEqual([g['position'] for g in groups],[0,1,1])
        self.assertEqual([g['tint'] for g in groups],[0,-4,4])
        args.update(selected_pattern='backyard_echo',echo_tail_lights=['light.c'])
        groups=self.render(INIT['cohorts'],**args)
        self.assertEqual(groups[-1]['lights'],['light.c'])
        self.assertTrue(all(g['tint']==0 for g in groups))

    def test_all_nine_patterns_have_bounded_changing_frames(self):
        self.assertEqual(len(PATTERNS),9)
        for pattern in PATTERNS:
            frames=[]
            for t in range(0,600,3):
                frame=self.render(FRAME,elapsed=t,cycle_phase=t%360,seed=1.2,dip_period=53,initial_hue=359,selected_pattern=pattern,repeat=NS(item=NS(position=2,tint=4,lights=['light.a'])))
                self.assertTrue((1 if pattern=='ice_breath' else 10)<=frame['brightness_pct']<=(100 if pattern=='ice_breath' else 85),(pattern,frame))
                if 'hs_color' in frame:
                    self.assertTrue(0<=frame['hs_color'][0]<360)
                    self.assertTrue(0<=frame['hs_color'][1]<=100)
                else:self.assertTrue(2000<=frame['color_temp_kelvin']<=6500)
                frames.append(str(frame))
            self.assertGreater(len(set(frames)),5,pattern)

    def test_paired_aurora_has_same_brightness_with_small_hue_difference(self):
        frames=[self.render(FRAME,elapsed=12,seed=1.2,dip_period=53,initial_hue=0,selected_pattern='aurora',repeat=NS(item=NS(position=0,tint=tint,lights=['light.a']))) for tint in [-4,4]]
        self.assertEqual(frames[0]['brightness_pct'],frames[1]['brightness_pct'])
        self.assertAlmostEqual(frames[1]['hs_color'][0]-frames[0]['hs_color'][0],8)

    def test_stop_deadline_and_off_bulbs_block_dispatch(self):
        args=dict(run_minutes=0,started=0,repeat=NS(item=NS(lights=['light.a'])))
        self.env.globals['now']=lambda:3600
        guard=DISPATCH['if'][0]['value_template']
        self.assertTrue(self.render(guard,**args))
        self.assertFalse(self.render(guard,**dict(args,run_minutes=1)))
        self.assertFalse(self.render(guard,**dict(args,repeat=NS(item=NS(lights=['light.off'])))))
        self.env.globals['is_state']=lambda entity,state:False
        self.assertFalse(self.render(guard,**args))

    def test_temperature_limits_and_white_only_fallback(self):
        args=dict(elapsed=12,seed=1.2,dip_period=53,initial_hue=0,selected_pattern='cloudlight',repeat=NS(item=NS(position=0,tint=0,lights=['light.a'])))
        self.attrs['min_color_temp_kelvin']=4000
        self.assertEqual(self.render(FRAME,**args)['color_temp_kelvin'],4000)
        self.attrs['supported_color_modes']=['brightness']
        self.assertEqual(list(self.render(FRAME,**args)),['brightness_pct'])

    def test_ice_breath_extremes_and_shared_frame(self):
        args=dict(elapsed=0,seed=1.2,dip_period=53,initial_hue=0,selected_pattern='ice_breath',repeat=NS(item=NS(position=0,tint=0,lights=['light.a','light.b'])))
        white=self.render(FRAME,cycle_phase=0,**args)
        blue=self.render(FRAME,cycle_phase=180,**args)
        self.assertEqual(white,{'brightness_pct':100,'hs_color':[240,0]})
        self.assertEqual(blue,{'brightness_pct':1,'hs_color':[240,100]})
        cohorts=self.render(INIT['cohorts'],bulbs=['light.a','light.b'],selected_pattern='ice_breath')
        self.assertEqual(cohorts,[{'lights':['light.a','light.b'],'position':0,'tint':0}])
        target=DISPATCH['then'][0]['target']['entity_id']
        self.assertEqual(self.render(target,repeat=NS(item=NS(lights=['light.a','light.off']))),['light.a'])
        self.assertEqual(self.render(LOOP['sequence'][-1]['delay']['milliseconds'],selected_pattern='ice_breath'),150)

if __name__=='__main__':unittest.main()
