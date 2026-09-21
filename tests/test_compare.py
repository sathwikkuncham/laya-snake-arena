import sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare import Comparison

class FakeBackend:
    def __init__(self,delay=.002,fail=False):
        self.delay=delay;self.fail=fail;self.calls=0;self.reported_model='test-only';self.closed=False
    def predict(self,state,questions):
        self.calls+=1
        time.sleep(self.delay)
        if self.fail: raise RuntimeError('TypeSafe rate limit reached.')
        labels=questions['move']['criteria']
        best=next((k for k,v in labels.items() if 'Best' in v),next(iter(labels)))
        return {'answers':{'move':{'type':'choice','probabilities':{k:float(k==best) for k in labels}},'risk':{'type':'noul','noul':1},'food':{'type':'noul','noul':1}},'usage':{'input_tokens':10,'output_tokens':0}}
    def close(self): self.closed=True

class FakeSolo:
    ready=True;error=None;busy=False;hardware='test'
    def __init__(self): self.backend=FakeBackend();self.paused=False
    def command(self,_): self.paused=True

def wait(predicate):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.005)
    raise AssertionError('Timed out')

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.c=Comparison(FakeSolo(),{'model':'test.gguf','jev_settings':'unused','seed':7})
    def tearDown(self): self.c.close()
    def test_laya_only_does_not_acquire_credentials(self):
        with patch('providers.JevBackend',side_effect=AssertionError('No cloud client expected')):
            self.c.command({'action':'configure','mode':'laya','limit':5})
            self.c.command({'action':'start'})
            wait(lambda:not self.c.active)
        self.assertEqual(self.c.snapshot()['lanes']['laya']['game']['ticks'],5)
        self.assertEqual(self.c.snapshot()['lanes']['jev']['game']['ticks'],0)
    def test_pause_resume_continuity_and_independent_completion(self):
        cloud=FakeBackend(.03)
        with patch('providers.JevBackend',side_effect=lambda *args: cloud):
            self.c.command({'action':'configure','mode':'both','limit':6})
            self.c.command({'action':'start'})
            wait(lambda:self.c.snapshot()['lanes']['laya']['game']['ticks']==6)
            with self.assertRaises(ValueError):self.c.command({'action':'configure','seed':2})
            self.c.command({'action':'pause'})
            wait(lambda:not self.c.active)
            paused=self.c.snapshot()
            elapsed=paused['lanes']['laya']['elapsed_s']
            time.sleep(.04)
            self.assertEqual(self.c.snapshot()['lanes']['laya']['elapsed_s'],elapsed)
            self.c.command({'action':'start'})
            wait(lambda:not self.c.active)
        self.assertEqual(self.c.solo.backend.calls,6)
        self.assertEqual(cloud.calls,6)
        for lane in self.c.export()['frames'].values():
            self.assertEqual(len(lane),6)
            for a,b in zip(lane,lane[1:]):self.assertEqual(a['after'],b['before'])
    def test_cloud_error_stops_without_automatic_retries(self):
        cloud=FakeBackend(.002,True)
        with patch('providers.JevBackend',return_value=cloud):
            self.c.command({'action':'start'})
            wait(lambda:not self.c.active)
        self.assertEqual(cloud.calls,1)
        self.assertIn('rate limit',self.c.snapshot()['lanes']['jev']['error'])
        self.assertTrue(cloud.closed)
    def test_bad_config_rejected_without_mutation(self):
        for values in ({'mode':'fake'},{'seed':True},{'limit':0},{'limit':2000},{'guarded':'false'}):
            with self.assertRaises(ValueError):self.c.command({'action':'configure',**values})
        self.assertEqual(self.c.seed,7)
        self.assertEqual(self.c.limit,300)

if __name__ == '__main__':
    unittest.main()
