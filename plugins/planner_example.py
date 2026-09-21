"""A deterministic integration example, explicitly NOT a trained AI model."""


class PlannerExample:
    reported_model = "planner-baseline-not-ai"
    hardware = "Deterministic CPU rules (not AI)"

    def predict(self, state, questions):
        answers = {}
        for qid, question in questions.items():
            if question["type"] == "choice":
                labels = question["criteria"]
                chosen = next((k for k, v in labels.items() if "Best" in v), next(iter(labels)))
                answers[qid] = {"type": "choice", "choice": chosen,
                                "probabilities": {k: float(k == chosen) for k in labels}}
            else:
                # Demo integration logic for the original compact prompt only.
                phrase = "Safe route: yes" if qid == "risk" else "Food reachable through empty cells: yes"
                answers[qid] = {"type": "noul", "noul": float(phrase in str(state))}
        return {"model": self.reported_model, "answers": answers,
                "usage": {"input_tokens": 0, "output_tokens": 0}}

    def close(self):
        pass


def register(registry):
    registry.register("planner-example", lambda options, config: PlannerExample())
