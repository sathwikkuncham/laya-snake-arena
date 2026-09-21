import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from settings import load_config
from jev_backend import JevBackend


class SettingsTests(unittest.TestCase):
    def test_precedence_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root=Path(directory)
            (root/'config.example.json').write_text(json.dumps({'executable':'bin/laya.exe','model':'models/base.gguf','port':8765,'device':'cuda'}))
            (root/'config.json').write_text(json.dumps({'model':'models/custom.gguf','port':9000}))
            (root/'.env').write_text('LAYA_PORT=9001\nTYPESAFE_API_KEY="test-value"\nUNRECOGNIZED=ignored\n')
            os.environ['LAYA_PORT']='9002'
            config=load_config(root)
            self.assertEqual(config['port'],9002)
            self.assertEqual(Path(config['model']),(root/'models/custom.gguf').resolve())
            self.assertEqual(os.environ['TYPESAFE_API_KEY'],'test-value')
            self.assertNotIn('UNRECOGNIZED',os.environ)

    def test_env_key_does_not_require_verdict(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY':'test-value'}, clear=True):
            client=JevBackend(None)
            self.assertIsNone(client._connection)
            client.close()

    def test_missing_key_is_actionable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'TYPESAFE_API_KEY'):
                JevBackend(None)

    def test_invalid_key_does_not_leak(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY':'private\r\nvalue'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'invalid format') as context:
                JevBackend(None)
            self.assertNotIn('private',str(context.exception))


if __name__=='__main__':
    unittest.main()
