"""Real server smoke test with a deterministic plugin; no GPU or network API."""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class HttpTests(unittest.TestCase):
    def test_loopback_api_and_custom_engine(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        config={'port':port,'seed':7,'solo_engine':'baseline','plugins':['plugins.planner_example'],
                'engines':{'baseline':{'provider':'planner-example','label':'Not AI','caption':'Test baseline','options':{}}}}
        code='import sys;sys.path.insert(0,sys.argv[1]);from app import run;import json;run(json.loads(sys.argv[2]))'
        process=subprocess.Popen([sys.executable,'-c',code,str(ROOT),json.dumps(config)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        base=f'http://127.0.0.1:{port}'
        def get(path):return json.load(urllib.request.urlopen(base+path,timeout=2))
        try:
            end=time.monotonic()+10
            while time.monotonic()<end:
                try:
                    state=get('/api/state')
                    if state['ready']:break
                except OSError:pass
                time.sleep(.05)
            self.assertTrue(state['ready'])
            html=urllib.request.urlopen(base).read().decode()
            token=re.search(r'name="app-token" content="([^"]+)"',html).group(1)
            def post(path,data,headers=None):
                request=urllib.request.Request(base+path,json.dumps(data).encode(),headers=headers or {'Content-Type':'application/json','X-App-Token':token})
                return json.load(urllib.request.urlopen(request))
            for headers in ({'Content-Type':'application/json'}, {'Content-Type':'application/json','X-App-Token':token,'Origin':'https://untrusted.example'}):
                with self.assertRaises(urllib.error.HTTPError) as error:post('/api/control',{'action':'step'},headers)
                self.assertEqual(error.exception.code,403)
            badhost=urllib.request.Request(base+'/',headers={'Host':'untrusted.example'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(badhost)
            self.assertEqual(error.exception.code,403)
            post('/api/control',{'action':'step'})
            for _ in range(100):
                state=get('/api/state')
                if state['game']['ticks']==1:break
                time.sleep(.01)
            self.assertEqual(state['game']['ticks'],1)
            self.assertEqual(state['engine']['id'],'baseline')
            post('/api/compare/control',{'action':'configure','limit':4})
            post('/api/compare/control',{'action':'start'})
            for _ in range(100):
                state=get('/api/compare/state')
                if not state['active']:break
                time.sleep(.01)
            self.assertEqual(state['lanes']['baseline']['game']['ticks'],4)
            post('/api/shutdown',{})
            process.wait(timeout=5)
            self.assertEqual(process.returncode,0)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':unittest.main()
