"""Raw-board decisions without planner hints, admissibility filtering, or overrides."""
import time

from providers import validate_response
from upstream.game import DIRECTIONS
from upstream.policy import Decision


class BoardPolicy:
    def __init__(self, agent):
        self.agent = agent

    @staticmethod
    def request(game):
        cells = [["." for _ in range(game.width)] for _ in range(game.height)]
        for x, y in game.body:
            cells[y][x] = "B"
        tx, ty = game.body[-1]
        cells[ty][tx] = "T"
        hx, hy = game.head
        cells[hy][hx] = "H"
        if game.food is not None:
            fx, fy = game.food
            cells[fy][fx] = "F"
        state = (
            f"Snake board: {game.width} columns, {game.height} rows. "
            "H=head, B=body, T=tail, F=food, .=empty. Rows run top to bottom.\n"
            + "\n".join("".join(row) for row in cells)
        )
        questions = {
            "move": {
                "type": "choice",
                "instructions": (
                    "Choose the next move to eat food and survive. Move one cell. "
                    "Moving outside the board or into body, including reversing into the neck, ends the game. "
                    "Eating food grows the snake; otherwise the tail vacates its cell."
                ),
                "criteria": {"UP": "One cell toward the top.", "DOWN": "One cell toward the bottom.",
                             "LEFT": "One cell to the left.", "RIGHT": "One cell to the right."},
            },
            "risk": {"type": "noul", "instructions": "Does the head have a next move that avoids an immediate collision?"},
            "food": {"type": "noul", "instructions": "Is food reachable through the currently empty cells from the head?"},
        }
        return state, questions

    def decide(self, game):
        started = time.perf_counter()
        state, questions = self.request(game)
        inference_start = time.perf_counter()
        output = validate_response(self.agent.predict(state, questions), questions)
        inference_ms = (time.perf_counter() - inference_start) * 1000
        answers = output["answers"]
        probabilities = answers["move"]["probabilities"]
        proposed = max(DIRECTIONS, key=probabilities.__getitem__)
        return Decision(
            probabilities=probabilities, proposed=proposed, executed=proposed,
            safe_directions=None, intervened=False,
            dead_end_risk=1-answers["risk"]["noul"], food_reachable=answers["food"]["noul"],
            inference_ms=inference_ms, decision_ms=(time.perf_counter()-started)*1000,
            input_tokens=output["usage"]["input_tokens"], output_tokens=output["usage"].get("output_tokens",0),
            safe_count=None, planner_best=None,
        )
