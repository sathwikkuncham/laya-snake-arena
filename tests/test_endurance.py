import copy
import unittest
from unittest.mock import patch

from board_policy import BoardPolicy
from compare import Comparison
from upstream.game import SnakeGame
from test_compare import FakeBackend, FakeSolo, wait


class FixedDirection:
    def __init__(self, direction):self.direction=direction;self.calls=0;self.closed=False
    def predict(self,state,questions):
        self.calls+=1
        return {'answers':{
            'move':{'type':'choice','probabilities':{d:float(d==self.direction) for d in ('UP','DOWN','LEFT','RIGHT')}},
            'risk':{'type':'noul','noul':.5},'food':{'type':'noul','noul':.5}},
            'usage':{'input_tokens':100,'output_tokens':0}}
    def close(self):self.closed=True


class EnduranceTests(unittest.TestCase):
    def test_raw_board_has_no_planner_calls_or_move_corrections(self):
        game=SnakeGame(seed=0)
        with patch.object(game,'moves',side_effect=AssertionError('Planner must not be used')),patch.object(game,'food_reachability',side_effect=AssertionError('Planner must not be used')):
            state,questions=BoardPolicy.request(game)
            decision=BoardPolicy(FixedDirection('LEFT')).decide(game)
        self.assertIn('H',state);self.assertIn('T',state);self.assertIn('F',state)
        self.assertNotIn('Best route',str(questions))
        self.assertNotIn('Slower route',str(questions))
        self.assertEqual(decision.proposed,decision.executed)
        self.assertEqual(decision.executed,'LEFT')
        self.assertFalse(decision.intervened)
        self.assertIsNone(decision.planner_best)
        game.step(decision.executed)
        self.assertFalse(game.alive)
        self.assertEqual(game.death_reason,'reverse')

    def test_endurance_ignores_budget_stops_at_wall_and_bounds_recording(self):
        solo=FakeSolo();solo.backend=FixedDirection('RIGHT')
        c=Comparison(solo,{'model':'unused','comparison_limit':1,'max_recorded_moves':3})
        try:
            c.command({'action':'configure','mode':'laya','stop_condition':'endurance','observation':'board','guarded':True,'limit':999999})
            self.assertFalse(c.guarded)
            c.command({'action':'start'});wait(lambda:not c.active)
            lane=c.snapshot()['lanes']['laya']
            self.assertGreater(lane['game']['ticks'],1)
            self.assertEqual(lane['state'],'game_over')
            self.assertEqual(lane['termination_reason'],'wall')
            self.assertEqual(lane['interventions'],0)
            frames=c.export()['frames']['laya']
            self.assertEqual(len(frames),3)
            self.assertEqual(frames[-1]['after']['ticks'],lane['game']['ticks'])
        finally:c.close()

    def test_one_snake_death_does_not_stop_other_lane(self):
        solo=FakeSolo();solo.backend=FixedDirection('LEFT')
        second=FixedDirection('RIGHT')
        c=Comparison(solo,{'model':'unused','jev_settings':None})
        try:
            with patch('providers.JevBackend',return_value=second):
                c.command({'action':'configure','stop_condition':'endurance','observation':'board'})
                c.command({'action':'start'});wait(lambda:not c.active)
            lanes=c.snapshot()['lanes']
            self.assertEqual(lanes['laya']['game']['ticks'],1)
            self.assertGreater(lanes['jev']['game']['ticks'],1)
            self.assertEqual(lanes['laya']['termination_reason'],'reverse')
            self.assertEqual(lanes['jev']['termination_reason'],'wall')
        finally:c.close()

    def test_endurance_can_cross_previous_1000_move_cap(self):
        solo=FakeSolo();solo.backend=FakeBackend(delay=0)
        c=Comparison(solo,{'model':'unused','comparison_limit':1,'max_recorded_moves':2})
        try:
            c.command({'action':'configure','mode':'laya','stop_condition':'endurance','observation':'planner'})
            c.lanes['laya']['game'].ticks=1000
            c.command({'action':'start'})
            wait(lambda:c.snapshot()['lanes']['laya']['game']['ticks']>=1002 or not c.active)
            c.command({'action':'pause'});wait(lambda:not c.active)
            self.assertGreaterEqual(c.snapshot()['lanes']['laya']['game']['ticks'],1002)
            self.assertLessEqual(len(c.export()['frames']['laya']),2)
        finally:c.close()

    def test_full_board_is_a_win_not_an_error(self):
        solo=FakeSolo();solo.backend=FixedDirection('RIGHT')
        c=Comparison(solo,{'model':'unused'})
        try:
            c.command({'action':'configure','mode':'laya','stop_condition':'endurance'})
            # The completed board is terminal without asking the provider for another move.
            c.lanes['laya']['game'].won=True
            c.command({'action':'start'});wait(lambda:not c.active)
            self.assertEqual(c.snapshot()['lanes']['laya']['termination_reason'],'board_filled')
            self.assertEqual(solo.backend.calls,0)
        finally:c.close()

    def test_teardown_time_is_excluded_from_survival(self):
        clock={'now':0.0}
        class ClosingBackend(FixedDirection):
            def close(self):clock['now']+=100
        c=Comparison(FakeSolo(),{'model':'unused','jev_settings':None})
        try:
            with patch('providers.JevBackend',return_value=ClosingBackend('LEFT')),patch('compare.time.perf_counter',side_effect=lambda:clock['now']):
                c.command({'action':'configure','mode':'jev','stop_condition':'endurance'})
                c.command({'action':'start'});wait(lambda:not c.active)
                self.assertEqual(c.snapshot()['lanes']['jev']['elapsed_s'],0)
        finally:c.close()


if __name__=='__main__':unittest.main()
