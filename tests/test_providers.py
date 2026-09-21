import copy
import math
import unittest
from unittest.mock import patch

from providers import CheckedBackend, EngineRegistry, validate_response
from settings import DEFAULTS, validate_config
from compare import Comparison
from plugins.planner_example import PlannerExample
from test_compare import FakeSolo, wait


class ProvidersTests(unittest.TestCase):
    def test_third_provider_runs_without_controller_changes(self):
        config = copy.deepcopy(DEFAULTS)
        config.update({"model":"unused.gguf", "plugins":["plugins.planner_example"], "solo_engine":"baseline", "engines": {
            key: {"provider":"planner-example","label":key,"options":{}} for key in ("baseline","alternative","third")
        }})
        registry=EngineRegistry(validate_config(config))
        solo=FakeSolo()
        solo.registry,solo.engine_id=registry,"baseline"
        solo.backend=registry.create("baseline")
        compare=Comparison(solo,config)
        try:
            compare.command({"action":"configure","limit":8})
            compare.command({"action":"start"})
            wait(lambda:not compare.active)
            result=compare.snapshot()
            self.assertEqual(set(result["lanes"]),{"baseline","alternative","third"})
            for lane in result["lanes"].values():
                self.assertEqual(lane["game"]["ticks"],8)
                self.assertIsNone(lane["error"])
            self.assertNotIn("options",repr(result["engines"]))
        finally:
            compare.close();solo.backend.close()

    def test_invalid_probabilities_fail_before_execution(self):
        questions={"move":{"type":"choice","criteria":{"UP":"a","DOWN":"b"}}}
        for probabilities in ({"UP":float('nan'),"DOWN":0}, {"UP":.8,"DOWN":.8}, {"UP":True,"DOWN":0}, {"LEFT":1}):
            with self.assertRaises(ValueError):
                validate_response({"answers":{"move":{"type":"choice","probabilities":probabilities}},"usage":{"input_tokens":1}},questions)

    def test_custom_exception_never_exposes_its_contents(self):
        class Broken:
            def predict(self,*_):raise RuntimeError("private-api-key")
            def close(self):pass
        with self.assertRaises(RuntimeError) as error:
            CheckedBackend(Broken()).predict("",{})
        self.assertNotIn("private-api-key",str(error.exception))

    def test_public_metadata_excludes_options(self):
        config={"engines":{"example":{"provider":"typesafe","label":"Example","options":{"api_key":"private-api-key"}}}}
        self.assertNotIn("private-api-key",repr(EngineRegistry(config).public("example")))

    def test_config_validates_board_and_engine_identifiers(self):
        for patch_value in ({"width":5,"height":5},{"initial_length":1000},{"fps":float('nan')},{"comparison_limit":1001},{"solo_engine":"missing"},{"engines":{"bad<script>":{"provider":"ggmlc"}}}):
            config=copy.deepcopy(DEFAULTS);config.update(patch_value)
            with self.assertRaises(ValueError):validate_config(config)


if __name__=='__main__':unittest.main()
