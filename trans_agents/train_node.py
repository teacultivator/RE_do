from typing import Dict
from graph.state import State

def train_node(state: State) -> Dict:
    return {
        "train_options": state.get("train_options") or [],
        "needs_refresh": False,
    }
