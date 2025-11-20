from typing import Dict
from graph.state import State

def flight_node(state: State) -> Dict:
    return {
        "flight_options": state.get("flight_options") or [],
        "needs_refresh": False,
    }
